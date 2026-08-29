import type {
  ConfirmedIssueProposal,
  CreateIssueRecordResponse,
  IssueAnalysis,
  IssueRecord,
  IssueProposalPreviewData,
  IssueRecordProposal,
  IssueRecordReviewFields,
  RuntimeInfo,
  ToolResult,
  WorkflowActor,
  WorkflowTransitionInput,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string | { error_code?: string; message?: string };
    } | null;
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    const code = typeof detail === "object" ? detail?.error_code : undefined;
    throw new Error(message ? `${message}${code ? `（${code}）` : ""}` : `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getRuntime() {
    return request<RuntimeInfo>("/api/runtime");
  },
  previewIssueProposal(invocationId: string, analysis: IssueAnalysis) {
    return request<ToolResult<IssueProposalPreviewData>>(
      "/api/issue-proposals/preview",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invocation_id: invocationId, analysis }),
      },
    );
  },
  confirmIssueProposal(
    proposal: IssueRecordProposal,
    proposalToken: string,
    editedFields: IssueRecordReviewFields,
  ) {
    return request<ConfirmedIssueProposal>("/api/issue-proposals/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proposal,
        proposal_token: proposalToken,
        edited_fields: editedFields,
        confirmed: true,
      }),
    });
  },
  createIssueRecord(
    confirmation: ConfirmedIssueProposal,
    idempotencyKey: string,
    actor: WorkflowActor,
  ) {
    return request<CreateIssueRecordResponse>("/api/issue-records", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirmation,
        idempotency_key: idempotencyKey,
        actor,
      }),
    });
  },
  transitionIssueRecord(recordId: string, input: WorkflowTransitionInput) {
    return request<IssueRecord>(`/api/issue-records/${recordId}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  getIssueRecord(recordId: string) {
    return request<IssueRecord>(`/api/issue-records/${recordId}`);
  },
};
