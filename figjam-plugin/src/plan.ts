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

export interface ColumnPlan {
  header: StickyPlan;
  quotes: StickyPlan[];
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
      const quotes = col.quotes.map((q): StickyPlan => {
        const url = safeClipUrl(q.clipUrl);
        if (q.clipUrl && !url) droppedLinks++;
        let line = q.attribution;
        if (url) line += ` · ${board.clipLabel}`;
        const characters = `${q.text}\n${line}`;
        const lineStart = q.text.length + 1;
        const plan: StickyPlan = {
          characters,
          fill: board.palette[q.colour],
          italic: [lineStart, characters.length],
          small: [lineStart, characters.length],
        };
        if (url) {
          hosts.add(url.host);
          plan.link = { range: [characters.length - board.clipLabel.length, characters.length], url: url.href };
        }
        return plan;
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
