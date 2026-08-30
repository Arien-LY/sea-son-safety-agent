<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import type { IssueAnalysis, IssueProposalPreviewData, TextTurnRequest, TextTurnResponse, VisionRuntime } from "../types";

const emit = defineEmits<{ proposal: [data: IssueProposalPreviewData]; analysis: [data: IssueAnalysis | null]; busy: [value: boolean] }>();
const runtime = ref<VisionRuntime | null>(null);
const form = reactive({ message: "", project: "", area: "", requester_role: "" });
const consent = ref(false);
const busy = ref(false);
const error = ref("");
const latest = ref<TextTurnResponse | null>(null);
const turns = ref<{ message: string; result: TextTurnResponse }[]>([]);
const proposed = ref(false);
let pending: TextTurnRequest | null = null;
const canSend = computed(() => !busy.value && !proposed.value && runtime.value?.configured && form.message.trim()
  && (latest.value?.remaining_turns ?? 6) > 0 && (runtime.value.mode === "mock" || consent.value));
const dirty = computed(() => Boolean(form.message.trim()));

onMounted(async () => {
  try { runtime.value = await api.getTextRuntime(); }
  catch { error.value = "文字服务未连接，请启动后端并刷新；已有工单不受影响。"; }
});
watch(form, () => { consent.value = false; pending = null; });
watch(busy, value => emit("busy", value), { flush: "sync" });

function reset() {
  if (busy.value) return;
  latest.value = null; turns.value = []; proposed.value = false; error.value = "";
  form.message = ""; pending = null; consent.value = false; emit("analysis", null);
}

async function send() {
  if (!canSend.value) return;
  busy.value = true; error.value = "";
  const input = { message: form.message.trim(), project: form.project.trim() || null,
    area: form.area.trim() || null, requester_role: form.requester_role.trim() || null };
  pending ||= { request_id: crypto.randomUUID(), input, consultation_id: latest.value?.consultation_id || null,
    expected_turn: latest.value?.turn || 0, allow_external: consent.value };
  try {
    const result = await api.sendText(pending);
    latest.value = result;
    turns.value.push({ message: input.message, result });
    form.message = ""; pending = null;
    emit("analysis", result.reply.analysis);
  } catch (cause) { error.value = String(cause); }
  finally { busy.value = false; consent.value = false; }
}

async function propose() {
  if (!latest.value?.can_propose || dirty.value || busy.value || proposed.value) return;
  busy.value = true; error.value = "";
  try {
    const result = await api.proposeText(latest.value.consultation_id, latest.value.turn);
    if (!result.ok) throw new Error(result.summary);
    proposed.value = true; emit("proposal", result.data);
  } catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="proposal-workbench text-panel" aria-labelledby="text-title">
    <div class="section-heading"><div><p class="eyebrow">文字咨询 · 人工把关</p><h2 id="text-title">描述你遇到的问题</h2></div>
      <span class="safe-chip">{{ runtime?.mode === "real" ? "真实模型" : "Mock · 不理解真实文字" }}</span></div>
    <p class="section-note">普通咨询直接回答；需要跟进时由你确认提案。每个问题最多6轮补充，30分钟不活跃或后端重启后会话失效；未保存内容刷新后不保留。</p>
    <p v-if="runtime" class="section-note">文字模型：{{ runtime.model }}。{{ runtime.configured ? "已配置" : "配置不可用，请核对后端.env并重启" }}</p>
    <ol v-if="turns.length" class="conversation" aria-label="当前问题对话记录" aria-live="polite">
      <li v-for="turn in turns" :key="turn.result.turn">
        <p class="user-message"><strong>你 · 第{{ turn.result.turn }}轮</strong><br />{{ turn.message }}</p>
        <div class="assistant-message"><strong>{{ turn.result.mode === 'mock' ? 'Mock提示' : '助手建议（未经现场核验）' }}</strong>
          <p class="preserve-lines">{{ turn.result.reply.answer }}</p>
          <p>类别 {{ turn.result.reply.analysis.category }} · 风险 {{ turn.result.reply.analysis.risk_level }} · {{ turn.result.reply.analysis.requires_human_review ? '必须人工复核' : '仍需结合现场判断' }}</p>
          <p v-for="action in turn.result.reply.analysis.immediate_actions" :key="action" class="error-message">{{ action }}</p>
          <ul v-if="turn.result.reply.follow_up_questions.length"><li v-for="question in turn.result.reply.follow_up_questions" :key="question">{{ question }}</li></ul>
          <details><summary>查看已校验分析</summary><p>{{ turn.result.reply.analysis.summary }}</p>
            <p>已述事实：{{ turn.result.reply.analysis.observed_facts.join('；') || '未确认' }}</p>
            <p>不确定性：{{ turn.result.reply.analysis.uncertainties.join('；') || '仍需现场核验' }}</p>
            <p>缺失信息：{{ turn.result.reply.analysis.missing_fields.join('；') || '无额外追问' }}</p>
          </details>
        </div>
      </li>
    </ol>
    <form @submit.prevent="send">
      <fieldset :disabled="busy || proposed" class="plain-fieldset">
        <div class="form-grid">
          <label>项目标签（可选）<input v-model="form.project" maxlength="100" /></label>
          <label>区域标签（可选）<input v-model="form.area" maxlength="200" /></label>
          <label>咨询者角色（自报，非权限）<input v-model="form.requester_role" maxlength="50" /></label>
          <label class="full-field">{{ latest ? '补充同一问题' : '问题描述' }}<textarea v-model="form.message" maxlength="1000" rows="4" required placeholder="说明发生了什么、在哪里、当前状态，以及人员是否处于危险中。不要填写密钥或未经授权的个人资料。"></textarea></label>
        </div>
        <label v-if="runtime?.mode === 'real'" class="text-consent"><input v-model="consent" type="checkbox" />本次允许将问题、标签及本会话历次用户补充发送至DeepSeek，理解可能产生费用</label>
        <button type="submit" class="primary-button" :disabled="!canSend">{{ busy ? '正在处理…' : latest ? '发送补充并重新分析' : '发送问题' }}</button>
      </fieldset>
    </form>
    <p v-if="error" class="error-message" role="alert">{{ error }}。未自动重试；输入已保留。</p>
    <p v-if="latest?.risk_retained" class="info-callout">此前高风险已保留，不能通过后续文字自行降级或宣告解除。</p>
    <p v-if="latest && !latest.remaining_turns" class="info-callout">本问题已达6轮上限，请由人工核对。</p>
    <div class="button-row">
      <button v-if="latest?.can_propose && !proposed" class="primary-button" :disabled="busy || dirty" @click="propose">基于最新分析生成待确认提案</button>
      <button class="secondary-button" :disabled="busy" @click="reset">开始新问题</button>
    </div>
    <p v-if="dirty && latest?.can_propose && !proposed" class="section-note">还有未发送的补充，请先发送，避免使用旧分析生成提案。</p>
    <p v-if="proposed" class="success-callout">待确认提案已生成，请在下方补齐记录字段并确认；尚未建单。该会话已停止补充。</p>
  </section>
</template>

<style scoped>
.plain-fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
.text-consent { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 18px; line-height: 1.7; }
.text-consent input { width: auto; margin-top: 7px; }
.conversation { list-style: none; padding: 0; display: grid; gap: 18px; }
.user-message, .assistant-message { padding: 18px; border-radius: 14px; line-height: 1.75; overflow-wrap: anywhere; }
.user-message { background: #edf4ff; white-space: pre-wrap; }
.assistant-message { border: 1px solid #dae5ee; background: #fafdfc; }
.preserve-lines { white-space: pre-wrap; }
summary { cursor: pointer; font-weight: 700; }
@media (max-width: 600px) { .section-heading { flex-wrap: wrap; } }
</style>
