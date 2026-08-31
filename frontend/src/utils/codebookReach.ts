/**
 * The one sentence that says how big a codebook is and how far it has reached.
 *
 * TWO FACTS, NOT A RATIO. The count of tags is a property of the CODEBOOK — the
 * size of its vocabulary, identical in every project and identical whether it is
 * installed. The count of quotes is a property of THIS project. "28 tags on 2
 * quotes" welded them into one relationship, which reads as *these 28 tags were
 * applied, landing on 2 quotes* — implying the whole vocabulary is in play when
 * usually a handful of it is. Worse, the eye computes 28:2 and concludes
 * something about coverage that nobody said.
 *
 * The interpunct separates them back into two facts, and naming the project
 * marks the exact point where the scope changes from "this codebook, anywhere"
 * to "your corpus, here".
 *
 * NAMED `codebookReach`, NOT `codebookCounts`: `codebookCounts()` is already an
 * unrelated function in `lensSubtitle.ts` returning `{codebooks, tags}` for the
 * window subtitle. Two different things under one stem is the collision
 * `docs/design-shared-formats.md` §5 exists to prevent — a grep for the family
 * would have returned both. Renamed 31 Aug 2026, the same day it was added.
 *
 * @module codebookReach
 */

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

/** "28 tags" — vocabulary size, for a codebook not installed here. */
export function vocabularyPhrase(tags: number): string {
  return `${tags} ${plural(tags, "tag", "tags")}`;
}

/**
 * "28 tags · applied to 2 quotes in Ikea" — vocabulary size, then reach.
 *
 * ZERO DROPS THE WHOLE CLAUSE. "applied to 0 quotes" asserts an application
 * that did not happen; the codebook is installed and nothing has been coded
 * with it yet, which is a state the researcher can see. Saying only "31 tags"
 * is true and complete. One of the three call sites had already worked this
 * out and guarded with `book.quotes ? … : ""` — the other two carried "on 0
 * quotes" into the UI. Putting it here is what stops that being a per-site
 * decision.
 *
 * Falls back to the un-scoped phrasing when the project has no name to give;
 * "in " with nothing after it is worse than the sentence it replaced.
 */
export function reachPhrase(
  tags: number,
  quotes: number,
  projectName: string,
): string {
  if (quotes === 0) return vocabularyPhrase(tags);
  const reach = `applied to ${quotes} ${plural(quotes, "quote", "quotes")}`;
  const scoped = projectName.trim() ? `${reach} in ${projectName}` : reach;
  return `${vocabularyPhrase(tags)} \u00b7 ${scoped}`;
}
