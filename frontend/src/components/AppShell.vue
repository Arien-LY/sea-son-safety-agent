<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import { statusNames } from "../customerLabels";
import type { RecordListItem, ChatSessionItem } from "../types";

const route = useRoute();
const router = useRouter();
const openChatMenu = ref<string | null>(null);
const chatActionBusy = ref(false);
let chatLoadGeneration = 0;
const drawerOpen = ref(false);
const recent = ref<RecordListItem[]>([]);
const chats = ref<ChatSessionItem[]>([]);
const chatError = ref('');
const newChatNumber = ref(0);
async function loadChats() {
  const generation = ++chatLoadGeneration;
  try {
    const result = await api.listChatSessions();
    if (generation !== chatLoadGeneration) return;
    chats.value = result.filter(item => item.intent === 'auto' || item.intent === 'chat'); chatError.value = '';
  } catch { if (generation === chatLoadGeneration) chatError.value = '聊天历史暂时无法读取'; }
}
function toggleChatMenu(id: string) {
  if (!chatActionBusy.value) openChatMenu.value = openChatMenu.value === id ? null : id;
}
async function pinChat(chat: ChatSessionItem) {
  if (chatActionBusy.value) return;
  chatActionBusy.value = true; chatError.value = ''; openChatMenu.value = null;
  ++chatLoadGeneration;
  try { await api.pinChatSession(chat.consultation_id, !chat.pinned); await loadChats(); }
  catch (cause) { chatError.value = cause instanceof Error ? cause.message : '置顶操作失败，请重试'; }
  finally { chatActionBusy.value = false; }
}
async function leaveDeletedChat(id: string) {
  if (route.query.chat !== id) return;
  const failure = await router.replace({ path: '/chat', query: { new: String(Date.now()) } });
  if (failure || route.query.chat === id) throw new Error('当前操作尚未完成，请稍后再删除聊天。');
}
async function deleteChat(chat: ChatSessionItem) {
  if (chatActionBusy.value) return;
  openChatMenu.value = null;
  if (!window.confirm('确定删除这条聊天吗？删除后无法恢复；已创建的工单不受影响。')) return;
  chatActionBusy.value = true; chatError.value = ''; ++chatLoadGeneration;
  try {
    // Leave first so a late answer cannot reopen the conversation being deleted.
    await leaveDeletedChat(chat.consultation_id);
    await api.deleteChatSession(chat.consultation_id);
    ++chatLoadGeneration;
    chats.value = chats.value.filter(item => item.consultation_id !== chat.consultation_id);
    try { window.sessionStorage.removeItem('sea-son-pending:' + chat.consultation_id); } catch { /* Browser storage is optional. */ }
    await leaveDeletedChat(chat.consultation_id);
    await loadChats();
  } catch (cause) { chatError.value = cause instanceof Error ? cause.message : '删除失败，请重试'; }
  finally { chatActionBusy.value = false; }
}
const historyBusy = ref(false);
const loginOpen = ref(false);
const userMenuOpen = ref(false);
const loginName = ref("");
const currentUser = ref<{ name: string } | null>(null);
const userInitial = computed(() => currentUser.value?.name?.trim().slice(0, 1).toUpperCase() || "用");

const DEMO_USER_KEY = "sea-son-demo-user";

async function loadRecent() {
  historyBusy.value = true;
  try {
    const query = new URLSearchParams({ offset: "0", limit: "6" });
    recent.value = (await api.listRecords(query)).items;
  } catch {
    recent.value = [];
  } finally {
    historyBusy.value = false;
  }
}

watch(() => route.fullPath, () => {
  openChatMenu.value = null;
  drawerOpen.value = false;
  userMenuOpen.value = false;
  void loadRecent();
  void loadChats();
});

function restoreUser() {
  try {
    const saved = window.localStorage.getItem(DEMO_USER_KEY);
    const parsed = saved ? JSON.parse(saved) as { name?: unknown } : null;
    if (typeof parsed?.name === "string" && parsed.name.trim() && parsed.name.length <= 30) {
      currentUser.value = { name: parsed.name.trim() };
    }
  } catch { currentUser.value = null; }
}

function login() {
  const name = loginName.value.trim();
  if (!name) return;
  currentUser.value = { name };
  try { window.localStorage.setItem(DEMO_USER_KEY, JSON.stringify(currentUser.value)); } catch { /* UI-only identity still works. */ }
  loginName.value = "";
  loginOpen.value = false;
}

function logout() {
  currentUser.value = null;
  userMenuOpen.value = false;
  try { window.localStorage.removeItem(DEMO_USER_KEY); } catch { /* Ignore unavailable local storage. */ }
}

onMounted(() => { restoreUser(); void loadRecent(); void loadChats(); window.addEventListener('sea-son-chat-saved', loadChats); });
onBeforeUnmount(() => window.removeEventListener('sea-son-chat-saved', loadChats));
</script>

<template>
  <div class="app-shell" @click="openChatMenu = null" @keydown.esc="openChatMenu = null">
    <header class="mobile-bar">
      <button class="icon-button" type="button" aria-label="打开导航" @click="drawerOpen = true"><span></span><span></span><span></span></button>
      <RouterLink class="mobile-brand" to="/chat"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><strong>海之子工作台</strong></RouterLink>
      <span class="mobile-spacer"></span>
    </header>
    <button v-if="drawerOpen" class="drawer-scrim" type="button" aria-label="关闭导航" @click="drawerOpen = false"></button>
    <aside class="sidebar" :class="{ open: drawerOpen }" aria-label="工作台导航">
      <div class="sidebar-head">
        <RouterLink class="brand" to="/chat"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span><strong>海之子</strong><small>安全质量工作台</small></span></RouterLink>
        <button class="close-drawer" type="button" aria-label="关闭导航" @click="drawerOpen = false">×</button>
      </div>
      <nav class="action-nav" aria-label="新建与提交">
        <RouterLink :to="`/chat?new=${newChatNumber}`" class="nav-action" @click="newChatNumber = Date.now()"><span class="nav-icon">＋</span><span><strong>新建聊天</strong><small>问答、咨询与AI工单判断</small></span></RouterLink>
        <RouterLink to="/submit" class="nav-action submit-action"><span class="nav-icon">↗</span><span><strong>提交工单</strong><small>填写并确认问题信息</small></span></RouterLink>
      </nav>
      <section class="sidebar-history chat-history" aria-labelledby="chat-history-title">
        <div class="sidebar-section-title"><span id="chat-history-title">最近聊天</span><button type="button" aria-label="刷新聊天历史" @click="loadChats">↻</button></div>
        <p v-if="chatError" class="sidebar-muted">{{ chatError }}</p>
        <p v-else-if="!chats.length" class="sidebar-muted">发送后自动保存在本机</p>
        <div v-for="chat in chats" :key="chat.consultation_id" class="chat-history-row">
          <RouterLink :to="'/chat?chat=' + chat.consultation_id" class="history-link"><span>{{ chat.title }}</span><small>{{ chat.pinned ? '已置顶 · ' : '' }}{{ chat.turns }} 轮对话</small></RouterLink>
          <button type="button" class="chat-menu-toggle" :disabled="chatActionBusy" :aria-label="'会话菜单：' + chat.title" :aria-expanded="openChatMenu === chat.consultation_id" @click.stop="toggleChatMenu(chat.consultation_id)">⋯</button>
          <div v-if="openChatMenu === chat.consultation_id" class="chat-menu" @click.stop>
            <button type="button" :disabled="chatActionBusy" @click="pinChat(chat)">{{ chat.pinned ? '取消置顶' : '置顶' }}</button>
            <button type="button" :disabled="chatActionBusy" class="chat-delete" @click="deleteChat(chat)">删除</button>
          </div>
        </div>
      </section>
      <section class="sidebar-history" aria-labelledby="recent-title">
        <div class="sidebar-section-title"><span id="recent-title">最近工单</span><button type="button" :disabled="historyBusy" aria-label="刷新最近工单" @click="loadRecent">↻</button></div>
        <p v-if="historyBusy && !recent.length" class="sidebar-muted">正在同步…</p>
        <p v-else-if="!recent.length" class="sidebar-muted">暂无已保存工单</p>
        <RouterLink v-for="item in recent" :key="item.record_id" :to="`/records/${item.record_id}`" class="history-link"><span>{{ item.title }}</span><small>{{ item.record_id }} · {{ statusNames[item.status] }}</small></RouterLink>
        <RouterLink to="/records" class="all-history">查看全部历史 <span>→</span></RouterLink>
      </section>
      <div class="sidebar-account">
        <button v-if="!currentUser" type="button" class="login-entry" @click="loginOpen = true">
          <span class="user-avatar-shell">用</span><span><strong>设置称呼</strong><small>仅本机使用</small></span><b>→</b>
        </button>
        <div v-else class="signed-in-account">
          <button type="button" class="login-entry" :aria-expanded="userMenuOpen" @click="userMenuOpen = !userMenuOpen">
            <span class="user-avatar-shell signed-in">{{ userInitial }}</span><span><strong>{{ currentUser.name }}</strong><small>本机使用者</small></span><b>⌄</b>
          </button>
          <div v-if="userMenuOpen" class="account-menu"><p>称呼仅保存在此浏览器，不用于身份认证或审批授权。</p><button type="button" @click="logout">清除称呼</button></div>
        </div>
      </div>
    </aside>
    <main class="workspace"><slot /></main>

    <div v-if="loginOpen" class="dialog-backdrop" @click.self="loginOpen = false">
      <form class="login-dialog" role="dialog" aria-modal="true" aria-labelledby="login-title" @submit.prevent="login">
        <span class="dialog-mark" aria-hidden="true">用</span>
        <p class="workspace-kicker">本地工作台</p>
        <h2 id="login-title">设置你的称呼</h2>
        <p>称呼仅用于页面展示，不代表真实账号、项目权限或审批资质。</p>
        <label>显示名称<input v-model="loginName" maxlength="30" autocomplete="name" autofocus placeholder="请输入姓名或昵称" /></label>
        <div class="dialog-actions"><button type="button" class="secondary-button" @click="loginOpen = false">取消</button><button type="submit" class="primary-button" :disabled="!loginName.trim()">保存称呼</button></div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.chat-history-row { position: relative; display: flex; align-items: center; flex-wrap: wrap; }
.chat-history-row .history-link { flex: 1; min-width: 0; }
.chat-menu-toggle { width: 30px; height: 30px; border: 0; border-radius: 6px; background: transparent; font-size: 22px; cursor: pointer; }
.chat-menu-toggle:hover { background: #e7e7e3; }
.chat-menu { width: 100%; margin: 0 0 6px; padding: 4px; border: 1px solid #deded9; border-radius: 8px; background: #fff; }
.chat-menu button { display: block; width: 100%; padding: 7px 10px; text-align: left; border: 0; border-radius: 5px; background: transparent; cursor: pointer; }
.chat-menu button:hover { background: #f0f0ed; }
.chat-menu .chat-delete { color: #b42318; }
</style>
