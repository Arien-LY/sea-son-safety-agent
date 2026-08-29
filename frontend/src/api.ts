import type {
  ConfirmedIssueProposal,
  IssueAnalysis,
  IssueProposalPreviewData,
  IssueRecordProposal,
  IssueRecordReviewFields,
  RuntimeInfo,
  ToolResult,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail || `请求失败：${response.status}`);
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
};
