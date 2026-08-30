"""Image application boundary: explicit external consent, human decisions, links."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from agents.schemas import IssueAnalysis
from agents.tools import ToolAuditLog, ToolResult
from agents.vision import (
    DeepSeekVisionBackend, MockVisionBackend, SingleImageAnalyzer, VisionConfig, VisionError,
)
from backend.app.photo_models import (
    AnalyzePhotoRequest, CandidateDecision, CandidateDecisionRequest, LinkPhotoRequest,
    PhotoAnalysisRecord, PhotoDocument, PhotoLink,
)
from backend.app.photo_store import PhotoError, PhotoStore
from backend.app.proposals import Phase2ProposalService, ProposalPreviewRequest
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_models import ActorRole, RecordDisposition, WorkflowStatus


def runtime_vision_info() -> dict[str, object]:
    mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
    mode = "real" if mode == "real" else "mock"
    model = os.getenv("VISION_MODEL", "").strip()
    if mode == "mock":
        return {"mode": mode, "model": "mock-no-image-recognition", "configured": True,
                "external_provider": None}
    try:
        VisionConfig(api_key=os.getenv("LLM_API_KEY", ""), model=model,
                     base_url=os.getenv("LLM_BASE_URL", "")).validate()
        configured = True
    except VisionError:
        configured = False
    # Do not expose arbitrary env values or endpoints as public UI strings.
    return {"mode": mode, "model": "deepseek-v4-flash-vision-exp" if configured else "not-configured",
            "configured": configured, "external_provider": "DeepSeek"}


def default_analyzer(mode: str) -> SingleImageAnalyzer:
    if mode == "mock":
        return SingleImageAnalyzer(MockVisionBackend())
    config = VisionConfig(api_key=os.getenv("LLM_API_KEY", ""),
                          model=os.getenv("VISION_MODEL", ""),
                          base_url=os.getenv("LLM_BASE_URL", ""))
    return SingleImageAnalyzer(DeepSeekVisionBackend(config))


class PhotoService:
    def __init__(self, store: PhotoStore, proposals: Phase2ProposalService,
                 workflow: IssueWorkflowService, *,
                 analyzer_factory: Callable[[str], SingleImageAnalyzer] = default_analyzer) -> None:
        self.store, self.proposals, self.workflow = store, proposals, workflow
        self.analyzer_factory = analyzer_factory
        self.audit = ToolAuditLog()

    def analyze(self, photo_id: str, request: AnalyzePhotoRequest) -> PhotoAnalysisRecord:
        mode = "real" if os.getenv("AGENT_MODE", "mock").strip().casefold() == "real" else "mock"
        if mode == "real" and not request.allow_external:
            raise PhotoError("external_consent_required", "真实模式须确认将脱敏图片与补充文字发送至DeepSeek并承担费用。", 403)
        def store_analysis(document: PhotoDocument) -> PhotoAnalysisRecord:
            if sum(item.photo_id == photo_id for item in document.analyses.values()) >= 10:
                raise PhotoError("analysis_capacity_limit", "此图片已达到本地演示分析次数上限。", 409)
            document.analyses[record.analysis_id] = record
            return record
        try:
            # Reject unknown/corrupt photos before allocating a per-photo guard.
            self.store.read(photo_id)
            with self.store.analysis_guard(photo_id):
                # Re-read after acquiring the guard so metadata and bytes form one current snapshot.
                document = self.store.snapshot()
                if sum(item.photo_id == photo_id for item in document.analyses.values()) >= 10:
                    raise PhotoError("analysis_capacity_limit", "此图片已达到本地演示分析次数上限。", 409)
                photo, jpeg = self.store.read(photo_id)
                analyzer = self.analyzer_factory(mode)
                result = analyzer.analyze(
                    jpeg, request.context, low_resolution=min(photo.width, photo.height) < 384,
                )
                record = PhotoAnalysisRecord(
                    analysis_id="VIS-" + uuid4().hex[:24].upper(), photo_id=photo_id, mode=mode,
                    model="deepseek-v4-flash-vision-exp" if mode == "real" else "mock-no-image-recognition",
                    result=result, created_at=datetime.now(UTC),
                )
                record = self.store.mutate(store_analysis)
        except (PhotoError, VisionError) as exc:
            self._audit(photo_id, False, exc.code)
            raise
        self._audit(photo_id, True, None)
        return record

    def _audit(self, photo_id: str, ok: bool, code: str | None) -> None:
        result = ToolResult(tool_name="analyze_photo", ok=ok,
                            summary="单张图片分析完成，等待人工核验。" if ok else "单张图片分析失败，文字路径保持可用。",
                            error_code=code, recoverable=not ok)
        self.audit.record(tool_name="analyze_photo", arguments={"photo_id": photo_id}, result=result)

    def decide(self, analysis_id: str, request: CandidateDecisionRequest) -> ToolResult:
        def decision(document: PhotoDocument) -> ToolResult:
            record = document.analyses.get(analysis_id)
            if record is None:
                raise PhotoError("analysis_not_found", "图片分析不存在。", 404)
            candidate = next((item for item in record.result.candidates if item.candidate_id == request.candidate_id), None)
            if candidate is None:
                raise PhotoError("candidate_not_found", "候选问题不存在。", 404)
            if any(item.analysis_id == analysis_id and item.request.candidate_id == request.candidate_id for item in document.decisions):
                raise PhotoError("candidate_already_reviewed", "该候选已经处理；如需重新判断，请补充说明后重新分析。", 409)
            if request.decision == "reject":
                result = ToolResult(tool_name="review_photo_candidate", ok=True,
                                    summary="候选已由用户驳回并留痕，未创建提案或改变问题状态。")
            else:
                payload = candidate.analysis.model_dump(mode="json")
                if request.corrected_summary:
                    payload["summary"] = request.corrected_summary
                    payload["observed_facts"] = ["用户纠正的描述（待现场核实）：" + request.corrected_summary[:280]]
                # Deliberately do not accept risk, route, action or review overrides.
                analysis = IssueAnalysis.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)
                result = self.proposals.preview(ProposalPreviewRequest(
                    invocation_id="vision-" + uuid4().hex, analysis=analysis,
                ))
                if not result.ok:
                    raise PhotoError("candidate_proposal_failed", "候选提案生成失败，可稍后重试。", 503)
            document.decisions.append(CandidateDecision(analysis_id=analysis_id, request=request,
                                                        created_at=datetime.now(UTC)))
            return result
        return self.store.mutate(decision)

    def link(self, record_id: str, request: LinkPhotoRequest) -> PhotoLink:
        with self.workflow.store.locked_snapshot(record_id, expected_revision=request.expected_revision) as record:
            if record.disposition is not RecordDisposition.ACTIVE or record.status is WorkflowStatus.CLOSED:
                raise PhotoError("record_not_attachable", "已关闭或取消的记录不接受新照片。", 409)
            if request.stage == "before":
                allowed = (request.actor.role is ActorRole.REPORTER and request.actor.actor_id == record.reporter_id
                           and record.status in {WorkflowStatus.DRAFT, WorkflowStatus.SUBMITTED, WorkflowStatus.ASSIGNED})
            else:
                allowed = (request.actor.role is ActorRole.RECTIFIER and request.actor.actor_id == record.assigned_to
                           and record.status in {WorkflowStatus.RECTIFYING, WorkflowStatus.PENDING_REVIEW})
            if not allowed:
                raise PhotoError("photo_permission_denied", "当前人员或阶段无权关联此类照片。", 403)
            self.store.read(request.photo_id)
            link = PhotoLink(record_id=record_id, photo_id=request.photo_id, stage=request.stage,
                             actor=request.actor, record_revision=record.revision, created_at=datetime.now(UTC))
            def attach(document: PhotoDocument) -> PhotoLink:
                previous = document.links.get(request.photo_id)
                if previous is not None:
                    if previous.record_id == record_id and previous.stage == request.stage:
                        return previous
                    raise PhotoError("photo_link_conflict", "同一照片不能更换记录或前后阶段。", 409)
                document.links[request.photo_id] = link
                return link
            return self.store.mutate(attach)

    def linked(self, record_id: str) -> list[dict[str, object]]:
        self.workflow.get(record_id)
        document = self.store.snapshot()
        return [{"link": link.model_dump(mode="json"), "photo": document.photos[link.photo_id].model_dump(mode="json")}
                for link in document.links.values() if link.record_id == record_id]
