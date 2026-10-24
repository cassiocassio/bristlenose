/**
 * Has the whole report crashed again after its Retry? (spec
 * `docs/mockups/report-crash-repeat.html`; `docs/design-feedback-native.md`
 * § Feedback and problem reports.)
 *
 * Retry is a page reload, so nothing in memory survives it. The report's Retry
 * leaves one flag in `sessionStorage` before reloading; a report that then
 * mounts clears it (`AppLayout`), and one that crashes again finds it standing
 * and offers Send feedback in Retry's place. The counterpart of the Mac boot
 * pane's `startedByRetry`.
 *
 * `sessionStorage` lasts for the tab or web view, so a new window, a project
 * switch or a restarted serve (a new origin) starts with Retry again. The flag
 * carries nothing about the crash. Storage that throws (a `file:` export in
 * some engines, a locked-down browser) reads as "not retried": Retry, always.
 */
export const REPORT_RETRY_KEY = "bn-report-retry";

export function markReportRetry(): void {
  try {
    sessionStorage.setItem(REPORT_RETRY_KEY, "1");
  } catch {
    /* storage unavailable: Retry stays the button */
  }
}

export function reportWasRetried(): boolean {
  try {
    return sessionStorage.getItem(REPORT_RETRY_KEY) === "1";
  } catch {
    return false;
  }
}

export function clearReportRetry(): void {
  try {
    sessionStorage.removeItem(REPORT_RETRY_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** The report crash pane's Retry: mark it, then reload. */
export function retryReport(): void {
  markReportRetry();
  window.location.reload();
}
