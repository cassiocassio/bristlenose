/**
 * exportActions — single source of truth for the four canonical export
 * actions, shared by the SPA ExportDropdown (web clicks) and the macOS
 * native menu (via AppLayout's `bn:menu-action` bridge handlers).
 *
 * Keeping these here guarantees the web and native surfaces invoke
 * identical behaviour — the drift this module exists to prevent was the
 * native "Copy as CSV" reimplementing the quotes export client-side while
 * the web hit the server endpoint.
 *
 * Canonical list (see docs/mockups/export-menu-comparison.html):
 *   1. Export Report      — handled by the ExportDialog / report endpoint
 *   2. Copy Quotes        — clipboard, lean set (quote · code · name · timecode)
 *   3. Save as Spreadsheet — rich 11-column CSV / XLSX download
 *   4. Extract Video Clips — ffmpeg background job
 *
 * `anonymise` strips participant *names* (display names) from every export;
 * participant codes (p1, p2) are kept. On the web it rides the Export Report
 * modal checkbox; on macOS it's the global menu toggle, threaded here.
 *
 * @module exportActions
 */

import type { TFunction } from "i18next";
import { startClipExtraction } from "./api";
import { addJob } from "../contexts/ActivityStore";
import { toast } from "./toast";
import { announce } from "./announce";
import type { QuotesState } from "../contexts/QuotesContext";

/** The 11 rich export columns, by i18n key, in ExportableQuote field order. */
export const QUOTE_EXPORT_COL_KEYS = [
  "export.colQuote",
  "export.colParticipantCode",
  "export.colParticipantName",
  "export.colSection",
  "export.colTheme",
  "export.colSentiment",
  "export.colTags",
  "export.colStarred",
  "export.colTimecode",
  "export.colSession",
  "export.colSourceFile",
] as const;

/** Comma-joined translated headers for the rich CSV / XLSX endpoints. */
export function buildQuoteColHeaders(t: TFunction): string {
  return QUOTE_EXPORT_COL_KEYS.map((k) => t(k)).join(",");
}

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function tsvEsc(v: string): string {
  // Tab-separated for clean paste into Sheets / Excel / Miro / Slides.
  return v.replace(/\t/g, " ").replace(/\r?\n/g, " ").trim();
}

/**
 * Build the LEAN clipboard payload — one tab-separated row per quote:
 * quote · participant code · display name · timecode. Tuned for pasting
 * into Miro / PowerPoint / a slide, distinct from the rich spreadsheet set.
 * When `anonymise`, the display-name column is dropped (code is kept).
 */
export function buildLeanQuotesText(
  store: QuotesState,
  ids: string[],
  anonymise = false,
): string {
  const byId = new Map(store.quotes.map((q) => [q.dom_id, q]));
  const rows: string[] = [];
  for (const id of ids) {
    const q = byId.get(id);
    if (!q) continue;
    const text = store.edits[q.dom_id] ?? q.edited_text ?? q.text;
    const cells = anonymise
      ? [text, q.participant_id, formatTimecode(q.start_timecode)]
      : [text, q.participant_id, q.speaker_name, formatTimecode(q.start_timecode)];
    rows.push(cells.map(tsvEsc).join("\t"));
  }
  return rows.join("\n");
}

/**
 * Copy the lean quote set to the clipboard. Builds the payload synchronously
 * from the in-memory store (no fetch) so the clipboard write stays inside the
 * user-gesture stack — Safari-safe without the ClipboardItem dance.
 * Returns the number of quotes copied (0 = nothing matched).
 */
export async function copyQuotesToClipboard(
  store: QuotesState,
  ids: string[],
  t: TFunction,
  anonymise = false,
): Promise<number> {
  if (ids.length === 0) {
    toast(t("export.noQuotesMatch"));
    return 0;
  }
  const text = buildLeanQuotesText(store, ids, anonymise);
  try {
    await navigator.clipboard.writeText(text);
    const msg = t("export.quotesCopied", { count: ids.length });
    toast(msg);
    announce(msg);
    return ids.length;
  } catch (err) {
    console.error("[exportActions] Copy failed:", err);
    toast(t("export.exportFailed"));
    return 0;
  }
}

/** Spreadsheet download formats. Both endpoints exist server-side. */
export type SpreadsheetFormat = "csv" | "xlsx";

/**
 * Trigger a download of the rich quotes spreadsheet. `format` selects the
 * endpoint (`quotes.csv` / `quotes.xlsx`); defaults to XLSX for back-compat
 * with callers that don't pass one. Direct anchor navigation — the auth cookie
 * carries the bearer; the server's Content-Disposition supplies the filename.
 * The sandboxed WKWebView routes this through an NSSavePanel; browsers use the
 * native download UI.
 */
export function saveQuotesSpreadsheet(
  projectId: number | string,
  ids: string[],
  t: TFunction,
  anonymise = false,
  format: SpreadsheetFormat = "xlsx",
): void {
  if (ids.length === 0) {
    toast(t("export.noQuotesMatch"));
    return;
  }
  const params = new URLSearchParams({
    quote_ids: ids.join(","),
    col_headers: buildQuoteColHeaders(t),
  });
  if (anonymise) params.set("anonymise", "true");
  const a = document.createElement("a");
  a.href = `/api/projects/${projectId}/export/quotes.${format}?${params.toString()}`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Kick off the ffmpeg clip-extraction background job. Registers an activity
 * chip and surfaces ffmpeg-missing / in-progress / failed states via toast.
 */
export async function extractVideoClips(t: TFunction, anonymise = false): Promise<void> {
  try {
    const result = await startClipExtraction(anonymise);
    if (result.total === 0) {
      toast(t("export.clips.noClips"));
      return;
    }
    addJob("clips", { type: "clips", frameworkId: "", frameworkTitle: "", total: result.total });
    if (result.pii_warning) toast(t("export.clips.piiWarning"));
    announce(t("export.clips.progress", { progress: 0, total: result.total }));
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "";
    if (msg.includes("422")) toast(t("export.clips.ffmpegMissing"));
    else if (msg.includes("409")) toast(t("export.clips.inProgress"));
    else toast(t("export.clips.failed"));
  }
}

