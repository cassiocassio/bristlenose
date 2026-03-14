/**
 * SidebarLayout — 6-column CSS grid wrapper for the dual-sidebar layout.
 *
 * When `active` is true (Quotes tab), renders the full grid:
 *   [toc-rail | toc-sidebar | center | minimap | tag-sidebar | tag-rail]
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
 * Column 4: Minimap — VS Code-style abstract overview, between center
 * content and the tag sidebar. Stays in same position whether tags are
 * open or closed.
 *
 * @module SidebarLayout
 */

import { useCallback, useEffect, useRef } from "react";
import {
  useSidebarStore,
  toggleToc,
  toggleTags,
  toggleBoth,
  openTocPush,
  closeToc,
  closeTags,
} from "../contexts/SidebarStore";
import { usePlaygroundStore } from "../contexts/PlaygroundStore";
import { TocSidebar } from "./TocSidebar";
import { TagSidebar } from "./TagSidebar";
import { Minimap } from "./Minimap";
import { useDragResize, MIN_WIDTH, MAX_WIDTH } from "../hooks/useDragResize";
import { useTocOverlay } from "../hooks/useTocOverlay";
import { Tooltip } from "./Tooltip";

// ── SVG icons (inline, 18×18) ─────────────────────────────────────────────

/** List icon — for TOC rail button */
function ListIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" focusable="false">
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
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M2.5 3.5h5l7 7-5 5-7-7z" />
      <circle cx="6" cy="7" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}

// ── Animation helper ──────────────────────────────────────────────────────

/**
 * Add `.animating` before state change, remove after transition completes.
 * Fallback timeout (200ms) covers 75ms grid transition + rAF scheduling.
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
  const fallback = setTimeout(cleanup, 200);

  // Run state change after animating class is applied (next frame)
  requestAnimationFrame(() => {
    action();
  });
}

// ── Animation registry ────────────────────────────────────────────────────
//
// Module-level object populated by SidebarLayout on mount. Allows
// useKeyboardShortcuts (which has no DOM ref access) to trigger
// animated sidebar toggles instead of bare store mutations.

export const sidebarAnimations = {
  toggleToc: toggleToc as () => void,
  toggleTags: toggleTags as () => void,
  toggleBoth: toggleBoth as () => void,
};

// ── Component ─────────────────────────────────────────────────────────────

interface SidebarLayoutProps {
  /** True when the sidebar grid should be active. */
  active: boolean;
  /** Custom left panel content (default: TocSidebar). */
  leftPanel?: React.ReactNode;
  /** Title for the left sidebar header (default: "Contents"). */
  leftPanelTitle?: string;
  /** Show minimap + tag sidebar + tag rail (default: true). */
  showRightSidebar?: boolean;
  children: React.ReactNode;
}

export function SidebarLayout({ active, leftPanel, leftPanelTitle, showRightSidebar = true, children }: SidebarLayoutProps) {
  const { tocMode, tagsOpen, tocWidth, tagsWidth } = useSidebarStore();
  const pg = usePlaygroundStore();
  const layoutRef = useRef<HTMLDivElement>(null);
  const tocRailRef = useRef<HTMLDivElement>(null);
  const tocRailBtnRef = useRef<HTMLButtonElement>(null);
  const tagRailBtnRef = useRef<HTMLButtonElement>(null);
  const tocPanelRef = useRef<HTMLDivElement>(null);
  const tagSidebarRef = useRef<HTMLDivElement>(null);
  // Guard against overlapping close animations.
  const closingRef = useRef(false);

  // Track previous open state for focus management.
  const tocOpen = tocMode !== "closed";
  const prevTocOpen = useRef(tocOpen);
  const prevTagsOpen = useRef(tagsOpen);

  // Hover-intent: 80ms delay before showing the blue accent highlight on
  // drag handles. Filters out casual mouse traversals (6px handle crossed
  // in <15ms at normal mousing speed) while feeling instant for deliberate
  // acquisition (~60ms+ dwell when slowing to grab).
  const hoverIntentTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onHandleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    clearTimeout(hoverIntentTimer.current);
    const el = e.currentTarget;
    hoverIntentTimer.current = setTimeout(() => el.classList.add("hover-intent"), 80);
  }, []);
  const onHandleMouseLeave = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    clearTimeout(hoverIntentTimer.current);
    e.currentTarget.classList.remove("hover-intent");
  }, []);

  // Drag-to-resize handles.
  const tocEdge = useDragResize({
    side: "toc", source: "sidebar", layoutRef, currentWidth: tocWidth,
  });
  const tagEdge = useDragResize({
    side: "tags", source: "sidebar", layoutRef, currentWidth: tagsWidth,
  });
  const tocRailDrag = useDragResize({
    side: "toc", source: "rail", layoutRef, currentWidth: tocWidth,
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
      layout.classList.remove("toc-closing", "overlay-ios");
      panel?.removeEventListener("animationend", onEnd);
      clearTimeout(fallback);
      closingRef.current = false;
      closeToc();
    };
    const onEnd = (e: AnimationEvent) => {
      if (e.target === panel) cleanup();
    };
    panel?.addEventListener("animationend", onEnd);
    const fallback = setTimeout(cleanup, 120);
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

  // Focus management: move focus when sidebars open/close.
  useEffect(() => {
    if (prevTocOpen.current !== tocOpen) {
      if (tocOpen) {
        // Just opened — focus first interactive element in sidebar.
        const target = tocPanelRef.current?.querySelector<HTMLElement>(
          ".sidebar-close, .toc-link",
        );
        target?.focus();
      } else {
        // Just closed — return focus to rail button.
        tocRailBtnRef.current?.focus();
      }
      prevTocOpen.current = tocOpen;
    }
  }, [tocOpen]);

  useEffect(() => {
    if (prevTagsOpen.current !== tagsOpen) {
      if (tagsOpen) {
        const target = tagSidebarRef.current?.querySelector<HTMLElement>(
          ".sidebar-close",
        );
        target?.focus();
      } else {
        tagRailBtnRef.current?.focus();
      }
      prevTagsOpen.current = tagsOpen;
    }
  }, [tagsOpen]);

  // Populate animation registry so keyboard shortcuts can animate.
  // Reads tocMode at call time to pick overlay-close vs grid-transition.
  useEffect(() => {
    sidebarAnimations.toggleToc = () => {
      if (tocMode === "overlay") {
        closeTocOverlayAnimated();
      } else {
        withAnimation(layoutRef.current, toggleToc);
      }
    };
    sidebarAnimations.toggleTags = () => {
      withAnimation(layoutRef.current, toggleTags);
    };
    sidebarAnimations.toggleBoth = () => {
      if (tocMode === "overlay") {
        closeTocOverlayAnimated();
        withAnimation(layoutRef.current, toggleTags);
      } else {
        withAnimation(layoutRef.current, toggleBoth);
      }
    };
    return () => {
      // Reset to bare store calls when SidebarLayout unmounts.
      sidebarAnimations.toggleToc = toggleToc;
      sidebarAnimations.toggleTags = toggleTags;
      sidebarAnimations.toggleBoth = toggleBoth;
    };
  }, [tocMode, closeTocOverlayAnimated]);

  // Escape key: close the sidebar that contains focus.
  useEffect(() => {
    if (!active) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const target = e.target as Node | null;
      if (tocOpen && tocPanelRef.current?.contains(target)) {
        e.preventDefault();
        handleCloseToc();
      } else if (tagsOpen && tagSidebarRef.current?.contains(target)) {
        e.preventDefault();
        handleCloseTags();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [active, tocOpen, tagsOpen, handleCloseToc, handleCloseTags]);

  if (!active) {
    return <>{children}</>;
  }

  const classes = ["layout"];
  if (tocMode === "push") classes.push("toc-open");
  if (tocMode === "overlay") {
    classes.push("toc-overlay");
    if (pg.overlayStyle === "ios") classes.push("overlay-ios");
  }
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
        <Tooltip content="Contents" shortcut={{ key: "[" }}>
          <button
            ref={tocRailBtnRef}
            className="rail-btn"
            onClick={handleOpenTocPush}
            onMouseEnter={overlay.onButtonMouseEnter}
            onMouseLeave={overlay.onButtonMouseLeave}
            aria-label="Toggle table of contents"
          >
            <ListIcon />
          </button>
        </Tooltip>
        {tocMode === "closed" && (
          <div
            className={`drag-handle toc-rail-drag${tocRailDrag.isDragging ? " active" : ""}`}
            onPointerDown={tocRailDrag.handlePointerDown}
            onMouseEnter={(e) => { onHandleMouseEnter(e); overlay.onDragHandleMouseEnter(); }}
            onMouseLeave={(e) => { onHandleMouseLeave(e); overlay.onDragHandleMouseLeave(); }}
          />
        )}
      </div>

      {/* Column 2: TOC sidebar panel */}
      <div
        ref={tocPanelRef}
        className="toc-sidebar"
        inert={!tocOpen ? true : undefined}
        onMouseEnter={overlay.onPanelMouseEnter}
        onMouseLeave={overlay.onPanelMouseLeave}
      >
        <div className="sidebar-header toc-sidebar-header">
          <span className="sidebar-title">{leftPanelTitle ?? "Contents"}</span>
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
          {leftPanel ?? <TocSidebar onOverlayClose={closeTocOverlayAnimated} />}
        </div>
        {(tocMode === "push" || tocMode === "overlay") && (
          <div
            className={`drag-handle toc-drag-handle${tocEdge.isDragging ? " active" : ""}`}
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={tocWidth}
            aria-valuemin={MIN_WIDTH}
            aria-valuemax={MAX_WIDTH}
            aria-label="Resize table of contents"
            tabIndex={0}
            onPointerDown={tocEdge.handlePointerDown}
            onKeyDown={tocEdge.handleKeyDown}
            onMouseEnter={onHandleMouseEnter}
            onMouseLeave={onHandleMouseLeave}
          />
        )}
      </div>

      {/* Column 3: Center — header, nav, content, footer */}
      <div className="center">
        {children}
      </div>

      {showRightSidebar && (
        <>
          {/* Column 4: Minimap (between center content and tag sidebar) */}
          <Minimap />

          {/* Column 5: Tag sidebar panel */}
          <div
            ref={tagSidebarRef}
            className="tag-sidebar"
            inert={!tagsOpen ? true : undefined}
          >
            <div className="sidebar-header tag-sidebar-header">
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
                role="separator"
                aria-orientation="vertical"
                aria-valuenow={tagsWidth}
                aria-valuemin={MIN_WIDTH}
                aria-valuemax={MAX_WIDTH}
                aria-label="Resize tag sidebar"
                tabIndex={0}
                onPointerDown={tagEdge.handlePointerDown}
                onKeyDown={tagEdge.handleKeyDown}
                onMouseEnter={onHandleMouseEnter}
                onMouseLeave={onHandleMouseLeave}
              />
            )}
          </div>

          {/* Column 6: Tag rail (rightmost — visible when tag sidebar is closed) */}
          <div className="tag-rail">
            <Tooltip content="Tags" shortcut={{ key: "]" }}>
              <button
                ref={tagRailBtnRef}
                className="rail-btn"
                onClick={handleToggleTags}
                aria-label="Toggle tag sidebar"
              >
                <TagIcon />
              </button>
            </Tooltip>
            {!tagsOpen && (
              <div
                className={`drag-handle tag-rail-drag${tagRailDrag.isDragging ? " active" : ""}`}
                onPointerDown={tagRailDrag.handlePointerDown}
                onMouseEnter={onHandleMouseEnter}
                onMouseLeave={onHandleMouseLeave}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
