<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api";
import KnowledgePanel from "../components/KnowledgePanel.vue";
import type {
  ActorRole,
  ConfirmedIssueProposal,
  IssueAnalysis,
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
const runtimeError = ref("");
const actionError = ref("");
const previewing = ref(false);
const confirming = ref(false);
const saving = ref(false);
const advancing = ref(false);
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

onMounted(async () => {
  try {
    runtime.value = await api.getRuntime();
  } catch {
    runtimeError.value = "后端尚未启动";
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

async function createPreview() {
  previewing.value = true;
  actionError.value = "";
  confirmed.value = null;
  record.value = null;
  try {
    const result = await api.previewIssueProposal(uniqueId("preview"), buildAnalysis());
    if (!result.ok) {
      throw new Error(`${result.summary}（${result.error_code || "unknown_error"}）`);
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
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : "无法确认提案";
  } finally {
    confirming.value = false;
  }
}

async function saveDraft() {
  if (!confirmed.value) return;
  saving.value = true;
  actionError.value = "";
  try {
    const result = await api.createIssueRecord(
      confirmed.value,
      uniqueId("create"),
      { actor_id: "reporter-demo", role: "reporter" },
    );
    record.value = result.record;
    selectedRole.value = result.record.suggested_responsible_role;
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
    return advance("cancel", "reporter-demo", "reporter", { note: true });
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
  <section class="hero proposal-hero">
    <div>
      <p class="eyebrow">施工现场问题闭环</p>
      <h1>由人确认提案，由代码推进整改</h1>
      <p class="lead">
        Phase 4 增加只读知识依据；建议、来源和人工结论分开展示，既有整改状态仍由确定性代码推进。
      </p>
    </div>
    <div class="runtime-card">
      <span class="status-dot" :class="{ online: runtime }"></span>
      <div v-if="runtime">
        <strong>底座已连接</strong>
        <p>{{ runtime.tutorial_baseline }} · {{ runtime.framework }} {{ runtime.framework_version }}</p>
        <small>运行模式：{{ runtime.agent_mode }}</small>
      </div>
      <div v-else>
        <strong>{{ runtimeError || "正在检查后端" }}</strong>
        <p>启动 FastAPI 后可进行工作流验收。</p>
      </div>
    </div>
  </section>

  <section class="proposal-workbench" aria-labelledby="proposal-workbench-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">确定性验收入口</p>
        <h2 id="proposal-workbench-title">已校验问题分析</h2>
      </div>
      <span class="safe-chip">无真实模型 · 无自动归责</span>
    </div>
    <p class="section-note">
      使用结构化本地验收输入验证四类问题共用生命周期与知识检索；这里不是自然语言模型入口。
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
      {{ previewing ? "正在生成…" : "生成建议创建记录" }}
    </button>
    <p v-if="actionError" class="error-message" role="alert">{{ actionError }}</p>
  </section>

  <section v-if="proposal && editedFields" class="proposal-card" aria-labelledby="suggestion-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">等待用户确认</p>
        <h2 id="suggestion-title">建议创建记录</h2>
      </div>
      <span class="warning-chip">尚未保存</span>
    </div>

    <div class="analysis-strip">
      <div><span>类别</span><strong>{{ proposal.analysis.category }}</strong></div>
      <div><span>风险</span><strong>{{ proposal.analysis.risk_level }}</strong></div>
      <div><span>路由</span><strong>{{ proposal.analysis.recommended_route }}</strong></div>
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
      {{ confirming ? "正在确认…" : "确认提案" }}
    </button>
  </section>

  <section v-if="confirmed && !record" class="confirmation-card" aria-live="polite">
    <strong>提案已由用户确认</strong>
    <p>完整性凭据已生成，但尚未保存正式记录。</p>
    <button class="primary-button" :disabled="saving" @click="saveDraft">
      {{ saving ? "正在保存…" : "保存为正式草稿" }}
    </button>
  </section>

  <section v-if="record" class="workflow-card" aria-labelledby="workflow-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">本地持久化记录 · revision {{ record.revision }}</p>
        <h2 id="workflow-title">{{ record.record_id }}</h2>
      </div>
      <span :class="record.disposition === 'active' ? 'safe-chip' : 'warning-chip'">
        {{ record.disposition === "active" ? statusLabels[record.status] : "已取消" }}
      </span>
    </div>

    <div class="record-summary-grid">
      <div><span>责任角色建议</span><strong>{{ roleLabels[record.suggested_responsible_role] }}</strong></div>
      <div><span>人工指派角色</span><strong>{{ record.assigned_role ? roleLabels[record.assigned_role] : "尚未指派" }}</strong></div>
      <div><span>整改人</span><strong>{{ record.assigned_to || "尚未指派" }}</strong></div>
      <div><span>风险</span><strong>{{ record.analysis.risk_level }}</strong></div>
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
          @click="advance('submit', 'reporter-demo', 'reporter')"
        >提交记录</button>
        <button
          v-if="record.status === 'draft' && record.information_request"
          class="primary-button"
          :disabled="advancing"
          @click="advance('supplement_information', 'reporter-demo', 'reporter', { note: true })"
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
          @click="advance('start_rectification', 'rectifier-demo', 'rectifier')"
        >开始整改</button>
        <button
          v-if="record.status === 'rectifying'"
          class="primary-button"
          :disabled="advancing"
          @click="advance('submit_rectification', 'rectifier-demo', 'rectifier', { note: true })"
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
          <strong>#{{ event.sequence }} · {{ event.action }}</strong>
          <span>{{ event.from_status || "无" }} → {{ event.to_status }}</span>
          <small>{{ event.note || event.summary }} · {{ event.actor_id }} / {{ event.actor_role }}</small>
        </li>
      </ol>
    </div>
  </section>

  <KnowledgePanel :analysis="record?.analysis || buildAnalysis()" :record="record" />

  <section class="boundary">
    <h2>当前能力边界</h2>
    <p>记录保存在本地 JSON Store，知识使用小规模本地关键词检索，不含向量库、登录鉴权、外部派单、通知、图片或真实模型调用；演示角色标识不代表生产身份。</p>
  </section>
</template>
