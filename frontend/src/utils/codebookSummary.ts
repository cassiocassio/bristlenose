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
): FrameworkSummary {
  let tagCount = 0;
  let codedQuotes = 0;
  for (const g of groups) {
    tagCount += g.tags.length;
    codedQuotes += g.total_quotes;
  }
  return { tagCount, codedQuotes };
}
