from fastapi.testclient import TestClient

from backend.app.proposals import Phase2ProposalService
from backend.app.main import create_app


client = TestClient(create_app())


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_runtime_exposes_tutorial_baseline(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MODE", "mock")

    response = client.get("/api/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_mode"] == "mock"
    assert payload["framework"] == "hello-agents"
    assert payload["framework_version"] == "0.2.9"
    assert payload["tutorial_baseline"] == "Hello-Agents V1.0.3"


def test_invalid_runtime_mode_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MODE", "unexpected")

    response = client.get("/api/runtime")

    assert response.json()["agent_mode"] == "mock"


def proposal_analysis() -> dict[str, object]:
    return {
        "category": "management",
        "issue_type": "材料堆放",
        "summary": "通道旁材料堆放杂乱，需要现场跟进。",
        "observed_facts": ["用户报告通道旁材料堆放杂乱"],
        "uncertainties": ["具体项目和区域未知"],
        "missing_fields": ["项目", "具体区域"],
        "risk_level": "medium",
        "immediate_actions": [],
        "suggested_actions": ["安排现场管理人员核实"],
        "recommended_route": "propose_workflow",
        "requires_human_review": False,
        "confidence": 0.8,
    }


def test_proposal_preview_returns_suggestion_without_persistence() -> None:
    response = client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "preview-api-001", "analysis": proposal_analysis()},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["ok"] is True
    proposal = result["data"]["proposal"]
    assert result["data"]["proposal_token"].startswith("hmac-sha256:")
    assert proposal["status"] == "awaiting_user_confirmation"
    assert proposal["review_fields"]["record_title"] == "材料堆放"
    assert proposal["requires_user_confirmation"] is True
    assert proposal["persisted"] is False
    assert proposal["dispatched"] is False


def test_invalid_preview_body_returns_uniform_tool_result() -> None:
    response = client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "invalid-api-001", "analysis": {"summary": "缺字段"}},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["ok"] is False
    assert result["error_code"] == "invalid_arguments"
    assert result["data"] == {}


def test_duplicate_preview_id_is_rejected_and_audited() -> None:
    service = Phase2ProposalService()
    local_client = TestClient(create_app(proposal_service=service))
    request = {
        "invocation_id": "duplicate-api-001",
        "analysis": proposal_analysis(),
    }

    first = local_client.post("/api/issue-proposals/preview", json=request).json()
    duplicate = local_client.post("/api/issue-proposals/preview", json=request).json()

    assert first["ok"] is True
    assert duplicate["ok"] is False
    assert duplicate["error_code"] == "duplicate_call"
    events = service.audit_snapshot()
    assert len(events) == 2
    assert events[-1].error_code == "duplicate_call"


def test_confirmation_returns_server_diff_but_still_does_not_persist() -> None:
    preview_data = client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "confirm-api-001", "analysis": proposal_analysis()},
    ).json()["data"]
    preview = preview_data["proposal"]
    edited_fields = {
        **preview["review_fields"],
        "project": "验收演示项目",
        "area": "一层材料通道",
        "reporter_note": "请现场管理人员核实",
    }

    response = client.post(
        "/api/issue-proposals/confirm",
        json={
            "proposal": preview,
            "proposal_token": preview_data["proposal_token"],
            "edited_fields": edited_fields,
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    confirmed = response.json()
    assert confirmed["status"] == "confirmed_pending_persistence"
    assert {change["field"] for change in confirmed["changes"]} == {
        "project",
        "area",
        "reporter_note",
    }
    assert confirmed["analysis"] == preview["analysis"]
    assert confirmed["user_confirmed"] is True
    assert confirmed["persisted"] is False
    assert confirmed["dispatched"] is False


def test_confirmation_cannot_change_locked_analysis_fields() -> None:
    preview_data = client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "locked-api-001", "analysis": proposal_analysis()},
    ).json()["data"]
    preview = preview_data["proposal"]
    forged_fields = {
        **preview["review_fields"],
        "risk_level": "low",
    }

    response = client.post(
        "/api/issue-proposals/confirm",
        json={
            "proposal": preview,
            "proposal_token": preview_data["proposal_token"],
            "edited_fields": forged_fields,
            "confirmed": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "提案确认请求参数无效。"


def test_confirmation_rejects_tampered_locked_analysis() -> None:
    preview_data = client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "tamper-api-001", "analysis": proposal_analysis()},
    ).json()["data"]
    tampered_proposal = preview_data["proposal"]
    tampered_proposal["analysis"] = {
        **tampered_proposal["analysis"],
        "risk_level": "low",
        "recommended_route": "direct_answer",
    }

    response = client.post(
        "/api/issue-proposals/confirm",
        json={
            "proposal": tampered_proposal,
            "proposal_token": preview_data["proposal_token"],
            "edited_fields": tampered_proposal["review_fields"],
            "confirmed": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "提案完整性校验失败。"


def test_service_audit_does_not_contain_user_text() -> None:
    service = Phase2ProposalService()
    local_client = TestClient(create_app(proposal_service=service))
    analysis = proposal_analysis()
    analysis["summary"] = "PRIVATE-API-USER-CONTENT"

    local_client.post(
        "/api/issue-proposals/preview",
        json={"invocation_id": "audit-api-001", "analysis": analysis},
    )

    serialized = "".join(
        event.model_dump_json() for event in service.audit_snapshot()
    )
    assert "PRIVATE-API-USER-CONTENT" not in serialized
    assert "reasoning" not in serialized.casefold()
