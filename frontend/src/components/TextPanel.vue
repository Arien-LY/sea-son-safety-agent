<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import type { IssueAnalysis, IssueProposalPreviewData, TextTurnRequest, TextTurnResponse, VisionRuntime } from "../types";

const props = defineProps<{ mode: "chat" | "consult" }>();
const emit = defineEmits<{
  proposal: [data: IssueProposalPreviewData];
  analysis: [data: IssueAnalysis | null];
  busy: [value: boolean];
  attachment: [];
}>();
const runtime = ref<VisionRuntime | null>(null);
const form = reactive({ message: "", project: "", area: "", requester_role: "" });
const consent = ref(false);
const busy = ref(false);
const error = ref("");
const latest = ref<TextTurnResponse | null>(null);
const turns = ref<{ message: string; result: TextTurnResponse }[]>([]);
const proposed = ref(false);
const contextOpen = ref(false);
let pending: TextTurnRequest | null = null;
const canSend = computed(() => !busy.value && !proposed.value && runtime.value?.configured && Boolean(form.message.trim())
  && (latest.value?.remaining_turns ?? 6) > 0 && (runtime.value.mode === "mock" || consent.value));
const dirty = computed(() => Boolean(form.message.trim()));
const canCreateProposal = computed(() => props.mode === "consult" && latest.value?.can_propose && !proposed.value);
const prompt = computed(() => props.mode === "chat"
  ? "你好！想了解哪项现场安全、质量或管理知识？"
  : "描述现场发生了什么，我会先提取信息、追问并判断风险。");

onMounted(async () => {
  try { runtime.value = await api.getTextRuntime(); }
  catch { error.value = "文字服务未连接，请启动后端并刷新；已有工单不受影响。"; }
});
watch(form, () => { consent.value = false; pending = null; });
watch(busy, value => emit("busy", value), { flush: "sync" });
watch(() => props.mode, reset);

function reset() {
  if (busy.value) return;
  latest.value = null; turns.value = []; proposed.value = false; error.value = "";
  form.message = ""; pending = null; consent.value = false; contextOpen.value = false; emit("analysis", null);
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
  } catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { busy.value = false; consent.value = false; }
}

function onComposerKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void send();
  }
}

async function propose() {
  if (!canCreateProposal.value || dirty.value || busy.value || !latest.value) return;
  busy.value = true; error.value = "";
  try {
    const result = await api.proposeText(latest.value.consultation_id, latest.value.turn);
    if (!result.ok) throw new Error(result.summary);
    proposed.value = true; emit("proposal", result.data);
  } catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="conversation-workspace" :aria-labelledby="mode === 'chat' ? 'chat-title' : 'consult-title'">
    <header class="conversation-header">
      <div>
        <p class="workspace-kicker">{{ mode === "chat" ? "普通聊天" : "专业咨询" }}</p>
        <h1 :id="mode === 'chat' ? 'chat-title' : 'consult-title'">{{ mode === "chat" ? "新建聊天" : "新建咨询" }}</h1>
        <p>{{ mode === "chat" ? "用于一般问答，不会在此模式生成或提交工单。" : "先理解事实与风险；满足受控条件后，才会出现工单步骤。" }}</p>
      </div>
      <div class="connection-pill" :class="{ online: runtime?.configured }"><span></span>{{ runtime?.configured ? "服务已连接" : "连接检查中" }}</div>
    </header>

    <div class="message-stage">
      <section v-if="!turns.length" class="empty-conversation" aria-live="polite">
        <div class="assistant-orb" aria-hidden="true"></div>
        <h2>{{ prompt }}</h2>
        <p>{{ mode === "chat" ? "回答仅供参考；涉及现场风险时仍需专业人员核验。" : "请尽量说明位置、当前状态、影响范围，以及是否有人正处于危险中。" }}</p>
        <div class="starter-grid">
          <button type="button" @click="form.message = '临边作业前需要重点检查哪些事项？'"><strong>检查要点</strong><span>了解通用安全注意事项</span></button>
          <button type="button" @click="form.message = '现场发现一个问题，但信息不完整，我该如何描述？'"><strong>帮我描述</strong><span>梳理事实与缺失信息</span></button>
          <button v-if="mode === 'consult'" type="button" @click="form.message = '有人正在漏电设备附近作业，现场还没有断电。'"><strong>风险咨询</strong><span>先判断紧迫性与避险要求</span></button>
        </div>
      </section>

      <ol v-else class="conversation" aria-label="当前会话消息" aria-live="polite">
        <li v-for="turn in turns" :key="turn.result.turn">
          <div class="message-row user-row"><div class="message-avatar user-avatar">你</div><div class="message-body user-message"><p>{{ turn.message }}</p></div></div>
          <div class="message-row assistant-row">
            <div class="message-avatar assistant-avatar">安</div>
            <div class="message-body assistant-message">
              <div class="message-meta"><strong>{{ turn.result.mode === "mock" ? "Mock 助手" : "安全质量助手" }}</strong><span>第 {{ turn.result.turn }} 轮</span></div>
              <p class="preserve-lines">{{ turn.result.reply.answer }}</p>
              <div v-if="mode === 'consult' || turn.result.reply.analysis.risk_level === 'high' || turn.result.reply.analysis.risk_level === 'emergency'" class="analysis-summary">
                <span>类别 {{ turn.result.reply.analysis.category }}</span><span>风险 {{ turn.result.reply.analysis.risk_level }}</span><span>{{ turn.result.reply.analysis.requires_human_review ? "必须人工复核" : "需结合现场判断" }}</span>
              </div>
              <div v-for="action in turn.result.reply.analysis.immediate_actions" :key="action" class="urgent-callout">{{ action }}</div>
              <div v-if="turn.result.reply.follow_up_questions.length" class="follow-up-box"><strong>还需要确认</strong><ul><li v-for="question in turn.result.reply.follow_up_questions" :key="question">{{ question }}</li></ul></div>
              <details v-if="mode === 'consult'"><summary>查看已校验分析</summary><p>{{ turn.result.reply.analysis.summary }}</p><p>已述事实：{{ turn.result.reply.analysis.observed_facts.join("；") || "未确认" }}</p><p>不确定性：{{ turn.result.reply.analysis.uncertainties.join("；") || "仍需现场核验" }}</p><p>缺失信息：{{ turn.result.reply.analysis.missing_fields.join("；") || "无额外追问" }}</p></details>
            </div>
          </div>
        </li>
      </ol>
      <div v-if="busy" class="typing-row" role="status"><span></span><span></span><span></span><em>正在分析，最多约 35 秒</em></div>
    </div>

    <div class="composer-dock">
      <p v-if="error" class="composer-error" role="alert">{{ error }}。未自动重试，输入已保留。</p>
      <p v-if="latest?.risk_retained" class="risk-retained">此前高风险已由服务端保留，补充文字不能自行降级或宣告解除。</p>
      <div v-if="canCreateProposal" class="proposal-ready">
        <div><strong>最新分析已满足受控工单条件</strong><span>仍需生成提案、核对字段并人工确认后才能保存。</span></div>
        <button type="button" class="primary-button" :disabled="busy || dirty" @click="propose">生成待确认提案</button>
      </div>
      <div class="composer">
        <textarea v-model="form.message" maxlength="1000" rows="1" :disabled="busy || proposed" :placeholder="latest ? '补充同一问题…' : mode === 'chat' ? '输入你的问题…' : '描述现场情况…'" aria-label="会话输入" @keydown="onComposerKeydown"></textarea>
        <div class="composer-toolbar">
          <div class="composer-tools">
            <button type="button" class="tool-button" :disabled="busy" title="添加图片" @click="emit('attachment')">＋ <span>图片</span></button>
            <button type="button" class="tool-button" :class="{ active: contextOpen }" :disabled="busy" @click="contextOpen = !contextOpen">⌁ <span>背景</span></button>
            <label v-if="runtime?.mode === 'real'" class="compact-consent" title="仅授权本次发送到 DeepSeek；可能产生模型费用">
              <input v-model="consent" type="checkbox" /><span>允许本次外发</span>
            </label>
          </div>
          <div class="send-controls"><span>{{ form.message.length }}/1000</span><button type="button" class="send-button" :disabled="!canSend" :aria-label="latest ? '发送补充' : '发送消息'" @click="send">↑</button></div>
        </div>
      </div>
      <div v-if="contextOpen" class="context-fields">
        <label>项目标签（可选）<input v-model="form.project" maxlength="100" /></label>
        <label>区域标签（可选）<input v-model="form.area" maxlength="200" /></label>
        <label>自报角色（非权限）<input v-model="form.requester_role" maxlength="50" /></label>
      </div>
      <div class="composer-foot"><span>Enter 发送 · Shift+Enter 换行</span><button type="button" :disabled="busy" @click="reset">清空并开始新问题</button></div>
      <p v-if="dirty && canCreateProposal" class="section-note">还有未发送的补充，请先发送，避免使用旧分析生成提案。</p>
      <p v-if="proposed" class="success-callout">待确认提案已生成。会话已冻结，尚未创建正式工单。</p>
      <p v-if="latest && !latest.remaining_turns" class="info-callout">本问题已达 6 轮上限，请由人工核对。</p>
    </div>
  </section>
</template>
