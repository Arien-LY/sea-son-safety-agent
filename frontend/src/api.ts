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
  TextProgress,
  TextContentDelta,
  ChatSession, ChatSessionItem,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit, timeoutMs?: number,
  read?: (response: Response) => Promise<T>): Promise<T> {
  const controller = timeoutMs ? new AbortController() : null;
  const abortFromCaller = () => controller?.abort(init?.signal?.reason);
  if (controller && init?.signal) {
    if (init.signal.aborted) abortFromCaller();
    else init.signal.addEventListener("abort", abortFromCaller, { once: true });
  }
  const timeout = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller?.signal ?? init?.signal });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {
        detail?: string | { error_code?: string; message?: string };
      } | null;
      const detail = payload?.detail;
      const message = typeof detail === "string" ? detail : detail?.message;
      throw new Error(message || "操作暂未成功，请稍后重试。");
    }
    return read ? await read(response) : await response.json() as T;
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      if (init?.signal?.aborted) throw new Error("请求已取消。");
      throw new Error(`等待超过 ${Math.ceil((timeoutMs || 35_000) / 1000)} 秒，已停止等待。服务端可能仍在处理，请稍后手动重试；不会自动重复提交。`);
    }
    throw cause;
  } finally {
    if (timeout !== null) window.clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", abortFromCaller);
  }
}

async function readEvents<T>(response: Response, onProgress: (event: TextProgress) => void,
  onDelta?: (event: TextContentDelta) => void): Promise<T> {
  const invalid = () => new Error("执行状态连接中断或格式无效，请稍后手动重试；未自动重发请求。");
  if (!response.headers.get("content-type")?.includes("application/x-ndjson") || !response.body) throw invalid();
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const stages = ["queued", "preparing", "model_running", "validating", "tool_running", "tool_completed", "responding", "completed"];
  let buffer = "", total = 0, count = 0, sequence = 0, elapsed = 0;
  let deltaIndex = 0, deltaChars = 0;
  let result: T | undefined, receivedResult = false, streamDone = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      streamDone = done;
      buffer += decoder.decode(value, { stream: !done });
      total += value?.byteLength || 0;
      if (total > 8388608) throw invalid();
      let newline;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (!line) continue;
        if (receivedResult) throw invalid();
        if (++count > 64032) throw invalid();
        let event;
        try { event = JSON.parse(line); } catch { throw invalid(); }
        if (!event || typeof event !== "object" || Array.isArray(event)) throw invalid();
        if (event.type === "progress") {
          if (Object.keys(event).sort().join() !== "elapsed_ms,seq,stage,tool,type"
            || !Number.isInteger(event.seq) || event.seq !== sequence + 1
            || !Number.isInteger(event.elapsed_ms) || event.elapsed_ms < elapsed
            || !stages.includes(event.stage)
            || (["tool_running", "tool_completed"].includes(event.stage)
              ? !["propose_issue_record", "web_search", "read_webpage", "current_time", "search_knowledge", "calculate"].includes(event.tool)
              : event.tool !== null)) throw invalid();
          sequence = event.seq; elapsed = event.elapsed_ms;
          onProgress(event as TextProgress);
        } else if (event.type === "content_delta" && onDelta
          && Object.keys(event).sort().join() === "index,text,type"
          && Number.isInteger(event.index) && event.index === deltaIndex + 1
          && typeof event.text === "string" && event.text.length >= 1 && [...event.text].length <= 1000) {
          deltaIndex = event.index; deltaChars += [...event.text].length;
          if (deltaChars > 64000) throw invalid();
          onDelta(event as TextContentDelta);
        } else if (event.type === "result" && event.data && typeof event.data === "object" && !Array.isArray(event.data)) {
          result = event.data as T; receivedResult = true;
        } else if (event.type === "error" && typeof event.message === "string"
          && event.message.length <= 500 && /^[a-z_]{1,64}$/.test(event.error_code)) {
          throw new Error(event.message);
        } else throw invalid();
      }
      if (done) {
        if (receivedResult && !buffer.trim()) return result as T;
        throw invalid();
      }
    }
  } finally {
    if (!streamDone) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export const api = {
  listChatSessions() { return request<ChatSessionItem[]>("/api/chat-sessions", undefined, 5_000); },
  pinChatSession(id: string, pinned: boolean) { return request<{ consultation_id: string; pinned: boolean }>(
    '/api/chat-sessions/' + encodeURIComponent(id), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pinned }) }, 5_000); },
  deleteChatSession(id: string) { return request<{ deleted: boolean }>(
    '/api/chat-sessions/' + encodeURIComponent(id), { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed: true }) }, 5_000); },
  getChatSession(id: string) { return request<ChatSession>(`/api/chat-sessions/${encodeURIComponent(id)}`, undefined, 5_000); },
  getTextRuntime() { return request<VisionRuntime>("/api/text/runtime", undefined, 5_000); },
  sendText(input: TextTurnRequest, signal?: AbortSignal, onProgress?: (event: TextProgress) => void,
    onDelta?: (event: TextContentDelta) => void) {
    return request<TextTurnResponse>(`/api/text-consultations${onProgress ? "/stream" : ""}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input), signal,
    }, input.intent === "chat" || input.intent === "auto" ? 190_000 : 35_000,
    onProgress ? response => readEvents(response, onProgress, onDelta) : undefined);
  },
  proposeText(consultationId: string, turn: number, onProgress?: (event: TextProgress) => void) {
    return request<ToolResult<IssueProposalPreviewData>>(`/api/text-consultations/${encodeURIComponent(consultationId)}/proposal${onProgress ? "/stream" : ""}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_turn: turn, confirmed: true }),
    }, 35_000, onProgress ? response => readEvents(response, onProgress) : undefined);
  },
  rejudgeText(consultationId: string, turn: number, onProgress?: (event: TextProgress) => void) {
    return request<TextTurnResponse>(`/api/text-consultations/${encodeURIComponent(consultationId)}/ticket-decision${onProgress ? "/stream" : ""}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_turn: turn, confirmed: true }),
    }, 190_000, onProgress ? response => readEvents(response, onProgress) : undefined);
  },
  issueRecordWordUrl(recordId: string) { return `${API_BASE}/api/issue-records/${encodeURIComponent(recordId)}/export.docx`; },
  listRecords(query: URLSearchParams) { return request<RecordPage>(`/api/issue-records?${query}`); },
  getVisionRuntime() { return request<VisionRuntime>("/api/vision/runtime"); },
  uploadPhoto(file: File, signal?: AbortSignal) {
    return request<PhotoMetadata>("/api/photos", {
      method: "POST", headers: { "Content-Type": file.type, "X-Upload-Authorized": "true" }, body: file, signal,
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
  deleteIssueRecord(recordId: string) {
    return request<{ deleted: boolean; record_id: string }>(
      `/api/issue-records/${encodeURIComponent(recordId)}`, { method: "DELETE" });
  },
};
