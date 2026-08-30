<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import type { IssueAnalysis, IssueProposalPreviewData, TextTurnRequest, TextTurnResponse, VisionRuntime, TextProgress } from "../types";

const props = defineProps<{ mode: "chat" | "consult" }>();
const emit = defineEmits<{
  proposal: [data: IssueProposalPreviewData];
  analysis: [data: IssueAnalysis | null];
  busy: [value: boolean];
  proposing: [value: boolean];
  attachment: [];
}>();
const runtime = ref<VisionRuntime | null>(null);
const form = reactive({ message: "", project: "", area: "", requester_role: "" });
const busy = ref(false);
const error = ref("");
const latest = ref<TextTurnResponse | null>(null);
const turns = ref<{ message: string; result: TextTurnResponse; seconds: number; steps: TextProgress[] }[]>([]);
const proposed = ref(false);
const contextOpen = ref(false);
const pendingMessage = ref("");
const messageStage = ref<HTMLElement | null>(null);
let pending: TextTurnRequest | null = null;
let activeRequest: AbortController | null = null;
const elapsedSeconds = ref(0);
const steps = ref<TextProgress[]>([]);
let startedAt = 0;
let ticker: ReturnType<typeof setInterval> | null = null;
const stageLabels: Record<TextProgress["stage"], string> = {
  queued: "服务端已接收，等待执行", preparing: "正在校验请求与整理上下文",
  model_running: "等待模型回复", validating: "正在校验结果与安全边界",
  tool_running: "正在生成待确认提案", completed: "处理完成",
};
function stageLabel(step: TextProgress) {
  return step.stage === "model_running" && runtime.value?.mode === "mock"
    ? "正在执行 Mock 验证（未调用真实模型）"
    : step.stage === "model_running" && props.mode === "chat" ? "模型处理中（已开启深度思考）" : stageLabels[step.stage];
}
const currentStep = computed(() => steps.value.at(-1));
const activeStepLabel = computed(() => currentStep.value ? stageLabel(currentStep.value) : "正在发送，等待服务端接收");
function beginProgress() {
  stopProgress(); steps.value = []; elapsedSeconds.value = 0; startedAt = performance.now();
  ticker = setInterval(() => { elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1000); }, 250);
}
function stopProgress() {
  if (ticker !== null) {
    elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1000);
    clearInterval(ticker); ticker = null;
  }
}
function requestId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
}
const maxInput = computed(() => props.mode === "chat" ? 16_000 : 1000);
const maxTurns = computed(() => props.mode === "chat" ? 50 : 6);
const canSend = computed(() => !busy.value && !proposed.value && runtime.value?.configured && Boolean(form.message.trim())
  && form.message.length <= maxInput.value && (latest.value?.remaining_turns ?? maxTurns.value) > 0);
const dirty = computed(() => Boolean(form.message.trim()));
const canCreateProposal = computed(() => props.mode === "consult" && latest.value?.can_propose && !proposed.value);
const modelLabel = computed(() => {
  const model = runtime.value?.model;
  if (!model) return "模型检查中";
  if (model === "deepseek-v4-flash") return "DeepSeek V4 Flash";
  if (model === "deepseek-v4-pro") return "DeepSeek V4 Pro";
  if (runtime.value?.mode === "mock") return "本地 Mock";
  return model;
});
const prompt = computed(() => props.mode === "chat"
  ? "你好，今天想聊点什么？"
  : "描述现场发生了什么，我会先提取信息、追问并判断风险。");

onMounted(async () => {
  try { runtime.value = await api.getTextRuntime(); }
  catch { error.value = "文字服务未连接，请启动后端并刷新；已有工单不受影响。"; }
});
watch(form, () => { if (!busy.value) pending = null; }, { flush: "sync" });
watch(busy, value => emit("busy", value), { flush: "sync" });
watch(() => props.mode, () => reset(true));
watch([pendingMessage, () => turns.value.length], async () => {
  await nextTick();
  messageStage.value?.scrollTo({ top: messageStage.value.scrollHeight });
});
onBeforeUnmount(cancelActiveRequest);

function cancelActiveRequest() {
  stopProgress();
  activeRequest?.abort();
  activeRequest = null;
  busy.value = false;
  emit("busy", false);
}

function stopWaiting() {
  const savedRequest = pending;
  const message = pendingMessage.value;
  cancelActiveRequest();
  form.message = message;
  pendingMessage.value = "";
  pending = savedRequest;
  error.value = "已停止等待，服务端可能仍在处理或计费；原请求已保留，可稍后手动重试";
}

function reset(force = false) {
  if (busy.value && !force) return;
  if (force) cancelActiveRequest();
  busy.value = false;
  latest.value = null; turns.value = []; proposed.value = false; error.value = "";
  form.message = ""; pending = null; pendingMessage.value = ""; contextOpen.value = false; emit("analysis", null);
  steps.value = []; elapsedSeconds.value = 0;
}

async function send() {
  if (!canSend.value) return;
  busy.value = true; error.value = "";
  const input = { message: form.message.trim(), project: form.project.trim() || null,
    area: form.area.trim() || null, requester_role: form.requester_role.trim() || null };
  pendingMessage.value = input.message;
  form.message = "";
  const requestController = new AbortController();
  activeRequest = requestController;
  try {
    beginProgress();
    pending ||= { request_id: requestId(), intent: props.mode, input,
      consultation_id: latest.value?.consultation_id || null, expected_turn: latest.value?.turn || 0,
      allow_external: runtime.value?.mode === "real" };
    const receiveProgress = (step: TextProgress) => {
      if (!requestController.signal.aborted) steps.value.push(step);
    };
    const result = await api.sendText(pending, requestController.signal, receiveProgress);
    if (requestController.signal.aborted) return;
    latest.value = result;
    stopProgress();
    turns.value.push({ message: input.message, result, seconds: elapsedSeconds.value, steps: [...steps.value] });
    pendingMessage.value = ""; pending = null;
    emit("analysis", result.reply.analysis);
  } catch (cause) {
    if (requestController.signal.aborted) return;
    error.value = !pending ? "发送准备失败，请刷新页面或更换浏览器后重试。" : cause instanceof Error ? cause.message : String(cause);
    form.message = pendingMessage.value;
    pendingMessage.value = "";
  } finally {
    if (activeRequest === requestController) {
      stopProgress();
      activeRequest = null;
      busy.value = false;
    }
  }
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
  emit("proposing", true);
  try {
    beginProgress();
    const result = await api.proposeText(latest.value.consultation_id, latest.value.turn, step => steps.value.push(step));
    if (!result.ok) throw new Error(result.summary);
    proposed.value = true; emit("proposal", result.data);
  } catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { stopProgress(); busy.value = false; emit("proposing", false); }
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
      <div class="connection-pill" :class="{ online: runtime?.configured }" title="仅检查本地配置，不代表模型已成功回复"><span></span>{{ runtime?.configured ? runtime.mode === 'mock' ? "Mock 已配置" : "模型已配置" : error ? "服务未连接" : "连接检查中" }}</div>
    </header>

    <div ref="messageStage" class="message-stage">
      <section v-if="!turns.length && !pendingMessage" class="empty-conversation" aria-live="polite">
        <div class="assistant-orb" aria-hidden="true"></div>
        <h2>{{ prompt }}</h2>
        <p>{{ mode === "chat" ? "回答仅供参考；涉及现场风险时仍需专业人员核验。" : "请尽量说明位置、当前状态、影响范围，以及是否有人正处于危险中。" }}</p>
        <div v-if="mode === 'chat'" class="starter-grid">
          <button type="button" @click="form.message = '今天几号了？'"><strong>日常问答</strong><span>日期、常识，随时聊聊</span></button>
          <button type="button" @click="form.message = '帮我写一段简短的自我介绍。'"><strong>帮我写作</strong><span>整理表达与文字草稿</span></button>
          <button type="button" @click="form.message = '请用简单的语言解释什么是人工智能。'"><strong>解释概念</strong><span>把复杂知识说清楚</span></button>
        </div>
        <div v-else class="starter-grid">
          <button type="button" @click="form.message = '临边作业前需要重点检查哪些事项？'"><strong>检查要点</strong><span>了解通用安全注意事项</span></button>
          <button type="button" @click="form.message = '现场发现一个问题，但信息不完整，我该如何描述？'"><strong>帮我描述</strong><span>梳理事实与缺失信息</span></button>
          <button v-if="mode === 'consult'" type="button" @click="form.message = '有人正在漏电设备附近作业，现场还没有断电。'"><strong>风险咨询</strong><span>先判断紧迫性与避险要求</span></button>
        </div>
      </section>

      <ol v-else class="conversation" aria-label="当前会话消息" aria-live="polite">
        <li v-for="turn in turns" :key="turn.result.turn">
          <div class="message-row user-row" aria-label="你的消息" role="group"><div class="message-body user-message"><p>{{ turn.message }}</p></div></div>
          <div class="message-row assistant-row" aria-label="助手回复" role="group">
            <div class="message-body assistant-message">
              <details class="execution-history">
                <summary>用时 {{ turn.seconds }} 秒</summary>
                <div class="execution-detail">
                  <p v-if="turn.result.mode === 'mock'">Mock 验证，未调用真实模型。</p>
                  <p v-if="!turn.steps.some(step => step.tool)">未调用业务工具。</p>
                  <ol v-if="turn.steps.length"><li v-for="step in turn.steps" :key="step.seq">{{ (step.elapsed_ms / 1000).toFixed(1) }} 秒 · {{ stageLabel(step) }}{{ step.tool ? ` · ${step.tool}` : '' }}</li></ol>
                </div>
              </details>
              <p class="preserve-lines">{{ turn.result.reply.answer }}</p>
              <div v-if="mode === 'consult' || turn.result.reply.analysis.risk_level === 'high' || turn.result.reply.analysis.risk_level === 'emergency'" class="analysis-summary">
                <span>类别 {{ turn.result.reply.analysis.category }}</span><span>风险 {{ turn.result.reply.analysis.risk_level }}</span><span>{{ turn.result.reply.analysis.requires_human_review ? "必须人工复核" : "需结合现场判断" }}</span>
              </div>
              <div v-for="action in turn.result.reply.analysis.immediate_actions" :key="action" class="urgent-callout">{{ action }}</div>
              <div v-if="mode === 'consult' && turn.result.reply.follow_up_questions.length" class="follow-up-box"><strong>还需要确认</strong><ul><li v-for="question in turn.result.reply.follow_up_questions" :key="question">{{ question }}</li></ul></div>
              <details v-if="mode === 'consult'"><summary>查看已校验分析</summary><p>{{ turn.result.reply.analysis.summary }}</p><p>已述事实：{{ turn.result.reply.analysis.observed_facts.join("；") || "未确认" }}</p><p>不确定性：{{ turn.result.reply.analysis.uncertainties.join("；") || "仍需现场核验" }}</p><p>缺失信息：{{ turn.result.reply.analysis.missing_fields.join("；") || "无额外追问" }}</p></details>
            </div>
          </div>
        </li>
        <li v-if="pendingMessage" class="pending-turn">
          <div class="message-row user-row" aria-label="你的消息" role="group"><div class="message-body user-message"><p>{{ pendingMessage }}</p></div></div>
        </li>
      </ol>
      <div v-if="busy" class="execution-status" role="status" aria-live="polite">
        <div class="execution-current"><span class="execution-spinner" aria-hidden="true"></span><strong>{{ activeStepLabel }}</strong><span class="elapsed-time" aria-live="off">已等待 {{ elapsedSeconds }} 秒</span></div>
        <p v-if="currentStep?.tool">正在调用工具：{{ currentStep.tool }}</p>
        <button v-if="pendingMessage" type="button" class="tool-button" @click="stopWaiting">停止等待</button>
        <details><summary>查看执行步骤</summary><p>{{ mode === 'chat' ? '最多约 190 秒' : '最多约 35 秒' }} · {{ currentStep?.tool ? '业务工具执行中' : '当前未调用业务工具' }}</p><ol v-if="steps.length"><li v-for="step in steps" :key="step.seq">{{ (step.elapsed_ms / 1000).toFixed(1) }} 秒 · {{ stageLabel(step) }}{{ step.tool ? ` · ${step.tool}` : '' }}</li></ol></details>
      </div>
      <p v-else-if="proposed" class="execution-finished">提案工具 propose_issue_record 已完成 · 用时 {{ elapsedSeconds }} 秒 · 尚未保存工单</p>
    </div>

    <div class="composer-dock">
      <p v-if="error" class="composer-error" role="alert">{{ error }}。未自动重试，输入已保留。</p>
      <p v-if="latest?.context_trimmed" class="section-note">本轮仅参考最近的部分对话；早期内容仍显示在页面，但未全部发送给模型。需要时请重新补充。</p>
      <p v-if="latest?.risk_retained" class="risk-retained">此前高风险已由服务端保留，补充文字不能自行降级或宣告解除。</p>
      <div v-if="canCreateProposal" class="proposal-ready">
        <div><strong>最新分析已满足受控工单条件</strong><span>仍需生成提案、核对字段并人工确认后才能保存。</span></div>
        <button type="button" class="primary-button" :disabled="busy || dirty" @click="propose">生成待确认提案</button>
      </div>
      <div class="composer">
        <textarea v-model="form.message" :maxlength="maxInput" rows="1" :disabled="busy || proposed" :placeholder="mode === 'chat' ? '输入你的问题，或继续追问…' : latest ? '补充同一问题…' : '描述现场情况…'" aria-label="会话输入" @keydown="onComposerKeydown"></textarea>
        <div class="composer-toolbar">
          <div class="composer-tools">
            <button type="button" class="tool-button" :disabled="busy" title="添加图片" @click="emit('attachment')">＋ <span>图片</span></button>
            <button type="button" class="tool-button" :class="{ active: contextOpen }" :disabled="busy" @click="contextOpen = !contextOpen">⌁ <span>背景</span></button>
          </div>
          <div class="send-controls">
            <label class="model-picker" title="模型由服务端安全配置，网页不能覆盖"><span class="sr-only">模型</span><select aria-label="选择模型" :disabled="!runtime?.configured"><option>{{ modelLabel }}</option></select></label>
            <span>{{ form.message.length }}/{{ maxInput }}</span><button type="button" class="send-button" :disabled="!canSend" :aria-label="latest ? '发送补充' : '发送消息'" @click="send">↑</button>
          </div>
        </div>
      </div>
      <div v-if="contextOpen" class="context-fields">
        <label>项目标签（可选）<input v-model="form.project" maxlength="100" /></label>
        <label>区域标签（可选）<input v-model="form.area" maxlength="200" /></label>
        <label>自报角色（非权限）<input v-model="form.requester_role" maxlength="50" /></label>
      </div>
      <div class="composer-foot"><span>Enter 发送 · Shift+Enter 换行</span><button type="button" :disabled="busy" @click="reset()">清空并开始新问题</button></div>
      <p v-if="dirty && canCreateProposal" class="section-note">还有未发送的补充，请先发送，避免使用旧分析生成提案。</p>
      <p v-if="proposed" class="success-callout">待确认提案已生成。会话已冻结，尚未创建正式工单。</p>
      <p v-if="latest && !latest.remaining_turns" class="info-callout">本会话已达 {{ maxTurns }} 轮上限，请开始新问题。</p>
    </div>

  </section>
</template>
