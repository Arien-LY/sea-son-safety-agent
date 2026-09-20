const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { parse, compileScript } = require('@vue/compiler-sfc');
const ts = require('typescript');
const vue = require('vue');
const chat = { consultation_id: 'TXT-fixture', title: '测试聊天', turns: 1, intent: 'auto', pinned: false };
const deferred = () => { let resolve; const promise = new Promise(ok => { resolve = ok; }); return { promise, resolve }; };

async function mount(options = {}) {
  let list = [{ ...chat }];
  const calls = [], removed = [], navigation = [];
  const route = vue.reactive({ path: '/chat', query: options.current ? { chat: chat.consultation_id } : {}, fullPath: '/chat' });
  const api = {
    listRecords: async () => ({ items: [] }),
    listChatSessions: () => options.list ? options.list() : Promise.resolve(list.map(item => ({ ...item }))),
    pinChatSession: async (id, pinned) => { calls.push(['pin', id, pinned]); if (options.fail) throw new Error('保存失败'); list[0].pinned = pinned; },
    deleteChatSession: async id => { calls.push(['delete', id]); if (options.fail) throw new Error('删除失败'); list = []; },
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/components/AppShell.vue'), 'utf8');
  const { descriptor } = parse(source);
  const js = ts.transpileModule(compileScript(descriptor, { id: 'menu-test' }).content,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  new Function('require', 'exports', 'window', js)(name => {
    if (name === '../api') return { api };
    if (name === '../customerLabels') return {};
    if (name === 'vue-router') return { useRoute: () => route, useRouter: () => ({ replace: async value => {
      navigation.push(value);
      if (options.block) return new Error('blocked');
      route.query = value.query; route.fullPath = '/chat?new=' + value.query.new;
    } }) };
    return require(name);
  }, exports, { confirm: () => { calls.push(['confirm']); return options.confirm !== false; }, localStorage: { getItem: () => null },
    sessionStorage: { removeItem: id => removed.push(id) }, addEventListener() {}, removeEventListener() {} });
  const component = exports.default;
  component.render = () => null;
  const renderer = vue.createRenderer({ createComment: () => ({}), createText: () => ({}), createElement: () => ({}),
    insert() {}, remove() {}, patchProp() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null });
  let instance;
  const app = renderer.createApp({ render: () => vue.h(component, { ref: value => { if (value) instance = value.$; } }) });
  app.mount({}); await vue.nextTick(); await vue.nextTick();
  return { app, state: instance.setupState, calls, route, removed, navigation, source };
}

test('menu opens without navigation; pin and unpin reload server state', async () => {
  const p = await mount();
  try {
    p.state.toggleChatMenu(chat.consultation_id); assert.equal(p.state.openChatMenu, chat.consultation_id);
    assert.equal(p.navigation.length, 0); assert.match(p.source, /@click.stop="toggleChatMenu/);
    assert.ok(p.source.indexOf('</RouterLink>\n          <button type="button" class="chat-menu-toggle"') > 0);
    await p.state.pinChat(p.state.chats[0]); assert.equal(p.state.chats[0].pinned, true);
    await p.state.pinChat(p.state.chats[0]); assert.equal(p.state.chats[0].pinned, false);
    assert.equal(p.state.openChatMenu, null); assert.equal(p.navigation.length, 0);
  } finally { p.app.unmount(); }
});
test('cancelled deletion does not mutate or navigate', async () => {
  const p = await mount({ current: true, confirm: false });
  try { await p.state.deleteChat(chat); assert.deepEqual(p.calls, [['confirm']]); assert.equal(p.navigation.length, 0); assert.equal(p.state.chats.length, 1); }
  finally { p.app.unmount(); }
});
test('confirmed current deletion leaves chat, clears draft and removes list item', async () => {
  const p = await mount({ current: true });
  try {
    await p.state.deleteChat(chat);
    assert.deepEqual(p.calls, [['confirm'], ['delete', chat.consultation_id]]);
    assert.equal(p.route.query.chat, undefined); assert.ok(p.route.query.new);
    assert.equal(p.state.chats.length, 0); assert.deepEqual(p.removed, ['sea-son-pending:' + chat.consultation_id]);
  } finally { p.app.unmount(); }
});
test('deleting another chat keeps current route; blocked navigation prevents deletion', async () => {
  for (const options of [{}, { current: true, block: true }]) {
    const p = await mount(options);
    try {
      await p.state.deleteChat(chat);
      if (options.block) { assert.deepEqual(p.calls, [['confirm']]); assert.equal(p.state.chats.length, 1); assert.match(p.state.chatError, /稍后/); }
      else { assert.equal(p.navigation.length, 0); assert.equal(p.state.chats.length, 0); }
    } finally { p.app.unmount(); }
  }
});
test('mutation failure preserves list and reports an error', async () => {
  const p = await mount({ fail: true });
  try {
    await p.state.pinChat(chat); assert.equal(p.state.chats[0].pinned, false);
    await p.state.deleteChat(chat); assert.equal(p.state.chats.length, 1); assert.match(p.state.chatError, /删除失败/);
    assert.equal(p.state.chatActionBusy, false);
  } finally { p.app.unmount(); }
});
test('late history response cannot resurrect deleted row', async () => {
  const stale = deferred(); let count = 0;
  const p = await mount({ list: () => ++count === 1 ? Promise.resolve([chat]) : count === 2 ? stale.promise : Promise.resolve([]) });
  try {
    const old = p.state.loadChats(); await p.state.deleteChat(chat);
    stale.resolve([chat]); await old; assert.equal(p.state.chats.length, 0);
    p.state.chatActionBusy = true; await p.state.pinChat(chat); await p.state.deleteChat(chat);
    assert.equal(p.calls.length, 2);
  } finally { p.app.unmount(); }
});
