/**
 * useDragResize — pointer-event state machine for sidebar drag-to-resize.
 *
 * Four instances per layout: two sidebar-edge handles (resize when open)
 * and two rail-edge handles (drag-to-open from collapsed state).
 *
 * During drag, CSS custom properties are updated directly on the layout
 * element (no React re-render) for 60fps performance. Store actions are
 * called only on pointerup to persist the final width.
 *
 * @module useDragResize
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
  closeToc,
  closeTags,
  openToc,
  openTags,
  setTocWidth,
  setTagsWidth,
} from "../contexts/SidebarStore";

// ── Constants ────────────────────────────────────────────────────────────

const MIN_WIDTH = 200;
const MAX_WIDTH = 320;
const SNAP_CLOSE_THRESHOLD = 80;
const RAIL_OPEN_THRESHOLD = 20;

// ── Types ────────────────────────────────────────────────────────────────

export interface UseDragResizeOptions {
  /** Which sidebar this handle controls. */
  side: "toc" | "tags";
  /** Whether this handle sits on the sidebar edge or the rail edge. */
  source: "sidebar" | "rail";
  /** Ref to the layout root element (for direct CSS var manipulation). */
  layoutRef: React.RefObject<HTMLElement | null>;
  /** Current sidebar width from the store (used as startWidth for sidebar handles). */
  currentWidth: number;
}

export interface UseDragResizeReturn {
  /** Attach to the drag handle div's onPointerDown. */
  handlePointerDown: (e: React.PointerEvent) => void;
  /** Whether this handle is actively being dragged (for `.active` class). */
  isDragging: boolean;
}

// ── Hook ─────────────────────────────────────────────────────────────────

export function useDragResize({
  side,
  source,
  layoutRef,
  currentWidth,
}: UseDragResizeOptions): UseDragResizeReturn {
  const [isDragging, setIsDragging] = useState(false);

  // Ref to the cleanup function so useEffect can tear down on unmount.
  const cleanupRef = useRef<(() => void) | null>(null);

  // Stable refs for values needed inside pointer listeners.
  const currentWidthRef = useRef(currentWidth);
  currentWidthRef.current = currentWidth;

  const cssVar = side === "toc" ? "--toc-width" : "--tags-width";
  const openFn = side === "toc" ? openToc : openTags;
  const closeFn = side === "toc" ? closeToc : closeTags;
  const setWidthFn = side === "toc" ? setTocWidth : setTagsWidth;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const layout = layoutRef.current;
      if (!layout) return;

      const startX = e.clientX;
      const startWidth = source === "sidebar" ? currentWidthRef.current : 0;
      let lastWidth = startWidth;
      let railConfirmed = false;

      setIsDragging(true);

      if (source === "sidebar") {
        document.body.classList.add("dragging");
        layout.classList.remove("animating");
      }

      const computeWidth = (clientX: number): number => {
        const delta =
          side === "toc" ? clientX - startX : startX - clientX;
        return startWidth + delta;
      };

      const onMove = (ev: PointerEvent) => {
        const raw = computeWidth(ev.clientX);

        if (source === "rail" && !railConfirmed) {
          if (Math.abs(raw) < RAIL_OPEN_THRESHOLD) return;
          // Crossed threshold — open the sidebar.
          railConfirmed = true;
          document.body.classList.add("dragging");
          openFn();
          // Remove animating so the open doesn't transition during drag.
          // Need a rAF because openFn triggers a React re-render that may
          // re-add .animating via withAnimation in SidebarLayout — but
          // since openFn is called directly (not through withAnimation),
          // .animating won't be added. Defensive removal anyway.
          requestAnimationFrame(() => layout.classList.remove("animating"));
        }

        if (source === "rail" && !railConfirmed) return;

        if (raw < SNAP_CLOSE_THRESHOLD) {
          layout.style.setProperty(cssVar, "0px");
          lastWidth = 0;
        } else {
          const clamped = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, raw));
          layout.style.setProperty(cssVar, `${clamped}px`);
          lastWidth = clamped;
        }
      };

      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        cleanupRef.current = null;
        document.body.classList.remove("dragging");
        setIsDragging(false);

        if (source === "rail" && !railConfirmed) {
          // Never crossed the threshold — treat as a no-op.
          return;
        }

        if (lastWidth < SNAP_CLOSE_THRESHOLD) {
          // Snap-close with animation.
          layout.classList.add("animating");
          closeFn();
          const removeAnimating = () => {
            layout.classList.remove("animating");
            layout.removeEventListener("transitionend", onTransitionEnd);
            clearTimeout(fallback);
          };
          const onTransitionEnd = (te: TransitionEvent) => {
            if (te.target === layout) removeAnimating();
          };
          layout.addEventListener("transitionend", onTransitionEnd);
          const fallback = setTimeout(removeAnimating, 300);
        } else {
          setWidthFn(lastWidth);
        }
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);

      cleanupRef.current = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        document.body.classList.remove("dragging");
      };
    },
    [side, source, layoutRef, cssVar, openFn, closeFn, setWidthFn],
  );

  // Cleanup on unmount if drag is in progress.
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  return { handlePointerDown, isDragging };
}
