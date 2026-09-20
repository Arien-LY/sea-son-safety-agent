"""Agent 与业务层之间的稳定问题分析契约。"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


IssueDetail = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class IssueCategory(StrEnum):
    SAFETY = "safety"
    QUALITY = "quality"
    MANAGEMENT = "management"
    LOGISTICS = "logistics"
    CONSULTATION = "consultation"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    UNDETERMINED = "undetermined"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class RecommendedRoute(StrEnum):
    DIRECT_ANSWER = "direct_answer"
    COLLECT_MORE_INFO = "collect_more_info"
    PROPOSE_WORKFLOW = "propose_workflow"
    HUMAN_REVIEW = "human_review"


class TextConsultationInput(BaseModel):
    """一条纯文字咨询消息及用户自报的可选上下文。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
    )

    message: str = Field(min_length=1, max_length=1_000)
    project: str | None = Field(default=None, min_length=1, max_length=100)
    area: str | None = Field(default=None, min_length=1, max_length=200)
    requester_role: str | None = Field(default=None, min_length=1, max_length=50)


class BasicDialogReply(BaseModel):
    """基础对话返回的已校验文字回答；不携带业务动作。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
    )

    answer: str = Field(min_length=1, max_length=4_000)


class IssueAnalysis(BaseModel):
    """模型分析结果；不能直接创建或修改业务记录。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: IssueCategory
    issue_type: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    observed_facts: list[IssueDetail] = Field(max_length=20)
    uncertainties: list[IssueDetail] = Field(max_length=20)
    missing_fields: list[IssueDetail] = Field(max_length=20)
    risk_level: RiskLevel
    immediate_actions: list[IssueDetail] = Field(max_length=10)
    suggested_actions: list[IssueDetail] = Field(max_length=10)
    recommended_route: RecommendedRoute
    requires_human_review: bool
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def enforce_safety_boundary(self) -> "IssueAnalysis":
        if self.missing_fields and not self.uncertainties:
            raise ValueError("存在缺失字段时必须明确说明不确定性。")
        if self.category == IssueCategory.UNKNOWN:
            if not self.missing_fields or not self.uncertainties:
                raise ValueError("未知类别必须列出缺失字段和不确定性。")
        if self.risk_level == RiskLevel.UNDETERMINED:
            if not self.missing_fields or not self.uncertainties:
                raise ValueError("风险未确定时必须列出缺失字段和不确定性。")
        if self.recommended_route == RecommendedRoute.COLLECT_MORE_INFO:
            if not self.missing_fields:
                raise ValueError("补充信息路由必须列出需要补充的字段。")
        if self.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}:
            if not self.requires_human_review:
                raise ValueError("高风险或紧急问题必须要求人工复核。")
            if not self.immediate_actions:
                raise ValueError("高风险或紧急问题必须提供立即行动建议。")
            if self.recommended_route != RecommendedRoute.HUMAN_REVIEW:
                raise ValueError("高风险或紧急问题必须路由人工复核。")
        return self


WORKFLOW_CATEGORIES = frozenset({
    IssueCategory.SAFETY,
    IssueCategory.QUALITY,
    IssueCategory.MANAGEMENT,
    IssueCategory.LOGISTICS,
})


class TicketStatus(StrEnum):
    """聊天回答之后唯一需要的三种工单判断。"""

    NO_TICKET = "no_ticket"
    NEED_MORE_INFO = "need_more_info"
    CREATE_TICKET = "create_ticket"


class TicketDecision(BaseModel):
    """比 IssueAnalysis 更小、更稳定的工单判断契约。

    模型只负责判断"要不要开单"；服务端把本契约确定性地转换成
    现有 IssueAnalysis，再进入 Proposal / HMAC / 正式工单流程。
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    status: TicketStatus
    category: IssueCategory = IssueCategory.UNKNOWN
    issue_type: str = Field(default="", max_length=100)
    summary: str = Field(default="", max_length=500)
    risk_level: RiskLevel = RiskLevel.UNDETERMINED
    requires_human_review: bool = False
    missing_information: list[IssueDetail] = Field(default_factory=list, max_length=10)
    immediate_action: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def enforce_ticket_boundary(self) -> "TicketDecision":
        # 高风险或紧急不允许被模型降级：服务端强制开单并要求人工复核。
        if self.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}:
            self.requires_human_review = True
            self.status = TicketStatus.CREATE_TICKET
        if self.status is TicketStatus.CREATE_TICKET:
            if self.category not in WORKFLOW_CATEGORIES:
                raise ValueError("只有安全/质量/管理/后勤现场问题才能生成工单。")
            if not self.summary:
                raise ValueError("生成工单必须给出问题摘要。")
        return self
