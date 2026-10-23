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

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorNotice } from "../components/RouteError";
import { apiGet, getCodebook } from "../utils/api";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import type { QuotesListResponse } from "../utils/types";
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
import { handoverClass, useLensRead } from "../hooks/useLensRead";
import { SectionHeading } from "../components";
import { groupQuotesBySession, type SessionGroup } from "../utils/quoteGroups";

interface QuoteSessionsProps {
  projectId: string;
  refreshKey?: number;
  headingAction?: React.ReactNode;
}

/** Every quote the route returned, grouped by session, in session then time order. */
export function groupBySession(data: QuotesListResponse): SessionGroup[] {
  return groupQuotesBySession([
    ...data.sections.flatMap((s) => s.quotes),
    ...data.themes.flatMap((t) => t.quotes),
    ...(data.unjoined ?? []),
    ...(data.uncategorised ?? []),
  ]);
}

export function QuoteSessions({ projectId, refreshKey = 0, headingAction }: QuoteSessionsProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);
  const [tagGroupMap, setTagGroupMap] = useState<Record<string, TagGroupInfo>>({});
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);

  // Read on open, again after a run (once more if that fails) and when tags change elsewhere
  // (the codebook lens applying AutoCode). The codebook comes with the quotes, so a re-read swaps
  // both together; without it the quotes still show, with no tag vocabulary.
  const { reload, handingOver } = useLensRead({
    read: () =>
      Promise.all([
        apiGet<QuotesListResponse>("/quotes"),
        getCodebook().catch((e: unknown) => {
          console.warn("Quotes: no codebook, so no tag vocabulary", e);
          return null;
        }),
      ]),
    apply: ([json, cb], kind) => {
      // A failed read is not left over the good one that follows: during a run there is a
      // re-read per import.
      setError(null);
      setData(json);
      initFromQuotes(
        [
          ...json.sections.flatMap((s) => s.quotes),
          ...json.themes.flatMap((th) => th.quotes),
          ...(json.unjoined ?? []),
        ],
        kind !== "first",
        json.uncategorised,
      );
      initHeadingEdits(json.sections, json.themes);
      if (!cb) return;
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
      setCodebookTagNames(cb.all_tag_names);
      setTagGroupMap(map);
      setGroupedVocabulary(groups);
    },
    // The wire string is for the console (the hook logs it); the lens says it in its own words (R86).
    onError: (err) => setError(err instanceof Error && err.message ? err.message : "read failed"),
    refreshKey,
    key: projectId,
    label: "Quotes read failed:",
  });

  useEffect(() => {
    document.addEventListener("bn:tags-changed", reload);
    return () => document.removeEventListener("bn:tags-changed", reload);
  }, [reload]);

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

  // The notice is for a lens with nothing to show: a failed re-read keeps what is drawn (R86).
  if (error && !data) {
    return (
      <section>
        {heading}
        <ErrorNotice scope="lens" />
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
    <section className={handoverClass(handingOver)} data-testid="bn-quotes-by-session">
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
