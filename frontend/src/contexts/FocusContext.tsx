/**
 * FocusContext — keyboard focus and multi-select state for quotes.
 *
 * Replaces `focus.js` in serve mode. Manages:
 * - Focus (keyboard cursor): at most one quote focused at a time
 * - Selection (multi-select): zero or more quotes selected for bulk actions
 * - Movement: j/k navigation through visible quotes in DOM order
 *
 * Focus state lives in React state (not refs) because QuoteCard needs
 * to re-render when focused/selected status changes (to apply CSS
 * classes via React).
 *
 * @module FocusContext
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

// ── Types ────────────────────────────────────────────────────────────────

interface FocusContextValue {
  /** Currently focused quote ID, or null if no focus. */
  focusedId: string | null;
  /** Set of selected quote IDs. */
  selectedIds: Set<string>;
  /** Set focus to a quote by ID (null to clear). Scrolls into view. */
  setFocus: (id: string | null, options?: { scroll?: boolean }) => void;
  /** Toggle selection on a single quote. */
  toggleSelection: (id: string) => void;
  /** Select a range of quotes between two IDs (inclusive). */
  selectRange: (fromId: string, toId: string) => void;
  /** Clear all selections. */
  clearSelection: () => void;
  /** Move focus to next (1) or previous (-1) visible quote. */
  moveFocus: (direction: 1 | -1) => void;
  /** Set the anchor for Shift-extend selection. */
  setAnchor: (id: string | null) => void;
  /** Current anchor ID for range selection. */
  anchorId: string | null;
  /**
   * Register visible quote IDs (in DOM order) from a named source.
   * Sources are merged in registration order (sections then themes).
   */
  registerVisibleQuoteIds: (source: string, ids: string[]) => void;
  /** Get the current list of visible quote IDs (for synchronous computation). */
  getVisibleQuoteIds: () => string[];
  /** Open tag input on the focused quote (or selected quotes for bulk). */
  openTagInput: (domId: string) => void;
  /** Register a callback for opening a tag input on a specific quote. */
  registerTagOpener: (domId: string, opener: () => void) => void;
  /** Unregister a tag opener. */
  unregisterTagOpener: (domId: string) => void;
  /** Hide a quote via its QuoteGroup handler (triggers fly-up animation). */
  hideQuote: (domId: string) => void;
  /** Register a hide handler for a specific quote (called by QuoteGroup). */
  registerHideHandler: (domId: string, handler: () => void) => void;
  /** Unregister a hide handler. */
  unregisterHideHandler: (domId: string) => void;
}

// ── Context ──────────────────────────────────────────────────────────────

const FocusContext = createContext<FocusContextValue | null>(null);

// ── No-op fallback (for components rendered outside FocusProvider) ────────

const EMPTY_SET = new Set<string>();
const noop = () => {};
const noopStr = (_s: string) => {};
const noopStrStr = (_a: string, _b: string) => {};
const noopStrOrNull = (_s: string | null) => {};
const noopStrFn = (_s: string, _fn: () => void) => {};

const NO_FOCUS: FocusContextValue = {
  focusedId: null,
  selectedIds: EMPTY_SET,
  setFocus: noopStrOrNull as FocusContextValue["setFocus"],
  toggleSelection: noopStr,
  selectRange: noopStrStr,
  clearSelection: noop,
  moveFocus: noop as unknown as FocusContextValue["moveFocus"],
  setAnchor: noopStrOrNull,
  anchorId: null,
  registerVisibleQuoteIds: noopStrStr as unknown as FocusContextValue["registerVisibleQuoteIds"],
  getVisibleQuoteIds: () => [],
  openTagInput: noopStr,
  registerTagOpener: noopStrFn,
  unregisterTagOpener: noopStr,
  hideQuote: noopStr,
  registerHideHandler: noopStrFn,
  unregisterHideHandler: noopStr,
};

// ── Hook ─────────────────────────────────────────────────────────────────

/**
 * Access the focus context.  Returns a no-op stub when called outside
 * a FocusProvider (e.g. in legacy island mode or unit tests that don't
 * wrap with providers).
 */
export function useFocus(): FocusContextValue {
  const ctx = useContext(FocusContext);
  return ctx ?? NO_FOCUS;
}

/**
 * Read-only hook for checking if a specific quote is focused or selected.
 * Returns stable booleans — components that only need to know their own
 * focus/selection state should use this to minimise re-renders.
 */
export function useQuoteFocusState(domId: string): {
  isFocused: boolean;
  isSelected: boolean;
} {
  const { focusedId, selectedIds } = useFocus();
  return useMemo(
    () => ({
      isFocused: focusedId === domId,
      isSelected: selectedIds.has(domId),
    }),
    [focusedId, selectedIds, domId],
  );
}

// ── Provider ─────────────────────────────────────────────────────────────

export function FocusProvider({ children }: { children: ReactNode }) {
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [anchorId, setAnchorId] = useState<string | null>(null);

  // Visible quote IDs from multiple sources, merged in order.
  const visibleIdsRef = useRef<string[]>([]);
  const sourceIdsRef = useRef<Map<string, string[]>>(new Map());

  // Tag opener callbacks registered by QuoteCard instances.
  const tagOpenersRef = useRef<Map<string, () => void>>(new Map());

  // Hide handler callbacks registered by QuoteGroup instances.
  const hideHandlersRef = useRef<Map<string, () => void>>(new Map());

  // ── Visible quote ID management ─────────────────────────────────────

  const registerVisibleQuoteIds = useCallback((source: string, ids: string[]) => {
    sourceIdsRef.current.set(source, ids);
    // Merge all sources in map iteration order (sections registered first).
    const merged: string[] = [];
    for (const sourceIds of sourceIdsRef.current.values()) {
      merged.push(...sourceIds);
    }
    visibleIdsRef.current = merged;
  }, []);

  // ── Focus ───────────────────────────────────────────────────────────

  const setFocus = useCallback(
    (id: string | null, options?: { scroll?: boolean }) => {
      const shouldScroll = options?.scroll !== false;
      setFocusedId(id);
      if (id && shouldScroll) {
        // Defer scroll to next frame so React has rendered the focus class.
        requestAnimationFrame(() => {
          const el = document.getElementById(id);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        });
      }
    },
    [],
  );

  // ── Selection ───────────────────────────────────────────────────────

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectRange = useCallback(
    (fromId: string, toId: string) => {
      const ids = visibleIdsRef.current;
      const fromIdx = ids.indexOf(fromId);
      const toIdx = ids.indexOf(toId);
      if (fromIdx === -1 || toIdx === -1) return;

      const start = Math.min(fromIdx, toIdx);
      const end = Math.max(fromIdx, toIdx);

      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (let i = start; i <= end; i++) {
          next.add(ids[i]);
        }
        return next;
      });
    },
    [],
  );

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // ── Movement ────────────────────────────────────────────────────────

  const moveFocus = useCallback(
    (direction: 1 | -1) => {
      const ids = visibleIdsRef.current;
      if (!ids.length) return;

      if (!focusedId) {
        // No focus: start from beginning (next) or end (prev)
        const idx = direction > 0 ? 0 : ids.length - 1;
        setFocus(ids[idx]);
        return;
      }

      const currentIdx = ids.indexOf(focusedId);
      if (currentIdx === -1) {
        // Focused quote no longer visible — start from beginning/end
        const fallback = direction > 0 ? 0 : ids.length - 1;
        setFocus(ids[fallback]);
        return;
      }

      // Move, clamping at boundaries
      const newIdx = Math.max(0, Math.min(ids.length - 1, currentIdx + direction));
      if (newIdx !== currentIdx) {
        setFocus(ids[newIdx]);
      }
    },
    [focusedId, setFocus],
  );

  // ── Anchor ──────────────────────────────────────────────────────────

  const setAnchor = useCallback((id: string | null) => {
    setAnchorId(id);
  }, []);

  // ── Visible ID getter ────────────────────────────────────────────────

  const getVisibleQuoteIds = useCallback(() => visibleIdsRef.current, []);

  // ── Tag openers ─────────────────────────────────────────────────────

  const registerTagOpener = useCallback(
    (domId: string, opener: () => void) => {
      tagOpenersRef.current.set(domId, opener);
    },
    [],
  );

  const unregisterTagOpener = useCallback((domId: string) => {
    tagOpenersRef.current.delete(domId);
  }, []);

  const openTagInput = useCallback((domId: string) => {
    const opener = tagOpenersRef.current.get(domId);
    if (opener) opener();
  }, []);

  // ── Hide handlers ─────────────────────────────────────────────────

  const registerHideHandler = useCallback(
    (domId: string, handler: () => void) => {
      hideHandlersRef.current.set(domId, handler);
    },
    [],
  );

  const unregisterHideHandler = useCallback((domId: string) => {
    hideHandlersRef.current.delete(domId);
  }, []);

  const hideQuote = useCallback((domId: string) => {
    const handler = hideHandlersRef.current.get(domId);
    if (handler) handler();
  }, []);

  // ── Context value ───────────────────────────────────────────────────

  const value = useMemo<FocusContextValue>(
    () => ({
      focusedId,
      selectedIds,
      setFocus,
      toggleSelection,
      selectRange,
      clearSelection,
      moveFocus,
      setAnchor,
      anchorId,
      registerVisibleQuoteIds,
      getVisibleQuoteIds,
      openTagInput,
      registerTagOpener,
      unregisterTagOpener,
      hideQuote,
      registerHideHandler,
      unregisterHideHandler,
    }),
    [
      focusedId,
      selectedIds,
      setFocus,
      toggleSelection,
      selectRange,
      clearSelection,
      moveFocus,
      setAnchor,
      anchorId,
      registerVisibleQuoteIds,
      getVisibleQuoteIds,
      openTagInput,
      registerTagOpener,
      unregisterTagOpener,
      hideQuote,
      registerHideHandler,
      unregisterHideHandler,
    ],
  );

  return (
    <FocusContext.Provider value={value}>{children}</FocusContext.Provider>
  );
}
