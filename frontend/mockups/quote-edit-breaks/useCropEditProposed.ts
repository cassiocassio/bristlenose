/**
 * The proposal's version of hooks/useCropEdit.ts.
 *
 * Same three modes (idle → hybrid → crop) and the same drag. What changes:
 *  - the edit modes keep the blocks shown at rest (frozen until commit);
 *  - Shift-Return / Option-Return start a paragraph at the caret,
 *    Backspace at a paragraph's start and Delete at its end join;
 *  - commit writes the words (a QuoteEdit) only if the words changed, and the
 *    paragraphs (the quote_breaks overlay) only if they changed by hand.
 *
 * The host element is drawn by proposedDom.ts, never by React.
 */

import { useCallback, useRef, useState } from "react";
import { sameWords } from "../../src/utils/sameWords";
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
} from "./proposedDom";

type CropMode = "idle" | "hybrid" | "crop";

const MIN_DRAG = 5;

export interface CommitResult {
  /** New words, if they changed. */
  text: string | null;
  /** New researcher breaks (null = automatic), if they changed. */
  breaks: { value: number[] | null } | null;
}

interface Options {
  currentText: string;
  /** The researcher's own breaks for this quote, or null (automatic). */
  researcherBreaks: number[] | null;
  /** The breaks drawn at rest right now. */
  shownBreaks: number[];
  onCommit: (r: CommitResult) => void;
  onKey: (what: string) => void;
}

export function useCropEditProposed({ currentText, researcherBreaks, shownBreaks, onCommit, onKey }: Options) {
  const [mode, setMode] = useState<CropMode>("idle");
  const [hasLeftCrop, setHasLeftCrop] = useState(false);
  const [hasRightCrop, setHasRightCrop] = useState(false);
  // Trim mode draws from these; text mode draws once and reads the host back.
  const [cropStart, setCropStart] = useState(0);
  const [cropEnd, setCropEnd] = useState(0);
  const model = useRef<EditModel>({ words: [], breaks: [], cropStart: 0, cropEnd: 0 });
  const touched = useRef(false);
  const preEditText = useRef(currentText);
  const suppressBlurRef = useRef(false);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enterEditMode = useCallback(() => {
    if (mode !== "idle") return;
    const words = currentText.split(/\s+/).filter(Boolean);
    preEditText.current = currentText;
    touched.current = false;
    model.current = { words, breaks: [...shownBreaks], cropStart: 0, cropEnd: words.length };
    setCropStart(0);
    setCropEnd(words.length);
    setMode("hybrid");
  }, [mode, currentText, shownBreaks]);

  const reenterTextEdit = useCallback(() => setMode("hybrid"), []);

  /** In text mode the host holds the truth; bring the model up to date from it. */
  const sync = useCallback((host: HTMLElement | null) => {
    if (host && mode === "hybrid") model.current = read(host);
    return model.current;
  }, [mode]);

  const commitEdit = useCallback(
    (host?: HTMLElement | null) => {
      if (mode === "idle") return;
      const m = sync(host ?? null);
      const kept = m.words.slice(m.cropStart, m.cropEnd);
      const keptBreaks = m.breaks.filter((b) => b >= m.cropStart && b < m.cropEnd - 1).map((b) => b - m.cropStart);
      const newText = kept.join(" ");
      setHasLeftCrop((v) => v || m.cropStart > 0);
      setHasRightCrop((v) => v || m.cropEnd < m.words.length);
      setMode("idle");
      suppressBlurRef.current = false;
      if (newText.length === 0) {
        onCommit({ text: null, breaks: null });
        return;
      }
      const textChanged = !sameWords(newText, preEditText.current);
      let next: number[] | null;
      if (touched.current) {
        next = sameBreaks(keptBreaks, autoBreaks(newText)) ? null : keptBreaks;
      } else if (researcherBreaks !== null) {
        next = keptBreaks; // their own breaks, carried through the word edit
      } else {
        next = null;
      }
      onCommit({
        text: textChanged ? newText : null,
        breaks: sameBreaks(next, researcherBreaks) ? null : { value: next },
      });
    },
    [mode, sync, researcherBreaks, onCommit],
  );

  const cancelEdit = useCallback(() => {
    setMode("idle");
    suppressBlurRef.current = false;
    onCommit({ text: null, breaks: null });
  }, [onCommit]);

  // ── Paragraph keys (text mode) ──────────────────────────────────────

  const redraw = (host: HTMLElement, m: EditModel, bracketsVisible: boolean) => {
    draw(host, m, { mode: "hybrid", leftEllipsis: hasLeftCrop, rightEllipsis: hasRightCrop, bracketsVisible });
  };

  /** Shift-Return / Option-Return. Returns what happened, for the key echo. */
  const splitAtCaret = useCallback(
    (host: HTMLElement, bracketsVisible: boolean): string => {
      const at = caretPlace(host);
      const m = read(host);
      if (!at) return "nothing (a selection, not a caret)";
      const ranges = blockRanges(m.words.length, m.breaks);
      const [s, e] = ranges[at.block];
      const g = firstTyped(m, at.block) + at.word;
      if (g <= s || g >= e) return "nothing (already a paragraph edge)";
      m.breaks = [...m.breaks, g - 1].sort((a, b) => a - b);
      model.current = m;
      touched.current = true;
      redraw(host, m, bracketsVisible);
      placeCaret(host, m, g);
      return `new paragraph before “${m.words[g]}”`;
    },
    [hasLeftCrop, hasRightCrop],
  );

  /** Backspace at a paragraph's start (dir -1) or Delete at its end (dir +1). Null = not at an edge. */
  const joinAtCaret = useCallback(
    (host: HTMLElement, dir: -1 | 1, bracketsVisible: boolean): string | null => {
      const at = caretPlace(host);
      if (!at) return null;
      if (dir === -1 ? !at.atStart : !at.atEnd) return null;
      const m = read(host);
      const ranges = blockRanges(m.words.length, m.breaks);
      if (dir === -1 && (at.excludedBefore || at.block === 0)) return "nothing (start of the quote)";
      if (dir === 1 && (at.excludedAfter || at.block === ranges.length - 1)) return "nothing (end of the quote)";
      const gone = dir === -1 ? ranges[at.block][0] - 1 : ranges[at.block][1] - 1;
      m.breaks = m.breaks.filter((b) => b !== gone);
      model.current = m;
      touched.current = true;
      redraw(host, m, bracketsVisible);
      if (dir === -1) placeCaret(host, m, gone + 1);
      else placeCaret(host, m, gone, true);
      return `joined to the paragraph ${dir === -1 ? "above" : "below"}`;
    },
    [hasLeftCrop, hasRightCrop],
  );

  // ── Bracket drag (as useCropEdit, reading the host back first) ─────

  const handleBracketPointerDown = useCallback(
    (side: "start" | "end", e: PointerEvent, host: HTMLElement) => {
      if (mode === "idle") return;
      e.preventDefault();
      e.stopPropagation();
      suppressBlurRef.current = true;
      if (blurTimeoutRef.current) {
        clearTimeout(blurTimeoutRef.current);
        blurTimeoutRef.current = null;
      }
      const snap = mode === "hybrid" ? read(host) : { ...model.current };
      const dragStartX = e.clientX;
      let dragConfirmed = false;
      let localStart = snap.cropStart;
      let localEnd = snap.cropEnd;

      const onMove = (ev: PointerEvent) => {
        if (!dragConfirmed) {
          if (Math.abs(ev.clientX - dragStartX) < MIN_DRAG) return;
          dragConfirmed = true;
          model.current = snap;
          setCropStart(localStart);
          setCropEnd(localEnd);
          setMode("crop");
          onKey("drag a bracket → trim");
        }
        const wordEls = host.querySelectorAll(".crop-word");
        if (wordEls.length === 0) return;
        const firstRect = wordEls[0].getBoundingClientRect();
        const lastRect = wordEls[wordEls.length - 1].getBoundingClientRect();
        let closestIdx: number;
        if (ev.clientY < firstRect.top) closestIdx = 0;
        else if (ev.clientY > lastRect.bottom) closestIdx = Number(wordEls[wordEls.length - 1].getAttribute("data-i") ?? 0);
        else {
          closestIdx = 0;
          let best = Infinity;
          for (let i = 0; i < wordEls.length; i++) {
            const r = wordEls[i].getBoundingClientRect();
            const cx = Math.max(r.left, Math.min(ev.clientX, r.right));
            const cy = Math.max(r.top, Math.min(ev.clientY, r.bottom));
            const d = Math.hypot(ev.clientX - cx, ev.clientY - cy);
            if (d < best) {
              best = d;
              closestIdx = Number(wordEls[i].getAttribute("data-i") ?? 0);
            }
          }
        }
        if (side === "start") {
          const ns = Math.max(0, Math.min(closestIdx, localEnd - 1));
          if (ns !== localStart) {
            localStart = ns;
            model.current = { ...model.current, cropStart: ns };
            setCropStart(ns);
          }
        } else {
          const ne = Math.min(snap.words.length, Math.max(closestIdx + 1, localStart + 1));
          if (ne !== localEnd) {
            localEnd = ne;
            model.current = { ...model.current, cropEnd: ne };
            setCropEnd(ne);
          }
        }
      };
      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        if (!dragConfirmed) {
          suppressBlurRef.current = false;
          return;
        }
        const card = host.closest("blockquote");
        if (card instanceof HTMLElement) {
          card.setAttribute("tabindex", "-1");
          card.focus();
        }
      };
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [mode, onKey],
  );

  return {
    mode,
    model,
    cropStart,
    cropEnd,
    hasLeftCrop,
    hasRightCrop,
    suppressBlurRef,
    blurTimeoutRef,
    enterEditMode,
    reenterTextEdit,
    commitEdit,
    cancelEdit,
    splitAtCaret,
    joinAtCaret,
    handleBracketPointerDown,
  };
}
