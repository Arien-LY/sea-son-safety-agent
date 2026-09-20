<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { api } from "../api";
import { categoryNames, riskNames, routeNames, actorNames, actionNames } from "../customerLabels";
import TextPanel from "../components/TextPanel.vue";
import type {
  ActorRole,
  ConfirmedIssueProposal,
  IssueAnalysis,
  IssueProposalPreviewData,
  IssueCategory,
  IssueRecord,
  IssueRecordProposal,
  IssueRecordReviewFields,
  ProposalFieldChange,
  ResponsibleRole,
  RiskLevel,
  RuntimeInfo,
  WorkflowAction,
  WorkflowTransitionInput,
} from "../types";

const runtime = ref<RuntimeInfo | null>(null);
const route = useRoute();
const router = useRouter();
const isDetail = computed(() => route.name === "record-detail");
const workspaceMode = computed<"chat" | "submit">(() => {
  if (route.name === "submit") return "submit";
  return "chat";
});
const isConversation = computed(() => !isDetail.value && workspaceMode.value !== "submit");
const isSubmit = computed(() => !isDetail.value && workspaceMode.value === "submit");
function rememberChat(id: string) {
  window.dispatchEvent(new Event('sea-son-chat-saved'));
  if (isConversation.value) void router.replace({ path: '/chat', query: id ? { chat: id } : { new: String(Date.now()) } });
}
const loadingRecord = ref(false);
const recordError = ref("");
let loadGeneration = 0;
let saveKey = "";
const runtimeError = ref("");
const actionError = ref("");
const previewing = ref(false);
const confirming = ref(false);
const saving = ref(false);
const advancing = ref(false);
const deleting = ref(false);
const textBusy = ref(false);
const imageBusy = ref(false);
const textProposalBusy = ref(false);
const working = computed(() => previewing.value || confirming.value || saving.value || advancing.value || textBusy.value || imageBusy.value);
const routeBlocking = computed(() => previewing.value || confirming.value || saving.value || advancing.value || imageBusy.value || textProposalBusy.value);
const proposal = ref<IssueRecordProposal | null>(null);
const proposalToken = ref("");
const editedFields = ref<IssueRecordReviewFields | null>(null);
const confirmed = ref<ConfirmedIssueProposal | null>(null);
const record = ref<IssueRecord | null>(null);
const actionNote = ref("");
const selectedRole = ref<ResponsibleRole>("safety_officer");

const analysisForm = reactive({
  category: "safety" as Extract<IssueCategory, "safety" | "quality" | "management" | "logistics">,
  issueType: "临边防护",
  summary: "作业层临边缺少防护栏杆，需要现场人员核实并跟进。",
  riskLevel: "medium" as RiskLevel,
});

const fieldLabels: Record<keyof IssueRecordReviewFields, string> = {
  record_title: "记录标题",
  record_description: "问题描述",
  project: "项目",
  area: "区域",
  reporter_note: "补充说明",
};

const statusLabels = {
  draft: "草稿",
  submitted: "已提交",
  assigned: "已派工",
  rectifying: "整改中",
  pending_review: "待复查",
  closed: "已关闭",
};

const roleLabels: Record<ResponsibleRole, string> = {
  safety_officer: "安全管理人员",
  quality_inspector: "质量检查人员",
  site_manager: "现场管理人员",
  facilities_staff: "后勤维修人员",
};

const liveChanges = computed<ProposalFieldChange[]>(() => {
  if (!proposal.value || !editedFields.value) return [];
  const before = proposal.value.review_fields;
  const after = editedFields.value;
  return (Object.keys(fieldLabels) as Array<keyof IssueRecordReviewFields>)
    .filter((field) => before[field] !== after[field])
    .map((field) => ({ field, before: before[field], after: after[field] }));
});

const highRiskRecord = computed(() =>
  record.value ? ["high", "emergency"].includes(record.value.analysis.risk_level) : false,
);

onBeforeRouteLeave(() => !routeBlocking.value);
onBeforeRouteUpdate(() => !routeBlocking.value);

async function loadRecord() {
  const current = ++loadGeneration;
  record.value = null; recordError.value = ""; actionError.value = ""; actionNote.value = "";
  if (!isDetail.value) { loadingRecord.value = false; return; }
  const id = String(route.params.recordId);
  if (!/^ISS-[A-F0-9]{12}$/.test(id)) { recordError.value = "工单编号格式无效。"; loadingRecord.value = false; return; }
  loadingRecord.value = true;
  try {
    const result = await api.getIssueRecord(id);
    if (current === loadGeneration) { record.value = result; selectedRole.value = result.suggested_responsible_role; }
  } catch (cause) { if (current === loadGeneration) recordError.value = String(cause); }
  finally { if (current === loadGeneration) loadingRecord.value = false; }
}
watch(() => route.fullPath, () => {
  proposal.value = null; confirmed.value = null; editedFields.value = null;
  void loadRecord();
}, { immediate: true });
watch(editedFields, () => { confirmed.value = null; saveKey = ""; }, { deep: true });

onMounted(async () => {
  try {
    runtime.value = await api.getRuntime();
  } catch {
    runtimeError.value = "服务未连接，请重新打开软件";
  }
});

function buildAnalysis(): IssueAnalysis {
  const highRisk = ["high", "emergency"].includes(analysisForm.riskLevel);
  return {
    category: analysisForm.category,
    issue_type: analysisForm.issueType,
    summary: analysisForm.summary,
    observed_facts: [analysisForm.summary],
    uncertainties: ["具体项目、区域和影响范围仍需用户补充"],
    missing_fields: ["项目", "具体区域", "影响范围"],
    risk_level: analysisForm.riskLevel,
    immediate_actions: highRisk ? ["立即远离危险区域并通知现场专业人员"] : [],
    suggested_actions: ["安排有资格的现场人员核实并确定后续处置"],
    recommended_route: highRisk ? "human_review" : "propose_workflow",
    requires_human_review: highRisk,
    confidence: 0.8,
  };
}

function uniqueId(prefix: string): string {
  return globalThis.crypto?.randomUUID?.() || `${prefix}-${Date.now()}`;
}

function usePhotoProposal(data: IssueProposalPreviewData) {
  proposal.value = data.proposal;
  proposalToken.value = data.proposal_token;
  editedFields.value = { ...data.proposal.review_fields };
  confirmed.value = null;
  record.value = null;
  actionError.value = "";
  saveKey = "";
}

async function createPreview() {
  previewing.value = true;
  actionError.value = "";
  confirmed.value = null;
  record.value = null;
  try {
    const result = await api.previewIssueProposal(uniqueId("preview"), buildAnalysis());
    if (!result.ok) {
      throw new Error(result.summary);
    }
    proposal.value = result.data.proposal;
    proposalToken.value = result.data.proposal_token;
    editedFields.value = { ...result.data.proposal.review_fields };
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "无法生成提案";
  } finally {
    previewing.value = false;
  }
}

async function confirmProposal() {
  if (!proposal.value || !editedFields.value) return;
  confirming.value = true;
  actionError.value = "";
  try {
    confirmed.value = await api.confirmIssueProposal(
      proposal.value,
      proposalToken.value,
      editedFields.value,
    );
    saveKey = uniqueId("create");
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "无法确认提案";
  } finally {
    confirming.value = false;
  }
}

async function deleteRecord() {
  if (!record.value || deleting.value) return;
  if (!window.confirm("确定删除此工单吗？删除后本地记录将无法恢复。")) return;
  deleting.value = true;
  actionError.value = "";
  try {
    await api.deleteIssueRecord(record.value.record_id);
    record.value = null;
    deleting.value = false;
    await router.push({ name: "records" });
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "删除工单失败，请重试。";
    deleting.value = false;
  }
}

async function saveDraft() {
  if (!confirmed.value) return;
  saving.value = true;
  actionError.value = "";
  try {
    const result = await api.createIssueRecord(
      confirmed.value,
      saveKey || (saveKey = uniqueId("create")),
      { actor_id: "reporter-demo", role: "reporter" },
    );
    record.value = result.record;
    selectedRole.value = result.record.suggested_responsible_role;
    saving.value = false;
    await router.push({ name: "record-detail", params: { recordId: result.record.record_id } });
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "无法保存草稿";
  } finally {
    saving.value = false;
  }
}

async function advance(
  action: WorkflowAction,
  actorId: string,
  role: ActorRole,
  options: { note?: boolean; assign?: boolean } = {},
) {
  if (!record.value) return;
  if (options.note && !actionNote.value.trim()) {
    actionError.value = "请先填写本次动作说明。";
    return;
  }
  advancing.value = true;
  actionError.value = "";
  const input: WorkflowTransitionInput = {
    action,
    actor: { actor_id: actorId, role },
    expected_revision: record.value.revision,
  };
  if (options.note) input.note = actionNote.value.trim();
  if (options.assign) {
    input.assignee_id = "rectifier-demo";
    input.assignee_role = selectedRole.value;
  }
  try {
    record.value = await api.transitionIssueRecord(record.value.record_id, input);
    actionNote.value = "";
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "工作流动作失败";
  } finally {
    advancing.value = false;
  }
}

function cancelRecord() {
  if (!record.value) return;
  if (highRiskRecord.value) {
    return advance("cancel", "professional-reviewer-demo", "professional_reviewer", { note: true });
  }
  if (record.value.status === "draft") {
    return advance("cancel", record.value.reporter_id, "reporter", { note: true });
  }
  return advance("cancel", "coordinator-demo", "coordinator", { note: true });
}

function closeRecord() {
  return highRiskRecord.value
    ? advance("close", "professional-reviewer-demo", "professional_reviewer", { note: true })
    : advance("close", "reviewer-demo", "reviewer", { note: true });
}

function displayValue(value: string | null): string {
  return value || "（未填写）";
}
</script>

<template>
  <section v-if="isDetail || isSubmit" class="workspace-header">
    <div>
      <p class="workspace-kicker">{{ isDetail ? "历史工单" : "问题上报" }}</p>
      <h1>{{ isDetail ? "工单详情与整改" : "提交工单" }}</h1>
      <p>{{ isDetail ? "查看处理进展，继续整改与复查。" : "填写问题信息，核对并确认后保存。" }}</p>
    </div>
    <div class="connection-pill" :class="{ online: runtime }"><span></span>{{ runtime ? "服务已连接" : runtimeError || "正在检查服务" }}</div>
  </section>

  <fieldset class="workspace-fields" :class="{ 'conversation-fields': isConversation }" :disabled="routeBlocking || loadingRecord" aria-label="咨询和工单操作区">
  <TextPanel v-if="isConversation" mode="auto" :session-id="typeof route.query.chat === 'string' ? route.query.chat : undefined" :new-chat-key="String(route.query.new || '')" @session="rememberChat" @proposal="usePhotoProposal" @busy="textBusy = $event" @proposing="textProposalBusy = $event" :disabled="routeBlocking || loadingRecord" />
  <fieldset class="business-fields" :disabled="working || loadingRecord" aria-label="工单和附件操作区">
  <div v-if="isDetail" class="record-toolbar"><RouterLink to="/records" class="secondary-button">← 返回历史工单</RouterLink><button class="secondary-button" :disabled="loadingRecord || advancing" @click="loadRecord">刷新详情</button></div>
  <div v-if="loadingRecord" class="loading-state" role="status"><span></span><p><strong>正在读取工单详情</strong><small>正在获取处理记录…</small></p></div>
  <p v-if="recordError" class="error-message" role="alert">{{ recordError }}</p>
  <p v-if="actionError" class="error-message" role="alert">{{ actionError }}</p>

  <section v-if="isSubmit && !proposal" class="proposal-workbench direct-submit">
  <section aria-labelledby="proposal-workbench-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">第 1 步 · 描述待提交问题</p>
        <h2 id="proposal-workbench-title">问题信息</h2>
      </div>
      <span class="safe-chip">不调用模型</span>
    </div>
    <p class="section-note">
      请核对问题信息。确认保存前不会创建正式工单，也不会自动派工或确定责任。
    </p>

    <div class="form-grid">
      <label>
        问题类别
        <select v-model="analysisForm.category">
          <option value="safety">安全问题</option>
          <option value="quality">质量问题</option>
          <option value="management">管理问题</option>
          <option value="logistics">后勤问题</option>
        </select>
      </label>
      <label>
        风险等级
        <select v-model="analysisForm.riskLevel">
          <option value="undetermined">待判断</option>
          <option value="low">低</option>
          <option value="medium">中</option>
          <option value="high">高</option>
          <option value="emergency">紧急</option>
        </select>
      </label>
      <label>
        问题类型
        <input v-model.trim="analysisForm.issueType" maxlength="100" />
      </label>
      <label class="full-field">
        已观察问题摘要
        <textarea v-model.trim="analysisForm.summary" maxlength="500" rows="3"></textarea>
      </label>
    </div>
    <button class="primary-button" :disabled="previewing" @click="createPreview">
      {{ previewing ? "正在生成工单…" : "生成工单" }}
    </button>
    <p v-if="actionError" class="error-message" role="alert">{{ actionError }}</p>
  </section>
  </section>

  <section v-if="!isDetail && proposal && editedFields" class="proposal-card" aria-labelledby="suggestion-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">第 2 步 · 等待人工确认</p>
        <h2 id="suggestion-title">核对工单草稿</h2>
      </div>
      <span class="warning-chip">尚未保存</span>
    </div>

    <div class="analysis-strip">
      <div><span>类别</span><strong>{{ categoryNames[proposal.analysis.category] }}</strong></div>
      <div><span>风险</span><strong>{{ riskNames[proposal.analysis.risk_level] }}</strong></div>
      <div><span>处理建议</span><strong>{{ routeNames[proposal.analysis.recommended_route] }}</strong></div>
      <div><span>人工复核</span><strong>{{ proposal.analysis.requires_human_review ? "需要" : "否" }}</strong></div>
    </div>
    <p class="locked-note">以上分析字段已锁定。用户只能补充记录展示字段，不能降低风险或取消人工复核。</p>

    <div class="form-grid review-form">
      <label>
        记录标题
        <input v-model.trim="editedFields.record_title" maxlength="100" />
      </label>
      <label>
        项目
        <input v-model.trim="editedFields.project" maxlength="100" placeholder="待补充" />
      </label>
      <label>
        区域
        <input v-model.trim="editedFields.area" maxlength="200" placeholder="待补充" />
      </label>
      <label class="full-field">
        问题描述
        <textarea v-model.trim="editedFields.record_description" maxlength="1000" rows="4"></textarea>
      </label>
      <label class="full-field">
        补充说明
        <textarea v-model.trim="editedFields.reporter_note" maxlength="500" rows="3" placeholder="可选"></textarea>
      </label>
    </div>

    <div class="diff-panel">
      <h3>确认前后差异</h3>
      <p v-if="liveChanges.length === 0" class="muted">当前没有修改，将按原提案确认。</p>
      <div v-else class="diff-table" role="table" aria-label="提案修改差异">
        <div class="diff-row diff-head" role="row">
          <strong>字段</strong><strong>修改前</strong><strong>修改后</strong>
        </div>
        <div v-for="change in liveChanges" :key="change.field" class="diff-row" role="row">
          <strong>{{ fieldLabels[change.field] }}</strong>
          <span>{{ displayValue(change.before) }}</span>
          <span>{{ displayValue(change.after) }}</span>
        </div>
      </div>
    </div>

    <button class="primary-button confirm-button" :disabled="confirming" @click="confirmProposal">
      {{ confirming ? "正在确认…" : "确认工单内容" }}
    </button>
  </section>

  <section v-if="!isDetail && confirmed && !record" class="confirmation-card" aria-live="polite">
    <strong>第 3 步 · 工单草稿已确认</strong>
    <p>信息已确认，尚未保存。点击下方按钮保存为正式工单。</p>
    <button class="primary-button" :disabled="saving" @click="saveDraft">
      {{ saving ? "正在保存，请勿重复点击…" : "保存为正式工单" }}
    </button>
  </section>

  <section v-if="record" class="workflow-card" aria-labelledby="workflow-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">已保存工单</p>
        <h2 id="workflow-title">{{ record.record_id }}</h2>
      </div>
      <span :class="record.disposition === 'active' ? 'safe-chip' : 'warning-chip'">
        {{ record.disposition === "active" ? statusLabels[record.status] : "已取消" }}
      </span>
    </div>

    <h3>{{ record.review_fields.record_title }}</h3>
    <p class="section-note">项目：{{ record.review_fields.project || '待补充' }} · 区域：{{ record.review_fields.area || '待补充' }}</p>
    <p class="record-description">{{ record.review_fields.record_description }}</p>
    <p v-if="record.review_fields.reporter_note">补充说明：{{ record.review_fields.reporter_note }}</p>
    <p class="section-note">更新：{{ new Date(record.updated_at).toLocaleString() }}</p>
    <div class="record-toolbar"><a class="primary-button" :href="api.issueRecordWordUrl(record.record_id)" download>生成 Word 文件</a></div>
    <div class="record-summary-grid">
      <div><span>工单编号</span><strong>{{ record.record_id }}</strong></div>
      <div><span>生成时间</span><strong>{{ new Date(record.created_at).toLocaleString() }}</strong></div>
      <div><span>问题类别</span><strong>{{ categoryNames[record.analysis.category] }}</strong></div>
      <div><span>风险等级</span><strong>{{ riskNames[record.analysis.risk_level] }}</strong></div>
      <div><span>人工复核</span><strong>{{ record.analysis.requires_human_review ? "需要" : "不需要" }}</strong></div>
      <div><span>AI 简要建议</span><strong>{{ record.analysis.suggested_actions.join("；") || "待补充" }}</strong></div>
    </div>
    <details class="analysis-detail"><summary>查看 AI 分析详情</summary>
      <p>类别：{{ categoryNames[record.analysis.category] }} · 处理建议：{{ routeNames[record.analysis.recommended_route] }}</p>
      <p>{{ record.analysis.summary }}</p>
      <p>已述事实：{{ record.analysis.observed_facts.join('；') || '无' }}</p>
      <p>不确定性：{{ record.analysis.uncertainties.join('；') || '仍需现场复核' }}</p>
      <p>缺失字段：{{ record.analysis.missing_fields.join('；') || '无额外追问' }}</p>
      <p v-for="action in record.analysis.suggested_actions" :key="action">建议：{{ action }}</p>
    </details>
    <p v-for="action in record.analysis.immediate_actions" :key="action" class="error-message">{{ action }}</p>
    <p class="locked-note">本机版尚未核验操作人员身份和资质，仅供内部试用。高风险必须独立专业复查。</p>

    <div class="record-summary-grid">
      <div><span>责任角色建议</span><strong>{{ roleLabels[record.suggested_responsible_role] }}</strong></div>
      <div><span>人工指派角色</span><strong>{{ record.assigned_role ? roleLabels[record.assigned_role] : "尚未指派" }}</strong></div>
      <div><span>整改安排</span><strong>{{ record.assigned_to ? "已指派" : "尚未指派" }}</strong></div>
      <div><span>风险</span><strong>{{ riskNames[record.analysis.risk_level] }}</strong></div>
    </div>
    <p class="locked-note">责任角色建议只供协调员参考；系统不会根据建议自动归责或自动派工。</p>

    <div v-if="record.disposition === 'active' && record.status !== 'closed'" class="workflow-actions">
      <label>
        本次动作说明
        <textarea v-model.trim="actionNote" maxlength="2000" rows="3" placeholder="补充信息、整改说明、复查结论或取消原因"></textarea>
      </label>

      <div v-if="record.status === 'submitted'" class="assignment-row">
        <label>
          人工选择责任角色
          <select v-model="selectedRole">
            <option v-for="(label, value) in roleLabels" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
      </div>

      <div class="button-row">
        <button
          v-if="record.status === 'draft' && !record.information_request"
          class="primary-button"
          :disabled="advancing"
          @click="advance('submit', record.reporter_id, 'reporter')"
        >提交记录</button>
        <button
          v-if="record.status === 'draft' && record.information_request"
          class="primary-button"
          :disabled="advancing"
          @click="advance('supplement_information', record.reporter_id, 'reporter', { note: true })"
        >补充并重新提交</button>
        <button
          v-if="record.status === 'submitted'"
          class="secondary-button"
          :disabled="advancing"
          @click="advance('request_more_info', 'coordinator-demo', 'coordinator', { note: true })"
        >要求补充信息</button>
        <button
          v-if="record.status === 'submitted'"
          class="primary-button"
          :disabled="advancing"
          @click="advance('assign', 'coordinator-demo', 'coordinator', { assign: true })"
        >人工确认并派工</button>
        <button
          v-if="record.status === 'assigned'"
          class="primary-button"
          :disabled="advancing"
          @click="advance('start_rectification', record.assigned_to!, 'rectifier')"
        >开始整改</button>
        <button
          v-if="record.status === 'rectifying'"
          class="primary-button"
          :disabled="advancing"
          @click="advance('submit_rectification', record.assigned_to!, 'rectifier', { note: true })"
        >提交整改说明</button>
        <button
          v-if="record.status === 'pending_review'"
          class="secondary-button"
          :disabled="advancing"
          @click="advance('reject_review', 'reviewer-demo', 'reviewer', { note: true })"
        >驳回并重新整改</button>
        <button
          v-if="record.status === 'pending_review'"
          class="primary-button"
          :disabled="advancing"
          @click="closeRecord"
        >复查确认关闭</button>
        <button class="danger-button" :disabled="advancing" @click="cancelRecord">取消记录</button>
      </div>
      <p v-if="record.information_request" class="info-callout">待补充：{{ record.information_request }}</p>
    </div>

    <div v-if="record.status === 'closed'" class="success-callout">复查已完成，记录关闭。{{ record.review_note }}</div>
    <div v-if="record.disposition === 'cancelled'" class="info-callout">
      记录已终止，不能继续推进。原因：{{ record.cancellation_reason }}
    </div>

    <div class="timeline" aria-label="状态变化轨迹">
      <h3>完整状态轨迹</h3>
      <ol>
        <li v-for="event in record.events" :key="event.sequence">
          <strong>{{ actionNames[event.action] }}</strong>
          <span>{{ event.from_status ? statusLabels[event.from_status] : "新建" }} → {{ statusLabels[event.to_status] }}</span>
          <small>{{ event.note || event.summary }} · {{ actorNames[event.actor_role] }} · {{ new Date(event.occurred_at).toLocaleString() }}</small>
        </li>
      </ol>
    </div>

    <div class="record-danger-zone">
      <div>
        <strong>删除工单</strong>
        <span>仅从本机删除这条记录，删除后无法恢复；与“取消工单”是不同操作。</span>
      </div>
      <button type="button" class="danger-button" :disabled="deleting || advancing" @click="deleteRecord">{{ deleting ? "正在删除…" : "删除工单" }}</button>
    </div>
  </section>
  </fieldset>
  </fieldset>

  <section v-if="isDetail || isSubmit" class="boundary">
    <h2>使用提醒</h2>
    <p>AI 建议仅供参考。保存、派工、整改与关闭均需人工操作；高风险必须独立专业复查。</p>
  </section>
</template>

<style scoped>
.workspace-fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.business-fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.record-toolbar { display: flex; gap: 10px; margin-bottom: 18px; }
.direct-submit { margin-top: 18px; }
.record-description { white-space: pre-wrap; line-height: 1.7; }
.analysis-detail { padding: 16px; background: #f5f8fc; border-radius: 12px; overflow-wrap: anywhere; }
summary { cursor: pointer; font-weight: 700; }
.workflow-card { overflow-wrap: anywhere; }
.record-danger-zone { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 22px; padding: 14px 16px; border: 1px solid #e6c9c5; border-radius: 12px; background: #fdf6f5; }
.record-danger-zone strong { display: block; font-size: 14px; }
.record-danger-zone span { display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }
@media (max-width: 600px) { .section-heading { flex-wrap: wrap; } }
</style>
