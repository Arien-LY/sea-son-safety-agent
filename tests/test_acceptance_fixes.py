"""Regressions from real API acceptance, exercised with the real adapter and Fake SDK."""
import json

import pytest

from agents.text_assistant import TextError
from backend.app.text_models import TextProposalRequest
from test_chat_regression import transport, request, service
from test_web_tools import native_transport, native_request
from test_product_text import decision_payload, reply_payload


def test_auto_history_encodes_only_answers_without_inventing_business_analysis(transport):
    app = service()
    answer = '草稿："第一行"\n第二行\\结尾'
    transport.payload['answer'] = answer
    first = app.send(request())
    app.send(request(2, first, input={'message': '换话题：生日祝福'}))
    messages = transport.calls[-1]['messages']
    assert json.loads(messages[-2]['content']) == {'answer': answer}
    assert json.loads(messages[-1]['content'])['message'] == '换话题：生日祝福'
    assert len(transport.calls) == 2


@pytest.mark.parametrize('tool,arguments,answer', [
    ('current_time', '{}', '来自本地已核验目录[S1][S2][S3]'),
    ('web_search', '{"query":"规范"}', '已联网查到[S1]'),
    ('search_knowledge', '{"query":"消防通道","jurisdiction":"cn_mainland"}', '实际来源之外[S99]'),
])
def test_unverified_sources_never_stream_or_commit(native_transport, tool, arguments, answer):
    native_transport.tool, native_transport.arguments, native_transport.answer = tool, arguments, answer
    app, deltas = service(), []
    with pytest.raises(TextError) as error:
        app.send(native_request(), on_text=deltas.append)
    assert error.value.code == 'unverified_sources'
    assert deltas == [] and not app.list_sessions()
    assert len(native_transport.calls) == 2  # No repair/retry model call.


@pytest.mark.parametrize('category', ['safety', 'quality', 'management', 'logistics'])
def test_manual_review_draft_keeps_missing_diagnosis_without_saving(transport, category):
    transport.payload = decision_payload(category, 'undetermined', True)
    app = service()
    result = app.send(request(input={'message': '合成地点设备故障，请申请人工到场核验。'}))
    assert result.can_propose
    assert result.reply.analysis.risk_level == 'undetermined'
    assert result.reply.analysis.missing_fields
    assert result.reply.analysis.requires_human_review
    assert app.proposals.audit_snapshot() == ()
    preview = app.propose(result.consultation_id, TextProposalRequest(expected_turn=1, confirmed=True))
    assert preview.ok
    assert preview.data['proposal']['analysis']['missing_fields']


@pytest.mark.parametrize('category,risk,status', [
    ('consultation', 'low', 'no_ticket'), ('unknown', 'undetermined', 'need_more_info'),
    ('logistics', 'low', 'need_more_info'), ('safety', 'medium', 'no_ticket'),
])
def test_only_create_ticket_can_propose(transport, category, risk, status):
    # 只有 create_ticket + 安全/质量/管理/后勤 才能出现“生成工单”。
    transport.payload = decision_payload(category, risk, status=status)
    assert not service().send(request()).can_propose


def test_real_catalog_source_is_accepted_but_not_reused_without_new_retrieval(native_transport):
    native_transport.tool = 'search_knowledge'
    native_transport.arguments = '{"query":"消防通道","jurisdiction":"cn_mainland"}'
    native_transport.answer = '本地目录的消防通道管理释义[S1]，具体适用性待核验。'
    app, deltas = service(), []
    first = app.send(native_request(), on_text=deltas.append)
    assert first.sources[0]['id'] == 'S1'
    assert first.tool_results[0]['ok']
    assert ''.join(deltas) == first.reply.answer
    # The next native SDK reply skips tools and copies a previous citation.
    deltas.clear()
    with pytest.raises(TextError) as error:
        app.send(request(2, first, tools_enabled=True), on_text=deltas.append)
    assert error.value.code == 'unverified_sources'
    assert deltas == [] and app.get_session(first.consultation_id)['turns'][-1]['result']['turn'] == 1
    assert len(native_transport.calls) == 3


def test_tool_response_is_held_until_full_validation_even_without_a_tool_call(transport):
    app, deltas = service(), []
    transport.payload['answer'] = '来自已核验的目录[S1]'
    transport.before_finish = lambda: pytest.fail('Unverified prose escaped') if deltas else None
    with pytest.raises(TextError) as error:
        app.send(request(tools_enabled=True), on_text=deltas.append)
    assert error.value.code == 'unverified_sources'
    assert deltas == [] and app.list_sessions() == []
    assert len(transport.calls) == 1


def test_legacy_consult_missing_information_still_blocks_draft(transport):
    transport.payload = reply_payload('logistics', 'undetermined', True)
    transport.payload['analysis'].update(recommended_route='human_review', requires_human_review=True)
    assert not service().send(request(intent='consult')).can_propose


def test_json_escaped_history_counts_against_actual_context_budget(transport):
    app = service()
    transport.payload['answer'] = '"' * 64000
    first = app.send(request())
    transport.payload['answer'] = '新回答'
    second = app.send(request(2, first))
    assert second.context_trimmed
    assert [m['role'] for m in transport.calls[-1]['messages']] == ['system', 'user']
    assert len(app.get_session(first.consultation_id)['turns']) == 2
