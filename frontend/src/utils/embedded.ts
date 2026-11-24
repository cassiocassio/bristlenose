/**
 * Embedded mode detection — true when running inside a macOS WKWebView.
 *
 * The native shell injects `window.__BRISTLENOSE_EMBEDDED__ = true` via
 * WKUserScript at `.atDocumentStart` before the page loads.  This module
 * caches the result on first access (same pattern as isExportMode).
 *
 * For dev testing: set `window.__BRISTLENOSE_EMBEDDED__ = true` in devtools
 * console and reload.
 */

let _cached: boolean | undefined;

export function isEmbedded(): boolean {
  if (_cached === undefined) {
    _cached =
      (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ === true ||
      new URLSearchParams(window.location.search).has("embedded");
  }
  return _cached;
}

/** Reset cached value — for tests only. */
export function _resetEmbeddedCache(): void {
  _cached = undefined;
}

/**
 * The Mac host's sidebar draws AutoCode's progress and its endings (the AppKit sidebar, landing
 * plan D51), so the page draws no pop-up of its own for a first run or a catch-up (D38, D40).
 * Injected as `window.__BRISTLENOSE_SIDEBAR_AUTOCODE__` by `WebView.sidebarAutoCodeScript`; the
 * SwiftUI sidebar and the browser never set it, and keep the pop-up.
 */
export function hostShowsAutoCode(): boolean {
  return (window as unknown as Record<string, unknown>).__BRISTLENOSE_SIDEBAR_AUTOCODE__ === true;
}
