/**
 * QuoteSections — React island for the "Sections" (screen-specific
 * findings) content area.
 *
 * Fetches quote data from the API and renders each section as a
 * QuoteGroup with editable headings, descriptions, and interactive
 * quote cards.
 */

import { useCallback, useEffect, useState, useMemo } from "react";
import { getCodebook } from "../utils/api";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import type { QuotesListResponse } from "../utils/types";
import { QuoteGroup } from "./QuoteGroup";

interface QuoteSectionsProps {
  projectId: string;
}

export function QuoteSections({ projectId }: QuoteSectionsProps) {
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codebookTagNames, setCodebookTagNames] = useState<string[]>([]);
  // Incremented on each re-fetch to force QuoteGroup remount (resets local state).
  const [dataVersion, setDataVersion] = useState(0);

  const fetchQuotes = useCallback(() => {
    fetch(`/api/projects/${projectId}/quotes`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: QuotesListResponse) => {
        setData(json);
        setDataVersion((v) => v + 1);
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
    const handler = () => fetchQuotes();
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
      {data.sections.map((section) => {
        const anchor = `section-${section.screen_label.toLowerCase().replace(/ /g, "-")}`;
        return (
          <QuoteGroup
            key={`${section.cluster_id}-v${dataVersion}`}
            anchor={anchor}
            label={section.screen_label}
            description={section.description}
            itemType="section"
            quotes={section.quotes}
            tagVocabulary={tagVocabulary}
            hasMedia={hasMedia}
            transcriptCache={transcriptCache}
          />
        );
      })}
    </section>
  );
}
