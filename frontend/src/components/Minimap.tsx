/**
 * Minimap — VS Code-style abstract overview of the Quotes tab.
 *
 * Renders a narrow vertical strip (grid column 4) with pale grey lines
 * for quotes, darker grey lines for headings, and a blue translucent
 * viewport indicator. Scroll tracking, click-to-scroll, drag-to-scroll,
 * and parallax scrolling for long pages. At 2+ columns it mirrors the
 * live quote grid's column count (see design-minimap.md § Multi-column).
 *
 * Data comes from the same /api/projects/{id}/quotes endpoint — fetched
 * independently so the minimap renders without waiting for main content.
 *
 * @module Minimap
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { QuotesListResponse } from "../utils/types";
import { useProjectId } from "../hooks/useProjectId";
import { apiGet } from "../utils/api";

export function Minimap() {
  const projectId = useProjectId();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  // Column count mirrored from the live quote grid (1 = today's single strip).
  const [cols, setCols] = useState(1);
  const slotRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Fetch quotes data for minimap lines.
  useEffect(() => {
    apiGet<QuotesListResponse>("/quotes")
      .then((json) => setData(json))
      .catch(() => {});
  }, [projectId]);

  // Re-fetch when autocode tags change.
  useEffect(() => {
    const handler = () => {
      apiGet<QuotesListResponse>("/quotes")
        .then((json) => setData(json))
        .catch(() => {});
    };
    document.addEventListener("bn:tags-changed", handler);
    return () => document.removeEventListener("bn:tags-changed", handler);
  }, [projectId]);

  // Column detection — mirror the live quote grid's responsive column count.
  // Reads getComputedStyle(.quote-group).gridTemplateColumns track count from
  // the real grid; no independent breakpoint logic (follow the page, don't
  // lead it). Re-detects when the grid box resizes (window / sidebar / density)
  // via ResizeObserver. Falls back to 1 column — identical to today.
  useEffect(() => {
    if (!data) return;
    let ro: ResizeObserver | null = null;
    let raf = 0;
    let tries = 0;

    const detect = () => {
      const grid = document.querySelector<HTMLElement>(".quote-group");
      if (!grid) return;
      const tpl = getComputedStyle(grid).gridTemplateColumns;
      const n = tpl && tpl !== "none" ? Math.max(1, tpl.trim().split(/\s+/).length) : 1;
      setCols((prev) => (prev === n ? prev : n));
    };

    // The grid island mounts independently of the minimap, so it may not be in
    // the DOM yet — retry on rAF (bounded) until it appears, then observe it.
    const attach = () => {
      const grid = document.querySelector<HTMLElement>(".quote-group");
      if (grid && typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(detect);
        ro.observe(grid);
        detect();
      } else if (tries++ < 200) {
        raf = requestAnimationFrame(attach);
      }
    };

    attach();
    window.addEventListener("resize", detect, { passive: true });

    return () => {
      cancelAnimationFrame(raf);
      ro?.disconnect();
      window.removeEventListener("resize", detect);
    };
  }, [data]);

  // Scroll tracking — update viewport indicator position and parallax.
  useEffect(() => {
    if (!data) return;
    const content = contentRef.current;
    const viewport = viewportRef.current;
    if (!content || !viewport) return;

    let rafId = 0;

    const update = () => {
      const scrollY = window.scrollY;
      const scrollHeight = document.documentElement.scrollHeight;
      const viewportHeight = window.innerHeight;
      const contentHeight = content.scrollHeight;

      const maxScroll = Math.max(1, scrollHeight - viewportHeight);
      const scrollRatio = Math.min(1, Math.max(0, scrollY / maxScroll));
      const indicatorHeight = Math.max(8, (viewportHeight / scrollHeight) * contentHeight);

      if (contentHeight > viewportHeight) {
        // Parallax mode
        const parallaxOffset = scrollRatio * (contentHeight - viewportHeight);
        content.style.transform = `translateY(${-parallaxOffset}px)`;
        const indicatorTop = scrollRatio * (contentHeight - indicatorHeight);
        viewport.style.top = (indicatorTop - parallaxOffset) + "px";
      } else {
        // Simple mode
        content.style.transform = "none";
        const indicatorTop = scrollRatio * (contentHeight - indicatorHeight);
        viewport.style.top = indicatorTop + "px";
      }
      viewport.style.height = indicatorHeight + "px";
    };

    const onScroll = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(update);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    // Initial position after DOM has rendered minimap lines.
    requestAnimationFrame(update);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
    // cols is a dep so the indicator/parallax recompute when the minimap
    // reflows to a new column count (content height changes).
  }, [data, cols]);

  // Click-to-scroll — click on minimap background jumps the page.
  const handleClick = useCallback((e: React.MouseEvent) => {
    if (isDraggingRef.current) return;
    if (e.target === viewportRef.current) return;

    const slot = slotRef.current;
    const content = contentRef.current;
    if (!slot || !content) return;

    const rect = slot.getBoundingClientRect();
    const clickY = e.clientY - rect.top;
    const contentHeight = content.scrollHeight;
    const viewportHeight = window.innerHeight;
    const scrollHeight = document.documentElement.scrollHeight;
    const maxScroll = Math.max(1, scrollHeight - viewportHeight);

    // In parallax mode, solving the parallax equation algebraically gives
    // scrollRatio = pointerY / viewportHeight — no need to read the CSS
    // transform. In simple mode, ratio = pointerY / contentHeight.
    const ratio = contentHeight > viewportHeight
      ? Math.min(1, Math.max(0, clickY / viewportHeight))
      : Math.min(1, Math.max(0, clickY / contentHeight));

    window.scrollTo({ top: Math.max(0, ratio * maxScroll), behavior: "smooth" });
  }, []);

  // Drag-to-scroll — drag viewport indicator to scroll the page.
  const handleViewportPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;

    const slot = slotRef.current;
    const content = contentRef.current;
    if (!slot || !content) return;

    const contentHeight = content.scrollHeight;
    const viewportHeight = window.innerHeight;
    const scrollHeight = document.documentElement.scrollHeight;
    const maxScroll = Math.max(1, scrollHeight - viewportHeight);

    const onMove = (ev: PointerEvent) => {
      const rect = slot.getBoundingClientRect();
      const y = ev.clientY - rect.top;

      // Same algebraic simplification as click-to-scroll: in parallax
      // mode scrollRatio = y / viewportHeight, no CSS transform parsing.
      const ratio = contentHeight > viewportHeight
        ? Math.min(1, Math.max(0, y / viewportHeight))
        : Math.min(1, Math.max(0, y / contentHeight));

      window.scrollTo({ top: Math.max(0, ratio * maxScroll) });
    };

    const onUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }, []);

  // Empty placeholder while loading — keeps grid column from collapsing.
  if (!data) return <div className="minimap-slot" />;

  // At 2+ columns, mirror the grid: each section becomes an N-column block.
  // At 1 column, render exactly as before (no `multi` class, no CSS var).
  const multi = cols >= 2;
  const contentStyle = multi
    ? ({ "--bn-minimap-cols": cols } as CSSProperties)
    : undefined;

  return (
    // Minimap track; click maps to scroll position. Supplementary nav, content keyboard-scrollable elsewhere.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="minimap-slot" ref={slotRef} onClick={handleClick}>
      <div
        className={multi ? "bn-minimap-content multi" : "bn-minimap-content"}
        ref={contentRef}
        style={contentStyle}
      >
        {/* Sections group */}
        {data.sections.length > 0 && (
          <>
            <div className="bn-minimap-group-heading" />
            {data.sections.map((s) => (
              <div key={s.cluster_id} className="bn-minimap-section">
                <div className="bn-minimap-heading" />
                {s.quotes.map((_, i) => (
                  <div key={i} className="bn-minimap-quote" />
                ))}
              </div>
            ))}
          </>
        )}
        {/* Division between sections and themes */}
        {data.sections.length > 0 && data.themes.length > 0 && (
          <div className="bn-minimap-division" />
        )}
        {/* Themes group */}
        {data.themes.length > 0 && (
          <>
            <div className="bn-minimap-group-heading" />
            {data.themes.map((t) => (
              <div key={t.theme_id} className="bn-minimap-section">
                <div className="bn-minimap-heading" />
                {t.quotes.map((_, i) => (
                  <div key={i} className="bn-minimap-quote" />
                ))}
              </div>
            ))}
          </>
        )}
      </div>
      <div
        className="bn-minimap-viewport"
        ref={viewportRef}
        onPointerDown={handleViewportPointerDown}
      />
    </div>
  );
}
