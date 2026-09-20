import pytest

from agents.text_assistant import TextAssistant, TextError
from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from backend.app.text_models import TextRequest
from test_product_text import FakeTextBackend, decision_payload


def service(path, backend=None):
    return TextConsultationService(Phase2ProposalService(integrity_key=b'p' * 32), store_path=path,
        assistant_factory=lambda *_: TextAssistant(backend or FakeTextBackend()))


def request(previous=None, n=1):
    return TextRequest(request_id=f'persist-{n:04}', intent='auto', input={'message': f'第{n}轮'},
                       consultation_id=previous.consultation_id if previous else None,
                       expected_turn=previous.turn if previous else 0)


def test_restart_restores_pairs_risk_and_idempotent_result(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_MODE', 'mock')
    path = tmp_path / 'chat.sqlite3'
    first = service(path, FakeTextBackend([decision_payload('safety', 'high')]))
    result = first.send(request())
    restarted = service(path)
    assert restarted.send(request()).model_dump() == result.model_dump()
    assert restarted.list_sessions()[0]['turns'] == 1
    assert restarted.get_session(result.consultation_id)['turns'][0]['message'] == '第1轮'
    following = restarted.send(request(result, 2))
    assert following.risk_retained and following.reply.analysis.risk_level == 'high'
    assert len(service(path).get_session(result.consultation_id)['turns']) == 2


def test_failed_write_and_failed_model_do_not_append(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_MODE', 'mock')
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    result = app.send(request())
    def fail(*_): raise TextError('chat_store_error', 'disk full')
    monkeypatch.setattr(app.store, 'save', fail)
    with pytest.raises(TextError): app.send(request(result, 2))
    assert len(app.get_session(result.consultation_id)['turns']) == 1
    assert len(service(path).get_session(result.consultation_id)['turns']) == 1


def test_stale_tab_and_changed_idempotency_fail_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_MODE', 'mock')
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    first = app.send(request())
    app.send(request(first, 2))
    app = service(path)
    with pytest.raises(TextError, match='已更新'): app.send(request(first, 3))
    changed = request().model_copy(update={'input': request(first, 2).input})
    with pytest.raises(TextError, match='不同内容'): app.send(changed)
    other = app.send(request(n=4))
    assert other.consultation_id != first.consultation_id
    assert len(app.list_sessions()) == 2


def test_corrupt_store_allows_service_construction_but_blocks_chat_writes(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    path.write_bytes(b'corrupt fixture')
    app = service(path)
    for action in [app.list_sessions, lambda: app.get_session('missing'), lambda: app.send(request())]:
        with pytest.raises(TextError, match='原数据未覆盖'):
            action()
    assert path.read_bytes() == b'corrupt fixture'
