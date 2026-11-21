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
  // In text editing the field's value is the words being kept: the quote
  // marks, brackets, ellipses and trimmed words are kept out of what a screen
  // reader reads as the quote (review 21 Nov, finding 12).
  if (o.mode === "hybrid") {
    host.querySelectorAll('[contenteditable="false"]').forEach((n) => n.setAttribute("aria-hidden", "true"));
  }
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

const BLOCK_TAGS = new Set([
  "BR", "DIV", "P", "LI", "UL", "OL", "BLOCKQUOTE", "PRE", "TABLE", "TR", "TD", "TH",
  "H1", "H2", "H3", "H4", "H5", "H6",
]);

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
    // A <br> or a block element the browser made (or a drop brought) is a
    // space between words, never a joint: "end of</p><p>next" is two words.
    const isBlock = n instanceof HTMLElement && BLOCK_TAGS.has(n.tagName);
    if (isBlock) buf += " ";
    n.childNodes.forEach(walk);
    if (isBlock) buf += " ";
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
  /**
   * The paragraph, numbered as `read()` numbers them: only blocks that hold
   * words count, so a paragraph the researcher emptied does not shift the
   * ones after it (review 21 Nov, finding 5). In an emptied block it is the
   * index of the paragraph that follows.
   */
  block: number;
  /** The caret is in a block with no words left in it. */
  empty: boolean;
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
  const holdsWords = (b: Element) => blockTokens(b).length > 0;
  let index = 0;
  for (const b of Array.from(host.querySelectorAll(":scope > .bn-block"))) {
    if (b === block) break;
    if (holdsWords(b)) index += 1;
  }
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
    block: index,
    empty: !holdsWords(block),
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

// ── Keeping the surface whole ───────────────────────────────────────────

/** The caret's run, or null when it sits outside the typed text. */
function runAt(node: Node): Element | null {
  return (node instanceof Element ? node : node.parentElement)?.closest(".crop-editable") ?? null;
}

/**
 * Keep a collapsed caret inside the typed text. Home, ⌘← or an arrow can put
 * it before a quote mark or between two trimmed words, and text typed there
 * lands outside the words being kept: `read()` then counts it among the
 * trimmed ones and saves words the researcher never wrote (review 21 Nov,
 * findings 1 and 19). It goes to the nearer end of its own paragraph's run,
 * or to the nearest run when its paragraph has none.
 */
export function clampCaret(host: HTMLElement): void {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return;
  const caret = sel.getRangeAt(0);
  if (!host.contains(caret.startContainer) || runAt(caret.startContainer)) return;
  const runs = Array.from(host.querySelectorAll(".crop-editable"));
  if (runs.length === 0) return;
  const startEl = caret.startContainer instanceof Element ? caret.startContainer : caret.startContainer.parentElement;
  const block = startEl?.closest(".bn-block");
  const own = block?.querySelector(".crop-editable") ?? null;
  const edge = (run: Element, atEnd: boolean) => {
    const r = document.createRange();
    r.selectNodeContents(run);
    r.collapse(!atEnd);
    return r;
  };
  let target: Range;
  if (own) {
    const start = edge(own, false);
    target = caret.compareBoundaryPoints(Range.START_TO_START, start) <= 0 ? start : edge(own, true);
  } else {
    const after = runs.find((r) => {
      const at = edge(r, false);
      return caret.compareBoundaryPoints(Range.START_TO_START, at) <= 0;
    });
    target = after ? edge(after, false) : edge(runs[runs.length - 1], true);
  }
  sel.removeAllRanges();
  sel.addRange(target);
}

/** An input the browser would make outside the model: refuse it. */
export type InputVerdict = "allow" | "refuse" | "retype";

/**
 * Judge an input before the browser makes it (a native `beforeinput`; React's
 * onBeforeInput misses deletes and line breaks, as TranscriptPage found).
 * Return, Shift-Return and the paragraph-edge Backspace and Delete are handled
 * on keydown and never reach here. Everything else that would delete a quote
 * mark or a trimmed word, run two paragraphs together, add a line break the
 * read-back would turn into a space, bring in dropped markup or format the
 * text is refused (review 21 Nov, finding 3): Option-/⌘-Backspace, Ctrl-H,
 * Ctrl-K, Ctrl-O, Edit ▸ Delete, a drop, ⌘B. Text typed where the caret sits
 * outside the typed run is moved into it ("retype"). An input method's
 * composition always goes through: refusing it loses the conversion.
 */
export function judgeInput(host: HTMLElement, e: InputEvent): InputVerdict {
  const t = e.inputType;
  if (e.isComposing || t.includes("Composition")) return "allow";
  if (t === "insertParagraph" || t === "insertLineBreak") return "refuse";
  if (t.startsWith("insertFrom") && t !== "insertFromPaste") return "refuse"; // drop, yank, quotation
  if (t.startsWith("format")) return "refuse";
  if (t.startsWith("history")) return "allow";
  const ranges: AbstractRange[] = e.getTargetRanges?.() ?? [];
  const sel = window.getSelection();
  if (ranges.length === 0 && sel && sel.rangeCount > 0) ranges.push(sel.getRangeAt(0));
  for (const sr of ranges) {
    const r = document.createRange();
    r.setStart(sr.startContainer, sr.startOffset);
    r.setEnd(sr.endContainer, sr.endOffset);
    const blockOf = (n: Node) => (n instanceof Element ? n : n.parentElement)?.closest(".bn-block") ?? null;
    if (blockOf(r.startContainer) !== blockOf(r.endContainer)) return "refuse";
    if (!r.collapsed) {
      for (const island of Array.from(host.querySelectorAll('[contenteditable="false"]'))) {
        if (r.intersectsNode(island)) return "refuse";
      }
    } else if (t.startsWith("insert") && !runAt(r.startContainer)) {
      return "retype";
    }
  }
  return "allow";
}
