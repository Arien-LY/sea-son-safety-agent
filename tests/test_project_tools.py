import json
from datetime import date

import pytest

from agents.tools.web_tools import WebTools
from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from test_web_tools import native_transport, native_request


@pytest.mark.parametrize('expression,result', [('0.1+0.2', '0.3'), ('(12.5 * 8) / 2', '50'),
    ('-3*(2+4)', '-18'), ('25/200*100', '12.5'), ('1/3', '0.333333333333')])
def test_decimal_calculator(expression, result):
    tools = WebTools()
    answer = tools.execute('calculate', json.dumps({'expression': expression}))
    assert answer.ok and answer.data['result'] == result


@pytest.mark.parametrize('expression', ['1/0', '2**1000', '__import__("os")', '1e99',
    '1 2', '2(3)', '(' * 15 + '1' + ')' * 15, '1+' , '9' * 31])
def test_calculator_rejects_code_ambiguous_and_unbounded_input(expression):
    answer = WebTools().execute('calculate', json.dumps({'expression': expression}))
    assert not answer.ok and answer.error_code == 'invalid_calculation'


def test_knowledge_uses_existing_reviewed_catalog_and_actual_sources(monkeypatch):
    monkeypatch.setenv('KNOWLEDGE_ENABLED', 'true')
    tools = WebTools()
    tools.knowledge._clock = lambda: date(2026, 8, 30)
    result = tools.execute('search_knowledge', json.dumps({'query': '临边 警示标志', 'jurisdiction': 'cn_mainland'}))
    assert result.ok and result.data['citations']
    assert tools.sources and all(c['display_source_id'] in [s['id'] for s in tools.sources] for c in result.data['citations'])
    assert '释义' in tools.sources[0]['excerpt']
    unknown = tools.execute('search_knowledge', '{"query":"隐患","jurisdiction":"unknown"}')
    assert not unknown.data['citations']


def test_disabled_knowledge_returns_honest_error(monkeypatch):
    monkeypatch.setenv('KNOWLEDGE_ENABLED', 'false')
    result = WebTools().execute('search_knowledge', '{"query":"隐患","jurisdiction":"cn_mainland"}')
    assert result.error_code == 'knowledge_disabled'


@pytest.mark.parametrize('name,arguments', [('calculate', '{"expression":"0.1+0.2"}'),
    ('search_knowledge', '{"query":"隐患","jurisdiction":"unknown"}')])
def test_native_model_dispatches_project_tool_and_receives_matching_result(native_transport, name, arguments):
    native_transport.tool, native_transport.arguments = name, arguments
    events = []
    result = TextConsultationService(Phase2ProposalService()).send(native_request(), progress=lambda *a: events.append(a))
    returned = native_transport.calls[1]['messages'][-1]
    assert returned['tool_call_id'] == 'call-1'
    assert json.loads(returned['content'])['tool_name'] == name
    assert result.tool_results[0]['tool'] == name
    assert ('tool_completed', name) in events
    specs = {s['function']['name'] for s in native_transport.calls[0]['tools']}
    assert specs == {'calculate', 'search_knowledge', 'web_search', 'read_webpage', 'current_time'}
