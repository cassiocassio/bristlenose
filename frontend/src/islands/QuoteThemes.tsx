/**
 * QuoteThemes — React island for the "Themes" content area.
 *
 * Fetches quote data from the API and renders each theme as a
 * QuoteGroup with editable headings, descriptions, and interactive
 * quote cards.  On fetch, populates the shared QuotesStore so
 * mutations are visible across all quote islands.
 */

import { useCallback, useEffect, useState, useMemo } from "react";
import { getCodebook } from "../utils/api";
import type { QuotesListResponse } from "../utils/types";
import { initFromQuotes } from "../contexts/QuotesContext";
import { QuoteGroup } from "./QuoteGroup";

interface QuoteThemesProps {
  projectId: string;
}

export function QuoteThemes({ projectId }: QuoteThemesProps) {
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
    // Also fetch codebook tag names for auto-suggest vocabulary
    getCodebook()
      .then((cb) => setCodebookTagNames(cb.all_tag_names))
      .catch(() => {}); // Non-critical — silently ignore
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

  const hasMedia = true;

  if (error) {
    return (
      <section>
        <h2 id="themes">Themes</h2>
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          Failed to load quotes: {error}
        </p>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <h2 id="themes">Themes</h2>
        <p style={{ opacity: 0.5, padding: "1rem" }}>Loading quotes&hellip;</p>
      </section>
    );
  }

  if (data.themes.length === 0) return null;

  return (
    <section>
      <h2 id="themes">Themes</h2>
      {data.themes.map((theme) => {
        const anchor = `theme-${theme.theme_label.toLowerCase().replace(/ /g, "-")}`;
        return (
          <QuoteGroup
            key={theme.theme_id}
            anchor={anchor}
            label={theme.theme_label}
            description={theme.description}
            itemType="theme"
            quotes={theme.quotes}
            tagVocabulary={tagVocabulary}
            hasMedia={hasMedia}
          />
        );
      })}
    </section>
  );
}
