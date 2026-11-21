/**
 * The quote card's editing surface, drawn and read back by hand.
 *
 * In edit and trim modes the card draws the quote as the SAME blocks it shows
 * at rest, so nothing moves when you click in (21 Nov 2026; before, the
 * paragraphs folded into one run and the card jumped). React draws the rest
 * state; this module draws the two edit states into one host element that
 * React leaves empty, because a contenteditable that React re-renders under the
 * browser's own edits loses them.
 *
 * The model is always words + break positions (a break falls after word i),
 * the same word split as breakIntoBlocks and useCropEdit (`split(/\s+/)`), so
 * a break is whitespace and never changes a word. Every structural key
 * (a new paragraph, a join) reads the host back into the model, changes the
 * model, and draws it again: the browser never has to merge or split our
 * elements itself. Spec: docs/design-quote-editing.md §"Paragraphs".
 */

import { breakIntoBlocks } from "./breakParagraphs";

export interface EditModel {
  words: string[];
  /** Ascending. A break after word i: blocks are [0..b0], [b0+1..b1], ... */
  breaks: number[];
  cropStart: number;
  cropEnd: number;
}

/** The automatic breaks for `text`, as word positions. */
export function autoBreaks(text: string): number[] {
  const blocks = breakIntoBlocks(text);
  if (blocks.length < 2) return [];
  const out: number[] = [];
  let n = 0;
  for (let i = 0; i < blocks.length - 1; i++) {
    n += blocks[i].split(/\s+/).filter(Boolean).length;
    out.push(n - 1);
  }
  return out;
}

/** Word ranges [start, end) of each block. */
export function blockRanges(nWords: number, breaks: number[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  let from = 0;
  for (const b of breaks) {
    if (b < from || b >= nWords - 1) continue;
    out.push([from, b + 1]);
    from = b + 1;
  }
  out.push([from, nWords]);
  return out;
}

export function sameBreaks(a: number[] | null, b: number[] | null): boolean {
  if (a === null || b === null) return a === b;
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

// ── Drawing ─────────────────────────────────────────────────────────────

interface DrawOptions {
  mode: "hybrid" | "crop";
  leftEllipsis: boolean;
  rightEllipsis: boolean;
  bracketsVisible: boolean;
}

function el(tag: string, cls: string, text?: string): HTMLElement {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function island(cls: string, text?: string): HTMLElement {
  const e = el("span", cls, text);
  e.setAttribute("contenteditable", "false");
  return e;
}

function handle(side: "start" | "end", visible: boolean): HTMLElement {
  const h = el("span", `crop-handle ${visible ? "bracket-visible" : "bracket-delayed"}`, side === "start" ? "[" : "]");
  h.dataset.handle = side;
  return h;
}

/** A quote mark that keeps its place; the bracket, when it sits there, is laid over it. */
function mark(glyph: string, h: HTMLElement | null): HTMLElement {
  const m = island("bn-mark");
  m.append(el("span", "smart-quote", glyph));
  if (h) m.append(h);
  return m;
}

/** A bracket that takes no room in the line: it sits in the gap before or after a word. */
function anchor(h: HTMLElement, side: "start" | "end"): HTMLElement {
  const a = island(`bn-anchor bn-anchor-${side}`);
  a.append(h);
  return a;
}

export function draw(host: HTMLElement, m: EditModel, o: DrawOptions): void {
  host.replaceChildren();
  const { words, cropStart, cropEnd } = m;
  const ranges = blockRanges(words.length, m.breaks);
  const last = ranges.length - 1;
  ranges.forEach(([s, e], bi) => {
    const block = el("span", "bn-block");
    if (bi === 0) {
      block.append(mark("“", cropStart === 0 ? handle("start", o.bracketsVisible) : null));
      if (o.leftEllipsis) block.append(island("crop-ellipsis", "…"));
    }
    // Leading excluded words (trim), each carrying its own space after.
    for (let i = s; i < Math.min(e, cropStart); i++) {
      const w = island("crop-word excluded", `${words[i]} `);
      w.dataset.i = String(i);
      block.append(w);
    }
    if (cropStart > 0 && cropStart >= s && cropStart < e) block.append(anchor(handle("start", o.bracketsVisible), "start"));
    const inFrom = Math.max(s, cropStart);
    const inTo = Math.min(e, cropEnd);
    if (inTo > inFrom) {
      if (o.mode === "hybrid") {
        block.append(el("span", "crop-editable", words.slice(inFrom, inTo).join(" ")));
      } else {
        const region = el("span", "crop-included-region");
        for (let i = inFrom; i < inTo; i++) {
          const w = el("span", "crop-word included", words[i]);
          w.dataset.i = String(i);
          region.append(w);
          if (i < inTo - 1) region.append(document.createTextNode(" "));
        }
        block.append(region);
      }
    }
    if (cropEnd < words.length && cropEnd - 1 >= s && cropEnd - 1 < e) block.append(anchor(handle("end", o.bracketsVisible), "end"));
    // Trailing excluded words, each carrying its own space before.
    for (let i = Math.max(s, cropEnd); i < e; i++) {
      const w = island("crop-word excluded", ` ${words[i]}`);
      w.dataset.i = String(i);
      block.append(w);
    }
    if (bi === last) {
      if (o.rightEllipsis) block.append(island("crop-ellipsis", "…"));
      block.append(mark("”", cropEnd === words.length ? handle("end", o.bracketsVisible) : null));
    }
    host.append(block);
  });
}

export function setBracketsVisible(host: HTMLElement, visible: boolean): void {
  host.querySelectorAll(".crop-handle").forEach((h) => {
    h.classList.toggle("bracket-visible", visible);
    h.classList.toggle("bracket-delayed", !visible);
  });
}

// ── Reading back ────────────────────────────────────────────────────────

const isIsland = (n: Node): n is HTMLElement =>
  n instanceof HTMLElement && n.getAttribute("contenteditable") === "false";

/** The words of one block, the typed ones and the excluded ones, in order. */
function blockTokens(block: Node): Array<{ word: string; excluded: boolean }> {
  const out: Array<{ word: string; excluded: boolean }> = [];
  let buf = "";
  const flush = () => {
    for (const w of buf.split(/\s+/).filter(Boolean)) out.push({ word: w, excluded: false });
    buf = "";
  };
  const walk = (n: Node) => {
    if (isIsland(n)) {
      if (n.classList.contains("excluded")) {
        flush();
        out.push({ word: (n.textContent ?? "").trim(), excluded: true });
      }
      return; // a quote mark, bracket or ellipsis is not words
    }
    if (n.nodeType === Node.TEXT_NODE) {
      buf += n.textContent ?? "";
      return;
    }
    // A <br> or a block the browser made counts as a space between words.
    if (n instanceof HTMLElement && (n.tagName === "BR" || n.tagName === "DIV")) buf += " ";
    n.childNodes.forEach(walk);
    if (n instanceof HTMLElement && n.tagName === "DIV") buf += " ";
  };
  block.childNodes.forEach(walk);
  flush();
  return out;
}

/** The host back into the model. A block left with no words takes its break with it. */
export function read(host: HTMLElement): EditModel {
  // Anything the browser put directly in the host belongs to the block before it.
  const groups: Node[][] = [];
  host.childNodes.forEach((n) => {
    if (n instanceof HTMLElement && n.classList.contains("bn-block")) groups.push([n]);
    else if (groups.length) groups[groups.length - 1].push(n);
    else groups.push([n]);
  });
  const words: string[] = [];
  const breaks: number[] = [];
  let cropStart = 0;
  let included = 0;
  for (const g of groups) {
    const holder = document.createElement("span");
    g.forEach((n) => holder.append(n.cloneNode(true)));
    const toks = blockTokens(holder);
    if (toks.length === 0) continue;
    for (const t of toks) {
      if (t.excluded && included === 0) cropStart += 1;
      else if (!t.excluded) included += 1;
      words.push(t.word);
    }
    breaks.push(words.length - 1);
  }
  breaks.pop();
  return { words, breaks, cropStart, cropEnd: cropStart + included };
}

// ── The caret ───────────────────────────────────────────────────────────

/** Text of the range with the islands taken out. */
function plainText(r: Range): string {
  const holder = document.createElement("span");
  holder.append(r.cloneContents());
  holder.querySelectorAll('[contenteditable="false"]').forEach((n) => n.remove());
  return holder.textContent ?? "";
}

export interface CaretPlace {
  block: number;
  /** Words of this block's typed text before the caret, by the transcript's rule. */
  word: number;
  atStart: boolean;
  atEnd: boolean;
  /** An excluded word sits between the caret and the block's edge. */
  excludedBefore: boolean;
  excludedAfter: boolean;
}

export function caretPlace(host: HTMLElement): CaretPlace | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return null;
  const caret = sel.getRangeAt(0);
  if (!host.contains(caret.startContainer)) return null;
  const startEl = caret.startContainer instanceof Element ? caret.startContainer : caret.startContainer.parentElement;
  const block = startEl?.closest(".bn-block");
  if (!block || !host.contains(block)) return null;
  const blocks = Array.from(host.querySelectorAll(":scope > .bn-block"));
  const before = document.createRange();
  before.selectNodeContents(block);
  before.setEnd(caret.startContainer, caret.startOffset);
  const after = document.createRange();
  after.selectNodeContents(block);
  after.setStart(caret.startContainer, caret.startOffset);
  const textBefore = plainText(before);
  const textAfter = plainText(after);
  const whole = textBefore.split(/\s+/).filter(Boolean).length;
  // Touching a word: at its end it counts; inside it, the cut goes before it
  // (utils/paragraphEdits.ts caretWords, the transcript's Return).
  const word =
    textBefore.length === 0 || /\s$/.test(textBefore) || textAfter.length === 0 || /^\s/.test(textAfter)
      ? whole
      : whole - 1;
  const hasExcluded = (r: Range) => {
    const h = document.createElement("span");
    h.append(r.cloneContents());
    return h.querySelector(".excluded") !== null;
  };
  return {
    block: blocks.indexOf(block),
    word,
    atStart: textBefore.trim().length === 0,
    atEnd: textAfter.trim().length === 0,
    excludedBefore: hasExcluded(before),
    excludedAfter: hasExcluded(after),
  };
}

/** Put the caret before word `index` (or after the last word of its block with `atEnd`). */
export function placeCaret(host: HTMLElement, m: EditModel, index: number, atEnd = false): void {
  const ranges = blockRanges(m.words.length, m.breaks);
  const bi = ranges.findIndex(([s, e]) => index >= s && index < e);
  if (bi < 0) return;
  const run = host.querySelectorAll(":scope > .bn-block")[bi]?.querySelector(".crop-editable");
  const text = run?.firstChild;
  if (!run || !text) return;
  const [s] = ranges[bi];
  const from = Math.max(s, m.cropStart);
  let offset = 0;
  for (let i = from; i < index; i++) offset += m.words[i].length + 1;
  if (atEnd) offset += m.words[index].length;
  const r = document.createRange();
  r.setStart(text, Math.min(offset, text.textContent?.length ?? 0));
  r.collapse(true);
  const sel = window.getSelection();
  sel?.removeAllRanges();
  sel?.addRange(r);
}

/** Put the caret where a point is, if the point falls on the typed text. */
export function caretAtPoint(host: HTMLElement, x: number, y: number): boolean {
  type CaretDoc = Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
  };
  const d = document as CaretDoc;
  let node: Node | null = null;
  let offset = 0;
  if (d.caretPositionFromPoint) {
    const p = d.caretPositionFromPoint(x, y);
    if (p) ({ offsetNode: node, offset } = p);
  } else if (d.caretRangeFromPoint) {
    const r = d.caretRangeFromPoint(x, y);
    if (r) {
      node = r.startContainer;
      offset = r.startOffset;
    }
  }
  if (!node || !host.contains(node)) return false;
  const inRun = (node instanceof Element ? node : node.parentElement)?.closest(".crop-editable");
  if (!inRun) return false;
  const r = document.createRange();
  r.setStart(node, offset);
  r.collapse(true);
  const sel = window.getSelection();
  sel?.removeAllRanges();
  sel?.addRange(r);
  return true;
}

/** Index of the first typed word of block `bi`. */
export function firstTyped(m: EditModel, bi: number): number {
  const [s] = blockRanges(m.words.length, m.breaks)[bi];
  return Math.max(s, m.cropStart);
}
