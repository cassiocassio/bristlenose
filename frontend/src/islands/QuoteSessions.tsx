/**
 * QuoteSessions — the Quotes lens grouped By session.
 *
 * docs/design-progressive-lenses.md, Phase 2. During a first analysis a
 * session's quotes arrive when its extraction finishes, long before sections
 * and themes exist, so this is the only grouping the lens can draw then. After
 * the run it is one of two groupings (QuoteGroupingToggle).
 *
 * Every quote the route returns — in a section, in a theme, or not yet joined —
 * sits in its session's group, one `QuoteGroup` per session, ordered by session
 * number and then by time. A quote is in exactly one group, which is the
 * exclusivity rule restated for this grouping. The heading names the session
 * and is not editable; there is nothing to move a quote between, and no
 * freezing or pinning happens here.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { apiGet, getCodebook } from "../utils/api";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import type { QuoteResponse, QuotesListResponse } from "../utils/types";
import type { TagGroupInfo } from "./QuoteGroup";
import type { TagVocabularyGroup } from "../components";
import {
  filterStateOf,
  initFromQuotes,
  initHeadingEdits,
  useQuotesStore,
} from "../contexts/QuotesContext";
import { useFocus } from "../contexts/FocusContext";
import { filterQuotes, highlightTermsOf } from "../utils/filter";
import { QuoteGroup } from "./QuoteGroup";
import { useRefetching, refetchOverlayProps } from "../hooks/useRefetching";
import { SectionHeading } from "../components";

interface QuoteSessionsProps {
  projectId: string;
  refreshKey?: number;
  headingAction?: React.ReactNode;
}

interface SessionGroup {
  sessionId: string;
  number: number;
  quotes: QuoteResponse[];
}

/** `s12` → 12; anything else sorts last. */
function sessionNumber(sessionId: string): number {
  const n = Number(sessionId.replace(/^s/, ""));
  return Number.isFinite(n) ? n : Number.MAX_SAFE_INTEGER;
}

/** Every quote the route returned, grouped by session, in session then time order. */
export function groupBySession(data: QuotesListResponse): SessionGroup[] {
  const seen = new Set<string>();
  const bySession = new Map<string, QuoteResponse[]>();
  const all = [
    ...data.sections.flatMap((s) => s.quotes),
    ...data.themes.flatMap((t) => t.quotes),
    ...(data.unjoined ?? []),
    ...(data.uncategorised ?? []),
  ];
  for (const q of all) {
    if (seen.has(q.dom_id)) continue;
    seen.add(q.dom_id);
    const list = bySession.get(q.session_id) ?? [];
    list.push(q);
    bySession.set(q.session_id, list);
  }
  return [...bySession.entries()]
    .map(([sessionId, quotes]) => ({
      sessionId,
      number: sessionNumber(sessionId),
      quotes: [...quotes].sort((a, b) => a.start_timecode - b.start_timecode),
    }))
    .sort((a, b) => a.number - b.number || a.sessionId.localeCompare(b.sessionId));
}

export function QuoteSessions({ projectId, refreshKey = 0, headingAction }: QuoteSessionsProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);
  const [tagGroupMap, setTagGroupMap] = useState<Record<string, TagGroupInfo>>({});
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const { isRefetching, beginRefetch, endRefetch } = useRefetching();

  const fetchQuotes = useCallback((replace = false) => {
    apiGet<QuotesListResponse>("/quotes")
      .then((json) => {
        // One failed refetch during a run (there is one per import) must not
        // stay on screen over the good data that follows.
        setError(null);
        setData(json);
        initFromQuotes(
          [
            ...json.sections.flatMap((s) => s.quotes),
            ...json.themes.flatMap((th) => th.quotes),
            ...(json.unjoined ?? []),
          ],
          replace,
          json.uncategorised,
        );
        initHeadingEdits(json.sections, json.themes);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => endRefetch());
    getCodebook()
      .then((cb) => {
        setCodebookTagNames(cb.all_tag_names);
        const map: Record<string, TagGroupInfo> = {};
        const groups: TagVocabularyGroup[] = [];
        for (const g of cb.groups) {
          const tags: { name: string; colourIndex: number }[] = [];
          for (const tag of g.tags) {
            map[tag.name.toLowerCase()] = {
              group: g.name,
              colour_set: g.colour_set,
              colour_index: tag.colour_index,
              frameworkId: g.framework_id,
            };
            tags.push({ name: tag.name, colourIndex: tag.colour_index });
          }
          groups.push({ groupName: g.name, colourSet: g.colour_set, tags });
        }
        setTagGroupMap(map);
        setGroupedVocabulary(groups);
      })
      .catch(() => {});
    // projectId: a project switch refetches.
  }, [projectId, endRefetch]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  useEffect(() => {
    const handler = () => fetchQuotes(true);
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, [fetchQuotes]);

  // A run that delivers sessions moves the refresh key once per import.
  useEffect(() => {
    if (refreshKey === 0) return;
    beginRefetch();
    fetchQuotes(true);
  }, [refreshKey, fetchQuotes, beginRefetch]);

  const groups = useMemo(() => (data ? groupBySession(data) : []), [data]);

  const tagVocabulary = useMemo(() => {
    const names = new Set<string>(codebookTagNames);
    for (const g of groups) for (const q of g.quotes) for (const tag of q.tags) names.add(tag.name);
    return Array.from(names).sort();
  }, [groups, codebookTagNames]);

  const transcriptCache = useTranscriptCache();
  const store = useQuotesStore();
  const filterState = filterStateOf(store);

  const filtered = useMemo(
    () =>
      groups
        .map((g) => ({ ...g, visible: filterQuotes(g.quotes, filterState) }))
        .filter((g) => g.visible.length > 0 || g.quotes.some((q) => filterState.hidden[q.dom_id])),
    [groups, filterState],
  );

  const { registerVisibleQuoteIds } = useFocus();
  const visibleIds = useMemo(
    () => filtered.flatMap((g) => g.visible.map((q) => q.dom_id)),
    [filtered],
  );
  useEffect(() => {
    registerVisibleQuoteIds("sessions", visibleIds);
    return () => registerVisibleQuoteIds("sessions", []);
  }, [registerVisibleQuoteIds, visibleIds]);

  const heading = (
    <SectionHeading id="quotes-by-session" action={headingAction}>
      {t("quotes.groupBy.session")}
    </SectionHeading>
  );

  if (error) {
    return (
      <section>
        {heading}
        <p className="bn-empty-state">{t("quotes.failedToLoad", { error })}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section>
        {heading}
        <p className="bn-empty-state">{t("quotes.loading")}</p>
      </section>
    );
  }

  return (
    <section {...refetchOverlayProps(isRefetching)} data-testid="bn-quotes-by-session">
      {heading}
      {filtered.map((g) => (
        <QuoteGroup
          key={g.sessionId}
          anchor={`session-quotes-${g.sessionId}`}
          editKeyBase={`session-${g.sessionId}`}
          label={t("dashboard.coverageSession", { number: g.number })}
          description=""
          itemType="session"
          quotes={g.visible}
          allQuotes={g.quotes}
          tagVocabulary={tagVocabulary}
          groupedVocabulary={groupedVocabulary}
          tagGroupMap={tagGroupMap}
          hasMedia
          transcriptCache={transcriptCache}
          hasModerator={data.has_moderator}
          highlight={highlightTermsOf(filterState)}
        />
      ))}
    </section>
  );
}
