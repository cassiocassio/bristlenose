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
import { isExportMode } from "../utils/exportData";
import { usePlayer } from "../contexts/PlayerContext";
import {
  useQuotesStore,
  toggleStar,
  setSearchQuery,
  setTagFilter,
  addTag,
  getLastUsedTag,
} from "../contexts/QuotesContext";
import {
  useSidebarStore,
  closeToc,
  exitSoloMode,
} from "../contexts/SidebarStore";
import { sidebarAnimations } from "../components/SidebarLayout";
import {
  togglePlayground,
  toggleHUD,
} from "../contexts/PlaygroundStore";
import { toggleInspector } from "../contexts/InspectorStore";
import { toggleFocusMode } from "../contexts/FocusModeStore";
import { isEditing } from "../utils/editing";
import { isEmbedded } from "../utils/embedded";
import { postEditingStarted, postEditingEnded } from "../shims/bridge";
import { type Direction } from "../utils/spatialNav";

// ── Helpers ──────────────────────────────────────────────────────────────

/** Check if the current pathname matches a given route (ignoring trailing slash). */
function pathMatches(pathname: string, route: string): boolean {
  return pathname === route || pathname === route + "/";
}

/** Arrow keys, mapped to the geometric direction they draw. */
const ARROW_DIRECTIONS: Record<string, Direction | undefined> = {
  ArrowDown: "down",
  ArrowUp: "up",
  ArrowLeft: "left",
  ArrowRight: "right",
};

/**
 * Native-menu actions that act on quotes, and so must respect the same lens
 * gate the keydown path does.
 *
 * Player transport and window actions are deliberately absent — those are
 * valid from any lens. Without this, off-lens safety for the menu path rests
 * entirely on the Swift side remembering `.disabled(!onQuotesTab)` on every
 * item it ever adds; one omission and a quote the user can no longer see gets
 * starred, hidden, or silently dropped from the selection.
 */
const QUOTE_SCOPED_MENU_ACTIONS = new Set([
  "star",
  "hide",
  "addTag",
  "applyLastTag",
  "nextQuote",
  "previousQuote",
  "extendSelectionDown",
  "extendSelectionUp",
  "toggleSelection",
  "selectAllQuotes",
  "clearSelection",
  "revealInTranscript",
]);

// ── Hook ─────────────────────────────────────────────────────────────────

interface UseKeyboardShortcutsOptions {
  /** Whether the help modal is currently open. */
  helpModalOpen: boolean;
  /** Toggle the help modal. */
  onToggleHelp: () => void;
  /** Whether the settings modal is currently open. */
  settingsModalOpen?: boolean;
  /** Toggle the settings modal. */
  onToggleSettings?: () => void;
}

export function useKeyboardShortcuts({
  helpModalOpen,
  onToggleHelp,
  settingsModalOpen,
  onToggleSettings,
}: UseKeyboardShortcutsOptions): void {
  const {
    focusedId,
    selectedIds,
    setFocus,
    toggleSelection,
    selectAll,
    clearSelection,
    moveFocus,
    moveFocusSpatial,
    getSpatialTarget,
    setAnchor,
    anchorId,
    openTagInput,
    getVisibleQuoteIds,
    hideQuote,
    flashTag,
  } = useFocus();
  const { seekTo, sendCommand } = usePlayer();
  const navigate = useNavigate();
  const location = useLocation();
  const store = useQuotesStore();
  const { tocMode, soloTag } = useSidebarStore();

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
  const settingsModalOpenRef = useRef(settingsModalOpen);
  settingsModalOpenRef.current = settingsModalOpen;
  const tocModeRef = useRef(tocMode);
  tocModeRef.current = tocMode;
  const soloTagRef = useRef(soloTag);
  soloTagRef.current = soloTag;
  const locationRef = useRef(location);
  locationRef.current = location;

  // ── Star action ─────────────────────────────────────────────────────

  const handleStar = useCallback(() => {
    // Read-only in an exported report — no server to persist mutations.
    if (isExportMode()) return;
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
    // Read-only in an exported report — no server to persist mutations.
    if (isExportMode()) return;
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

  // ── Tag actions ─────────────────────────────────────────────────────

  const handleTagOpen = useCallback(() => {
    // Read-only in an exported report — no server to persist mutations.
    if (isExportMode()) return;
    const focused = focusedIdRef.current;
    if (focused) {
      openTagInput(focused);
    }
  }, [openTagInput]);

  /** Quick-apply last-used tag to focused/selected quotes (double-t). */
  const handleQuickApply = useCallback(() => {
    if (isExportMode()) return true;
    const tag = getLastUsedTag();
    if (!tag) return false; // No last tag — caller should fall back to open TagInput

    const focused = focusedIdRef.current;
    const selected = selectedIdsRef.current;
    const targets = selected.size > 0 ? Array.from(selected) : focused ? [focused] : [];
    if (targets.length === 0) return false;

    for (const domId of targets) {
      addTag(domId, { ...tag, source: "human" });
      flashTag(domId, tag.name);
    }
    return true;
  }, [flashTag]);

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

  // ── Extend selection (Shift+move) ───────────────────────────────────

  /**
   * Select the focused quote, move focus to `targetId`, and select that too.
   *
   * This is an *accumulate* model, not a true range: each step adds the quote
   * it passes over. That's what makes it generalise to the arrow keys — a 2-D
   * range has no unambiguous meaning over a masonry grid, whereas accumulating
   * along the path the cursor actually travelled always does.
   */
  const extendTo = useCallback(
    (targetId: string | null) => {
      const focused = focusedIdRef.current;

      // Select the current quote if not already selected
      if (focused) {
        if (!selectedIdsRef.current.has(focused)) {
          toggleSelection(focused);
        }
        if (!anchorIdRef.current) setAnchor(focused);
      }

      // Move focus and select the new target in one synchronous batch
      if (targetId) {
        setFocus(targetId);
        if (!selectedIdsRef.current.has(targetId)) {
          toggleSelection(targetId);
        }
      }
    },
    [toggleSelection, setAnchor, setFocus],
  );

  /** Shift+j/k — extend along DOM order. */
  const handleShiftMove = useCallback(
    (direction: 1 | -1) => {
      const focused = focusedIdRef.current;

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

      extendTo(targetId);
    },
    [extendTo, getVisibleQuoteIds],
  );

  /**
   * Shift+arrow — extend along the geometry, so it tracks exactly where a bare
   * arrow would have gone. Sharing `getSpatialTarget` with `moveFocusSpatial`
   * is what stops the two from disagreeing about which quote is "down".
   */
  const handleShiftMoveSpatial = useCallback(
    (direction: Direction) => {
      extendTo(getSpatialTarget(focusedIdRef.current, direction));
    },
    [extendTo, getSpatialTarget],
  );

  // ── Keydown handler ─────────────────────────────────────────────────

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      const key = e.key;

      // A bare-key shortcut must not fire as part of a ⌘/Ctrl/⌥ chord. Each
      // handler below matched on `key` alone, so ⌘S starred the focused quote
      // *and* opened Save Page, ⌘X toggled selection alongside Cut, and any
      // future chord landing on one of these letters would have doubled up
      // silently. The isEditing() guard doesn't help: the chords that collide
      // are most wanted just after an edit commits, when isEditing() is false.
      //
      // ⌥ is belt-and-braces on a Mac — ⌥s arrives as "ß", so it never matches
      // — but it costs nothing and keeps the rule one clause rather than two.
      // Shift is deliberately absent: Shift+j/k is a real binding.
      const bare = !e.metaKey && !e.ctrlKey && !e.altKey;

      // Ctrl+Shift+P — toggle responsive playground (dev-only)
      if (key === "P" && e.ctrlKey && e.shiftKey) {
        e.preventDefault();
        togglePlayground();
        return;
      }

      // Ctrl+Shift+U — toggle playground HUD (dev-only)
      if (key === "U" && e.ctrlKey && e.shiftKey) {
        e.preventDefault();
        toggleHUD();
        return;
      }

      // ⌘, / Ctrl+, — toggle settings modal
      if (key === "," && (e.metaKey || e.ctrlKey) && !isEditing()) {
        e.preventDefault();
        onToggleSettings?.();
        return;
      }

      // Escape — cascade: close modal → close overlay → clear search → clear selection → clear focus
      if (key === "Escape") {
        if (settingsModalOpenRef.current) {
          e.preventDefault();
          onToggleSettings?.();
          return;
        }
        if (helpModalOpenRef.current) {
          e.preventDefault();
          onToggleHelp();
          return;
        }
        if (tocModeRef.current === "overlay") {
          e.preventDefault();
          closeToc();
          return;
        }
        if (soloTagRef.current !== null) {
          e.preventDefault();
          exitSoloMode(setTagFilter);
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
      if (settingsModalOpenRef.current) return;

      // ⌘A / Ctrl+A — select all visible quotes (quotes tab only).
      // Preempts the browser's native "select all text" so ⌘A acts on
      // quotes as objects (ready to star/hide/tag), not on page text. On
      // other tabs (e.g. transcripts) native text select-all is left intact.
      // In the desktop app this path is unreached — BristlenoseWebView
      // intercepts ⌘A in performKeyEquivalent and routes it via the menu
      // bridge instead (the main menu's Select All would otherwise win).
      if (key === "a" && (e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey) {
        if (
          pathMatches(locationRef.current.pathname, "/report/quotes") &&
          getVisibleQuoteIds().length > 0
        ) {
          e.preventDefault();
          selectAll();
          return;
        }
      }

      // ⌘C / Ctrl+C — copy the selected quotes' text, matching "Copy Quotes ▸
      // Selected" from the export menu. Object selection isn't a text
      // selection, so native copy would grab nothing after ⌘A — this makes ⌘C
      // the natural next step. Only hijacks when quotes are object-selected on
      // the Quotes tab; with no selection, native copy is left intact so
      // ordinary text drag-copy still works. Routes through the same
      // bn:menu-action path AppLayout uses for the native menu, so browser and
      // desktop copy identically. In the desktop app this keydown is unreached
      // — BristlenoseWebView claims ⌘C in performKeyEquivalent and dispatches
      // the same menu action (the main menu's Copy would otherwise win).
      if (key === "c" && (e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey) {
        if (
          pathMatches(locationRef.current.pathname, "/report/quotes") &&
          selectedIdsRef.current.size > 0
        ) {
          e.preventDefault();
          window.dispatchEvent(
            new CustomEvent("bn:menu-action", {
              detail: { action: "copyQuotes", payload: { scope: "selected" } },
            }),
          );
          return;
        }
      }

      // [ — toggle TOC sidebar (quotes, codebook, analysis; sessions in the
      // browser only — embedded removed the Sessions left panel in favour of
      // the native switcher popover, and toggling a panel that isn't there
      // would flip the store flag with no pixels to show for it)
      if (key === "[" && bare) {
        const loc = locationRef.current.pathname;
        const onSessions = loc.startsWith("/report/sessions");
        if (
          pathMatches(loc, "/report/quotes") ||
          pathMatches(loc, "/report/codebook") ||
          // `pathMatches` is exact-or-trailing-slash, so codebook-v2 needs its
          // own arm — the v2 lens has the same left panel and the same key.
          pathMatches(loc, "/report/codebook-v2") ||
          pathMatches(loc, "/report/analysis") ||
          (onSessions && !isEmbedded())
        ) {
          e.preventDefault();
          sidebarAnimations.toggleToc();
          return;
        }
      }

      // ] — toggle tag sidebar (quotes tab only)
      if (key === "]" && bare) {
        if (pathMatches(locationRef.current.pathname, "/report/quotes")) {
          e.preventDefault();
          sidebarAnimations.toggleTags();
          return;
        }
      }

      // \ or ⌘. / Ctrl+. — toggle both sidebars (quotes tab only).
      // `§` is an ISO-layout alias: it's the unmodified top-left key on Apple
      // British and the closest thing a Mac has to Photoshop's Tab. It stays a
      // web-layer alias rather than the advertised binding because US ANSI has
      // no § key at all (⌥6) — the menu advertises ⌘⌥\, which everyone has.
      if (
        ((key === "\\" || key === "§") && bare) ||
        (key === "." && (e.metaKey || e.ctrlKey))
      ) {
        if (pathMatches(locationRef.current.pathname, "/report/quotes")) {
          e.preventDefault();
          sidebarAnimations.toggleBoth();
          return;
        }
      }

      // m — toggle heatmap inspector panel (analysis tab only)
      if (key === "m" && bare) {
        if (pathMatches(locationRef.current.pathname, "/report/analysis")) {
          e.preventDefault();
          toggleInspector();
          return;
        }
      }

      // / — focus search
      if (key === "/" && bare) {
        e.preventDefault();
        focusSearchInput();
        return;
      }

      // Everything below acts on quotes — movement, selection, and the
      // per-quote actions. Gate the lot on the Quotes lens.
      //
      // Focus is a *logical* cursor that deliberately survives scrolling and
      // route changes, so without this guard the quote keys stay live on every
      // other lens: `j`/arrows preventDefault the page scroll on Transcripts
      // and Analysis, and `s`/`h` mutate whichever quote was focused before
      // the user navigated away — one they can no longer see. The keys that
      // legitimately work off-lens (`/`, `?`, Escape, `[`, `]`, `\`, `m`, and
      // the ⌘A/⌘C traps) all sit above this line and carry their own routing.
      if (!pathMatches(locationRef.current.pathname, "/report/quotes")) return;

      // Arrows — geometric movement, measured off the laid-out grid.
      //
      // Split from j/k because the quote grid is multi-column `auto-fill` that
      // upgrades to masonry (`grid-lanes`), so the next quote in DOM order
      // renders to the *right*. An arrow bound to DOM order therefore pointed
      // somewhere it didn't draw, and ←/→ did nothing at all.
      const arrowDirection = ARROW_DIRECTIONS[key];
      if (arrowDirection) {
        // A focused control that already claimed this key owns it. The live
        // case is the sidebar resize separator (role="separator", ←/→ in
        // useDragResize), which calls preventDefault but not stopPropagation
        // — so before this guard, one ArrowLeft resized the sidebar *and*
        // moved the quote cursor *and* scrolled the page. Scoped to the arrow
        // block rather than the top of the handler: hoisting it would quietly
        // rewrite the Escape cascade and the ⌘A/⌘C traps too.
        if (e.defaultPrevented) return;

        if (e.shiftKey) {
          // Extending at an edge is still a claim — the selection changed
          // even when focus didn't.
          e.preventDefault();
          handleShiftMoveSpatial(arrowDirection);
          return;
        }
        // Only claim the key if the cursor actually moved. At the edge of the
        // grid, on an empty search result, or before the islands have
        // registered, an unconditional preventDefault left the arrows dead —
        // page scroll lost with nothing gained.
        if (moveFocusSpatial(arrowDirection)) e.preventDefault();
        return;
      }

      // Shift+j/k — extend selection along DOM order
      if ((key === "j" || key === "k") && e.shiftKey && bare) {
        e.preventDefault();
        handleShiftMove(key === "j" ? 1 : -1);
        return;
      }

      // j/k — the DOM-order list cursor (Gmail / GitHub / Linear lineage).
      // Deliberately *not* geometric: these mean "next item in reading order"
      // whatever the layout, and they're what the native Quotes menu's
      // Next/Previous Quote drive. Two coherent models, not one compromised
      // one — in a single column they coincide.
      if ((key === "j" || key === "k") && bare) {
        e.preventDefault();
        moveFocus(key === "j" ? 1 : -1);
        return;
      }

      // x — toggle selection on focused quote
      if (key === "x" && bare && focusedIdRef.current) {
        e.preventDefault();
        toggleSelection(focusedIdRef.current);
        if (!anchorIdRef.current) setAnchor(focusedIdRef.current);
        return;
      }

      // h — hide
      if (key === "h" && bare) {
        if (selectedIdsRef.current.size > 0 || focusedIdRef.current) {
          e.preventDefault();
          handleHide();
          return;
        }
      }

      // s — star
      if (key === "s" && bare) {
        if (selectedIdsRef.current.size > 0 || focusedIdRef.current) {
          e.preventDefault();
          handleStar();
          return;
        }
      }

      // z — focus mode (quotes lens only)
      //
      // Needs no focused or selected quote (it's a view state, not a quote
      // mutation), but does need a route guard the sibling bare keys don't:
      //
      // 1. Modifiers, via the shared `bare` predicate — ⌘Z is Undo, and the
      //    report has inline quote/heading/name editing. This was the first
      //    handler to need the guard, and for a while the only one with it.
      // 2. Route. The recede transform is defined for quote cards; the native
      //    View-menu twin dims off this lens, and the two must agree or the
      //    menu says "unavailable" while the key still works.
      if (key === "z" && bare) {
        if (pathMatches(locationRef.current.pathname, "/report/quotes")) {
          e.preventDefault();
          toggleFocusMode();
          return;
        }
      }

      // t — add tag
      if (key === "t" && focusedIdRef.current) {
        e.preventDefault();
        handleTagOpen();
        return;
      }

      // r — repeat last tag (quick-apply to focused/selected quotes)
      if (key === "r" && (focusedIdRef.current || selectedIdsRef.current.size > 0)) {
        e.preventDefault();
        handleQuickApply();
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

    // ── Menu action handler (native menu bar → bridge) ────────────────
    const handleMenuAction = (e: Event) => {
      const { action } = (e as CustomEvent).detail;
      // Mirror the keydown path's lens gate — see QUOTE_SCOPED_MENU_ACTIONS.
      if (
        QUOTE_SCOPED_MENU_ACTIONS.has(action) &&
        !pathMatches(locationRef.current.pathname, "/report/quotes")
      ) {
        return;
      }
      switch (action) {
        case "star":
          handleStar();
          break;
        case "hide":
          handleHide();
          break;
        case "addTag":
          handleTagOpen();
          break;
        case "applyLastTag":
          handleQuickApply();
          break;
        case "playPause":
          sendCommand("playPause");
          break;
        case "skipForward5":
          sendCommand("skipRelative", { seconds: 5 });
          break;
        case "skipBack5":
          sendCommand("skipRelative", { seconds: -5 });
          break;
        case "skipForward30":
          sendCommand("skipRelative", { seconds: 30 });
          break;
        case "skipBack30":
          sendCommand("skipRelative", { seconds: -30 });
          break;
        case "speedUp":
          sendCommand("speedStep", { delta: 0.25 });
          break;
        case "slowDown":
          sendCommand("speedStep", { delta: -0.25 });
          break;
        case "normalSpeed":
          sendCommand("setSpeed", { rate: 1 });
          break;
        case "volumeUp":
          sendCommand("volumeStep", { delta: 0.1 });
          break;
        case "volumeDown":
          sendCommand("volumeStep", { delta: -0.1 });
          break;
        case "mute":
          sendCommand("toggleMute");
          break;
        case "pictureInPicture":
          sendCommand("togglePip");
          break;
        case "fullscreen":
          sendCommand("toggleFullscreen");
          break;
        case "nextQuote":
          moveFocus(1);
          break;
        case "previousQuote":
          moveFocus(-1);
          break;
        case "extendSelectionDown":
          handleShiftMove(1);
          break;
        case "extendSelectionUp":
          handleShiftMove(-1);
          break;
        case "toggleSelection":
          if (focusedIdRef.current) {
            toggleSelection(focusedIdRef.current);
            if (!anchorIdRef.current) setAnchor(focusedIdRef.current);
          }
          break;
        case "selectAllQuotes":
          selectAll();
          break;
        case "clearSelection":
          clearSelection();
          break;
        case "revealInTranscript": {
          const fid = focusedIdRef.current;
          if (!fid) break;
          const bq = document.getElementById(fid);
          const pid = bq?.getAttribute("data-participant");
          const anchor = bq?.getAttribute("data-anchor");
          if (pid && anchor) {
            navigate(`/report/sessions/${pid}#${anchor}`);
          }
          break;
        }
      }
    };

    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("click", handleBackgroundClick);
    window.addEventListener("bn:menu-action", handleMenuAction);

    // Track editing state transitions for the native bridge.
    // focusin/focusout bubble (unlike focus/blur), so a single document
    // listener catches all input focus transitions.
    let wasEditing = false;
    const embedded = isEmbedded();

    const handleFocusChange = () => {
      const nowEditing = isEditing();
      if (nowEditing && !wasEditing) {
        postEditingStarted(document.activeElement?.tagName ?? "unknown");
        wasEditing = true;
      } else if (!nowEditing && wasEditing) {
        postEditingEnded();
        wasEditing = false;
      }
    };

    if (embedded) {
      document.addEventListener("focusin", handleFocusChange);
      document.addEventListener("focusout", handleFocusChange);
    }

    return () => {
      document.removeEventListener("keydown", handleKeydown);
      document.removeEventListener("click", handleBackgroundClick);
      window.removeEventListener("bn:menu-action", handleMenuAction);
      if (embedded) {
        document.removeEventListener("focusin", handleFocusChange);
        document.removeEventListener("focusout", handleFocusChange);
      }
    };
  }, [
    onToggleHelp,
    onToggleSettings,
    clearSearch,
    clearSelection,
    setFocus,
    navigate,
    focusSearchInput,
    handleShiftMove,
    handleShiftMoveSpatial,
    moveFocus,
    moveFocusSpatial,
    toggleSelection,
    selectAll,
    getVisibleQuoteIds,
    setAnchor,
    handleHide,
    handleStar,
    handleTagOpen,
    handleQuickApply,
    handlePlay,
    sendCommand,
  ]);
}
