/**
 * TocSidebar — table of contents for the Quotes tab left sidebar.
 *
 * The page's contents in the grouping the column is drawing: Sections and
 * Themes links, or a row per session (the Sessions lens's row). It lists the
 * groups the column draws and no others, follows the scroll, and a click
 * scrolls to the group's heading.
 *
 * Fetches the same /api/projects/{id}/quotes the column does (again after a
 * run imports), so the contents render before the column has loaded.
 *
 * @module TocSidebar
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { QuoteResponse, QuotesListResponse, SessionsListResponse } from "../utils/types";
import { apiGet } from "../utils/api";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { useLastRun } from "../contexts/LastRunStore";
import { useSidebarStore, closeToc } from "../contexts/SidebarStore";
import { useSidebarTuning } from "../contexts/sidebarTuning";
import { filterStateOf, useQuotesStore } from "../contexts/QuotesContext";
import { useQuoteGroupingView } from "../contexts/QuoteGroupingSlot";
import { useProjectId } from "../hooks/useProjectId";
import { filterQuotes } from "../utils/filter";
import { groupAnchor, groupQuotesBySession, keepsGroup } from "../utils/quoteGroups";
import { scrollToLand } from "../utils/scrollToLand";
import { quotesPath } from "../utils/quotesLink";
import { placeProps, sectionPlace } from "../utils/contextPlace";
import { SessionEntryRow, useSessionRowLayout } from "./SessionEntry";

// ── TOC entry type ────────────────────────────────────────────────────────

interface TocEntry {
  id: string;
  label: string;
}

/** The anchor `QuoteSessions` puts on a session group's heading. */
const sessionAnchor = (sessionId: string) => `session-quotes-${sessionId}`;

const NO_IDS = new Set<string>();

function visibleIdsOf(quotes: QuoteResponse[], filterState: ReturnType<typeof filterStateOf>): Set<string> {
  return new Set(filterQuotes(quotes, filterState).map((q) => q.dom_id));
}

// ── Component ─────────────────────────────────────────────────────────────

interface TocSidebarProps {
  /** Animated close callback for overlay mode. When provided, TOC link clicks
   *  in overlay mode scroll first, then close after a brief delay so the user
   *  sees the scroll begin before the panel slides shut. */
  onOverlayClose?: () => void;
}

export function TocSidebar({ onOverlayClose }: TocSidebarProps) {
  const { t } = useTranslation();
  const projectId = useProjectId();
  const { tocMode } = useSidebarStore();
  const pg = useSidebarTuning();
  const store = useQuotesStore();
  const filterState = filterStateOf(store);
  const { refreshKey } = useLastRun();
  const grouping = useQuoteGroupingView();
  const bySession = grouping?.shown === "session";
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [sessionsData, setSessionsData] = useState<SessionsListResponse | null>(null);
  const activeRef = useRef<HTMLAnchorElement | null>(null);
  // Click intent: when the user clicks a TOC link, this ref overrides
  // the scroll spy so the clicked heading stays highlighted even if
  // the page can't scroll far enough to make it topmost (last-item edge case).
  const clickedIdRef = useRef<string | null>(null);

  // Fetch quotes data for TOC entries — on mount, and again when a run
  // imports (the column refetches on the same key).
  useEffect(() => {
    apiGet<QuotesListResponse>("/quotes")
      .then(setData)
      .catch((e: unknown) => {
        // The lens says so on screen; the contents list keeps what it has.
        console.error("Contents: /quotes failed", e);
      });
  }, [refreshKey]);

  // Re-fetch when autocode tags change (same event QuoteSections listens to).
  useEffect(() => {
    const handler = () => {
      apiGet<QuotesListResponse>("/quotes")
        .then(setData)
        .catch((e: unknown) => console.error("Contents: /quotes failed after a tag change", e));
    };
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, []);

  // ── Sections & themes ──────────────────────────────────────────────────
  // The anchor is the column's (the group's id), so no rename can move it; the
  // label is the heading's text, which also follows a rename made in this
  // session (the store's edits).

  const sectionVisible = useMemo(
    () =>
      data && !bySession
        ? visibleIdsOf([...data.sections.flatMap((s) => s.quotes), ...data.themes.flatMap((th) => th.quotes)], filterState)
        : NO_IDS,
    [data, bySession, filterState],
  );

  const sections: TocEntry[] = useMemo(() => {
    if (!data || bySession) return [];
    return data.sections
      .filter((s) => keepsGroup(s.quotes, sectionVisible, filterState.hidden))
      .map((s) => {
        return {
          id: groupAnchor("section", s.cluster_id),
          label: store.edits[`section-cluster-${s.cluster_id}:title`] ?? s.edited_label ?? s.screen_label,
        };
      });
  }, [data, bySession, sectionVisible, filterState.hidden, store.edits]);

  const themes: TocEntry[] = useMemo(() => {
    if (!data || bySession) return [];
    return data.themes
      .filter((th) => keepsGroup(th.quotes, sectionVisible, filterState.hidden))
      .map((th) => {
        return {
          id: groupAnchor("theme", th.theme_id),
          label: store.edits[`theme-group-${th.theme_id}:title`] ?? th.edited_label ?? th.theme_label,
        };
      });
  }, [data, bySession, sectionVisible, filterState.hidden, store.edits]);

  // ── Sessions ───────────────────────────────────────────────────────────

  // The same quotes the column groups (QuoteSessions.groupBySession), from
  // the same endpoint, so the two cannot list different sessions.
  const sessionGroups = useMemo(
    () =>
      data && bySession
        ? groupQuotesBySession([
            ...data.sections.flatMap((s) => s.quotes),
            ...data.themes.flatMap((th) => th.quotes),
            ...(data.unjoined ?? []),
            ...(data.uncategorised ?? []),
          ])
        : [],
    [data, bySession],
  );
  const sessionVisible = useMemo(
    () => (bySession ? visibleIdsOf(sessionGroups.flatMap((g) => g.quotes), filterState) : NO_IDS),
    [bySession, sessionGroups, filterState],
  );

  // Row metadata. Refetched only when a session joins the study (a run in
  // progress delivers them one by one), not on every quote change.
  const sessionIdsKey = sessionGroups.map((g) => g.sessionId).join(",");
  const haveQuotes = data !== null;
  useEffect(() => {
    if (!bySession || !haveQuotes) return; // the session ids are not known yet
    let current = true; // a slower, older answer must not replace a newer one
    apiGet<SessionsListResponse>("/sessions")
      .then((json) => {
        if (current) setSessionsData(json);
      })
      .catch(() => {});
    return () => {
      current = false;
    };
  }, [bySession, haveQuotes, sessionIdsKey, projectId]);

  const { navRef, layout } = useSessionRowLayout(sessionsData?.sessions ?? null);

  const sessionRows = useMemo(() => {
    if (!bySession || !sessionsData) return [];
    const byId = new Map(sessionsData.sessions.map((s) => [s.session_id, s]));
    return sessionGroups
      .filter((g) => keepsGroup(g.quotes, sessionVisible, filterState.hidden))
      .flatMap((g) => {
        const session = byId.get(g.sessionId);
        return session ? [session] : [];
      });
  }, [bySession, sessionsData, sessionGroups, sessionVisible, filterState.hidden]);

  // ── Scroll spy ─────────────────────────────────────────────────────────
  // Keyed on the ids themselves, so a star or an edit (a new filter state, the
  // same groups) does not hand the spy a new array and re-arm its click intent.

  const idsKey = (bySession
    ? sessionRows.map((s) => sessionAnchor(s.session_id))
    : [...sections, ...themes].map((e) => e.id)
  ).join("\0");
  const allIds = useMemo(() => (idsKey ? idsKey.split("\0") : []), [idsKey]);

  const activeId = useScrollSpy(allIds, 100, clickedIdRef);

  // Auto-scroll active TOC link into view within the sidebar.
  // Uses "instant" (not "smooth") to avoid competing scrollIntoView calls
  // when activeId changes rapidly during fast scrolling.
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        block: "nearest",
        behavior: "instant",
      });
    }
  }, [activeId]);

  // Click handler — smooth scroll to the target heading, landing on it even
  // though the cards in between are measured only as the scroll passes them.
  // In overlay mode, behaviour depends on the playground's overlayAutoClose
  // toggle: when true (default/legacy), close the panel after a 400ms delay;
  // when false, leave the panel open — the user closes by mousing out.
  const autoClose = pg.overlayAutoClose ?? false;
  const handleClick = useCallback((e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    clickedIdRef.current = id;
    const el = document.getElementById(id);
    if (el) {
      scrollToLand(el, "start");
    }
    if (tocMode === "overlay" && autoClose) {
      if (onOverlayClose) {
        setTimeout(onOverlayClose, 400);
      } else {
        closeToc();
      }
    }
  }, [tocMode, onOverlayClose, autoClose]);

  const handleSessionClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, sessionId: string) => handleClick(e, sessionAnchor(sessionId)),
    [handleClick],
  );

  // Nothing until the page has said which grouping it draws: guessing would
  // show one list while the column loads the other.
  if (!grouping) return null;

  if (bySession) {
    return (
      <nav aria-label={t("nav.tableOfContents")} ref={navRef}>
        {sessionRows.map((session) => (
          <SessionEntryRow
            key={session.session_id}
            session={session}
            layout={layout}
            href={`#${sessionAnchor(session.session_id)}`}
            active={activeId === sessionAnchor(session.session_id)}
            rowRef={activeRef}
            onClick={handleSessionClick}
            current="location"
          />
        ))}
      </nav>
    );
  }

  if (!data) return null;

  return (
    <nav aria-label={t("nav.tableOfContents")}>
      {sections.length > 0 && (
        <>
          <div className="toc-heading">{t("quotes.sections")}</div>
          {sections.map((entry) => (
            <a
              key={entry.id}
              href={`#${entry.id}`}
              className={`toc-link${activeId === entry.id ? " active" : ""}`}
              aria-current={activeId === entry.id ? "location" : undefined}
              ref={activeId === entry.id ? activeRef : undefined}
              onClick={(e) => handleClick(e, entry.id)}
              {...placeProps(sectionPlace(entry.id, quotesPath(entry.id)))}
            >
              {entry.label}
            </a>
          ))}
        </>
      )}
      {themes.length > 0 && (
        <>
          <div className="toc-heading">{t("quotes.themes")}</div>
          {themes.map((entry) => (
            <a
              key={entry.id}
              href={`#${entry.id}`}
              className={`toc-link${activeId === entry.id ? " active" : ""}`}
              aria-current={activeId === entry.id ? "location" : undefined}
              ref={activeId === entry.id ? activeRef : undefined}
              onClick={(e) => handleClick(e, entry.id)}
              {...placeProps(sectionPlace(entry.id, quotesPath(entry.id)))}
            >
              {entry.label}
            </a>
          ))}
        </>
      )}
    </nav>
  );
}
