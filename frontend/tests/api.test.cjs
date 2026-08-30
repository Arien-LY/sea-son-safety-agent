const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function apiHarness(fetch) {
  // Vite replaces import.meta.env during the build; set only this build-time value.
  const source = fs.readFileSync(path.join(__dirname, '../src/api.ts'), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', '""');
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  let deadline, timeoutMs, cleared = false;
  const timers = {
    setTimeout: (callback, delay) => { deadline = callback; timeoutMs = delay; return 1; },
    clearTimeout: () => { cleared = true; },
  };
  new Function('exports', 'window', 'fetch', js)(exports, timers, fetch);
  return { api: exports.api, expire: () => deadline(), cleared: () => cleared, timeout: () => timeoutMs };
}

test('request timeout covers the response body, not only response headers', async () => {
  let finishBody;
  const body = new Promise(resolve => { finishBody = resolve; });
  const harness = apiHarness(async () => ({ ok: true, json: () => body }));
  const response = harness.api.sendText({});
  await Promise.resolve();
  assert.equal(harness.cleared(), false);
  finishBody({ ok: true });
  assert.deepEqual(await response, { ok: true });
  assert.equal(harness.cleared(), true);
});

test('caller cancellation propagates and is not mislabeled a timeout', async () => {
  const harness = apiHarness((_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new DOMException('abort', 'AbortError')));
  }));
  const caller = new AbortController();
  const response = harness.api.sendText({}, caller.signal);
  caller.abort();
  await assert.rejects(response, /请求已取消/);
  assert.equal(harness.cleared(), true);
});

const progress = { type: 'progress', seq: 1, elapsed_ms: 0, stage: 'model_running', tool: null };
function eventResponse(lines, size = 1000) {
  const bytes = new TextEncoder().encode(lines.map(line => typeof line === 'string' ? line : JSON.stringify(line)).join('\n') + '\n');
  return new Response(new ReadableStream({ start(controller) {
    for (let offset = 0; offset < bytes.length; offset += size) controller.enqueue(bytes.slice(offset, offset + size));
    controller.close();
  } }), { headers: { 'Content-Type': 'application/x-ndjson' } });
}

test('stream decodes split UTF-8 frames and receives progress before final result', async () => {
  const seen = [];
  const harness = apiHarness(async url => {
    assert.equal(url, '/api/text-consultations/stream');
    return eventResponse([progress, { type: 'result', data: { answer: '你好，老大' } }], 1);
  });
  const result = await harness.api.sendText({}, undefined, p => seen.push(p));
  assert.deepEqual(seen, [progress]);
  assert.deepEqual(result, { answer: '你好，老大' });
  assert.equal(harness.cleared(), true);
});

for (const [name, frames] of [
  ['truncated', [progress]],
  ['malformed', ['{bad']],
  ['forged tool', [{ ...progress, tool: 'run_shell' }]],
  ['wrong sequence', [{ ...progress, seq: 8 }]],
  ['negative time', [{ ...progress, elapsed_ms: -1 }]],
  ['unknown stage', [{ ...progress, stage: 'thinking_secret' }]],
]) test(`stream fails closed on ${name} without retry`, async () => {
  let calls = 0;
  const harness = apiHarness(async () => { calls++; return eventResponse(frames); });
  await assert.rejects(harness.api.sendText({}, undefined, () => {}), /连接中断或格式无效/);
  assert.equal(calls, 1);
  assert.equal(harness.cleared(), true);
});

test('safe error event reaches the UI and a proposal also has a bounded stream', async () => {
  const harness = apiHarness(async url => {
    assert.equal(url, '/api/text-consultations/TXT-test/proposal/stream');
    return eventResponse([{ type: 'error', error_code: 'text_busy', message: '服务繁忙' }]);
  });
  await assert.rejects(harness.api.proposeText('TXT-test', 1, () => {}), /服务繁忙（text_busy）/);
  assert.equal(harness.cleared(), true);
});

test('deadline aborts stalled stream body and cleans up without retry', async () => {
  let calls = 0;
  const harness = apiHarness(async (_url, init) => {
    calls++;
    return new Response(new ReadableStream({ start(controller) {
      init.signal.addEventListener('abort', () => controller.error(new DOMException('abort', 'AbortError')));
    } }), { headers: { 'Content-Type': 'application/x-ndjson' } });
  });
  const request = harness.api.sendText({}, undefined, () => {});
  await Promise.resolve();
  harness.expire();
  await assert.rejects(request, /35 秒/);
  assert.equal(calls, 1);
  assert.equal(harness.cleared(), true);
});

test('successful stream drains to EOF instead of aborting a completed network request', async () => {
  let cancelled = false;
  const encoder = new TextEncoder();
  const harness = apiHarness(async () => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(JSON.stringify({ type: 'result', data: { ok: true } }) + '\n'));
    },
    pull(controller) { controller.close(); },
    cancel() { cancelled = true; },
  }), { headers: { 'Content-Type': 'application/x-ndjson' } }));
  assert.deepEqual(await harness.api.sendText({}, undefined, () => {}), { ok: true });
  assert.equal(cancelled, false);
});

test('chat has a 190 second body deadline while consult retains 35 seconds', async () => {
  for (const [intent, duration] of [['chat', 190000], ['consult', 35000]]) {
    const harness = apiHarness(async (_url, init) => new Response(new ReadableStream({ start(controller) {
      init.signal.addEventListener('abort', () => controller.error(new DOMException('abort', 'AbortError')));
    } }), { headers: { 'Content-Type': 'application/x-ndjson' } }));
    const request = harness.api.sendText({ intent }, undefined, () => {});
    await Promise.resolve();
    assert.equal(harness.timeout(), duration);
    harness.expire();
    await assert.rejects(request, new RegExp(`${duration / 1000} 秒`));
    assert.equal(harness.cleared(), true);
  }
});

test('maximum Chinese final answer fits the bounded stream decoder', async () => {
  const answer = '文'.repeat(64000);
  const harness = apiHarness(async () => eventResponse([progress, { type: 'result', data: { answer } }], 1024));
  assert.deepEqual(await harness.api.sendText({ intent: 'chat' }, undefined, () => {}), { answer });
});
