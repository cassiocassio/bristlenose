/**
 * Board geometry for the Screens lens: which edge of the screengrab each card annotates, where it
 * sits along that edge, when a column stacks, the leader from a card to its line, and the
 * researcher's arrangement. Pure functions, unit-tested; the lens only measures and draws. The one
 * exception is the arrangement store at the end, which reads and writes the project's database.
 *
 * Rules (docs/design-screens.md S5, "Placement" and "Arrangement"):
 * - Boundary labelling, as on an architect's drawing or a UX redline: annotations all around the
 *   artefact, never over it. Automatic placement puts a card in a column beside the screengrab or a
 *   band above or below it, across a gutter the leader visibly crosses. Cards and gutter keep their
 *   size; the screengrab is what shrinks.
 * - Four edges. A linked card goes to the band nearest its line: left or right by which half of the
 *   page the line is in, top for a line in the top BAND_Y of the page and away from the side edges,
 *   bottom likewise. Along a band, cards keep the order of their lines (time order breaks ties), so
 *   automatic leaders do not cross.
 * - Widths, by mode: two side columns ("lr"), one on the right ("r"), or rows above and below
 *   ("rows"). The mode changes only at a threshold, with HYSTERESIS.
 * - A column that would run past the screengrab stacks, and each later card in a stack steps
 *   diagonally down and away from the screengrab (STAGGER_STEP), as the 1984 Mac cascaded windows:
 *   you can count them, they read as separate cards, and each one's left-edge grip shows.
 * - Arrangement: automatic until the researcher drags a card; then the whole board is custom, every
 *   card frozen where it was as INTENT relative to the screengrab, and nothing re-flows until Tidy.
 */

import { apiGet, sendPut } from "../../utils/api";

/** Every card's width, in the margins and in the list alike: one kind of card. */
export const CARD_W = 340;
/** Between a card column and the screengrab: --bn-space-xl (2rem), in px at the default zoom. */
export const COLUMN_GUTTER = 32;
/** Below this width the screengrab stops being legible, so no column takes room from it. */
export const MIN_SHOT_W = 480;
/** How far each later card in a stack steps away from the screengrab, and how many steps before
 *  the cascade starts again. */
export const STAGGER_STEP = 8;
export const STAGGER_STEPS = 3;
export const MAX_STAGGER = STAGGER_STEP * STAGGER_STEPS;
/** A column holds a card and its widest stagger, so a staggered card never enters the gutter. */
export const COLUMN_W = CARD_W + MAX_STAGGER;
/** Stage widths that fit two columns, and one, beside a legible screengrab. */
export const WIDE_STAGE = MIN_SHOT_W + 2 * (COLUMN_W + COLUMN_GUTTER); // 1272
export const ONE_COLUMN_STAGE = MIN_SHOT_W + COLUMN_W + COLUMN_GUTTER; // 876
/** How far ⌥ + an arrow moves a card. */
export const MOVE_STEP = 24;
export const GUTTER = 12;
export const MIN_STEP = 46;

export type Side = "L" | "R";
/** The four edges of the screengrab a card can annotate. */
export type Edge = "L" | "R" | "T" | "B";
/** The board's arrangement for a stage width: two side columns, one (right), or rows. */
export type Mode = "lr" | "r" | "rows";

export interface Box {
  /** x, y, w, h in 0–1 of the (cropped) screengrab. */
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A line in the top or bottom BAND_Y of the page, and in the middle of it (BAND_X in from either
 *  side), goes to the band above or below; anything else to a side. */
export const BAND_Y = 0.15;
export const BAND_X = 0.2;
/** How far past a threshold the stage must widen before the layout widens back (px). Without it a
 *  stage resting on a threshold flips back and forth: the layout's own height change brings a page
 *  scrollbar in or out, which moves the stage's width across the line again. */
export const HYSTERESIS = 24;

const RANK: Record<Mode, number> = { rows: 0, r: 1, lr: 2 };
const rawMode = (w: number, lift = 0): Mode =>
  w >= WIDE_STAGE + lift ? "lr" : w >= ONE_COLUMN_STAGE + lift ? "r" : "rows";

/**
 * The mode for a stage width, given the mode it is in now. Narrowing switches at the threshold, so
 * the screengrab never falls under MIN_SHOT_W; widening waits until the stage is HYSTERESIS past
 * it. A stage of width 0 has not been measured (jsdom, the first layout): it keeps its mode, or
 * starts with one column, never the rows.
 */
export function stageMode(stageW: number, prev?: Mode | null): Mode {
  if (stageW <= 0) return prev ?? "r";
  const raw = rawMode(stageW);
  if (!prev || RANK[raw] <= RANK[prev]) return raw;
  const up = rawMode(stageW, HYSTERESIS);
  return RANK[up] > RANK[prev] ? up : prev;
}

/** Which edge an automatic card about the line `box` annotates, in `mode`. */
export function edgeFor(box: Box, mode: Mode): Edge {
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  if (mode === "rows") return cy < 0.5 ? "T" : "B";
  if (cx >= BAND_X && cx <= 1 - BAND_X) {
    if (cy < BAND_Y) return "T";
    if (cy > 1 - BAND_Y) return "B";
  }
  return mode === "lr" && cx < 0.5 ? "L" : "R";
}

/**
 * Which card columns the board draws: "lr", "l" or "r" beside the screengrab, or "none" (rows
 * mode, or no card for a side). `sides` is which sides have a card to place.
 */
export type Columns = "lr" | "l" | "r" | "none";
export function boardColumns(mode: Mode, sides: { L: boolean; R: boolean }): Columns {
  if (mode === "rows") return "none";
  if (sides.L && sides.R) return "lr";
  if (sides.L) return "l";
  if (sides.R) return "r";
  return "none";
}

export interface Placed {
  top: number;
}

/**
 * Tops for a column of cards, in the order of their elements down the page.
 * `want` is where each card would like its top; `height` its measured height; `limit` the column's
 * height budget (the screengrab's height, at least 320).
 */
export function placeColumn(
  cards: { want: number; height: number }[],
  limit: number,
): { placed: Placed[]; stacked: boolean; bottom: number } {
  if (cards.length === 0) return { placed: [], stacked: false, bottom: 0 };
  const placed: Placed[] = [];
  let y = 0;
  for (const c of cards) {
    const top = Math.max(c.want, y);
    placed.push({ top });
    y = top + c.height + GUTTER;
  }
  const last = cards[cards.length - 1];
  const budget = Math.max(limit, 320);
  const overflow = placed[placed.length - 1].top + last.height > budget;
  if (!overflow || cards.length < 2) {
    return { placed, stacked: false, bottom: placed[placed.length - 1].top + last.height };
  }
  const start = Math.max(0, Math.min(cards[0].want, budget - last.height - MIN_STEP * (cards.length - 1)));
  const step = Math.max(MIN_STEP, (budget - start - last.height) / (cards.length - 1));
  const stackedPlaced = cards.map((_, i) => ({ top: start + i * step }));
  return {
    placed: stackedPlaced,
    stacked: true,
    bottom: stackedPlaced[stackedPlaced.length - 1].top + last.height,
  };
}

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** A drafting leader's shoulder: how far the leader leaves the card straight before it turns. */
export const SHOULDER = 12;
/** How far inside a card's edge a straight leader may start. */
const LEADER_INSET = 12;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/**
 * The leader from a card to its line, in the board's space: a drafting leader. Where the line is
 * level with the card (beside it) or under it (above or below it), one straight run from the card's
 * facing edge; otherwise a short shoulder straight out of the card, then one straight run to the
 * line — a single elbow. It ends on the line's near edge, so every card about one line ends on the
 * same point and their leaders fan into it. `edge` is the edge of the screengrab the card annotates;
 * without one (a card dropped over the screengrab) the side facing the line is used.
 */
export function leaderPath(card: Rect, element: Rect, edge?: Edge): { d: string; end: [number, number] } {
  const vertical = edge === "T" || edge === "B";
  if (vertical) {
    const down = edge === "T";
    const ny = down ? card.top + card.height : card.top;
    const hx = element.left + element.width / 2;
    const hy = down ? element.top - 3 : element.top + element.height + 3;
    const lo = card.left + LEADER_INSET;
    const hi = card.left + card.width - LEADER_INSET;
    if (hx >= lo && hx <= hi) return { d: `M${hx},${ny} L${hx},${hy}`, end: [hx, hy] };
    const nx = clamp(hx, lo, hi);
    const sy = ny + (down ? SHOULDER : -SHOULDER);
    return { d: `M${nx},${ny} L${nx},${sy} L${hx},${hy}`, end: [hx, hy] };
  }
  const fromRight = edge ? edge === "L" : card.left + card.width / 2 < element.left + element.width / 2;
  const nx = fromRight ? card.left + card.width : card.left;
  const hx = fromRight ? element.left - 3 : element.left + element.width + 3;
  const hy = element.top + element.height / 2;
  if (hy >= card.top + LEADER_INSET && hy <= card.top + card.height - LEADER_INSET) {
    return { d: `M${nx},${hy} L${hx},${hy}`, end: [hx, hy] };
  }
  const ny = card.top + 16;
  const sx = nx + (fromRight ? SHOULDER : -SHOULDER);
  return { d: `M${nx},${ny} L${sx},${ny} L${hx},${hy}`, end: [hx, hy] };
}

// ── A band above or below the screengrab ───────────────────────────────────

/**
 * Lefts for a band of cards, in the order given (the order of their lines along the edge): each as
 * near its `want` as the cards before it allow, a GUTTER apart, inside `limit`. A band that runs out
 * of width carries on on a further line under the first. `height` is the band's whole height, which
 * the board reserves above or below the screengrab: the band never runs onto it.
 */
export function placeRow(
  cards: { want: number; width: number; height: number }[],
  limit: number,
): { lefts: number[]; tops: number[]; height: number } {
  const lefts: number[] = [];
  const tops: number[] = [];
  let x = 0;
  let lineTop = 0;
  let lineH = 0;
  for (const c of cards) {
    let left = Math.min(Math.max(c.want, x), Math.max(x, limit - c.width));
    if (left + c.width > limit && x > 0) {
      lineTop += lineH + GUTTER;
      lineH = 0;
      x = 0;
      left = Math.min(Math.max(0, c.want), Math.max(0, limit - c.width));
    }
    left = Math.max(0, left);
    lefts.push(left);
    tops.push(lineTop);
    lineH = Math.max(lineH, c.height);
    x = left + c.width + GUTTER;
  }
  return { lefts, tops, height: cards.length ? lineTop + lineH : 0 };
}

// ── The whole board, automatic ──────────────────────────────────────────────

/** A linked card the automatic layout places on an edge. */
export interface BoardCard {
  id: string;
  height: number;
  /** The line it is about on the visible screengrab. */
  anchor: Box;
}

export interface Spot {
  edge: Edge;
  /** In the edge's own box: a column's top, or a band's top and left. For a column, `left` is the
   *  card's stagger within the COLUMN_W track (an unstacked left card sits at MAX_STAGGER, flush
   *  to the gutter; a right one at 0). */
  top: number;
  left: number;
  /** Stacking order within a column, the later card over the earlier. */
  z: number;
}

export interface Composition {
  at: Record<string, Spot>;
  stacked: Record<Side, boolean>;
  /** How far the side columns run down from the screengrab's top. */
  colBottom: number;
  /** The height each band takes above (T) and below (B) the screengrab. */
  band: Record<"T" | "B", number>;
}

const centreX = (b: Box) => b.x + b.w / 2;
const centreY = (b: Box) => b.y + b.h / 2;

/**
 * Where every linked card goes, for a screengrab of `shot` px in `mode`. Cards come in time order,
 * which breaks ties; columns are ordered by their lines' heights and stack (with the diagonal
 * stagger) when they run long; bands by their lines left to right.
 */
export function composeBoard(cards: BoardCard[], mode: Mode, shot: { W: number; H: number }): Composition {
  const at: Record<string, Spot> = {};
  const stacked: Record<Side, boolean> = { L: false, R: false };
  const band: Record<"T" | "B", number> = { T: 0, B: 0 };
  let colBottom = 0;
  for (const side of ["L", "R"] as Side[]) {
    const col = cards
      .filter((c) => edgeFor(c.anchor, mode) === side)
      .map((c, i) => ({ c, i, want: Math.max(0, centreY(c.anchor) * shot.H - 20) }))
      .sort((a, b) => a.want - b.want || a.i - b.i);
    if (!col.length) continue;
    const { placed, stacked: st, bottom } = placeColumn(col.map((x) => ({ want: x.want, height: x.c.height })), shot.H);
    col.forEach((x, i) => {
      const k = st ? i % (STAGGER_STEPS + 1) : 0;
      const left = side === "L" ? MAX_STAGGER - k * STAGGER_STEP : k * STAGGER_STEP;
      at[x.c.id] = { edge: side, top: placed[i].top, left, z: 2 + i };
    });
    stacked[side] = st;
    colBottom = Math.max(colBottom, bottom);
  }
  for (const edge of ["T", "B"] as const) {
    const row = cards
      .map((c, i) => ({ c, i }))
      .filter((x) => edgeFor(x.c.anchor, mode) === edge)
      .sort((a, b) => centreX(a.c.anchor) - centreX(b.c.anchor) || a.i - b.i);
    if (!row.length) continue;
    const { lefts, tops, height } = placeRow(
      row.map((x) => ({ want: centreX(x.c.anchor) * shot.W - CARD_W / 2, width: CARD_W, height: x.c.height })),
      shot.W,
    );
    row.forEach((x, i) => (at[x.c.id] = { edge, top: tops[i], left: lefts[i], z: 2 }));
    band[edge] = height;
  }
  return { at, stacked, colBottom, band };
}

// ── Arrangement: automatic, or the researcher's ─────────────────────────────
//
// The owner, 15 Oct 2026, replacing the 14 Oct rule that untouched cards re-flow round placed ones:
// "when I drag a card I'm saying leave all the other cards where they are and move this one… Tidy is
// the get-out-of-jail card… losing custom positioning is a choice." So a version of a screen is
// either automatic (no arrangement stored) or custom (an arrangement stored, holding every card the
// board showed when the researcher first dragged). In custom nothing re-flows; a window resize
// scales the arrangement with the screengrab; Tidy alone returns to automatic.
//
// A card's spot is INTENT relative to the screengrab, so it moves with the image:
// - beside, above or below it ("edge"): which edge, how far along that edge as a fraction of the
//   screengrab's height (L, R) or width (T, B), and how far out from it in px — the gutter and any
//   stagger — which does not scale, so a card frozen beside the screengrab never slides onto it;
// - over it ("over", only by hand): its top-left as fractions of the screengrab's width and height.
// A card that was in the list under the screengrab freezes as a bottom-edge card: its left as a
// fraction of the screengrab's width from the screengrab's left (negative where the list starts
// left of it), and its distance below the screengrab in px.

export type Intent =
  | { kind: "edge"; edge: Edge; along: number; out: number; z: number }
  | { kind: "over"; x: number; y: number; z: number };

/** A custom version's arrangement: a spot per card. Absent = automatic. */
export type Arrangement = Record<string, Intent>;

/** The intent for a card at `r` (board coordinates), against the screengrab at `s`. Below or above
 *  it first (the list, a band, a long column's tail), then beside it, else over it. */
export function intentFromRect(r: Rect, s: Rect, z: number): Intent {
  if (r.top >= s.top + s.height) {
    return { kind: "edge", edge: "B", along: (r.left - s.left) / s.width, out: r.top - (s.top + s.height), z };
  }
  if (r.top + r.height <= s.top) {
    return { kind: "edge", edge: "T", along: (r.left - s.left) / s.width, out: s.top - (r.top + r.height), z };
  }
  if (r.left + r.width <= s.left) {
    return { kind: "edge", edge: "L", along: (r.top - s.top) / s.height, out: s.left - (r.left + r.width), z };
  }
  if (r.left >= s.left + s.width) {
    return { kind: "edge", edge: "R", along: (r.top - s.top) / s.height, out: r.left - (s.left + s.width), z };
  }
  return { kind: "over", x: (r.left - s.left) / s.width, y: (r.top - s.top) / s.height, z };
}

/** Where a card with intent `p` and height `h` sits, against the screengrab at `s` (the inverse of
 *  intentFromRect). An edge card's distance out never goes negative, so it never covers the
 *  screengrab; only a card the researcher dropped over it does. */
export function rectFromIntent(p: Intent, s: Rect, h: number): { left: number; top: number } {
  if (p.kind === "over") return { left: s.left + p.x * s.width, top: s.top + p.y * s.height };
  const out = Math.max(0, p.out);
  switch (p.edge) {
    case "L":
      return { left: s.left - out - CARD_W, top: s.top + p.along * s.height };
    case "R":
      return { left: s.left + s.width + out, top: s.top + p.along * s.height };
    case "T":
      return { left: s.left + p.along * s.width, top: s.top - out - h };
    default:
      return { left: s.left + p.along * s.width, top: s.top + s.height + out };
  }
}

/** Where Tidy would put a linked card, as intent: from its automatic spot. `bandT` is the height of
 *  the band above the screengrab in that layout; `below` how far the side columns run past the
 *  screengrab's foot, since the band below starts under the taller of the two (the grid's row). */
export function autoIntent(spot: Spot, h: number, shot: { W: number; H: number }, bandT: number, z: number, below = 0): Intent {
  switch (spot.edge) {
    case "L":
      return { kind: "edge", edge: "L", along: spot.top / shot.H, out: COLUMN_GUTTER + MAX_STAGGER - spot.left, z };
    case "R":
      return { kind: "edge", edge: "R", along: spot.top / shot.H, out: COLUMN_GUTTER + spot.left, z };
    case "T":
      return { kind: "edge", edge: "T", along: spot.left / shot.W, out: COLUMN_GUTTER + bandT - (spot.top + h), z };
    default:
      return { kind: "edge", edge: "B", along: spot.left / shot.W, out: COLUMN_GUTTER + below + spot.top, z };
  }
}

/** What a custom board reserves round the screengrab: a column for each side that has a card, and
 *  each band tall enough for the cards above and below it (less the gutter, which the band's
 *  margin carries). */
export function customFrame(cards: { intent: Intent; height: number }[]): { L: boolean; R: boolean; T: number; B: number } {
  const f = { L: false, R: false, T: 0, B: 0 };
  for (const { intent: p, height } of cards) {
    if (p.kind !== "edge") continue;
    if (p.edge === "L" || p.edge === "R") f[p.edge] = true;
    else f[p.edge] = Math.max(f[p.edge], Math.max(0, p.out) + height - COLUMN_GUTTER, 1);
  }
  return f;
}

// ── Storage ────────────────────────────────────────────────────────────────

/**
 * Arrangements are a researcher edit, kept in the project's database
 * (`GET …/screens/arrangements`, `PUT …/screens/arrangement`; server/routes/screens.py): one row
 * per VERSION — the screen's key and the participant's session, not the still's moment, which a
 * re-read may pick differently. Loaded once per project (`loadArrangements`) before the board
 * shows; each change is sent for its own version alone, in order. Until 15 Oct 2026 they lived in
 * this browser's localStorage, which in the Mac app is an in-memory store per serve session, so
 * quitting the app lost them; the three keys below are read once and removed.
 */
/** The 15 Oct store (`version → cards`): moved to the server on first load, then removed. */
const storeKey = (projectId: string) => `bristlenose-screens-arrangements-${projectId}`;
/** The 14 Oct store: one placement per card, keyed by still (`session@t/dom`). Read once per
 *  version, converted, then removed. */
const oldKey = (projectId: string) => `bristlenose-screens-placements-${projectId}`;
/** The first build's store: coordinates. Folded into the 14 Oct store on read, as it always was. */
const legacyKey = (projectId: string) => `bristlenose-screens-arrangement-${projectId}`;

export function versionKey(screenKey: string, sessionId: string): string {
  return `${screenKey}|${sessionId}`;
}

/** A first-build spot {x, y, z} (top-left as fractions of the screengrab) as a 14 Oct placement. */
export function fromLegacy(spot: { x: number; y: number; z: number }): OldPlacement {
  if (spot.x < 0) return { kind: "edge", side: "L", frac: spot.y, z: spot.z };
  if (spot.x >= 0.95) return { kind: "edge", side: "R", frac: spot.y, z: spot.z };
  return { kind: "over", x: spot.x, y: spot.y, z: spot.z };
}

/** The 14 Oct placement: a side and a fraction down it, or over. */
export type OldPlacement =
  | { kind: "edge"; side: Side; frac: number; z: number }
  | { kind: "over"; x: number; y: number; z: number };

/** A 14 Oct placement as intent: beside its side at the gutter, or over where it was. */
export function fromOld(p: OldPlacement): Intent {
  return p.kind === "over"
    ? { kind: "over", x: p.x, y: p.y, z: p.z }
    : { kind: "edge", edge: p.side, along: p.frac, out: COLUMN_GUTTER, z: p.z };
}

function isOld(v: unknown): v is OldPlacement {
  if (!v || typeof v !== "object") return false;
  const p = v as Record<string, unknown>;
  if (p.kind === "edge") return (p.side === "L" || p.side === "R") && typeof p.frac === "number" && typeof p.z === "number";
  if (p.kind === "over") return typeof p.x === "number" && typeof p.y === "number" && typeof p.z === "number";
  return false;
}

function isIntent(v: unknown): v is Intent {
  if (!v || typeof v !== "object") return false;
  const p = v as Record<string, unknown>;
  if (p.kind === "edge") {
    return ["L", "R", "T", "B"].includes(p.edge as string) && typeof p.along === "number" &&
      typeof p.out === "number" && typeof p.z === "number";
  }
  return p.kind === "over" && typeof p.x === "number" && typeof p.y === "number" && typeof p.z === "number";
}

function load<T>(key: string): Record<string, T> {
  try {
    const raw = localStorage.getItem(key);
    const v = raw ? (JSON.parse(raw) as unknown) : {};
    return v && typeof v === "object" ? (v as Record<string, T>) : {};
  } catch {
    return {};
  }
}

function save(key: string, v: object | null): void {
  try {
    if (v === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* private window or full storage: the arrangement lasts the page */
  }
}

/** The 14 Oct store, with the first build's folded in (and removed), as it was read before. */
function readOld(projectId: string): Record<string, OldPlacement> {
  const out: Record<string, OldPlacement> = {};
  for (const [k, p] of Object.entries(load<unknown>(oldKey(projectId)))) if (isOld(p)) out[k] = p;
  const legacy = load<{ x: number; y: number; z?: number }>(legacyKey(projectId));
  if (Object.keys(legacy).length) {
    for (const [k, spot] of Object.entries(legacy)) {
      if (!(k in out) && spot && typeof spot.x === "number" && typeof spot.y === "number") {
        out[k] = fromLegacy({ x: spot.x, y: spot.y, z: typeof spot.z === "number" ? spot.z : 31 });
      }
    }
    save(legacyKey(projectId), null);
    save(oldKey(projectId), out);
  }
  return out;
}

const memory = new Map<string, Record<string, Arrangement>>();
const loading = new Map<string, Promise<boolean>>();
// Rises on every change, so a board — or an undo after the board has moved on — re-reads.
let version = 0;
const listeners = new Set<() => void>();
export function subscribeArrangement(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export function arrangementVersion(): number {
  return version;
}
function changed(): void {
  version++;
  for (const l of listeners) l();
}

function all(projectId: string): Record<string, Arrangement> {
  return memory.get(projectId) ?? {};
}

function cardsOf(v: unknown): Arrangement {
  const cards: Arrangement = {};
  if (v && typeof v === "object") for (const [d, p] of Object.entries(v)) if (isIntent(p)) cards[d] = p;
  return cards;
}

/** Whether this project's arrangements have been read. */
export function arrangementsLoaded(projectId: string): boolean {
  return memory.has(projectId);
}

/**
 * Read this project's arrangements, once, before its board shows: a board that showed automatic
 * and then jumped to custom would be the wrong board for a moment. A version this browser kept
 * before the server held them, and the server lacks, is sent up and then forgotten here. Resolves
 * whether the read succeeded. A failed read loads nothing: a board drawn automatic over a custom
 * arrangement the server still holds would be overwritten by its first drag, so the lens waits and
 * asks again instead.
 */
export function loadArrangements(projectId: string): Promise<boolean> {
  const pending = loading.get(projectId);
  if (pending) return pending;
  const p = apiGet<{ versions: { screen_key: string; session_id: string; cards: unknown }[] }>(
    "/screens/arrangements",
  )
    .then((r) => {
      const a: Record<string, Arrangement> = {};
      for (const v of r.versions) a[versionKey(v.screen_key, v.session_id)] = cardsOf(v.cards);
      memory.set(projectId, a);
      // This browser's copy is forgotten only once the server holds every version it carried.
      const sent: Promise<boolean>[] = [];
      for (const [k, cards] of Object.entries(load<unknown>(storeKey(projectId)))) {
        const cut = k.lastIndexOf("|");
        if (cut <= 0 || k in a) continue;
        const kept = cardsOf(cards);
        if (!Object.keys(kept).length) continue;
        a[k] = kept;
        sent.push(persist(projectId, k.slice(0, cut), k.slice(cut + 1), kept));
      }
      void Promise.all(sent).then((ok) => {
        if (ok.every(Boolean)) save(storeKey(projectId), null);
      });
      changed();
      return true;
    })
    .catch((e: unknown) => {
      console.error("Screens: the arrangements could not be read", e);
      loading.delete(projectId);
      return false;
    });
  loading.set(projectId, p);
  return p;
}

/**
 * Read this project's arrangements again — when a run finishes, as the lens re-reads its screens —
 * so another window's changes show. It waits for this page's own writes to land first, and a write
 * made while the read is in flight discards the read: the page's newer copy stands, and the
 * server already has it. A failed read keeps what is shown.
 */
export function reloadArrangements(projectId: string): Promise<boolean> {
  if (!memory.has(projectId)) return loadArrangements(projectId);
  const seq = writes.get(projectId) ?? 0;
  return (queues.get(projectId) ?? Promise.resolve())
    .then(() => apiGet<{ versions: { screen_key: string; session_id: string; cards: unknown }[] }>("/screens/arrangements"))
    .then((r) => {
      if ((writes.get(projectId) ?? 0) !== seq) return true;
      const a: Record<string, Arrangement> = {};
      for (const v of r.versions) a[versionKey(v.screen_key, v.session_id)] = cardsOf(v.cards);
      memory.set(projectId, a);
      changed();
      return true;
    })
    .catch((e: unknown) => {
      console.error("Screens: the arrangements could not be read again", e);
      return false;
    });
}

// One queue per project: writes reach the server in the order they were made, so an undo lands
// after the act it reverses. Resolves whether the server took it (sendPut toasts a failure itself).
const queues = new Map<string, Promise<unknown>>();
const writes = new Map<string, number>();
function persist(projectId: string, screenKey: string, sessionId: string, cards: Arrangement | null): Promise<boolean> {
  writes.set(projectId, (writes.get(projectId) ?? 0) + 1);
  const last = queues.get(projectId) ?? Promise.resolve();
  const next = last.then(() =>
    sendPut("/screens/arrangement", { screen_key: screenKey, session_id: sessionId, cards })
      .then(() => true)
      .catch(() => false),
  );
  queues.set(projectId, next);
  return next;
}

function commit(projectId: string, screenKey: string, sessionId: string, cards: Arrangement | null): void {
  const a = { ...all(projectId) };
  const key = versionKey(screenKey, sessionId);
  if (cards === null) delete a[key];
  else a[key] = cards;
  memory.set(projectId, a);
  changed();
  persist(projectId, screenKey, sessionId, cards);
}

/** The arrangement of one version, or null while it is automatic. A pure read. */
export function arrangementFor(projectId: string, screenKey: string, sessionId: string): Arrangement | null {
  return all(projectId)[versionKey(screenKey, sessionId)] ?? null;
}

/**
 * Migrate one version from the 14 Oct store (keyed by `session@t`), once: its placed cards keep
 * their spots, the version becomes custom, and the old entries are removed. Returns whether it
 * moved anything. A version already in the new store is left alone.
 */
export function migrateArrangement(projectId: string, screenKey: string, sessionId: string, t: number): boolean {
  const key = versionKey(screenKey, sessionId);
  const a = all(projectId);
  if (key in a) return false;
  const old = readOld(projectId);
  const prefix = `${sessionId}@${t}/`;
  const mine = Object.keys(old).filter((k) => k.startsWith(prefix));
  if (!mine.length) return false;
  const cards: Arrangement = {};
  for (const k of mine) {
    cards[k.slice(prefix.length)] = fromOld(old[k]);
    delete old[k];
  }
  save(oldKey(projectId), Object.keys(old).length ? old : null);
  commit(projectId, screenKey, sessionId, cards);
  return true;
}

/** Replace one version's arrangement: null returns it to automatic (Tidy); a saved copy puts it
 *  back (undo). */
export function setArrangement(projectId: string, screenKey: string, sessionId: string, cards: Arrangement | null): void {
  commit(projectId, screenKey, sessionId, cards);
}

/** The highest stacking order of any placed card, so a card moved by hand comes out on top. */
export function topZ(projectId: string): number {
  let z = 30;
  for (const cards of Object.values(all(projectId))) for (const p of Object.values(cards)) z = Math.max(z, p.z);
  return z;
}

/** Tests only. */
export function resetArrangementMemory(): void {
  memory.clear();
  loading.clear();
  queues.clear();
  writes.clear();
  version++;
}
