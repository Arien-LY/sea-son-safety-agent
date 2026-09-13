const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { parse, compileScript } = require('@vue/compiler-sfc');
const ts = require('typescript');
const vue = require('vue');

test('AI handoff can generate a proposal after Vue wraps analysis reactively', async () => {
  const route = vue.reactive({ name: 'chat', fullPath: '/chat', query: {}, params: {} });
  const previews = [];
  const api = {
    getRuntime: async () => ({ agent_mode: 'mock' }),
    previewIssueProposal: async (_id, analysis) => {
      previews.push(analysis);
      return { ok: true, data: { proposal: { analysis, review_fields: {} }, proposal_token: 'fixture' } };
    },
  };
  const filename = path.join(__dirname, '../src/views/HomeView.vue');
  const { descriptor } = parse(fs.readFileSync(filename, 'utf8'));
  const script = compileScript(descriptor, { id: 'handoff-test' });
  const js = ts.transpileModule(script.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  new Function('require', 'exports', js)(name => {
    if (name === '../api') return { api };
    if (name === 'vue-router') return {
      useRoute: () => route, useRouter: () => ({ push: async value => {
        route.name = value.name; route.query = value.query; route.fullPath = '/submit?source=ai';
        await vue.nextTick();
      } }), onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    };
    if (name.endsWith('.vue') || name === '../customerLabels') return {};
    return require(name);
  }, exports);
  const component = exports.default;
  component.render = () => null;
  const renderer = vue.createRenderer({ createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
    insert() {}, remove() {}, patchProp() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null });
  let instance;
  const app = renderer.createApp({ render: () => vue.h(component, { ref: value => { if (value) instance = value.$; } }) });
  app.mount({});
  try {
    const analysis = { category: 'logistics', risk_level: 'medium', issue_type: '空调报修', summary: '合成报修', observed_facts: ['合成事实'] };
    await instance.setupState.openTicketFromAnalysis(analysis);
    await instance.setupState.createPreview();
    assert.equal(previews.length, 1, instance.setupState.actionError);
    assert.deepEqual(previews[0], analysis);
    previews[0].observed_facts.push('independent copy');
    assert.equal(instance.setupState.transferredAnalysis.observed_facts.length, 1);
    assert.equal(instance.setupState.record, null);
    assert.equal(instance.setupState.confirmed, null);
  } finally { app.unmount(); }
});
