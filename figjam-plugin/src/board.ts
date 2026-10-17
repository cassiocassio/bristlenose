// Reading a Bristlenose board file — and refusing one we would draw wrong.
//
// The file is untrusted: anyone can write one and a colleague can send one.
// So every field is checked for type before it is used, sizes are capped, and
// anything wrong ends in one plain sentence, never a stack trace. The shape is
// written by bristlenose/board_manifest.py; tests/fixtures/figjam-board-v1.json
// is the contract both sides test against.

/** The newest `min_reader_version` this plugin can draw. */
export const READER_VERSION = 1;
export const FORMAT = "bristlenose-board";

export const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_QUOTES = 5000;
const MAX_PARTS = 5; // Bristlenose writes at most 3; a little room before refusing
const MAX_TEXT = 20000;

export interface Quote {
  /** One to three stickies' worth, split by Bristlenose where a researcher would split it. */
  parts: string[];
  attribution: string;
  colour: string;
  clipUrl: string | null;
}

export interface Column {
  label: string;
  count: string;
  quoteCount: number;
  colour: string;
  quotes: Quote[];
}

export interface Frame {
  title: string;
  columns: Column[];
}

export interface Board {
  title: string;
  stickyShape: string;
  clipLabel: string;
  palette: Record<string, string>;
  totalQuotes: number;
  frames: Frame[];
}

export type RefusalKind = "not_json" | "not_a_board" | "too_new" | "malformed" | "too_large";

export class Refusal extends Error {
  constructor(public kind: RefusalKind, detail: string) {
    super(detail);
  }
}

/** What the researcher reads when a file is refused. One sentence each. */
export const REFUSAL_TEXT: Record<RefusalKind, string> = {
  not_json: "That file isn't a Bristlenose board file. Choose the .json file Bristlenose downloaded.",
  not_a_board: "That file isn't a Bristlenose board file. Choose the .json file Bristlenose downloaded.",
  too_new: "This board was made by a newer Bristlenose. Update the Bristlenose board plugin, then try again.",
  malformed: "This board file is damaged or was edited by hand, so it can't be drawn. Download it again from Bristlenose.",
  too_large: "This board file is too large to draw in one go. Export a smaller selection from Bristlenose.",
};

type Json = unknown;

function isObject(v: Json): v is Record<string, Json> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function str(o: Record<string, Json>, key: string, max = MAX_TEXT): string {
  const v = o[key];
  if (typeof v !== "string") throw new Refusal("malformed", `${key} is not text`);
  if (v.length > max) throw new Refusal("too_large", `${key} is too long`);
  return v;
}

function int(o: Record<string, Json>, key: string): number {
  const v = o[key];
  if (typeof v !== "number" || !Number.isInteger(v) || v < 0) {
    throw new Refusal("malformed", `${key} is not a count`);
  }
  return v;
}

function arr(o: Record<string, Json>, key: string): Json[] {
  const v = o[key];
  if (!Array.isArray(v)) throw new Refusal("malformed", `${key} is not a list`);
  return v;
}

const HEX = /^#[0-9A-Fa-f]{6}$/;

export function parseBoard(text: string): Board {
  let doc: Json;
  try {
    doc = JSON.parse(text);
  } catch {
    throw new Refusal("not_json", "not JSON");
  }
  if (!isObject(doc) || doc.format !== FORMAT) throw new Refusal("not_a_board", "wrong format");
  // The envelope is read before anything else, so a plugin of any age can
  // refuse a file it would draw wrong rather than draw it.
  const floor = doc.min_reader_version;
  if (typeof floor !== "number" || !Number.isInteger(floor)) {
    throw new Refusal("malformed", "min_reader_version is missing");
  }
  if (floor > READER_VERSION) throw new Refusal("too_new", `needs reader ${floor}`);

  const paletteIn = doc.palette;
  if (!isObject(paletteIn)) throw new Refusal("malformed", "palette is missing");
  const palette: Record<string, string> = {};
  for (const [token, hex] of Object.entries(paletteIn)) {
    if (typeof hex !== "string" || !HEX.test(hex)) throw new Refusal("malformed", `colour ${token}`);
    palette[token] = hex;
  }
  const colour = (o: Record<string, Json>): string => {
    const token = str(o, "colour", 64);
    if (!(token in palette)) throw new Refusal("malformed", `no colour for ${token}`);
    return token;
  };

  const strings = doc.strings;
  if (!isObject(strings)) throw new Refusal("malformed", "strings are missing");
  const totals = doc.totals;
  if (!isObject(totals)) throw new Refusal("malformed", "totals are missing");

  let seen = 0;
  const frames: Frame[] = arr(doc, "frames").map((f) => {
    if (!isObject(f)) throw new Refusal("malformed", "frame");
    const columns: Column[] = arr(f, "columns").map((c) => {
      if (!isObject(c)) throw new Refusal("malformed", "column");
      const quotes: Quote[] = arr(c, "quotes").map((q) => {
        if (!isObject(q)) throw new Refusal("malformed", "quote");
        if (++seen > MAX_QUOTES) throw new Refusal("too_large", "too many quotes");
        const clip = q.clip_url;
        if (clip !== null && typeof clip !== "string") throw new Refusal("malformed", "clip_url");
        const partsIn = arr(q, "parts");
        if (partsIn.length === 0 || partsIn.length > MAX_PARTS) throw new Refusal("malformed", "parts");
        const parts = partsIn.map((p) => {
          if (typeof p !== "string" || p.length > MAX_TEXT) throw new Refusal("malformed", "part");
          return p;
        });
        return { parts, attribution: str(q, "attribution", 200), colour: colour(q), clipUrl: clip };
      });
      const quoteCount = int(c, "quote_count");
      if (quoteCount !== quotes.length) throw new Refusal("malformed", "column count disagrees");
      return { label: str(c, "label", 500), count: str(c, "count", 200), quoteCount, colour: colour(c), quotes };
    });
    return { title: str(f, "title", 200), columns };
  });

  const totalQuotes = int(totals, "quotes");
  if (totalQuotes !== seen) throw new Refusal("malformed", "totals disagree");

  return {
    title: str(doc, "title", 500),
    stickyShape: str(doc, "sticky_shape", 32),
    clipLabel: str(strings, "clip", 100),
    palette,
    totalQuotes,
    frames,
  };
}

// http(s), a host with no credentials in it (no "@"), then an optional path,
// with no whitespace or backslash anywhere.
const WEB_ADDRESS = /^https?:\/\/([^\s/?#@\\]+)(?:[/?#][^\s\\]*)?$/i;

/** A clip link is drawn only if it is plainly a web address. The file could
 * have been edited, so this is checked here as well as in Bristlenose.
 *
 * A pattern, not `new URL()`: Figma's plugin sandbox has no `URL` (measured
 * 17 Oct 2026 — `ReferenceError: 'URL' is not defined`), so the first build
 * silently dropped every clip link while passing its tests under Node. */
export function safeClipUrl(raw: string | null): { href: string; host: string } | null {
  if (!raw || raw.length > 2048) return null;
  const match = WEB_ADDRESS.exec(raw);
  return match ? { href: raw, host: match[1].toLowerCase() } : null;
}
