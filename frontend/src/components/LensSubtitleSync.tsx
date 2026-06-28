import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { useAnalysisSignalStore } from "../contexts/AnalysisSignalStore";
import { useQuotesStore } from "../contexts/QuotesContext";
import { postLensSubtitle, postQuotesFilter } from "../shims/bridge";
import { getCodebook } from "../utils/api";
import { isEmbedded } from "../utils/embedded";
import { filterQuotes } from "../utils/filter";
import {
  codebookCounts,
  codebookSubtitle,
  quotesSubtitle,
  signalsSubtitle,
} from "../utils/lensSubtitle";
import type { CodebookResponse } from "../utils/types";

function tabFromPath(pathname: string): string {
  if (pathname.startsWith("/report/quotes")) return "quotes";
  if (pathname.startsWith("/report/codebook")) return "codebook";
  if (pathname.startsWith("/report/analysis")) return "analysis";
  if (pathname.startsWith("/report/sessions")) return "sessions";
  return "project";
}

/**
 * Side-effect-only: derives the active lens's subtitle and pushes it to both
 * surfaces — the desktop window subtitle (via the native bridge) and the
 * browser tab (`document.title`). One string, computed where the live counts
 * already are. Sessions/Project carry no SPA subtitle (the desktop renders
 * those from its own DB read); their tab title falls back to the app name.
 *
 * Renders `null` so the store + route subscriptions that drive it re-render
 * this leaf, not the whole `AppShell`.
 */
export function LensSubtitleSync(): null {
  const { pathname } = useLocation();
  const tab = tabFromPath(pathname);
  const store = useQuotesStore();
  const signals = useAnalysisSignalStore();
  const [codebook, setCodebook] = useState<CodebookResponse | null>(null);

  // Codebook is fetched, not a reactive store — load on mount and refetch when
  // tags change (codebook edits dispatch `codebook-changed`), so the count
  // stays live the way the user expects.
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getCodebook()
        .then((c) => {
          if (!cancelled) setCodebook(c);
        })
        .catch(() => {});
    };
    load();
    window.addEventListener("codebook-changed", load);
    return () => {
      cancelled = true;
      window.removeEventListener("codebook-changed", load);
    };
  }, []);

  useEffect(() => {
    let subtitle = "";
    if (tab === "quotes") {
      const visible = filterQuotes(store.quotes, {
        searchQuery: store.searchQuery,
        viewMode: store.viewMode,
        tagFilter: store.tagFilter,
        hidden: store.hidden,
        starred: store.starred,
        tags: store.tags,
      }).length;
      subtitle = quotesSubtitle(visible, store.viewMode === "starred");
    } else if (tab === "analysis") {
      subtitle = signalsSubtitle(
        signals.sentimentSignals.length + signals.tagSignals.length,
      );
    } else if (tab === "codebook" && codebook) {
      const { codebooks, tags } = codebookCounts(codebook);
      subtitle = codebookSubtitle(codebooks, tags);
    }

    document.title = subtitle || "Bristlenose";
    if (isEmbedded()) {
      postLensSubtitle(tab, subtitle);
      // Mirror the Quotes filter state to the native toolbar (search field +
      // starred toggle) — only on the Quotes lens, where those controls live.
      // Native equality-guards the assigns, so the occasional same-value post
      // (this effect also fires on signals/codebook changes) is a no-op.
      if (tab === "quotes") postQuotesFilter(store.searchQuery, store.viewMode);
    }
  }, [tab, store, signals, codebook]);

  return null;
}
