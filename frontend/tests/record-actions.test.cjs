// HomeView 工单操作：删除确认、删除后返回列表、以及“生成工单→核对草稿”的分步门控。
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { parse, compileScript } = require('@vue/compiler-sfc');
const ts = require('typescript');
const vue = require('vue');

const RECORD_ID = 'ISS-ABCDEF123456';

function fakeRecord() {
  return {
    record_id: RECORD_ID,
    analysis: { category: 'safety', risk_level: 'medium', requires_human_review: true,
      recommended_route: 'human_review', suggested_actions: [], immediate_actions: [] },
    review_fields: { record_title: '合成工单', record_description: '合成描述', project: null, area: null, reporter_note: null },
    status: 'draft', disposition: 'active', revision: 1,
    suggested_responsible_role: 'safety_officer', assigned_to: null, assigned_role: null,
    events: [], created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  };
}

async function mountHome(options = {}) {
  const route = vue.reactive({ name: 'record-detail', fullPath: '/records/' + RECORD_ID, query: {}, params: { recordId: RECORD_ID } });
  const pushes = [], deleted = [], confirmations = [];
  const api = {
    getRuntime: async () => ({ agent_mode: 'mock' }),
    getIssueRecord: async id => ({ ...fakeRecord(), record_id: id }),
    deleteIssueRecord: async id => {
      if (options.deleteFails) throw new Error('删除失败，请重试。');
      deleted.push(id);
      return { deleted: true, record_id: id };
    },
  };
  const filename = path.join(__dirname, '../src/views/HomeView.vue');
  const { descriptor } = parse(fs.readFileSync(filename, 'utf8'));
  const script = compileScript(descriptor, { id: 'record-actions' });
  const js = ts.transpileModule(script.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  const fakeWindow = {
    confirm: message => { confirmations.push(message); return options.confirmResult !== false; },
    dispatchEvent() {}, addEventListener() {}, removeEventListener() {},
  };
  new Function('require', 'exports', 'window', js)(name => {
    if (name === '../api') return { api };
    if (name === 'vue-router') return {
      useRoute: () => route,
      useRouter: () => ({ push: async value => {
        pushes.push(value);
        route.name = value.name; route.fullPath = '/' + String(value.name);
        await vue.nextTick();
      } }),
      onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    };
    if (name.endsWith('.vue') || name === '../customerLabels') return {};
    return require(name);
  }, exports, fakeWindow);
  const component = exports.default;
  component.render = () => null;
  const renderer = vue.createRenderer({ createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
    insert() {}, remove() {}, patchProp() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null });
  let instance;
  const app = renderer.createApp({ render: () => vue.h(component, { ref: value => { if (value) instance = value.$; } }) });
  app.mount({});
  await vue.nextTick(); await vue.nextTick();
  return { state: instance.setupState, app, pushes, deleted, confirmations };
}

test('删除工单必须先二次确认，取消时什么都不做', async () => {
  const home = await mountHome({ confirmResult: false });
  try {
    assert.equal(home.state.record.record_id, RECORD_ID);
    await home.state.deleteRecord();
    assert.equal(home.confirmations.length, 1);
    assert.match(home.confirmations[0], /确定删除此工单吗？删除后本地记录将无法恢复。/);
    assert.deepEqual(home.deleted, []);
    assert.equal(home.state.record.record_id, RECORD_ID);
    assert.equal(home.pushes.length, 0);
  } finally { home.app.unmount(); }
});

test('确认后真正删除工单并返回历史工单列表', async () => {
  const home = await mountHome();
  try {
    await home.state.deleteRecord();
    assert.deepEqual(home.deleted, [RECORD_ID]);
    assert.equal(home.state.record, null);
    assert.equal(home.pushes.at(-1).name, 'records');
  } finally { home.app.unmount(); }
});

test('删除失败要提示用户并保留当前工单', async () => {
  const home = await mountHome({ deleteFails: true });
  try {
    await home.state.deleteRecord();
    assert.match(home.state.actionError, /删除失败/);
    assert.equal(home.state.record.record_id, RECORD_ID);
    assert.equal(home.pushes.length, 0);
  } finally { home.app.unmount(); }
});

test('只有点击生成工单拿到草稿后，才显示核对工单草稿', () => {
  const home = fs.readFileSync(path.join(__dirname, '../src/views/HomeView.vue'), 'utf8');
  const panel = fs.readFileSync(path.join(__dirname, '../src/components/TextPanel.vue'), 'utf8');
  assert.match(panel, /@click="propose">生成工单/);
  assert.ok(!panel.includes('openTicket'));
  assert.match(home, /v-if="isSubmit && !proposal"/);
  assert.match(home, /v-if="!isDetail && proposal && editedFields"/);
  assert.ok(home.includes('核对工单草稿'));
  assert.ok(!home.includes('openTicketFromAnalysis'));
  assert.ok(!home.includes('transferredAnalysis'));
});

test('正式工单页面不展示参考资料或图片证据模块，并提供 Word 与删除入口', () => {
  const home = fs.readFileSync(path.join(__dirname, '../src/views/HomeView.vue'), 'utf8');
  assert.ok(!home.includes('KnowledgePanel'));
  assert.ok(!home.includes('ImagePanel'));
  assert.ok(!home.includes('参考资料'));
  assert.ok(!home.includes('图片证据'));
  assert.match(home, /生成 Word 文件/);
  assert.match(home, /删除工单/);
});
