import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from agents.vision import DeepSeekVisionBackend, VisionConfig, VisionError
from backend.app.photos import runtime_vision_info


def test_multimodal_request_is_native_bounded_and_never_logs_reasoning(monkeypatch):
    captured = {}
    class Message:
        content = "{}"
        @property
        def reasoning_content(self): raise AssertionError("Hidden reasoning must not be accessed")
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=Message())],
                               usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3))
    class Client:
        def __init__(self, **kwargs):
            captured["client"] = {key: value for key, value in kwargs.items() if key != "api_key"}
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr("agents.vision.OpenAI", Client)
    backend = DeepSeekVisionBackend(VisionConfig(api_key="FAKE-KEY-NOT-A-SECRET", max_output_tokens=1024))
    assert backend.complete([{"role": "system", "content": "json"}, {"role": "user", "content": "context"}], b"jpeg") == "{}"
    assert captured["client"]["timeout"] == 30
    assert captured["client"]["max_retries"] == 0
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert captured["max_tokens"] == 1024
    assert "tools" not in captured
    image = captured["messages"][-1]["content"][1]
    assert image["type"] == "image_url" and image["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert backend.usage == {"prompt_tokens": 12, "completion_tokens": 3}


@pytest.mark.parametrize("failure,code", [
    (APITimeoutError(request=httpx.Request("POST", "https://api.deepseek.com")), "vision_timeout"),
    (RuntimeError("PRIVATE-RAW-PROVIDER-ERROR"), "vision_provider_error"),
])
def test_provider_failures_redact_details(monkeypatch, failure, code):
    def fail(**kwargs): raise failure
    monkeypatch.setattr("agents.vision.OpenAI", fail)
    with pytest.raises(VisionError) as error:
        DeepSeekVisionBackend(VisionConfig(api_key="FAKE-KEY")).complete([{"role": "user", "content": "context"}], b"jpeg")
    assert error.value.code == code
    assert "PRIVATE" not in str(error.value)


def test_runtime_reports_real_misconfiguration_without_secret_values(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "real")
    monkeypatch.setenv("LLM_API_KEY", "FAKE-PRIVATE-VALUE")
    monkeypatch.setenv("VISION_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    info = runtime_vision_info()
    assert info["mode"] == "real" and info["configured"] is False
    assert "FAKE-PRIVATE" not in json.dumps(info)
    monkeypatch.setenv("VISION_MODEL", "deepseek-v4-flash-vision-exp")
    assert runtime_vision_info()["configured"] is True
