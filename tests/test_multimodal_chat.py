import base64
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.text_assistant import TextError
from backend.app.main import create_app
from backend.app.photo_store import PhotoStore
from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from backend.app.text_models import TextRequest
from test_phase5_images import make_image
from test_web_tools import native_transport


@pytest.fixture
def photo_chat(native_transport, monkeypatch, tmp_path):
    monkeypatch.setenv('VISION_MODEL', 'deepseek-v4-flash-vision-exp')
    monkeypatch.setenv('PHOTO_STORE_PATH', str(tmp_path / 'photos'))
    monkeypatch.setenv('CHAT_STORE_PATH', str(tmp_path / 'app-chat.sqlite3'))
    store = PhotoStore(tmp_path / 'photos')
    photo = store.upload(make_image(comment=True, color='red'), 'image/png')
    service = TextConsultationService(Phase2ProposalService(), photo_store=store, store_path=tmp_path / 'chat.sqlite3')
    return service, store, photo, native_transport


def request(photo, **updates):
    values = dict(request_id='multimodal-0001', intent='auto', input={'message': '你能看到这张图吗'},
                  photo_id=photo.photo_id, allow_external=True, allow_image_external=True, tools_enabled=True)
    values.update(updates)
    return TextRequest(**values)


@pytest.mark.parametrize('tool,args', [('calculate', '{"expression":"12*3"}'),
    ('search_knowledge', '{"query":"临边防护"}'), ('web_search', '{"query":"公开建筑规范"}')])
def test_image_survives_native_tool_loop_and_history_restore(photo_chat, tmp_path, tool, args):
    service, store, photo, transport = photo_chat
    transport.tool, transport.arguments = tool, args
    transport.deep = True
    result = service.send(request(photo, thinking_mode='deep'))
    assert result.photo_id == photo.photo_id and result.model == 'deepseek-flash'
    assert len(transport.calls) == 2
    first = transport.calls[0]['messages'][-1]
    assert first['role'] == 'user' and first['content'][0]['type'] == 'text'
    block = first['content'][1]
    assert block['type'] == 'image_url'
    jpeg = base64.b64decode(block['image_url']['url'].split(',', 1)[1])
    assert jpeg == store.read(photo.photo_id)[1] and b'PRIVATE-PNG-TEXT' not in jpeg
    assert first in transport.calls[1]['messages']
    assert transport.calls[1]['messages'][-1]['role'] == 'tool'
    assert result.tool_results[0]['tool'] == tool
    assert service.send(request(photo, thinking_mode='deep')) == result
    assert len(transport.calls) == 2
    restored = TextConsultationService(Phase2ProposalService(), photo_store=store, store_path=tmp_path / 'chat.sqlite3')
    assert restored.get_session(result.consultation_id)['turns'][0]['result']['photo_id'] == photo.photo_id
    assert b'data:image' not in (tmp_path / 'chat.sqlite3').read_bytes()
    assert b'opaque-provider-state' not in (tmp_path / 'chat.sqlite3').read_bytes()
    restored.send(TextRequest(request_id='text-follow-up', intent='auto', input={'message': '继续说明'},
        consultation_id=result.consultation_id, expected_turn=1, allow_external=True, tools_enabled=True))
    assert all(isinstance(m['content'], str) for m in transport.calls[-1]['messages'])
    assert '未重新发送图片' in str(transport.calls[-1]['messages'])


def test_image_only_schema_and_strict_fields(photo_chat):
    service, _, photo, _ = photo_chat
    incoming = request(photo, input={'message': ''})
    assert '图片' in incoming.input.message
    assert service.send(incoming).photo_id == photo.photo_id
    for updates in ({'photo_id': 'https://example.com/a.png'}, {'photo_id': ['PHOTO-' + 'A'*24]},
                    {'allow_image_external': 'true'}, {'intent': 'consult'}):
        with pytest.raises(ValidationError): request(photo, **updates)
    with pytest.raises(ValidationError): TextRequest(request_id='empty-text-1', input={'message': ''})


@pytest.mark.parametrize('change,code', [({'allow_image_external': False}, 'image_consent_required'),
    ({'allow_external': False}, 'text_consent_required'), ({'photo_id': 'PHOTO-'+'A'*24}, 'photo_not_found')])
def test_no_external_call_without_image_consent_or_valid_photo(photo_chat, change, code):
    service, _, photo, transport = photo_chat
    with pytest.raises(TextError) as caught: service.send(request(photo, **change))
    assert caught.value.code == code
    assert not transport.calls and not service.list_sessions()


def test_vision_configuration_and_corruption_fail_closed(photo_chat, monkeypatch):
    service, store, photo, transport = photo_chat
    monkeypatch.setenv('VISION_MODEL', '')
    with pytest.raises(TextError, match='图片外发服务未配置'): service.send(request(photo))
    monkeypatch.setenv('VISION_MODEL', 'deepseek-v4-flash-vision-exp')
    (store.root / (photo.photo_id + '.jpg')).write_bytes(b'corrupt')
    with pytest.raises(TextError, match='完整性'): service.send(request(photo))
    assert not transport.calls


def test_api_reuses_upload_validation_and_passes_id_to_chat(photo_chat):
    _, _, _, transport = photo_chat
    client = TestClient(create_app())
    raw = make_image(comment=True)
    assert client.post('/api/photos', content=raw, headers={'Content-Type':'image/png'}).status_code == 403
    for data, mime, status in [(raw, 'image/gif', 415), (b'x'*(5*1024*1024+1), 'image/png', 413),
                                (b'not an image', 'image/png', 400)]:
        assert client.post('/api/photos', content=data, headers={'Content-Type':mime, 'X-Upload-Authorized':'true'}).status_code == status
    photo = client.post('/api/photos', content=raw, headers={'Content-Type':'image/png','X-Upload-Authorized':'true'}).json()
    body = request(type('Photo', (), photo)()).model_dump(mode='json')
    response = client.post('/api/text-consultations/stream', json=body)
    assert response.status_code == 200 and photo['photo_id'] in response.text
    assert 'image_url' in str(transport.calls[0]['messages'])
    assert 'data:image' not in response.text


def test_legacy_text_digest_is_unchanged(photo_chat):
    service, _, _, transport = photo_chat
    req = TextRequest(request_id='legacy-request', intent='auto', input={'message':'你好'}, allow_external=True, tools_enabled=True)
    old_payload = req.model_dump_json(exclude={'photo_id','allow_image_external'})
    result = service.send(req)
    digest = service._sessions[result.consultation_id].responses[req.request_id][0]
    assert digest == hashlib.sha256(old_payload.encode()).hexdigest()
    assert service.send(req) == result and len(transport.calls) == 2


def test_visual_workflow_analysis_requires_human_review(photo_chat):
    from agents.text_assistant import TextAssistant
    from test_product_text import FakeTextBackend, decision_payload
    service, _, photo, _ = photo_chat
    payload = decision_payload(category='safety', risk='low')
    service.assistant_factory = lambda *_: TextAssistant(FakeTextBackend([payload]))
    result = service.send(request(photo, tools_enabled=False))
    assert result.ticket_decision.status == 'create_ticket'
    assert result.can_propose
    assert result.reply.analysis.requires_human_review
    assert result.reply.analysis.recommended_route == 'human_review'
    assert any('图片' in v for v in result.reply.analysis.uncertainties)
