import json
from pathlib import Path
from typing import Any

import pytest

from agents.schemas import IssueAnalysis
from agents.tools import (
    IssueRecordProposal,
    ProposeIssueRecordTool,
    build_issue_proposal_registry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase1_issue_analysis.v1.schema.json"
)
PROPOSAL_SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase2_issue_record_proposal.v1.schema.json"
)


def valid_issue_payload(
    *, recommended_route: str = "propose_workflow", risk_level: str = "medium"
) -> dict[str, Any]:
    high_risk = risk_level in {"high", "emergency"}
    return {
        "category": "safety",
        "issue_type": "临边防护",
        "summary": "用户报告作业层临边防护缺失，需要现场跟进。",
        "observed_facts": ["用户报告作业层临边没有防护栏杆"],
        "uncertainties": ["具体范围仍需现场核实"],
        "missing_fields": ["具体区域和影响范围"],
        "risk_level": risk_level,
        "immediate_actions": ["立即远离临边并提醒周边人员"] if high_risk else [],
        "suggested_actions": ["安排有资格的现场人员核实防护状态"],
        "recommended_route": recommended_route,
        "requires_human_review": high_risk,
        "confidence": 0.8,
    }


def test_phase2_registry_contains_exactly_one_tool() -> None:
    registry = build_issue_proposal_registry()

    assert registry.names == ("propose_issue_record",)


def test_tool_metadata_and_native_function_schema_are_frozen() -> None:
    tool = ProposeIssueRecordTool()
    schema = tool.to_openai_schema()
    frozen_analysis_schema = json.loads(ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8"))
    frozen_analysis_schema.pop("$schema")
    frozen_analysis_schema.pop("$id")

    assert tool.name == "propose_issue_record"
    assert "待用户确认" in tool.description
    assert "不保存、不派单" in tool.description
    assert schema == {
        "type": "function",
        "function": {
            "name": "propose_issue_record",
            "description": tool.description,
            "parameters": frozen_analysis_schema,
        },
    }


def test_eligible_analysis_returns_unpersisted_proposal() -> None:
    result = ProposeIssueRecordTool().run(valid_issue_payload())

    assert result.ok is True
    assert result.error_code is None
    proposal = IssueRecordProposal.model_validate_json(
        json.dumps(result.data["proposal"], ensure_ascii=False), strict=True
    )
    assert proposal.status == "awaiting_user_confirmation"
    assert proposal.requires_user_confirmation is True
    assert proposal.persisted is False
    assert proposal.dispatched is False
    assert proposal.analysis.recommended_route.value == "propose_workflow"


def test_high_risk_human_review_analysis_is_eligible() -> None:
    result = ProposeIssueRecordTool().run(
        valid_issue_payload(recommended_route="human_review", risk_level="high")
    )

    assert result.ok is True
    assert result.data["proposal"]["analysis"]["requires_human_review"] is True


@pytest.mark.parametrize("route", ["direct_answer", "collect_more_info"])
def test_non_follow_up_route_is_rejected(route: str) -> None:
    payload = valid_issue_payload(recommended_route=route, risk_level="low")
    if route == "collect_more_info":
        payload["category"] = "unknown"
        payload["risk_level"] = "undetermined"

    result = ProposeIssueRecordTool().run(payload)

    assert result.ok is False
    assert result.recoverable is True
    assert result.error_code == "issue_not_eligible_for_proposal"
    assert result.data == {}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("summary"),
        lambda payload: payload.update(confidence="0.8"),
        lambda payload: payload.update(responsible_person="某班组"),
    ],
)
def test_invalid_arguments_return_stable_safe_error(mutate) -> None:
    payload = valid_issue_payload()
    mutate(payload)

    result = ProposeIssueRecordTool().run(payload)

    assert result.ok is False
    assert result.recoverable is True
    assert result.error_code == "invalid_arguments"
    assert result.data == {}
    assert "某班组" not in result.summary


def test_frozen_proposal_contract_has_only_confirmation_safe_fields() -> None:
    frozen_schema = json.loads(PROPOSAL_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert frozen_schema["additionalProperties"] is False
    assert frozen_schema["properties"]["analysis"] == {
        "$ref": "phase1_issue_analysis.v1.schema.json"
    }
    assert frozen_schema["properties"]["requires_user_confirmation"]["const"] is True
    assert frozen_schema["properties"]["persisted"]["const"] is False
    assert frozen_schema["properties"]["dispatched"]["const"] is False
    assert frozen_schema["required"] == [
        "proposal_type",
        "status",
        "analysis",
        "requires_user_confirmation",
        "persisted",
        "dispatched",
    ]


def test_proposal_model_rejects_claimed_side_effects() -> None:
    proposal = {
        "proposal_type": "issue_record",
        "status": "awaiting_user_confirmation",
        "analysis": IssueAnalysis.model_validate(valid_issue_payload()),
        "requires_user_confirmation": True,
        "persisted": True,
        "dispatched": False,
    }

    with pytest.raises(ValueError):
        IssueRecordProposal.model_validate(proposal)
