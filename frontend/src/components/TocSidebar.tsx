/**
 * TocSidebar — table of contents for the Quotes tab left sidebar.
 *
 * Two groups of links: Sections and Themes, matching the quote groupings
 * on the page. Active link tracked via useScrollSpy, auto-scrolled into
 * view. Click scrolls smoothly to the heading.
 *
 * Data comes from the same /api/projects/{id}/quotes endpoint — we
 * fetch independently so the TOC renders even if the main content is
 * still loading.
 *
 * @module TocSidebar
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { QuotesListResponse } from "../utils/types";
import { useProjectId } from "../hooks/useProjectId";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { useSidebarStore, closeToc } from "../contexts/SidebarStore";

// ── Slug helper (mirrors QuoteSections/QuoteThemes) ───────────────────────

function toAnchor(prefix: string, label: string): string {
  return `${prefix}-${label.toLowerCase().replace(/ /g, "-")}`;
}

// ── TOC entry type ────────────────────────────────────────────────────────

interface TocEntry {
  id: string;
  label: string;
}

// ── Component ─────────────────────────────────────────────────────────────

export function TocSidebar() {
  const projectId = useProjectId();
  const { tocMode } = useSidebarStore();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const activeRef = useRef<HTMLAnchorElement | null>(null);

  // Fetch quotes data for TOC entries.
  useEffect(() => {
    fetch(`/api/projects/${projectId}/quotes`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: QuotesListResponse) => setData(json))
      .catch(() => {
        // Silently fail — the main content area shows the error.
      });
  }, [projectId]);

  // Re-fetch when autocode tags change (same event QuoteSections listens to).
  useEffect(() => {
    const handler = () => {
      fetch(`/api/projects/${projectId}/quotes`)
        .then((res) => res.json())
        .then((json: QuotesListResponse) => setData(json))
        .catch(() => {});
    };
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, [projectId]);

  // Build TOC entries from API data.
  const sections: TocEntry[] = useMemo(() => {
    if (!data) return [];
    return data.sections.map((s) => ({
      id: toAnchor("section", s.screen_label),
      label: s.screen_label,
    }));
  }, [data]);

  const themes: TocEntry[] = useMemo(() => {
    if (!data) return [];
    return data.themes.map((t) => ({
      id: toAnchor("theme", t.theme_label),
      label: t.theme_label,
    }));
  }, [data]);

  // All IDs for scroll spy (in DOM order: sections heading, sections, themes heading, themes).
  const allIds = useMemo(() => {
    const ids: string[] = [];
    if (sections.length > 0) {
      ids.push("sections");
      ids.push(...sections.map((s) => s.id));
    }
    if (themes.length > 0) {
      ids.push("themes");
      ids.push(...themes.map((t) => t.id));
    }
    return ids;
  }, [sections, themes]);

  const activeId = useScrollSpy(allIds);

  // Auto-scroll active TOC link into view within the sidebar.
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [activeId]);

  // Click handler — smooth scroll to the target heading.
  // In overlay mode, close the overlay after initiating the scroll.
  const handleClick = useCallback((e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (tocMode === "overlay") {
      closeToc();
    }
  }, [tocMode]);

  if (!data) return null;

  return (
    <>
      {sections.length > 0 && (
        <>
          <div className="toc-heading">Sections</div>
          {sections.map((entry) => (
            <a
              key={entry.id}
              href={`#${entry.id}`}
              className={`toc-link${activeId === entry.id ? " active" : ""}`}
              ref={activeId === entry.id ? activeRef : undefined}
              onClick={(e) => handleClick(e, entry.id)}
            >
              {entry.label}
            </a>
          ))}
        </>
      )}
      {themes.length > 0 && (
        <>
          <div className="toc-heading">Themes</div>
          {themes.map((entry) => (
            <a
              key={entry.id}
              href={`#${entry.id}`}
              className={`toc-link${activeId === entry.id ? " active" : ""}`}
              ref={activeId === entry.id ? activeRef : undefined}
              onClick={(e) => handleClick(e, entry.id)}
            >
              {entry.label}
            </a>
          ))}
        </>
      )}
    </>
  );
}
