from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.proposals import Phase2ProposalService
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_store import JsonIssueRecordStore


def analysis_payload(category: str, risk_level: str = "low") -> dict[str, object]:
    high_risk = risk_level in {"high", "emergency"}
    return {
        "category": category,
        "issue_type": "宿舍门锁损坏" if category == "logistics" else "临边防护缺失",
        "summary": "用户报告现场存在需要跟进的问题。",
        "observed_facts": ["用户报告现场存在需要跟进的问题"],
        "uncertainties": [],
        "missing_fields": [],
        "risk_level": risk_level,
        "immediate_actions": ["立即远离危险区域并通知专业人员"] if high_risk else [],
        "suggested_actions": ["安排现场人员核实并跟进"],
        "recommended_route": "human_review" if high_risk else "propose_workflow",
        "requires_human_review": high_risk,
        "confidence": 0.9,
    }


def phase3_client(tmp_path: Path) -> TestClient:
    proposal_service = Phase2ProposalService(integrity_key=b"i" * 32)
    workflow_service = IssueWorkflowService(
        JsonIssueRecordStore(tmp_path / "api-records.json"),
        confirmation_verifier=proposal_service.verify_confirmation,
    )
    return TestClient(
        create_app(
            proposal_service=proposal_service,
            workflow_service=workflow_service,
        )
    )


def confirmed_payload(
    client: TestClient,
    *,
    category: str,
    risk_level: str,
    suffix: str,
) -> dict[str, object]:
    preview_data = client.post(
        "/api/issue-proposals/preview",
        json={
            "invocation_id": f"preview-api-{suffix}",
            "analysis": analysis_payload(category, risk_level),
        },
    ).json()["data"]
    proposal = preview_data["proposal"]
    edited = {
        **proposal["review_fields"],
        "project": "API 验收项目",
        "area": "API 验收区域",
    }
    response = client.post(
        "/api/issue-proposals/confirm",
        json={
            "proposal": proposal,
            "proposal_token": preview_data["proposal_token"],
            "edited_fields": edited,
            "confirmed": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def post_action(
    client: TestClient,
    record: dict[str, object],
    action: str,
    actor_id: str,
    role: str,
    **fields: object,
) -> dict[str, object]:
    response = client.post(
        f"/api/issue-records/{record['record_id']}/actions",
        json={
            "action": action,
            "actor": {"actor_id": actor_id, "role": role},
            "expected_revision": record["revision"],
            **fields,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_logistics_api_runs_complete_lifecycle_with_rework(tmp_path: Path) -> None:
    client = phase3_client(tmp_path)
    confirmation = confirmed_payload(
        client,
        category="logistics",
        risk_level="low",
        suffix="logistics-e2e-001",
    )
    create_request = {
        "confirmation": confirmation,
        "idempotency_key": "create-logistics-e2e-001",
        "actor": {"actor_id": "reporter-api", "role": "reporter"},
    }
    created = client.post("/api/issue-records", json=create_request)
    assert created.status_code == 200
    assert created.json()["created"] is True
    record = created.json()["record"]
    assert record["status"] == "draft"
    assert record["suggested_responsible_role"] == "facilities_staff"
    assert record["assigned_to"] is None

    repeated = client.post("/api/issue-records", json=create_request)
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["record"]["record_id"] == record["record_id"]

    record = post_action(client, record, "submit", "reporter-api", "reporter")
    record = post_action(
        client,
        record,
        "assign",
        "coordinator-api",
        "coordinator",
        assignee_id="facilities-api",
        assignee_role="facilities_staff",
    )
    record = post_action(
        client,
        record,
        "start_rectification",
        "facilities-api",
        "rectifier",
    )
    record = post_action(
        client,
        record,
        "submit_rectification",
        "facilities-api",
        "rectifier",
        note="已更换门锁。",
    )
    record = post_action(
        client,
        record,
        "reject_review",
        "reviewer-api",
        "reviewer",
        note="锁闭测试未通过，请重新整改。",
    )
    record = post_action(
        client,
        record,
        "submit_rectification",
        "facilities-api",
        "rectifier",
        note="已调整锁舌并重新测试。",
    )
    record = post_action(
        client,
        record,
        "close",
        "reviewer-api",
        "reviewer",
        note="复查通过。",
    )
    assert record["status"] == "closed"
    assert record["revision"] == 8
    assert len(record["events"]) == 8

    fetched = client.get(f"/api/issue-records/{record['record_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == record


def test_api_rejects_tampered_confirmation_and_stale_revision(tmp_path: Path) -> None:
    client = phase3_client(tmp_path)
    confirmation = confirmed_payload(
        client,
        category="logistics",
        risk_level="medium",
        suffix="tampered-confirmation-001",
    )
    tampered = {
        **confirmation,
        "analysis": {**confirmation["analysis"], "risk_level": "low"},
    }
    rejected = client.post(
        "/api/issue-records",
        json={
            "confirmation": tampered,
            "idempotency_key": "create-tampered-confirmation-001",
            "actor": {"actor_id": "reporter-api", "role": "reporter"},
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["error_code"] == "invalid_confirmation"

    valid = client.post(
        "/api/issue-records",
        json={
            "confirmation": confirmation,
            "idempotency_key": "create-valid-confirmation-001",
            "actor": {"actor_id": "reporter-api", "role": "reporter"},
        },
    ).json()["record"]
    submitted = post_action(client, valid, "submit", "reporter-api", "reporter")
    stale = client.post(
        f"/api/issue-records/{valid['record_id']}/actions",
        json={
            "action": "submit",
            "actor": {"actor_id": "reporter-api", "role": "reporter"},
            "expected_revision": valid["revision"],
        },
    )
    assert submitted["revision"] == 2
    assert stale.status_code == 409
    assert stale.json()["detail"]["error_code"] == "revision_conflict"


def test_api_high_risk_submitter_cannot_close_own_record(tmp_path: Path) -> None:
    client = phase3_client(tmp_path)
    confirmation = confirmed_payload(
        client,
        category="safety",
        risk_level="high",
        suffix="high-risk-close-001",
    )
    record = client.post(
        "/api/issue-records",
        json={
            "confirmation": confirmation,
            "idempotency_key": "create-high-risk-close-001",
            "actor": {"actor_id": "same-person", "role": "reporter"},
        },
    ).json()["record"]
    record = post_action(client, record, "submit", "same-person", "reporter")
    record = post_action(
        client,
        record,
        "assign",
        "coordinator-api",
        "coordinator",
        assignee_id="rectifier-api",
        assignee_role="safety_officer",
    )
    record = post_action(
        client,
        record,
        "start_rectification",
        "rectifier-api",
        "rectifier",
    )
    record = post_action(
        client,
        record,
        "submit_rectification",
        "rectifier-api",
        "rectifier",
        note="整改完成。",
    )
    response = client.post(
        f"/api/issue-records/{record['record_id']}/actions",
        json={
            "action": "close",
            "actor": {"actor_id": "same-person", "role": "professional_reviewer"},
            "expected_revision": record["revision"],
            "note": "试图自行关闭。",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == (
        "submitter_cannot_close_high_risk"
    )
