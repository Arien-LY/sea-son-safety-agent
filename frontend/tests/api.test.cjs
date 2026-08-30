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
  let deadline, cleared = false;
  const timers = {
    setTimeout: callback => { deadline = callback; return 1; },
    clearTimeout: () => { cleared = true; },
  };
  new Function('exports', 'window', 'fetch', js)(exports, timers, fetch);
  return { api: exports.api, expire: () => deadline(), cleared: () => cleared };
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
