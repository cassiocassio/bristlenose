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

interface TocSidebarProps {
  /** Animated close callback for overlay mode. When provided, TOC link clicks
   *  in overlay mode scroll first, then close after a brief delay so the user
   *  sees the scroll begin before the panel slides shut. */
  onOverlayClose?: () => void;
}

export function TocSidebar({ onOverlayClose }: TocSidebarProps) {
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

  // All IDs for scroll spy — only actual link targets, not group headings.
  // Group headings ("sections", "themes") are excluded because the scroll spy
  // would set activeId to a heading with no corresponding link, causing a
  // brief gap where nothing in the sidebar is highlighted.
  const allIds = useMemo(() => {
    const ids: string[] = [];
    ids.push(...sections.map((s) => s.id));
    ids.push(...themes.map((t) => t.id));
    return ids;
  }, [sections, themes]);

  const activeId = useScrollSpy(allIds);

  // Auto-scroll active TOC link into view within the sidebar.
  // Uses "instant" (not "smooth") to avoid competing scrollIntoView calls
  // when activeId changes rapidly during fast scrolling.
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        block: "nearest",
        behavior: "instant",
      });
    }
  }, [activeId]);

  // Click handler — smooth scroll to the target heading.
  // In overlay mode, let the scroll begin visibly, then close the panel.
  // The 400ms delay lets the user see the "you are here" highlight move
  // to the clicked heading before the panel slides shut — confirming
  // their intent was actioned.
  const handleClick = useCallback((e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (tocMode === "overlay") {
      if (onOverlayClose) {
        setTimeout(onOverlayClose, 400);
      } else {
        closeToc();
      }
    }
  }, [tocMode, onOverlayClose]);

  if (!data) return null;

  return (
    <nav aria-label="Table of contents">
      {sections.length > 0 && (
        <>
          <div className="toc-heading">Sections</div>
          {sections.map((entry) => (
            <a
              key={entry.id}
              href={`#${entry.id}`}
              className={`toc-link${activeId === entry.id ? " active" : ""}`}
              aria-current={activeId === entry.id ? "location" : undefined}
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
              aria-current={activeId === entry.id ? "location" : undefined}
              ref={activeId === entry.id ? activeRef : undefined}
              onClick={(e) => handleClick(e, entry.id)}
            >
              {entry.label}
            </a>
          ))}
        </>
      )}
    </nav>
  );
}
