import pytest
from pydantic import ValidationError

from agents.schemas import (
    IssueAnalysis,
    IssueCategory,
    RecommendedRoute,
    RiskLevel,
)


def test_hello_agents_tutorial_api_is_importable() -> None:
    from hello_agents import FunctionCallAgent, HelloAgentsLLM, SimpleAgent, ToolRegistry

    assert all(
        item is not None
        for item in (FunctionCallAgent, HelloAgentsLLM, SimpleAgent, ToolRegistry)
    )


def test_high_risk_issue_requires_human_review_and_immediate_action() -> None:
    analysis = IssueAnalysis(
        category=IssueCategory.SAFETY,
        issue_type="临时用电",
        summary="潮湿地面存在裸露接线。",
        observed_facts=["电线接头未见绝缘保护"],
        uncertainties=["无法确认线路是否带电"],
        missing_fields=["具体位置"],
        risk_level=RiskLevel.HIGH,
        immediate_actions=["保持距离并通知现场电工断电核查"],
        suggested_actions=["由持证电工重新布线并复查"],
        recommended_route=RecommendedRoute.HUMAN_REVIEW,
        requires_human_review=True,
        confidence=0.72,
    )

    assert analysis.category == IssueCategory.SAFETY


def test_high_risk_issue_rejects_missing_human_review() -> None:
    with pytest.raises(ValidationError, match="必须要求人工复核"):
        IssueAnalysis(
            category=IssueCategory.SAFETY,
            issue_type="临时用电",
            summary="疑似危险接线。",
            risk_level=RiskLevel.HIGH,
            immediate_actions=["停止靠近"],
            suggested_actions=[],
            recommended_route=RecommendedRoute.DIRECT_ANSWER,
            requires_human_review=False,
            confidence=0.5,
        )


def test_issue_analysis_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        IssueAnalysis.model_validate(
            {
                "category": "consultation",
                "issue_type": "咨询",
                "summary": "咨询安全帽使用要求。",
                "risk_level": "low",
                "recommended_route": "direct_answer",
                "requires_human_review": False,
                "confidence": 0.9,
                "unexpected": "not allowed",
            }
        )
