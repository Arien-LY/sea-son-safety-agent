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
  catch (cause) { if (current === generation) error.value = String(cause); }
  finally { if (current === generation) busy.value = false; }
}
watch(() => route.fullPath, load, { immediate: true });
function search() { router.push({ name: "records", query: Object.fromEntries(Object.entries(form).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])) }); }
function move(value: number) { router.push({ name: "records", query: { ...route.query, offset: String(value) } }); }
function clear() { router.push({ name: "records" }); }
</script>

<template>
  <section>
    <p class="eyebrow">本地工单 · 唯一状态来源</p><h1>历史工单</h1>
    <p class="lead">查找已保存的记录，继续整改与复查。未保存的提案和临时咨询不会出现在这里。</p>
    <form class="proposal-workbench" @submit.prevent="search">
      <div class="form-grid">
        <label>搜索工单<input v-model="form.q" maxlength="100" placeholder="编号、标题、项目、区域或描述" /></label>
        <label>类别筛选<select v-model="form.category"><option value="">全部类别</option><option v-for="(label, value) in categories" :key="value" :value="value">{{ label }}</option></select></label>
        <label>状态筛选<select v-model="form.status"><option value="">全部状态</option><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select></label>
        <label>处置筛选<select v-model="form.disposition"><option value="">全部处置</option><option value="active">有效记录</option><option value="cancelled">已取消</option></select></label>
      </div>
      <div class="button-row"><button class="primary-button" :disabled="busy">查询工单</button><button type="button" class="secondary-button" :disabled="busy" @click="clear">清除筛选</button><button type="button" class="secondary-button" :disabled="busy" @click="load">刷新列表</button></div>
    </form>
    <p v-if="busy" role="status">正在读取本地工单…</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <section v-if="page" aria-label="工单查询结果" aria-live="polite">
      <p class="section-note">共 {{ page.total }} 条 · 按最近更新时间排序</p>
      <p v-if="!page.items.length" class="info-callout">没有符合条件的工单。可调整筛选，或先到咨询页确认并保存记录。</p>
      <ul class="record-list"><li v-for="item in page.items" :key="item.record_id">
        <RouterLink :to="`/records/${item.record_id}`" class="record-link">
          <div><span class="eyebrow">{{ categories[item.category] }} · {{ item.record_id }}</span><h2>{{ item.title }}</h2><p>{{ item.project || '项目待补充' }} / {{ item.area || '区域待补充' }}</p></div>
          <div><strong>{{ item.disposition === 'cancelled' ? '已取消' : statusLabels[item.status] }}</strong><p>风险 {{ item.risk_level }} · revision {{ item.revision }}</p><small>{{ new Date(item.updated_at).toLocaleString() }}</small><p class="open-label">查看详情 →</p></div>
        </RouterLink>
      </li></ul>
      <nav class="button-row" aria-label="工单分页"><button class="secondary-button" :disabled="busy || offset === 0" @click="move(Math.max(0, offset - 20))">上一页</button><span>第 {{ Math.floor(offset / 20) + 1 }} 页</span><button class="secondary-button" :disabled="busy || offset + 20 >= page.total" @click="move(offset + 20)">下一页</button></nav>
    </section>
  </section>
</template>

<style scoped>
.record-list { padding: 0; list-style: none; display: grid; gap: 16px; }
.record-link { display: grid; grid-template-columns: 1fr auto; gap: 24px; padding: 24px; background: white; border: 1px solid #dce5ef; border-radius: 16px; overflow-wrap: anywhere; }
.record-link:hover { border-color: #1668e8; }
.record-link:focus-visible { outline: 3px solid #1668e8; }
.record-link h2 { font-size: 22px; margin-bottom: 8px; }
.record-link p, .record-link small { color: #647085; }
.record-link .open-label { color: #1668e8; font-weight: 700; }
.button-row { align-items: center; }
@media (max-width: 600px) { .record-link { grid-template-columns: 1fr; gap: 8px; } }
</style>
