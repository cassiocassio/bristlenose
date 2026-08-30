/**
 * codebookSummary — the one-line meta shown when a codebook section is folded.
 *
 * When a codebook is switched off its groups collapse; a summary line takes
 * their place so the researcher still sees, at a glance, what they've tucked
 * away ("N tags · M coded"). Pure aggregation over the framework's groups.
 *
 * See design-codebook-library.md § "Fold animation" / collapsed summary meta.
 *
 * @module codebookSummary
 */

import type { CodebookGroupResponse } from "./types";

export interface FrameworkSummary {
  /** Total tags across all the framework's groups. */
  tagCount: number;
  /** Total coded quotes across the framework's groups (the per-group
   * "Total" figures summed — the same volume already surfaced per column). */
  codedQuotes: number;
}

/** Aggregate a framework's groups into the folded-summary figures. */
export function summariseFramework(
  groups: CodebookGroupResponse[],
  distinctQuotes?: number,
): FrameworkSummary {
  let tagCount = 0;
  let summedQuotes = 0;
  for (const g of groups) {
    tagCount += g.tags.length;
    summedQuotes += g.total_quotes;
  }
  // `total_quotes` is distinct WITHIN a group, so summing it across a
  // framework's groups counts a quote once per group it appears in — which
  // showed the researcher a figure larger than their quote count. The server
  // sends the distinct total (`framework_quote_totals`); the sum survives only
  // as the fallback for a response that predates it. Register B6.
  return { tagCount, codedQuotes: distinctQuotes ?? summedQuotes };
}
