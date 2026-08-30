import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from agents.text_assistant import TextError
from backend.app.text_models import TextRequest
from test_product_text import text_client, request_payload, reply_payload


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")
    def forbidden(*args, **kwargs):
        raise AssertionError("No real models")
    monkeypatch.setattr("agents.text_assistant.OpenAI", forbidden)


def events(client, payload):
    response = client.post("/api/text-consultations/stream", json=payload)
    assert response.status_code == 200, response.text
    assert "application/x-ndjson" in response.headers["content-type"]
    return [json.loads(line) for line in response.text.splitlines()]


def test_stream_reports_actual_steps_without_tools_and_replays_without_model(tmp_path):
    client, service, workflow, fake = text_client(tmp_path)
    payload = request_payload()
    trace = events(client, payload)
    progress = trace[:-1]
    assert [p["stage"] for p in progress] == ["queued", "preparing", "model_running", "validating", "completed"]
    assert [p["seq"] for p in progress] == list(range(1, 6))
    assert all(p["tool"] is None and p["elapsed_ms"] >= 0 for p in progress)
    assert trace[-1]["type"] == "result"
    assert workflow.store.snapshot() == ()
    replay = events(client, payload)
    assert replay[-1] == trace[-1]
    assert not any(p.get("stage") == "model_running" for p in replay)
    assert len(fake.messages) == 1


def test_stream_safe_error_has_no_result_or_raw_exception(tmp_path):
    client, *_ = text_client(tmp_path, [RuntimeError("SECRET-sentinel")])
    trace = events(client, request_payload())
    assert trace[-1]["type"] == "error"
    assert trace[-1]["error_code"] == "text_provider_error"
    assert "SECRET" not in json.dumps(trace)
    assert not any(p.get("stage") == "completed" for p in trace)


def test_slow_text_does_not_create_an_unbounded_queue(tmp_path):
    entered, release = Event(), Event()
    def slow(*args):
        entered.set()
        assert release.wait(5)
        return "Fake answer"
    _, service, _, _ = text_client(tmp_path, quick_answerer=slow)
    with ThreadPoolExecutor(2) as executor:
        first = executor.submit(service.send, TextRequest(**request_payload(intent="chat")))
        assert entered.wait(1)
        second = executor.submit(service.send, TextRequest(**request_payload(2, intent="chat")))
        try:
            with pytest.raises(TextError, match="繁忙"):
                second.result(timeout=2)
        finally:
            release.set()
            first.result(timeout=2)


def test_proposal_stream_only_reports_tool_after_eligibility(tmp_path):
    client, service, workflow, _ = text_client(tmp_path, [reply_payload("safety", "high")])
    reply = events(client, request_payload())[-1]["data"]
    url = f"/api/text-consultations/{reply['consultation_id']}/proposal/stream"
    response = client.post(url, json={"expected_turn": 1, "confirmed": True})
    trace = [json.loads(line) for line in response.text.splitlines()]
    assert [e["tool"] for e in trace if e.get("stage") == "tool_running"] == ["propose_issue_record"]
    assert trace[-1]["data"]["ok"]
    assert len(service.proposals.audit_snapshot()) == 1
    assert workflow.store.snapshot() == ()
    assert client.post(url, json={"expected_turn": 1, "confirmed": 1}).status_code == 400


def test_stream_rejects_invalid_body_before_starting(tmp_path):
    client, _, _, fake = text_client(tmp_path)
    assert client.post("/api/text-consultations/stream", json={"input": {"message": ""}}).status_code == 400
    assert not fake.messages
