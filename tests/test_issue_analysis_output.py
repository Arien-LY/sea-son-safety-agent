import json
from pathlib import Path
from typing import Any

import pytest

from agents.schemas import IssueAnalysis, IssueCategory, RecommendedRoute, RiskLevel
from agents.structured_output import (
    AnalysisOutputError,
    AnalysisOutputErrorCode,
    parse_issue_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase1_issue_analysis.v1.schema.json"
)


def valid_payload() -> dict[str, Any]:
    return {
        "category": "consultation",
        "issue_type": "个人防护咨询",
        "summary": "用户咨询安全帽下颏带的检查方法。",
        "observed_facts": ["用户询问安全帽下颏带怎么检查"],
        "uncertainties": [],
        "missing_fields": [],
        "risk_level": "low",
        "immediate_actions": [],
        "suggested_actions": ["说明下颏带贴合和防松脱检查方法"],
        "recommended_route": "direct_answer",
        "requires_human_review": False,
        "confidence": 0.95,
    }


def parse_payload(payload: dict[str, Any]) -> IssueAnalysis:
    return parse_issue_analysis(json.dumps(payload, ensure_ascii=False))


def test_valid_json_is_parsed_into_issue_analysis() -> None:
    analysis = parse_payload(valid_payload())

    assert analysis.category == IssueCategory.CONSULTATION
    assert analysis.risk_level == RiskLevel.LOW
    assert analysis.recommended_route == RecommendedRoute.DIRECT_ANSWER
    assert analysis.observed_facts == ["用户询问安全帽下颏带怎么检查"]


@pytest.mark.parametrize("raw_output", [None, b"{}", {}, []])
def test_non_string_output_has_stable_error(raw_output: object) -> None:
    with pytest.raises(AnalysisOutputError) as captured:
        parse_issue_analysis(raw_output)

    assert captured.value.error_code == AnalysisOutputErrorCode.INVALID_OUTPUT_TYPE
    assert str(captured.value) == "模型结构化输出必须是 JSON 字符串。"


@pytest.mark.parametrize("raw_output", ["", " \t\r\n "])
def test_empty_output_has_stable_error(raw_output: str) -> None:
    with pytest.raises(AnalysisOutputError) as captured:
        parse_issue_analysis(raw_output)

    assert captured.value.error_code == AnalysisOutputErrorCode.EMPTY_OUTPUT


@pytest.mark.parametrize(
    "raw_output",
    [
        "{not-json}",
        "```json\n{}\n```",
        '{"category": "consultation"} trailing text',
    ],
)
def test_malformed_or_fenced_json_is_rejected(raw_output: str) -> None:
    with pytest.raises(AnalysisOutputError) as captured:
        parse_issue_analysis(raw_output)

    assert captured.value.error_code == AnalysisOutputErrorCode.INVALID_JSON
    assert str(captured.value) == "模型输出不是合法 JSON。"


def test_required_lists_cannot_be_omitted() -> None:
    payload = valid_payload()
    payload.pop("missing_fields")

    with pytest.raises(AnalysisOutputError) as captured:
        parse_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


def test_extra_fields_are_rejected() -> None:
    payload = valid_payload()
    payload["responsible_person"] = "某班组"

    with pytest.raises(AnalysisOutputError) as captured:
        parse_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confidence", "0.95"),
        ("requires_human_review", "false"),
        ("observed_facts", "不是数组"),
    ],
)
def test_json_types_are_strict(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(AnalysisOutputError) as captured:
        parse_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


@pytest.mark.parametrize("invalid_detail", ["", "   ", "详" * 301])
def test_list_items_must_be_nonblank_and_bounded(invalid_detail: str) -> None:
    payload = valid_payload()
    payload["uncertainties"] = [invalid_detail]

    with pytest.raises(AnalysisOutputError) as captured:
        parse_payload(payload)

    assert captured.value.error_code == AnalysisOutputErrorCode.SCHEMA_VALIDATION_FAILED


def test_validation_error_does_not_echo_raw_model_output() -> None:
    secret_marker = "PRIVATE-MODEL-CONTENT"

    with pytest.raises(AnalysisOutputError) as captured:
        parse_issue_analysis(f"{{not-json:{secret_marker}}}")

    assert secret_marker not in str(captured.value)


def test_frozen_schema_matches_pydantic_contract() -> None:
    frozen_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert frozen_schema.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert frozen_schema.pop("$id").endswith("/phase1-issue-analysis-v1.schema.json")
    assert frozen_schema == IssueAnalysis.model_json_schema()
