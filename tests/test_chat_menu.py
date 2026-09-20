import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from agents.text_assistant import TextError
from backend.app.main import create_app
from test_chat_persistence import service, request


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv('AGENT_MODE', 'mock')
    monkeypatch.setenv('PHOTO_STORE_PATH', str(tmp_path / 'photos'))
    monkeypatch.setenv('ISSUE_STORE_PATH', str(tmp_path / 'records.json'))


def ids(app):
    return [item['consultation_id'] for item in app.list_sessions()]


def test_pin_persists_without_changing_recency_and_survives_followup(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    first, second = app.send(request(n=1)), app.send(request(n=2))
    assert ids(app) == [second.consultation_id, first.consultation_id]
    before = json.loads(app.store.load()[first.consultation_id])['updated']
    app.set_pinned(first.consultation_id, True)
    assert json.loads(app.store.load()[first.consultation_id])['updated'] == before
    assert ids(service(path)) == [first.consultation_id, second.consultation_id]
    app.set_pinned(first.consultation_id, False)
    assert ids(service(path)) == [second.consultation_id, first.consultation_id]
    app.set_pinned(first.consultation_id, True)
    app.send(request(first, n=3))
    app.set_pinned(second.consultation_id, True)
    restarted = service(path)
    assert ids(restarted) == [first.consultation_id, second.consultation_id]
    assert all(item['pinned'] for item in restarted.list_sessions())
    assert restarted.get_session(first.consultation_id)['turns'][-1]['message'] == '第3轮'


def test_old_snapshot_defaults_to_unpinned(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    response = app.send(request())
    body = json.loads(app.store.load()[response.consultation_id])
    body.pop('pinned')
    app.store.save(response.consultation_id, json.dumps(body))
    assert service(path).list_sessions()[0]['pinned'] is False


def test_delete_removes_sqlite_and_memory_and_stale_followup_cannot_recreate(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    first, second = app.send(request()), app.send(request(n=2))
    app.delete_session(first.consultation_id)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT count(*) FROM sessions WHERE id=?', (first.consultation_id,)).fetchone()[0] == 0
    for instance in [app, service(path)]:
        assert ids(instance) == [second.consultation_id]
        with pytest.raises(TextError) as caught: instance.get_session(first.consultation_id)
        assert caught.value.status == 404
        with pytest.raises(TextError): instance.send(request(first, n=3))
        assert ids(instance) == [second.consultation_id]


def test_write_failures_keep_memory_and_disk_unchanged(tmp_path, monkeypatch):
    path = tmp_path / 'chat.sqlite3'
    app = service(path)
    first = app.send(request())
    def fail(*a, **k): raise TextError('chat_store_error', 'disk full')
    monkeypatch.setattr(app.store, 'save', fail)
    monkeypatch.setattr(app.store, 'delete', fail)
    with pytest.raises(TextError): app.set_pinned(first.consultation_id, True)
    with pytest.raises(TextError): app.delete_session(first.consultation_id)
    assert app.list_sessions()[0]['pinned'] is False
    assert ids(app) == ids(service(path)) == [first.consultation_id]


def test_running_save_excludes_delete_and_pin(tmp_path):
    app = service(tmp_path / 'chat.sqlite3')
    first = app.send(request())
    entered, release = Event(), Event()
    def running():
        with app._operation(lambda *_: None):
            entered.set()
            release.wait(8)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(running)
        assert entered.wait(2)
        try:
            assert pool.submit(app.list_sessions).result(timeout=1)[0]['consultation_id'] == first.consultation_id
            for action in [lambda: app.delete_session(first.consultation_id), lambda: app.set_pinned(first.consultation_id, True)]:
                with pytest.raises(TextError) as caught: action()
                assert caught.value.code == 'text_busy'
        finally:
            release.set(); future.result()
    assert app.list_sessions()[0]['pinned'] is False


def test_api_confirmation_strict_types_and_missing_sessions(tmp_path):
    app = service(tmp_path / 'chat.sqlite3')
    first = app.send(request())
    client = TestClient(create_app(text_service=app))
    url = '/api/chat-sessions/' + first.consultation_id
    assert client.patch(url, json={'pinned': True}).json()['pinned'] is True
    assert client.get('/api/chat-sessions').json()[0]['pinned'] is True
    for body in [{'pinned': 'true'}, {'pinned': 1}, {'pinned': True, 'other': 1}]:
        assert client.patch(url, json=body).status_code == 400
    for body in [{'confirmed': False}, {'confirmed': 'true'}, {'confirmed': 1}, {}]:
        assert client.request('DELETE', url, json=body).status_code == 400
    assert client.get(url).status_code == 200
    assert client.request('DELETE', url, json={'confirmed': True}).json() == {'deleted': True}
    assert client.get(url).status_code == 404
    assert client.patch(url, json={'pinned': False}).status_code == 404
    assert client.request('DELETE', url, json={'confirmed': True}).status_code == 404
