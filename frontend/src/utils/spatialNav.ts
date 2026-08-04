/**
 * spatialNav — geometric quote navigation for the arrow keys.
 *
 * The quotes lens is a multi-column `auto-fill` grid that upgrades to masonry
 * (`display: grid-lanes`, `organisms/responsive-grid.css`) on WebKit — so the
 * WKWebView always gets masonry. DOM order and visual position therefore
 * diverge: the next quote in the DOM renders to the *right*, not below, which
 * made the arrow keys mean something other than what they draw.
 *
 * `j`/`k` keep the DOM-order list model — "next item in reading order" is
 * correct for them whatever the layout, and they're what the native Quotes
 * menu's Next/Previous Quote drive. The arrows are answered geometrically here.
 *
 * **The rule is nearest-centre within the pressed half-plane.** Three rules
 * were prototyped side by side in `docs/mockups/quotes-spatial-arrow-nav.html`
 * (line-of-sight with a remembered y, nearest-centre, max-overlap); all three
 * felt equivalent on a realistic sample, so this is the one that wins on
 * parsimony — no lane detection, no carried state, no reset rules. The mockup
 * keeps the other two implementations and records the symptom that would
 * justify switching (focus that "wanders" or won't return, on wide windows or
 * studies with very uneven quote lengths — that's non-reversibility, and
 * line-of-sight is the fix).
 *
 * Nothing here computes the layout. Lanes, column count, section boundaries
 * and filtered-out cards all resolve by measuring, which is why none of them
 * need special-casing.
 *
 * **Cost, stated honestly.** `.quote-group .quote-card` carries
 * `content-visibility: auto` so the browser can skip layout for scrolled-out
 * cards (there is no virtualisation — see `bristlenose/theme/CLAUDE.md`
 * § Off-screen rendering skip). Calling `getBoundingClientRect()` on such a
 * card *forces* that skipped layout, so `readCardRects` is not free and does
 * not merely read geometry the browser already had: its cost scales with the
 * number of quotes passing the current filter, not with what's on screen.
 * Both quote islands mount at once, so on the largest fixtures that is a few
 * thousand elements per keypress. Bounding this is tracked as an open
 * finding; measure before optimising, and prefer document-relative caching
 * invalidated on layout change over a per-keypress budget.
 *
 * @module spatialNav
 */

export type Direction = "up" | "down" | "left" | "right";

/** A laid-out quote card, reduced to what the scoring needs. */
export interface CardRect {
  id: string;
  cx: number;
  cy: number;
}

/**
 * Horizontal tolerance in px for "same column".
 *
 * Cards in one lane share a left edge — every lane is `1fr` off the same
 * `minmax`, so their centres coincide. This band is what excludes same-lane
 * cards from a left/right move, which is why the rule needs no lane detection:
 * the tolerance does that work implicitly.
 */
const LANE_TOL = 6;

/** Does `c` lie in `dir` from `from`? */
const IN_DIRECTION: Record<Direction, (c: CardRect, from: CardRect) => boolean> = {
  right: (c, from) => c.cx > from.cx + LANE_TOL,
  left: (c, from) => c.cx < from.cx - LANE_TOL,
  down: (c, from) => c.cy > from.cy + 1,
  up: (c, from) => c.cy < from.cy - 1,
};

/**
 * How much harder a step across the pressed axis is penalised.
 *
 * Without this, plain nearest-centre answers a *vertical* press with a
 * *sideways* card. `.quote-group` is `align-items: start`, so two cards in the
 * same visual row have different centres as soon as their heights differ — and
 * a tall neighbour one lane over can then be closer than the card genuinely
 * below. Worked case at the real 388px lane pitch: from a short card at
 * (582, 60), the tall left-hand neighbour at (194, 200) scores 412 while the
 * card actually below it at (582, 495) scores 435, so `↓` moved *left*.
 * Weighting the cross axis makes those 788 vs 435 — the intuitive answer.
 *
 * This is not masonry-specific: the rectangular grid Chromium and Firefox
 * render has exactly the same shape.
 *
 * **Where 2 stops being enough.** A level sideways neighbour wins again once
 * the same-lane card below is more than `hypot(lanePitch * 2, 0)` away
 * centre-to-centre — ~776px at today's 388px pitch, i.e. two stacked cards of
 * roughly 750px each. Real quote cards run 100–300px, so there is ~2.5×
 * headroom. The constant is chosen, not derived: if cards ever get much taller
 * (very long verbatims, or a density mode that stacks more metadata) that
 * margin shrinks and this wants re-deriving rather than nudging.
 */
const CROSS_AXIS_PENALTY = 2;

/**
 * The quote nearest `currentId` in `direction`, or null when there's nothing
 * that way (the edge of the grid) or `currentId` isn't among `rects`.
 *
 * Pure — takes measured geometry so it can be tested without a layout engine.
 */
export function nextSpatial(
  rects: CardRect[],
  currentId: string,
  direction: Direction,
): string | null {
  const from = rects.find((r) => r.id === currentId);
  if (!from) return null;

  const isCandidate = IN_DIRECTION[direction];
  const horizontal = direction === "left" || direction === "right";
  // Penalise displacement across the pressed axis, never along it.
  const kx = horizontal ? 1 : CROSS_AXIS_PENALTY;
  const ky = horizontal ? CROSS_AXIS_PENALTY : 1;

  let bestId: string | null = null;
  let bestDistance = Infinity;

  for (const c of rects) {
    if (c.id === currentId || !isCandidate(c, from)) continue;
    const d = Math.hypot((c.cx - from.cx) * kx, (c.cy - from.cy) * ky);
    // Strict `<` keeps the first of any tie, so a tie resolves in DOM order —
    // stable across keypresses rather than dependent on iteration accidents.
    if (d < bestDistance) {
      bestDistance = d;
      bestId = c.id;
    }
  }
  return bestId;
}

/**
 * Measure the given quotes from the DOM, in one batched pass.
 *
 * One reflow per keypress rather than one per card. Cards with no box are
 * dropped: a `display: none` quote (the hidden-quote path) reports a zero rect
 * at the origin, which would otherwise sit at (0,0) and win every distance
 * comparison from anywhere on the page.
 */
export function readCardRects(ids: string[]): CardRect[] {
  const out: CardRect[] = [];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    // WebKit returns physically impossible boxes (bottom < top, negative
    // height) while a smooth `scrollIntoView` is animating — a documented
    // repo hazard, see frontend/CLAUDE.md § Testing. Key-repeat lands the
    // next measurement squarely inside that window, and the zero-size check
    // above doesn't catch it: a glitched rect keeps a plausible width, so
    // `cx` survives while `cy` is garbage and focus jumps somewhere
    // wrong-but-believable. An impossible box is not "not laid out" — it's
    // an unusable measurement, so drop it rather than score it.
    if (r.width < 0 || r.height < 0) continue;
    out.push({ id, cx: r.left + r.width / 2, cy: r.top + r.height / 2 });
  }
  // Registered quotes that measure to nothing at all is never a legitimate
  // state, and it's the shape both of this module's worst bugs took — the
  // arrow silently does nothing, or re-enters on the same unmeasurable card
  // forever. Neither announced itself; both were found by review. Say it out
  // loud in dev rather than wait for the next one.
  if (import.meta.env.DEV && ids.length > 0 && out.length === 0) {
    console.warn(
      `[spatialNav] ${ids.length} quote(s) registered, none measurable — ` +
        `arrow navigation can only re-enter, not move.`,
    );
  }
  return out;
}

/**
 * Where focus should land when an arrow is pressed with nothing focused.
 *
 * Matches `j`/`k` from cold — forward keys enter at the top of reading order,
 * backward keys at the end — so the two models agree on the entry point even
 * though they disagree about what a step is.
 */
export function entryPoint(ids: string[], direction: Direction): string | null {
  if (!ids.length) return null;
  return direction === "down" || direction === "right" ? ids[0] : ids[ids.length - 1];
}
