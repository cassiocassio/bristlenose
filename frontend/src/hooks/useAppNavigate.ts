/**
 * useAppNavigate — tab and session navigation via React Router.
 *
 * Provides `navigateToTab(tab, anchor?)` and `navigateToSession(sid, anchor?)`
 * that delegate to React Router's `useNavigate`.
 */

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useScrollToAnchor } from "./useScrollToAnchor";

const TAB_PATHS: Record<string, string> = {
  project: "/report/",
  sessions: "/report/sessions/",
  quotes: "/report/quotes/",
  codebook: "/report/codebook/",
  analysis: "/report/analysis/",
  settings: "/report/settings/",
  about: "/report/about/",
};

export function useAppNavigate() {
  const navigate = useNavigate();
  const scrollToAnchor = useScrollToAnchor();

  const navigateToTab = useCallback(
    (tab: string, anchor?: string) => {
      const path = TAB_PATHS[tab] ?? "/report/";
      navigate(path);
      if (anchor) {
        scrollToAnchor(anchor);
      }
    },
    [navigate, scrollToAnchor],
  );

  const navigateToSession = useCallback(
    (sid: string, anchor?: string) => {
      navigate(`/report/sessions/${sid}`);
      if (anchor) {
        scrollToAnchor(anchor, { block: "center", highlight: true });
      }
    },
    [navigate, scrollToAnchor],
  );

  return { navigateToTab, navigateToSession, scrollToAnchor };
}
