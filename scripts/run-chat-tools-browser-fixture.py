"""Explicit offline SDK/search fixture exercising production native loop and stores.

Run with WORKBENCH_FIXTURE_DIR and WORKBENCH_FIXTURE_PORT. No real client exists.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import agents.text_assistant as adapter
import backend.app.text_consultations as consultations
from agents.tools.web_tools import WebTools
from backend.app.main import create_app
from backend.app.proposals import Phase2ProposalService
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_store import JsonIssueRecordStore

spec = importlib.util.spec_from_file_location('workbench_fixture', ROOT / 'scripts/run-workbench-browser-fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def fake_fetch(url, **kwargs):
    if kwargs:
        return json.dumps({'results': [{'url': 'https://example.com/fixture', 'title': '隔离合成来源（非工程依据）',
            'content': '此资料仅验证来源展示与工具调用，不代表真实规范或现场结论。'}]}, ensure_ascii=False).encode(), 'application/json'
    return '<html><p>隔离合成网页：现场问题仍须人工核验。</p><script>neverExecute()</script></html>'.encode(), 'text/html'


class FakeSDK:
    def __init__(self, **kwargs):
        self.chat = NS(completions=NS(create=self.create))

    def __enter__(self): return self
    def __exit__(self, *args): pass

    def create(self, **options):
        messages = options['messages']
        question = next(m['content'] for m in reversed(messages) if m['role'] == 'user')
        tool_messages = [m for m in messages if m['role'] == 'tool']
        call = None
        if options.get('tools'):
            if '搜索' in question and not tool_messages:
                call = ('web_search', {'query': '公开合成测试'})
            elif '搜索' in question and len(tool_messages) == 1:
                call = ('read_webpage', {'url': 'https://example.com/fixture'})
            elif '日期' in question and not tool_messages:
                call = ('current_time', {})
        def chunk(content=None, calls=None, finish=None):
            return NS(choices=[NS(index=0, finish_reason=finish, delta=NS(content=content, tool_calls=calls, reasoning_content=None))])
        def stream():
            if call:
                yield chunk(calls=[NS(index=0, id='fixture-' + str(len(tool_messages)),
                    function=NS(name=call[0], arguments=json.dumps(call[1])))])
                yield chunk(finish='tool_calls')
                return
            payload = json.loads(fixture.WorkbenchFakeBackend().invoke([{'role': 'user', 'content': question}]))
            if '搜索' in question:
                payload['answer'] = '已完成隔离搜索与网页读取。合成资料说明，现场问题仍需人工核验。[S1]\n\n此结果仅用于功能验收，不是真实联网检索。'
            elif '简短' in question:
                payload['answer'] = '人工智能帮助计算机学习规律。\n\n这是对上一轮内容的合成改写。'
            raw = json.dumps(payload, ensure_ascii=False)
            for i in range(0, len(raw), 32):
                yield chunk(content=raw[i:i+32])
                time.sleep(.025)  # Explicit offline transport latency only.
                if '模拟中断' in question and i > 50:
                    raise RuntimeError('offline synthetic disconnect')
            yield chunk(finish='stop')
        return stream()


if __name__ == '__main__':
    root = Path(os.environ['WORKBENCH_FIXTURE_DIR']).resolve()
    os.environ.update(AGENT_MODE='real', LLM_PROVIDER='deepseek', LLM_API_KEY='FAKE-OFFLINE', DEEPSEEK_API_KEY='FAKE-OFFLINE',
        LLM_MODEL='deepseek-v4-flash', LLM_BASE_URL='https://api.deepseek.com', TAVILY_API_KEY='FAKE-SEARCH',
        PHOTO_STORE_PATH=str(root / 'photos'))
    adapter.OpenAI = FakeSDK
    consultations.WebTools = lambda **kwargs: WebTools(fetch=fake_fetch, **kwargs)
    proposals = Phase2ProposalService(integrity_key=b'isolated-tools-browser-fixture-32')
    workflow = IssueWorkflowService(JsonIssueRecordStore(root / 'records.json'), confirmation_verifier=proposals.verify_confirmation)
    texts = consultations.TextConsultationService(proposals, store_path=root / 'chat.sqlite3')
    app = create_app(proposal_service=proposals, workflow_service=workflow, text_service=texts)
    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend/dist/assets'))
    @app.get('/{path:path}')
    def page(path: str):
        return FileResponse(ROOT / 'frontend/dist/index.html')
    uvicorn.run(app, host='127.0.0.1', port=int(os.getenv('WORKBENCH_FIXTURE_PORT', '8041')), log_level='warning')
