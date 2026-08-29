<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api";
import type {
  ConfirmedIssueProposal,
  IssueAnalysis,
  IssueRecordProposal,
  IssueRecordReviewFields,
  ProposalFieldChange,
  RiskLevel,
  RuntimeInfo,
} from "../types";

const runtime = ref<RuntimeInfo | null>(null);
const runtimeError = ref("");
const actionError = ref("");
const previewing = ref(false);
const confirming = ref(false);
const proposal = ref<IssueRecordProposal | null>(null);
const proposalToken = ref("");
const editedFields = ref<IssueRecordReviewFields | null>(null);
const confirmed = ref<ConfirmedIssueProposal | null>(null);

const analysisForm = reactive({
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

const liveChanges = computed<ProposalFieldChange[]>(() => {
  if (!proposal.value || !editedFields.value) return [];
  const before = proposal.value.review_fields;
  const after = editedFields.value;
  return (Object.keys(fieldLabels) as Array<keyof IssueRecordReviewFields>)
    .filter((field) => before[field] !== after[field])
    .map((field) => ({ field, before: before[field], after: after[field] }));
});

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
    category: "safety",
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

function invocationId(): string {
  return globalThis.crypto?.randomUUID?.() || `preview-${Date.now()}`;
}

async function createPreview() {
  previewing.value = true;
  actionError.value = "";
  confirmed.value = null;
  try {
    const result = await api.previewIssueProposal(invocationId(), buildAnalysis());
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

function displayValue(value: string | null): string {
  return value || "（未填写）";
}
</script>

<template>
  <section class="hero proposal-hero">
    <div>
      <p class="eyebrow">施工现场问题闭环</p>
      <h1>先生成建议，再由人补充和确认</h1>
      <p class="lead">
        当前 Phase 2 只生成问题记录提案。确认前后均不会保存正式记录、派单或改变整改状态。
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
        <p>启动 FastAPI 后可进行提案验收。</p>
      </div>
    </div>
  </section>

  <section class="proposal-workbench" aria-labelledby="proposal-workbench-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">确定性验收入口</p>
        <h2 id="proposal-workbench-title">已校验问题分析</h2>
      </div>
      <span class="safe-chip">不落库 · 不派单</span>
    </div>
    <p class="section-note">
      本阶段尚未接入真实模型。这里用明确标注的结构化输入验证提案、补充、差异和确认边界。
    </p>

    <div class="form-grid">
      <label>
        问题类型
        <input v-model.trim="analysisForm.issueType" maxlength="100" />
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
    <p class="locked-note">以上分析字段已锁定。用户只能补充下面的记录展示字段，不能降低风险或取消人工复核。</p>

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
      {{ confirming ? "正在确认…" : "确认提案（仍不落库）" }}
    </button>
  </section>

  <section v-if="confirmed" class="confirmation-card" aria-live="polite">
    <strong>提案已由用户确认</strong>
    <p>状态：confirmed_pending_persistence。共记录 {{ confirmed.changes.length }} 项修改。</p>
    <small>persisted=false · dispatched=false · 正式记录与派单将在后续受控工作流中处理。</small>
  </section>

  <section class="boundary">
    <h2>当前能力边界</h2>
    <p>页面只完成提案预览、用户补充、差异和确认；没有正式问题记录、数据库、派单或整改状态。</p>
  </section>
</template>
