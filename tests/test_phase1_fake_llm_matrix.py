import json
from typing import Any

import pytest
from pydantic import ValidationError

from agents.analysis import (
    AnalysisExecutionError,
    AnalysisExecutionErrorCode,
    IssueAnalyzer,
)
from agents.schemas import TextConsultationInput
from agents.structured_output import AnalysisOutputError, AnalysisOutputErrorCode


class RecordingFakeLLM:
    def __init__(self, result: str | Exception) -> None:
        self._result = result
        self.call_count = 0

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        self.call_count += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def normal_analysis_json() -> str:
    return json.dumps(
        {
            "category": "consultation",
            "issue_type": "个人防护咨询",
            "summary": "用户咨询安全帽下颏带检查方法。",
            "observed_facts": ["用户询问安全帽下颏带怎么检查"],
            "uncertainties": [],
            "missing_fields": [],
            "risk_level": "low",
            "immediate_actions": [],
            "suggested_actions": ["说明贴合和防松脱检查方法"],
            "recommended_route": "direct_answer",
            "requires_human_review": False,
            "confidence": 0.95,
        },
        ensure_ascii=False,
    )


def test_fake_llm_normal_analysis() -> None:
    fake_llm = RecordingFakeLLM(normal_analysis_json())
    analyzer = IssueAnalyzer(fake_llm)

    result = analyzer.analyze(TextConsultationInput(message="安全帽下颏带怎么检查？"))

    assert result.category.value == "consultation"
    assert result.recommended_route.value == "direct_answer"
    assert fake_llm.call_count == 1


def test_empty_input_is_rejected_before_fake_llm_call() -> None:
    fake_llm = RecordingFakeLLM(normal_analysis_json())
    analyzer = IssueAnalyzer(fake_llm)

    with pytest.raises(ValidationError):
        analyzer.analyze(TextConsultationInput(message="   "))

    assert fake_llm.call_count == 0


def test_fake_llm_invalid_json() -> None:
    analyzer = IssueAnalyzer(RecordingFakeLLM("{invalid-json}"))

    with pytest.raises(AnalysisOutputError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisOutputErrorCode.INVALID_JSON


def test_fake_llm_timeout() -> None:
    analyzer = IssueAnalyzer(RecordingFakeLLM(TimeoutError("provider detail")))

    with pytest.raises(AnalysisExecutionError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisExecutionErrorCode.MODEL_TIMEOUT
    assert "provider detail" not in str(captured.value)


def test_fake_llm_model_error() -> None:
    analyzer = IssueAnalyzer(RecordingFakeLLM(RuntimeError("provider secret")))

    with pytest.raises(AnalysisExecutionError) as captured:
        analyzer.analyze(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == AnalysisExecutionErrorCode.MODEL_ERROR
    assert "provider secret" not in str(captured.value)
