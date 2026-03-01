/**
 * Export mode detection and embedded data resolution.
 *
 * When a report is exported as a self-contained HTML file, all API data is
 * embedded as `window.BRISTLENOSE_EXPORT`.  This module detects export mode
 * and resolves API paths to embedded data without network requests.
 */

import type {
  CodebookAnalysisListResponse,
  CodebookResponse,
  DashboardResponse,
  SentimentAnalysisData,
  TranscriptPageResponse,
} from "./types";
import type { PersonData } from "./api";

// ---------------------------------------------------------------------------
// Embedded data shape
// ---------------------------------------------------------------------------

export interface ExportData {
  version: number;
  exported_at: string;
  project: { project_name: string; session_count: number; participant_count: number };
  health: { status: string; version: string };
  dashboard: DashboardResponse;
  sessions: unknown; // SessionsListResponse (not typed here to avoid circular dep)
  quotes: unknown; // QuotesListResponse
  codebook: CodebookResponse;
  analysis: {
    sentiment: SentimentAnalysisData | null;
    codebooks: CodebookAnalysisListResponse | null;
  };
  transcripts: Record<string, TranscriptPageResponse>;
  people: Record<string, PersonData>;
  videoMap: unknown | null;
}

// ---------------------------------------------------------------------------
// Detection (cached after first check)
// ---------------------------------------------------------------------------

let _cached: ExportData | null | undefined;

export function getExportData(): ExportData | null {
  if (_cached === undefined) {
    _cached =
      ((window as unknown as Record<string, unknown>)
        .BRISTLENOSE_EXPORT as ExportData | undefined) ?? null;
  }
  return _cached;
}

export function isExportMode(): boolean {
  return getExportData() !== null;
}

// ---------------------------------------------------------------------------
// Path → embedded data resolver
// ---------------------------------------------------------------------------

/**
 * Map an API path (relative to project base, e.g. "/dashboard") to the
 * corresponding embedded data blob.  Returns `null` when not in export mode
 * or if the path is unrecognised.
 */
export function resolveFromExport<T>(path: string): T | null {
  const data = getExportData();
  if (!data) return null;

  // Exact matches
  if (path === "/info") return data.project as T;
  if (path === "/dashboard") return data.dashboard as T;
  if (path === "/sessions") return data.sessions as T;
  if (path === "/quotes") return data.quotes as T;
  if (path === "/codebook") return data.codebook as T;
  if (path === "/people") return data.people as T;
  if (path === "/video-map") return data.videoMap as T;
  if (path === "/analysis/sentiment") return data.analysis.sentiment as T;

  // Prefix: /analysis/codebooks[?...]
  if (path === "/analysis/codebooks" || path.startsWith("/analysis/codebooks?")) {
    return data.analysis.codebooks as T;
  }

  // Pattern: /transcripts/{sessionId}
  const txMatch = path.match(/^\/transcripts\/(.+)$/);
  if (txMatch) {
    const sid = txMatch[1];
    const tx = data.transcripts[sid];
    return (tx ?? null) as T;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Reset (for tests)
// ---------------------------------------------------------------------------

/** @internal — reset cached state between tests. */
export function _resetExportCache(): void {
  _cached = undefined;
}
