/**
 * Board geometry for the Screens lens: which edge of the screengrab each card annotates, where it
 * sits along that edge, when a column stacks, and the leader from a card to its line. Pure
 * functions, unit-tested; the lens only measures and draws.
 *
 * Rules (docs/design-screens.md S5, "Placement"):
 * - Boundary labelling, as on an architect's drawing or a UX redline: annotations all around the
 *   artefact, never over it (the owner, 14 Oct 2026, reversing the prototype's overlapping edge).
 *   Automatic placement puts a card in a column beside the screengrab or a band above or below it,
 *   across a gutter the leader visibly crosses. Cards and gutter keep their size; the screengrab is
 *   what shrinks. A card the researcher drags goes wherever they put it.
 * - Four edges. A linked card goes to the band nearest its line: left or right by which half of the
 *   page the line is in, top for a line in the top BAND_Y of the page and away from the side edges
 *   (a header, a search box), bottom likewise (a footer). The top and bottom bands are for those
 *   clear cases only, so most cards still go to the sides.
 * - Along a band, cards keep the order of their lines along that edge, so automatic leaders do not
 *   cross; a card wants to sit level with (or above, or below) its line.
 * - Widths, by mode: two side columns when the stage fits both beside a screengrab of at least
 *   MIN_SHOT_W ("lr"); one, on the right, when it fits one ("r"); below that ("rows") the side
 *   bands become rows above and below the screengrab, in order, with short vertical leaders. A
 *   column with no cards takes no room. The mode changes only at a threshold, with HYSTERESIS.
 * - A column that would run past the screengrab stacks: evenly stepped, each card showing its
 *   timecode and first line, the later card over the earlier one's tail. Stacks are straight.
 * - Leaders are short, straight or single-elbow: a drafting leader's shoulder off the card, then
 *   one straight run to the line. Cards about one line share its anchor, so their leaders fan in.
 */

/** A card column's width: the cards keep this size whatever the stage. */
export const CARD_W = 270;
/** Between a card column and the screengrab: --bn-space-xl (2rem), in px at the default zoom. */
export const COLUMN_GUTTER = 32;
/** Below this width the screengrab stops being legible, so no column takes room from it. */
export const MIN_SHOT_W = 480;
/** Stage widths that fit two columns, and one, beside a legible screengrab. */
export const WIDE_STAGE = MIN_SHOT_W + 2 * (CARD_W + COLUMN_GUTTER); // 1084
export const ONE_COLUMN_STAGE = MIN_SHOT_W + CARD_W + COLUMN_GUTTER; // 782
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

// ── Arrangement: where the researcher put each card, per screengrab ─────────
//
// The owner, 14 Oct 2026: "if the user does nothing but resize, re-order automagically; if they
// reposition some or all cards, respect that work and intention but still re-organise the cards
// they didn't touch." So a placed card is stored as INTENT, not coordinates — which edge of the
// screengrab it sits beside, and how far down that edge as a fraction of the screengrab's height —
// and it moves with the image as the stage resizes. A card dropped over the screengrab keeps its
// place there (the researcher's choice; automatic placement never covers it).

export type Placement =
  /** Beside the screengrab: which side, and its top as a fraction of the screengrab's height. */
  | { kind: "edge"; side: Side; frac: number; z: number }
  /** Over the screengrab: its top-left as fractions of the screengrab's width and height. */
  | { kind: "over"; x: number; y: number; z: number };

/**
 * Kept in this browser's storage, keyed by the page's project id. Today that id is always "1"
 * (`data-project-id` is hard-coded in server/app.py and routes/export.py), so the key separates
 * arrangements by origin — the port the report is served on — and nothing finer: two projects
 * served on one port share them. The id is in the key so it becomes real with multi-project. Where
 * arrangements should live (a saved researcher edit, per project, perhaps in the export) is the
 * owner's call, docs/design-screens.md §6.9.
 */
const storeKey = (projectId: string) => `bristlenose-screens-placements-${projectId}`;
/** The first build's store: coordinates. Read once, converted to intent, then removed. */
const legacyKey = (projectId: string) => `bristlenose-screens-arrangement-${projectId}`;

type Arrangement = Record<string, Placement>;

export function stillKey(sessionId: string, t: number): string {
  return `${sessionId}@${t}`;
}

function isPlacement(v: unknown): v is Placement {
  if (!v || typeof v !== "object") return false;
  const p = v as Record<string, unknown>;
  if (p.kind === "edge") return (p.side === "L" || p.side === "R") && typeof p.frac === "number" && typeof p.z === "number";
  if (p.kind === "over") return typeof p.x === "number" && typeof p.y === "number" && typeof p.z === "number";
  return false;
}

/** A first-build spot {x, y, z} (top-left as fractions of the screengrab) as intent: left of the
 *  screengrab is the left edge, past its right edge the right, anything else was put over it. */
export function fromLegacy(spot: { x: number; y: number; z: number }): Placement {
  if (spot.x < 0) return { kind: "edge", side: "L", frac: spot.y, z: spot.z };
  if (spot.x >= 0.95) return { kind: "edge", side: "R", frac: spot.y, z: spot.z };
  return { kind: "over", x: spot.x, y: spot.y, z: spot.z };
}

function read(projectId: string): Arrangement {
  const out: Arrangement = {};
  try {
    const raw = localStorage.getItem(storeKey(projectId));
    const v = raw ? (JSON.parse(raw) as unknown) : {};
    if (v && typeof v === "object") for (const [k, p] of Object.entries(v)) if (isPlacement(p)) out[k] = p;
    const old = localStorage.getItem(legacyKey(projectId));
    if (old) {
      const legacy = JSON.parse(old) as Record<string, { x: number; y: number; z: number }>;
      for (const [k, spot] of Object.entries(legacy ?? {})) {
        if (!(k in out) && spot && typeof spot.x === "number" && typeof spot.y === "number") {
          out[k] = fromLegacy({ x: spot.x, y: spot.y, z: typeof spot.z === "number" ? spot.z : 31 });
        }
      }
      localStorage.setItem(storeKey(projectId), JSON.stringify(out));
      localStorage.removeItem(legacyKey(projectId));
    }
  } catch {
    /* unreadable or unavailable storage: start automatic */
  }
  return out;
}

function write(projectId: string, a: Arrangement): void {
  try {
    localStorage.setItem(storeKey(projectId), JSON.stringify(a));
  } catch {
    /* private window or full storage: the arrangement lasts the page */
  }
}

const memory = new Map<string, Arrangement>();
// A version that rises on every write, so a board — or an undo after the board has moved to another
// screen — re-reads the arrangement through useSyncExternalStore.
let version = 0;
const listeners = new Set<() => void>();
export function subscribeArrangement(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export function arrangementVersion(): number {
  return version;
}
function store(projectId: string, a: Arrangement): void {
  memory.set(projectId, a);
  write(projectId, a);
  version++;
  for (const l of listeners) l();
}
function all(projectId: string): Arrangement {
  let a = memory.get(projectId);
  if (!a) {
    a = read(projectId);
    memory.set(projectId, a);
  }
  return a;
}

export function placementsFor(projectId: string, still: string): Record<string, Placement> {
  const out: Record<string, Placement> = {};
  const prefix = `${still}/`;
  for (const [k, v] of Object.entries(all(projectId))) if (k.startsWith(prefix)) out[k.slice(prefix.length)] = v;
  return out;
}

export function topZ(projectId: string): number {
  return Object.values(all(projectId)).reduce((m, s) => Math.max(m, s.z), 30);
}

export function putPlacement(projectId: string, still: string, domId: string, placement: Placement): void {
  const a = { ...all(projectId), [`${still}/${domId}`]: placement };
  store(projectId, a);
}

/** One card back to automatic placement. */
export function clearPlacement(projectId: string, still: string, domId: string): void {
  const a = { ...all(projectId) };
  delete a[`${still}/${domId}`];
  store(projectId, a);
}

/** A screengrab's whole arrangement, replaced: `{}` returns every card to automatic (Tidy); a
 *  saved copy puts it back (undo). */
export function setPlacements(projectId: string, still: string, placements: Record<string, Placement>): void {
  const a = { ...all(projectId) };
  for (const k of Object.keys(a)) if (k.startsWith(`${still}/`)) delete a[k];
  for (const [d, p] of Object.entries(placements)) a[`${still}/${d}`] = p;
  store(projectId, a);
}

/** Tests only. */
export function resetArrangementMemory(): void {
  memory.clear();
  version++;
}

// ── A column with hand-placed cards ─────────────────────────────────────────

export interface ColumnCard {
  id: string;
  height: number;
  /** Where its top would like to be: a placed card's spot, or level with an untouched card's element. */
  want: number;
  /** Placed by hand: it keeps its spot, and the untouched cards give way. */
  placed: boolean;
  /** Placing order, to keep the researcher's order between two placed cards at one height. */
  z?: number;
}

/**
 * Tops for a column that may hold hand-placed cards. Placed cards win: each sits at its own spot,
 * in the researcher's order, pushed down only as far as it takes not to overlap another placed
 * card. Untouched cards then re-flow around them, each in turn by its element's height into the
 * free slot nearest its anchor. A column with no placed card is the automatic column
 * (`placeColumn`, which stacks when it runs long); one with placed cards grows rather than stack,
 * so nobody's card is hidden under another's.
 */
export function arrangeColumn(
  cards: ColumnCard[],
  limit: number,
): { tops: Record<string, number>; stacked: boolean; bottom: number } {
  if (!cards.some((c) => c.placed)) {
    const order = [...cards].sort((a, b) => a.want - b.want);
    const { placed, stacked, bottom } = placeColumn(order, limit);
    const tops: Record<string, number> = {};
    order.forEach((c, i) => (tops[c.id] = placed[i].top));
    return { tops, stacked, bottom };
  }
  const tops: Record<string, number> = {};
  const taken: [number, number][] = [];
  const free = (y: number, h: number) =>
    y >= 0 && taken.every(([t, b]) => y + h + GUTTER <= t || y >= b + GUTTER);
  const own = cards.filter((c) => c.placed).sort((a, b) => a.want - b.want || (a.z ?? 0) - (b.z ?? 0));
  let floor = 0;
  for (const c of own) {
    const y = Math.max(c.want, floor);
    tops[c.id] = y;
    taken.push([y, y + c.height]);
    floor = y + c.height + GUTTER;
  }
  for (const c of cards.filter((c) => !c.placed).sort((a, b) => a.want - b.want)) {
    const candidates = [c.want, 0];
    for (const [t, b] of taken) candidates.push(t - c.height - GUTTER, b + GUTTER);
    const fits = candidates.filter((y) => free(y, c.height));
    const y = fits.reduce((best, y) => (Math.abs(y - c.want) < Math.abs(best - c.want) ? y : best), Infinity);
    const top = Number.isFinite(y) ? y : Math.max(0, ...taken.map(([, b]) => b + GUTTER));
    tops[c.id] = top;
    taken.push([top, top + c.height]);
  }
  const bottom = Math.max(0, ...cards.map((c) => tops[c.id] + c.height));
  return { tops, stacked: false, bottom };
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

// ── The whole board ─────────────────────────────────────────────────────────

/** A card the board places on an edge: a linked card (its line on the visible screengrab), or one
 *  the researcher placed beside it. Cards dropped over the screengrab are not placed here. */
export interface BoardCard {
  id: string;
  height: number;
  /** The line it is about on the visible screengrab: an automatic card. */
  anchor?: Box;
  /** Where the researcher put it beside the screengrab: a placed card, which wins. */
  placed?: { side: Side; frac: number; z: number };
}

export interface Spot {
  edge: Edge;
  /** In the edge's own box: a column's top, or a band's top and left. */
  top: number;
  left: number;
  /** Stacking order within a column, the lowest card on top of the one above it. */
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

/**
 * The edge a card goes to. A placed card keeps its side; where its side has no column (one column,
 * on the right) it goes to the right; in rows mode, where the side columns have become rows, it goes
 * to the row above for the top half of the screengrab and below for the rest, at the head of the row
 * (placed cards lead, as they led the list under the screengrab before rows).
 */
export function cardEdge(c: Pick<BoardCard, "anchor" | "placed">, mode: Mode): Edge {
  if (c.placed) {
    if (mode === "rows") return c.placed.frac < 0.5 ? "T" : "B";
    return mode === "lr" ? c.placed.side : "R";
  }
  return edgeFor(c.anchor ?? { x: 1, y: 0.5, w: 0, h: 0 }, mode);
}

const centreX = (b?: Box) => (b ? b.x + b.w / 2 : 0);
const centreY = (b?: Box) => (b ? b.y + b.h / 2 : 0);

/**
 * Where every edge card goes, for a screengrab of `shot` px in `mode`. Side columns are
 * `arrangeColumn` (placed cards win; the rest re-flow by their lines' heights); bands are
 * `placeRow` in the order of the lines left to right, placed cards first.
 */
export function composeBoard(cards: BoardCard[], mode: Mode, shot: { W: number; H: number }): Composition {
  const at: Record<string, Spot> = {};
  const stacked: Record<Side, boolean> = { L: false, R: false };
  const band: Record<"T" | "B", number> = { T: 0, B: 0 };
  let colBottom = 0;
  for (const side of ["L", "R"] as Side[]) {
    const col = cards.filter((c) => cardEdge(c, mode) === side);
    if (!col.length) continue;
    const { tops, stacked: st, bottom } = arrangeColumn(
      col.map((c) => ({
        id: c.id,
        height: c.height,
        want: c.placed ? Math.max(0, c.placed.frac * shot.H) : Math.max(0, centreY(c.anchor) * shot.H - 20),
        placed: !!c.placed,
        z: c.placed?.z ?? 0,
      })),
      shot.H,
    );
    [...col].sort((a, b) => tops[a.id] - tops[b.id]).forEach((c, i) => (at[c.id] = { edge: side, top: tops[c.id], left: 0, z: 2 + i }));
    stacked[side] = st;
    colBottom = Math.max(colBottom, bottom);
  }
  for (const edge of ["T", "B"] as const) {
    const row = cards.filter((c) => cardEdge(c, mode) === edge);
    if (!row.length) continue;
    const placed = row
      .filter((c) => c.placed)
      .sort((a, b) => a.placed!.frac - b.placed!.frac || a.placed!.z - b.placed!.z);
    const auto = row
      .filter((c) => !c.placed)
      .sort((a, b) => centreX(a.anchor) - centreX(b.anchor) || centreY(a.anchor) - centreY(b.anchor));
    const order = [...placed, ...auto];
    const { lefts, tops, height } = placeRow(
      order.map((c) => ({
        want: c.placed ? 0 : centreX(c.anchor) * shot.W - CARD_W / 2,
        width: CARD_W,
        height: c.height,
      })),
      shot.W,
    );
    order.forEach((c, i) => (at[c.id] = { edge, top: tops[i], left: lefts[i], z: 2 }));
    band[edge] = height;
  }
  return { at, stacked, colBottom, band };
}

/**
 * Where a card dropped at `card` (board coordinates) should live, as intent: beside the screengrab
 * on the side its centre fell, or over it. `shot` is the screengrab's rectangle in the same space.
 */
export function placementFromDrop(
  card: { left: number; top: number; width: number },
  shot: { left: number; top: number; width: number; height: number },
  z: number,
): Placement {
  const cx = card.left + card.width / 2;
  if (cx < shot.left) return { kind: "edge", side: "L", frac: (card.top - shot.top) / shot.height, z };
  if (cx > shot.left + shot.width) return { kind: "edge", side: "R", frac: (card.top - shot.top) / shot.height, z };
  return { kind: "over", x: (card.left - shot.left) / shot.width, y: (card.top - shot.top) / shot.height, z };
}
