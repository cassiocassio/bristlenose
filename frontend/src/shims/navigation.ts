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
  // Keys are `Tab.rawValue` on the Swift side, so this is camelCase where the
  // route is kebab. Pinned by tests/test_tab_route_parity.py — the contract
  // was stated in Tab.swift's doc comment for months with nothing enforcing
  // it, and the day it was broken the lens just went quietly to /report/.
  codebookV2: "/report/codebook-v2/",
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
    const route = TAB_ROUTES[tab];
    if (route === undefined) {
      // Falling back to the Project tab is right for a shipped build — a
      // researcher gets a working screen, not a blank one. But in dev it is
      // how a missing key hides: the control looks dead, nothing errors, and
      // the tab you were on is the tab you stay on. Say so.
      if (import.meta.env.DEV) {
        console.warn(
          `switchToTab: unknown tab "${tab}" — no TAB_ROUTES entry, ` +
            `falling back to /report/. Add it to shims/navigation.ts.`,
        );
      }
      navigateRef("/report/");
      return;
    }
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
