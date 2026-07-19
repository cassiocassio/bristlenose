/**
 * QuoteSections — React island for the "Sections" (screen-specific
 * findings) content area.
 *
 * Fetches quote data from the API and renders each section as a
 * QuoteGroup with editable headings, descriptions, and interactive
 * quote cards.  On fetch, populates the shared QuotesStore so
 * mutations are visible across all quote islands.
 */

import { useCallback, useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { apiGet, getCodebook } from "../utils/api";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import type { QuoteResponse, QuotesListResponse } from "../utils/types";
import type { TagGroupInfo } from "./QuoteGroup";
import type { TagVocabularyGroup } from "../components";
import { initFromQuotes, initHeadingEdits, useQuotesStore } from "../contexts/QuotesContext";
import { useFocus } from "../contexts/FocusContext";
import { filterQuotes } from "../utils/filter";
import { QuoteGroup } from "./QuoteGroup";
import { useLastRun } from "../contexts/LastRunStore";
import { useRefetching, refetchOverlayProps } from "../hooks/useRefetching";

interface QuoteSectionsProps {
  projectId: string;
  /**
   * Bumped by `LastRunStore` when a pipeline run completes. When this
   * changes, the island refetches `/quotes` and replaces QuotesStore.
   * Optional so non-SPA mounts (legacy island mode) continue to work.
   */
  refreshKey?: number;
}

export function QuoteSections({ projectId, refreshKey = 0 }: QuoteSectionsProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);
  const [tagGroupMap, setTagGroupMap] = useState<Record<string, TagGroupInfo>>({});
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const { isRefetching, beginRefetch, endRefetch } = useRefetching();
  const { lastRun } = useLastRun();

  const fetchQuotes = useCallback((replace = false) => {
    apiGet<QuotesListResponse>("/quotes")
      .then((json) => {
        setData(json);
        const allQuotes = [
          ...json.sections.flatMap((s) => s.quotes),
          ...json.themes.flatMap((t) => t.quotes),
        ];
        initFromQuotes(allQuotes, replace, json.uncategorised);
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
          for (let i = 0; i < g.tags.length; i++) {
            map[g.tags[i].name.toLowerCase()] = {
              group: g.name,
              colour_set: g.colour_set,
              colour_index: g.tags[i].colour_index,
            };
            tags.push({ name: g.tags[i].name, colourIndex: g.tags[i].colour_index });
          }
          groups.push({ groupName: g.name, colourSet: g.colour_set, tags });
        }
        setTagGroupMap(map);
        setGroupedVocabulary(groups);
      })
      .catch(() => {});
  }, [projectId, endRefetch]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  // Re-fetch when another island (CodebookPanel) applies bulk autocode tags.
  useEffect(() => {
    const handler = () => fetchQuotes(true);
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, [fetchQuotes]);

  // Re-fetch on pipeline-run completion (LastRunStore bump). Skip the
  // initial mount — the dedicated mount effect above handles that.
  useEffect(() => {
    if (refreshKey === 0) return;
    beginRefetch();
    fetchQuotes(true);
  }, [refreshKey, fetchQuotes, beginRefetch]);

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
  const filterState = useMemo(
    () => ({
      searchQuery: store.searchQuery,
      viewMode: store.viewMode,
      tagFilter: store.tagFilter,
      hidden: store.hidden,
      starred: store.starred,
      tags: store.tags,
    }),
    [store.searchQuery, store.viewMode, store.tagFilter, store.hidden, store.starred, store.tags],
  );

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
  }, [registerVisibleQuoteIds, visibleIds]);

  // Detect media availability — if any quote has a video timecode link
  // in the original report, we assume media is available.
  // For now, default to true (the server can add this field later).
  const hasMedia = true;

  if (error) {
    return (
      <section>
        <h2 id="sections" className="section-heading">{t("quotes.sections")}</h2>
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          {t("quotes.failedToLoad", { error })}
        </p>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <h2 id="sections" className="section-heading">{t("quotes.sections")}</h2>
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
        <h2 id="sections" className="section-heading">{t("quotes.sections")}</h2>
        <p className="bn-empty-state">{t("emptyState.postZeroQuotes")}</p>
      </section>
    );
  }

  return (
    <section {...refetchOverlayProps(isRefetching)}>
      <h2 id="sections" className="section-heading">{t("quotes.sections")}</h2>
      {filteredSections.map((section) => {
        // Scroll anchor tracks the *displayed* label (rename if present).
        const displayLabel = section.edited_label ?? section.screen_label;
        const anchor = `section-${displayLabel.toLowerCase().replace(/ /g, "-")}`;
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
            searchQuery={store.searchQuery}
          />
        );
      })}
    </section>
  );
}
