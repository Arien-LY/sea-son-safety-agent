import json
from typing import Any

import pytest

from agents.analysis import (
    AnalysisExecutionError,
    AnalysisExecutionErrorCode,
    IssueAnalyzer,
)
from agents.prompts import ISSUE_ANALYSIS_SYSTEM_PROMPT
from agents.schemas import IssueCategory, TextConsultationInput
from agents.structured_output import AnalysisOutputError, AnalysisOutputErrorCode


class FakeLLM:
    """返回预设结构化输出，不创建客户端、不读取密钥或访问网络。"""

    def __init__(self, *results: str | Exception) -> None:
        self._results = list(results)
        self.calls: list[list[dict[str, str]]] = []

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        self.calls.append([message.copy() for message in messages])
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def analysis_json(category: str) -> str:
    risk_level = "undetermined" if category == "unknown" else "low"
    route = "collect_more_info" if category == "unknown" else "direct_answer"
    payload = {
        "category": category,
        "issue_type": "测试类型",
        "summary": "用于验证分类协议的结构化输出。",
        "observed_facts": [],
        "uncertainties": [],
        "missing_fields": ["具体问题"] if category == "unknown" else [],
        "risk_level": risk_level,
        "immediate_actions": [],
        "suggested_actions": [],
        "recommended_route": route,
        "requires_human_review": False,
        "confidence": 0.8,
    }
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("安全帽下颏带怎么检查？", "consultation"),
        ("二层西侧临边护栏被拆了。", "safety"),
        ("刚浇筑的楼板出现裂缝。", "quality"),
        ("主通道材料没有标识。", "management"),
        ("宿舍空调不制冷。", "logistics"),
        ("这个要怎么处理？", "unknown"),
    ],
)
def test_all_six_categories_round_trip_through_issue_analyzer(
    message: str, category: str
) -> None:
    analyzer = IssueAnalyzer(FakeLLM(analysis_json(category)))

    result = analyzer.analyze(TextConsultationInput(message=message))

    assert result.category == IssueCategory(category)


def test_category_prompt_freezes_vocabulary_and_category_risk_separation() -> None:
    expected_categories = {
        "consultation",
        "safety",
        "quality",
        "management",
        "logistics",
        "unknown",
    }

    assert all(
        f"- {category}：" in ISSUE_ANALYSIS_SYSTEM_PROMPT
        for category in expected_categories
    )
    assert "类别表示用户主诉的业务归口，风险等级单独判断" in (
        ISSUE_ANALYSIS_SYSTEM_PROMPT
    )
    assert '"category"' in ISSUE_ANALYSIS_SYSTEM_PROMPT
    assert "只输出一个符合下列 JSON Schema 的 JSON 对象" in (
        ISSUE_ANALYSIS_SYSTEM_PROMPT
    )


def test_optional_context_is_labeled_unverified_for_analysis() -> None:
    fake_llm = FakeLLM(analysis_json("logistics"))
    analyzer = IssueAnalyzer(fake_llm)

    analyzer.analyze(
        TextConsultationInput(
            message="空调不制冷。",
            project="海景花园项目",
            area="宿舍 3 楼 305",
            requester_role="管理员",
        )
    )

    messages = fake_llm.calls[0]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[0]["content"] == ISSUE_ANALYSIS_SYSTEM_PROMPT
    assert "用户自报且未经核实" in messages[1]["content"]
    assert "项目标签：海景花园项目" in messages[1]["content"]
    assert "区域标签：宿舍 3 楼 305" in messages[1]["content"]
    assert "咨询者角色：管理员" in messages[1]["content"]


def test_each_analysis_uses_one_agent_without_shared_history() -> None:
    fake_llm = FakeLLM(analysis_json("consultation"), analysis_json("unknown"))
    analyzer = IssueAnalyzer(fake_llm)

    analyzer.analyze(TextConsultationInput(message="第一个问题"))
    analyzer.analyze(TextConsultationInput(message="第二个问题"))

    assert len(fake_llm.calls) == 2
    assert [message["role"] for message in fake_llm.calls[0]] == ["system", "user"]
    assert [message["role"] for message in fake_llm.calls[1]] == ["system", "user"]
    assert fake_llm.calls[1][-1]["content"] == "第二个问题"
    assert "第一个问题" not in str(fake_llm.calls[1])


def test_unsupported_category_is_rejected_by_structured_guard() -> None:
    analyzer = IssueAnalyzer(FakeLLM(analysis_json("environment")))

    with pytest.raises(AnalysisOutputError) as captured:
        analyzer.analyze(TextConsultationInput(message="现场扬尘很大。"))

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


@pytest.mark.parametrize(
    "invalid_output",
    ["```json\n{}\n```", "[TOOL_CALL:create_task:title=测试]"],
)
def test_non_json_or_tool_call_output_is_rejected(invalid_output: str) -> None:
    analyzer = IssueAnalyzer(FakeLLM(invalid_output))

    with pytest.raises(AnalysisOutputError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisOutputErrorCode.INVALID_JSON


def test_analysis_timeout_has_stable_error() -> None:
    analyzer = IssueAnalyzer(FakeLLM(TimeoutError("provider timeout detail")))

    with pytest.raises(AnalysisExecutionError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisExecutionErrorCode.MODEL_TIMEOUT
    assert "provider timeout detail" not in str(captured.value)


def test_analysis_model_failure_has_stable_error() -> None:
    analyzer = IssueAnalyzer(FakeLLM(RuntimeError("provider secret detail")))

    with pytest.raises(AnalysisExecutionError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisExecutionErrorCode.MODEL_ERROR
    assert "provider secret detail" not in str(captured.value)
