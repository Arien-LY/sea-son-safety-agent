"""Phase 3 问题记录创建、权限检查和确定性状态推进服务。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.proposals import ConfirmedIssueProposal
from backend.app.workflow_models import (
    ActorRole,
    CreateIssueRecordRequest,
    CreateIssueRecordResponse,
    IssueRecord,
    RecordDisposition,
    RESPONSIBLE_ROLE_SUGGESTIONS,
    WorkflowAction,
    WorkflowEvent,
    WorkflowStatus,
    WorkflowTransitionRequest,
)
from backend.app.workflow_store import JsonIssueRecordStore


class WorkflowRuleError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class IssueWorkflowService:
    """业务状态唯一由此服务和 Store 推进，Agent 不能直接调用。"""

    def __init__(
        self,
        store: JsonIssueRecordStore,
        *,
        confirmation_verifier: Callable[[ConfirmedIssueProposal], bool],
        clock: Callable[[], datetime] | None = None,
        record_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self._confirmation_verifier = confirmation_verifier
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._record_id_factory = record_id_factory or (
            lambda: f"ISS-{uuid4().hex[:12].upper()}"
        )

    def create_draft(
        self,
        request: CreateIssueRecordRequest,
    ) -> CreateIssueRecordResponse:
        if not self._confirmation_verifier(request.confirmation):
            raise WorkflowRuleError(
                "invalid_confirmation",
                "已确认提案的完整性校验失败。",
            )
        analysis = request.confirmation.analysis
        suggestion = RESPONSIBLE_ROLE_SUGGESTIONS.get(analysis.category)
        if suggestion is None:
            raise WorkflowRuleError(
                "unsupported_workflow_category",
                "当前问题类别不能进入整改工作流。",
            )
        now = self._clock()
        record_id = self._record_id_factory()
        event = WorkflowEvent(
            sequence=1,
            occurred_at=now,
            action=WorkflowAction.CREATE_DRAFT,
            actor_id=request.actor.actor_id,
            actor_role=request.actor.role,
            from_status=None,
            to_status=WorkflowStatus.DRAFT,
            from_disposition=None,
            to_disposition=RecordDisposition.ACTIVE,
            summary="报告人已将确认提案保存为草稿。",
        )
        record = IssueRecord(
            record_id=record_id,
            analysis=analysis,
            review_fields=request.confirmation.review_fields,
            status=WorkflowStatus.DRAFT,
            disposition=RecordDisposition.ACTIVE,
            revision=1,
            reporter_id=request.actor.actor_id,
            suggested_responsible_role=suggestion,
            created_at=now,
            updated_at=now,
            events=[event],
        )
        payload_digest = self._creation_digest(request)
        stored, created = self.store.create(
            record,
            idempotency_key=request.idempotency_key,
            payload_digest=payload_digest,
        )
        return CreateIssueRecordResponse(record=stored, created=created)

    def get(self, record_id: str) -> IssueRecord:
        return self.store.get(record_id)

    def delete(self, record_id: str) -> IssueRecord:
        """本地删除一条已保存工单，与“取消工单”是相互独立的操作。"""

        return self.store.delete(record_id)

    def transition(
        self,
        record_id: str,
        request: WorkflowTransitionRequest,
    ) -> IssueRecord:
        return self.store.update(
            record_id,
            expected_revision=request.expected_revision,
            transform=lambda current: self._apply_transition(current, request),
        )

    def _apply_transition(
        self,
        current: IssueRecord,
        request: WorkflowTransitionRequest,
    ) -> IssueRecord:
        if current.disposition is RecordDisposition.CANCELLED:
            raise WorkflowRuleError(
                "record_cancelled",
                "已取消记录不能继续推进。",
            )
        action = request.action
        if action is WorkflowAction.SUBMIT:
            self._require_status(current, WorkflowStatus.DRAFT)
            self._require_reporter(current, request)
            if current.information_request is not None:
                raise WorkflowRuleError(
                    "supplement_required",
                    "存在补充信息要求时必须使用补充信息动作重新提交。",
                )
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.SUBMITTED,
                summary="报告人已提交问题记录。",
            )
        if action is WorkflowAction.REQUEST_MORE_INFO:
            self._require_status(current, WorkflowStatus.SUBMITTED)
            self._require_role(request, {ActorRole.COORDINATOR})
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.DRAFT,
                summary="协调员已退回并要求补充信息。",
                information_request=request.note,
            )
        if action is WorkflowAction.SUPPLEMENT_INFORMATION:
            self._require_status(current, WorkflowStatus.DRAFT)
            self._require_reporter(current, request)
            if current.information_request is None:
                raise WorkflowRuleError(
                    "information_not_requested",
                    "当前记录没有待补充信息要求。",
                )
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.SUBMITTED,
                summary="报告人已补充信息并重新提交。",
                information_request=None,
                reporter_note=request.note,
            )
        if action is WorkflowAction.ASSIGN:
            self._require_status(current, WorkflowStatus.SUBMITTED)
            self._require_role(request, {ActorRole.COORDINATOR})
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.ASSIGNED,
                summary="协调员已人工确认责任角色并完成派工。",
                assigned_to=request.assignee_id,
                assigned_role=request.assignee_role,
                assignment_confirmed_by_human=True,
            )
        if action is WorkflowAction.START_RECTIFICATION:
            self._require_status(current, WorkflowStatus.ASSIGNED)
            self._require_assignee(current, request)
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.RECTIFYING,
                summary="整改人已开始整改。",
            )
        if action is WorkflowAction.SUBMIT_RECTIFICATION:
            self._require_status(current, WorkflowStatus.RECTIFYING)
            self._require_assignee(current, request)
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.PENDING_REVIEW,
                summary="整改人已提交整改说明，等待复查。",
                rectification_note=request.note,
            )
        if action is WorkflowAction.REJECT_REVIEW:
            self._require_status(current, WorkflowStatus.PENDING_REVIEW)
            self._require_role(
                request,
                {ActorRole.REVIEWER, ActorRole.PROFESSIONAL_REVIEWER},
            )
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.RECTIFYING,
                summary="复查人已驳回并要求重新整改。",
                review_note=request.note,
            )
        if action is WorkflowAction.CLOSE:
            self._require_status(current, WorkflowStatus.PENDING_REVIEW)
            self._require_role(
                request,
                {ActorRole.REVIEWER, ActorRole.PROFESSIONAL_REVIEWER},
            )
            if current.is_high_risk:
                if request.actor.role is not ActorRole.PROFESSIONAL_REVIEWER:
                    raise WorkflowRuleError(
                        "professional_review_required",
                        "高风险问题必须由专业复查人确认关闭。",
                    )
                if request.actor.actor_id == current.reporter_id:
                    raise WorkflowRuleError(
                        "submitter_cannot_close_high_risk",
                        "高风险问题禁止提交人自行关闭。",
                    )
            return self._updated(
                current,
                request,
                to_status=WorkflowStatus.CLOSED,
                summary="复查人已确认整改结果并关闭记录。",
                review_note=request.note,
            )
        if action is WorkflowAction.CANCEL:
            if current.status is WorkflowStatus.CLOSED:
                raise WorkflowRuleError(
                    "invalid_transition",
                    "已关闭记录不能取消。",
                )
            if current.is_high_risk:
                self._require_role(request, {ActorRole.PROFESSIONAL_REVIEWER})
                if request.actor.actor_id == current.reporter_id:
                    raise WorkflowRuleError(
                        "submitter_cannot_cancel_high_risk",
                        "高风险问题禁止提交人自行取消。",
                    )
            elif not (
                request.actor.role is ActorRole.COORDINATOR
                or (
                    request.actor.role is ActorRole.REPORTER
                    and request.actor.actor_id == current.reporter_id
                    and current.status in {WorkflowStatus.DRAFT, WorkflowStatus.SUBMITTED}
                )
            ):
                raise WorkflowRuleError(
                    "permission_denied",
                    "当前人员无权取消该记录。",
                )
            return self._updated(
                current,
                request,
                to_status=current.status,
                to_disposition=RecordDisposition.CANCELLED,
                summary="有权限的人员已取消记录并说明原因。",
                cancellation_reason=request.note,
            )
        raise WorkflowRuleError("invalid_action", "不支持的工作流动作。")

    def _updated(
        self,
        current: IssueRecord,
        request: WorkflowTransitionRequest,
        *,
        to_status: WorkflowStatus,
        summary: str,
        to_disposition: RecordDisposition | None = None,
        information_request: str | None | object = ...,
        reporter_note: str | None = None,
        assigned_to: str | None = None,
        assigned_role: object = ...,
        assignment_confirmed_by_human: bool | None = None,
        rectification_note: str | None = None,
        review_note: str | None = None,
        cancellation_reason: str | None = None,
    ) -> IssueRecord:
        now = self._clock()
        disposition = to_disposition or current.disposition
        event = WorkflowEvent(
            sequence=len(current.events) + 1,
            occurred_at=now,
            action=request.action,
            actor_id=request.actor.actor_id,
            actor_role=request.actor.role,
            from_status=current.status,
            to_status=to_status,
            from_disposition=current.disposition,
            to_disposition=disposition,
            summary=summary,
            note=request.note,
        )
        data = current.model_dump(mode="python")
        data.update(
            status=to_status,
            disposition=disposition,
            revision=current.revision + 1,
            updated_at=now,
            events=[*current.events, event],
        )
        if information_request is not ...:
            data["information_request"] = information_request
        if reporter_note is not None:
            review_fields = current.review_fields.model_dump(mode="python")
            review_fields["reporter_note"] = reporter_note
            data["review_fields"] = review_fields
        if assigned_to is not None:
            data["assigned_to"] = assigned_to
        if assigned_role is not ...:
            data["assigned_role"] = assigned_role
        if assignment_confirmed_by_human is not None:
            data["assignment_confirmed_by_human"] = assignment_confirmed_by_human
        if rectification_note is not None:
            data["rectification_note"] = rectification_note
        if review_note is not None:
            data["review_note"] = review_note
        if cancellation_reason is not None:
            data["cancellation_reason"] = cancellation_reason
        return IssueRecord.model_validate(data, strict=True)

    @staticmethod
    def _require_status(current: IssueRecord, expected: WorkflowStatus) -> None:
        if current.status is not expected:
            raise WorkflowRuleError(
                "invalid_transition",
                f"动作要求状态为 {expected.value}，当前为 {current.status.value}。",
            )

    @staticmethod
    def _require_role(
        request: WorkflowTransitionRequest,
        allowed: set[ActorRole],
    ) -> None:
        if request.actor.role not in allowed:
            raise WorkflowRuleError(
                "permission_denied",
                "当前角色无权执行该动作。",
            )

    @staticmethod
    def _require_reporter(
        current: IssueRecord,
        request: WorkflowTransitionRequest,
    ) -> None:
        if (
            request.actor.role is not ActorRole.REPORTER
            or request.actor.actor_id != current.reporter_id
        ):
            raise WorkflowRuleError(
                "permission_denied",
                "只有原报告人可以执行该动作。",
            )

    @staticmethod
    def _require_assignee(
        current: IssueRecord,
        request: WorkflowTransitionRequest,
    ) -> None:
        if (
            request.actor.role is not ActorRole.RECTIFIER
            or request.actor.actor_id != current.assigned_to
        ):
            raise WorkflowRuleError(
                "permission_denied",
                "只有已人工指派的整改人可以执行该动作。",
            )

    @staticmethod
    def _creation_digest(request: CreateIssueRecordRequest) -> str:
        canonical = json.dumps(
            {
                "confirmation": request.confirmation.model_dump(mode="json"),
                "actor": request.actor.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
