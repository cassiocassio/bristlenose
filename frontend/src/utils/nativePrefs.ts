/**
 * Per-viewer preferences that must outlive the Mac app's web view (R89).
 *
 * The report keeps zoom, quote grouping, panel open state and panel widths in
 * localStorage. In a browser that lasts; in the Mac app every web view's
 * storage is `.nonPersistent()` per serve session (`SharedConfigStore.swift`),
 * so it was lost on quit, on any serve restart and when a project's last
 * window closed. The fix is the subtitle-prefs pattern made generic: each
 * change of a listed key is also posted to native (`report-pref`),
 * `BridgeHandler` saves it in UserDefaults, and a document-start script seeds
 * a new web view's storage before the module-level readers run. Outside the
 * app there is no handler, so nothing is posted and localStorage behaves
 * exactly as before.
 *
 * App-wide, not per project, and not live across windows: another open
 * window picks a change up at its next load, and the last write wins. Keep the
 * lists in step with `tests/fixtures/report-prefs-contract.json`, which both
 * sides assert.
 *
 * Posts straight to the handler rather than through `shims/bridge.ts`, which
 * imports SidebarStore — a store importing it back would be a cycle.
 *
 * @module nativePrefs
 */

export const MIRRORED_PREF_KEYS: readonly string[] = [
  "bristlenose-zoom",
  "bn-toc-open",
  "bn-tags-open",
  "bn-toc-width",
  "bn-tags-width",
  "bn-inspector-open",
  "bn-inspector-height",
  "bn-inspector-dimension",
  "bn-screens-nav-open",
  "bn-screens-nav-width",
  "bn-discussion-guide-open",
  "bn-discussion-nav-width",
];

/** Keys mirrored by prefix. Serve always names the project "1", so in
 *  practice this is one key (`QuoteGroupingToggle.tsx`). */
export const MIRRORED_PREF_PREFIXES: readonly string[] = ["bristlenose-quote-grouping-"];

function isMirrored(key: string): boolean {
  return MIRRORED_PREF_KEYS.includes(key) || MIRRORED_PREF_PREFIXES.some((p) => key.startsWith(p));
}

/**
 * Write (or, with `null`, remove) one preference, and hand a listed one to the
 * Mac app unless `mirror` is false (a value the viewer never chose, such as a
 * measured height). Only a change is posted, judged against this partition's
 * storage, which every window on the project shares: a callback that rewrites
 * the same value posts nothing. Storage can be unavailable (private window,
 * blocked site data): the value then lasts the page, and is still posted.
 *
 * No caller removes a mirrored key today. One that does should know the Mac's
 * seed fills only absent keys, so a later document in the same view could get
 * the saved value back.
 */
export function storePref(key: string, value: string | null, mirror = true): void {
  let unchanged = false;
  try {
    unchanged = localStorage.getItem(key) === value;
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // not remembered by this page
  }
  if (!mirror || unchanged || !isMirrored(key)) return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit?.messageHandlers?.navigation?.postMessage({ type: "report-pref", key, value });
  } catch {
    // Not in WKWebView, or the handler deregistered during a race.
  }
}
