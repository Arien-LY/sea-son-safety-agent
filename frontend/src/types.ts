export interface RuntimeInfo {
  agent_mode: "mock" | "real";
  framework: string;
  framework_version: string;
  tutorial_baseline: string;
}

export type KnowledgeJurisdiction = "unknown" | "cn_mainland" | "overseas";

export interface KnowledgeCitation {
  entry: {
    entry_id: string;
    locator: string;
    title: string;
    text: string;
    content_kind: "paraphrase";
    scope: string;
    reviewed_on: string;
    review_due_on: string;
  };
  source: {
    source_id: string;
    title: string;
    publisher: string;
    url: string;
    version: string;
    updated_on: string;
  };
  content_digest: string;
}

export interface KnowledgeAnswer {
  analysis: IssueAnalysis;
  model_suggestions: string[];
  suggestion_notice: string;
  retrieved_evidence: KnowledgeCitation[];
  evidence_notice: string;
  human_conclusion: {
    status: "not_reviewed" | "reviewed";
    record_id: string | null;
    revision: number | null;
    actor_id: string | null;
    actor_role: string | null;
    occurred_at: string | null;
    note: string | null;
  };
  knowledge_status: "matched" | "no_results" | "unavailable";
  knowledge_error_code: string | null;
}

export type IssueCategory =
  | "safety"
  | "quality"
  | "management"
  | "logistics"
  | "consultation"
  | "unknown";

export type RiskLevel = "undetermined" | "low" | "medium" | "high" | "emergency";
export type RecommendedRoute =
  | "direct_answer"
  | "collect_more_info"
  | "propose_workflow"
  | "human_review";

export interface IssueAnalysis {
  category: IssueCategory;
  issue_type: string;
  summary: string;
  observed_facts: string[];
  uncertainties: string[];
  missing_fields: string[];
  risk_level: RiskLevel;
  immediate_actions: string[];
  suggested_actions: string[];
  recommended_route: RecommendedRoute;
  requires_human_review: boolean;
  confidence: number;
}

export interface IssueRecordReviewFields {
  record_title: string;
  record_description: string;
  project: string | null;
  area: string | null;
  reporter_note: string | null;
}

export interface IssueRecordProposal {
  proposal_type: "issue_record";
  status: "awaiting_user_confirmation";
  analysis: IssueAnalysis;
  review_fields: IssueRecordReviewFields;
  requires_user_confirmation: true;
  persisted: false;
  dispatched: false;
}

export interface ToolResult<TData = Record<string, unknown>> {
  tool_name: string;
  ok: boolean;
  summary: string;
  data: TData;
  recoverable: boolean;
  error_code: string | null;
}

export interface IssueProposalPreviewData {
  proposal: IssueRecordProposal;
  proposal_token: string;
}

export interface ProposalFieldChange {
  field: keyof IssueRecordReviewFields;
  before: string | null;
  after: string | null;
}

export interface ConfirmedIssueProposal {
  status: "confirmed_pending_persistence";
  analysis: IssueAnalysis;
  review_fields: IssueRecordReviewFields;
  changes: ProposalFieldChange[];
  user_confirmed: true;
  persisted: false;
  dispatched: false;
  confirmation_token: string;
}

export type WorkflowStatus =
  | "draft"
  | "submitted"
  | "assigned"
  | "rectifying"
  | "pending_review"
  | "closed";

export type RecordDisposition = "active" | "cancelled";
export type ActorRole =
  | "reporter"
  | "coordinator"
  | "rectifier"
  | "reviewer"
  | "professional_reviewer";
export type ResponsibleRole =
  | "safety_officer"
  | "quality_inspector"
  | "site_manager"
  | "facilities_staff";
export type WorkflowAction =
  | "submit"
  | "request_more_info"
  | "supplement_information"
  | "assign"
  | "start_rectification"
  | "submit_rectification"
  | "reject_review"
  | "close"
  | "cancel";

export interface WorkflowActor {
  actor_id: string;
  role: ActorRole;
}

export interface WorkflowEvent {
  sequence: number;
  occurred_at: string;
  action: WorkflowAction | "create_draft";
  actor_id: string;
  actor_role: ActorRole;
  from_status: WorkflowStatus | null;
  to_status: WorkflowStatus;
  from_disposition: RecordDisposition | null;
  to_disposition: RecordDisposition;
  summary: string;
  note: string | null;
}

export interface IssueRecord {
  schema_version: "phase3-issue-record-v1";
  record_id: string;
  analysis: IssueAnalysis;
  review_fields: IssueRecordReviewFields;
  status: WorkflowStatus;
  disposition: RecordDisposition;
  revision: number;
  reporter_id: string;
  suggested_responsible_role: ResponsibleRole;
  assigned_to: string | null;
  assigned_role: ResponsibleRole | null;
  assignment_confirmed_by_human: boolean;
  information_request: string | null;
  rectification_note: string | null;
  review_note: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  events: WorkflowEvent[];
}

export interface CreateIssueRecordResponse {
  record: IssueRecord;
  created: boolean;
}

export interface WorkflowTransitionInput {
  action: WorkflowAction;
  actor: WorkflowActor;
  expected_revision: number;
  note?: string;
  assignee_id?: string;
  assignee_role?: ResponsibleRole;
}
