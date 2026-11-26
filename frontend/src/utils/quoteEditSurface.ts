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

export interface DrawOptions {
  mode: "hybrid" | "crop";
  leftEllipsis: boolean;
  rightEllipsis: boolean;
  bracketsVisible: boolean;
  /** Draw an empty paragraph before this one (at the end when past the last): a selection deleted it all. */
  emptyAt?: number;
  /** This paragraph, if it has no typed words, gets an empty run to hold the caret. */
  holdCaret?: number;
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
  // An emptied paragraph is no range of words: it is drawn from [-1, -1].
  if (o.emptyAt !== undefined) ranges.splice(Math.min(o.emptyAt, ranges.length), 0, [-1, -1]);
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
    } else if (o.mode === "hybrid" && bi === o.holdCaret) {
      // No typed words left: an empty run holds the caret, with the <br> the
      // engines put in an emptied line, so what is typed reads back as typed.
      const run = el("span", "crop-editable");
      run.append(document.createElement("br"));
      block.append(run);
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

/**
 * Whether text typed at this node is read back as the words being kept: inside
 * the typed run, or in a paragraph the researcher has emptied. The engines
 * remove a run once all its text is deleted, and moving the caret out of that
 * paragraph would type into the next one (review 25 Nov, finding 28). Text in
 * a paragraph with no run and no trimmed words reads back as typed.
 */
export function typedPlace(node: Node): boolean {
  const el = node instanceof Element ? node : node.parentElement;
  if (el?.closest(".crop-editable")) return true;
  const block = el?.closest(".bn-block");
  return !!block && !block.querySelector(".crop-editable, .excluded");
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
  if (!host.contains(caret.startContainer) || typedPlace(caret.startContainer)) return;
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

/**
 * An input the browser would make outside the model: refuse it. A selection
 * that reaches past one paragraph's words is typed over or deleted by the
 * card instead ("replace", `replaceRange`).
 */
export type InputVerdict = "allow" | "refuse" | "retype" | "replace";

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
  // A drag that moves words is a delete here and a drop there; the drop is
  // refused, so the delete must be too, or the words vanish (finding 34).
  if (t === "deleteByDrag") return "refuse";
  if (t.startsWith("format")) return "refuse";
  if (t.startsWith("history")) return "allow";
  const sel = window.getSelection();
  // Something selected across a paragraph break, a quote mark or a trimmed
  // word: typing replaces it and a delete deletes it, as anywhere else; the
  // card does it on the words alone. A word or line delete from a caret
  // that would cross one is still refused.
  if (sel && sel.rangeCount > 0 && !sel.isCollapsed && (t === "insertText" || t.startsWith("delete"))) {
    const r = sel.getRangeAt(0);
    if (host.contains(r.commonAncestorContainer) && !rangeKeepsSurface(host, r)) return "replace";
  }
  const ranges: AbstractRange[] = e.getTargetRanges?.() ?? [];
  if (ranges.length === 0 && sel && sel.rangeCount > 0) ranges.push(sel.getRangeAt(0));
  for (const sr of ranges) {
    const r = document.createRange();
    r.setStart(sr.startContainer, sr.startOffset);
    r.setEnd(sr.endContainer, sr.endOffset);
    if (!rangeKeepsSurface(host, r)) return "refuse";
    if (r.collapsed && t.startsWith("insert") && !typedPlace(r.startContainer)) return "retype";
  }
  return "allow";
}

/**
 * Whether replacing this range keeps the surface whole: it stays in one
 * paragraph and takes no quote mark, bracket or trimmed word with it. The
 * paste handler asks too, because a paste inserts by `execCommand`, which
 * Chromium sends through no `beforeinput` (finding 33).
 */
export function rangeKeepsSurface(host: HTMLElement, r: Range): boolean {
  const blockOf = (n: Node) => (n instanceof Element ? n : n.parentElement)?.closest(".bn-block") ?? null;
  if (blockOf(r.startContainer) !== blockOf(r.endContainer)) return false;
  if (r.collapsed) return true;
  return !Array.from(host.querySelectorAll('[contenteditable="false"]')).some((n) => r.intersectsNode(n));
}

// ── Replacing a selection ───────────────────────────────────────────────

/** The typed text under `n`: the islands left out, a line break or block a space (as `blockTokens`). */
function typedOf(n: Node): string {
  let s = "";
  const walk = (x: Node) => {
    if (isIsland(x)) return;
    if (x.nodeType === Node.TEXT_NODE) {
      s += x.textContent ?? "";
      return;
    }
    const isBlock = x instanceof HTMLElement && BLOCK_TAGS.has(x.tagName);
    if (isBlock) s += " ";
    x.childNodes.forEach(walk);
    if (isBlock) s += " ";
  };
  n.childNodes.forEach(walk);
  return s;
}

type Point = [Node, number];

/** The typed text of `block` between two points (its own start and end when left out). */
function typedBetween(block: Element, from?: Point, to?: Point): string {
  const r = document.createRange();
  r.selectNodeContents(block);
  if (from) r.setStart(from[0], from[1]);
  if (to) r.setEnd(to[0], to[1]);
  const holder = document.createElement("span");
  holder.append(r.cloneContents());
  return typedOf(holder);
}

const wordsOf = (s: string) => s.split(/\s+/).filter(Boolean);

export interface Replaced {
  model: EditModel;
  /** The typed words the range held, a paragraph a line: what a cut puts on the clipboard. */
  removed: string;
  /** The range crossed a paragraph break, so paragraphs were joined. */
  joined: boolean;
}

/**
 * Replace what a range selects with `text` (empty for a delete), on the typed
 * words only: the quote marks, brackets and trimmed words in it stay, and the
 * paragraphs it spans become one. A range that ends at the very start of a
 * paragraph, as a triple-click's does, takes none of that paragraph and leaves
 * its break. Redraws the surface and puts the caret after the inserted text.
 * Native undo does not reach across the redraw, as for Shift-Return.
 */
export function replaceRange(host: HTMLElement, r: Range, text: string, o: DrawOptions): Replaced | null {
  const blocks = Array.from(host.querySelectorAll(":scope > .bn-block"));
  if (blocks.length === 0) return null;
  const blockAt = ([node, offset]: Point) => {
    const i = blocks.findIndex((b) => {
      const all = document.createRange();
      all.selectNodeContents(b);
      return all.comparePoint(node, offset) <= 0;
    });
    return i < 0 ? blocks.length - 1 : i;
  };
  const from: Point = [r.startContainer, r.startOffset];
  let to: Point = [r.endContainer, r.endOffset];
  const a = blockAt(from);
  let b = blockAt(to);
  if (b > a && typedBetween(blocks[b], undefined, to).trim() === "") {
    b -= 1;
    to = [blocks[b], blocks[b].childNodes.length];
  }
  const pre = typedBetween(blocks[a], undefined, from);
  const post = typedBetween(blocks[b], to, undefined);
  const removed = blocks
    .slice(a, b + 1)
    .map((blk, k) => wordsOf(typedBetween(blk, k === 0 ? from : undefined, a + k === b ? to : undefined)).join(" "))
    .filter(Boolean)
    .join("\n");

  // Each paragraph as trimmed words before, typed words, trimmed words after.
  let seenTyped = false;
  const parts = blocks.map((blk) => {
    const p = { lead: [] as string[], words: [] as string[], trail: [] as string[] };
    for (const t of blockTokens(blk)) {
      if (!t.excluded) {
        seenTyped = true;
        p.words.push(t.word);
      } else (seenTyped ? p.trail : p.lead).push(t.word);
    }
    return p;
  });
  const span = parts.slice(a, b + 1);
  const merged = {
    lead: span.flatMap((p) => p.lead),
    words: wordsOf(pre + text + post),
    trail: span.flatMap((p) => p.trail),
  };
  const out = [...parts.slice(0, a), merged, ...parts.slice(b + 1)];

  const words: string[] = [];
  const breaks: number[] = [];
  let cropStart = 0;
  let included = 0;
  let mergedAt = 0;
  out.forEach((p, i) => {
    const toks = [...p.lead, ...p.words, ...p.trail];
    if (i === a) mergedAt = breaks.length + (words.length > 0 ? 1 : 0);
    if (toks.length === 0) return;
    if (words.length > 0) breaks.push(words.length - 1);
    cropStart += p.lead.length;
    included += p.words.length;
    words.push(...toks);
  });
  const model: EditModel = { words, breaks, cropStart, cropEnd: cropStart + included };

  const mergedDrawn = merged.lead.length + merged.words.length + merged.trail.length > 0;
  const emptyAt = mergedDrawn || words.length === 0 ? undefined : mergedAt;
  const at = words.length === 0 ? 0 : mergedAt;
  draw(host, model, { ...o, emptyAt, holdCaret: at });

  const run = host.querySelectorAll(":scope > .bn-block")[at]?.querySelector(".crop-editable");
  if (run) {
    const head = wordsOf(pre + text);
    let offset = head.join(" ").length + (head.length > 0 && /\s$/.test(pre + text) ? 1 : 0);
    const node = run.firstChild;
    const c = document.createRange();
    if (node?.nodeType === Node.TEXT_NODE) {
      offset = Math.min(offset, node.textContent?.length ?? 0);
      c.setStart(node, offset);
    } else c.setStart(run, 0);
    c.collapse(true);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(c);
  }
  return { model, removed, joined: b > a };
}
