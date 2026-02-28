/**
 * useKeyboardShortcuts — single keydown listener for all keyboard shortcuts.
 *
 * Replaces handleKeydown() in focus.js for serve mode.  Installs one
 * document-level keydown handler that dispatches to the appropriate
 * action based on the current focus/selection state.
 *
 * Guards:
 * - No-op when isEditing() (input/textarea/contenteditable/tag-suggest active)
 * - No-op when a modal is open (except Escape to close it)
 *
 * @module useKeyboardShortcuts
 */

import { useCallback, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useFocus } from "../contexts/FocusContext";
import { usePlayer } from "../contexts/PlayerContext";
import {
  useQuotesStore,
  toggleStar,
  setSearchQuery,
} from "../contexts/QuotesContext";

// ── Helpers ──────────────────────────────────────────────────────────────

/**
 * Check if user is currently editing (input, textarea, contenteditable,
 * or tag suggest active).  Keyboard shortcuts should not fire while editing.
 */
function isEditing(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return true;
  if ((el as HTMLElement).isContentEditable) return true;
  if (el.closest(".tag-suggest")) return true;
  return false;
}

// ── Hook ─────────────────────────────────────────────────────────────────

interface UseKeyboardShortcutsOptions {
  /** Whether the help modal is currently open. */
  helpModalOpen: boolean;
  /** Toggle the help modal. */
  onToggleHelp: () => void;
}

export function useKeyboardShortcuts({
  helpModalOpen,
  onToggleHelp,
}: UseKeyboardShortcutsOptions): void {
  const {
    focusedId,
    selectedIds,
    setFocus,
    toggleSelection,
    clearSelection,
    moveFocus,
    setAnchor,
    anchorId,
    openTagInput,
    getVisibleQuoteIds,
    hideQuote,
  } = useFocus();
  const { seekTo } = usePlayer();
  const navigate = useNavigate();
  const location = useLocation();
  const store = useQuotesStore();

  // Use refs for values that change frequently to avoid re-attaching the listener.
  const focusedIdRef = useRef(focusedId);
  focusedIdRef.current = focusedId;
  const selectedIdsRef = useRef(selectedIds);
  selectedIdsRef.current = selectedIds;
  const anchorIdRef = useRef(anchorId);
  anchorIdRef.current = anchorId;
  const storeRef = useRef(store);
  storeRef.current = store;
  const helpModalOpenRef = useRef(helpModalOpen);
  helpModalOpenRef.current = helpModalOpen;
  const locationRef = useRef(location);
  locationRef.current = location;

  // ── Star action ─────────────────────────────────────────────────────

  const handleStar = useCallback(() => {
    const focused = focusedIdRef.current;
    const selected = selectedIdsRef.current;
    const s = storeRef.current;

    if (selected.size > 0) {
      // Bulk star — direction follows focused quote's state
      let willStar: boolean;
      if (focused && selected.has(focused)) {
        willStar = !s.starred[focused];
      } else {
        // Fallback: if any unstarred, star all
        willStar = Array.from(selected).some((id) => !s.starred[id]);
      }
      for (const id of selected) {
        const isStarred = !!s.starred[id];
        if (willStar && !isStarred) toggleStar(id, true);
        else if (!willStar && isStarred) toggleStar(id, false);
      }
    } else if (focused) {
      toggleStar(focused, !s.starred[focused]);
    }
  }, []);

  // ── Hide action ─────────────────────────────────────────────────────

  const handleHide = useCallback(() => {
    const focused = focusedIdRef.current;
    const selected = selectedIdsRef.current;

    if (selected.size > 0) {
      for (const id of selected) {
        hideQuote(id);
      }
      clearSelection();
    } else if (focused) {
      hideQuote(focused);
      moveFocus(1);
    }
  }, [clearSelection, moveFocus, hideQuote]);

  // ── Tag action ──────────────────────────────────────────────────────

  const handleTag = useCallback(() => {
    const focused = focusedIdRef.current;
    if (focused) {
      openTagInput(focused);
    }
  }, [openTagInput]);

  // ── Play action ─────────────────────────────────────────────────────

  const handlePlay = useCallback(() => {
    const focused = focusedIdRef.current;
    if (!focused) return;
    // Find the timecode link data from the DOM (quotes embed data-seconds).
    const bq = document.getElementById(focused);
    if (!bq) return;
    const tc = bq.querySelector<HTMLElement>(".timecode[data-seconds]");
    const pid = bq.getAttribute("data-participant");
    if (tc && pid) {
      const seconds = parseFloat(tc.getAttribute("data-seconds") ?? "0");
      seekTo(pid, seconds);
    }
  }, [seekTo]);

  // ── Focus search ────────────────────────────────────────────────────

  const focusSearchInput = useCallback(() => {
    // Find and focus the search input in the toolbar
    const input = document.querySelector<HTMLInputElement>(".search-input");
    if (input) {
      // Expand the search container if collapsed
      const container = input.closest(".search-container");
      if (container && !container.classList.contains("expanded")) {
        container.classList.add("expanded");
      }
      input.focus();
      input.select();
    }
  }, []);

  // ── Clear search ────────────────────────────────────────────────────

  const clearSearch = useCallback((): boolean => {
    const s = storeRef.current;
    if (s.searchQuery) {
      setSearchQuery("");
      return true;
    }
    return false;
  }, []);

  // ── Shift+j/k extend selection ──────────────────────────────────────

  const handleShiftMove = useCallback(
    (direction: 1 | -1) => {
      const focused = focusedIdRef.current;

      // Select the current quote if not already selected
      if (focused) {
        if (!selectedIdsRef.current.has(focused)) {
          toggleSelection(focused);
        }
        if (!anchorIdRef.current) setAnchor(focused);
      }

      // Compute the target ID synchronously from the visible list
      // (can't rely on moveFocus because it updates React state async).
      const ids = getVisibleQuoteIds();
      let targetId: string | null = null;

      if (!focused) {
        targetId = direction > 0 ? ids[0] ?? null : ids[ids.length - 1] ?? null;
      } else {
        const currentIdx = ids.indexOf(focused);
        if (currentIdx === -1) {
          targetId = direction > 0 ? ids[0] ?? null : ids[ids.length - 1] ?? null;
        } else {
          const newIdx = Math.max(0, Math.min(ids.length - 1, currentIdx + direction));
          if (newIdx !== currentIdx) {
            targetId = ids[newIdx];
          }
        }
      }

      // Move focus and select the new target in one synchronous batch
      if (targetId) {
        setFocus(targetId);
        if (!selectedIdsRef.current.has(targetId)) {
          toggleSelection(targetId);
        }
      }
    },
    [toggleSelection, setAnchor, setFocus, getVisibleQuoteIds],
  );

  // ── Keydown handler ─────────────────────────────────────────────────

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      const key = e.key;

      // Escape — cascade: close modal → clear search → clear selection → clear focus
      if (key === "Escape") {
        if (helpModalOpenRef.current) {
          e.preventDefault();
          onToggleHelp();
          return;
        }
        if (clearSearch()) {
          e.preventDefault();
          return;
        }
        if (selectedIdsRef.current.size > 0) {
          e.preventDefault();
          clearSelection();
          return;
        }
        if (focusedIdRef.current) {
          e.preventDefault();
          setFocus(null);
          return;
        }
        return;
      }

      // ? — toggle help modal (when not editing)
      if (key === "?" && !isEditing()) {
        e.preventDefault();
        onToggleHelp();
        return;
      }

      // Don't intercept other keys while editing or modal is open
      if (isEditing()) return;
      if (helpModalOpenRef.current) return;

      // / — focus search
      if (key === "/") {
        e.preventDefault();
        focusSearchInput();
        return;
      }

      // Shift+j/ArrowDown — extend selection down
      if ((key === "j" || key === "ArrowDown") && e.shiftKey) {
        e.preventDefault();
        handleShiftMove(1);
        return;
      }

      // Shift+k/ArrowUp — extend selection up
      if ((key === "k" || key === "ArrowUp") && e.shiftKey) {
        e.preventDefault();
        handleShiftMove(-1);
        return;
      }

      // j/ArrowDown — next quote
      if (key === "j" || key === "ArrowDown") {
        e.preventDefault();
        moveFocus(1);
        return;
      }

      // k/ArrowUp — prev quote
      if (key === "k" || key === "ArrowUp") {
        e.preventDefault();
        moveFocus(-1);
        return;
      }

      // x — toggle selection on focused quote
      if (key === "x" && focusedIdRef.current) {
        e.preventDefault();
        toggleSelection(focusedIdRef.current);
        if (!anchorIdRef.current) setAnchor(focusedIdRef.current);
        return;
      }

      // h — hide
      if (key === "h") {
        if (selectedIdsRef.current.size > 0 || focusedIdRef.current) {
          e.preventDefault();
          handleHide();
          return;
        }
      }

      // s — star
      if (key === "s") {
        if (selectedIdsRef.current.size > 0 || focusedIdRef.current) {
          e.preventDefault();
          handleStar();
          return;
        }
      }

      // t — add tag
      if (key === "t" && focusedIdRef.current) {
        e.preventDefault();
        handleTag();
        return;
      }

      // Enter — play video
      if (key === "Enter" && focusedIdRef.current) {
        e.preventDefault();
        handlePlay();
        return;
      }
    };

    // ── Background click → clear focus/selection ─────────────────────
    const handleBackgroundClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const inQuote = target.closest("blockquote.quote-card");
      const inToolbar = target.closest(".toolbar, header, nav, .toc, .help-overlay");
      // If click was on a quote card, QuoteCard's onClick handles it.
      // Note: closest() walks *up* — descendant selectors don't work.
      if (inQuote) return;
      // If click was on toolbar/header/nav/modal, ignore
      if (inToolbar) return;
      // Clear focus and selection (like Finder)
      clearSelection();
      setFocus(null);
    };

    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("click", handleBackgroundClick);

    return () => {
      document.removeEventListener("keydown", handleKeydown);
      document.removeEventListener("click", handleBackgroundClick);
    };
  }, [
    onToggleHelp,
    clearSearch,
    clearSelection,
    setFocus,
    navigate,
    focusSearchInput,
    handleShiftMove,
    moveFocus,
    toggleSelection,
    setAnchor,
    handleHide,
    handleStar,
    handleTag,
    handlePlay,
  ]);
}
