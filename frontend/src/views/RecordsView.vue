<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api";
import type { RecordPage } from "../types";

const route = useRoute();
const router = useRouter();
const form = reactive({ q: "", category: "", status: "", disposition: "" });
const page = ref<RecordPage | null>(null);
const error = ref("");
const busy = ref(false);
let generation = 0;
const offset = computed(() => Math.max(0, Number(route.query.offset) || 0));
const statusLabels: Record<string, string> = { draft: "草稿", submitted: "已提交", assigned: "已派工", rectifying: "整改中", pending_review: "待复查", closed: "已关闭" };
const categories: Record<string, string> = { safety: "安全", quality: "质量", management: "管理", logistics: "后勤" };
const riskLabels: Record<string, string> = { undetermined: "待判断", low: "低", medium: "中", high: "高", emergency: "紧急" };

async function load() {
  const current = ++generation;
  busy.value = true; page.value = null; error.value = "";
  const query = new URLSearchParams();
  for (const key of Object.keys(form) as (keyof typeof form)[]) {
    form[key] = typeof route.query[key] === "string" ? route.query[key] as string : "";
    if (form[key]) query.set(key, form[key]);
  }
  query.set("offset", String(offset.value)); query.set("limit", "20");
  try { const result = await api.listRecords(query); if (current === generation) page.value = result; }
  catch (cause) { if (current === generation) error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { if (current === generation) busy.value = false; }
}
watch(() => route.fullPath, load, { immediate: true });
function search() { router.push({ name: "records", query: Object.fromEntries(Object.entries(form).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])) }); }
function move(value: number) { router.push({ name: "records", query: { ...route.query, offset: String(value) } }); }
function clear() { router.push({ name: "records" }); }
</script>

<template>
  <section class="records-workspace">
    <header class="records-header">
      <div><p class="workspace-kicker">唯一状态来源</p><h1>历史工单</h1><p>查找已保存记录，恢复完整轨迹并继续人工整改。临时聊天与未确认提案不会出现在这里。</p></div>
      <RouterLink to="/submit" class="primary-button">＋ 提交工单</RouterLink>
    </header>

    <form class="records-filter" @submit.prevent="search">
      <label class="search-field"><span class="search-icon">⌕</span><input v-model="form.q" maxlength="100" placeholder="搜索编号、标题、项目、区域或描述" aria-label="搜索工单" /></label>
      <select v-model="form.category" aria-label="类别筛选"><option value="">全部类别</option><option v-for="(label, value) in categories" :key="value" :value="value">{{ label }}</option></select>
      <select v-model="form.status" aria-label="状态筛选"><option value="">全部状态</option><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select>
      <select v-model="form.disposition" aria-label="处置筛选"><option value="">全部处置</option><option value="active">有效记录</option><option value="cancelled">已取消</option></select>
      <button class="secondary-button" :disabled="busy">查询</button>
      <button type="button" class="filter-clear" :disabled="busy" @click="clear">清除</button>
    </form>

    <div v-if="busy" class="records-loading" role="status">
      <span></span><div><strong>正在读取历史工单</strong><small>从本地 Store 获取最新快照…</small></div>
    </div>
    <div v-if="error" class="records-error" role="alert"><strong>历史工单暂时无法读取</strong><p>{{ error }}</p><button class="secondary-button" @click="load">重新加载</button></div>

    <section v-if="page" class="records-results" aria-label="工单查询结果" aria-live="polite">
      <div class="results-meta"><span>共 {{ page.total }} 条记录</span><button type="button" :disabled="busy" @click="load">↻ 刷新</button></div>
      <div v-if="!page.items.length" class="empty-records">
        <div>⌕</div><h2>没有符合条件的工单</h2><p>调整筛选条件，或通过“提交工单”创建待确认提案。</p>
        <RouterLink to="/submit" class="primary-button">前往提交</RouterLink>
      </div>
      <ul v-else class="record-list">
        <li v-for="item in page.items" :key="item.record_id">
          <RouterLink :to="`/records/${item.record_id}`" class="record-link">
            <div class="record-main">
              <div class="record-topline"><span class="category-dot" :data-category="item.category"></span><span>{{ categories[item.category] }}问题</span><small>{{ item.record_id }}</small></div>
              <h2>{{ item.title }}</h2>
              <p>{{ item.project || "项目待补充" }} · {{ item.area || "区域待补充" }}</p>
            </div>
            <div class="record-status">
              <span :class="{ cancelled: item.disposition === 'cancelled' }">{{ item.disposition === "cancelled" ? "已取消" : statusLabels[item.status] }}</span>
              <small>风险 {{ riskLabels[item.risk_level] }} · rev.{{ item.revision }}</small>
              <time>{{ new Date(item.updated_at).toLocaleString() }}</time>
            </div>
            <span class="record-arrow">›</span>
          </RouterLink>
        </li>
      </ul>
      <nav v-if="page.items.length" class="pagination" aria-label="工单分页"><button class="secondary-button" :disabled="busy || offset === 0" @click="move(Math.max(0, offset - 20))">← 上一页</button><span>第 {{ Math.floor(offset / 20) + 1 }} 页</span><button class="secondary-button" :disabled="busy || offset + 20 >= page.total" @click="move(offset + 20)">下一页 →</button></nav>
    </section>
  </section>
</template>

<style scoped>
.records-workspace { width: min(980px, 100%); margin: 0 auto; padding-bottom: 40px; }
.records-header { min-height: 128px; display: flex; align-items: center; justify-content: space-between; gap: 24px; border-bottom: 1px solid var(--border); }
.records-header h1 { margin: 4px 0 7px; font-size: 26px; }
.records-header p { max-width: 650px; margin: 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
.records-filter { display: grid; grid-template-columns: minmax(240px, 1fr) repeat(3, 130px) auto auto; gap: 8px; margin: 22px 0; }
.search-field { position: relative; }
.search-field input { height: 40px; padding-left: 34px; }
.search-icon { position: absolute; left: 12px; top: 9px; color: #8a8b86; }
.records-filter select, .records-filter button { height: 40px; }
.filter-clear { border: 0; color: #777872; background: transparent; cursor: pointer; }
.results-meta { display: flex; justify-content: space-between; margin: 0 2px 10px; color: #7b7c77; font-size: 11px; }
.results-meta button { border: 0; color: inherit; background: transparent; cursor: pointer; }
.record-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 7px; }
.record-link { position: relative; display: grid; grid-template-columns: 1fr auto 18px; gap: 22px; align-items: center; min-height: 98px; padding: 17px 18px; border: 1px solid var(--border); border-radius: 12px; background: #fff; transition: border-color .15s, transform .15s; }
.record-link:hover { transform: translateY(-1px); border-color: #bfc0bb; }
.record-topline { display: flex; align-items: center; gap: 7px; color: #5f605c; font-size: 11px; }
.record-topline small { color: #959691; }
.category-dot { width: 7px; height: 7px; border-radius: 50%; background: #5c8d7a; }
.category-dot[data-category="quality"] { background: #557fbe; }.category-dot[data-category="management"] { background: #956fb0; }.category-dot[data-category="logistics"] { background: #aa7b3c; }
.record-main h2 { margin: 7px 0 5px; font-size: 15px; line-height: 1.35; }
.record-main p { margin: 0; color: #7a7b76; font-size: 11px; }
.record-status { min-width: 145px; text-align: right; }
.record-status span, .record-status small, .record-status time { display: block; }
.record-status span { color: #176b52; font-size: 12px; font-weight: 800; }.record-status span.cancelled { color: #9a6100; }
.record-status small, .record-status time { margin-top: 5px; color: #8b8c87; font-size: 10px; }
.record-arrow { color: #a5a6a1; font-size: 22px; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 18px; color: #747570; font-size: 11px; }
.records-loading, .records-error, .empty-records { padding: 50px 20px; text-align: center; border: 1px dashed #d5d6d1; border-radius: 14px; background: #fff; }
.records-loading { display: flex; justify-content: center; align-items: center; gap: 12px; }
.records-loading > span { width: 18px; height: 18px; border: 2px solid #ddd; border-top-color: #176b52; border-radius: 50%; animation: spin .8s linear infinite; }
.records-loading strong, .records-loading small { display: block; text-align: left; }.records-loading small { margin-top: 4px; color: var(--muted); }
.records-error strong { color: #9b2d25; }.records-error p, .empty-records p { color: var(--muted); font-size: 12px; }
.empty-records > div { color: #999a95; font-size: 28px; }.empty-records h2 { margin: 10px 0 5px; font-size: 17px; }
@media (max-width: 980px) { .records-filter { grid-template-columns: 1fr 1fr; }.search-field { grid-column: 1 / -1; } }
@media (max-width: 600px) {
  .records-header { min-height: auto; padding: 20px 2px 16px; align-items: flex-start; flex-direction: column; }
  .records-filter { grid-template-columns: 1fr 1fr; }.records-filter select:nth-of-type(3) { grid-column: 1 / -1; }
  .record-link { grid-template-columns: 1fr 14px; gap: 10px; }.record-status { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px 14px; text-align: left; }.record-status small, .record-status time { margin-top: 0; }.record-arrow { grid-column: 2; grid-row: 1; }
}
</style>
