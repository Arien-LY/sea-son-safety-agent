export interface RuntimeInfo {
  agent_mode: "mock" | "real";
  framework: string;
  framework_version: string;
  tutorial_baseline: string;
}

export interface TextTurnRequest {
  request_id: string;
  intent: "chat" | "consult" | "auto";
  thinking_mode?: "fast" | "deep";
  tools_enabled?: boolean;
  model: string | null;
  input: { message: string; project: string | null; area: string | null; requester_role: string | null };
  consultation_id: string | null;
  expected_turn: number;
  allow_external: boolean;
  photo_id?: string | null;
  allow_image_external?: boolean;
}

export interface TextTurnResponse {
  photo_id?: string | null;
  consultation_id: string;
  turn: number;
  mode: "mock" | "real";
  model: string;
  reply: { answer: string; follow_up_questions: string[]; analysis: IssueAnalysis };
  can_propose: boolean;
  risk_retained: boolean;
  remaining_turns: number;
  context_trimmed?: boolean;
  analysis_status?: "validated" | "unavailable" | "not_requested";
  ticket_decision?: TicketDecision | null;
  rejudge_available?: boolean;
  analysis_retry_used?: boolean;
  sources?: { id: string; title: string; url: string; excerpt: string }[];
  tool_results?: { tool: string; ok: boolean; summary: string }[];
}

export interface ChatSessionItem { pinned: boolean; consultation_id: string; title: string; turns: number; intent: string }
export interface ChatSession { consultation_id: string; proposed: boolean; turns: { request_id: string; message: string; result: TextTurnResponse; thinking: "fast" | "deep" }[] }

export interface RecordListItem {
  record_id: string;
  title: string;
  project: string | null;
  area: string | null;
  category: IssueCategory;
  risk_level: RiskLevel;
  status: WorkflowStatus;
  disposition: RecordDisposition;
  revision: number;
  updated_at: string;
}

export interface RecordPage { total: number; offset: number; limit: number; items: RecordListItem[] }

export interface PhotoMetadata {
  photo_id: string;
  content_digest: string;
  byte_size: number;
  width: number;
  height: number;
  metadata_removed: true;
  created_at: string;
}

export interface VisualCandidate {
  candidate_id: string;
  observation_ids: string[];
  analysis: IssueAnalysis;
}

export interface PhotoAnalysisRecord {
  analysis_id: string;
  photo_id: string;
  mode: "mock" | "real";
  model: string;
  result: {
    preliminary_only: true;
    requires_human_review: true;
    observations: { observation_id: string; status: "observed" | "uncertain" | "not_observed"; description: string }[];
    limitations: string[];
    follow_up_questions: string[];
    candidates: VisualCandidate[];
  };
}

export interface LinkedPhoto {
  photo: PhotoMetadata;
  link: { record_id: string; photo_id: string; stage: "before" | "after"; record_revision: number; created_at: string };
}

export interface VisionRuntime {
  mode: "mock" | "real";
  model: string;
  configured: boolean;
  external_provider: string | null;
  available_models?: string[];
  custom_model_allowed?: boolean;
  image_configured?: boolean;
  image_model?: string;
  web_tools?: { search_configured: boolean; search_provider: string; read_webpage: boolean; current_time: boolean };
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

export type TicketStatus = "no_ticket" | "need_more_info" | "create_ticket";

export interface TicketDecision {
  status: TicketStatus;
  category: IssueCategory;
  issue_type: string;
  summary: string;
  risk_level: RiskLevel;
  requires_human_review: boolean;
  missing_information: string[];
  immediate_action: string | null;
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
export interface TextProgress {
  type: "progress";
  seq: number;
  elapsed_ms: number;
  stage: "queued" | "preparing" | "model_running" | "validating" | "tool_running" | "tool_completed" | "responding" | "completed";
  tool: "propose_issue_record" | "web_search" | "read_webpage" | "current_time" | "search_knowledge" | "calculate" | null;
}

export interface TextContentDelta {
  type: "content_delta";
  index: number;
  text: string;
}
