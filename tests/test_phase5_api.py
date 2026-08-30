import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.vision import SingleImageAnalyzer, VisionError
from backend.app.main import create_app
from backend.app.photo_store import PhotoStore
from backend.app.photos import PhotoService
from backend.app.proposals import Phase2ProposalService
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_store import JsonIssueRecordStore
from test_phase3_api import confirmed_payload, post_action
from test_phase5_images import FakeVisionBackend, make_image, vision_payload


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")
    def forbidden(*args, **kwargs): raise AssertionError("Paid model calls forbidden in pytest")
    monkeypatch.setattr("agents.vision.OpenAI", forbidden)


def photo_client(tmp_path: Path, response=None):
    proposals = Phase2ProposalService(integrity_key=b"p" * 32)
    workflow = IssueWorkflowService(JsonIssueRecordStore(tmp_path / "records.json"), confirmation_verifier=proposals.verify_confirmation)
    fake = FakeVisionBackend(response if response is not None else json.dumps(vision_payload(count=2, risk="high")))
    service = PhotoService(PhotoStore(tmp_path / "photos"), proposals, workflow,
                           analyzer_factory=lambda mode: SingleImageAnalyzer(fake))
    client = TestClient(create_app(proposal_service=proposals, workflow_service=workflow, photo_service=service))
    return client, service, fake


def upload(client, *, color="white"):
    response = client.post("/api/photos", content=make_image(color=color),
                           headers={"Content-Type": "image/png", "X-Upload-Authorized": "true"})
    assert response.status_code == 200, response.text
    return response.json()


def analyze(client, photo):
    response = client.post(f"/api/photos/{photo['photo_id']}/analysis", json={"context": "合成验收输入"})
    assert response.status_code == 200, response.text
    return response.json()


def decision(candidate="CAND-1", kind="accept", **fields):
    return {"candidate_id": candidate, "decision": kind, "corrected_summary": "人工纠正的可见情况，待专业确认",
            "note": "核对图片与文字，不能单凭照片认定", "confirmed": True, **fields}


def test_upload_content_headers_and_no_workflow_side_effect(tmp_path):
    client, service, _ = photo_client(tmp_path)
    photo = upload(client)
    assert photo["metadata_removed"] is True
    content = client.get(f"/api/photos/{photo['photo_id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/jpeg"
    assert content.headers["cache-control"] == "no-store"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert not (tmp_path / "records.json").exists()


def test_upload_requires_consent_rejects_multi_file_and_size(tmp_path):
    client, _, _ = photo_client(tmp_path)
    assert client.post("/api/photos", content=make_image(), headers={"Content-Type": "image/png"}).status_code == 403
    multipart = client.post("/api/photos", files=[("photos", ("a.png", make_image())), ("photos", ("b.png", make_image()))], headers={"X-Upload-Authorized": "true"})
    assert multipart.status_code == 415
    response = client.post("/api/photos", content=b"x" * (5 * 1024 * 1024 + 1), headers={"Content-Type": "image/png", "X-Upload-Authorized": "true"})
    assert response.status_code == 413
    assert not (tmp_path / "photos").exists()


def test_real_mode_needs_per_call_consent_but_tests_stay_fake(tmp_path, monkeypatch):
    client, _, fake = photo_client(tmp_path)
    photo = upload(client)
    monkeypatch.setenv("AGENT_MODE", "real")
    endpoint = f"/api/photos/{photo['photo_id']}/analysis"
    assert client.post(endpoint, json={"context": "context"}).status_code == 403
    assert not fake.calls
    assert client.post(endpoint, json={"context": "context", "allow_external": "true"}).status_code == 400
    assert client.post(endpoint, json={"context": "context", "allow_external": True}).status_code == 200
    assert len(fake.calls) == 1


def test_candidate_correction_rejection_and_preserved_risk(tmp_path):
    client, service, _ = photo_client(tmp_path)
    result = analyze(client, upload(client))
    endpoint = f"/api/photo-analyses/{result['analysis_id']}/decisions"
    assert len(result["result"]["candidates"]) == 2
    assert client.post(endpoint, json=decision(risk_level="low")).status_code == 400
    corrected = client.post(endpoint, json=decision()).json()
    proposal = corrected["data"]["proposal"]
    assert proposal["analysis"]["risk_level"] == "high"
    assert proposal["analysis"]["requires_human_review"] is True
    assert proposal["analysis"]["summary"] == decision()["corrected_summary"]
    assert proposal["analysis"]["immediate_actions"]
    assert client.post(endpoint, json=decision()).status_code == 409
    assert client.post(endpoint, json=decision("CAND-2", "reject")).json()["ok"]
    assert not (tmp_path / "records.json").exists()
    snapshot = service.store.snapshot()
    assert len(snapshot.decisions) == 2
    assert snapshot.analyses[result["analysis_id"]].result.candidates[0].analysis.summary != proposal["analysis"]["summary"]


@pytest.mark.parametrize("response,code", [("{", "invalid_vision_output"),
                                          (TimeoutError("PRIVATE-provider"), "vision_timeout"),
                                          (RuntimeError("PRIVATE-provider"), "vision_provider_error")])
def test_image_failures_do_not_affect_text_proposals_or_leak(tmp_path, response, code):
    client, service, fake = photo_client(tmp_path, response)
    photo = upload(client)
    result = client.post(f"/api/photos/{photo['photo_id']}/analysis", json={"context": "PRIVATE-user"})
    assert result.status_code == 503
    assert result.json()["detail"]["error_code"] == code
    assert len(fake.calls) == 1
    assert not service.store.snapshot().analyses
    assert "PRIVATE" not in result.text
    logs = " ".join(event.model_dump_json() for event in service.audit.snapshot())
    assert "PRIVATE" not in logs and "reasoning" not in logs
    assert confirmed_payload(client, category="logistics", risk_level="low", suffix="image-fallback")["user_confirmed"]


def test_before_after_photos_share_record_without_changing_state(tmp_path):
    client, _, _ = photo_client(tmp_path)
    confirmation = confirmed_payload(client, category="safety", risk_level="high", suffix="photos-e2e")
    record = client.post("/api/issue-records", json={"confirmation": confirmation, "idempotency_key": "photo-create-001",
        "actor": {"actor_id": "reporter-photo", "role": "reporter"}}).json()["record"]
    before, after = upload(client), upload(client, color="blue")
    endpoint = f"/api/issue-records/{record['record_id']}/photos"
    request = {"photo_id": before["photo_id"], "stage": "before", "actor": {"actor_id": "reporter-photo", "role": "reporter"},
               "expected_revision": record["revision"], "confirmed": True}
    raw = (tmp_path / "records.json").read_bytes()
    assert client.post(endpoint, json=request).status_code == 200
    assert client.post(endpoint, json=request).status_code == 200
    assert (tmp_path / "records.json").read_bytes() == raw
    assert client.post(endpoint, json={**request, "stage": "after"}).status_code == 403
    record = post_action(client, record, "submit", "reporter-photo", "reporter")
    assert client.post(endpoint, json=request).status_code == 409
    record = post_action(client, record, "assign", "coordinator-photo", "coordinator", assignee_id="rectifier-photo", assignee_role="safety_officer")
    record = post_action(client, record, "start_rectification", "rectifier-photo", "rectifier")
    after_request = {**request, "photo_id": after["photo_id"], "stage": "after", "expected_revision": record["revision"],
                     "actor": {"actor_id": "rectifier-photo", "role": "rectifier"}}
    raw = (tmp_path / "records.json").read_bytes()
    assert client.post(endpoint, json=after_request).status_code == 200
    assert client.post(endpoint, json={**after_request, "photo_id": before["photo_id"]}).status_code == 409
    links = client.get(endpoint).json()
    assert [item["link"]["stage"] for item in links] == ["before", "after"]
    assert {item["link"]["record_id"] for item in links} == {record["record_id"]}
    assert (tmp_path / "records.json").read_bytes() == raw
    record = post_action(client, record, "submit_rectification", "rectifier-photo", "rectifier", note="合成整改说明")
    record = post_action(client, record, "close", "reviewer-photo", "professional_reviewer", note="人工复查关闭，不由图片自动关闭")
    assert client.post(endpoint, json={**after_request, "expected_revision": record["revision"]}).status_code == 409


def test_missing_photos_records_and_extra_fields(tmp_path):
    client, _, _ = photo_client(tmp_path)
    assert client.get("/api/photos/PHOTO-000000000000000000000000/content").status_code == 404
    assert client.get("/api/issue-records/ISS-000000000000/photos").status_code == 404
    photo = upload(client)
    assert client.post(f"/api/photos/{photo['photo_id']}/analysis", json={"context": "test", "model": "other"}).status_code == 400
    assert client.post("/api/photo-analyses/VIS-000000000000000000000000/decisions", json=decision()).status_code == 404


@pytest.mark.parametrize("value", [1, 1.0, "true", False])
def test_numeric_or_string_confirmation_cannot_bypass_human_gate(tmp_path, value):
    client, _, _ = photo_client(tmp_path)
    result = analyze(client, upload(client))
    response = client.post(f"/api/photo-analyses/{result['analysis_id']}/decisions", json=decision(confirmed=value))
    assert response.status_code == 400


def test_failed_proposal_does_not_consume_candidate_and_can_retry(tmp_path, monkeypatch):
    from agents.tools import ToolResult
    client, service, _ = photo_client(tmp_path)
    result = analyze(client, upload(client))
    original = service.proposals.preview
    monkeypatch.setattr(service.proposals, "preview", lambda request: ToolResult(
        tool_name="propose_issue_record", ok=False, error_code="internal_error", summary="提案失败"))
    endpoint = f"/api/photo-analyses/{result['analysis_id']}/decisions"
    assert client.post(endpoint, json=decision()).status_code == 503
    assert service.store.snapshot().decisions == []
    monkeypatch.setattr(service.proposals, "preview", original)
    assert client.post(endpoint, json=decision()).status_code == 200


def test_analysis_count_is_bounded_before_extra_model_call(tmp_path):
    client, service, fake = photo_client(tmp_path)
    photo = upload(client)
    for _ in range(10): analyze(client, photo)
    assert client.post(f"/api/photos/{photo['photo_id']}/analysis", json={"context": "context"}).status_code == 409
    assert len(fake.calls) == 10
