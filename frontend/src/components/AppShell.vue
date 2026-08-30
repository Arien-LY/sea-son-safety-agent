<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "../api";
import type { RecordListItem } from "../types";

const route = useRoute();
const drawerOpen = ref(false);
const recent = ref<RecordListItem[]>([]);
const historyBusy = ref(false);

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
  void loadRecent();
});
onMounted(loadRecent);
</script>

<template>
  <div class="app-shell">
    <header class="mobile-bar">
      <button class="icon-button" type="button" aria-label="打开导航" @click="drawerOpen = true"><span></span><span></span><span></span></button>
      <RouterLink class="mobile-brand" to="/consult"><span class="brand-mark">安</span><strong>海之子工作台</strong></RouterLink>
      <span class="mobile-spacer"></span>
    </header>
    <button v-if="drawerOpen" class="drawer-scrim" type="button" aria-label="关闭导航" @click="drawerOpen = false"></button>
    <aside class="sidebar" :class="{ open: drawerOpen }" aria-label="工作台导航">
      <div class="sidebar-head">
        <RouterLink class="brand" to="/consult"><span class="brand-mark">安</span><span><strong>海之子</strong><small>安全质量工作台</small></span></RouterLink>
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
      <div class="sidebar-foot"><span class="privacy-dot"></span><p><strong>本地演示环境</strong><small>人工确认后才会写入正式记录</small></p></div>
    </aside>
    <main class="workspace"><slot /></main>
  </div>
</template>
