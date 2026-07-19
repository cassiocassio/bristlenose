/**
 * QuoteThemes — React island for the "Themes" content area.
 *
 * Fetches quote data from the API and renders each theme as a
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
import { useRefetching, refetchOverlayProps } from "../hooks/useRefetching";

interface QuoteThemesProps {
  projectId: string;
  /** See `QuoteSectionsProps.refreshKey`. */
  refreshKey?: number;
}

export function QuoteThemes({ projectId, refreshKey = 0 }: QuoteThemesProps) {
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
    // Also fetch codebook tag names for auto-suggest vocabulary
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
      .catch(() => {}); // Non-critical — silently ignore
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

  // Re-fetch on pipeline-run completion (LastRunStore bump).
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

  // Build a map of theme_id → original (unfiltered) quotes for the hidden counter.
  const allQuotesMap = useMemo(() => {
    if (!data) return new Map<number, QuoteResponse[]>();
    const map = new Map<number, QuoteResponse[]>();
    for (const t of data.themes) {
      map.set(t.theme_id, t.quotes);
    }
    return map;
  }, [data]);

  const filteredThemes = useMemo(() => {
    if (!data) return [];
    return data.themes
      .map((t) => ({
        ...t,
        quotes: filterQuotes(t.quotes, filterState),
      }))
      .filter((t) => t.quotes.length > 0 || (allQuotesMap.get(t.theme_id)?.some((q) => filterState.hidden[q.dom_id]) ?? false));
  }, [data, filterState, allQuotesMap]);

  // Register visible quote IDs for keyboard navigation.
  const { registerVisibleQuoteIds } = useFocus();
  const visibleIds = useMemo(
    () => filteredThemes.flatMap((t) => t.quotes.map((q) => q.dom_id)),
    [filteredThemes],
  );
  useEffect(() => {
    registerVisibleQuoteIds("themes", visibleIds);
  }, [registerVisibleQuoteIds, visibleIds]);

  const hasMedia = true;

  if (error) {
    return (
      <section>
        <h2 id="themes" className="section-heading">{t("quotes.themes")}</h2>
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          {t("quotes.failedToLoad", { error })}
        </p>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <h2 id="themes" className="section-heading">{t("quotes.themes")}</h2>
        <p style={{ opacity: 0.5, padding: "1rem" }}>{t("quotes.loading")}</p>
      </section>
    );
  }

  if (data.themes.length === 0) return null;

  return (
    <section {...refetchOverlayProps(isRefetching)}>
      <h2 id="themes" className="section-heading">{t("quotes.themes")}</h2>
      {filteredThemes.map((theme) => {
        const displayLabel = theme.edited_label ?? theme.theme_label;
        const anchor = `theme-${displayLabel.toLowerCase().replace(/ /g, "-")}`;
        return (
          <QuoteGroup
            key={theme.theme_id}
            anchor={anchor}
            editKeyBase={`theme-group-${theme.theme_id}`}
            label={theme.theme_label}
            description={theme.description}
            editedLabel={theme.edited_label}
            editedDescription={theme.edited_description}
            isNew={theme.is_new}
            newSince={data.new_since ?? null}
            itemType="theme"
            quotes={theme.quotes}
            allQuotes={allQuotesMap.get(theme.theme_id)}
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
