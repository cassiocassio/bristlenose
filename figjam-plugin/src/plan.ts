// The board as a list of stickies to draw — pure, so it is tested without Figma.
//
// Every character offset is computed here, on the exact string the sticky will
// hold. Figma's setRange* calls count JavaScript string positions (UTF-16 code
// units), which is why composition happens in the plugin and not in Python,
// whose len() counts code points and would drift after any emoji.

import { type Board, safeClipUrl } from "./board";

export type Range = [start: number, end: number];

export interface StickyPlan {
  characters: string;
  fill: string; // #RRGGBB
  bold?: Range;
  italic?: Range;
  small?: Range;
  link?: { range: Range; url: string };
}

/** One quote: one sticky, or a set of two or three read as one. */
export interface QuoteSet {
  name: string; // the attribution, so a set is findable in the layers list
  parts: StickyPlan[];
}

export interface ColumnPlan {
  header: StickyPlan;
  quotes: QuoteSet[];
}

export interface FramePlan {
  title: string;
  columns: ColumnPlan[];
}

export interface BoardPlan {
  title: string;
  wide: boolean;
  frames: FramePlan[];
  /** Quote stickies the board should end up with. */
  expectedQuotes: number;
  /** Clip links left out because they were not plain web addresses. */
  droppedLinks: number;
  /** The sites clip links point at, shown before anything is drawn. */
  clipHosts: string[];
}

export function planBoard(board: Board): BoardPlan {
  let droppedLinks = 0;
  const hosts = new Set<string>();

  const frames = board.frames.map((frame) => ({
    title: frame.title,
    columns: frame.columns.map((col) => {
      const head = `${col.label}\n${col.count}`;
      const header: StickyPlan = {
        characters: head,
        fill: board.palette[col.colour],
        bold: [0, col.label.length],
      };
      const quotes = col.quotes.map((q): QuoteSet => {
        const url = safeClipUrl(q.clipUrl);
        if (q.clipUrl && !url) droppedLinks++;
        const fill = board.palette[q.colour];
        // Every part but the last is just its words; the last carries the
        // attribution (and clip link), as on the Miro board.
        const parts = q.parts.slice(0, -1).map((text): StickyPlan => ({ characters: text, fill }));
        const lastText = q.parts[q.parts.length - 1];
        let line = q.attribution;
        if (url) line += ` · ${board.clipLabel}`;
        const characters = `${lastText}\n${line}`;
        const lineStart = lastText.length + 1;
        const last: StickyPlan = {
          characters,
          fill,
          italic: [lineStart, characters.length],
          small: [lineStart, characters.length],
        };
        if (url) {
          hosts.add(url.host);
          last.link = { range: [characters.length - board.clipLabel.length, characters.length], url: url.href };
        }
        return { name: q.attribution, parts: [...parts, last] };
      });
      return { header, quotes };
    }),
  }));

  return {
    title: board.title,
    wide: board.stickyShape === "rectangle",
    frames,
    expectedQuotes: board.totalQuotes,
    droppedLinks,
    clipHosts: [...hosts].sort(),
  };
}

/** #RRGGBB to Figma's 0–1 channels, exact so FigJam reads it as a palette colour. */
export function rgb(hex: string): { r: number; g: number; b: number } {
  const n = (i: number) => parseInt(hex.slice(i, i + 2), 16) / 255;
  return { r: n(1), g: n(3), b: n(5) };
}
