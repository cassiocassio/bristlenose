/**
 * Navigation shims — install window.switchToTab, window.scrollToAnchor, and
 * window.navigateToSession as functions that delegate to React Router.
 *
 * This maintains backward compatibility for:
 * - Vanilla JS modules not yet migrated (focus.js, player.js, etc.)
 * - Dashboard and AnalysisPage module-level wrapper functions
 * - Any external callers
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

export function installNavigationShims(
  navigate: NavigateFunction,
  scrollToAnchor: (anchorId: string, opts?: ScrollToAnchorOptions) => void,
): void {
  (window as unknown as Record<string, unknown>).switchToTab = (
    tab: string,
  ) => {
    const route = TAB_ROUTES[tab] ?? "/report/";
    navigate(route);
  };

  (window as unknown as Record<string, unknown>).scrollToAnchor = (
    anchorId: string,
    opts?: ScrollToAnchorOptions,
  ) => {
    scrollToAnchor(anchorId, opts);
  };

  (window as unknown as Record<string, unknown>).navigateToSession = (
    sid: string,
    anchorId?: string,
  ) => {
    navigate(`/report/sessions/${sid}`);
    if (anchorId) {
      scrollToAnchor(anchorId, { block: "center", highlight: true });
    }
  };
}
