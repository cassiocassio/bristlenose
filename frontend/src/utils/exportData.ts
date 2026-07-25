/**
 * Export mode detection and embedded data resolution.
 *
 * When a report is exported as a self-contained HTML file, every read endpoint's
 * JSON is embedded as `window.BRISTLENOSE_EXPORT.endpoints`, keyed by the same
 * relative API path the SPA calls (e.g. "/dashboard", "/transcripts/s1").  The
 * server builds this map from its own OpenAPI read surface (see
 * `bristlenose/server/routes/export.py`), so the offline data contract is
 * derived, not hand-mirrored — a new embedded endpoint appears here for free.
 *
 * This module detects export mode and resolves an API path to its embedded blob
 * without any network request.  A MISS returns `undefined` (path not embedded),
 * distinct from a present-but-null value (e.g. "/video-map"): `apiGet` uses that
 * distinction to fail loud on an uncovered read in export mode rather than fall
 * through to a doomed fetch.
 */

import type { HealthResponse } from "./health";

// ---------------------------------------------------------------------------
// Embedded data shape
// ---------------------------------------------------------------------------

export interface ExportData {
  version: number;
  exported_at: string;
  health: HealthResponse;
  logos?: { light?: string; dark?: string };
  /** Path-keyed embed: relative API path → the endpoint's JSON response. */
  endpoints: Record<string, unknown>;
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
 * corresponding embedded blob.  Returns `undefined` when not in export mode or
 * when the path is not embedded; returns the value (which may be `null`) when
 * the path IS embedded.  The query string is ignored — embedded keys are
 * query-less (e.g. "/analysis/codebooks?elaborate=true" → "/analysis/codebooks").
 */
export function resolveFromExport<T>(path: string): T | undefined {
  const data = getExportData();
  if (!data) return undefined;
  const endpoints = data.endpoints ?? {};
  const q = path.indexOf("?");
  const base = q >= 0 ? path.slice(0, q) : path;
  if (Object.prototype.hasOwnProperty.call(endpoints, base)) {
    return endpoints[base] as T;
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Reset (for tests)
// ---------------------------------------------------------------------------

/** @internal — reset cached state between tests. */
export function _resetExportCache(): void {
  _cached = undefined;
}
