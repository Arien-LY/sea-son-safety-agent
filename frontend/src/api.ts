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
  KnowledgeAnswer,
  KnowledgeJurisdiction,
  PhotoMetadata,
  PhotoAnalysisRecord,
  LinkedPhoto,
  VisionRuntime,
  TextTurnRequest,
  TextTurnResponse,
  RecordPage,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const controller = timeoutMs ? new AbortController() : null;
  const timeout = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller?.signal ?? init?.signal });
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
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw new Error("分析等待超过 35 秒，已停止等待；可以直接重试，不会自动重复提交。");
    }
    throw cause;
  } finally {
    if (timeout !== null) window.clearTimeout(timeout);
  }
}

export const api = {
  getTextRuntime() { return request<VisionRuntime>("/api/text/runtime"); },
  sendText(input: TextTurnRequest) {
    return request<TextTurnResponse>("/api/text-consultations", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
    }, 35_000);
  },
  proposeText(consultationId: string, turn: number) {
    return request<ToolResult<IssueProposalPreviewData>>(`/api/text-consultations/${encodeURIComponent(consultationId)}/proposal`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_turn: turn, confirmed: true }),
    });
  },
  listRecords(query: URLSearchParams) { return request<RecordPage>(`/api/issue-records?${query}`); },
  getVisionRuntime() { return request<VisionRuntime>("/api/vision/runtime"); },
  uploadPhoto(file: File) {
    return request<PhotoMetadata>("/api/photos", {
      method: "POST", headers: { "Content-Type": file.type, "X-Upload-Authorized": "true" }, body: file,
    });
  },
  photoContentUrl(photoId: string) { return `${API_BASE}/api/photos/${encodeURIComponent(photoId)}/content`; },
  analyzePhoto(photoId: string, context: string, allowExternal: boolean) {
    return request<PhotoAnalysisRecord>(`/api/photos/${encodeURIComponent(photoId)}/analysis`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context, allow_external: allowExternal }),
    });
  },
  decidePhotoCandidate(analysisId: string, candidateId: string, decision: "accept" | "reject", correctedSummary: string, note: string) {
    return request<ToolResult<IssueProposalPreviewData>>(`/api/photo-analyses/${encodeURIComponent(analysisId)}/decisions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId, decision, corrected_summary: correctedSummary, note, confirmed: true }),
    });
  },
  linkPhoto(record: IssueRecord, photoId: string, stage: "before" | "after") {
    return request(`/api/issue-records/${encodeURIComponent(record.record_id)}/photos`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_id: photoId, stage, expected_revision: record.revision, confirmed: true,
        actor: stage === "before" ? { actor_id: record.reporter_id, role: "reporter" }
          : { actor_id: record.assigned_to, role: "rectifier" },
      }),
    });
  },
  getRecordPhotos(recordId: string) { return request<LinkedPhoto[]>(`/api/issue-records/${encodeURIComponent(recordId)}/photos`); },
  getKnowledgeAnswer(query: string, jurisdiction: KnowledgeJurisdiction, analysis: IssueAnalysis, recordId?: string) {
    return request<KnowledgeAnswer>(
      recordId ? `/api/issue-records/${encodeURIComponent(recordId)}/knowledge` : "/api/knowledge/answer",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(recordId ? { query, jurisdiction } : { query, jurisdiction, analysis }),
      },
    );
  },
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
