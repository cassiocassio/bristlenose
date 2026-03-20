/**
 * useVerticalDragResize — pointer-event state machine for vertical panel resize.
 *
 * Purpose-built for the analysis inspector panel (bottom panel). Follows the
 * same pointer-event pattern as useDragResize (sidebars) but operates on the
 * Y axis and calls InspectorStore actions.
 *
 * Key difference from useDragResize: a 3px movement threshold distinguishes
 * click (open to auto-height) from drag (open and resize). pointerup is the
 * trigger for click-to-open, not pointerdown.
 *
 * During drag, the `--inspector-height` CSS custom property is updated directly
 * on the container element (no React re-render) for 60fps performance. Store
 * actions are called only on pointerup to persist the final height.
 *
 * @module useVerticalDragResize
 */

import { useCallback, useRef, useEffect } from "react";
import {
  closeInspector,
  openInspector,
  setInspectorHeight,
  MIN_HEIGHT,
  MAX_HEIGHT,
  SNAP_CLOSE_THRESHOLD,
} from "../contexts/InspectorStore";

// ── Constants ────────────────────────────────────────────────────────────

/** Pixels of pointer movement before we enter drag mode. */
const DRAG_THRESHOLD = 3;
const RESIZE_STEP = 10;
/** Height of the collapsed handle bar (1.75rem = 28px). */
const COLLAPSED_HEIGHT = 28;

// ── Types ────────────────────────────────────────────────────────────────

export interface UseVerticalDragResizeOptions {
  /** Ref to the panel container element (for direct CSS var manipulation). */
  containerRef: React.RefObject<HTMLElement | null>;
  /** Current panel height from the store. */
  currentHeight: number;
  /** Whether the panel is currently open. */
  isOpen: boolean;
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
  isOpen,
  minHeight = MIN_HEIGHT,
  maxHeight = MAX_HEIGHT,
}: UseVerticalDragResizeOptions): UseVerticalDragResizeReturn {
  // Use a ref (not state) to avoid re-renders during drag.
  // React re-renders overwrite the DOM-level --inspector-height CSS var
  // with the stale store value, causing the panel to snap back.
  const isDraggingRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const currentHeightRef = useRef(currentHeight);
  currentHeightRef.current = currentHeight;
  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container) return;

      const startY = e.clientY;
      const wasCollapsed = !isOpenRef.current;
      // When collapsed, grow from the handle bar height (28px), not the stored height.
      const startHeight = wasCollapsed ? COLLAPSED_HEIGHT : currentHeightRef.current;
      let enteredDrag = false;
      let lastHeight = startHeight;

      document.body.classList.add("dragging-v");

      const onMove = (ev: PointerEvent) => {
        const deltaY = startY - ev.clientY; // upward = positive = taller

        if (!enteredDrag) {
          if (Math.abs(deltaY) < DRAG_THRESHOLD) return;
          enteredDrag = true;
          isDraggingRef.current = true;

          // If panel was collapsed, remove the collapsed class directly on the
          // DOM so tabs/body become visible — but don't call openInspector()
          // yet (that would trigger a React re-render with the stored height).
          // Set --inspector-height to the handle bar height first so the panel
          // doesn't flash to a stale CSS var value.
          if (wasCollapsed) {
            container.style.setProperty("--inspector-height", `${COLLAPSED_HEIGHT}px`);
            container.classList.remove("collapsed");
          }
        }

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
        document.body.classList.remove("dragging-v");
        isDraggingRef.current = false;

        if (!enteredDrag) {
          // Click (no drag) — toggle open/close
          if (isOpenRef.current) {
            closeInspector();
          } else {
            openInspector();
          }
          return;
        }

        // Drag completed
        if (lastHeight < SNAP_CLOSE_THRESHOLD) {
          // Dragged below snap threshold → close
          closeInspector();
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
        document.body.classList.remove("dragging-v");
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

  return { handlePointerDown, handleKeyDown, isDragging: isDraggingRef.current };
}
