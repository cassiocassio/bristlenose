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
import {
  entryPoint,
  nextSpatial,
  readCardRects,
  type Direction,
} from "../utils/spatialNav";

export type { Direction };

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
  /** Select every currently-visible quote (⌘A). */
  selectAll: () => void;
  /** Clear all selections. */
  clearSelection: () => void;
  /** Move focus to next (1) or previous (-1) visible quote, in DOM order. */
  moveFocus: (direction: 1 | -1) => void;
  /**
   * Move focus geometrically — the arrow keys. Distinct from `moveFocus`
   * because the quote grid is multi-column masonry, where the next quote in
   * DOM order renders to the *right* rather than below. See `spatialNav`.
   *
   * Returns whether focus actually moved, so the caller can decline the key
   * and let the browser scroll when there's nowhere to go.
   */
  moveFocusSpatial: (direction: Direction) => boolean;
  /**
   * Resolve the quote lying in `direction` from `fromId` without moving focus.
   * Lets Shift+arrow extend the selection along the same path a bare arrow
   * would travel, so the two can't disagree about where "down" is.
   *
   * Takes `null` for a cold cursor so callers never hand-roll the entry point:
   * doing that from the registry rather than the measured set is exactly the
   * bug that made the arrow key stick permanently.
   */
  getSpatialTarget: (fromId: string | null, direction: Direction) => string | null;
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
  /** Flash a tag badge on a quote (visual confirmation for quick-apply). */
  flashTag: (domId: string, tagName: string) => void;
  /** Register a flash-tag handler for a specific quote (called by QuoteGroup). */
  registerFlashTag: (domId: string, handler: (tagName: string) => void) => void;
  /** Unregister a flash-tag handler. */
  unregisterFlashTag: (domId: string) => void;
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
const noopStrStrFn = (_s: string, _fn: (s: string) => void) => {};

const NO_FOCUS: FocusContextValue = {
  focusedId: null,
  selectedIds: EMPTY_SET,
  setFocus: noopStrOrNull as FocusContextValue["setFocus"],
  toggleSelection: noopStr,
  selectRange: noopStrStr,
  selectAll: noop,
  clearSelection: noop,
  moveFocus: noop as unknown as FocusContextValue["moveFocus"],
  moveFocusSpatial: () => false,
  getSpatialTarget: () => null,
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
  flashTag: noopStrStr,
  registerFlashTag: noopStrStrFn,
  unregisterFlashTag: noopStr,
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

  // Flash-tag handlers registered by QuoteGroup instances (for quick-apply flash).
  const flashTagHandlersRef = useRef<Map<string, (tagName: string) => void>>(new Map());

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
          if (!el) return;
          // `nearest`, not `center`. Centring re-scrolls the viewport on
          // every move even when the target is already fully visible — which
          // with horizontal arrows means the page lurches vertically each
          // time you step one lane sideways. `nearest` scrolls the minimum
          // and does nothing at all when the card is already on screen, which
          // is also what Finder and Mail do with a moving selection.
          //
          // It also shrinks a measurement hazard: WebKit reports impossible
          // rects while a smooth scroll animates (frontend/CLAUDE.md), and
          // key-repeat measures inside that window. Fewer animations started,
          // smaller window.
          // `matchMedia` is optional-chained: jsdom doesn't implement it, and
          // an absent media-query API should degrade to "animate" rather than
          // throw inside a rAF callback where nothing would catch it.
          const reduceMotion =
            window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
          el.scrollIntoView({
            behavior: reduceMotion ? "auto" : "smooth",
            block: "nearest",
          });
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

  const selectAll = useCallback(() => {
    const ids = visibleIdsRef.current;
    if (!ids.length) return;
    setSelectedIds(new Set(ids));
  }, []);

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

  // ── Spatial movement (arrow keys) ───────────────────────────────────

  /**
   * The single resolver for every geometric move — bare arrow and
   * Shift+arrow both go through here.
   *
   * Recovery lives here rather than in the callers on purpose. When it sat in
   * `moveFocusSpatial` alone, Shift+arrow inherited none of it: an unmeasured
   * cursor resolved to null, and the extend path then *selected the invisible
   * quote and stayed put*, feeding it to bulk star / hide / copy. Sharing the
   * scorer was never enough — the fallback has to be shared too.
   */
  const getSpatialTarget = useCallback(
    (fromId: string | null, direction: Direction): string | null => {
      const ids = visibleIdsRef.current;
      if (!ids.length) return null;

      const rects = readCardRects(ids);

      // No focus, or a focused quote that's no longer laid out (filtered,
      // searched away, hidden) — enter at the same end `j`/`k` would.
      //
      // Enter from the *measured* set, not the registry. Entering from `ids`
      // hands focus back to the unmeasurable quote whenever it happens to sit
      // at the end we're entering from, so the next press repeats the same
      // failure and the arrow key is permanently dead — each press still
      // firing a scroll back to the card that can't be measured.
      // `readCardRects` preserves registry order, so reading order is
      // unaffected.
      if (!fromId || !rects.some((r) => r.id === fromId)) {
        return entryPoint(
          rects.map((r) => r.id),
          direction,
        );
      }

      // Null at the edge of the grid: stay put rather than wrap. Wrapping
      // would have to invent a row to wrap to, and masonry has none.
      return nextSpatial(rects, fromId, direction);
    },
    [],
  );

  /** Returns whether focus actually moved, so the caller can decide whether
   *  to claim the key or let the browser scroll the page. */
  const moveFocusSpatial = useCallback(
    (direction: Direction): boolean => {
      const next = getSpatialTarget(focusedId, direction);
      if (!next) return false;
      setFocus(next);
      return true;
    },
    [focusedId, getSpatialTarget, setFocus],
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

  // ── Flash-tag handlers ──────────────────────────────────────────────

  const registerFlashTag = useCallback(
    (domId: string, handler: (tagName: string) => void) => {
      flashTagHandlersRef.current.set(domId, handler);
    },
    [],
  );

  const unregisterFlashTag = useCallback((domId: string) => {
    flashTagHandlersRef.current.delete(domId);
  }, []);

  const flashTag = useCallback((domId: string, tagName: string) => {
    const handler = flashTagHandlersRef.current.get(domId);
    if (handler) handler(tagName);
  }, []);

  // ── Context value ───────────────────────────────────────────────────

  const value = useMemo<FocusContextValue>(
    () => ({
      focusedId,
      selectedIds,
      setFocus,
      toggleSelection,
      selectRange,
      selectAll,
      clearSelection,
      moveFocus,
      moveFocusSpatial,
      getSpatialTarget,
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
      flashTag,
      registerFlashTag,
      unregisterFlashTag,
    }),
    [
      focusedId,
      selectedIds,
      setFocus,
      toggleSelection,
      selectRange,
      selectAll,
      clearSelection,
      moveFocus,
      moveFocusSpatial,
      getSpatialTarget,
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
      flashTag,
      registerFlashTag,
      unregisterFlashTag,
    ],
  );

  return (
    <FocusContext.Provider value={value}>{children}</FocusContext.Provider>
  );
}
