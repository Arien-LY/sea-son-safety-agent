import json
from typing import Any

import pytest

from agents.analysis import IssueAnalyzer
from agents.prompts import ISSUE_ANALYSIS_SYSTEM_PROMPT
from agents.schemas import RiskLevel, TextConsultationInput
from agents.structured_output import AnalysisOutputError, AnalysisOutputErrorCode


class FakeLLM:
    """返回预设 JSON，不创建客户端、不读取密钥或访问网络。"""

    def __init__(self, *results: str) -> None:
        self._results = list(results)

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        return self._results.pop(0)


def analysis_payload(
    risk_level: str,
    *,
    category: str = "safety",
) -> dict[str, Any]:
    high_or_emergency = risk_level in {"high", "emergency"}
    return {
        "category": category,
        "issue_type": "风险协议测试",
        "summary": "用于验证风险等级协议的结构化输出。",
        "observed_facts": [],
        "uncertainties": ["信息不足"] if risk_level == "undetermined" else [],
        "missing_fields": ["现场状态"] if risk_level == "undetermined" else [],
        "risk_level": risk_level,
        "immediate_actions": ["保持距离并通知现场专业人员"]
        if high_or_emergency
        else [],
        "suggested_actions": [],
        "recommended_route": "human_review"
        if high_or_emergency
        else "collect_more_info"
        if risk_level == "undetermined"
        else "direct_answer",
        "requires_human_review": high_or_emergency,
        "confidence": 0.8,
    }


def analysis_json(risk_level: str, *, category: str = "safety") -> str:
    return json.dumps(
        analysis_payload(risk_level, category=category),
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("message", "category", "risk_level"),
    [
        ("这个要怎么处理？", "unknown", "undetermined"),
        ("安全帽下颏带怎么检查？", "consultation", "low"),
        ("墙面出现局部空鼓。", "quality", "medium"),
        ("临边护栏被拆了。", "safety", "high"),
        ("宿舍配电板进水并冒火花。", "logistics", "emergency"),
    ],
)
def test_all_five_risk_levels_round_trip_through_issue_analyzer(
    message: str,
    category: str,
    risk_level: str,
) -> None:
    analyzer = IssueAnalyzer(FakeLLM(analysis_json(risk_level, category=category)))

    result = analyzer.analyze(TextConsultationInput(message=message))

    assert result.risk_level == RiskLevel(risk_level)


def test_risk_prompt_freezes_vocabulary_and_separates_confidence() -> None:
    expected_levels = {"undetermined", "low", "medium", "high", "emergency"}

    assert all(
        f"- {risk_level}：" in ISSUE_ANALYSIS_SYSTEM_PROMPT
        for risk_level in expected_levels
    )
    assert "证据不足时使用 undetermined，不得降为 low" in (
        ISSUE_ANALYSIS_SYSTEM_PROMPT
    )
    assert "confidence 表示对当前分析的把握程度，不是风险严重度" in (
        ISSUE_ANALYSIS_SYSTEM_PROMPT
    )


def test_unsupported_risk_level_is_rejected() -> None:
    analyzer = IssueAnalyzer(FakeLLM(analysis_json("critical")))

    with pytest.raises(AnalysisOutputError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


@pytest.mark.parametrize(
    ("risk_level", "immediate_actions", "requires_human_review"),
    [
        ("high", [], True),
        ("emergency", ["立即远离危险"], False),
    ],
)
def test_high_and_emergency_keep_existing_safety_contract(
    risk_level: str,
    immediate_actions: list[str],
    requires_human_review: bool,
) -> None:
    payload = analysis_payload(risk_level)
    payload["immediate_actions"] = immediate_actions
    payload["requires_human_review"] = requires_human_review
    analyzer = IssueAnalyzer(FakeLLM(json.dumps(payload, ensure_ascii=False)))

    with pytest.raises(AnalysisOutputError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


@pytest.mark.parametrize(
    ("category", "risk_level"),
    [
        ("consultation", "high"),
        ("logistics", "emergency"),
    ],
)
def test_category_does_not_cap_risk_level(category: str, risk_level: str) -> None:
    analyzer = IssueAnalyzer(FakeLLM(analysis_json(risk_level, category=category)))

    result = analyzer.analyze(TextConsultationInput(message="测试交叉场景"))

    assert result.category.value == category
    assert result.risk_level.value == risk_level
