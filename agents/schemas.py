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
        if self.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}:
            if not self.requires_human_review:
                raise ValueError("高风险或紧急问题必须要求人工复核。")
            if not self.immediate_actions:
                raise ValueError("高风险或紧急问题必须提供立即行动建议。")
        return self
