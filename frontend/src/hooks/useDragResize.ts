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
  openTocPush,
  openTags,
  setTocWidth,
  setTagsWidth,
} from "../contexts/SidebarStore";

// ── Constants ────────────────────────────────────────────────────────────

export const MIN_WIDTH = 200;
export const MAX_WIDTH = 320;
const SNAP_CLOSE_THRESHOLD = 80;
const RAIL_SNAP_OPEN_THRESHOLD = 60;
const RESIZE_STEP = 10;

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
  /** Minimum sidebar width in px. Defaults to MIN_WIDTH (200). */
  minWidth?: number;
  /** Maximum sidebar width in px. Defaults to MAX_WIDTH (320). */
  maxWidth?: number;
}

export interface UseDragResizeReturn {
  /** Attach to the drag handle div's onPointerDown. */
  handlePointerDown: (e: React.PointerEvent) => void;
  /** Attach to the drag handle div's onKeyDown for keyboard resize. */
  handleKeyDown: (e: React.KeyboardEvent) => void;
  /** Whether this handle is actively being dragged (for `.active` class). */
  isDragging: boolean;
}

// ── Hook ─────────────────────────────────────────────────────────────────

export function useDragResize({
  side,
  source,
  layoutRef,
  currentWidth,
  minWidth = MIN_WIDTH,
  maxWidth = MAX_WIDTH,
}: UseDragResizeOptions): UseDragResizeReturn {
  const [isDragging, setIsDragging] = useState(false);

  // Ref to the cleanup function so useEffect can tear down on unmount.
  const cleanupRef = useRef<(() => void) | null>(null);

  // Stable refs for values needed inside pointer listeners.
  const currentWidthRef = useRef(currentWidth);
  currentWidthRef.current = currentWidth;

  const cssVar = side === "toc" ? "--toc-width" : "--tags-width";
  const openFn = side === "toc" ? openTocPush : openTags;
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

      // Rail drag: CSS class name used as a temporary overlay during drag.
      const railDragClass = side === "toc" ? "toc-rail-dragging" : "tags-rail-dragging";

      // Rail drag: deferred — class is added on first pointermove, not
      // pointerdown, so no ghost border/shadow appears before the user moves.
      let railRevealed = false;

      setIsDragging(true);
      document.body.classList.add("dragging");

      if (source === "sidebar") {
        layout.classList.remove("animating");
      }

      const computeWidth = (clientX: number): number => {
        const delta =
          side === "toc" ? clientX - startX : startX - clientX;
        return startWidth + delta;
      };

      const onMove = (ev: PointerEvent) => {
        const raw = computeWidth(ev.clientX);

        if (source === "rail") {
          // Track 1:1 from 0 upward, clamped to maxWidth.
          const w = Math.max(0, Math.min(maxWidth, raw));
          // Reveal the overlay on the first move that produces width > 0.
          // Deferring avoids a ghost border/shadow flash on pointerdown.
          if (!railRevealed && w > 0) {
            railRevealed = true;
            layout.classList.add(railDragClass);
          }
          layout.style.setProperty(cssVar, `${w}px`);
          lastWidth = w;
          return;
        }

        // Sidebar edge drag: snap-close zone + min/max clamping.
        // In the snap zone, collapse to 0 — previewing the closed state.
        // Content disappears, matching what happens on release.
        if (raw < SNAP_CLOSE_THRESHOLD) {
          layout.style.setProperty(cssVar, "0px");
          lastWidth = 0;
        } else {
          const clamped = Math.max(minWidth, Math.min(maxWidth, raw));
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

        if (source === "rail") {
          // Remove the temporary overlay class (only added if drag moved).
          if (railRevealed) layout.classList.remove(railDragClass);

          if (lastWidth >= RAIL_SNAP_OPEN_THRESHOLD) {
            // Commit: open in push mode at the dragged width (clamped to min).
            const finalWidth = Math.max(minWidth, lastWidth);
            layout.style.setProperty(cssVar, `${finalWidth}px`);
            openFn();
            setWidthFn(finalWidth);
          } else {
            // Abort: snap back to closed — reset CSS var.
            layout.style.removeProperty(cssVar);
          }
          return;
        }

        // Sidebar edge drag commit.
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
        if (source === "rail" && railRevealed) {
          layout.classList.remove(railDragClass);
          layout.style.removeProperty(cssVar);
        }
      };
    },
    [side, source, layoutRef, cssVar, openFn, closeFn, setWidthFn, minWidth, maxWidth],
  );

  // Keyboard resize for sidebar edge handles (arrow keys ±10px, Home/End for min/max).
  // Rail handles use the toggle button for keyboard access instead.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (source !== "sidebar") return;

      // For TOC (left sidebar): ArrowRight = wider, ArrowLeft = narrower.
      // For Tags (right sidebar): ArrowLeft = wider, ArrowRight = narrower.
      const increaseKey = side === "toc" ? "ArrowRight" : "ArrowLeft";
      const decreaseKey = side === "toc" ? "ArrowLeft" : "ArrowRight";

      let newWidth: number | null = null;

      if (e.key === increaseKey) {
        newWidth = Math.min(maxWidth, currentWidthRef.current + RESIZE_STEP);
      } else if (e.key === decreaseKey) {
        newWidth = Math.max(minWidth, currentWidthRef.current - RESIZE_STEP);
      } else if (e.key === "Home") {
        newWidth = minWidth;
      } else if (e.key === "End") {
        newWidth = maxWidth;
      }

      if (newWidth !== null) {
        e.preventDefault();
        setWidthFn(newWidth);
      }
    },
    [side, source, setWidthFn, minWidth, maxWidth],
  );

  // Cleanup on unmount if drag is in progress.
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  return { handlePointerDown, handleKeyDown, isDragging };
}
