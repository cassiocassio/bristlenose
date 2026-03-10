/**
 * Minimap — VS Code-style abstract overview of the Quotes tab.
 *
 * Renders a narrow vertical strip (grid column 6) with pale grey lines
 * for quotes, darker grey lines for headings, and a blue translucent
 * viewport indicator. Scroll tracking, click-to-scroll, drag-to-scroll,
 * and parallax scrolling for long pages.
 *
 * Data comes from the same /api/projects/{id}/quotes endpoint — fetched
 * independently so the minimap renders without waiting for main content.
 *
 * @module Minimap
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { QuotesListResponse } from "../utils/types";
import { useProjectId } from "../hooks/useProjectId";

export function Minimap() {
  const projectId = useProjectId();
  const [data, setData] = useState<QuotesListResponse | null>(null);
  const slotRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Fetch quotes data for minimap lines.
  useEffect(() => {
    fetch(`/api/projects/${projectId}/quotes`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: QuotesListResponse) => setData(json))
      .catch(() => {});
  }, [projectId]);

  // Re-fetch when autocode tags change.
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
  }, [data]);

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

  return (
    <div className="minimap-slot" ref={slotRef} onClick={handleClick}>
      <div className="bn-minimap-content" ref={contentRef}>
        {/* Sections group */}
        {data.sections.length > 0 && (
          <>
            <div className="bn-minimap-group-heading" />
            {data.sections.map((s) => (
              <div key={s.cluster_id}>
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
              <div key={t.theme_id}>
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
