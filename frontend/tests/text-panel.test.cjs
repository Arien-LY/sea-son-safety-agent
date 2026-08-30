// Mount the actual SFC setup with Vue's renderer; only HTTP is replaced.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { parse, compileScript } = require('@vue/compiler-sfc');
const ts = require('typescript');
const vue = require('vue');

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

async function mountPanel() {
  const requests = [], busyEvents = [], analyses = [], proposalEvents = [], proposingEvents = [];
  const api = {
    getTextRuntime: async () => ({ configured: true, mode: 'real', model: 'deepseek-v4-flash' }),
    sendText: (input, signal) => {
      const response = deferred();
      requests.push({ input, signal, ...response });
      return response.promise;
    },
    proposeText: () => {
      const response = deferred();
      requests.push(response);
      return response.promise;
    },
  };
  const filename = path.join(__dirname, '../src/components/TextPanel.vue');
  const { descriptor } = parse(fs.readFileSync(filename, 'utf8'));
  const script = compileScript(descriptor, { id: 'behavior-test' });
  const js = ts.transpileModule(script.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  new Function('require', 'exports', js)(name => name === '../api' ? { api } : require(name), exports);
  const component = exports.default;
  component.render = () => null;
  const renderer = vue.createRenderer({
    createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
    insert() {}, remove() {}, patchProp() {}, setText() {}, setElementText() {},
    parentNode: () => null, nextSibling: () => null,
  });
  const mode = vue.ref('chat');
  let instance;
  const app = renderer.createApp({ render: () => vue.h(component, {
    mode: mode.value, ref: value => { if (value) instance = value.$; },
    onBusy: value => busyEvents.push(value), onAnalysis: value => analyses.push(value),
    onProposal: value => proposalEvents.push(value),
    onProposing: value => proposingEvents.push(value),
  }) });
  app.mount({});
  await vue.nextTick();
  return { state: instance.setupState, app, mode, requests, busyEvents, analyses, proposalEvents, proposingEvents };
}

const result = { consultation_id: 'TXT-test', turn: 1, remaining_turns: 5,
  can_propose: false, reply: { answer: 'hello', analysis: { category: 'unknown' } } };

test('send shows the user message and clears composer before HTTP completes', async () => {
  const panel = await mountPanel();
  panel.state.form.message = '今天几号了';
  const sent = panel.state.send();
  assert.equal(panel.state.form.message, '');
  assert.equal(panel.state.pendingMessage, '今天几号了');
  assert.equal(panel.state.busy, true);
  assert.equal(panel.requests[0].input.intent, 'chat');
  assert.equal(panel.requests[0].input.allow_external, true);
  panel.requests[0].resolve(result);
  await sent;
  assert.equal(panel.state.turns.length, 1);
  assert.equal(panel.state.pendingMessage, '');
  assert.equal(panel.busyEvents.at(-1), false);
  panel.app.unmount();
});

test('unmount aborts waiting and unlocks the parent; a late answer cannot refill it', async () => {
  const panel = await mountPanel();
  panel.state.form.message = 'slow';
  const sent = panel.state.send();
  panel.app.unmount();
  assert.equal(panel.requests[0].signal.aborted, true);
  assert.equal(panel.busyEvents.at(-1), false);
  panel.requests[0].resolve(result);
  await sent;
  assert.equal(panel.analyses.length, 0);
});

test('changing intent clears waiting state and ignores the previous reply', async () => {
  const panel = await mountPanel();
  panel.state.form.message = 'slow';
  const sent = panel.state.send();
  panel.mode.value = 'consult';
  await vue.nextTick();
  assert.equal(panel.requests[0].signal.aborted, true);
  assert.equal(panel.state.pendingMessage, '');
  assert.equal(panel.state.busy, false);
  panel.requests[0].resolve(result);
  await sent;
  assert.equal(panel.state.latest, null);
  assert.equal(panel.state.turns.length, 0);
  panel.app.unmount();
});

test('manual retry restores the message and reuses the same request id', async () => {
  const panel = await mountPanel();
  panel.state.form.message = 'retry me';
  const first = panel.state.send();
  panel.requests[0].reject(new Error('test failure'));
  await first;
  assert.equal(panel.state.form.message, 'retry me');
  assert.equal(panel.state.busy, false);
  const second = panel.state.send();
  assert.equal(panel.requests[1].input.request_id, panel.requests[0].input.request_id);
  panel.requests[1].resolve(result);
  await second;
  assert.equal(panel.state.turns.length, 1);
  panel.app.unmount();
});

test('proposal generation keeps its separate navigation guard until completion', async () => {
  const panel = await mountPanel();
  panel.mode.value = 'consult';
  await vue.nextTick();
  panel.state.latest = { ...result, can_propose: true };
  const proposed = panel.state.propose();
  assert.equal(panel.proposingEvents.at(-1), true);
  panel.requests[0].resolve({ ok: true, data: { proposal: 'fixture' } });
  await proposed;
  assert.equal(panel.proposingEvents.at(-1), false);
  assert.equal(panel.state.proposed, true);
  panel.app.unmount();
});
