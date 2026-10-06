/**
 * Split and join transcript paragraphs, undoably (design-transcript-editing.md
 * §"Split and join, stage 1").
 *
 * The common case (owner, 6 Oct 2026): a long paragraph that does not read as
 * one thing, split in two with the same speaker by placing the caret and
 * pressing Return; Backspace at the start of a paragraph joins it to the one
 * above. The server records each edit and makes it again after every import;
 * undo forgets it. Every edit counts in words as the page draws them — Whisper's
 * words where the paragraph has them, else its text — so the cut lands where the
 * researcher put the caret, at the word boundary before it.
 */

import { pushUndo } from "../contexts/UndoStore";
import { deleteParagraphEdit, postParagraphJoin, postParagraphSplit } from "./api";

/** Fired when a split, a join or its undo has landed, so the transcript re-reads. */
export const TRANSCRIPT_WRITTEN_EVENT = "bn:transcript-written";

/** How many words an edit sends to check it lands where it was made — the
 *  server's ``VERIFY_WORDS``. */
const VERIFY_WORDS = 6;

/** A paragraph's words as the page draws them. */
export function drawnTokens(text: string, words: { text: string }[] | null | undefined): string[] {
  if (words && words.length > 0) return words.map((w) => w.text.trim());
  return text.split(/\s+/).filter(Boolean);
}

export function verifyOf(tokens: string[], from: number): string {
  return tokens.slice(from, from + VERIFY_WORDS).join(" ");
}

/**
 * Where a collapsed caret sits in a paragraph, in words: how many whole words
 * precede it. A caret inside a word cuts before that word. ``null`` when the
 * caret is not in ``body`` or a range is selected.
 */
export function caretWords(body: HTMLElement): number | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return null;
  const caret = sel.getRangeAt(0);
  if (!body.contains(caret.startContainer)) return null;
  const before = document.createRange();
  before.selectNodeContents(body);
  before.setEnd(caret.startContainer, caret.startOffset);
  const text = before.toString();
  const after = (body.textContent ?? "").slice(text.length);
  const whole = text.split(/\s+/).filter(Boolean).length;
  if (text.length === 0 || /\s$/.test(text)) return whole;
  // Touching a word: at its end it counts; inside it, the cut goes before it.
  return after.length === 0 || /^\s/.test(after) ? whole : whole - 1;
}

/** Whether a collapsed caret sits before every character of ``body`` — where
 *  Backspace joins. Not ``caretWords(body) === 0``: that is also true inside
 *  the first word, and anywhere in a paragraph with no spaces. */
export function caretAtStart(body: HTMLElement): boolean {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return false;
  const caret = sel.getRangeAt(0);
  if (!body.contains(caret.startContainer)) return false;
  const before = document.createRange();
  before.selectNodeContents(body);
  before.setEnd(caret.startContainer, caret.startOffset);
  return before.toString().trim().length === 0;
}

function written(): void {
  window.dispatchEvent(new CustomEvent(TRANSCRIPT_WRITTEN_EVENT));
}

/** Split paragraph ``position`` after ``token`` words. Undo forgets the split;
 *  redo makes it again. Resolves once the split has landed. */
export async function splitParagraph(
  sessionId: string, position: number, token: number, verify: string,
): Promise<void> {
  let id = (await postParagraphSplit(sessionId, position, token, verify)).id;
  written();
  pushUndo({
    action: "splitParagraph",
    undo: () => deleteParagraphEdit(sessionId, id).then(written),
    redo: () => postParagraphSplit(sessionId, position, token, verify).then((r) => {
      id = r.id;
      written();
    }),
  });
}

/** Join paragraph ``position`` onto the one above it. */
export async function joinParagraphs(sessionId: string, position: number, verify: string): Promise<void> {
  let id = (await postParagraphJoin(sessionId, position, verify)).id;
  written();
  pushUndo({
    action: "joinParagraphs",
    undo: () => deleteParagraphEdit(sessionId, id).then(written),
    redo: () => postParagraphJoin(sessionId, position, verify).then((r) => {
      id = r.id;
      written();
    }),
  });
}
