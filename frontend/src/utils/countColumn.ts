/**
 * The count column shared by every tag row in a list (tag sidebar, Codebook lens).
 *
 * Each tag row is its own small grid, so nothing ties one row's bar to the next.
 * The bars line up only if every count takes the same width, and that width is
 * the widest count in the list, in digits: one value set on the list's outer
 * element as `--bn-count-digits`, read by `.tag-count` as `min-width: N ch`
 * (tabular figures, so every digit is one `ch`). Owner's choice, 23 Nov 2026:
 * as tight as the counts allow, moving only when the widest count crosses 9→10
 * or 99→100, and then every row together.
 *
 * Set on the list, not on a lens root: a custom property invalidates the style
 * of everything beneath it in WebKit (frontend/gotchas.md), and a tag list is a
 * few hundred nodes whose value changes at a digit boundary, not on every frame.
 */

import type { CSSProperties } from "react";

/** Digits in the widest count, at least one. */
export function countDigits(counts: Iterable<number>): number {
  let max = 0;
  for (const n of counts) if (n > max) max = n;
  return String(Math.floor(max)).length;
}

/** Inline style that sets the list's count-column width. */
export function countColumnStyle(counts: Iterable<number>): CSSProperties {
  return { "--bn-count-digits": countDigits(counts) } as CSSProperties;
}
