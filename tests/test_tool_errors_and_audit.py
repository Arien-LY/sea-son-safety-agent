from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from agents.tools import ProposeIssueRecordTool, ToolAuditLog, ToolResult


def valid_payload() -> dict[str, Any]:
    return {
        "category": "quality",
        "issue_type": "墙面开裂",
        "summary": "用户报告墙面出现连续裂缝，需要现场核实。",
        "observed_facts": ["用户报告墙面出现连续裂缝"],
        "uncertainties": ["裂缝宽度和延伸范围未知"],
        "missing_fields": ["具体区域", "裂缝宽度", "延伸范围"],
        "risk_level": "medium",
        "immediate_actions": [],
        "suggested_actions": ["安排质量人员现场核实"],
        "recommended_route": "propose_workflow",
        "requires_human_review": False,
        "confidence": 0.8,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "tool_name": "test",
            "ok": True,
            "summary": "成功",
            "error_code": "unexpected",
        },
        {
            "tool_name": "test",
            "ok": True,
            "summary": "成功",
            "recoverable": True,
        },
        {"tool_name": "test", "ok": False, "summary": "失败"},
    ],
)
def test_tool_result_rejects_inconsistent_success_and_error_fields(payload) -> None:
    with pytest.raises(ValidationError):
        ToolResult.model_validate(payload)


def test_duplicate_successful_call_returns_uniform_error() -> None:
    tool = ProposeIssueRecordTool()
    payload = valid_payload()

    first = tool.run(payload)
    duplicate = tool.run(payload)

    assert first.ok is True
    assert duplicate.ok is False
    assert duplicate.recoverable is True
    assert duplicate.error_code == "duplicate_call"
    assert duplicate.data == {}


def test_internal_proposal_error_is_caught_without_detail_leak() -> None:
    def fail_factory(_analysis):
        raise RuntimeError("PRIVATE-INTERNAL-DETAIL")

    tool = ProposeIssueRecordTool(proposal_factory=fail_factory)

    result = tool.run(valid_payload())

    assert result.ok is False
    assert result.recoverable is False
    assert result.error_code == "internal_error"
    assert "PRIVATE-INTERNAL-DETAIL" not in result.summary


def test_audit_records_safe_metadata_without_argument_values_or_thoughts() -> None:
    fixed_time = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    audit_log = ToolAuditLog(clock=lambda: fixed_time)
    tool = ProposeIssueRecordTool(audit_log=audit_log)
    payload = valid_payload()
    payload["summary"] = "SENSITIVE-USER-CONTENT"

    result = tool.run(payload)
    event = audit_log.snapshot()[0]
    serialized = event.model_dump_json()

    assert result.ok is True
    assert event.occurred_at == fixed_time
    assert event.tool_name == "propose_issue_record"
    assert event.ok is True
    assert event.error_code is None
    assert event.argument_keys == tuple(sorted(payload))
    assert event.argument_digest.startswith("sha256:")
    assert "SENSITIVE-USER-CONTENT" not in serialized
    assert "thought" not in serialized.casefold()
    assert "reasoning" not in serialized.casefold()


def test_audit_buffer_is_capacity_limited() -> None:
    audit_log = ToolAuditLog(max_events=2)
    for index in range(3):
        result = ToolResult(
            tool_name="test_tool",
            ok=False,
            summary="测试错误",
            error_code=f"error_{index}",
        )
        audit_log.record(
            tool_name="test_tool",
            arguments={"index": index},
            result=result,
        )

    events = audit_log.snapshot()
    assert [event.error_code for event in events] == ["error_1", "error_2"]
