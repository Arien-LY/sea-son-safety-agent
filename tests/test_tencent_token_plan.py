"""Tencent Cloud Token Plan provider: Fake SDK only; zero paid calls."""

import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from agents.schemas import TextConsultationInput
from agents.text_assistant import (
    TencentTokenPlanTextBackend, TextConfig, TextError,
    TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL, TEXT_PROVIDER_TENCENT_TOKEN_PLAN,
)
from backend.app.text_consultations import text_config, text_runtime
from test_product_text import text_client


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")

    def forbidden(*args, **kwargs):
        raise AssertionError("Real provider calls forbidden")

    monkeypatch.setattr("agents.text_assistant.OpenAI", forbidden)


def configure_tencent(monkeypatch, *, model="deepseek-v4-flash-202605"):
    monkeypatch.setenv("AGENT_MODE", "real")
    monkeypatch.setenv("LLM_PROVIDER", "tencent_token_plan")
    monkeypatch.setenv("TENCENT_TOKEN_PLAN_API_KEY", "FAKE-PRIVATE-TENCENT-KEY")
    monkeypatch.setenv("TENCENT_TOKEN_PLAN_MODEL", model)
    monkeypatch.setenv("TENCENT_TOKEN_PLAN_MODEL_OPTIONS", "glm-5.3, kimi-k3")
    monkeypatch.setenv("TENCENT_TOKEN_PLAN_BASE_URL", TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL)


def test_tencent_runtime_is_recognized_without_secret_exposure(monkeypatch):
    configure_tencent(monkeypatch)
    runtime = text_runtime()
    assert runtime["configured"] is True
    assert runtime["mode"] == "real"
    assert runtime["provider"] == "tencent_token_plan"
    assert runtime["external_provider"] == "腾讯云 Token Plan"
    assert runtime["model"] == "deepseek-v4-flash-202605"
    assert runtime["available_models"] == ["deepseek-v4-flash-202605", "glm-5.3", "kimi-k3"]
    assert runtime["custom_model_allowed"] is True
    assert "FAKE-PRIVATE" not in json.dumps(runtime)


def test_tencent_config_requires_official_endpoint_and_valid_model(monkeypatch):
    configure_tencent(monkeypatch)
    config = text_config("glm-5.3")
    config.validate()
    assert config.base_url == TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL
    with pytest.raises(TextError) as error:
        TextConfig(
            api_key="FAKE",
            model="glm-5.3",
            base_url="https://api.deepseek.com",
            provider=TEXT_PROVIDER_TENCENT_TOKEN_PLAN,
        ).validate()
    assert error.value.code == "text_configuration_error"
    assert "腾讯云 Token Plan" in error.value.message
    assert "api.deepseek.com" not in error.value.message


def test_tencent_structured_transport_uses_official_base_and_strict_json(monkeypatch):
    captured = {}

    class Message:
        content = "{}"
        tool_calls = None

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=Message())])

    class Client:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("agents.text_assistant.OpenAI", Client)
    backend = TencentTokenPlanTextBackend(TextConfig(
        api_key="FAKE", model="glm-5.3",
        base_url=TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL,
        provider=TEXT_PROVIDER_TENCENT_TOKEN_PLAN))
    assert backend.invoke([{"role": "user", "content": "json"}]) == "{}"
    assert captured["settings"]["base_url"] == TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL
    assert captured["settings"]["max_retries"] == 0 and captured["settings"]["timeout"] == 30
    assert captured["model"] == "glm-5.3"
    assert captured["max_tokens"] == 4096
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "tools" not in captured


def test_tencent_chat_transport_keeps_thinking_budget(monkeypatch):
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content="今天是什么日子？", tool_calls=None))])

    class Client:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("agents.text_assistant.OpenAI", Client)
    backend = TencentTokenPlanTextBackend(TextConfig(
        api_key="FAKE", model="glm-5.3",
        base_url=TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL,
        provider=TEXT_PROVIDER_TENCENT_TOKEN_PLAN))
    answer = backend.answer_brief(
        [TextConsultationInput(message="今天几号？")], date(2026, 8, 30), [])
    assert "今天是什么日子？" in answer
    assert captured["settings"]["timeout"] == 180 and captured["settings"]["max_retries"] == 0
    assert captured["max_tokens"] == 32768
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}
    assert captured["reasoning_effort"] == "high"


@pytest.mark.parametrize("failure,code", [
    (APITimeoutError(request=httpx.Request("POST", TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL)), "text_timeout"),
    (RuntimeError("PRIVATE-PROVIDER-DETAIL"), "text_provider_error"),
])
def test_tencent_errors_are_redacted(monkeypatch, failure, code):
    def fail(**kwargs):
        raise failure

    monkeypatch.setattr("agents.text_assistant.OpenAI", fail)
    backend = TencentTokenPlanTextBackend(TextConfig(
        api_key="FAKE", model="glm-5.3",
        base_url=TENCENT_TOKEN_PLAN_OFFICIAL_BASE_URL,
        provider=TEXT_PROVIDER_TENCENT_TOKEN_PLAN))
    with pytest.raises(TextError) as error:
        backend.invoke([{"role": "user", "content": "json"}])
    assert error.value.code == code and "PRIVATE" not in str(error.value)


def test_http_consent_names_tencent_and_real_send_stays_within_fake(tmp_path, monkeypatch):
    configure_tencent(monkeypatch)
    client, service, workflow, fake = text_client(tmp_path)
    assert client.get("/api/text/runtime").json()["external_provider"] == "腾讯云 Token Plan"
    payload = {
        "request_id": "tencent-http-0001",
        "intent": "consult",
        "model": None,
        "input": {"message": "合成现场问题，仅用于离线协议验证", "project": None, "area": None, "requester_role": None},
        "consultation_id": None,
        "expected_turn": 0,
        "allow_external": False,
    }
    blocked = client.post("/api/text-consultations", json=payload)
    assert blocked.status_code == 403
    assert "腾讯云 Token Plan" in blocked.text
    assert not fake.messages and not workflow.store.snapshot()
    payload["allow_external"] = True
    result = client.post("/api/text-consultations", json=payload).json()
    assert result["mode"] == "real" and result["model"] == "deepseek-v4-flash-202605"
    assert len(fake.messages) == 1
    assert service.proposals.audit_snapshot() == () and workflow.store.snapshot() == ()
    assert "FAKE-PRIVATE" not in json.dumps(result)
