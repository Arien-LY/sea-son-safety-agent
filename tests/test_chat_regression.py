"""Actual auto service/adapter with an offline SDK, not canned routing assertions."""

import copy
import asyncio
import json
from threading import Event
from types import SimpleNamespace

import pytest

from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from backend.app.text_models import TextRequest
from test_product_text import reply_payload


@pytest.fixture
def transport(monkeypatch):
    for key, value in {"AGENT_MODE": "real", "LLM_MODEL": "deepseek-v4-flash",
                       "LLM_API_KEY": "FAKE-OFFLINE", "LLM_BASE_URL": "https://api.deepseek.com"}.items():
        monkeypatch.setenv(key, value)
    state = SimpleNamespace(calls=[], payload=reply_payload(), parts=None, exhausted=False, closed=False, before_finish=lambda: None)

    class Delta:
        tool_calls = None
        def __init__(self, content): self.content = content
        @property
        def reasoning_content(self): raise AssertionError("Never read hidden reasoning")

    def create(**kwargs):
        state.calls.append(copy.deepcopy(kwargs))
        raw = json.dumps(state.payload, ensure_ascii=False)
        if not kwargs.get("stream"):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=Delta(raw))])
        def chunks():
            try:
                for part in state.parts if state.parts is not None else [raw[i:i+3] for i in range(0, len(raw), 3)]:
                    if isinstance(part, Exception): raise part
                    yield SimpleNamespace(choices=[SimpleNamespace(index=0, finish_reason=None, delta=Delta(part))])
                state.before_finish()
                state.exhausted = True
                yield SimpleNamespace(choices=[SimpleNamespace(index=0, finish_reason="stop", delta=Delta(None))])
            finally:
                state.closed = True
        return chunks()

    class Client:
        def __init__(self, **kwargs): self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        def __enter__(self): return self
        def __exit__(self, *args): pass

    monkeypatch.setattr("agents.text_assistant.OpenAI", Client)
    return state


def request(n=1, previous=None, **overrides):
    return TextRequest.model_validate({"request_id": f"regression-{n:04d}", "intent": "auto",
        "input": {"message": "你好"}, "consultation_id": previous.consultation_id if previous else None,
        "expected_turn": previous.turn if previous else 0, "allow_external": True, **overrides})


def service():
    return TextConsultationService(Phase2ProposalService(integrity_key=b"r" * 32))


def test_auto_has_paired_history_and_independent_latest_message(transport):
    app = service()
    previous = None
    for n, question in enumerate(["请用简单的语言解释什么是人工智能。", "你好", "把上一段改短"], 1):
        transport.payload["answer"] = f"第{n}轮合成回答"
        previous = app.send(request(n, previous, input={"message": question}))
        messages = transport.calls[-1]["messages"]
        assert [m["role"] for m in messages] == ["system"] + ["user", "assistant"] * (n - 1) + ["user"]
        assert json.loads(messages[-1]["content"])["message"] == question
        assert "user_statements" not in messages[-1]["content"]
        assert [json.loads(m["content"])["answer"] for m in messages if m["role"] == "assistant"] == [f"第{i}轮合成回答" for i in range(1, n)]
        assert "不要重新回答历史问题" in messages[0]["content"]


@pytest.mark.parametrize("mode", [None, "fast", "deep"])
def test_thinking_choice_is_explicit_and_fast_by_default(transport, mode):
    service().send(request(**({"thinking_mode": mode} if mode else {})))
    call = transport.calls[-1]
    assert call["extra_body"] == {"thinking": {"type": "enabled" if mode == "deep" else "disabled"}}
    assert call.get("reasoning_effort") == ("high" if mode == "deep" else None)
    assert call["max_tokens"] == 32768


def test_auto_delivers_only_answer_while_provider_is_still_generating(transport):
    transport.payload["answer"] = '你好，\n"老大"！🌊'
    deltas = []
    def receive(text):
        assert not transport.exhausted
        deltas.append(text)
    result = service().send(request(), on_text=receive)
    assert transport.calls[0]["stream"] is True
    assert "".join(deltas) == result.reply.answer
    assert transport.closed


def test_stream_failure_does_not_commit_and_retry_has_no_phantom_history(transport):
    app = service()
    transport.parts = ['{"answer":"你好', RuntimeError("PRIVATE-SENTINEL")]
    with pytest.raises(Exception, match="文字服务暂不可用"):
        app.send(request(), on_text=lambda text: None)
    assert not app._sessions and transport.closed
    transport.parts = None
    first = app.send(request())
    count = len(transport.calls)
    assert app.send(request()) == first and len(transport.calls) == count
    app.send(request(2, first))
    assert [m["role"] for m in transport.calls[-1]["messages"]] == ["system", "user", "assistant", "user"]


def test_ndjson_delivers_first_text_before_provider_tail_is_released(transport):
    from backend.app.text_progress import stream_operation
    release = Event()
    transport.before_finish = lambda: release.wait(3) or pytest.fail("Client did not receive a delta before model completion")
    app = service()
    async def consume():
        events = []
        response = stream_operation(app.send, request(), stream_answer=True)
        try:
            async for line in response.body_iterator:
                event = json.loads(line)
                events.append(event)
                if event["type"] == "content_delta" and not release.is_set():
                    assert not transport.exhausted and not app._sessions
                    release.set()
        finally:
            release.set()
        return events
    events = asyncio.run(consume())
    assert events[-1]["type"] == "result", events[-1]
    assert "".join(e["text"] for e in events if e["type"] == "content_delta") == events[-1]["data"]["reply"]["answer"]
    assert len(transport.calls) == 1 and transport.closed


@pytest.mark.parametrize("suffix", ["", '","answer":"重复"}'])
def test_invalid_or_duplicate_json_never_commits_partial_answer(transport, suffix):
    from agents.text_assistant import TextError
    app = service()
    transport.parts = ['{"answer":"临时文字', suffix]
    with pytest.raises(TextError):
        app.send(request(), on_text=lambda text: None)
    assert not app._sessions and transport.closed


@pytest.mark.parametrize("change", [
    lambda p: p.pop("analysis"),
    lambda p: p.update(analysis=None),
    lambda p: p.update(analysis=[]),
    lambda p: p.update(analysis={}),
    lambda p: p["analysis"].update(category="not-a-category"),
    lambda p: p["analysis"].update(confidence="certain"),
    lambda p: p.update(follow_up_questions="bad-type"),
    lambda p: p.update(analysis_status="validated"),
])
def test_invalid_analysis_keeps_answer_without_ticket_or_extra_call(transport, change):
    app = service()
    transport.payload["answer"] = "完整可用的回答"
    change(transport.payload)
    seen = []
    result = app.send(request(), on_text=seen.append)
    assert result.reply.answer == "完整可用的回答" == "".join(seen)
    assert result.analysis_status == "unavailable" and not result.can_propose
    assert result.reply.analysis.category == "unknown"
    assert result.reply.analysis.risk_level == "undetermined"
    assert len(transport.calls) == 1
    assert app.send(request()) == result and len(transport.calls) == 1
    transport.payload = reply_payload()
    next_result = app.send(request(2, result))
    assert next_result.analysis_status == "validated"
    assert json.loads(transport.calls[-1]["messages"][-2]["content"]) == {"answer": "完整可用的回答"}


@pytest.mark.parametrize("risk", ["low", "high"])
def test_analysis_failure_revokes_old_proposal_eligibility(transport, risk):
    from agents.text_assistant import TextError
    from backend.app.text_models import TextProposalRequest
    app = service()
    transport.payload = reply_payload("safety", risk)
    first = app.send(request())
    assert first.can_propose
    transport.payload = {"answer": "正常回答", "analysis": {}}
    seen = []
    second = app.send(request(2, first), on_text=seen.append)
    assert not second.can_propose and second.analysis_status == "unavailable"
    if risk == "high":
        assert not seen and second.risk_retained
        assert second.reply.analysis.risk_level == "high"
        assert second.reply.analysis.immediate_actions == first.reply.analysis.immediate_actions
    with pytest.raises(TextError) as error:
        app.propose(second.consultation_id, TextProposalRequest(expected_turn=2, confirmed=True))
    assert error.value.code == "text_not_proposable"


@pytest.mark.parametrize("answer", [None, 3, "", "  ", "答" * 64001],
                         ids=["null", "number", "empty", "blank", "over-limit"])
def test_invalid_body_cannot_be_rescued_by_analysis_fallback(transport, answer):
    from agents.text_assistant import TextError
    app = service()
    transport.payload = {"answer": answer, "analysis": {}}
    with pytest.raises(TextError):
        app.send(request())
    assert not app._sessions


def test_retained_high_risk_does_not_stream_overwritten_model_answer(transport):
    app = service()
    transport.payload = reply_payload("safety", "high")
    previous = app.send(request())
    transport.payload = reply_payload()
    transport.payload["answer"] = "不应提前展示的降级回答"
    deltas = []
    result = app.send(request(2, previous), on_text=deltas.append)
    assert not deltas
    assert result.risk_retained and result.reply.analysis.risk_level == "high"
    assert "不应提前展示" not in result.reply.answer


def test_history_capacity_counts_previous_assistant_answers(transport):
    app = service()
    first = None
    for n in range(1, 15):
        first = app.send(request(n, first))
    assert first.context_trimmed
    assert [m["role"] for m in transport.calls[-1]["messages"]] == ["system"] + ["user", "assistant"] * 12 + ["user"]
    app = service()
    transport.payload["answer"] = "答" * 60000
    first = app.send(request())
    second = app.send(request(2, first))
    third = app.send(request(3, second))
    assert third.context_trimmed
    assert len(transport.calls[-1]["messages"]) == 4


def test_bad_thinking_option_rejected_before_provider(transport):
    for value in ("high", "auto", True, None):
        with pytest.raises(ValueError):
            request(thinking_mode=value)
    assert not transport.calls


@pytest.mark.parametrize("width", [1, 2, 7, 1000])
def test_incremental_json_escapes_and_unicode_are_preserved(width):
    from agents.answer_stream import AnswerStream
    text = '你好 🌊\n"引号" \\ / \t\b\r\f'
    raw = json.dumps({"answer": text, "analysis": {"answer": "NEVER-LEAK"}}, ensure_ascii=True)
    seen = []
    parser = AnswerStream(seen.append)
    for offset in range(0, len(raw), width):
        parser.feed(raw[offset:offset + width])
    assert "".join(seen) == text


def test_different_json_field_order_waits_for_full_validated_result(transport):
    payload = transport.payload
    transport.parts = [json.dumps({"analysis": payload["analysis"], "follow_up_questions": [], "answer": "你好"}, ensure_ascii=False)]
    seen = []
    result = service().send(request(), on_text=seen.append)
    assert not seen and result.reply.answer == "你好"


def test_stream_deadline_closes_provider_without_committing(transport, monkeypatch):
    from agents.text_assistant import TextError
    clock = iter([0, 181])
    monkeypatch.setattr("agents.text_assistant.monotonic", lambda: next(clock))
    app = service()
    with pytest.raises(TextError) as error:
        app.send(request(), on_text=lambda text: None)
    assert error.value.code == "text_timeout"
    assert transport.closed and not app._sessions


def test_cancelled_consumer_releases_bounded_queue_and_closes_producer(transport):
    from backend.app.text_progress import stream_operation
    transport.payload["answer"] = "答" * 2000
    app = service()
    async def consume():
        response = stream_operation(app.send, request(), stream_answer=True)
        async for line in response.body_iterator:
            if json.loads(line)["type"] == "content_delta":
                await response.body_iterator.aclose()
                break
    asyncio.run(consume())
    # The worker notices the closed transport on the next queued publication.
    for _ in range(100):
        if transport.closed:
            break
        Event().wait(0.01)
    assert transport.closed and not app._sessions
