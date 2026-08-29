import json
from pathlib import Path

from agents.schemas import IssueCategory
from backend.app.workflow_models import (
    ActorRole,
    IssueRecord,
    RecordDisposition,
    RESPONSIBLE_ROLE_SUGGESTIONS,
    WorkflowAction,
    WorkflowStatus,
)


ROOT = Path(__file__).resolve().parents[1]
RECORD_SCHEMA_PATH = ROOT / "contracts" / "phase3_issue_record.v1.schema.json"
WORKFLOW_CONTRACT_PATH = ROOT / "contracts" / "phase3_workflow.v1.json"


def test_frozen_issue_record_schema_matches_pydantic_contract() -> None:
    frozen = json.loads(RECORD_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert frozen == IssueRecord.model_json_schema()
    assert frozen["additionalProperties"] is False


def test_machine_workflow_contract_matches_code_enums() -> None:
    contract = json.loads(WORKFLOW_CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["contract_version"] == "phase3-workflow-v1"
    assert contract["primary_statuses"] == [status.value for status in WorkflowStatus]
    assert contract["record_dispositions"] == [
        disposition.value for disposition in RecordDisposition
    ]
    assert contract["suggestion_is_assignment"] is False
    assert contract["responsible_role_suggestions"] == {
        category.value: role.value
        for category, role in RESPONSIBLE_ROLE_SUGGESTIONS.items()
    }


def test_transition_contract_has_unique_actions_and_known_values() -> None:
    contract = json.loads(WORKFLOW_CONTRACT_PATH.read_text(encoding="utf-8"))
    transitions = contract["transitions"]
    actions = [transition["action"] for transition in transitions]

    assert len(actions) == len(set(actions))
    assert set(actions) == {
        action.value
        for action in WorkflowAction
        if action not in {WorkflowAction.CREATE_DRAFT, WorkflowAction.CANCEL}
    }
    known_statuses = {status.value for status in WorkflowStatus}
    known_roles = {role.value for role in ActorRole}
    for transition in transitions:
        assert transition["from"] in known_statuses
        assert transition["to"] in known_statuses
        assert set(transition["actors"]) <= known_roles


def test_logistics_and_safety_share_contract_but_have_distinct_suggestions() -> None:
    assert RESPONSIBLE_ROLE_SUGGESTIONS[IssueCategory.SAFETY].value == "safety_officer"
    assert (
        RESPONSIBLE_ROLE_SUGGESTIONS[IssueCategory.LOGISTICS].value
        == "facilities_staff"
    )
    assert (
        RESPONSIBLE_ROLE_SUGGESTIONS[IssueCategory.SAFETY]
        != RESPONSIBLE_ROLE_SUGGESTIONS[IssueCategory.LOGISTICS]
    )
