/**
 * useTocOverlay — hover-to-peek and click-outside-to-close for the TOC overlay.
 *
 * Hover intent: mouseenter on the left rail starts a hover timer. If not
 * cancelled, the TOC opens in overlay mode. A leave grace period allows
 * the mouse to move from the rail into the overlay panel without closing.
 *
 * Safe zone: mouse over the rail *button* or *drag handle* cancels the
 * hover timer so users can click the push-open icon or grab the resize
 * handle without the overlay pre-empting.
 *
 * Direction-aware leave: only mousing rightward (into main content) closes
 * the overlay. Left/top/bottom exits are treated as accidental.
 *
 * Click outside: mousedown on document closes the overlay if the target
 * is outside the rail and panel. Same pattern as useDropdown.ts.
 *
 * @module useTocOverlay
 */

import { useCallback, useEffect, useRef } from "react";
import type { TocMode } from "../contexts/SidebarStore";
import { openTocOverlay } from "../contexts/SidebarStore";

const DEFAULT_HOVER_DELAY = 200;
const DEFAULT_LEAVE_GRACE = 100;

interface UseTocOverlayOptions {
  tocMode: TocMode;
  railRef: React.RefObject<HTMLElement | null>;
  panelRef: React.RefObject<HTMLElement | null>;
  /** Animated close callback — provided by SidebarLayout for slide-out animation. */
  onClose: () => void;
  /** Hover delay in ms. Default 400. Configurable from playground HUD. */
  hoverDelay?: number;
  /** Leave grace period in ms. Default 100. Configurable from playground HUD. */
  leaveGrace?: number;
}

export interface UseTocOverlayHandlers {
  onRailMouseEnter: (e: React.MouseEvent) => void;
  onRailMouseLeave: (e: React.MouseEvent) => void;
  onPanelMouseEnter: () => void;
  onPanelMouseLeave: (e: React.MouseEvent) => void;
  onRailAreaClick: (e: React.MouseEvent) => void;
  onButtonMouseEnter: () => void;
  onButtonMouseLeave: () => void;
  onDragHandleMouseEnter: () => void;
  onDragHandleMouseLeave: () => void;
}

export function useTocOverlay({
  tocMode,
  railRef,
  panelRef,
  onClose,
  hoverDelay = DEFAULT_HOVER_DELAY,
  leaveGrace = DEFAULT_LEAVE_GRACE,
}: UseTocOverlayOptions): UseTocOverlayHandlers {
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHover = useCallback(() => {
    if (hoverTimer.current !== null) {
      clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  }, []);

  const clearLeave = useCallback(() => {
    if (leaveTimer.current !== null) {
      clearTimeout(leaveTimer.current);
      leaveTimer.current = null;
    }
  }, []);

  // Clean up timers on unmount.
  useEffect(() => {
    return () => {
      clearHover();
      clearLeave();
    };
  }, [clearHover, clearLeave]);

  // ── Hover intent ──────────────────────────────────────────────────────

  const startHoverTimer = useCallback(() => {
    clearHover();
    hoverTimer.current = setTimeout(() => {
      hoverTimer.current = null;
      openTocOverlay();
    }, hoverDelay);
  }, [clearHover, hoverDelay]);

  const onRailMouseEnter = useCallback(
    (e: React.MouseEvent) => {
      clearLeave();
      if (tocMode !== "closed") return;
      // Safe zone: if entering the rail via the button or drag handle,
      // don't start the timer — let the user click/drag without pre-emption.
      const target = e.target as HTMLElement;
      if (target.closest(".rail-btn") || target.closest(".drag-handle")) return;
      startHoverTimer();
    },
    [tocMode, clearLeave, startHoverTimer],
  );

  const onRailMouseLeave = useCallback(
    (e: React.MouseEvent) => {
      clearHover();
      if (tocMode !== "overlay") return;
      // Direction check: only close if mouse moved rightward (toward content).
      const rail = railRef.current;
      if (rail) {
        const rect = rail.getBoundingClientRect();
        if (e.clientX <= rect.left) return; // moved left (off-screen) — ignore
      }
      // Grace period — mouse may be moving into the panel.
      leaveTimer.current = setTimeout(() => {
        leaveTimer.current = null;
        onClose();
      }, leaveGrace);
    },
    [tocMode, clearHover, railRef, onClose, leaveGrace],
  );

  const onPanelMouseEnter = useCallback(() => {
    clearLeave();
  }, [clearLeave]);

  const onPanelMouseLeave = useCallback(
    (e: React.MouseEvent) => {
      if (tocMode !== "overlay") return;
      // Direction check: only close if mouse exited rightward (into content).
      const panel = panelRef.current;
      if (panel) {
        const rect = panel.getBoundingClientRect();
        if (e.clientX < rect.right) return; // moved left, up, or down — ignore
      }
      leaveTimer.current = setTimeout(() => {
        leaveTimer.current = null;
        onClose();
      }, leaveGrace);
    },
    [tocMode, panelRef, onClose, leaveGrace],
  );

  // ── Safe zone: button enter/leave ────────────────────────────────────

  /** Mouse entered the icon button — cancel hover timer (don't pre-empt click). */
  const onButtonMouseEnter = useCallback(() => {
    clearHover();
  }, [clearHover]);

  /** Mouse left the button back into the rail — restart the hover timer. */
  const onButtonMouseLeave = useCallback(() => {
    if (tocMode !== "closed") return;
    startHoverTimer();
  }, [tocMode, startHoverTimer]);

  // ── Safe zone: drag handle enter/leave ───────────────────────────────

  /** Mouse entered the drag handle — cancel hover timer (don't pre-empt drag). */
  const onDragHandleMouseEnter = useCallback(() => {
    clearHover();
  }, [clearHover]);

  /** Mouse left the drag handle back into the rail — restart the hover timer. */
  const onDragHandleMouseLeave = useCallback(() => {
    if (tocMode !== "closed") return;
    startHoverTimer();
  }, [tocMode, startHoverTimer]);

  // ── Rail area click (not the icon button or drag handle) → immediate overlay

  const onRailAreaClick = useCallback(
    (e: React.MouseEvent) => {
      // If the click was on the icon button or drag handle, let their own
      // handlers fire. Only open overlay for clicks elsewhere in the rail.
      const target = e.target as HTMLElement;
      if (target.closest(".rail-btn") || target.closest(".drag-handle")) return;
      if (tocMode === "closed") {
        clearHover();
        openTocOverlay();
      }
    },
    [tocMode, clearHover],
  );

  // ── Click outside → close overlay ─────────────────────────────────────

  useEffect(() => {
    if (tocMode !== "overlay") return;
    function onClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (railRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      onClose();
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [tocMode, railRef, panelRef, onClose]);

  return {
    onRailMouseEnter,
    onRailMouseLeave,
    onPanelMouseEnter,
    onPanelMouseLeave,
    onRailAreaClick,
    onButtonMouseEnter,
    onButtonMouseLeave,
    onDragHandleMouseEnter,
    onDragHandleMouseLeave,
  };
}
