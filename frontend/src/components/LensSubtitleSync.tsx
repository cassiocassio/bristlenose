import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { useSignalStore } from "../contexts/SignalStore";
import { filterStateOf, useQuotesStore } from "../contexts/QuotesContext";
import { useLocaleStore } from "../i18n/LocaleStore";
import { postLensSubtitle, postQuotesFilter } from "../shims/bridge";
import { tokensToWire } from "../utils/searchBridge";
import { apiGet, getCodebook } from "../utils/api";
import { isEmbedded } from "../utils/embedded";
import { filterQuotes } from "../utils/filter";
import {
  codebookCounts,
  codebookSubtitle,
  quotesSubtitle,
  screensSubtitle,
  signalsSubtitle,
} from "../utils/lensSubtitle";
import { useScreensCount } from "../islands/screens/screensCount";
import type { CodebookResponse } from "../utils/types";

export function tabFromPath(pathname: string): string {
  if (pathname.startsWith("/report/quotes")) return "quotes";
  // The v2 arm retired with its route on 31 Aug 2026, and so did the
  // longest-prefix hazard it guarded: "/report/codebook-v2" had
  // "/report/codebook" as a prefix, so the shorter test swallowed it and the
  // subtitle was posted under the wrong tag — Swift then discarded it
  // (`countSubtitle` guards on `lensSubtitleTab == activeTab.rawValue`) and the
  // window fell back to the SESSION count on a codebook lens. Recorded because
  // the RULE outlives the case: the tag here must be the Swift `Tab` rawValue,
  // and any future sibling route sharing a prefix must be tested first.
  //
  if (pathname.startsWith("/report/codebook")) return "codebook";
  if (pathname.startsWith("/report/signals")) return "signals";
  if (pathname.startsWith("/report/sessions")) return "sessions";
  if (pathname.startsWith("/report/screens")) return "screens";
  return "project";
}

/** Which lens the browser-tab title names. Finer than `tabFromPath`, whose
 *  tag is the Swift `Tab` rawValue (Discussion has no native tab, so it is
 *  "project" there): the tab title must say "Discussion". */
export function titleLensOf(pathname: string): { key: string; sessionNumber?: number } {
  const m = pathname.match(/^\/report\/sessions\/s?(\d+)\/?$/);
  if (m) return { key: "session", sessionNumber: Number(m[1]) };
  if (pathname.startsWith("/report/discussion")) return { key: "discussion" };
  return { key: tabFromPath(pathname) };
}

/** `<Lens> \u00b7 <Project> \u00b7 Bristlenose`; the project segment is dropped
 *  until its name is known. The native window subtitle is unaffected. */
export function tabTitle(lens: string, project: string | null): string {
  return [lens, project, "Bristlenose"].filter(Boolean).join(" \u00b7 ");
}

/**
 * Side-effect-only: derives the active lens's subtitle and pushes it to both
 * surfaces — the desktop window subtitle (via the native bridge) and the
 * browser tab (`document.title`). The window subtitle is the lens's live count
 * (Sessions/Project carry none: the desktop renders those from its own DB
 * read). The tab title is `<Lens> \u00b7 <Project> \u00b7 Bristlenose` and carries no
 * count (BR-19, owner ruling 16 Nov 2026; it used to equal the subtitle).
 *
 * Renders `null` so the store + route subscriptions that drive it re-render
 * this leaf, not the whole `AppShell`.
 */
export function LensSubtitleSync(): null {
  const { pathname } = useLocation();
  const tab = tabFromPath(pathname);
  const store = useQuotesStore();
  // The subtitle and the token labels are i18n strings: re-post on a language change.
  const { locale } = useLocaleStore();
  const signals = useSignalStore();
  const screensCount = useScreensCount();
  const [codebook, setCodebook] = useState<CodebookResponse | null>(null);
  const { t } = useTranslation();
  const [projectName, setProjectName] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    apiGet<{ project_name: string }>("/info")
      .then((info) => {
        if (!cancelled) setProjectName(info.project_name || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  const onCodebook = tab === "codebook";

  // Codebook is fetched, not a reactive store — load on mount, refetch when
  // tags change (codebook edits dispatch `codebook-changed`) and when the lens
  // is opened, as the lens itself does: a tag made on a quote card dispatches
  // nothing, so the count would otherwise stay as it was at page load.
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
  }, [onCodebook]);

  useEffect(() => {
    let subtitle = "";
    if (tab === "quotes") {
      const visible = filterQuotes(store.quotes, filterStateOf(store)).length;
      subtitle = quotesSubtitle(visible, store.viewMode === "starred");
    } else if (tab === "signals") {
      subtitle = signalsSubtitle(signals.signals.length);
    } else if (tab === "codebook" && codebook) {
      const { codebooks, tags } = codebookCounts(codebook);
      subtitle = codebookSubtitle(codebooks, tags);
    } else if (tab === "screens") {
      subtitle = screensSubtitle(screensCount.screens, screensCount.screenshots, screensCount.quotes);
    }

    const lens = titleLensOf(pathname);
    const lensLabel =
      lens.key === "session"
        ? t("dashboard.coverageSession", { number: lens.sessionNumber })
        : t(`nav.${lens.key}`);
    document.title = tabTitle(lensLabel, projectName);
    if (isEmbedded()) {
      postLensSubtitle(tab, subtitle);
      // Mirror the Quotes filter state to the native toolbar (search field +
      // starred toggle) — only on the Quotes lens, where those controls live.
      // Native equality-guards the assigns, so the occasional same-value post
      // (this effect also fires on signals/codebook changes) is a no-op.
      if (tab === "quotes") {
        postQuotesFilter(store.searchQuery, store.viewMode, tokensToWire(store.searchTokens));
      }
    }
  }, [tab, pathname, store, signals, codebook, locale, screensCount, projectName, t]);

  return null;
}
