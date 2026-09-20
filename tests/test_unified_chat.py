import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.text_consultations import TextConsultationService, text_runtime
from backend.app.text_models import TextRequest
from backend.app.proposals import Phase2ProposalService
from agents.text_assistant import DeepSeekTextBackend, TextAssistant, TextConfig
from test_product_text import FakeTextBackend, decision_payload


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")
    monkeypatch.setattr("agents.text_assistant.OpenAI", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("No real model calls")))


def payload(**overrides):
    value = {
        "request_id": "unified-test-0001",
        "intent": "auto",
        "model": None,
        "input": {"message": "宿舍空调坏了，帮我上报"},
        "consultation_id": None,
        "expected_turn": 0,
        "allow_external": False,
    }
    value.update(overrides)
    return value


def test_unified_request_has_long_chat_capacity_and_strict_model_id():
    request = TextRequest.model_validate(payload(input={"message": "问" * 16_000}))
    assert request.intent == "auto"
    assert len(request.input.message) == 16_000
    assert TextRequest.model_validate(payload(model="deepseek-custom-2026")).model == "deepseek-custom-2026"
    for invalid in ("", "../model", "model with spaces", "x" * 101):
        with pytest.raises(ValueError):
            TextRequest.model_validate(payload(model=invalid))


def test_unified_ai_decision_routes_logistics_without_creating_a_record():
    fake = FakeTextBackend([decision_payload("logistics", "medium")])
    seen = []
    service = TextConsultationService(
        Phase2ProposalService(integrity_key=b"u" * 32),
        assistant_factory=lambda mode, model: seen.append((mode, model)) or TextAssistant(fake),
    )
    result = service.send(TextRequest.model_validate(payload(model="deepseek-v4-pro")))
    assert result.can_propose
    assert result.reply.analysis.category == "logistics"
    assert result.model == "mock-no-text-understanding"
    assert seen == [("mock", "mock-no-text-understanding")]
    assert service.proposals.audit_snapshot() == ()


def test_unified_transport_keeps_deep_chat_budget_and_strict_json(monkeypatch):
    captured = {}
    message = SimpleNamespace(content=json.dumps(decision_payload("logistics", "medium"), ensure_ascii=False), tool_calls=None)

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=message)])

    class Client:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        def __enter__(self): return self
        def __exit__(self, *args): pass

    monkeypatch.setattr("agents.text_assistant.OpenAI", Client)
    backend = DeepSeekTextBackend(TextConfig(
        api_key="FAKE", model="deepseek-custom-2026", base_url="https://api.deepseek.com"))
    raw = backend.invoke([{"role": "user", "content": "structured"}], unified=True)
    assert json.loads(raw)["ticket_decision"]["category"] == "logistics"
    assert captured["settings"]["timeout"] == 180 and captured["settings"]["max_retries"] == 0
    assert captured["max_tokens"] == 32768
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["reasoning_effort"] == "high"
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}


def test_runtime_exposes_model_choices_without_secrets(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "real")
    monkeypatch.setenv("LLM_API_KEY", "PRIVATE-secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_MODEL_OPTIONS", "deepseek-v4-pro, deepseek-custom-2026")
    runtime = text_runtime()
    assert runtime["available_models"] == ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-custom-2026"]
    assert runtime["custom_model_allowed"] is True
    assert "PRIVATE" not in json.dumps(runtime)


def test_answer_stream_contains_validated_deltas_before_the_final_result(tmp_path):
    from test_product_text import text_client

    client, *_ = text_client(tmp_path, [decision_payload("logistics", "medium")])
    response = client.post("/api/text-consultations/stream", json=payload())
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    deltas = [event for event in events if event["type"] == "content_delta"]
    assert deltas and "".join(event["text"] for event in deltas) == events[-1]["data"]["reply"]["answer"]
    types = [event["type"] for event in events]
    responding = next(i for i, event in enumerate(events) if event.get("stage") == "responding")
    completed = next(i for i, event in enumerate(events) if event.get("stage") == "completed")
    assert responding < types.index("content_delta") < completed < len(events) - 1


def test_unified_contract_keeps_human_confirmation_and_honest_streaming_boundaries():
    contract = (Path(__file__).resolve().parents[1] / "docs/unified-chat-routing-contract.md").read_text(encoding="utf-8")
    for scenario in ("U01", "U02", "U03", "U04", "U05", "U06", "U07", "U08"):
        assert scenario in contract
    assert "不确认、不落库、不派工" in contract
    assert "不是供应商原始 token 直通" in contract
    assert "不会改善模型首字等待时间" in contract
