export interface RuntimeInfo {
  agent_mode: "mock" | "real";
  framework: string;
  framework_version: string;
  tutorial_baseline: string;
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
}
