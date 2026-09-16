<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import { categoryNames, riskNames } from "../customerLabels";
import { renderAssistantMarkdown } from "../markdown";
import type { IssueAnalysis, IssueProposalPreviewData, TextTurnRequest, TextTurnResponse, VisionRuntime, TextProgress, TextContentDelta } from "../types";

const props = defineProps<{ mode: "chat" | "consult" | "auto"; sessionId?: string; newChatKey?: string }>();
const emit = defineEmits<{
  proposal: [data: IssueProposalPreviewData];
  analysis: [data: IssueAnalysis | null];
  busy: [value: boolean];
  proposing: [value: boolean];
  attachment: [];
  ticket: [analysis: IssueAnalysis];
  session: [id: string];
}>();
const runtime = ref<VisionRuntime | null>(null);
const form = reactive({ message: "", project: "", area: "", requester_role: "" });
const busy = ref(false);
const error = ref("");
const latest = ref<TextTurnResponse | null>(null);
const turns = ref<{ message: string; result: TextTurnResponse; seconds: number; steps: TextProgress[]; thinking: "fast" | "deep" }[]>([]);
const proposed = ref(false);
const contextOpen = ref(false);
const pendingMessage = ref("");
const messageStage = ref<HTMLElement | null>(null);
let pending: TextTurnRequest | null = null;
let activeRequest: AbortController | null = null;
const elapsedSeconds = ref(0);
const steps = ref<TextProgress[]>([]);
const streamedAnswer = ref("");
const modelChoice = ref("");
const customModel = ref("");
const thinkingMode = ref<"fast" | "deep">("fast");
const activeThinking = ref<"fast" | "deep">("fast");
const toolsEnabled = ref(true);
const restoring = ref(false);
let restoreGeneration = 0;
const pendingKey = () => `sea-son-pending:${props.sessionId || 'new'}`;
function savePending(value: TextTurnRequest | null) {
  try {
    if (value) window.sessionStorage.setItem(pendingKey(), JSON.stringify(value));
    else window.sessionStorage.removeItem(pendingKey());
  } catch { /* In-memory retry remains available when browser storage is disabled. */ }
}
async function restoreSession(force = false) {
  if (!force && props.sessionId && props.sessionId === latest.value?.consultation_id) return;
  const generation = ++restoreGeneration;
  reset(true); restoring.value = true;
  let completedRequests: string[] = [];
  try {
    if (props.sessionId) {
      const session = await api.getChatSession(props.sessionId);
      if (generation !== restoreGeneration) return;
      turns.value = session.turns.map(turn => ({ ...turn, seconds: 0, steps: [] }));
      completedRequests = session.turns.map(turn => turn.request_id);
      latest.value = turns.value.at(-1)?.result || null;
      proposed.value = session.proposed;
    }
    try {
      const raw = window.sessionStorage.getItem(pendingKey());
      const saved = raw ? JSON.parse(raw) as TextTurnRequest : null;
      if (saved && typeof saved.request_id === 'string' && typeof saved.input?.message === 'string'
          && (saved.consultation_id || null) === (props.sessionId || null)) {
        if (completedRequests.includes(saved.request_id)) { savePending(null); return; }
        form.message = saved.input.message;
        thinkingMode.value = saved.thinking_mode || 'fast';
        if (saved.model) modelChoice.value = saved.model;
        toolsEnabled.value = saved.tools_enabled ?? false;
        pending = saved.expected_turn === (latest.value?.turn || 0) ? saved : null;
        error.value = pending ? '上次请求尚未确认完成；可手动重试，服务端会复用已保存结果。' : '会话已更新；原输入已恢复，请核对最新回复后发送。';
      }
    } catch { /* Invalid browser draft is never used as model history. */ }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause); }
  finally { if (generation === restoreGeneration) restoring.value = false; }
}
async function reloadLatest() {
  const draft = form.message;
  savePending(null);
  await restoreSession(true);
  form.message = draft;
  pending = null;
}
let startedAt = 0;
let ticker: ReturnType<typeof setInterval> | null = null;
const stageLabels: Record<TextProgress["stage"], string> = {
  queued: "已收到，等待处理", preparing: "正在整理你的问题",
  model_running: "等待模型回复", validating: "正在检查回答",
  tool_running: "正在生成待确认提案", tool_completed: "工具已返回", responding: "正在回复", completed: "处理完成",
};
const toolLabels: Record<string, string> = { propose_issue_record: "工单申请", web_search: "搜索网页", read_webpage: "读取网页", current_time: "读取日期时间", search_knowledge: "检索规范知识", calculate: "基础计算" };
function stageLabel(step: TextProgress) {
  if (step.tool && step.stage === 'tool_running') return '正在' + toolLabels[step.tool];
  if (step.tool && step.stage === 'tool_completed') return toolLabels[step.tool] + '已返回';
  return step.stage === "model_running" && runtime.value?.mode === "mock"
    ? "AI 服务未启用，正在返回使用提示"
    : stageLabels[step.stage];
}
const currentStep = computed(() => steps.value.at(-1));
const activeStepLabel = computed(() => currentStep.value?.stage === "model_running" && runtime.value?.mode === "real"
  ? activeThinking.value === "deep" ? "深度思考已开启，等待回复" : "快速回复，等待模型输出"
  : currentStep.value ? stageLabel(currentStep.value) : "正在发送，等待服务端接收");
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
const maxInput = computed(() => props.mode === "consult" ? 1000 : 16_000);
const maxTurns = computed(() => props.mode === "consult" ? 6 : 50);
const selectedModel = computed(() => modelChoice.value === "__custom__" ? customModel.value.trim() : modelChoice.value);
const modelReady = computed(() => runtime.value?.mode === "mock" || /^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/.test(selectedModel.value));
const canSend = computed(() => !restoring.value && !busy.value && !proposed.value && runtime.value?.configured && Boolean(form.message.trim())
  && modelReady.value && form.message.length <= maxInput.value && (latest.value?.remaining_turns ?? maxTurns.value) > 0);
const dirty = computed(() => Boolean(form.message.trim()));
const canCreateProposal = computed(() => props.mode === "consult" && latest.value?.can_propose && !proposed.value);
function modelLabel(model: string) {
  if (!model) return "模型检查中";
  if (model === "deepseek-v4-flash") return "DeepSeek V4 Flash";
  if (model === "deepseek-v4-pro") return "DeepSeek V4 Pro";
  if (runtime.value?.mode === "mock") return "AI 未启用";
  return model;
}
const prompt = "你好，今天想聊点什么？";

onMounted(async () => {
  try {
    runtime.value = await api.getTextRuntime();
    modelChoice.value = runtime.value.model;
    if (props.sessionId || typeof window !== 'undefined') await restoreSession();
  }
  catch { error.value = "工作台未连接，请重新打开软件；已保存工单不受影响。"; }
});
watch(form, () => { if (!busy.value) pending = null; }, { flush: "sync" });
watch([thinkingMode, modelChoice, customModel], () => { if (!busy.value) pending = null; }, { flush: "sync" });
watch(toolsEnabled, () => { if (!busy.value) pending = null; }, { flush: "sync" });
watch(busy, value => emit("busy", value), { flush: "sync" });
watch(() => props.mode, () => reset(true));
watch(() => props.sessionId, () => { void restoreSession(); });
watch(() => props.newChatKey, key => {
  if (!key) return; // Saving replaces ?new with ?chat; it is not a new-chat action.
  ++restoreGeneration; savePending(null); reset(true); restoring.value = false;
});
watch([pendingMessage, streamedAnswer, () => turns.value.length], async () => {
  await nextTick();
  messageStage.value?.scrollTo({ top: messageStage.value.scrollHeight });
});
onBeforeUnmount(() => { ++restoreGeneration; cancelActiveRequest(); });

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
  streamedAnswer.value = "";
  pending = savedRequest;
  error.value = "已停止等待，服务端可能仍在处理或计费；原请求已保留，可稍后手动重试";
}

function reset(force = false) {
  if (busy.value && !force) return;
  if (force) cancelActiveRequest();
  busy.value = false;
  latest.value = null; turns.value = []; proposed.value = false; error.value = "";
  form.message = ""; pending = null; pendingMessage.value = ""; contextOpen.value = false; emit("analysis", null);
  steps.value = []; streamedAnswer.value = ""; elapsedSeconds.value = 0;
}
function newConversation() {
  savePending(null); ++restoreGeneration; reset(true); emit('session', '');
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
    pending ||= { request_id: requestId(), intent: "auto", input,
      thinking_mode: thinkingMode.value,
      tools_enabled: toolsEnabled.value,
      model: selectedModel.value || null,
      consultation_id: latest.value?.consultation_id || null, expected_turn: latest.value?.turn || 0,
      allow_external: runtime.value?.mode === "real" };
    savePending(pending);
    activeThinking.value = pending.thinking_mode || "fast";
    const receiveProgress = (step: TextProgress) => {
      if (!requestController.signal.aborted) steps.value.push(step);
    };
    const receiveDelta = (delta: TextContentDelta) => {
      if (!requestController.signal.aborted) streamedAnswer.value += delta.text;
    };
    const result = await api.sendText(pending, requestController.signal, receiveProgress, receiveDelta);
    if (requestController.signal.aborted) return;
    latest.value = result;
    stopProgress();
    if (!turns.value.some(turn => turn.result.turn === result.turn)) turns.value.push({ message: input.message, result, seconds: elapsedSeconds.value, steps: [...steps.value], thinking: activeThinking.value });
    savePending(null);
    pendingMessage.value = ""; streamedAnswer.value = ""; pending = null;
    emit('session', result.consultation_id);
    const analysisAvailable = !result.analysis_status || result.analysis_status === "validated";
    emit("analysis", analysisAvailable ? result.reply.analysis : null);
    if (analysisAvailable && result.can_propose) emit("ticket", result.reply.analysis);
  } catch (cause) {
    if (requestController.signal.aborted) return;
    error.value = !pending ? "发送准备失败，请刷新页面或更换浏览器后重试。" : cause instanceof Error ? cause.message : String(cause);
    form.message = pendingMessage.value;
    pendingMessage.value = "";
    streamedAnswer.value = "";
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
  <section class="conversation-workspace" aria-labelledby="chat-title">
    <header class="conversation-header">
      <div class="conversation-header-inner">
        <div>
          <p class="workspace-kicker">AI 对话</p>
          <h1 id="chat-title">{{ turns.length ? turns[0]?.message.slice(0, 36) : '新建聊天' }}</h1>
          <p>可以日常交流，也可以描述现场问题；AI 判断需要跟进时会打开对应工单申请，保存前仍需人工确认。</p>
        </div>
        <div class="connection-pill" :class="{ online: runtime?.configured && runtime.mode === 'real' }" title="可在软件的模型设置中配置 AI 服务"><span></span>{{ runtime?.configured ? runtime.mode === 'mock' ? "AI 服务未启用" : "AI 已配置" : error ? "服务未连接" : "连接检查中" }}</div>
      </div>
    </header>

    <div ref="messageStage" class="message-stage">
      <p v-if="restoring" role="status">正在恢复聊天记录…</p>
      <section v-if="!turns.length && !pendingMessage" class="empty-conversation" aria-live="polite">
        <div class="assistant-orb" aria-hidden="true"></div>
        <h2>{{ prompt }}</h2>
        <p>回答仅供参考；涉及现场问题时请说明位置、状态和影响，提交及专业结论仍由人工确认。</p>
        <div class="starter-grid">
          <button type="button" @click="form.message = '今天几号了？'"><strong>日常问答</strong><span>日期、常识，随时聊聊</span></button>
          <button type="button" @click="form.message = '帮我写一段简短的自我介绍。'"><strong>帮我写作</strong><span>整理表达与文字草稿</span></button>
          <button type="button" @click="form.message = '请用简单的语言解释什么是人工智能。'"><strong>解释概念</strong><span>把复杂知识说清楚</span></button>
        </div>
      </section>

      <ol v-else class="conversation" aria-label="当前会话消息" aria-live="polite">
        <li v-for="turn in turns" :key="turn.result.turn">
          <div class="message-row user-row" aria-label="你的消息" role="group"><div class="message-body user-message"><p>{{ turn.message }}</p></div></div>
          <div class="message-row assistant-row" aria-label="助手回复" role="group">
            <div class="message-body assistant-message">
              <div class="markdown-body" v-html="renderAssistantMarkdown(turn.result.mode === 'mock' ? 'AI 服务尚未启用。请在软件的模型设置中填写自己的密钥并启用 AI；也可以直接通过左侧“提交工单”填写问题。' : turn.result.reply.answer)"></div>
              <details class="execution-history">
                <summary>{{ turn.seconds ? `用时 ${turn.seconds} 秒` : '已保存的回复' }} · {{ turn.thinking === 'deep' ? '深度思考' : '快速回复' }} · {{ turn.result.model }}</summary>
                <div class="execution-detail">
                  <p v-if="turn.result.mode === 'mock'">AI 服务未启用，本次未进行智能分析。</p>
                  <p v-if="!turn.steps.some(step => step.tool) && !turn.result.tool_results?.length">未调用工具。</p>
                  <ol v-if="turn.steps.length"><li v-for="step in turn.steps" :key="step.seq">{{ (step.elapsed_ms / 1000).toFixed(1) }} 秒 · {{ stageLabel(step) }}</li></ol>
                  <p v-for="(tool, index) in turn.result.tool_results || []" :key="index">{{ toolLabels[tool.tool] }} · {{ tool.ok ? '完成' : '未完成' }}：{{ tool.summary }}</p>
                </div>
              </details>
              <details v-if="turn.result.sources?.length" class="web-sources"><summary>查看 {{ turn.result.sources.length }} 条来源</summary><ol><li v-for="source in turn.result.sources" :key="source.id"><a :href="source.url" target="_blank" rel="noopener noreferrer">[{{ source.id }}] {{ source.title }}</a><p>{{ source.excerpt }}</p></li></ol></details>
              <div v-if="mode === 'consult' || turn.result.reply.analysis.risk_level === 'high' || turn.result.reply.analysis.risk_level === 'emergency'" class="analysis-summary">
                <span>类别 {{ categoryNames[turn.result.reply.analysis.category] }}</span><span>风险 {{ riskNames[turn.result.reply.analysis.risk_level] }}</span><span>{{ turn.result.reply.analysis.requires_human_review ? "必须人工复核" : "需结合现场判断" }}</span>
              </div>
              <div v-for="action in turn.result.reply.analysis.immediate_actions" :key="action" class="urgent-callout">{{ action }}</div>
              <div v-if="mode === 'consult' && turn.result.reply.follow_up_questions.length" class="follow-up-box"><strong>还需要确认</strong><ul><li v-for="question in turn.result.reply.follow_up_questions" :key="question">{{ question }}</li></ul></div>
              <p v-if="turn.result.analysis_status === 'unavailable'" class="section-note" role="status">回答已保留，本次未能判断工单类型。需要上报时可从左侧“提交工单”填写；如有现场危险，请先远离危险并联系现场专业人员。</p>
              <button v-if="turn.result.turn === latest?.turn && turn.result.can_propose && turn.result.analysis_status !== 'unavailable'" type="button" class="tool-button" :disabled="busy" @click="emit('ticket', turn.result.reply.analysis)">继续工单申请</button>
              <details v-if="mode === 'consult' && turn.result.analysis_status !== 'unavailable'"><summary>查看已校验分析</summary><p>{{ turn.result.reply.analysis.summary }}</p><p>已述事实：{{ turn.result.reply.analysis.observed_facts.join("；") || "未确认" }}</p><p>不确定性：{{ turn.result.reply.analysis.uncertainties.join("；") || "仍需现场核验" }}</p><p>缺失信息：{{ turn.result.reply.analysis.missing_fields.join("；") || "无额外追问" }}</p></details>
            </div>
          </div>
        </li>
        <li v-if="pendingMessage" class="pending-turn">
          <div class="message-row user-row" aria-label="你的消息" role="group"><div class="message-body user-message"><p>{{ pendingMessage }}</p></div></div>
          <div v-if="streamedAnswer && runtime?.mode === 'real'" class="message-row assistant-row" aria-label="助手正在回复" role="group"><div class="message-body assistant-message streaming-answer"><div class="markdown-body" v-html="renderAssistantMarkdown(streamedAnswer)"></div><span class="stream-caret" aria-hidden="true"></span></div></div>
        </li>
      </ol>
      <div v-if="busy" class="execution-status" role="status" aria-live="polite">
        <div class="execution-current"><span class="execution-spinner" aria-hidden="true"></span><strong>{{ activeStepLabel }}</strong><span class="elapsed-time" aria-live="off">已等待 {{ elapsedSeconds }} 秒</span></div>
        <p v-if="currentStep?.tool">工具：{{ toolLabels[currentStep.tool] }}</p>
        <button v-if="pendingMessage" type="button" class="tool-button" @click="stopWaiting">停止等待</button>
        <details><summary>查看执行步骤</summary><p>{{ mode === 'consult' ? '最多约 35 秒' : '最多约 190 秒' }}</p><ol v-if="steps.length"><li v-for="step in steps" :key="step.seq">{{ (step.elapsed_ms / 1000).toFixed(1) }} 秒 · {{ stageLabel(step) }}</li></ol></details>
      </div>
      <p v-else-if="proposed" class="execution-finished">工单申请已准备好 · 用时 {{ elapsedSeconds }} 秒 · 尚未保存工单</p>
    </div>

    <div class="composer-dock">
      <p v-if="error" class="composer-error" role="alert">{{ error }} 未自动重试，输入已保留。</p>
      <button v-if="error && sessionId && !busy" type="button" class="tool-button" @click="reloadLatest">重新加载当前聊天</button>
      <p v-if="latest?.context_trimmed" class="section-note">本轮仅参考最近的部分对话；早期内容仍显示在页面，但未全部发送给模型。需要时请重新补充。</p>
      <p v-if="latest?.risk_retained" class="risk-retained">此前高风险已由服务端保留，补充文字不能自行降级或宣告解除。</p>
      <div v-if="canCreateProposal" class="proposal-ready">
        <div><strong>最新分析已满足受控工单条件</strong><span>仍需生成提案、核对字段并人工确认后才能保存。</span></div>
        <button type="button" class="primary-button" :disabled="busy || dirty" @click="propose">生成待确认提案</button>
      </div>
      <div class="composer">
        <textarea v-model="form.message" :maxlength="maxInput" rows="1" :disabled="busy || proposed" :placeholder="mode !== 'consult' ? '输入你的问题，或继续追问…' : latest ? '补充同一问题…' : '描述现场情况…'" aria-label="会话输入" @keydown="onComposerKeydown"></textarea>
        <div class="composer-toolbar">
          <div class="composer-tools">
            <button type="button" class="tool-button" :class="{ active: toolsEnabled }" :disabled="busy" @click="toolsEnabled = !toolsEnabled" :aria-pressed="toolsEnabled" title="允许按需检索规范、计算、读取公开网页、搜索和时间">工具</button>
            <button type="button" class="tool-button" :disabled="busy" title="添加图片" @click="emit('attachment')">＋ <span>图片</span></button>
            <button type="button" class="tool-button" :class="{ active: contextOpen }" :disabled="busy" @click="contextOpen = !contextOpen">⌁ <span>背景</span></button>
          </div>
          <div class="send-controls">
            <label class="model-picker"><span class="sr-only">回复方式</span><select v-model="thinkingMode" aria-label="回复方式" :disabled="busy || runtime?.mode !== 'real'"><option value="fast">快速回复</option><option value="deep">深度思考</option></select></label>
            <label class="model-picker" title="可选择服务端建议型号，或输入DeepSeek模型标识"><span class="sr-only">模型</span><select v-model="modelChoice" aria-label="选择模型" :disabled="busy || !runtime?.configured || runtime.mode === 'mock'"><option v-for="model in runtime?.available_models || []" :key="model" :value="model">{{ modelLabel(model) }}</option><option v-if="runtime?.custom_model_allowed" value="__custom__">自定义…</option></select></label>
            <span>{{ form.message.length }}/{{ maxInput }}</span><button type="button" class="send-button" :disabled="!canSend" :aria-label="latest ? '发送补充' : '发送消息'" @click="send">↑</button>
          </div>
        </div>
      </div>
      <label v-if="modelChoice === '__custom__'" class="custom-model-field">模型名称<input v-model.trim="customModel" :disabled="busy" aria-label="自定义模型标识" maxlength="100" placeholder="请输入服务商提供的模型名称" /><span>需使用当前模型服务支持的名称。</span></label>
      <div v-if="contextOpen" class="context-fields">
        <label>项目标签（可选）<input v-model="form.project" maxlength="100" /></label>
        <label>区域标签（可选）<input v-model="form.area" maxlength="200" /></label>
        <label>自报角色（非权限）<input v-model="form.requester_role" maxlength="50" /></label>
      </div>
      <div class="composer-foot"><span>{{ runtime?.external_provider || '本地演示' }} · Enter 发送</span><button type="button" @click="newConversation">新建聊天</button></div>
      <details v-if="toolsEnabled" class="section-note"><summary>{{ runtime?.web_tools?.search_configured ? '联网搜索已配置' : '联网搜索未配置' }} · 规范检索、计算与网页工具</summary><p>发送会将消息及必要上下文发给 {{ runtime?.external_provider || '已配置模型服务' }}；工具按需执行。本地规范检索和基础计算无需搜索密钥；规范目录可能不完整或已过期，计算不替代工程校核。搜索关键词发送至 Tavily，可能收费。请在软件“模型设置”填写搜索密钥；未配置时会明确提示，网页读取只支持公开 HTTPS。</p></details>
      <p v-if="dirty && canCreateProposal" class="section-note">还有未发送的补充，请先发送，避免使用旧分析生成提案。</p>
      <p v-if="proposed" class="success-callout">待确认提案已生成。会话已冻结，尚未创建正式工单。</p>
      <p v-if="latest && !latest.remaining_turns" class="info-callout">本会话已达 {{ maxTurns }} 轮上限，请开始新问题。</p>
    </div>

  </section>
</template>
