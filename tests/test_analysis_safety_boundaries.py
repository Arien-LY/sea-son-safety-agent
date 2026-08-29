import json
from typing import Any

import pytest

from agents.analysis import IssueAnalyzer
from agents.prompts import ISSUE_ANALYSIS_SYSTEM_PROMPT
from agents.schemas import RecommendedRoute, RiskLevel, TextConsultationInput
from agents.structured_output import AnalysisOutputError, AnalysisOutputErrorCode


class FakeLLM:
    def __init__(self, result: str) -> None:
        self._result = result

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        return self._result


def base_payload() -> dict[str, Any]:
    return {
        "category": "unknown",
        "issue_type": "信息不足",
        "summary": "用户没有说明需要处理的具体问题。",
        "observed_facts": ["用户只询问如何处理"],
        "uncertainties": ["无法判断问题类别和风险"],
        "missing_fields": ["具体问题描述", "发生位置", "当前状态和人员暴露情况"],
        "risk_level": "undetermined",
        "immediate_actions": [],
        "suggested_actions": [],
        "recommended_route": "collect_more_info",
        "requires_human_review": False,
        "confidence": 0.2,
    }


def analyze_payload(payload: dict[str, Any], message: str = "这个要怎么处理？"):
    analyzer = IssueAnalyzer(FakeLLM(json.dumps(payload, ensure_ascii=False)))
    return analyzer.analyze(TextConsultationInput(message=message))


def test_insufficient_information_returns_missing_fields_without_guessing() -> None:
    result = analyze_payload(base_payload())
    serialized = result.model_dump_json()

    assert result.risk_level == RiskLevel.UNDETERMINED
    assert result.recommended_route == RecommendedRoute.COLLECT_MORE_INFO
    assert result.missing_fields == [
        "具体问题描述",
        "发生位置",
        "当前状态和人员暴露情况",
    ]
    assert result.uncertainties == ["无法判断问题类别和风险"]
    for fabricated_value in ["二层西侧", "张三", "施工班组负责", "海景花园项目"]:
        assert fabricated_value not in serialized


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(missing_fields=[]),
        lambda payload: payload.update(uncertainties=[]),
        lambda payload: payload.update(
            category="safety",
            risk_level="low",
            recommended_route="collect_more_info",
            missing_fields=[],
            uncertainties=[],
        ),
    ],
)
def test_incomplete_analysis_cannot_hide_required_missing_information(mutate) -> None:
    payload = base_payload()
    mutate(payload)

    with pytest.raises(AnalysisOutputError) as captured:
        analyze_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


def test_known_high_risk_with_missing_context_still_routes_human_review() -> None:
    payload = {
        **base_payload(),
        "category": "safety",
        "issue_type": "临时用电",
        "summary": "疑似裸露电线，具体位置和带电状态不清楚。",
        "observed_facts": ["用户报告看到疑似裸露电线"],
        "uncertainties": ["无法确认线路是否带电", "具体位置未知"],
        "missing_fields": ["具体位置", "是否带电", "附近是否潮湿或有人接近"],
        "risk_level": "high",
        "immediate_actions": ["不要靠近或触摸，警示周边人员并联系现场电工核查"],
        "suggested_actions": [],
        "recommended_route": "human_review",
        "requires_human_review": True,
        "confidence": 0.7,
    }

    result = analyze_payload(payload, "有根电线看着不太对劲。")

    assert result.risk_level == RiskLevel.HIGH
    assert result.recommended_route == RecommendedRoute.HUMAN_REVIEW
    assert result.requires_human_review is True
    assert result.immediate_actions


@pytest.mark.parametrize("risk_level", ["high", "emergency"])
def test_high_risk_cannot_use_non_human_route(risk_level: str) -> None:
    payload = {
        **base_payload(),
        "category": "safety",
        "risk_level": risk_level,
        "immediate_actions": ["立即远离危险区域并通知现场专业人员"],
        "recommended_route": "propose_workflow",
        "requires_human_review": True,
    }

    with pytest.raises(AnalysisOutputError) as captured:
        analyze_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


def test_prompt_freezes_no_guessing_and_immediate_avoidance_rules() -> None:
    assert "不得补写未提供的地点、人员、状态或责任" in ISSUE_ANALYSIS_SYSTEM_PROMPT
    assert "高风险即使信息不全也必须优先路由人工复核" in ISSUE_ANALYSIS_SYSTEM_PROMPT
    assert "不得建议无资质用户靠近、触摸、带电测试、拆卸或自行修理" in (
        ISSUE_ANALYSIS_SYSTEM_PROMPT
    )
    assert "recommended_route=human_review" in ISSUE_ANALYSIS_SYSTEM_PROMPT
