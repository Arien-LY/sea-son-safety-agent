from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.tools.search_knowledge import SearchKnowledgeTool
from backend.app.main import create_app
from backend.app.proposals import Phase2ProposalService
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_store import JsonIssueRecordStore
from test_phase3_api import analysis_payload, confirmed_payload, post_action


def make_client(tmp_path: Path, *, enabled: bool = True) -> TestClient:
    proposals = Phase2ProposalService(integrity_key=b"k" * 32)
    workflow = IssueWorkflowService(JsonIssueRecordStore(tmp_path / "records.json"),
                                    confirmation_verifier=proposals.verify_confirmation)
    return TestClient(create_app(
        proposal_service=proposals, workflow_service=workflow,
        knowledge_tool=SearchKnowledgeTool(enabled=enabled, clock=lambda: date(2026, 8, 30)),
    ))


def test_readonly_api_has_three_sections_and_traceable_citations(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    result = client.post("/api/knowledge/answer", json={
        "analysis": analysis_payload("safety", "high"),
        "query": "临边防护", "jurisdiction": "cn_mainland",
    })
    assert result.status_code == 200
    data = result.json()
    assert data["analysis"]["requires_human_review"] is True
    assert data["human_conclusion"]["status"] == "not_reviewed"
    assert data["retrieved_evidence"][0]["entry"]["entry_id"] == "KB-SAF-028"
    assert data["model_suggestions"] == data["analysis"]["suggested_actions"]
    assert not (tmp_path / "records.json").exists()
    native = client.post("/api/knowledge/search", json={"query": "临边", "jurisdiction": "cn_mainland"}).json()
    assert native["tool_name"] == "search_knowledge" and native["ok"]


@pytest.mark.parametrize("extra", [
    {"human_conclusion": {"status": "reviewed", "note": "自动通过"}},
    {"retrieved_evidence": [{"source": "虚假"}]}, {"enabled": True}, {"as_of": "2020-01-01"},
])
def test_api_rejects_forged_evidence_conclusions_and_clock(tmp_path: Path, extra: dict) -> None:
    result = make_client(tmp_path).post("/api/knowledge/answer", json={
        "analysis": analysis_payload("safety"), "query": "临边", **extra,
    })
    assert result.status_code == 400
    assert result.json()["detail"]["error_code"] == "invalid_arguments"


def test_api_rejects_coerced_analysis_and_disabled_keeps_safety(tmp_path: Path) -> None:
    client = make_client(tmp_path, enabled=False)
    payload = {"analysis": analysis_payload("safety", "high"), "query": "临边", "jurisdiction": "cn_mainland"}
    response = client.post("/api/knowledge/answer", json=payload)
    assert response.status_code == 200
    assert response.json()["knowledge_error_code"] == "knowledge_disabled"
    assert response.json()["analysis"] == payload["analysis"]
    payload["analysis"]["requires_human_review"] = "true"
    assert client.post("/api/knowledge/answer", json=payload).status_code == 400


def test_default_environment_switch_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "false")
    client = TestClient(create_app())
    assert client.post("/api/knowledge/search", json={"query": "临边"}).json()["error_code"] == "knowledge_disabled"


def test_only_persisted_close_event_is_human_conclusion_and_retrieval_never_writes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    confirmation = confirmed_payload(client, category="safety", risk_level="high", suffix="knowledge-001")
    record = client.post("/api/issue-records", json={
        "confirmation": confirmation, "idempotency_key": "knowledge-create-001",
        "actor": {"actor_id": "reporter-test", "role": "reporter"},
    }).json()["record"]
    path = tmp_path / "records.json"
    endpoint = f"/api/issue-records/{record['record_id']}/knowledge"
    query = {"query": "临边", "jurisdiction": "cn_mainland"}
    before = path.read_bytes()
    assert client.post(endpoint, json=query).json()["human_conclusion"]["status"] == "not_reviewed"
    assert client.post(endpoint, json={**query, "analysis": analysis_payload("safety", "low")}).status_code == 400
    assert path.read_bytes() == before
    record = post_action(client, record, "submit", "reporter-test", "reporter")
    record = post_action(client, record, "assign", "coordinator-test", "coordinator",
                         assignee_id="rectifier-test", assignee_role="safety_officer")
    record = post_action(client, record, "start_rectification", "rectifier-test", "rectifier")
    record = post_action(client, record, "submit_rectification", "rectifier-test", "rectifier", note="整改完成")
    assert client.post(endpoint, json=query).json()["human_conclusion"]["status"] == "not_reviewed"
    record = post_action(client, record, "close", "professional-test", "professional_reviewer", note="人工复查通过，已核对防护")
    before = path.read_bytes()
    answer = client.post(endpoint, json=query).json()
    conclusion = answer["human_conclusion"]
    assert conclusion == {
        "status": "reviewed", "record_id": record["record_id"], "revision": 6,
        "actor_id": "professional-test", "actor_role": "professional_reviewer",
        "occurred_at": record["events"][-1]["occurred_at"], "note": record["events"][-1]["note"],
    }
    assert answer["analysis"] == record["analysis"]
    assert path.read_bytes() == before


def test_missing_and_corrupt_record_never_yield_fabricated_conclusion(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    endpoint = "/api/issue-records/ISS-000000000000/knowledge"
    assert client.post(endpoint, json={"query": "临边"}).status_code == 404
    (tmp_path / "records.json").write_text("{", encoding="utf-8")
    result = client.post(endpoint, json={"query": "临边"})
    assert result.status_code == 500
    assert result.json()["detail"]["error_code"] == "store_error"
