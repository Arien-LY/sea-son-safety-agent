import copy
import json
from types import SimpleNamespace as NS

import pytest

from agents.tools.web_tools import WebTools, public_url, fetch_public, PageText
from backend.app.text_consultations import TextConsultationService, text_runtime
from backend.app.proposals import Phase2ProposalService
from backend.app.text_models import TextRequest
from test_product_text import decision_payload


@pytest.mark.parametrize('url', ['http://example.com', 'https://127.0.0.1', 'https://10.1.2.3',
    'https://169.254.169.254/latest', 'file:///etc/passwd', 'https://localhost', 'https://example.com:444',
    'https://x:password@example.com', 'https://example.com/\r\nx', 'https://[::1]', 'https://example.com\\@localhost'])
def test_rejects_nonpublic_or_ambiguous_urls(url):
    with pytest.raises(ValueError): public_url(url)


def test_dns_mixed_public_private_never_opens_connection(monkeypatch):
    monkeypatch.setattr('agents.tools.web_tools.socket.getaddrinfo', lambda *a, **k: [
        (2, 1, 6, '', ('93.184.216.34', 443)), (2, 1, 6, '', ('127.0.0.1', 443))])
    def forbidden(*a, **k): raise AssertionError('No socket for blocked DNS')
    monkeypatch.setattr('agents.tools.web_tools.socket.socket', forbidden)
    with pytest.raises(ValueError): fetch_public('https://example.com')


def test_no_search_key_does_not_make_network_call(monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    def forbidden(*a, **k): raise AssertionError('No credential')
    events = []
    tools = WebTools(fetch=forbidden, progress=lambda *args: events.append(args))
    result = tools.execute('web_search', '{"query":"建筑"}')
    assert result.error_code == 'search_not_configured' and not tools.sources
    assert events == [('tool_running', 'web_search'), ('tool_completed', 'web_search')]
    assert tools.execute('current_time', '{}').ok
    assert tools.execute('current_time', '{"command":"shell"}').error_code == 'invalid_arguments'
    assert tools.execute('run_shell', '{}').error_code == 'tool_not_found'


def test_search_sources_and_plain_web_extract_are_real_and_bounded(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'FAKE-SEARCH-KEY')
    requests = []
    def fetch(url, **kwargs):
        requests.append((url, kwargs))
        if kwargs:
            return json.dumps({'results': [{'url': 'https://example.com/guide', 'title': 'Example', 'content': 'Verified fixture excerpt'},
                                           {'url': 'http://127.0.0.1', 'title': 'bad', 'content': 'bad'}]}).encode(), 'application/json'
        return b'<html><script>steal()</script><p>source text</p></html>', 'text/html'
    tools = WebTools(fetch=fetch)
    result = tools.execute('web_search', '{"query":"public guidance"}')
    assert result.ok and len(tools.sources) == 1
    assert tools.sources[0]['id'] == 'S1'
    assert json.loads(requests[0][1]['body'])['search_depth'] == 'basic'
    assert tools.execute('read_webpage', '{"url":"https://example.com/guide"}').data['untrusted_text'] == 'source text'
    assert 'FAKE-SEARCH-KEY' not in str(tools.results)


def test_ambiguous_arguments_and_malformed_search_fail_closed(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'FAKE-SEARCH-KEY')
    calls = []
    def fetch(*args, **kwargs):
        calls.append(args)
        return b'[]', 'application/json'
    tools = WebTools(fetch=fetch)
    assert tools.execute('web_search', '{"query":"first","query":"second"}').error_code == 'invalid_arguments'
    assert calls == []
    assert tools.execute('web_search', '{"query":"public"}').error_code == 'web_unavailable'
    assert not tools.sources


@pytest.fixture
def native_transport(monkeypatch):
    for key, value in {'AGENT_MODE': 'real', 'LLM_PROVIDER': 'deepseek', 'LLM_MODEL': 'deepseek-v4-flash',
                        'LLM_API_KEY': 'FAKE-OFFLINE', 'LLM_BASE_URL': 'https://api.deepseek.com'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    state = NS(calls=[], tool='current_time', arguments='{}', always=False, fail=False, closed=0, answer='今天的日期见时间工具。', deep=False)
    def create(**kwargs):
        state.calls.append(copy.deepcopy(kwargs))
        def stream():
            try:
                if len(state.calls) == 1 or state.always:
                    yield NS(choices=[NS(index=0, finish_reason=None, delta=NS(content=None, reasoning_content='opaque-provider-state' if state.deep else None,
                        tool_calls=[NS(index=0, id='call-' + str(len(state.calls)), function=NS(name=state.tool, arguments=state.arguments))]))])
                    yield NS(choices=[NS(index=0, finish_reason='tool_calls', delta=NS(content=None, reasoning_content=None, tool_calls=None))])
                else:
                    raw = json.dumps({**decision_payload(), 'answer': state.answer}, ensure_ascii=False)
                    for part in [raw[:22], raw[22:]]:
                        yield NS(choices=[NS(index=0, finish_reason=None, delta=NS(content=part, tool_calls=None, reasoning_content=None))])
                    if state.fail: raise TimeoutError('fixture timeout')
                    yield NS(choices=[NS(index=0, finish_reason='stop', delta=NS(content=None, tool_calls=None, reasoning_content=None))])
            finally: state.closed += 1
        return stream()
    class Client:
        def __init__(self, **kwargs): self.chat = NS(completions=NS(create=create))
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr('agents.text_assistant.OpenAI', Client)
    return state


def native_request(**kwargs):
    return TextRequest(request_id='native-test-1', intent='auto', input={'message': '今天日期是什么'},
                       allow_external=True, tools_enabled=True, **kwargs)


def test_native_call_results_stream_then_persist_without_reasoning(native_transport, tmp_path):
    state = native_transport
    state.deep = True
    service = TextConsultationService(Phase2ProposalService(), store_path=tmp_path / 'chat.sqlite3')
    deltas, events = [], []
    result = service.send(native_request(thinking_mode='deep'), on_text=deltas.append, progress=lambda *args: events.append(args))
    assert ''.join(deltas) == result.reply.answer
    assert len(state.calls) == 2 and state.closed == 2
    assert state.calls[1]['messages'][-1]['role'] == 'tool'
    assert state.calls[1]['messages'][-2]['reasoning_content'] == 'opaque-provider-state'
    assert result.tool_results[0]['tool'] == 'current_time'
    assert ('tool_running', 'current_time') in events
    assert 'opaque-provider-state' not in str(result.model_dump())
    assert b'opaque-provider-state' not in (tmp_path / 'chat.sqlite3').read_bytes()
    assert service.send(native_request(thinking_mode='deep')).model_dump() == result.model_dump()
    assert len(state.calls) == 2


def test_native_search_failure_is_returned_honestly(native_transport):
    native_transport.tool = 'web_search'
    native_transport.arguments = '{"query":"最新规范"}'
    native_transport.answer = '搜索未配置，无法核查最新资料。'
    result = TextConsultationService(Phase2ProposalService()).send(native_request())
    assert not result.sources
    assert result.tool_results[0]['ok'] is False
    returned = json.loads(native_transport.calls[1]['messages'][-1]['content'])
    assert returned['error_code'] == 'search_not_configured'


def test_native_loop_is_bounded_and_failure_commits_no_history(native_transport):
    from agents.text_assistant import TextError
    native_transport.always = True
    service = TextConsultationService(Phase2ProposalService())
    with pytest.raises(TextError): service.send(native_request())
    assert len(native_transport.calls) == 3
    assert 'tools' not in native_transport.calls[-1]
    assert not service.list_sessions()


def test_unknown_provider_does_not_fall_back(monkeypatch):
    monkeypatch.setenv('AGENT_MODE', 'real')
    monkeypatch.setenv('LLM_PROVIDER', 'typo-provider')
    monkeypatch.setenv('LLM_MODEL', 'deepseek-v4-flash')
    monkeypatch.setenv('LLM_API_KEY', 'FAKE')
    monkeypatch.setenv('LLM_BASE_URL', 'https://api.deepseek.com')
    assert not text_runtime()['configured']
