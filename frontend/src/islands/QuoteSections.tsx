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
import { getCodebook } from "../utils/api";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import type { QuoteResponse, QuotesListResponse } from "../utils/types";
import { initFromQuotes, useQuotesStore } from "../contexts/QuotesContext";
import { useFocus } from "../contexts/FocusContext";
import { filterQuotes } from "../utils/filter";
import { QuoteGroup } from "./QuoteGroup";

interface QuoteSectionsProps {
  projectId: string;
}

export function QuoteSections({ projectId }: QuoteSectionsProps) {
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);

  const fetchQuotes = useCallback((replace = false) => {
    fetch(`/api/projects/${projectId}/quotes`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: QuotesListResponse) => {
        setData(json);
        const allQuotes = [
          ...json.sections.flatMap((s) => s.quotes),
          ...json.themes.flatMap((t) => t.quotes),
        ];
        initFromQuotes(allQuotes, replace);
      })
      .catch((err: Error) => setError(err.message));
    getCodebook()
      .then((cb) => setCodebookTagNames(cb.all_tag_names))
      .catch(() => {});
  }, [projectId]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  // Re-fetch when another island (CodebookPanel) applies bulk autocode tags.
  useEffect(() => {
    const handler = () => fetchQuotes(true);
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, [fetchQuotes]);

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
        <h2 id="sections">Sections</h2>
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          Failed to load quotes: {error}
        </p>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <h2 id="sections">Sections</h2>
        <p style={{ opacity: 0.5, padding: "1rem" }}>Loading quotes&hellip;</p>
      </section>
    );
  }

  if (data.sections.length === 0) return null;

  return (
    <section>
      <h2 id="sections">Sections</h2>
      {filteredSections.map((section) => {
        const anchor = `section-${section.screen_label.toLowerCase().replace(/ /g, "-")}`;
        return (
          <QuoteGroup
            key={section.cluster_id}
            anchor={anchor}
            label={section.screen_label}
            description={section.description}
            itemType="section"
            quotes={section.quotes}
            allQuotes={allQuotesMap.get(section.cluster_id)}
            tagVocabulary={tagVocabulary}
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
