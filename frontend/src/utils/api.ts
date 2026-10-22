/**
 * API helpers for the data endpoints.
 *
 * Fire-and-forget PUT helpers (legacy localStorage sync) and
 * typed request helpers for the codebook CRUD endpoints.
 */

import type {
  AutoCodeJobStatus,
  AutoCodeJobsResponse,
  ClipJobStartResponse,
  ClipJobStatus,
  ScreensExportStart,
  ScreensExportStatus,
  ScreensMiroRequest,
  ScreensMiroStatus,
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
  ModeratorQuestionResponse,
  ProposalsListResponse,
  RemoveFrameworkInfo,
  CodebookSignalsListResponse,
  TagSignalsResponse,
  TemplateListResponse,
  TranscriptPageResponse,
  MiroStatusResponse,
  MiroExportRequest,
  MiroBoardStatus,
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
  /** The reason's variables (a partial Miro board's `url`), when the route sent any. */
  vars?: Record<string, string>;
  /** A curation PATCH's quotes the server no longer has; nothing was written for them. */
  unresolved?: string[];
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
  let vars: Record<string, string> | undefined;
  try {
    const body = (await resp.json()) as { detail?: unknown; reason?: unknown; vars?: unknown };
    if (typeof body?.detail === "string") detail = body.detail;
    // A refusal names itself (bristlenose/server/refusal.py). `detail` is English
    // prose written for a log; `reason` is the stable code a caller localises
    // from. Optional — routes that raise a plain HTTPException send no reason.
    if (typeof body?.reason === "string") reason = body.reason;
    // Its variables travel beside it (routes/miro.py sends `vars`); a caller
    // that localises from `reason` needs them, or a partial board's address
    // is dropped along with the English sentence that used to carry it.
    if (body?.vars && typeof body.vars === "object") {
      const picked: Record<string, string> = {};
      for (const [k, v] of Object.entries(body.vars as Record<string, unknown>)) {
        if (typeof v === "string") picked[k] = v;
      }
      vars = picked;
    }
  } catch {
    /* non-JSON error body — fall back to the status-only message */
  }
  const err = new Error(`${method} ${path} ${resp.status}${detail ? `: ${detail}` : ""}`);
  const annotated = err as ApiError;
  annotated.detail = detail;
  annotated.status = resp.status;
  if (reason) annotated.reason = reason;
  if (vars) annotated.vars = vars;
  return err;
}

/**
 * GET a text body (e.g. WebVTT) with the auth header, plus the response's
 * ``Content-Language``. Not available in an exported report (no server).
 */
export async function apiGetText(
  path: string,
): Promise<{ text: string; language: string | null }> {
  if (isExportMode()) throw new Error(`Export mode: no server for ${path}`);
  const resp = await fetch(`${apiBase()}${path}`, { headers: authHeaders() });
  if (!resp.ok) throw await httpError("GET", path, resp);
  return { text: await resp.text(), language: resp.headers.get("Content-Language") };
}

/** `timeoutMs`: a read that has not answered by then fails (an AbortController and a timer,
 *  not `AbortSignal.timeout`, which fake timers cannot drive). Without it, a read waits. */
export async function apiGet<T>(path: string, timeoutMs?: number): Promise<T> {
  const embedded = resolveFromExport<T>(path);
  if (embedded !== undefined) return embedded;
  if (isExportMode()) {
    // Exported (offline) report: there is no server. A resolver miss means this
    // read endpoint was not embedded — fail loud so the file:// e2e catches it,
    // instead of a doomed fetch that degrades silently.
    throw new Error(`Export mode: no embedded data for ${path}`);
  }
  const abort = timeoutMs ? new AbortController() : null;
  const timer = abort ? setTimeout(() => abort.abort(), timeoutMs) : undefined;
  try {
    const init = abort ? { headers: authHeaders(), signal: abort.signal } : { headers: authHeaders() };
    const resp = await fetch(`${apiBase()}${path}`, init);
    if (!resp.ok) throw await httpError("GET", path, resp);
    return (await resp.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

async function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok) throw await httpError("POST", path, resp);
  return resp.json() as Promise<T>;
}

/** Split a transcript paragraph in two at a word boundary (design-transcript-
 *  editing.md §"Split and join, stage 1"). Returns the recorded edit's id. */
export function postParagraphSplit(
  sessionId: string, position: number, token: number, verify: string,
): Promise<{ id: number }> {
  return apiPost(`/transcripts/${encodeURIComponent(sessionId)}/split`, { position, token, verify });
}

/** Join a paragraph onto the one above it (the same speaker's only). */
export function postParagraphJoin(sessionId: string, position: number, verify: string): Promise<{ id: number }> {
  return apiPost(`/transcripts/${encodeURIComponent(sessionId)}/join`, { position, verify });
}

/** Credit one paragraph to another speaker of its session, by that speaker's
 *  slot code (design-people.md §K, the picker's Paragraph scope). */
export function postParagraphReassign(
  sessionId: string, position: number, verify: string, to: { slot: string } | { new: "moderator" },
): Promise<{ id: number }> {
  return apiPost(`/transcripts/${encodeURIComponent(sessionId)}/reassign`, { position, verify, ...to });
}

/** Take a split, join or reassignment back. */
export function deleteParagraphEdit(sessionId: string, id: number): Promise<void> {
  return apiDelete(`/transcripts/${encodeURIComponent(sessionId)}/layout-edits/${id}`);
}

/** Whether a session needs a paid re-analysis after a speaker recode, and what
 *  it would cost (design-people.md §J7 R3). */
export interface ReanalyseInfo {
  needed: boolean;
  cost_usd: number | null;
  running: boolean;
  command: string;
}

export function getReanalyse(sessionId: string): Promise<ReanalyseInfo> {
  return apiGet<ReanalyseInfo>(`/sessions/${encodeURIComponent(sessionId)}/reanalyse`);
}

/** Pin the session's speakers as the researcher has them, for the next run. */
export function postReanalyse(sessionId: string): Promise<{ pinned: number; command: string }> {
  return apiPost(`/sessions/${encodeURIComponent(sessionId)}/reanalyse`, {});
}

async function apiPatch(path: string, body: unknown): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await httpError("PATCH", path, resp);
}

async function apiDelete(path: string): Promise<void> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!resp.ok) throw await httpError("DELETE", path, resp);
}

async function apiDeleteJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  // Status only: its caller (the codebook lens's uninstall) shows the message,
  // and `httpError` would carry the server's English detail into it.
  if (!resp.ok) throw new Error(`DELETE ${path} ${resp.status}`);
  return resp.json() as Promise<T>;
}

function firePut(path: string, body: unknown): void {
  sendPut(path, body).catch(() => undefined);
}

/**
 * The awaitable `firePut`: same request, same toast on failure, but the caller
 * can wait for it — which an ordered sequence of writes needs (an undo must
 * land after the act it reverses). Rejects after toasting.
 */
export function sendPut(path: string, body: unknown): Promise<void> {
  return sendWrite("PUT", path, body);
}

function sendWrite(
  method: "PUT" | "PATCH",
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<void> {
  if (isExportMode()) return Promise.resolve(); // No server in export mode
  return fetch(`${apiBase()}${path}`, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    signal,
  })
    .then(async (resp) => {
      // fetch only rejects on a network-layer failure — a 401/403/5xx *resolves*
      // with ok=false. Without this check the catch never fires and a failed
      // background sync is fully silent (DB never written, UI diverges on reload —
      // the dropped-auth-token masquerade). Surface it so it's at least greppable.
      if (!resp.ok) throw await httpError(method, path, resp);
      if (method === "PATCH") {
        // A curation PATCH names back the quotes it could not place (a re-run
        // removed them). Nothing was written for those: refuse, so the store
        // takes them back rather than drawing a change that never saved.
        // The server committed (200); an unreadable answer only loses the
        // "unresolved" list, so it counts as placed, and says so in the log.
        const answer = (await resp.json().catch((e: unknown) => {
          console.warn(`${method} ${path}: answer unreadable, taken as placed`, e);
          return null;
        })) as { unresolved?: unknown } | null;
        const unresolved = Array.isArray(answer?.unresolved) ? (answer.unresolved as string[]) : [];
        if (unresolved.length > 0) {
          throw Object.assign(new Error(`${method} ${path}: no such quote`), {
            status: resp.status,
            unresolved,
          }) as ApiError;
        }
      }
    })
    .catch((err) => {
      console.error(`${method} ${path} failed:`, err);
      // A failed background sync is otherwise invisible until reload silently
      // reverts the change. One toast covers every view-toggle consumer
      // (star/hide/tags/hidden-groups/framework-states/…); toast() is
      // one-at-a-time, so a burst during an outage collapses to a single message.
      toastSaveFailed(err);
      throw err;
    });
}

/**
 * What a write that did not land says. The connection only when the request
 * never reached the server, which is the one failure `fetch` rejects on;
 * anything the server answered is its refusal, named by `reason` when it sent
 * one (`bristlenose/server/refusal.py`). Every failure used to blame the
 * connection, so a speaker pick refused during an analysis sent the researcher
 * to check their network (14 Oct 2026).
 */
export function toastSaveFailed(err: unknown): void {
  const { reason, status, unresolved } = (err ?? {}) as ApiError;
  const message =
    reason === "run_in_progress"
      ? i18n.t("sync.runInProgress")
      : unresolved?.length
        ? // A re-run removed the quote; the store re-reads them (RE#20 #21).
          i18n.t("sync.quoteGone")
        : typeof status === "number"
          ? i18n.t("sync.saveRefused")
          : i18n.t("sync.saveFailed");
  toast(message, 4000);
}

// ---------------------------------------------------------------------------
// Curation writes: one gesture's change, never the whole map
// ---------------------------------------------------------------------------
//
// Each names only the quotes a gesture changed and only what changed. The
// server's `PUT` on the same paths replaces the whole map, so it erased what
// the client didn't hold: AutoCode tags re-applied after a run, the curation
// of quotes a speaker recode keeps off `/quotes`, and a deleted tag still in a
// stale map came back under Uncategorised.
//
// Writes to one path go out one at a time, in the order they were made. Sent
// together they reach the server's threadpool together, and a star and its
// unstar (or an act and its ⌘Z) could commit the wrong way round, leaving the
// server opposite to the screen. Each still toasts on failure and rejects, and
// one that has not answered in WRITE_TIMEOUT_MS fails, so a hung request cannot
// hold every later write on its path unsent.

export interface CurationDelta {
  add?: string[];
  remove?: string[];
  /** Tags only: how the added tags were applied, when an undo puts a removed
   *  one back (`QuoteTag.source`). Absent, the server records "human". */
  source?: string;
}

const writeQueues = new Map<string, Promise<void>>();
const WRITE_TIMEOUT_MS = 30_000;

function timedPatch(path: string, body: unknown): Promise<void> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), WRITE_TIMEOUT_MS);
  return sendWrite("PATCH", path, body, abort.signal).finally(() => clearTimeout(timer));
}

function queuedPatch(path: string, body: unknown): Promise<void> {
  const next = (writeQueues.get(path) ?? Promise.resolve()).then(() => timedPatch(path, body));
  // A failed write has already said why; the queue must outlive it, or every
  // later write to the path would be skipped.
  writeQueues.set(path, next.catch(() => undefined));
  return next;
}

export function patchHidden(data: Record<string, boolean>): Promise<void> {
  return queuedPatch("/hidden", data);
}

export function patchStarred(data: Record<string, boolean>): Promise<void> {
  return queuedPatch("/starred", data);
}

/** Text sets an edit; `null` clears it (the quote or heading reads as the pipeline's). */
export function patchEdits(data: Record<string, string | null>): Promise<void> {
  return queuedPatch("/edits", data);
}

export function patchTags(data: Record<string, CurationDelta>): Promise<void> {
  return queuedPatch("/tags", data);
}

export function patchDeletedBadges(data: Record<string, CurationDelta>): Promise<void> {
  return queuedPatch("/deleted-badges", data);
}

export function getHiddenTagGroups(): Promise<string[]> {
  return apiGet<string[]>("/hidden-tag-groups");
}

/** Hide (`true`) or show (`false`) the groups named, and no others. The `PUT`
 *  replaced the whole set, so an eye clicked before the first read landed, or
 *  after a failed one, erased every other group hidden on the server. */
export function patchHiddenTagGroups(data: Record<string, boolean>): Promise<void> {
  return queuedPatch("/hidden-tag-groups", data);
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
      if (!resp.ok) throw await httpError("PUT", "/framework-states", resp);
      const body = (await resp.json()) as Partial<FrameworkStatesPutResult>;
      return { status: body.status ?? "ok", catchUp: body.catchUp ?? [] };
    })
    .catch((err) => {
      console.error("PUT /framework-states failed:", err);
      toastSaveFailed(err);
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

/** Moderator and observer codes restart in every session — `m1` is "the first
 *  moderator in this session" — so a bare code does not name one person. Their
 *  names live per session (`putSessionSpeaker`), never in `/people`. */
export function isSessionScopedCode(code: string): boolean {
  return code.startsWith("m") || code.startsWith("o");
}

/** Rename one session's speaker; only the fields sent change. */
export function putSessionSpeaker(
  sessionId: string,
  speakerCode: string,
  /** `confirmed` alone says yes to the name as it stands (the picker's Enter
   *  on a proposed name); a name that is sent is confirmed either way. */
  edit: Partial<PersonData> & { confirmed?: boolean },
): void {
  firePut(
    `/sessions/${encodeURIComponent(sessionId)}/speakers/${encodeURIComponent(speakerCode)}`,
    edit,
  );
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

/** A background job's status read, polled every 2 s by its activity chip: one that has not
 *  answered in this long counts as a failed poll, so a hung server ends the chip (R13). */
const STATUS_READ_TIMEOUT_MS = 5_000;

export function getAutoCodeStatus(frameworkId: string): Promise<AutoCodeJobStatus> {
  return apiGet<AutoCodeJobStatus>(`/autocode/${frameworkId}/status`, STATUS_READ_TIMEOUT_MS);
}

/** The runs in flight, read once when the report loads (R14). */
export function listAutoCodeJobs(): Promise<AutoCodeJobsResponse> {
  return apiGet<AutoCodeJobsResponse>("/autocode/jobs", STATUS_READ_TIMEOUT_MS);
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

/** A proposal review, bounded like a curation write: the quotes store holds a
 *  quote as under review until its review answers, so one that never answered
 *  would freeze that quote's tags and proposals until a reload. */
function timedReview(path: string): Promise<void> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), WRITE_TIMEOUT_MS);
  return apiPost<void>(path, {}, abort.signal).finally(() => clearTimeout(timer));
}

export function acceptProposal(proposalId: number): Promise<void> {
  return timedReview(`/autocode/proposals/${proposalId}/accept`);
}

export function denyProposal(proposalId: number): Promise<void> {
  return timedReview(`/autocode/proposals/${proposalId}/deny`);
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

export function getTagSignals(groups?: string): Promise<TagSignalsResponse> {
  const qs = groups ? `?groups=${groups}` : "";
  return apiGet<TagSignalsResponse>(`/signals/tags${qs}`);
}

export function getCodebookSignals(
  elaborate?: boolean,
): Promise<CodebookSignalsListResponse> {
  const qs = elaborate ? "?elaborate=true" : "";
  return apiGet<CodebookSignalsListResponse>(`/signals/codebooks${qs}`);
}

export interface StreamedElaboration {
  key: string;
  signal_name: string;
  pattern: string;
  elaboration: string;
}

/**
 * Findings, read as the server writes them.
 *
 * **Deliberately `fetch` and not `EventSource`.** Every call here carries a
 * bearer token and `EventSource` cannot set request headers — there is no
 * option, only a longer route to discovering it. So the frames are parsed
 * here: `event: <name>\ndata: <json>\n\n`, split on the blank line.
 *
 * Resolves when the stream ends. `onItem` fires per finding; the caller stops
 * showing placeholders when this resolves, NOT when the last item arrives —
 * a card the model declined to name sends nothing, and without a terminator
 * its placeholder would sit there for ever, which is the defect the streaming
 * exists to end.
 *
 * Export mode resolves immediately without a request: an exported report has
 * no server, and its findings are already in the embedded payload.
 */
export async function streamElaborations(
  onItem: (e: StreamedElaboration) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (isExportMode()) return;

  const resp = await fetch(`${apiBase()}/signals/elaborations`, {
    headers: authHeaders({ Accept: "text/event-stream" }),
    signal,
  });
  if (!resp.ok || !resp.body) throw await httpError("GET", "/signals/elaborations", resp);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let cut: number;
    // A frame is only complete at the blank line. Reading a partial one and
    // JSON.parsing it is the classic streaming bug: it works on every payload
    // small enough to arrive in one chunk, which is every payload in a test.
    while ((cut = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, cut);
      buf = buf.slice(cut + 2);

      let name = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (name === "elaboration" && data) {
        try {
          onItem(JSON.parse(data) as StreamedElaboration);
        } catch {
          // One malformed frame must not abandon the rest of the stream.
        }
      }
    }
  }
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
  burnSubtitles = false,
): Promise<ClipJobStartResponse> {
  return apiPost<ClipJobStartResponse>("/export/clips", {
    anonymise,
    ...(ids != null ? { ids } : {}),
    ...(burnSubtitles ? { burn_subtitles: true } : {}),
  });
}

export function getClipExtractionStatus(): Promise<ClipJobStatus> {
  return apiGet<ClipJobStatus>("/export/clips/status", STATUS_READ_TIMEOUT_MS);
}

/** Stop a clip export. Named by `jobId`, only that export: the server refuses (409) when it
 *  holds another, which a newer export started since (RE#38). */
export function cancelClipExtraction(jobId?: string): Promise<{ cancelled: boolean }> {
  return apiPost<{ cancelled: boolean }>("/export/clips/cancel", jobId ? { job_id: jobId } : {});
}

export function revealClips(): Promise<{ revealed: boolean; path: string }> {
  return apiPost<{ revealed: boolean; path: string }>("/export/clips/reveal", {});
}

// ---------------------------------------------------------------------------
// Screens export — every still, full size, to bristlenose-output/screens/
// ---------------------------------------------------------------------------

export function startScreensExport(): Promise<ScreensExportStart> {
  return apiPost<ScreensExportStart>("/export/screens", {});
}

export function getScreensExportStatus(): Promise<ScreensExportStatus> {
  return apiGet<ScreensExportStatus>("/export/screens/status", STATUS_READ_TIMEOUT_MS);
}

/** Stop a screens export; as for clips, named by `jobId` it stops only that one. */
export function cancelScreensExport(jobId?: string): Promise<{ cancelled: boolean }> {
  return apiPost<{ cancelled: boolean }>("/export/screens/cancel", jobId ? { job_id: jobId } : {});
}

export function revealScreens(): Promise<{ revealed: boolean; path: string }> {
  return apiPost<{ revealed: boolean; path: string }>("/export/screens/reveal", {});
}

export function startScreensMiro(req: ScreensMiroRequest): Promise<ScreensExportStart> {
  return apiPost<ScreensExportStart>("/export/screens/miro", req);
}

export function getScreensMiroStatus(): Promise<ScreensMiroStatus> {
  return apiGet<ScreensMiroStatus>("/export/screens/miro/status");
}

export function cancelScreensMiro(): Promise<{ cancelled: boolean }> {
  return apiPost<{ cancelled: boolean }>("/export/screens/miro/cancel", {});
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

/** The quotes board, as a job: start it, read its progress, stop it (the screens board's shape). */
export function startMiroBoard(req: MiroExportRequest): Promise<{ status: string }> {
  return apiPost<{ status: string }>("/miro/board", req);
}

export function getMiroBoardStatus(): Promise<MiroBoardStatus> {
  return apiGet<MiroBoardStatus>("/miro/board/status");
}

export function cancelMiroBoard(): Promise<{ cancelled: boolean }> {
  return apiPost<{ cancelled: boolean }>("/miro/board/cancel", {});
}

// ---------------------------------------------------------------------------
// FigJam — a board file the Bristlenose FigJam plugin opens (no push, no token)
// ---------------------------------------------------------------------------

/** The choices the FigJam dialog sends: the same as the Miro export's, bar the connection. */
export interface FigJamBoardRequest {
  board_name: string;
  locale: string;
  split_long_quotes: boolean;
  sticky_shape: "square" | "rectangle";
  clips_base: string;
}

/** What the dialog reads back from the board file before downloading it. */
export interface FigJamBoardSummary {
  totals: { quotes: number };
}

function figjamBoardPath(req: FigJamBoardRequest): string {
  const q = new URLSearchParams({
    board_name: req.board_name,
    lang: req.locale,
    split_long_quotes: String(req.split_long_quotes),
    sticky_shape: req.sticky_shape,
  });
  if (req.clips_base) q.set("clips_base", req.clips_base);
  return `/export/figjam-board.json?${q.toString()}`;
}

/** Build the board file and read its counts — the check before the download, so a refusal
 *  (`no_quotes_selected`, `clips_base_not_http`) is said in the dialog, not saved as a file. */
export function getFigJamBoard(req: FigJamBoardRequest): Promise<FigJamBoardSummary> {
  return apiGet<FigJamBoardSummary>(figjamBoardPath(req));
}

/** The same file's address, for a download the browser (or the Mac's save panel) handles. */
export function figjamBoardDownloadUrl(req: FigJamBoardRequest): string {
  return `${apiBase()}${figjamBoardPath(req)}`;
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
