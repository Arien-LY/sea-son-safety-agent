"""Phase 3 确定性整改工作流的冻结数据契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.schemas import IssueAnalysis, IssueCategory, RiskLevel
from agents.tools import IssueRecordReviewFields
from backend.app.proposals import ConfirmedIssueProposal


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    RECTIFYING = "rectifying"
    PENDING_REVIEW = "pending_review"
    CLOSED = "closed"


class RecordDisposition(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class WorkflowAction(StrEnum):
    CREATE_DRAFT = "create_draft"
    SUBMIT = "submit"
    REQUEST_MORE_INFO = "request_more_info"
    SUPPLEMENT_INFORMATION = "supplement_information"
    ASSIGN = "assign"
    START_RECTIFICATION = "start_rectification"
    SUBMIT_RECTIFICATION = "submit_rectification"
    REJECT_REVIEW = "reject_review"
    CLOSE = "close"
    CANCEL = "cancel"


class ActorRole(StrEnum):
    REPORTER = "reporter"
    COORDINATOR = "coordinator"
    RECTIFIER = "rectifier"
    REVIEWER = "reviewer"
    PROFESSIONAL_REVIEWER = "professional_reviewer"


class ResponsibleRole(StrEnum):
    SAFETY_OFFICER = "safety_officer"
    QUALITY_INSPECTOR = "quality_inspector"
    SITE_MANAGER = "site_manager"
    FACILITIES_STAFF = "facilities_staff"


class WorkflowActor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    actor_id: str = Field(min_length=1, max_length=100)
    role: ActorRole


class WorkflowEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sequence: int = Field(ge=1)
    occurred_at: datetime
    action: WorkflowAction
    actor_id: str = Field(min_length=1, max_length=100)
    actor_role: ActorRole
    from_status: WorkflowStatus | None
    to_status: WorkflowStatus
    from_disposition: RecordDisposition | None
    to_disposition: RecordDisposition
    summary: str = Field(min_length=1, max_length=500)
    note: str | None = Field(default=None, min_length=1, max_length=2_000)


class IssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["phase3-issue-record-v1"] = "phase3-issue-record-v1"
    record_id: str = Field(pattern=r"^ISS-[A-F0-9]{12}$")
    analysis: IssueAnalysis
    review_fields: IssueRecordReviewFields
    status: WorkflowStatus
    disposition: RecordDisposition
    revision: int = Field(ge=1)
    reporter_id: str = Field(min_length=1, max_length=100)
    suggested_responsible_role: ResponsibleRole
    assigned_to: str | None = Field(default=None, min_length=1, max_length=100)
    assigned_role: ResponsibleRole | None = None
    assignment_confirmed_by_human: bool = False
    information_request: str | None = Field(default=None, min_length=1, max_length=500)
    rectification_note: str | None = Field(default=None, min_length=1, max_length=2_000)
    review_note: str | None = Field(default=None, min_length=1, max_length=1_000)
    cancellation_reason: str | None = Field(default=None, min_length=1, max_length=2_000)
    created_at: datetime
    updated_at: datetime
    events: list[WorkflowEvent] = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def enforce_record_invariants(self) -> "IssueRecord":
        workflow_categories = {
            IssueCategory.SAFETY,
            IssueCategory.QUALITY,
            IssueCategory.MANAGEMENT,
            IssueCategory.LOGISTICS,
        }
        if self.analysis.category not in workflow_categories:
            raise ValueError("正式问题记录必须属于四类工作流问题。")
        assignment_fields = (
            self.assigned_to,
            self.assigned_role,
            self.assignment_confirmed_by_human,
        )
        if self.status in {
            WorkflowStatus.ASSIGNED,
            WorkflowStatus.RECTIFYING,
            WorkflowStatus.PENDING_REVIEW,
            WorkflowStatus.CLOSED,
        } and (assignment_fields[0] is None or assignment_fields[1] is None or not assignment_fields[2]):
            raise ValueError("进入派工后状态必须包含人工确认的责任人和责任角色。")
        if self.status in {WorkflowStatus.DRAFT, WorkflowStatus.SUBMITTED} and (
            assignment_fields[0] is not None
            or assignment_fields[1] is not None
            or assignment_fields[2]
        ):
            raise ValueError("派工前状态不能预先包含责任人或责任角色。")
        if self.status is WorkflowStatus.CLOSED and not self.review_note:
            raise ValueError("关闭记录必须保留复查说明。")
        if self.disposition is RecordDisposition.CANCELLED and not self.cancellation_reason:
            raise ValueError("取消记录必须保留取消原因。")
        if self.disposition is RecordDisposition.CANCELLED and self.status is WorkflowStatus.CLOSED:
            raise ValueError("已复查关闭的记录不能同时标记为取消。")
        if [event.sequence for event in self.events] != list(
            range(1, len(self.events) + 1)
        ):
            raise ValueError("事件序号必须连续。")
        if self.revision != len(self.events):
            raise ValueError("revision 必须与完整事件数量一致。")
        last_event = self.events[-1]
        if (
            last_event.to_status is not self.status
            or last_event.to_disposition is not self.disposition
        ):
            raise ValueError("最后事件必须与当前记录状态和处置一致。")
        return self

    @property
    def is_high_risk(self) -> bool:
        return self.analysis.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}


class CreateIssueRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    confirmation: ConfirmedIssueProposal
    idempotency_key: str = Field(
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    actor: WorkflowActor

    @model_validator(mode="after")
    def require_reporter(self) -> "CreateIssueRecordRequest":
        if self.actor.role is not ActorRole.REPORTER:
            raise ValueError("只有报告人可以把已确认提案保存为草稿。")
        return self


class CreateIssueRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record: IssueRecord
    created: bool


class WorkflowTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    action: WorkflowAction
    actor: WorkflowActor
    expected_revision: int = Field(ge=1)
    note: str | None = Field(default=None, min_length=1, max_length=2_000)
    assignee_id: str | None = Field(default=None, min_length=1, max_length=100)
    assignee_role: ResponsibleRole | None = None

    @model_validator(mode="after")
    def enforce_action_arguments(self) -> "WorkflowTransitionRequest":
        if self.action is WorkflowAction.CREATE_DRAFT:
            raise ValueError("create_draft 只能由创建接口产生。")
        if self.action is WorkflowAction.ASSIGN:
            if self.assignee_id is None or self.assignee_role is None:
                raise ValueError("派工必须明确责任人和责任角色。")
        elif self.assignee_id is not None or self.assignee_role is not None:
            raise ValueError("只有派工动作可以包含责任人参数。")
        actions_requiring_note = {
            WorkflowAction.REQUEST_MORE_INFO,
            WorkflowAction.SUPPLEMENT_INFORMATION,
            WorkflowAction.SUBMIT_RECTIFICATION,
            WorkflowAction.REJECT_REVIEW,
            WorkflowAction.CLOSE,
            WorkflowAction.CANCEL,
        }
        if self.action in actions_requiring_note and self.note is None:
            raise ValueError("当前动作必须提供说明。")
        if self.action not in actions_requiring_note and self.note is not None:
            raise ValueError("当前动作不接收说明字段。")
        return self


RESPONSIBLE_ROLE_SUGGESTIONS: dict[IssueCategory, ResponsibleRole] = {
    IssueCategory.SAFETY: ResponsibleRole.SAFETY_OFFICER,
    IssueCategory.QUALITY: ResponsibleRole.QUALITY_INSPECTOR,
    IssueCategory.MANAGEMENT: ResponsibleRole.SITE_MANAGER,
    IssueCategory.LOGISTICS: ResponsibleRole.FACILITIES_STAFF,
}
