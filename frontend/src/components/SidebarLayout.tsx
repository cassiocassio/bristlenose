/**
 * SidebarLayout — 6-column CSS grid wrapper for the dual-sidebar layout.
 *
 * When `active` is true (Quotes tab), renders the full grid:
 *   [toc-rail | toc-sidebar | center | tag-sidebar | tag-rail | minimap]
 *
 * When `active` is false (all other tabs), renders a plain pass-through
 * wrapper with no grid — children render normally.
 *
 * Left panel: TocSidebar (sections + themes with scroll-spy).
 *   - Push mode (State C): click list icon, grid column expands, content narrows.
 *   - Overlay mode (State B): hover rail 400ms or click rail area,
 *     panel floats over content via position:fixed.
 *
 * Right panel: TagSidebar (codebook tree with tag checkboxes). Push only.
 *
 * Column 6: Minimap slot — empty placeholder for future scrollbar-style
 * minimap visualization.
 *
 * @module SidebarLayout
 */

import { useCallback, useRef } from "react";
import {
  useSidebarStore,
  toggleTags,
  openTocPush,
  closeToc,
  closeTags,
} from "../contexts/SidebarStore";
import { usePlaygroundStore } from "../contexts/PlaygroundStore";
import { TocSidebar } from "./TocSidebar";
import { TagSidebar } from "./TagSidebar";
import { Minimap } from "./Minimap";
import { useDragResize } from "../hooks/useDragResize";
import { useTocOverlay } from "../hooks/useTocOverlay";

// ── SVG icons (inline, 18×18) ─────────────────────────────────────────────

/** List icon — for TOC rail button */
function ListIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <line x1="5.5" y1="4.5" x2="14" y2="4.5" />
      <line x1="5.5" y1="9" x2="14" y2="9" />
      <line x1="5.5" y1="13.5" x2="14" y2="13.5" />
      <circle cx="3" cy="4.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="3" cy="9" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="3" cy="13.5" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Tag icon — for tag rail button */
function TagIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 3.5h5l7 7-5 5-7-7z" />
      <circle cx="6" cy="7" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}

// ── Animation helper ──────────────────────────────────────────────────────

/**
 * Add `.animating` before state change, remove after transition completes.
 * If no transition fires within 300ms (safety margin), remove anyway.
 */
function withAnimation(
  layoutEl: HTMLElement | null,
  action: () => void,
): void {
  if (!layoutEl) {
    action();
    return;
  }
  layoutEl.classList.add("animating");

  const cleanup = () => {
    layoutEl.classList.remove("animating");
    layoutEl.removeEventListener("transitionend", onEnd);
    clearTimeout(fallback);
  };
  const onEnd = (e: TransitionEvent) => {
    if (e.target === layoutEl) cleanup();
  };
  layoutEl.addEventListener("transitionend", onEnd);
  const fallback = setTimeout(cleanup, 300);

  // Run state change after animating class is applied (next microtask)
  requestAnimationFrame(() => {
    action();
  });
}

// ── Component ─────────────────────────────────────────────────────────────

interface SidebarLayoutProps {
  /** True when the sidebar grid should be active (Quotes tab). */
  active: boolean;
  children: React.ReactNode;
}

export function SidebarLayout({ active, children }: SidebarLayoutProps) {
  const { tocMode, tagsOpen, tocWidth, tagsWidth } = useSidebarStore();
  const pg = usePlaygroundStore();
  const layoutRef = useRef<HTMLDivElement>(null);
  const tocRailRef = useRef<HTMLDivElement>(null);
  const tocPanelRef = useRef<HTMLDivElement>(null);
  // Guard against overlapping close animations.
  const closingRef = useRef(false);

  // Drag-to-resize handles.
  const tocEdge = useDragResize({
    side: "toc", source: "sidebar", layoutRef, currentWidth: tocWidth,
  });
  const tagEdge = useDragResize({
    side: "tags", source: "sidebar", layoutRef, currentWidth: tagsWidth,
  });
  const tagRailDrag = useDragResize({
    side: "tags", source: "rail", layoutRef, currentWidth: tagsWidth,
  });

  // ── Animated overlay close ────────────────────────────────────────────

  /** Slide the overlay panel out before updating store (fly-out animation). */
  const closeTocOverlayAnimated = useCallback(() => {
    const layout = layoutRef.current;
    const panel = tocPanelRef.current;
    if (!layout || tocMode !== "overlay" || closingRef.current) {
      closeToc();
      return;
    }
    closingRef.current = true;
    layout.classList.add("toc-closing");

    const cleanup = () => {
      layout.classList.remove("toc-closing");
      panel?.removeEventListener("transitionend", onEnd);
      clearTimeout(fallback);
      closingRef.current = false;
      closeToc();
    };
    const onEnd = (e: TransitionEvent) => {
      if (e.target === panel) cleanup();
    };
    panel?.addEventListener("transitionend", onEnd);
    const fallback = setTimeout(cleanup, 400);
  }, [tocMode]);

  // Overlay hook for the TOC rail hover-to-peek.
  const overlay = useTocOverlay({
    tocMode,
    railRef: tocRailRef,
    panelRef: tocPanelRef,
    onClose: closeTocOverlayAnimated,
    hoverDelay: pg.hoverDelay ?? undefined,
    leaveGrace: pg.leaveGrace ?? undefined,
  });

  const handleOpenTocPush = useCallback(() => {
    withAnimation(layoutRef.current, openTocPush);
  }, []);

  const handleToggleTags = useCallback(() => {
    withAnimation(layoutRef.current, toggleTags);
  }, []);

  const handleCloseToc = useCallback(() => {
    if (tocMode === "overlay") {
      closeTocOverlayAnimated();
    } else {
      withAnimation(layoutRef.current, closeToc);
    }
  }, [tocMode, closeTocOverlayAnimated]);

  const handleCloseTags = useCallback(() => {
    withAnimation(layoutRef.current, closeTags);
  }, []);

  if (!active) {
    return <>{children}</>;
  }

  const classes = ["layout"];
  if (tocMode === "push") classes.push("toc-open");
  if (tocMode === "overlay") classes.push("toc-overlay");
  if (tagsOpen) classes.push("tags-open");

  const style: Record<string, string> = {};
  if (tocMode === "push" || tocMode === "overlay") {
    style["--toc-width"] = `${tocWidth}px`;
  }
  if (tagsOpen) style["--tags-width"] = `${tagsWidth}px`;

  return (
    <div ref={layoutRef} className={classes.join(" ")} style={style}>
      {/* Column 1: TOC rail (visible when TOC is closed or in overlay mode) */}
      <div
        ref={tocRailRef}
        className="toc-rail"
        onMouseEnter={overlay.onRailMouseEnter}
        onMouseLeave={overlay.onRailMouseLeave}
        onClick={overlay.onRailAreaClick}
      >
        <button
          className="rail-btn"
          onClick={handleOpenTocPush}
          onMouseEnter={overlay.onButtonMouseEnter}
          onMouseLeave={overlay.onButtonMouseLeave}
          title="Table of contents ( [ )"
          aria-label="Toggle table of contents"
        >
          <ListIcon />
        </button>
      </div>

      {/* Column 2: TOC sidebar panel */}
      <div
        ref={tocPanelRef}
        className="toc-sidebar"
        onMouseEnter={overlay.onPanelMouseEnter}
        onMouseLeave={overlay.onPanelMouseLeave}
      >
        <div className="toc-sidebar-header">
          <span className="sidebar-title">Contents</span>
          <button
            className="sidebar-close"
            onClick={handleCloseToc}
            title="Close"
            aria-label="Close table of contents"
          >
            ×
          </button>
        </div>
        <div className="toc-sidebar-body">
          <TocSidebar />
        </div>
        {(tocMode === "push" || tocMode === "overlay") && (
          <div
            className={`drag-handle toc-drag-handle${tocEdge.isDragging ? " active" : ""}`}
            onPointerDown={tocEdge.handlePointerDown}
          />
        )}
      </div>

      {/* Column 3: Center — header, nav, content, footer */}
      <div className="center">
        {children}
      </div>

      {/* Column 4: Tag sidebar panel */}
      <div className="tag-sidebar">
        <div className="tag-sidebar-header">
          <span className="sidebar-title">Tags</span>
          <button
            className="sidebar-close"
            onClick={handleCloseTags}
            title="Close"
            aria-label="Close tag sidebar"
          >
            ×
          </button>
        </div>
        <TagSidebar />
        {tagsOpen && (
          <div
            className={`drag-handle tag-drag-handle${tagEdge.isDragging ? " active" : ""}`}
            onPointerDown={tagEdge.handlePointerDown}
          />
        )}
      </div>

      {/* Column 5: Tag rail (visible when tag sidebar is closed) */}
      <div className="tag-rail">
        <button
          className="rail-btn"
          onClick={handleToggleTags}
          title="Tags ( ] )"
          aria-label="Toggle tag sidebar"
        >
          <TagIcon />
        </button>
        {!tagsOpen && (
          <div
            className={`drag-handle tag-rail-drag${tagRailDrag.isDragging ? " active" : ""}`}
            onPointerDown={tagRailDrag.handlePointerDown}
          />
        )}
      </div>

      {/* Column 6: Minimap */}
      <Minimap />
    </div>
  );
}
