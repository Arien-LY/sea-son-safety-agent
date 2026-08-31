<script setup lang="ts">
import { ref, watch } from "vue";
import { api } from "../api";
import { riskNames } from "../customerLabels";
import type { IssueAnalysis, IssueRecord, KnowledgeAnswer, KnowledgeJurisdiction } from "../types";

const props = defineProps<{ analysis: IssueAnalysis; record: IssueRecord | null }>();
const query = ref("临边防护需要哪些依据？");
const jurisdiction = ref<KnowledgeJurisdiction>("unknown");
const answer = ref<KnowledgeAnswer | null>(null);
const error = ref("");
const busy = ref(false);
let requestVersion = 0;

// Clear old citations/conclusions whenever their context changes; ignore late responses.
watch([query, jurisdiction, () => props.analysis, () => props.record], () => {
  requestVersion += 1;
  answer.value = null;
  error.value = "";
  busy.value = false;
}, { deep: true });

async function search() {
  const current = ++requestVersion;
  busy.value = true;
  answer.value = null;
  error.value = "";
  try {
    const result = await api.getKnowledgeAnswer(
      query.value, jurisdiction.value, props.analysis, props.record?.record_id,
    );
    if (current === requestVersion) answer.value = result;
  } catch (cause) {
    if (current === requestVersion) error.value = cause instanceof Error ? cause.message : "检索失败，请稍后重试";
  } finally {
    if (current === requestVersion) busy.value = false;
  }
}
</script>

<template>
  <section class="knowledge-panel" aria-labelledby="knowledge-title">
    <div class="section-heading">
      <div><p class="eyebrow">参考资料</p><h2 id="knowledge-title">建议、依据与人工结论</h2></div>
      <span class="safe-chip">8 条释义摘编 · 检索不额外调用模型</span>
    </div>
    <p class="section-note">
      {{ record ? `读取记录 ${record.record_id} 的分析与复查事件` : "使用当前已校验分析；尚未关联正式记录" }}。
      仅候选资料检索，不做法律适用、处罚或责任认定。
    </p>
    <div class="form-grid">
      <label>项目法规适用地区
        <select v-model="jurisdiction">
          <option value="unknown">尚未确认（不引用）</option>
          <option value="cn_mainland">中国内地建设工程（人工确认）</option>
          <option value="overseas">港澳及其他境外项目（本批不适用）</option>
        </select>
      </label>
      <label class="full-field">依据检索问题
        <textarea v-model.trim="query" maxlength="1000" rows="2"></textarea>
      </label>
    </div>
    <button class="primary-button" :disabled="busy || !query" @click="search">{{ busy ? "正在检索…" : "检索依据（不改变状态）" }}</button>
    <p v-if="error" class="error-message" role="alert">{{ error }}。检索失败不影响上方工作流，请由专业人员核对依据。</p>
    <div v-if="answer" class="knowledge-sections" aria-live="polite">
      <section aria-labelledby="model-advice-title">
        <h3 id="model-advice-title">模型建议（未经人工事实核验）</h3>
        <p class="section-note">{{ answer.suggestion_notice }}</p>
        <p>风险：{{ riskNames[answer.analysis.risk_level] }} · 人工复核：{{ answer.analysis.requires_human_review ? "必须" : "按现场情况" }}</p>
        <p v-for="action in answer.analysis.immediate_actions" :key="action" class="error-message">{{ action }}</p>
        <ul><li v-for="suggestion in answer.model_suggestions" :key="suggestion">{{ suggestion }}</li></ul>
      </section>
      <section aria-labelledby="evidence-title">
        <h3 id="evidence-title">检索依据</h3>
        <p>{{ answer.evidence_notice }}</p>
        <p v-if="answer.knowledge_error_code" class="info-callout">参考资料暂不可用；仍可继续咨询与人工处理。</p>
        <article v-for="citation in answer.retrieved_evidence" :key="citation.entry.entry_id" class="citation-card">
          <h4>{{ citation.entry.title }} · {{ citation.entry.locator }}</h4>
          <p>{{ citation.entry.text }}</p>
          <p><a :href="citation.source.url" target="_blank" rel="noopener noreferrer">官方来源：{{ citation.source.title }}</a></p>
          <p>{{ citation.source.publisher }} · {{ citation.source.version }}</p>
          <p>适用范围：{{ citation.entry.scope }}</p>
          <p>版本更新：{{ citation.source.updated_on }} · 入库核对：{{ citation.entry.reviewed_on }} · 下次复核：{{ citation.entry.review_due_on }}（非法律失效日）</p>
        </article>
      </section>
      <section aria-labelledby="human-conclusion-title">
        <h3 id="human-conclusion-title">人工结论</h3>
        <template v-if="answer.human_conclusion.status === 'reviewed'">
          <p>{{ answer.human_conclusion.note }}</p>
          <small>{{ answer.human_conclusion.record_id }} · {{ answer.human_conclusion.occurred_at }}</small>
          <p class="section-note">来自工单复查记录；本机版尚未核验操作人员身份和资质。</p>
        </template>
        <p v-else>尚无人工复查结论；模型建议和检索命中不能替代专业人员确认。</p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.knowledge-panel { margin-top: 24px; padding: 28px; border: 1px solid #d9e2ed; border-radius: 18px; background: #fff; }
.knowledge-sections { display: grid; gap: 18px; margin-top: 24px; }
.knowledge-sections > section { border-top: 1px solid #d9e2ed; padding-top: 16px; min-width: 0; }
.citation-card { background: #f4f7fb; border-left: 3px solid #2463ad; padding: 16px; margin-top: 12px; border-radius: 8px; }
.citation-card h4 { margin: 0 0 10px; }
.citation-card p, .knowledge-sections small { overflow-wrap: anywhere; line-height: 1.7; }
.citation-card summary { cursor: pointer; }
@media (max-width: 600px) {
  .knowledge-panel { padding: 18px; }
  .knowledge-panel .section-heading { flex-direction: column; align-items: flex-start; gap: 10px; }
}
</style>
