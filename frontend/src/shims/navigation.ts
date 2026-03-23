/**
 * Navigation shims — install window.switchToTab, window.scrollToAnchor, and
 * window.navigateToSession as functions that delegate to React Router.
 *
 * This maintains backward compatibility for:
 * - Vanilla JS modules not yet migrated (focus.js, player.js, etc.)
 * - Dashboard and AnalysisPage module-level wrapper functions
 * - Any external callers (including native macOS callAsyncJavaScript)
 *
 * The shim functions are installed once on window but always read navigate/
 * scrollToAnchor from module-level refs — so re-calling installNavigationShims
 * with a newer navigate function takes effect immediately without reinstalling
 * the window functions. This prevents stale-closure bugs where the initial
 * navigate captured at mount doesn't work until the router is fully ready.
 */

import type { NavigateFunction } from "react-router-dom";
import type { ScrollToAnchorOptions } from "../hooks/useScrollToAnchor";

const TAB_ROUTES: Record<string, string> = {
  project: "/report/",
  sessions: "/report/sessions/",
  quotes: "/report/quotes/",
  codebook: "/report/codebook/",
  analysis: "/report/analysis/",
  settings: "/report/settings/",
  about: "/report/about/",
};

// Module-level refs — always point to the latest functions.
let navigateRef: NavigateFunction = () => {};
let scrollToAnchorRef: (
  anchorId: string,
  opts?: ScrollToAnchorOptions,
) => void = () => {};

export function installNavigationShims(
  navigate: NavigateFunction,
  scrollToAnchor: (anchorId: string, opts?: ScrollToAnchorOptions) => void,
): void {
  // Update refs — existing window functions will pick up the new values.
  navigateRef = navigate;
  scrollToAnchorRef = scrollToAnchor;

  // Only install window functions once (idempotent).
  if ((window as unknown as Record<string, unknown>).switchToTab) return;

  (window as unknown as Record<string, unknown>).switchToTab = (
    tab: string,
  ) => {
    const route = TAB_ROUTES[tab] ?? "/report/";
    navigateRef(route);
  };

  (window as unknown as Record<string, unknown>).scrollToAnchor = (
    anchorId: string,
    opts?: ScrollToAnchorOptions,
  ) => {
    scrollToAnchorRef(anchorId, opts);
  };

  (window as unknown as Record<string, unknown>).navigateToSession = (
    sid: string,
    anchorId?: string,
  ) => {
    navigateRef(`/report/sessions/${sid}`);
    if (anchorId) {
      scrollToAnchorRef(anchorId, { block: "center", highlight: true });
    }
  };
}
