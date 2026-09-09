"""Bounded in-memory follow-ups; only server-owned analysis may become a proposal."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from threading import RLock
from uuid import uuid4

from agents.schemas import IssueAnalysis, TextConsultationInput
from agents.text_assistant import (
    DeepSeekTextBackend, MockTextBackend, TencentTokenPlanTextBackend, TextAssistant,
    TextConfig, TextError, TextReply, ChatReply, select_chat_context,
    TEXT_PROVIDER_DEEPSEEK, TEXT_PROVIDER_TENCENT_TOKEN_PLAN,
    TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL, text_provider_label,
)
from agents.chat_settings import CHAT_MAX_TURNS, CHAT_SESSION_CHARS, CHAT_HISTORY_PAIRS, CHAT_CONTEXT_CHARS
from agents.tools import ToolAuditLog, ToolResult
from backend.app.proposals import Phase2ProposalService, ProposalPreviewRequest
from backend.app.text_models import TextProposalRequest, TextRequest, TextResponse
from backend.app.text_progress import ProgressSink, ignore_progress

WORKFLOW_CATEGORIES = {"safety", "quality", "management", "logistics"}


def text_provider() -> str:
    return os.getenv("LLM_PROVIDER", TEXT_PROVIDER_DEEPSEEK).strip().casefold()


def text_config(model: str | None = None) -> TextConfig:
    provider = text_provider()
    if provider == TEXT_PROVIDER_TENCENT_TOKEN_PLAN:
        configured_model = os.getenv("TENCENT_TOKEN_PLAN_MODEL", "").strip() or os.getenv("LLM_MODEL", "").strip()
        return TextConfig(
            api_key=os.getenv("TENCENT_TOKEN_PLAN_API_KEY", ""),
            model=(model or configured_model).strip(),
            base_url=(os.getenv("TENCENT_TOKEN_PLAN_BASE_URL", "").strip()
                      or TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL),
            provider=TEXT_PROVIDER_TENCENT_TOKEN_PLAN,
        )
    return TextConfig(api_key=os.getenv("LLM_API_KEY", ""), model=(model or os.getenv("LLM_MODEL", "")).strip(),
                      base_url=os.getenv("LLM_BASE_URL", "").strip(),
                      provider=TEXT_PROVIDER_DEEPSEEK)


def text_model_options() -> list[str]:
    provider = text_provider()
    extras = [item.strip() for item in os.getenv("LLM_MODEL_OPTIONS", "").split(",")]
    if provider == TEXT_PROVIDER_TENCENT_TOKEN_PLAN:
        configured = (os.getenv("TENCENT_TOKEN_PLAN_MODEL", "").strip()
                      or os.getenv("LLM_MODEL", "").strip())
        provider_options = [item.strip() for item in os.getenv(
            "TENCENT_TOKEN_PLAN_MODEL_OPTIONS", "").split(",")]
        candidates = [configured, *provider_options, *extras]
    else:
        configured = os.getenv("LLM_MODEL", "").strip()
        candidates = [configured, "deepseek-v4-flash", "deepseek-v4-pro", *extras]
    return list(dict.fromkeys(item for item in candidates if item))


def text_runtime() -> dict[str, object]:
    mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
    if mode == "mock":
        return {"mode": "mock", "model": "mock-no-text-understanding", "configured": True,
                "external_provider": None, "available_models": ["mock-no-text-understanding"],
                "custom_model_allowed": False, "provider": None}
    config = text_config()
    provider = text_provider()
    try:
        config.validate()
        configured = mode == "real"
    except TextError:
        configured = False
    return {"mode": "real", "model": config.model if configured else "not-configured",
            "configured": configured, "external_provider": text_provider_label(provider),
            "provider": provider,
            "available_models": text_model_options() if configured else [],
            "custom_model_allowed": configured}


def default_text_assistant(mode: str, model: str) -> TextAssistant:
    if mode == "mock":
        return TextAssistant(MockTextBackend())
    config = text_config(model)
    backend = (TencentTokenPlanTextBackend(config)
               if config.provider == TEXT_PROVIDER_TENCENT_TOKEN_PLAN
               else DeepSeekTextBackend(config))
    return TextAssistant(backend)


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
    reply_model = ChatReply if isinstance(reply, ChatReply) else TextReply
    bounded = reply_model(**{**payload, "analysis": IssueAnalysis(**analysis)})
    return reply_model.model_validate_json(bounded.model_dump_json(), strict=True), retained


def can_propose(reply: TextReply) -> bool:
    return (reply.analysis.category in WORKFLOW_CATEGORIES
            and reply.analysis.recommended_route in {"propose_workflow", "human_review"})


def quick_chat_reply(answer: str) -> ChatReply:
    return ChatReply(
        answer=answer,
        follow_up_questions=["如涉及具体现场风险，请切换到“新建咨询”并补充位置、状态和人员暴露情况。"],
        analysis=IssueAnalysis(
            category="unknown",
            issue_type="日常聊天（未执行结构化风险分析）",
            summary="日常聊天启用深度思考，不执行现场风险结构化分析，也不进入工单流程。",
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


def default_quick_answerer(mode: str, model: str, inputs: list[TextConsultationInput], current: date,
                           previous_answers: list[str]) -> str:
    if mode == "mock":
        return "Mock模式未调用真实模型，仅用于验证日常聊天界面。"
    config = text_config(model)
    backend = (TencentTokenPlanTextBackend(config)
               if config.provider == TEXT_PROVIDER_TENCENT_TOKEN_PLAN
               else DeepSeekTextBackend(config))
    return backend.answer_brief(inputs, current, previous_answers)


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
                 assistant_factory: Callable[[str, str], TextAssistant] = default_text_assistant,
                 clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = date.today,
                 quick_answerer: Callable[[str, str, list[TextConsultationInput], date, list[str]], str] = default_quick_answerer) -> None:
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

    @contextmanager
    def _operation(self, progress: ProgressSink):
        progress("queued", None)
        if not self._lock.acquire(timeout=1):
            raise TextError("text_busy", "文字服务繁忙，前一次请求可能仍在运行；请稍后手动重试。", 429)
        try:
            progress("preparing", None)
            yield
        finally:
            self._lock.release()

    def send(self, request: TextRequest, *, progress: ProgressSink = ignore_progress) -> TextResponse:
        started = time.monotonic()
        try:
            response = self._send(request, progress)
        except TextError as exc:
            self._audit(request, False, exc.code, started)
            raise
        self._audit(request, True, None, started)
        progress("completed", None)
        return response

    def _audit(self, request: TextRequest, ok: bool, code: str | None, started: float) -> None:
        self.audit.record(tool_name="text_consultation", arguments={"request_id": request.request_id}, result=ToolResult(
            tool_name="text_consultation", ok=ok, error_code=code, recoverable=not ok,
            summary=f"文字请求{'完成' if ok else '失败'}；耗时{round(time.monotonic() - started, 2)}秒；无业务状态变化。"))

    def _send(self, request: TextRequest, progress: ProgressSink) -> TextResponse:
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self._operation(progress):
            self._expire()
            for session in self._sessions.values():
                previous = session.responses.get(request.request_id)
                if previous:
                    if previous[0] != digest:
                        raise TextError("text_request_conflict", "同一请求标识不能用于不同内容。", 409)
                    return previous[1].model_copy(deep=True)
            runtime = text_runtime()
            if runtime["mode"] == "real" and not request.allow_external:
                provider_name = str(runtime.get("external_provider") or "模型服务")
                raise TextError(
                    "text_consent_required",
                    f"请确认本次将问题及本会话用户补充发送至{provider_name}并承担费用。",
                    403,
                )
            if not runtime["configured"]:
                raise TextError("text_configuration_error", "文字模型未正确配置，请核对本地配置。")
            selected_model = str(runtime["model"])
            if runtime["mode"] == "real" and request.model:
                text_config(request.model).validate()
                selected_model = request.model
            if request.consultation_id:
                session = self._session(request.consultation_id, request.expected_turn)
                if session.intent != request.intent:
                    raise TextError("text_intent_conflict", "聊天与专业咨询不能共用同一会话，请开始新问题。", 409)
                if session.proposal is not None:
                    raise TextError("consultation_proposed", "已生成提案，请在工单中补充；其他问题请新建咨询。", 409)
                limit = CHAT_MAX_TURNS if request.intent in {"chat", "auto"} else 6
                if len(session.inputs) >= limit:
                    raise TextError("text_turn_limit", f"本会话已达{limit}轮上限，请开始新问题。", 409)
                consultation_id = request.consultation_id
            else:
                if len(self._sessions) >= 200:
                    raise TextError("text_capacity_limit", "本地咨询容量已满，请稍后重试。", 503)
                session = _Session(updated=self.clock(), intent=request.intent)
                consultation_id = "TXT-" + uuid4().hex
            inputs = [*session.inputs, request.input]
            context_trimmed = False
            if request.intent == "chat":
                # Reuse committed responses: failures and idempotent replays add no history.
                completed = sorted((response for _, response in session.responses.values()), key=lambda response: response.turn)
                answers = [response.reply.answer for response in completed]
                if sum(len(item.model_dump_json()) for item in inputs) + sum(map(len, answers)) > CHAT_SESSION_CHARS:
                    raise TextError("chat_capacity_limit", "本会话内容已达到容量上限，请开始新问题；已有消息未删除。", 409)
                selected_inputs, selected_answers, context_trimmed = select_chat_context(inputs, answers)
                progress("model_running", None)
                answer = self.quick_answerer(
                    str(runtime["mode"]), selected_model, selected_inputs, self.today(), selected_answers)
                progress("validating", None)
                reply = quick_chat_reply(answer)
                retained, response_model = False, selected_model
            else:
                selected_inputs = inputs
                if request.intent == "auto":
                    if sum(len(item.model_dump_json()) for item in inputs) > CHAT_SESSION_CHARS:
                        raise TextError("chat_capacity_limit", "本会话内容已达到容量上限，请开始新问题；已有消息未删除。", 409)
                    size, start = 0, len(inputs) - 1
                    for index in range(len(inputs) - 1, max(-1, len(inputs) - CHAT_HISTORY_PAIRS - 1), -1):
                        item_size = len(inputs[index].model_dump_json())
                        if size and size + item_size > CHAT_CONTEXT_CHARS:
                            break
                        size += item_size
                        start = index
                    selected_inputs = inputs[start:]
                    context_trimmed = start > 0
                progress("model_running", None)
                reply = self.assistant_factory(str(runtime["mode"]), selected_model).reply(
                    selected_inputs, previous_questions=session.latest.reply.follow_up_questions if session.latest else None,
                    unified=request.intent == "auto")
                progress("validating", None)
                reply, retained = apply_boundaries(reply, session.latest.reply if session.latest else None)
                response_model = selected_model
            response = TextResponse(consultation_id=consultation_id, turn=len(inputs), mode=runtime["mode"],
                                    model=response_model, reply=reply, can_propose=can_propose(reply),
                                    risk_retained=retained, remaining_turns=(CHAT_MAX_TURNS if request.intent in {"chat", "auto"} else 6) - len(inputs),
                                    context_trimmed=context_trimmed)
            session.inputs, session.latest, session.updated = inputs, response, self.clock()
            session.responses[request.request_id] = (digest, response)
            self._sessions[consultation_id] = session
            return response.model_copy(deep=True)

    def propose(self, consultation_id: str, request: TextProposalRequest,
                *, progress: ProgressSink = ignore_progress) -> ToolResult:
        with self._operation(progress):
            self._expire()
            session = self._session(consultation_id, request.expected_turn)
            if session.proposal is not None:
                progress("completed", None)
                return session.proposal.model_copy(deep=True)
            if session.latest is None or not session.latest.can_propose:
                raise TextError("text_not_proposable", "当前仅咨询或信息不足，不能生成问题提案。", 409)
            progress("tool_running", "propose_issue_record")
            result = self.proposals.preview(ProposalPreviewRequest(
                invocation_id="text-" + uuid4().hex, analysis=session.latest.reply.analysis))
            if not result.ok:
                raise TextError("text_proposal_failed", "提案暂时生成失败，可手动重试。")
            session.proposal, session.updated = result, self.clock()
            progress("completed", None)
            return result.model_copy(deep=True)
