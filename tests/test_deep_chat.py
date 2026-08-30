"""Expanded chat contract through HTTP and a Fake SDK; zero provider calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.text_assistant import ChatInput, select_chat_context
from test_chat_turn_history import sdk, post
from test_product_text import request_payload, text_client


@pytest.mark.parametrize("stream", [False, True])
def test_long_input_and_final_answer_pass_without_reading_hidden_reasoning(tmp_path, sdk, stream):
    class Message:
        content = "可检验的解释。" * 8000
        tool_calls = None

        @property
        def reasoning_content(self):
            raise AssertionError("Hidden reasoning must not be accessed")

    sdk.outcomes.append(SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=Message())]))
    client, service, workflow, _ = text_client(tmp_path)
    payload = request_payload(intent="chat", input={"message": "问题" * 8000}, allow_external=True)
    result = post(client, payload, stream=stream)
    assert result["reply"]["answer"] == Message.content
    assert len(result["reply"]["answer"]) > 4000
    assert result["remaining_turns"] == 49 and not result["context_trimmed"]
    assert not result["can_propose"] and workflow.store.snapshot() == ()
    assert json.loads(sdk.calls[0]["messages"][-1]["content"])["message"] == "问题" * 8000
    assert "reasoning_content" not in str(result) and len(service._sessions) == 1


@pytest.mark.parametrize("intent,message", [("chat", ""), ("chat", "x" * 16001), ("consult", "x" * 1001)])
def test_input_limits_are_intent_specific_before_model_call(tmp_path, sdk, intent, message):
    client, *_ = text_client(tmp_path)
    response = client.post("/api/text-consultations", json=request_payload(
        intent=intent, input={"message": message}, allow_external=True))
    assert response.status_code == 400
    assert not sdk.calls


@pytest.mark.parametrize("length", [20, 64000])
def test_partial_final_answer_is_preserved_with_explicit_budget_notice(tmp_path, sdk, length):
    sdk.outcomes.append(SimpleNamespace(choices=[SimpleNamespace(
        finish_reason="length", message=SimpleNamespace(content="文" * length, tool_calls=None))]))
    client, *_ = text_client(tmp_path)
    answer = post(client, request_payload(intent="chat", allow_external=True))["reply"]["answer"]
    assert answer.startswith("文" * min(length, 100))
    assert "达到预算上限" in answer and "继续" in answer
    assert len(answer) <= 64000


def test_context_character_budget_keeps_complete_recent_pairs_and_latest_input(tmp_path, sdk):
    client, service, *_ = text_client(tmp_path)
    sdk.outcomes.extend(["甲" * 60000, "乙" * 60000, "回答"])
    first = post(client, request_payload(intent="chat", allow_external=True))
    second = post(client, request_payload(2, first, intent="chat", allow_external=True))
    third = post(client, request_payload(3, second, intent="chat", input={"message": "新的完整问题"}, allow_external=True))
    assert not first["context_trimmed"] and not second["context_trimmed"]
    assert third["context_trimmed"]
    messages = sdk.calls[-1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "乙" * 60000
    assert json.loads(messages[-1]["content"])["message"] == "新的完整问题"
    assert sum(len(m["content"]) for m in messages[1:]) <= 120000
    assert len(service._sessions[third["consultation_id"]].responses) == 3
    inputs = [ChatInput(message="历史"), ChatInput(message="当前" * 8000)]
    selected, answers, trimmed = select_chat_context(inputs, ["答"])
    assert selected[-1].message == "当前" * 8000 and answers == ["答"] and not trimmed


def test_session_capacity_preserves_paid_final_answer_then_refuses_next_call(tmp_path, sdk):
    client, service, *_ = text_client(tmp_path)
    sdk.outcomes.extend(["答" * 64000] * 7)
    result = None
    payload = None
    for n in range(1, 8):
        payload = request_payload(n, result, intent="chat", allow_external=True)
        result = post(client, payload)
    assert len(result["reply"]["answer"]) == 64000
    assert post(client, payload) == result  # replay works even after the capacity threshold
    events = client.post("/api/text-consultations/stream", json=request_payload(
        8, result, intent="chat", allow_external=True)).text
    trace = [json.loads(line) for line in events.splitlines()]
    assert trace[-1]["error_code"] == "chat_capacity_limit"
    assert all(e.get("stage") != "model_running" for e in trace)
    assert len(sdk.calls) == 7 and len(service._sessions[result["consultation_id"]].inputs) == 7


def test_original_v1_contracts_stay_frozen():
    root = Path(__file__).resolve().parents[1] / "contracts"
    request = json.loads((root / "product_text_request.v1.schema.json").read_text(encoding="utf-8"))
    response = json.loads((root / "product_text_response.v1.schema.json").read_text(encoding="utf-8"))
    assert request["$defs"]["TextConsultationInput"]["properties"]["message"]["maxLength"] == 1000
    assert request["properties"]["expected_turn"]["maximum"] == 6
    assert response["$defs"]["TextReply"]["properties"]["answer"]["maxLength"] == 4000
