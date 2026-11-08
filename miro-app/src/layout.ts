// The board as Send to Miro lays it out — pure, so it is tested without Miro.
//
// A port of bristlenose/board_layout.py (`layout_board`, `_build_frame`, `quote_parts`,
// `set_tops`) and the sticky content of bristlenose/server/miro_export.py (`_sticky_content`,
// `fit_miro_sticky`). The in-Miro board must look like the REST one so a tester's feedback on
// either holds for both. tests/fixtures/miro-inboard-layout-v1.json is written by the Python side
// from the same columns as the board-file fixture, and layout.test.ts must arrive at it.
//
// Coordinates are top-left corners from the board's own top-left; draw.ts adds an origin and
// converts to the centres Miro wants.

import { type Board, safeClipUrl } from "../../figjam-plugin/src/board";
import { EAST_ASIAN_WIDE } from "./eastAsianWide";

// --- board_layout.py constants (board units) ---------------------------------
export const STICKY_W = 300.0;
export const RECT_ASPECT = 195.42857142857142 / 300;
export const SQUARE_ASPECT = 229.14572864321605 / 200;
const ASPECT: Record<Shape, number> = { rectangle: RECT_ASPECT, square: SQUARE_ASPECT };
const GAP_X = 36.0;
const GAP_Y = 24.0;
const FRAME_PAD = 28.0;
const FRAME_GAP = 72.0;
const MARGIN = 64.0;
const TITLE_Y = 46.0;
const FRAMES_Y = 120.0;
const TITLE_SIZE = 22;
const SIZE_K = 17.0;
const X_HEIGHT = 5.0;
const SET_STAGGER = X_HEIGHT;
const MIRO_PAPER = 0.825;
/** Miro refuses a sticky whose content, markup included, is longer than this. */
export const MIRO_STICKY_MAX = 6000;

export type Shape = "rectangle" | "square";

/** Miro's named sticky colours (Web SDK reference). A token outside them would make the SDK throw. */
export const MIRO_COLOURS: ReadonlySet<string> = new Set([
  "gray", "light_yellow", "yellow", "orange", "light_green", "green", "dark_green", "cyan",
  "light_pink", "pink", "violet", "red", "light_blue", "blue", "dark_blue", "black",
]);
const FALLBACK_COLOUR = "light_yellow";

export interface StickyPlan {
  kind: "header" | "quote";
  x: number;
  y: number;
  width: number;
  height: number;
  colour: string;
  content: string;
  /** The parts of one split quote share a set number; null for a quote on one sticky. */
  set: number | null;
  /** Which quote this sticky belongs to (0-based, board order); null for a header. */
  quote: number | null;
  /** The quote's last sticky: the one that completes it. */
  last: boolean;
}

export interface FramePlan {
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BoardPlan {
  shape: Shape;
  width: number;
  height: number;
  title: { content: string; x: number; y: number; width: number; fontSize: number };
  frames: FramePlan[];
  stickies: StickyPlan[];
  expectedQuotes: number;
  /** Clip links left out because they were not plain web addresses. */
  droppedLinks: number;
  /** Colour tokens Miro has no name for, drawn as light yellow instead. */
  unknownColours: number;
}

/** Python's html.escape(s, quote=True), character for character. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function isWide(cp: number): boolean {
  let lo = 0;
  let hi = EAST_ASIAN_WIDE.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const [a, b] = EAST_ASIAN_WIDE[mid];
    if (cp < a) hi = mid - 1;
    else if (cp > b) lo = mid + 1;
    else return true;
  }
  return false;
}

/** board_layout.text_width: a Latin letter is one, an East Asian wide or fullwidth character two.
 * Counted by code point, as Python counts, not by UTF-16 unit. */
export function textWidth(text: string): number {
  let n = 0;
  for (const ch of text) n += isWide(ch.codePointAt(0)!) ? 2 : 1;
  return n;
}

/** Python's len(): code points. */
function cpLength(s: string): number {
  let n = 0;
  for (const _ of s) n++;
  return n;
}

/** board_layout.fit_miro_sticky: escape(body) + rest, the body cut only if Miro would refuse it.
 * Escaping lengthens & and < up to five times, so the cut is searched for, not computed. */
export function fitMiroSticky(body: string, rest: string): string {
  const out = escapeHtml(body) + rest;
  if (cpLength(out) <= MIRO_STICKY_MAX) return out;
  const chars = Array.from(body);
  const cut = (n: number) => escapeHtml(chars.slice(0, n).join("").trimEnd() + "…") + rest;
  let lo = 0;
  let hi = chars.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (cpLength(cut(mid)) <= MIRO_STICKY_MAX) lo = mid;
    else hi = mid - 1;
  }
  return cut(lo);
}

function stickyWidth(chars: number, shape: Shape): number {
  return SIZE_K * Math.sqrt((Math.max(chars, 1) * RECT_ASPECT) / ASPECT[shape]);
}

interface Part {
  text: string;
  attributed: boolean;
  width: number;
  height: number;
}

function setOverlap(upper: Part): number {
  return upper.height * (1 - MIRO_PAPER) + X_HEIGHT;
}

function setTops(parts: Part[]): number[] {
  const tops: number[] = [];
  let y = 0.0;
  parts.forEach((part, k) => {
    tops.push(y);
    y += part.height - (k < parts.length - 1 ? setOverlap(part) : 0.0);
  });
  return tops;
}

function setExtent(parts: Part[]): [number, number] {
  const tops = setTops(parts);
  let w = 0.0;
  let h = 0.0;
  parts.forEach((p, k) => {
    w = Math.max(w, p.width + k * SET_STAGGER);
    h = Math.max(h, tops[k] + p.height);
  });
  return [w, h];
}

export function planBoard(board: Board): BoardPlan {
  const shape: Shape = board.stickyShape === "square" ? "square" : "rectangle";
  const aspect = ASPECT[shape];
  const headerH = STICKY_W * aspect;
  const stickies: StickyPlan[] = [];
  const frames: FramePlan[] = [];
  let droppedLinks = 0;
  let unknownColours = 0;
  let setId = 0;
  let quoteIndex = 0;

  const colourOf = (token: string): string => {
    if (MIRO_COLOURS.has(token)) return token;
    unknownColours++;
    return FALLBACK_COLOUR;
  };

  let x = MARGIN;
  for (const frame of board.frames) {
    const leftX = x;
    let cx = leftX + FRAME_PAD;
    let bottom = FRAMES_Y + FRAME_PAD + headerH;
    for (const col of frame.columns) {
      const sets = col.quotes.map((q) => {
        const parts: Part[] = q.parts.map((text, k) => {
          const last = k === q.parts.length - 1;
          const w = stickyWidth(textWidth(text) + (last ? textWidth(q.attribution) : 0), shape);
          return { text, attributed: last, width: w, height: w * aspect };
        });
        return { q, parts };
      });
      const colW = Math.max(STICKY_W, ...sets.map(({ parts }) => setExtent(parts)[0]));
      // miro_export._sticky_content splits the header's text at its first newline.
      const [label, ...rest] = `${col.label}\n${col.count}`.split("\n");
      stickies.push({
        kind: "header",
        x: cx,
        y: FRAMES_Y + FRAME_PAD,
        width: STICKY_W,
        height: headerH,
        colour: colourOf(col.colour),
        content: `<strong>${escapeHtml(label)}</strong>${rest.length ? `<br>${escapeHtml(rest[0])}` : ""}`,
        set: null,
        quote: null,
        last: false,
      });
      let sy = FRAMES_Y + FRAME_PAD + headerH + GAP_Y;
      for (const { q, parts } of sets) {
        let set: number | null = null;
        if (parts.length > 1) set = ++setId;
        const url = safeClipUrl(q.clipUrl);
        if (q.clipUrl && !url) droppedLinks++;
        const colour = colourOf(q.colour);
        const tops = setTops(parts);
        parts.forEach((part, k) => {
          let content: string;
          if (!part.attributed) {
            content = fitMiroSticky(part.text, "");
          } else {
            let line = escapeHtml(q.attribution);
            // The file's clip label already carries the ▶ (board_manifest: "▶ {clip}").
            if (url) line += ` · <a href="${escapeHtml(url.href)}">${escapeHtml(board.clipLabel)}</a>`;
            content = fitMiroSticky(part.text, `<br><i>${line}</i>`);
          }
          stickies.push({
            kind: "quote",
            x: cx + k * SET_STAGGER,
            y: sy + tops[k],
            width: part.width,
            height: part.height,
            colour,
            content,
            set,
            quote: quoteIndex,
            last: part.attributed,
          });
        });
        quoteIndex++;
        sy += setExtent(parts)[1] + GAP_Y;
      }
      bottom = Math.max(bottom, sy - GAP_Y);
      cx += colW + GAP_X;
    }
    const frameW = (frame.columns.length ? cx - GAP_X : cx) - leftX + FRAME_PAD;
    frames.push({ title: frame.title, x: leftX, y: FRAMES_Y, width: frameW, height: bottom - FRAMES_Y + FRAME_PAD });
    x = leftX + frameW + FRAME_GAP;
  }

  const right = frames.length ? Math.max(...frames.map((f) => f.x + f.width)) : MARGIN;
  const bottomAll = frames.length ? Math.max(...frames.map((f) => f.y + f.height)) : FRAMES_Y;
  return {
    shape,
    width: right + MARGIN,
    height: bottomAll + MARGIN,
    // As miro_export._push sends it: the text's left + 300 is its centre, 600 wide.
    title: { content: escapeHtml(board.title), x: MARGIN + 300, y: TITLE_Y, width: 600, fontSize: TITLE_SIZE },
    frames,
    stickies,
    expectedQuotes: board.totalQuotes,
    droppedLinks,
    unknownColours,
  };
}
