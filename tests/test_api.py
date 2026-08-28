from fastapi.testclient import TestClient

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

