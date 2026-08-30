"""Bounded in-memory follow-ups; only server-owned analysis may become a proposal."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from threading import RLock
from uuid import uuid4

from agents.schemas import IssueAnalysis, TextConsultationInput
from agents.text_assistant import DeepSeekTextBackend, MockTextBackend, TextAssistant, TextConfig, TextError, TextReply
from agents.tools import ToolAuditLog, ToolResult
from backend.app.proposals import Phase2ProposalService, ProposalPreviewRequest
from backend.app.text_models import TextProposalRequest, TextRequest, TextResponse

WORKFLOW_CATEGORIES = {"safety", "quality", "management", "logistics"}


def text_config() -> TextConfig:
    return TextConfig(api_key=os.getenv("LLM_API_KEY", ""), model=os.getenv("LLM_MODEL", "").strip(),
                      base_url=os.getenv("LLM_BASE_URL", "").strip())


def text_runtime() -> dict[str, object]:
    mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
    if mode == "mock":
        return {"mode": "mock", "model": "mock-no-text-understanding", "configured": True, "external_provider": None}
    config = text_config()
    try:
        config.validate()
        configured = mode == "real"
    except TextError:
        configured = False
    return {"mode": "real", "model": config.model if configured else "not-configured",
            "configured": configured, "external_provider": "DeepSeek"}


def default_text_assistant(mode: str) -> TextAssistant:
    return TextAssistant(MockTextBackend() if mode == "mock" else DeepSeekTextBackend(text_config()))


def apply_boundaries(reply: TextReply, previous: TextReply | None) -> tuple[TextReply, bool]:
    payload = reply.model_dump(mode="json")
    analysis = payload["analysis"]
    retained = previous is not None and previous.analysis.risk_level in {"high", "emergency"}
    if retained:
        old = previous.analysis
        analysis["risk_level"] = "emergency" if "emergency" in {old.risk_level, analysis["risk_level"]} else "high"
        analysis["immediate_actions"] = list(dict.fromkeys([*old.immediate_actions, *analysis["immediate_actions"]]))[:10]
        payload["answer"] = "同一问题此前已触发高风险提示，补充描述不能视为风险解除。请继续遵循避险要求，由现场专业人员复核；系统不会自动认定安全或关闭问题。"
    if analysis["risk_level"] in {"high", "emergency"}:
        analysis["requires_human_review"] = True
        analysis["recommended_route"] = "human_review"
    elif analysis["missing_fields"] or analysis["category"] == "unknown":
        analysis["requires_human_review"] = True
        analysis["recommended_route"] = "collect_more_info"
    elif analysis["category"] == "consultation":
        analysis["recommended_route"] = "direct_answer"
    return TextReply.model_validate_json(TextReply(**{**payload, "analysis": IssueAnalysis(**analysis)}).model_dump_json(), strict=True), retained


def can_propose(reply: TextReply) -> bool:
    return (reply.analysis.category in WORKFLOW_CATEGORIES
            and reply.analysis.recommended_route in {"propose_workflow", "human_review"})


def quick_chat_reply(answer: str) -> TextReply:
    return TextReply(
        answer=answer,
        follow_up_questions=["如涉及具体现场风险，请切换到“新建咨询”并补充位置、状态和人员暴露情况。"],
        analysis=IssueAnalysis(
            category="unknown",
            issue_type="日常聊天（未执行结构化风险分析）",
            summary="日常聊天使用轻量模型直接回答，不执行现场风险结构化分析，也不进入工单流程。",
            observed_facts=[],
            uncertainties=["日常聊天模式未执行现场风险结构化分析"],
            missing_fields=["如涉及具体现场风险，需切换到专业咨询并补充现场信息"],
            risk_level="undetermined",
            immediate_actions=[],
            suggested_actions=["涉及现场风险时请使用专业咨询，并由现场专业人员核验"],
            recommended_route="collect_more_info",
            requires_human_review=True,
            confidence=0.0,
        ),
    )


def default_quick_answerer(mode: str, inputs: list[TextConsultationInput], current: date,
                           previous_answer: str | None) -> str:
    if mode == "mock":
        return "Mock模式未调用真实模型，仅用于验证日常聊天界面。"
    return DeepSeekTextBackend(text_config()).answer_brief(inputs, current, previous_answer)


@dataclass
class _Session:
    updated: float
    intent: str = "consult"
    inputs: list[TextConsultationInput] = field(default_factory=list)
    responses: dict[str, tuple[str, TextResponse]] = field(default_factory=dict)
    latest: TextResponse | None = None
    proposal: ToolResult | None = None


class TextConsultationService:
    def __init__(self, proposals: Phase2ProposalService, *,
                 assistant_factory: Callable[[str], TextAssistant] = default_text_assistant,
                 clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = date.today,
                 quick_answerer: Callable[[str, list[TextConsultationInput], date, str | None], str] = default_quick_answerer) -> None:
        self.proposals, self.assistant_factory = proposals, assistant_factory
        self.clock, self.today, self.quick_answerer = clock, today, quick_answerer
        self._sessions: dict[str, _Session] = {}
        self._lock = RLock()
        self.audit = ToolAuditLog()

    def _expire(self) -> None:
        now = self.clock()
        for key in [key for key, value in self._sessions.items() if now - value.updated >= 1800]:
            del self._sessions[key]

    def _session(self, key: str, turn: int) -> _Session:
        session = self._sessions.get(key)
        if session is None:
            raise TextError("consultation_expired", "咨询不存在或已过期；请开始新问题，已有工单不受影响。", 404)
        if len(session.inputs) != turn:
            raise TextError("text_turn_conflict", "咨询已更新，请使用最新结果或开始新问题。", 409)
        return session

    def send(self, request: TextRequest) -> TextResponse:
        started = time.monotonic()
        try:
            response = self._send(request)
        except TextError as exc:
            self._audit(request, False, exc.code, started)
            raise
        self._audit(request, True, None, started)
        return response

    def _audit(self, request: TextRequest, ok: bool, code: str | None, started: float) -> None:
        self.audit.record(tool_name="text_consultation", arguments={"request_id": request.request_id}, result=ToolResult(
            tool_name="text_consultation", ok=ok, error_code=code, recoverable=not ok,
            summary=f"文字请求{'完成' if ok else '失败'}；耗时{round(time.monotonic() - started, 2)}秒；无业务状态变化。"))

    def _send(self, request: TextRequest) -> TextResponse:
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self._lock:
            self._expire()
            for session in self._sessions.values():
                previous = session.responses.get(request.request_id)
                if previous:
                    if previous[0] != digest:
                        raise TextError("text_request_conflict", "同一请求标识不能用于不同内容。", 409)
                    return previous[1].model_copy(deep=True)
            runtime = text_runtime()
            if runtime["mode"] == "real" and not request.allow_external:
                raise TextError("text_consent_required", "请确认本次将问题及本会话用户补充发送至DeepSeek并承担费用。", 403)
            if not runtime["configured"]:
                raise TextError("text_configuration_error", "文字模型未正确配置，请核对本地配置。")
            if request.consultation_id:
                session = self._session(request.consultation_id, request.expected_turn)
                if session.intent != request.intent:
                    raise TextError("text_intent_conflict", "聊天与专业咨询不能共用同一会话，请开始新问题。", 409)
                if session.proposal is not None:
                    raise TextError("consultation_proposed", "已生成提案，请在工单中补充；其他问题请新建咨询。", 409)
                if len(session.inputs) >= 6:
                    raise TextError("text_turn_limit", "本问题已达6轮上限，请人工核对或开始新问题。", 409)
                consultation_id = request.consultation_id
            else:
                if len(self._sessions) >= 200:
                    raise TextError("text_capacity_limit", "本地咨询容量已满，请稍后重试。", 503)
                session = _Session(updated=self.clock(), intent=request.intent)
                consultation_id = "TXT-" + uuid4().hex
            inputs = [*session.inputs, request.input]
            if request.intent == "chat":
                reply = quick_chat_reply(self.quick_answerer(
                    str(runtime["mode"]), inputs, self.today(), session.latest.reply.answer if session.latest else None))
                retained, response_model = False, str(runtime["model"])
            else:
                reply = self.assistant_factory(str(runtime["mode"])).reply(
                    inputs, previous_questions=session.latest.reply.follow_up_questions if session.latest else None)
                reply, retained = apply_boundaries(reply, session.latest.reply if session.latest else None)
                response_model = str(runtime["model"])
            response = TextResponse(consultation_id=consultation_id, turn=len(inputs), mode=runtime["mode"],
                                    model=response_model, reply=reply, can_propose=can_propose(reply),
                                    risk_retained=retained, remaining_turns=6 - len(inputs))
            session.inputs, session.latest, session.updated = inputs, response, self.clock()
            session.responses[request.request_id] = (digest, response)
            self._sessions[consultation_id] = session
            return response.model_copy(deep=True)

    def propose(self, consultation_id: str, request: TextProposalRequest) -> ToolResult:
        with self._lock:
            self._expire()
            session = self._session(consultation_id, request.expected_turn)
            if session.proposal is not None:
                return session.proposal.model_copy(deep=True)
            if session.latest is None or not session.latest.can_propose:
                raise TextError("text_not_proposable", "当前仅咨询或信息不足，不能生成问题提案。", 409)
            result = self.proposals.preview(ProposalPreviewRequest(
                invocation_id="text-" + uuid4().hex, analysis=session.latest.reply.analysis))
            if not result.ok:
                raise TextError("text_proposal_failed", "提案暂时生成失败，可手动重试。")
            session.proposal, session.updated = result, self.clock()
            return result.model_copy(deep=True)
