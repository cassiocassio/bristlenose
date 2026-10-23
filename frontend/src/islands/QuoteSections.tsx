/**
 * QuoteSections — React island for the "Sections" (screen-specific
 * findings) content area.
 *
 * Fetches quote data from the API and renders each section as a
 * QuoteGroup with editable headings, descriptions, and interactive
 * quote cards.  On fetch, populates the shared QuotesStore so
 * mutations are visible across all quote islands.
 */

import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ErrorNotice } from "../components/RouteError";
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
import { groupAnchor } from "../utils/quoteGroups";
import { QuoteGroup } from "./QuoteGroup";
import { useLastRun } from "../contexts/LastRunStore";
import { handoverClass, useLensRead } from "../hooks/useLensRead";
import { SectionHeading } from "../components";

interface QuoteSectionsProps {
  projectId: string;
  /**
   * Bumped by `LastRunStore` when a pipeline run completes. When this
   * changes, the island refetches `/quotes` and replaces QuotesStore.
   * Optional so non-SPA mounts (legacy island mode) continue to work.
   */
  refreshKey?: number;
  /** The grouping control, when it is not at the top of the content sidebar
   *  (QuoteGroupingToggle). */
  headingAction?: React.ReactNode;
}

export function QuoteSections({ projectId, refreshKey = 0, headingAction }: QuoteSectionsProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);
  const [tagGroupMap, setTagGroupMap] = useState<Record<string, TagGroupInfo>>({});
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const { lastRun } = useLastRun();

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
      const allQuotes = [
        ...json.sections.flatMap((s) => s.quotes),
        ...json.themes.flatMap((t) => t.quotes),
      ];
      // Unjoined quotes too (Phase 2), so a star made before the sections
      // existed shows wherever the quote is drawn.
      initFromQuotes([...allQuotes, ...(json.unjoined ?? [])], kind !== "first", json.uncategorised);
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

  // Collect all tag names across all quotes + codebook for the vocabulary.
  const tagVocabulary = useMemo(() => {
    const names = new Set<string>(codebookTagNames);
    if (data) {
      for (const section of data.sections) {
        for (const q of section.quotes) {
          for (const t of q.tags) {
            names.add(t.name);
          }
        }
      }
      for (const theme of data.themes) {
        for (const q of theme.quotes) {
          for (const t of q.tags) {
            names.add(t.name);
          }
        }
      }
    }
    return Array.from(names).sort();
  }, [data, codebookTagNames]);

  const transcriptCache = useTranscriptCache();

  // ── Filter state from toolbar ──────────────────────────────────────────

  const store = useQuotesStore();
  const filterState = filterStateOf(store);

  // Build a map of cluster_id → original (unfiltered) quotes for the hidden counter.
  const allQuotesMap = useMemo(() => {
    if (!data) return new Map<number, QuoteResponse[]>();
    const map = new Map<number, QuoteResponse[]>();
    for (const s of data.sections) {
      map.set(s.cluster_id, s.quotes);
    }
    return map;
  }, [data]);

  const filteredSections = useMemo(() => {
    if (!data) return [];
    return data.sections
      .map((s) => ({
        ...s,
        quotes: filterQuotes(s.quotes, filterState),
      }))
      .filter((s) => s.quotes.length > 0 || (allQuotesMap.get(s.cluster_id)?.some((q) => filterState.hidden[q.dom_id]) ?? false));
  }, [data, filterState, allQuotesMap]);

  // Register visible quote IDs for keyboard navigation.
  const { registerVisibleQuoteIds } = useFocus();
  const visibleIds = useMemo(
    () => filteredSections.flatMap((s) => s.quotes.map((q) => q.dom_id)),
    [filteredSections],
  );
  useEffect(() => {
    registerVisibleQuoteIds("sections", visibleIds);
    // Drop the ids on unmount, or they outlive this lens: the registry is the
    // single source for `moveFocus`/`selectAll`/`selectRange`, and a native
    // menu action (Quotes ▸ Next Quote, Select All) reaches them without the
    // keydown handler's route guard. Registers empty rather than deleting the
    // key, so the source keeps its slot and the merge order stays stable
    // across a remount.
    return () => registerVisibleQuoteIds("sections", []);
  }, [registerVisibleQuoteIds, visibleIds]);

  // Detect media availability — if any quote has a video timecode link
  // in the original report, we assume media is available.
  // For now, default to true (the server can add this field later).
  const hasMedia = true;

  // The notice is for a lens with nothing to show: a failed re-read keeps what is drawn (R86).
  if (error && !data) {
    return (
      <section>
        <SectionHeading id="sections">{t("quotes.sections")}</SectionHeading>
        <ErrorNotice scope="lens" />
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <SectionHeading id="sections">{t("quotes.sections")}</SectionHeading>
        <p style={{ opacity: 0.5, padding: "1rem" }}>{t("quotes.loading")}</p>
      </section>
    );
  }

  if (data.sections.length === 0) {
    // Pre-pipeline (no completed run) leaves the SPA entirely — the
    // server-failure-page intercept handles that surface. Render
    // nothing here. Once a run has completed (lastRun !== null) but
    // produced zero quotes, surface the explanation in-SPA — that's a
    // legitimate "successful but empty" sub-state.
    if (lastRun === null) return null;
    return (
      <section>
        <SectionHeading id="sections">{t("quotes.sections")}</SectionHeading>
        <p className="bn-empty-state">{t("emptyState.postZeroQuotes")}</p>
      </section>
    );
  }

  return (
    <section className={handoverClass(handingOver)}>
      <SectionHeading id="sections" action={headingAction}>{t("quotes.sections")}</SectionHeading>
      {filteredSections.map((section) => {
        const anchor = groupAnchor("section", section.cluster_id);
        return (
          <QuoteGroup
            key={section.cluster_id}
            anchor={anchor}
            editKeyBase={`section-cluster-${section.cluster_id}`}
            label={section.screen_label}
            description={section.description}
            editedLabel={section.edited_label}
            editedDescription={section.edited_description}
            isNew={section.is_new}
            newSince={data.new_since ?? null}
            itemType="section"
            quotes={section.quotes}
            allQuotes={allQuotesMap.get(section.cluster_id)}
            tagVocabulary={tagVocabulary}
            groupedVocabulary={groupedVocabulary}
            tagGroupMap={tagGroupMap}
            hasMedia={hasMedia}
            transcriptCache={transcriptCache}
            hasModerator={data.has_moderator}
            highlight={highlightTermsOf(filterState)}
          />
        );
      })}
    </section>
  );
}
