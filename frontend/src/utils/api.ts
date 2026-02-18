/**
 * API helpers for the data endpoints.
 *
 * Fire-and-forget PUT helpers (legacy localStorage sync) and
 * typed request helpers for the codebook CRUD endpoints.
 */

import type {
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
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
// Transcript page helpers
// ---------------------------------------------------------------------------

export function getTranscript(sessionId: string): Promise<TranscriptPageResponse> {
  return apiGet<TranscriptPageResponse>(`/transcripts/${sessionId}`);
}
