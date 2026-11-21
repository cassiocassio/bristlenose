/**
 * useCropEdit — state machine for unified quote editing + crop trimming.
 *
 * Three modes:
 *   idle   — plain text, no interactivity
 *   hybrid — the words are editable, with bracket handles (mode 2)
 *   crop   — individual word spans, handles snap to words (mode 3)
 *
 * The edit modes draw the quote as the same paragraphs it shows at rest,
 * frozen until commit (utils/quoteEditSurface.ts draws them). Shift-Return
 * starts a paragraph at the caret; Backspace at a paragraph's start and Delete
 * at its end join. A commit says what changed: the words (a QuoteEdit) only if
 * the words changed, and the researcher's own paragraphs (the quote_breaks
 * overlay) only if they were placed or removed by hand, or the words under
 * them changed.
 *
 * See docs/design-quote-editing.md for the full behaviour spec.
 */

import { useState, useRef, useCallback } from "react";
import { sameWords } from "../utils/sameWords";
import {
  autoBreaks,
  blockRanges,
  caretPlace,
  draw,
  firstTyped,
  placeCaret,
  read,
  sameBreaks,
  type EditModel,
} from "../utils/quoteEditSurface";

// ── Types ────────────────────────────────────────────────────────────────

export type CropMode = "idle" | "hybrid" | "crop";

/** A change to the researcher's own paragraphs: `value` null hands them back to the automatic placing. */
export interface BreaksChange {
  value: number[] | null;
}

export interface UseCropEditOptions {
  /** Current display text (may already be edited). */
  currentText: string;
  /** Original pipeline text (for undo comparison). */
  originalText: string;
  /** The researcher's own breaks for this quote, or null (placed automatically). */
  researcherBreaks?: number[] | null;
  /** The breaks drawn at rest right now: what the edit modes freeze. */
  shownBreaks?: number[];
  /**
   * Whether the Display setting places paragraphs automatically. The
   * researcher's paragraphs are compared with what rest would show without
   * them under this setting: with it off that is none, so any paragraph they
   * place is theirs (owner, 21 Nov 2026; review finding 4).
   */
  autoBreaksOn?: boolean;
  /**
   * Called when an edit/crop is committed with something to write. `text` is
   * the trimmed text (no ellipsis), or null when only the paragraphs changed;
   * `breaks` is present only when the paragraphs are written.
   */
  onCommit: (text: string | null, breaks?: BreaksChange) => void;
  /** Called when the user cancels (Escape), or commits nothing. */
  onCancel: () => void;
}

export interface UseCropEditReturn {
  mode: CropMode;
  /** Full word array (included + excluded) at the start of the edit, or after a drag. */
  words: string[];
  /** Index of first included word. */
  cropStart: number;
  /** Index past last included word. */
  cropEnd: number;
  /** Whether the left edge was cropped on last commit. */
  hasLeftCrop: boolean;
  /** Whether the right edge was cropped on last commit. */
  hasRightCrop: boolean;

  /** Ref that suppresses blur-triggered commits. Must be synchronous (not state). */
  suppressBlurRef: React.RefObject<boolean>;
  /** Ref to the blur timeout ID for cleanup. */
  blurTimeoutRef: React.RefObject<ReturnType<typeof setTimeout> | null>;

  /** Enter hybrid edit mode. Call on quote text click. */
  enterEditMode: () => void;
  /** Bracket pointerdown handler. Initiates drag. */
  handleBracketPointerDown: (
    side: "start" | "end",
    e: React.PointerEvent | PointerEvent,
    textSpanEl: HTMLElement,
  ) => void;
  /** Commit the current edit/crop. In text mode, pass the edit surface to read it back. */
  commitEdit: (host?: HTMLElement | null) => void;
  /** Cancel and revert to pre-edit state. */
  cancelEdit: () => void;
  /** Switch from crop mode back to hybrid (click on included word). */
  reenterTextEdit: () => void;
  /** Drop any pending blur commit and ignore the next blur: a commit is being made now. */
  holdBlur: () => void;
  /** Draw the edit surface into `host` for the current mode. */
  drawSurface: (host: HTMLElement, bracketsVisible: boolean) => void;
  /** Shift-Return: a paragraph at the caret. True if one was made. */
  splitAtCaret: (host: HTMLElement, bracketsVisible: boolean) => boolean;
  /**
   * Backspace at a paragraph's start (-1) or Delete at its end (+1): join.
   * "joined", "edge" (at the quote's own start or end: nothing to do, and the
   * key must not reach the browser) or null (not at a paragraph edge).
   */
  joinAtCaret: (host: HTMLElement, dir: -1 | 1, bracketsVisible: boolean) => "joined" | "edge" | null;
}

// Minimum pointer movement (px) before a bracket click becomes a drag.
const MIN_DRAG = 5;

// ── Hook ─────────────────────────────────────────────────────────────────

export function useCropEdit({
  currentText,
  originalText: _originalText,
  researcherBreaks = null,
  shownBreaks,
  autoBreaksOn = true,
  onCommit,
  onCancel,
}: UseCropEditOptions): UseCropEditReturn {
  // _originalText reserved for future re-expansion; undo is handled by QuoteCard
  void _originalText;
  const [mode, setModeState] = useState<CropMode>("idle");
  // The mode as of now, not as of the last render: a blur timer or a click
  // that fires after a commit holds a render-old `mode` and would commit the
  // same edit twice (two writes, two undo entries; Tab, 21 Nov 2026).
  const modeNow = useRef<CropMode>("idle");
  const setMode = useCallback((m: CropMode) => {
    modeNow.current = m;
    setModeState(m);
  }, []);
  const [words, setWords] = useState<string[]>([]);
  const [cropStart, setCropStart] = useState(0);
  const [cropEnd, setCropEnd] = useState(0);
  const [hasLeftCrop, setHasLeftCrop] = useState(false);
  const [hasRightCrop, setHasRightCrop] = useState(false);

  const suppressBlurRef = useRef(false);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearBlurHold = useCallback(() => {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    blurTimeoutRef.current = null;
    suppressBlurRef.current = false;
  }, []);

  // The edit as the model holds it. In text mode the surface holds the truth
  // and is read back into this on every structural key and on commit; in trim
  // mode this is the truth and the surface is drawn from it.
  const model = useRef<EditModel>({ words: [], breaks: [], cropStart: 0, cropEnd: 0 });
  // Whether a paragraph was placed or removed by hand in this edit.
  const touched = useRef(false);

  // Snapshot of text at time of entering edit mode (for cancel).
  const preEditTextRef = useRef(currentText);

  // ── Enter hybrid edit mode ───────────────────────────────────────────

  const enterEditMode = useCallback(() => {
    if (mode !== "idle") return;
    preEditTextRef.current = currentText;
    touched.current = false;
    // A hold or a blur timer left by the last edit belongs to it, not to this
    // one: Tab in trimming holds a blur that never comes (finding 10).
    clearBlurHold();
    const w = currentText.split(/\s+/).filter(Boolean);
    model.current = { words: w, breaks: [...(shownBreaks ?? [])], cropStart: 0, cropEnd: w.length };
    setWords(w);
    setCropStart(0);
    setCropEnd(w.length);
    setMode("hybrid");
  }, [mode, currentText, shownBreaks, setMode, clearBlurHold]);

  // ── Re-enter hybrid from crop mode ──────────────────────────────────

  const reenterTextEdit = useCallback(() => {
    clearBlurHold();
    setMode("hybrid");
  }, [setMode, clearBlurHold]);

  // ── Commit ──────────────────────────────────────────────────────────

  const commitEdit = useCallback(
    (host?: HTMLElement | null) => {
      if (mode === "idle" || modeNow.current === "idle") return;
      if (mode === "hybrid" && host) model.current = read(host);
      else if (mode === "hybrid") {
        // No surface to read (it is already gone): what was there on entry.
        const w = currentText.split(/\s+/).filter(Boolean);
        model.current = { ...model.current, words: w, cropStart: 0, cropEnd: w.length };
      }
      const m = model.current;
      const kept = m.words.slice(m.cropStart, m.cropEnd);
      const keptBreaks = m.breaks
        .filter((b) => b >= m.cropStart && b < m.cropEnd - 1)
        .map((b) => b - m.cropStart);
      const newText = kept.join(" ");

      setHasLeftCrop((v) => v || m.cropStart > 0);
      setHasRightCrop((v) => v || m.cropEnd < m.words.length);
      setMode("idle");
      suppressBlurRef.current = false;

      if (newText.length === 0) {
        onCancel();
        return;
      }
      // An edit opened and left as it was (clicked into, then blurred, clicked
      // outside or Enter) is not an edit: it writes nothing and adds no Undo.
      // The card's unmount path commits through here too (QuoteCard, R88).
      // Compared with the text before the edit, not `words`: a bracket drag
      // re-bases `words` on what was typed, which would read as unchanged.
      // A change only in spacing is no edit either way (decision #30).
      const textChanged = !sameWords(newText, preEditTextRef.current);
      // The paragraphs: placed by hand in this edit, they are the
      // researcher's own (unless they came out exactly as the automatic
      // ones); already the researcher's, they are carried through the edit;
      // otherwise they stay automatic and are placed again from the words.
      let next: number[] | null;
      const automatic = autoBreaksOn ? autoBreaks(newText) : [];
      if (touched.current) next = sameBreaks(keptBreaks, automatic) ? null : keptBreaks;
      else if (researcherBreaks !== null) next = keptBreaks;
      else next = null;
      // Their own breaks are written again whenever the words under them change:
      // the server keeps them against the wording they were placed in.
      const breaksChanged = !sameBreaks(next, researcherBreaks) || (textChanged && next !== null);
      if (!textChanged && !breaksChanged) onCancel();
      else if (!breaksChanged) onCommit(newText);
      else onCommit(textChanged ? newText : null, { value: next });
    },
    [mode, currentText, researcherBreaks, autoBreaksOn, onCommit, onCancel, setMode],
  );

  const holdBlur = useCallback(() => {
    if (blurTimeoutRef.current) {
      clearTimeout(blurTimeoutRef.current);
      blurTimeoutRef.current = null;
    }
    suppressBlurRef.current = true;
  }, []);

  // ── Cancel ──────────────────────────────────────────────────────────

  const cancelEdit = useCallback(() => {
    setMode("idle");
    suppressBlurRef.current = false;
    setHasLeftCrop(false);
    setHasRightCrop(false);
    onCancel();
  }, [onCancel, setMode]);

  // ── The surface ─────────────────────────────────────────────────────

  const drawSurface = useCallback(
    (host: HTMLElement, bracketsVisible: boolean) => {
      if (mode === "idle") return;
      const m = mode === "crop" ? { ...model.current, cropStart, cropEnd } : model.current;
      draw(host, m, { mode, leftEllipsis: hasLeftCrop, rightEllipsis: hasRightCrop, bracketsVisible });
    },
    [mode, cropStart, cropEnd, hasLeftCrop, hasRightCrop],
  );

  const splitAtCaret = useCallback(
    (host: HTMLElement, bracketsVisible: boolean): boolean => {
      const at = caretPlace(host);
      if (!at || at.empty) return false; // an emptied paragraph has nothing to split
      const m = read(host);
      const range = blockRanges(m.words.length, m.breaks)[at.block];
      if (!range) return false;
      const [s, e] = range;
      const g = firstTyped(m, at.block) + at.word;
      if (g <= s || g >= e) return false; // already a paragraph's edge
      m.breaks = [...m.breaks, g - 1].sort((a, b) => a - b);
      model.current = m;
      touched.current = true;
      draw(host, m, { mode: "hybrid", leftEllipsis: hasLeftCrop, rightEllipsis: hasRightCrop, bracketsVisible });
      placeCaret(host, m, g);
      return true;
    },
    [hasLeftCrop, hasRightCrop],
  );

  const joinAtCaret = useCallback(
    (host: HTMLElement, dir: -1 | 1, bracketsVisible: boolean): "joined" | "edge" | null => {
      const at = caretPlace(host);
      if (!at || (dir === -1 ? !at.atStart : !at.atEnd)) return null;
      const m = read(host);
      const ranges = blockRanges(m.words.length, m.breaks);
      const draw2 = () =>
        draw(host, m, { mode: "hybrid", leftEllipsis: hasLeftCrop, rightEllipsis: hasRightCrop, bracketsVisible });
      if (at.empty) {
        // A paragraph emptied of its words: the key takes it away, and the
        // caret goes to where the join would put it (review 21 Nov, finding 5).
        model.current = m;
        touched.current = true;
        draw2();
        const prev = ranges[at.block - 1];
        const next = ranges[at.block];
        if (dir === -1 && prev) placeCaret(host, m, prev[1] - 1, true);
        else if (next) placeCaret(host, m, next[0]);
        else if (prev) placeCaret(host, m, prev[1] - 1, true);
        return "joined";
      }
      if (!ranges[at.block]) return null;
      if (dir === -1 && (at.excludedBefore || at.block === 0)) return "edge";
      if (dir === 1 && (at.excludedAfter || at.block === ranges.length - 1)) return "edge";
      const gone = dir === -1 ? ranges[at.block][0] - 1 : ranges[at.block][1] - 1;
      m.breaks = m.breaks.filter((b) => b !== gone);
      model.current = m;
      touched.current = true;
      draw(host, m, { mode: "hybrid", leftEllipsis: hasLeftCrop, rightEllipsis: hasRightCrop, bracketsVisible });
      if (dir === -1) placeCaret(host, m, gone + 1);
      else placeCaret(host, m, gone, true);
      return "joined";
    },
    [hasLeftCrop, hasRightCrop],
  );

  // ── Bracket drag ────────────────────────────────────────────────────

  const handleBracketPointerDown = useCallback(
    (side: "start" | "end", e: React.PointerEvent | PointerEvent, textSpanEl: HTMLElement) => {
      if (mode === "idle") return;
      e.preventDefault();
      e.stopPropagation();

      // Suppress blur from the contenteditable losing focus
      suppressBlurRef.current = true;
      if (blurTimeoutRef.current) {
        clearTimeout(blurTimeoutRef.current);
        blurTimeoutRef.current = null;
      }

      // Snapshot the surface before switching to crop mode: the researcher
      // may have typed edits, and placed paragraphs, that must be kept.
      const snap: EditModel = mode === "hybrid" ? read(textSpanEl) : { ...model.current };

      const dragStartX = e.clientX;
      let dragConfirmed = false;
      let localStart = snap.cropStart;
      let localEnd = snap.cropEnd;

      const onMove = (ev: PointerEvent) => {
        if (!dragConfirmed) {
          if (Math.abs(ev.clientX - dragStartX) < MIN_DRAG) return;
          dragConfirmed = true;
          // Commit the snapshot and switch to crop mode
          model.current = snap;
          setWords(snap.words);
          setCropStart(localStart);
          setCropEnd(localEnd);
          setMode("crop");
        }

        // 2D hit detection: find nearest word span to pointer
        const wordEls = textSpanEl.querySelectorAll(".crop-word");
        if (wordEls.length === 0) return;

        const firstRect = wordEls[0].getBoundingClientRect();
        const lastRect = wordEls[wordEls.length - 1].getBoundingClientRect();
        const px = ev.clientX;
        const py = ev.clientY;
        let closestIdx: number;

        if (py < firstRect.top) {
          // Above all text → first word
          closestIdx = 0;
        } else if (py > lastRect.bottom) {
          // Below all text → last word
          closestIdx = parseInt(
            wordEls[wordEls.length - 1].getAttribute("data-i") ?? "0",
            10,
          );
        } else {
          // Normal 2D Euclidean distance scan
          closestIdx = 0;
          let closestDist = Infinity;
          for (let i = 0; i < wordEls.length; i++) {
            const rect = wordEls[i].getBoundingClientRect();
            const cx = Math.max(rect.left, Math.min(px, rect.right));
            const cy = Math.max(rect.top, Math.min(py, rect.bottom));
            const dist = Math.sqrt((px - cx) ** 2 + (py - cy) ** 2);
            if (dist < closestDist) {
              closestDist = dist;
              closestIdx = parseInt(
                wordEls[i].getAttribute("data-i") ?? "0",
                10,
              );
            }
          }
        }

        if (side === "start") {
          const newStart = Math.max(0, Math.min(closestIdx, localEnd - 1));
          if (newStart !== localStart) {
            localStart = newStart;
            model.current = { ...model.current, cropStart: newStart };
            setCropStart(newStart);
          }
        } else {
          const newEnd = Math.min(
            snap.words.length,
            Math.max(closestIdx + 1, localStart + 1),
          );
          if (newEnd !== localEnd) {
            localEnd = newEnd;
            model.current = { ...model.current, cropEnd: newEnd };
            setCropEnd(newEnd);
          }
        }
      };

      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);

        if (!dragConfirmed) {
          // Below threshold — no-op click on bracket
          suppressBlurRef.current = false;
          return;
        }

        // Focus the card so Enter/Escape work in crop mode.
        // The parent QuoteCard will set tabindex=-1 on the blockquote.
        const card = textSpanEl.closest("blockquote");
        if (card instanceof HTMLElement) {
          card.setAttribute("tabindex", "-1");
          card.focus();
        }
      };

      // Document-level listeners survive DOM rebuilds during drag.
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [mode, setMode],
  );

  return {
    mode,
    words,
    cropStart,
    cropEnd,
    hasLeftCrop,
    hasRightCrop,
    suppressBlurRef,
    blurTimeoutRef,
    enterEditMode,
    handleBracketPointerDown,
    commitEdit,
    cancelEdit,
    reenterTextEdit,
    holdBlur,
    drawSurface,
    splitAtCaret,
    joinAtCaret,
  };
}
