<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "../api";
import type { RecordListItem } from "../types";

const route = useRoute();
const drawerOpen = ref(false);
const recent = ref<RecordListItem[]>([]);
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
  drawerOpen.value = false;
  userMenuOpen.value = false;
  void loadRecent();
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

onMounted(() => { restoreUser(); void loadRecent(); });
</script>

<template>
  <div class="app-shell">
    <header class="mobile-bar">
      <button class="icon-button" type="button" aria-label="打开导航" @click="drawerOpen = true"><span></span><span></span><span></span></button>
      <RouterLink class="mobile-brand" to="/consult"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><strong>海之子工作台</strong></RouterLink>
      <span class="mobile-spacer"></span>
    </header>
    <button v-if="drawerOpen" class="drawer-scrim" type="button" aria-label="关闭导航" @click="drawerOpen = false"></button>
    <aside class="sidebar" :class="{ open: drawerOpen }" aria-label="工作台导航">
      <div class="sidebar-head">
        <RouterLink class="brand" to="/consult"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span><strong>海之子</strong><small>安全质量工作台</small></span></RouterLink>
        <button class="close-drawer" type="button" aria-label="关闭导航" @click="drawerOpen = false">×</button>
      </div>
      <nav class="action-nav" aria-label="新建与提交">
        <RouterLink to="/chat" class="nav-action"><span class="nav-icon">＋</span><span><strong>新建聊天</strong><small>一般问答，不生成工单</small></span></RouterLink>
        <RouterLink to="/consult" class="nav-action"><span class="nav-icon">◇</span><span><strong>新建咨询</strong><small>提取信息与风险判断</small></span></RouterLink>
        <RouterLink to="/submit" class="nav-action submit-action"><span class="nav-icon">↗</span><span><strong>提交工单</strong><small>结构化受控提交</small></span></RouterLink>
      </nav>
      <section class="sidebar-history" aria-labelledby="recent-title">
        <div class="sidebar-section-title"><span id="recent-title">最近工单</span><button type="button" :disabled="historyBusy" aria-label="刷新最近工单" @click="loadRecent">↻</button></div>
        <p v-if="historyBusy && !recent.length" class="sidebar-muted">正在同步…</p>
        <p v-else-if="!recent.length" class="sidebar-muted">暂无已保存工单</p>
        <RouterLink v-for="item in recent" :key="item.record_id" :to="`/records/${item.record_id}`" class="history-link"><span>{{ item.title }}</span><small>{{ item.record_id }} · {{ item.status }}</small></RouterLink>
        <RouterLink to="/records" class="all-history">查看全部历史 <span>→</span></RouterLink>
      </section>
      <div class="sidebar-account">
        <button v-if="!currentUser" type="button" class="login-entry" @click="loginOpen = true">
          <span class="user-avatar-shell">用</span><span><strong>登录</strong><small>使用本地演示身份</small></span><b>→</b>
        </button>
        <div v-else class="signed-in-account">
          <button type="button" class="login-entry" :aria-expanded="userMenuOpen" @click="userMenuOpen = !userMenuOpen">
            <span class="user-avatar-shell signed-in">{{ userInitial }}</span><span><strong>{{ currentUser.name }}</strong><small>本地演示身份</small></span><b>⌄</b>
          </button>
          <div v-if="userMenuOpen" class="account-menu"><p>仅保存在本机浏览器，不代表生产账号或工单权限。</p><button type="button" @click="logout">退出登录</button></div>
        </div>
      </div>
    </aside>
    <main class="workspace"><slot /></main>

    <div v-if="loginOpen" class="dialog-backdrop" @click.self="loginOpen = false">
      <form class="login-dialog" role="dialog" aria-modal="true" aria-labelledby="login-title" @submit.prevent="login">
        <span class="dialog-mark" aria-hidden="true">用</span>
        <p class="workspace-kicker">本地工作台</p>
        <h2 id="login-title">登录演示身份</h2>
        <p>该身份仅用于显示头像与称呼，不代表真实账号、项目权限或审批资质。</p>
        <label>显示名称<input v-model="loginName" maxlength="30" autocomplete="name" autofocus placeholder="请输入姓名或昵称" /></label>
        <div class="dialog-actions"><button type="button" class="secondary-button" @click="loginOpen = false">取消</button><button type="submit" class="primary-button" :disabled="!loginName.trim()">登录</button></div>
      </form>
    </div>
  </div>
</template>
