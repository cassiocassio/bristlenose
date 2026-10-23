/**
 * QuoteThemes — React island for the "Themes" content area.
 *
 * Fetches quote data from the API and renders each theme as a
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
import { handoverClass, useLensRead } from "../hooks/useLensRead";
import { SectionHeading } from "../components";

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
    // See QuoteSections — same reasoning: clear on unmount so the registry
    // can't outlive the lens, registering empty to keep the merge order.
    return () => registerVisibleQuoteIds("themes", []);
  }, [registerVisibleQuoteIds, visibleIds]);

  const hasMedia = true;

  // The notice is for a lens with nothing to show: a failed re-read keeps what is drawn (R86).
  if (error && !data) {
    return (
      <section>
        <SectionHeading id="themes">{t("quotes.themes")}</SectionHeading>
        <ErrorNotice scope="lens" />
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <SectionHeading id="themes">{t("quotes.themes")}</SectionHeading>
        <p style={{ opacity: 0.5, padding: "1rem" }}>{t("quotes.loading")}</p>
      </section>
    );
  }

  if (data.themes.length === 0) return null;

  return (
    <section className={handoverClass(handingOver)}>
      <SectionHeading id="themes">{t("quotes.themes")}</SectionHeading>
      {filteredThemes.map((theme) => {
        const anchor = groupAnchor("theme", theme.theme_id);
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
            highlight={highlightTermsOf(filterState)}
          />
        );
      })}
    </section>
  );
}
