/**
 * useCropEdit — state machine for unified quote editing + crop trimming.
 *
 * Three modes:
 *   idle   — plain text, no interactivity
 *   hybrid — contenteditable + bracket handles (mode 2)
 *   crop   — individual word spans, handles snap to words (mode 3)
 *
 * See docs/design-quote-editing.md for the full behaviour spec.
 */

import { useState, useRef, useCallback } from "react";

// ── Types ────────────────────────────────────────────────────────────────

export type CropMode = "idle" | "hybrid" | "crop";

export interface UseCropEditOptions {
  /** Current display text (may already be edited). */
  currentText: string;
  /** Original pipeline text (for undo comparison). */
  originalText: string;
  /** Called when an edit/crop is committed. Receives the trimmed text (no ellipsis). */
  onCommit: (text: string) => void;
  /** Called when the user cancels (Escape). */
  onCancel: () => void;
}

export interface UseCropEditReturn {
  mode: CropMode;
  /** Full word array (included + excluded). Only meaningful in hybrid/crop modes. */
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
    e: React.PointerEvent,
    textSpanEl: HTMLElement,
  ) => void;
  /** Commit the current edit/crop. */
  commitEdit: (editableEl?: HTMLElement | null) => void;
  /** Cancel and revert to pre-edit state. */
  cancelEdit: () => void;
  /** Switch from crop mode back to hybrid (click on included word). */
  reenterTextEdit: () => void;
}

// Minimum pointer movement (px) before a bracket click becomes a drag.
const MIN_DRAG = 5;

// ── Hook ─────────────────────────────────────────────────────────────────

export function useCropEdit({
  currentText,
  originalText: _originalText,
  onCommit,
  onCancel,
}: UseCropEditOptions): UseCropEditReturn {
  // _originalText reserved for future re-expansion; undo is handled by QuoteCard
  void _originalText;
  const [mode, setMode] = useState<CropMode>("idle");
  const [words, setWords] = useState<string[]>([]);
  const [cropStart, setCropStart] = useState(0);
  const [cropEnd, setCropEnd] = useState(0);
  const [hasLeftCrop, setHasLeftCrop] = useState(false);
  const [hasRightCrop, setHasRightCrop] = useState(false);

  const suppressBlurRef = useRef(false);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Snapshot of text at time of entering edit mode (for cancel).
  const preEditTextRef = useRef(currentText);

  // ── Enter hybrid edit mode ───────────────────────────────────────────

  const enterEditMode = useCallback(() => {
    if (mode !== "idle") return;
    preEditTextRef.current = currentText;
    const w = currentText.split(/\s+/).filter(Boolean);
    setWords(w);
    setCropStart(0);
    setCropEnd(w.length);
    setMode("hybrid");
  }, [mode, currentText]);

  // ── Re-enter hybrid from crop mode ──────────────────────────────────

  const reenterTextEdit = useCallback(() => {
    setMode("hybrid");
  }, []);

  // ── Commit ──────────────────────────────────────────────────────────

  const commitEdit = useCallback(
    (editableEl?: HTMLElement | null) => {
      if (mode === "idle") return;

      let newText: string;
      let leftCrop = false;
      let rightCrop = false;

      if (mode === "crop") {
        // In word-span mode — use word boundaries
        const kept = words.slice(cropStart, cropEnd);
        newText = kept.join(" ");
        leftCrop = cropStart > 0;
        rightCrop = cropEnd < words.length;
      } else {
        // In hybrid mode — read from contenteditable
        const raw = editableEl?.textContent?.trim() ?? currentText;
        newText = raw;
        leftCrop = cropStart > 0;
        rightCrop = cropEnd < words.length;
      }

      setHasLeftCrop(leftCrop);
      setHasRightCrop(rightCrop);
      setMode("idle");
      suppressBlurRef.current = false;

      if (newText.length > 0) {
        onCommit(newText);
      } else {
        onCancel();
      }
    },
    [mode, words, cropStart, cropEnd, currentText, onCommit, onCancel],
  );

  // ── Cancel ──────────────────────────────────────────────────────────

  const cancelEdit = useCallback(() => {
    setMode("idle");
    suppressBlurRef.current = false;
    setHasLeftCrop(false);
    setHasRightCrop(false);
    onCancel();
  }, [onCancel]);

  // ── Bracket drag ────────────────────────────────────────────────────

  const handleBracketPointerDown = useCallback(
    (side: "start" | "end", e: React.PointerEvent, textSpanEl: HTMLElement) => {
      if (mode === "idle") return;
      e.preventDefault();
      e.stopPropagation();

      // Suppress blur from the contenteditable losing focus
      suppressBlurRef.current = true;
      if (blurTimeoutRef.current) {
        clearTimeout(blurTimeoutRef.current);
        blurTimeoutRef.current = null;
      }

      // Snapshot contenteditable text before switching to crop mode.
      // The user may have typed edits that need to be preserved.
      const editableSpan = textSpanEl.querySelector(".crop-editable");
      let snapshotWords = [...words];
      let snapshotStart = cropStart;
      let snapshotEnd = cropEnd;

      if (editableSpan && mode === "hybrid") {
        const editedText = (editableSpan.textContent ?? "").trim();
        const editedWords = editedText.split(/\s+/).filter(Boolean);

        if (snapshotStart > 0 || snapshotEnd < snapshotWords.length) {
          // Re-entering crop from hybrid with existing boundaries
          const before = snapshotWords.slice(0, snapshotStart);
          const after = snapshotWords.slice(snapshotEnd);
          snapshotWords = [...before, ...editedWords, ...after];
          snapshotEnd = snapshotStart + editedWords.length;
        } else {
          // First crop from fresh edit
          snapshotWords = editedWords;
          snapshotStart = 0;
          snapshotEnd = editedWords.length;
        }
      }

      const dragStartX = e.clientX;
      let dragConfirmed = false;
      let localStart = snapshotStart;
      let localEnd = snapshotEnd;

      const onMove = (ev: PointerEvent) => {
        if (!dragConfirmed) {
          if (Math.abs(ev.clientX - dragStartX) < MIN_DRAG) return;
          dragConfirmed = true;
          // Commit the snapshot and switch to crop mode
          setWords(snapshotWords);
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
            setCropStart(newStart);
          }
        } else {
          const newEnd = Math.min(
            snapshotWords.length,
            Math.max(closestIdx + 1, localStart + 1),
          );
          if (newEnd !== localEnd) {
            localEnd = newEnd;
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
    [mode, words, cropStart, cropEnd],
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
  };
}
