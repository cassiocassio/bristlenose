/**
 * API helpers for the data endpoints.
 *
 * Fire-and-forget PUT helpers (legacy localStorage sync) and
 * typed request helpers for the codebook CRUD endpoints.
 */

import type {
  AutoCodeJobStatus,
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
  ProposalsListResponse,
  RemoveFrameworkInfo,
  CodebookAnalysisListResponse,
  TagAnalysisResponse,
  TemplateListResponse,
  TranscriptPageResponse,
} from "./types";

function apiBase(): string {
  return (
    (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE as string
  ) || "/api/projects/1";
}

// ---------------------------------------------------------------------------
// Generic request helpers
// ---------------------------------------------------------------------------

export async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`);
  if (!resp.ok) throw new Error(`GET ${path} ${resp.status}`);
  return resp.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`POST ${path} ${resp.status}`);
  return resp.json() as Promise<T>;
}

async function apiPatch(path: string, body: unknown): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`PATCH ${path} ${resp.status}`);
}

async function apiDelete(path: string): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`DELETE ${path} ${resp.status}`);
}

async function apiDeleteJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`DELETE ${path} ${resp.status}`);
  return resp.json() as Promise<T>;
}

function firePut(path: string, body: unknown): void {
  fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch((err) => {
    console.error(`PUT ${path} failed:`, err);
  });
}

// ---------------------------------------------------------------------------
// Fire-and-forget PUT helpers (legacy localStorage sync)
// ---------------------------------------------------------------------------

export function putHidden(data: Record<string, boolean>): void {
  firePut("/hidden", data);
}

export function putStarred(data: Record<string, boolean>): void {
  firePut("/starred", data);
}

export function putEdits(data: Record<string, string>): void {
  firePut("/edits", data);
}

export function putTags(data: Record<string, string[]>): void {
  firePut("/tags", data);
}

export function putDeletedBadges(data: Record<string, string[]>): void {
  firePut("/deleted-badges", data);
}

// ---------------------------------------------------------------------------
// Codebook CRUD helpers
// ---------------------------------------------------------------------------

export function getCodebook(): Promise<CodebookResponse> {
  return apiGet<CodebookResponse>("/codebook");
}

export function createCodebookGroup(
  name: string,
  colourSet?: string,
): Promise<CodebookGroupResponse> {
  return apiPost<CodebookGroupResponse>("/codebook/groups", {
    name,
    colour_set: colourSet ?? "ux",
  });
}

export function updateCodebookGroup(
  groupId: number,
  fields: { name?: string; subtitle?: string; colour_set?: string; order?: number },
): Promise<void> {
  return apiPatch(`/codebook/groups/${groupId}`, fields);
}

export function deleteCodebookGroup(groupId: number): Promise<void> {
  return apiDelete(`/codebook/groups/${groupId}`);
}

export function createCodebookTag(
  name: string,
  groupId: number,
): Promise<CodebookTagResponse> {
  return apiPost<CodebookTagResponse>("/codebook/tags", {
    name,
    group_id: groupId,
  });
}

export function updateCodebookTag(
  tagId: number,
  fields: { name?: string; group_id?: number },
): Promise<void> {
  return apiPatch(`/codebook/tags/${tagId}`, fields);
}

export function deleteCodebookTag(tagId: number): Promise<void> {
  return apiDelete(`/codebook/tags/${tagId}`);
}

export function mergeCodebookTags(
  sourceId: number,
  targetId: number,
): Promise<void> {
  return apiPost("/codebook/merge-tags", {
    source_id: sourceId,
    target_id: targetId,
  });
}

// ---------------------------------------------------------------------------
// Codebook template helpers
// ---------------------------------------------------------------------------

export function getCodebookTemplates(): Promise<TemplateListResponse> {
  return apiGet<TemplateListResponse>("/codebook/templates");
}

export function importCodebookTemplate(templateId: string): Promise<CodebookResponse> {
  return apiPost<CodebookResponse>("/codebook/import-template", {
    template_id: templateId,
  });
}

export function removeCodebookFramework(frameworkId: string): Promise<CodebookResponse> {
  return apiDeleteJson<CodebookResponse>(`/codebook/remove-framework/${frameworkId}`);
}

export function getRemoveFrameworkImpact(frameworkId: string): Promise<RemoveFrameworkInfo> {
  return apiGet<RemoveFrameworkInfo>(`/codebook/remove-framework/${frameworkId}/impact`);
}

// ---------------------------------------------------------------------------
// Transcript page helpers
// ---------------------------------------------------------------------------

export function getTranscript(sessionId: string): Promise<TranscriptPageResponse> {
  return apiGet<TranscriptPageResponse>(`/transcripts/${sessionId}`);
}

/** Lightweight session list for the transcript session selector. */
export interface SessionListSpeaker {
  speaker_code: string;
  name: string;
  role: string;
}

export interface SessionListItem {
  session_id: string;
  session_number: number;
  session_date: string | null;
  speakers: SessionListSpeaker[];
}

export async function getSessionList(): Promise<SessionListItem[]> {
  const data = await apiGet<{ sessions: SessionListItem[] }>("/sessions");
  return data.sessions;
}

// ---------------------------------------------------------------------------
// AutoCode helpers
// ---------------------------------------------------------------------------

export function startAutoCode(frameworkId: string): Promise<AutoCodeJobStatus> {
  return apiPost<AutoCodeJobStatus>(`/autocode/${frameworkId}`, {});
}

export function getAutoCodeStatus(frameworkId: string): Promise<AutoCodeJobStatus> {
  return apiGet<AutoCodeJobStatus>(`/autocode/${frameworkId}/status`);
}

export function cancelAutoCode(frameworkId: string): Promise<AutoCodeJobStatus> {
  return apiPost<AutoCodeJobStatus>(`/autocode/${frameworkId}/cancel`, {});
}

export function getAutoCodeProposals(
  frameworkId: string,
  minConfidence?: number,
): Promise<ProposalsListResponse> {
  const qs = minConfidence != null ? `?min_confidence=${minConfidence}` : "";
  return apiGet<ProposalsListResponse>(`/autocode/${frameworkId}/proposals${qs}`);
}

export function acceptProposal(proposalId: number): Promise<void> {
  return apiPost(`/autocode/proposals/${proposalId}/accept`, {});
}

export function denyProposal(proposalId: number): Promise<void> {
  return apiPost(`/autocode/proposals/${proposalId}/deny`, {});
}

export function acceptAllProposals(
  frameworkId: string,
  minConfidence?: number,
): Promise<{ accepted: number }> {
  return apiPost<{ accepted: number }>(`/autocode/${frameworkId}/accept-all`, {
    min_confidence: minConfidence ?? 0.5,
  });
}

export function denyAllProposals(
  frameworkId: string,
  maxConfidence?: number,
): Promise<{ denied: number }> {
  return apiPost<{ denied: number }>(`/autocode/${frameworkId}/deny-all`, {
    ...(maxConfidence != null ? { max_confidence: maxConfidence } : {}),
  });
}

// ---------------------------------------------------------------------------
// Tag-based analysis helpers
// ---------------------------------------------------------------------------

export function getTagAnalysis(groups?: string): Promise<TagAnalysisResponse> {
  const qs = groups ? `?groups=${groups}` : "";
  return apiGet<TagAnalysisResponse>(`/analysis/tags${qs}`);
}

export function getCodebookAnalysis(): Promise<CodebookAnalysisListResponse> {
  return apiGet<CodebookAnalysisListResponse>("/analysis/codebooks");
}
