/**
 * useVerticalDragResize — pointer-event state machine for vertical panel resize.
 *
 * Purpose-built for the analysis inspector panel (bottom panel). Follows the
 * same pointer-event pattern as useDragResize (sidebars) but operates on the
 * Y axis and calls InspectorStore actions.
 *
 * During drag, the `--inspector-height` CSS custom property is updated directly
 * on the container element (no React re-render) for 60fps performance. Store
 * actions are called only on pointerup to persist the final height.
 *
 * @module useVerticalDragResize
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
  closeInspector,
  openInspector,
  setInspectorHeight,
  MIN_HEIGHT,
  MAX_HEIGHT,
  SNAP_CLOSE_THRESHOLD,
} from "../contexts/InspectorStore";

// ── Constants ────────────────────────────────────────────────────────────

const RESIZE_STEP = 10;

// ── Types ────────────────────────────────────────────────────────────────

export interface UseVerticalDragResizeOptions {
  /** Ref to the panel container element (for direct CSS var manipulation). */
  containerRef: React.RefObject<HTMLElement | null>;
  /** Current panel height from the store. */
  currentHeight: number;
  /** Minimum panel height in px. Defaults to MIN_HEIGHT (150). */
  minHeight?: number;
  /** Maximum panel height in px. Defaults to MAX_HEIGHT (600). */
  maxHeight?: number;
}

export interface UseVerticalDragResizeReturn {
  /** Attach to the drag handle's onPointerDown. */
  handlePointerDown: (e: React.PointerEvent) => void;
  /** Attach to the drag handle's onKeyDown for keyboard resize. */
  handleKeyDown: (e: React.KeyboardEvent) => void;
  /** Whether the handle is actively being dragged. */
  isDragging: boolean;
}

// ── Hook ─────────────────────────────────────────────────────────────────

export function useVerticalDragResize({
  containerRef,
  currentHeight,
  minHeight = MIN_HEIGHT,
  maxHeight = MAX_HEIGHT,
}: UseVerticalDragResizeOptions): UseVerticalDragResizeReturn {
  const [isDragging, setIsDragging] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const currentHeightRef = useRef(currentHeight);
  currentHeightRef.current = currentHeight;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container) return;

      const startY = e.clientY;
      const startHeight = currentHeightRef.current;
      let lastHeight = startHeight;

      setIsDragging(true);
      document.body.classList.add("dragging");

      const onMove = (ev: PointerEvent) => {
        // Dragging upward (negative deltaY) = taller panel
        const deltaY = startY - ev.clientY;
        const raw = startHeight + deltaY;

        if (raw < SNAP_CLOSE_THRESHOLD) {
          container.style.setProperty("--inspector-height", "0px");
          lastHeight = 0;
        } else {
          const clamped = Math.max(minHeight, Math.min(maxHeight, raw));
          container.style.setProperty("--inspector-height", `${clamped}px`);
          lastHeight = clamped;
        }
      };

      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        cleanupRef.current = null;
        document.body.classList.remove("dragging");
        setIsDragging(false);

        if (lastHeight < SNAP_CLOSE_THRESHOLD) {
          closeInspector();
          // Reset CSS var so store-driven height takes over
          container.style.removeProperty("--inspector-height");
        } else {
          const finalHeight = Math.max(minHeight, lastHeight);
          setInspectorHeight(finalHeight);
          openInspector();
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
    [containerRef, minHeight, maxHeight],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      let newHeight: number | null = null;

      if (e.key === "ArrowUp") {
        newHeight = Math.min(maxHeight, currentHeightRef.current + RESIZE_STEP);
      } else if (e.key === "ArrowDown") {
        newHeight = Math.max(minHeight, currentHeightRef.current - RESIZE_STEP);
      } else if (e.key === "Home") {
        newHeight = maxHeight;
      } else if (e.key === "End") {
        newHeight = minHeight;
      }

      if (newHeight !== null) {
        e.preventDefault();
        setInspectorHeight(newHeight);
      }
    },
    [minHeight, maxHeight],
  );

  // Cleanup on unmount if drag is in progress.
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  return { handlePointerDown, handleKeyDown, isDragging };
}
