/**
 * API helpers for the data endpoints.
 *
 * Fire-and-forget PUT helpers (legacy localStorage sync) and
 * typed request helpers for the codebook CRUD endpoints.
 */

import type {
  AutoCodeJobStatus,
  ClipJobStartResponse,
  ClipJobStatus,
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
  ModeratorQuestionResponse,
  ProposalsListResponse,
  RemoveFrameworkInfo,
  CodebookAnalysisListResponse,
  TagAnalysisResponse,
  TemplateListResponse,
  TranscriptPageResponse,
  MiroStatusResponse,
  MiroExportRequest,
  MiroExportResponse,
  MiroPreviewResponse,
  MiroAuthUrlResponse,
} from "./types";
import { isExportMode, resolveFromExport } from "./exportData";
import { toast } from "./toast";
import i18n from "../i18n";

function apiBase(): string {
  return (
    (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE as string
  ) || "/api/projects/1";
}

/** Build headers with auth token for localhost API access control. */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = (window as unknown as Record<string, unknown>)
    .__BRISTLENOSE_AUTH_TOKEN__ as string | undefined;
  const headers: Record<string, string> = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

// ---------------------------------------------------------------------------
// Generic request helpers
// ---------------------------------------------------------------------------

/** An Error from a failed request, annotated with what the server said. */
export interface ApiError extends Error {
  /** FastAPI's `detail` — English prose. Do not display it to a researcher. */
  detail?: string;
  /** HTTP status code. */
  status?: number;
  /** Stable refusal code, when the route raised a `RefusalError`. Localise from this. */
  reason?: string;
}

/**
 * Build an Error from a non-ok response, surfacing the server's `detail` field
 * (FastAPI's HTTPException body) when present and attaching it as `.detail` so
 * callers can render it. Without this, the helpers threw only
 * "POST <path> <status>" and dropped the body — burying actionable messages
 * like the Miro partial-board recovery URL carried in a 502 `detail`.
 */
async function httpError(method: string, path: string, resp: Response): Promise<Error> {
  let detail = "";
  let reason = "";
  try {
    const body = (await resp.json()) as { detail?: unknown; reason?: unknown };
    if (typeof body?.detail === "string") detail = body.detail;
    // A refusal names itself (bristlenose/server/refusal.py). `detail` is English
    // prose written for a log; `reason` is the stable code a caller localises
    // from. Optional — routes that raise a plain HTTPException send no reason.
    if (typeof body?.reason === "string") reason = body.reason;
  } catch {
    /* non-JSON error body — fall back to the status-only message */
  }
  const err = new Error(`${method} ${path} ${resp.status}${detail ? `: ${detail}` : ""}`);
  const annotated = err as ApiError;
  annotated.detail = detail;
  annotated.status = resp.status;
  if (reason) annotated.reason = reason;
  return err;
}

export async function apiGet<T>(path: string): Promise<T> {
  const embedded = resolveFromExport<T>(path);
  if (embedded !== undefined) return embedded;
  if (isExportMode()) {
    // Exported (offline) report: there is no server. A resolver miss means this
    // read endpoint was not embedded — fail loud so the file:// e2e catches it,
    // instead of a doomed fetch that degrades silently.
    throw new Error(`Export mode: no embedded data for ${path}`);
  }
  const resp = await fetch(`${apiBase()}${path}`, { headers: authHeaders() });
  if (!resp.ok) throw await httpError("GET", path, resp);
  return resp.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await httpError("POST", path, resp);
  return resp.json() as Promise<T>;
}

async function apiPatch(path: string, body: unknown): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`PATCH ${path} ${resp.status}`);
}

async function apiDelete(path: string): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(`DELETE ${path} ${resp.status}`);
}

async function apiDeleteJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error(`DELETE ${path} ${resp.status}`);
  return resp.json() as Promise<T>;
}

function firePut(path: string, body: unknown): void {
  if (isExportMode()) return; // No server in export mode
  fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  })
    .then((resp) => {
      // fetch only rejects on a network-layer failure — a 401/403/5xx *resolves*
      // with ok=false. Without this check the catch never fires and a failed
      // background sync is fully silent (DB never written, UI diverges on reload —
      // the dropped-auth-token masquerade). Surface it so it's at least greppable.
      if (!resp.ok) throw new Error(`PUT ${path} ${resp.status}`);
    })
    .catch((err) => {
      console.error(`PUT ${path} failed:`, err);
      // A failed background sync is otherwise invisible until reload silently
      // reverts the change. One generic toast covers every view-toggle consumer
      // (star/hide/tags/hidden-groups/framework-states/…); toast() is
      // one-at-a-time, so a burst during an outage collapses to a single message.
      // i18n key is deferred to the propagation pass — defaultValue renders now.
      toast(
        i18n.t("sync.saveFailed", {
          defaultValue: "Couldn't save your change — check your connection.",
        }),
        4000,
      );
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

export function getHiddenTagGroups(): Promise<string[]> {
  return apiGet<string[]>("/hidden-tag-groups");
}

export function putHiddenTagGroups(groupNames: string[]): void {
  firePut("/hidden-tag-groups", groupNames);
}

/**
 * Per-framework enable/disable state (the codebook switch). Only frameworks with
 * an explicit stored opinion are returned; absence means enabled (the default).
 * Functional — "off means off" (design-codebook-state-model.md §8): drives the fold,
 * report-wide badge hide, the tags-sidebar/autocomplete drop, and the re-apply gate.
 */
export function getFrameworkStates(): Promise<Record<string, boolean>> {
  return apiGet<Record<string, boolean>>("/framework-states");
}

export interface FrameworkStatesPutResult {
  status: string;
  /** Framework ids that started a catch-up delta (re-enabled with new sessions to
   *  code). The caller surfaces these as activity chips. */
  catchUp: string[];
}

/**
 * Persist the enable/disable map and learn which frameworks started a catch-up.
 *
 * Unlike the other view-toggle syncs (fire-and-forget `firePut`), this reads the
 * response body: re-enabling a codebook that has new sessions kicks off a catch-up
 * delta, and the frontend shows an activity chip for it. Never rejects — a failed
 * sync toasts (like firePut) and resolves to an empty catch-up.
 */
export function putFrameworkStates(
  states: Record<string, boolean>,
): Promise<FrameworkStatesPutResult> {
  if (isExportMode()) return Promise.resolve({ status: "ok", catchUp: [] });
  return fetch(`${apiBase()}/framework-states`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(states),
  })
    .then(async (resp) => {
      if (!resp.ok) throw new Error(`PUT /framework-states ${resp.status}`);
      const body = (await resp.json()) as Partial<FrameworkStatesPutResult>;
      return { status: body.status ?? "ok", catchUp: body.catchUp ?? [] };
    })
    .catch((err) => {
      console.error("PUT /framework-states failed:", err);
      toast(
        i18n.t("sync.saveFailed", {
          defaultValue: "Couldn't save your change — check your connection.",
        }),
        4000,
      );
      return { status: "error", catchUp: [] };
    });
}

// ---------------------------------------------------------------------------
// People (names) helpers
// ---------------------------------------------------------------------------

export interface PersonData {
  full_name: string;
  short_name: string;
  role: string;
}

export function getPeople(): Promise<Record<string, PersonData>> {
  return apiGet<Record<string, PersonData>>("/people");
}

export function putPeople(data: Record<string, PersonData>): void {
  firePut("/people", data);
}

// ---------------------------------------------------------------------------
// Moderator question helper
// ---------------------------------------------------------------------------

/** Fetch the preceding moderator utterance for a quote. Returns null on 404. */
export async function getModeratorQuestion(
  domId: string,
): Promise<ModeratorQuestionResponse | null> {
  const path = `/quotes/${encodeURIComponent(domId)}/moderator-question`;
  if (isExportMode()) {
    // Embedded per-quote map; a miss means no preceding moderator utterance
    // (a legitimate 404, not a coverage gap) — resolve to null, no fetch.
    return resolveFromExport<ModeratorQuestionResponse>(path) ?? null;
  }
  const resp = await globalThis.fetch(
    `${apiBase()}${path}`,
    { headers: authHeaders() },
  );
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`GET moderator-question ${resp.status}`);
  return resp.json() as Promise<ModeratorQuestionResponse>;
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
  // Browsing/importing templates is a server-backed authoring action (SERVER_ONLY,
  // not embedded) — an exported report has none, so resolve to an empty list
  // rather than fail-loud on the codebook tab's mount fetch.
  if (isExportMode()) return Promise.resolve({ templates: [] });
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

export function getCodebookAnalysis(
  elaborate?: boolean,
): Promise<CodebookAnalysisListResponse> {
  const qs = elaborate ? "?elaborate=true" : "";
  return apiGet<CodebookAnalysisListResponse>(`/analysis/codebooks${qs}`);
}

// ---------------------------------------------------------------------------
// Clip export
// ---------------------------------------------------------------------------

/**
 * Start clip extraction. `ids` (DOM-style quote ids) is the scope picker's
 * chosen set — Selected/Starred/All. Pass `null` for the legacy no-scope path
 * (starred ∪ featured union), used by callers that don't offer a scope yet.
 */
export function startClipExtraction(
  anonymise = false,
  ids: string[] | null = null,
): Promise<ClipJobStartResponse> {
  return apiPost<ClipJobStartResponse>("/export/clips", {
    anonymise,
    ...(ids != null ? { ids } : {}),
  });
}

export function getClipExtractionStatus(): Promise<ClipJobStatus> {
  return apiGet<ClipJobStatus>("/export/clips/status");
}

export function cancelClipExtraction(): Promise<{ cancelled: boolean }> {
  return apiPost<{ cancelled: boolean }>("/export/clips/cancel", {});
}

export function revealClips(): Promise<{ revealed: boolean; path: string }> {
  return apiPost<{ revealed: boolean; path: string }>("/export/clips/reveal", {});
}

// ---------------------------------------------------------------------------
// Miro export (experimental)
// ---------------------------------------------------------------------------

export function getMiroStatus(): Promise<MiroStatusResponse> {
  return apiGet<MiroStatusResponse>("/miro/status");
}

export function postMiroConnect(token: string): Promise<MiroStatusResponse> {
  return apiPost<MiroStatusResponse>("/miro/connect", { token });
}

export function postMiroDisconnect(): Promise<MiroStatusResponse> {
  return apiPost<MiroStatusResponse>("/miro/disconnect", {});
}

export function getMiroAuthUrl(): Promise<MiroAuthUrlResponse> {
  return apiGet<MiroAuthUrlResponse>("/miro/auth-url");
}

export function postMiroPreview(req: MiroExportRequest): Promise<MiroPreviewResponse> {
  return apiPost<MiroPreviewResponse>("/miro/preview", req);
}

export function postMiroExport(req: MiroExportRequest): Promise<MiroExportResponse> {
  return apiPost<MiroExportResponse>("/miro/export", req);
}

// ---------------------------------------------------------------------------
// Manual re-assignment (Phase 0) — move quote(s) into a section or theme
// ---------------------------------------------------------------------------

export interface ReassignResult {
  status: string;
  /** DOM ids actually moved (unknown ids are skipped, not fatal). */
  moved: string[];
}

/** Re-file quote(s) into a section or theme as a researcher placement.
 *  `targetId` is the durable `cluster_id` / `theme_id` the quotes API exposes.
 *  The server makes the move exclusive on that axis and freezes the quote, so
 *  the placement survives re-analysis. Awaited (not fire-and-forget) so the
 *  caller can refetch the affected groups once it resolves. */
export function reassignQuotes(
  quotes: string[],
  targetKind: "section" | "theme",
  targetId: number,
): Promise<ReassignResult> {
  return apiPost<ReassignResult>("/reassign", {
    quotes,
    target_kind: targetKind,
    target_id: targetId,
  });
}
