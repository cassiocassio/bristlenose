/**
 * What a drag-select copy of transcript paragraphs puts on the clipboard.
 *
 * Two flavours, written together (owner, 8 Oct 2026):
 *   text/plain — Markdown in the house transcript format, `**`[00:42]` p1** text`,
 *                one paragraph per block. Matches the `.md` transcript export.
 *   text/html  — the same structure for Word, Pages and Google Docs: the stamp
 *                bold, the timecode in a monospace face, no other styling, so the
 *                words take the document's own font.
 *
 * Words inside a single paragraph copy as plain text, unescaped: that is a
 * snippet for a sentence, not a document.
 *
 * The prototype and its worst cases: experiments/transcript-copy/.
 */

import type { ClipboardEvent as ReactClipboardEvent } from "react";
import { formatTimecode } from "./format";

export interface CopiedParagraph {
  seconds: number;
  code: string;
  text: string;
}

// CommonMark's ASCII punctuation: a backslash escapes exactly these.
const PUNCT = new Set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~");
const ENTITY = /^&(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);/;
const TAG_START = /[A-Za-z/!?]/;
const ALNUM = /[\p{L}\p{N}]/u;

/**
 * Escape only the characters that would change how speech renders as Markdown.
 *
 * The text never starts a line (the bold stamp comes first), so `#`, `-`, `>`
 * and `1.` are inert. Speech almost never needs any of this: 7 of 28,908 real
 * paragraphs did (8 Oct 2026). Mirrors `escape_markdown_speech` in
 * bristlenose/utils/markdown.py; tests/fixtures/shared-format-contract.json pins both.
 */
export function escapeMarkdownSpeech(text: string): string {
  const chars = Array.from(text);
  let out = "";
  chars.forEach((ch, i) => {
    const prev = i > 0 ? chars[i - 1] : " ";
    const next = i + 1 < chars.length ? chars[i + 1] : " ";
    let esc = false;
    if (ch === "\\") esc = PUNCT.has(next) || i === chars.length - 1;
    else if (ch === "*" || ch === "`") esc = true;
    else if (ch === "_") esc = !(ALNUM.test(prev) && ALNUM.test(next)); // intraword is inert
    else if (ch === "~") esc = true; // strikethrough: GitHub and Slack take a single ~ too
    else if (ch === "]") esc = next === "("; // a link destination; a copy carries no definitions
    else if (ch === "<") esc = TAG_START.test(next); // a tag or an autolink
    else if (ch === "&") esc = ENTITY.test(chars.slice(i).join(""));
    out += esc ? `\\${ch}` : ch;
  });
  return out;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Both clipboard flavours for a selection spanning several paragraphs. */
export function transcriptClipboard(paras: CopiedParagraph[]): { plain: string; html: string } {
  const plain = paras
    .map((p) => `**\`[${formatTimecode(p.seconds)}]\` ${p.code}** ${escapeMarkdownSpeech(p.text)}`)
    .join("\n\n");
  const html =
    '<meta charset="utf-8">' +
    paras
      .map(
        (p) =>
          `<p><b><span style="font-family:Menlo,Consolas,monospace">[${formatTimecode(p.seconds)}]</span> ` +
          `${escapeHtml(p.code)}</b> ${escapeHtml(p.text)}</p>`,
      )
      .join("");
  return { plain, html };
}

const tidy = (s: string) => s.replace(/\s+/g, " ").trim();

/** The text as the page draws it: option C's capital, where the selection takes the first letter. */
function asDrawn(body: HTMLElement, text: string, fromStart: boolean): string {
  if (!fromStart || !body.classList.contains("bn-sentence-start")) return text;
  // ::first-letter takes the first letter OR digit; a digit draws no capital.
  return text.replace(/^([^\p{L}\p{N}]*)(\p{L})/u, (_, lead: string, c: string) =>
    lead + c.toLocaleUpperCase(body.lang || undefined),
  );
}

/** The part of `range` inside `node` (collapsed when they do not overlap). */
function clamp(range: Range, node: Node): Range {
  const cut = document.createRange();
  cut.selectNodeContents(node);
  if (range.compareBoundaryPoints(Range.START_TO_START, cut) > 0) {
    cut.setStart(range.startContainer, range.startOffset);
  }
  if (range.compareBoundaryPoints(Range.END_TO_END, cut) < 0) {
    cut.setEnd(range.endContainer, range.endOffset);
  }
  return cut;
}

/**
 * The paragraphs a selection covers, cut to the selected words. A paragraph
 * entered part-way takes the time of its first selected word, where words are
 * timed. Null when the selection touches no paragraph text.
 */
export function selectedParagraphs(range: Range, root: HTMLElement): CopiedParagraph[] | null {
  const out: CopiedParagraph[] = [];
  for (const body of root.querySelectorAll<HTMLElement>(".segment-body[data-position]")) {
    if (!range.intersectsNode(body)) continue;
    const cut = clamp(range, body);
    const text = tidy(cut.toString());
    if (!text) continue;
    const before = document.createRange();
    before.selectNodeContents(body);
    before.setEnd(cut.startContainer, cut.startOffset);
    const fromStart = tidy(before.toString()) === "";
    const row = body.closest<HTMLElement>(".transcript-segment");
    const word = fromStart
      ? null
      : // The first word the selection takes letters from: a drag that starts
        // in the gap after a word touches that word without taking any of it.
        Array.from(body.querySelectorAll<HTMLElement>(".transcript-word")).find(
          (w) => clamp(cut, w).toString().trim() !== "",
        );
    const seconds = Number(word?.dataset.start ?? row?.dataset.startSeconds ?? 0);
    out.push({
      seconds,
      code: row?.dataset.participant ?? "",
      text: asDrawn(body, text, fromStart),
    });
  }
  return out.length ? out : null;
}

/**
 * The page's copy handler. Several paragraphs: Markdown and rich text. One
 * paragraph: its selected words as plain text. Otherwise the browser's own copy.
 */
export function copyTranscriptSelection(e: ClipboardEvent | ReactClipboardEvent, root: HTMLElement): void {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
  const paras = selectedParagraphs(sel.getRangeAt(0), root);
  if (!paras || !e.clipboardData) return;
  e.preventDefault();
  if (paras.length === 1) {
    e.clipboardData.setData("text/plain", paras[0].text);
    return;
  }
  const { plain, html } = transcriptClipboard(paras);
  e.clipboardData.setData("text/plain", plain);
  e.clipboardData.setData("text/html", html);
}
