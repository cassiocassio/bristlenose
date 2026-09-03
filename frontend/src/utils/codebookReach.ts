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
 * CLDR PLURALS, not a hand-rolled ternary. This shipped with
 * `(n === 1 ? one : many)` while the lens was dev-gated and English-only; it
 * graduated on 31 Aug 2026, so the counts go through i18next like every other
 * counted string. `{{project}}` is interpolated rather than concatenated
 * because word order round the project name is not English's in every language.
 *
 * NAMED `codebookReach`, NOT `codebookCounts`: `codebookCounts()` is already an
 * unrelated function in `lensSubtitle.ts` returning `{codebooks, tags}` for the
 * window subtitle. Two different things under one stem is the collision
 * `docs/design-shared-formats.md` §5 exists to prevent — a grep for the family
 * would have returned both. Renamed 31 Aug 2026, the same day it was added.
 *
 * @module codebookReach
 */

import i18n from "../i18n";

/** "28 tags" — vocabulary size, for a codebook not installed here. */
export function vocabularyPhrase(tags: number): string {
  return i18n.t("codebook.tagCount", { count: tags });
}

/**
 * "28 tags · applied to 2 quotes in Ikea" — vocabulary size, then reach.
 *
 * ZERO SAYS SO, IT DOES NOT GO QUIET. This dropped the whole clause until
 * 3 Sep 2026, reasoning that "applied to 0 quotes" asserts an application that
 * did not happen and that a bare "31 tags" is "true and complete". The first
 * half of that is right and is why the wording is `none applied to {{project}}`
 * — which *denies* an application rather than asserting one at zero.
 *
 * The second half was wrong, and it is the more expensive error. A bare
 * "31 tags" is identical to the not-installed card minus three words, and
 * identical to a codebook whose run failed, and identical to one that has never
 * run. Four states, one rendering, and no signal at all — the docstring's own
 * claim that this is "a state the researcher can see" was the thing that made
 * it invisible. Naming the zero separates the legitimate outcome (it ran, it
 * matched nothing) from the rest.
 *
 * Note what this deliberately does NOT do: say *why* nothing was applied. An
 * incomplete or failed run is the project's status, not the codebook's — it
 * belongs to the sidebar status line and the run's diagnostic popover.
 *
 * Falls back to the un-scoped phrasing when the project has no name to give;
 * "in " with nothing after it is worse than the sentence it replaced.
 */
export function reachPhrase(
  tags: number,
  quotes: number,
  projectName: string,
): string {
  // NO PROJECT NAME, NO REACH CLAUSE. The sentence's second half exists to say
  // *where* the count applies; without a name to interpolate it renders
  // "…in " with nothing after it, which is worse than the sentence it
  // replaced. The pre-i18n version guarded this with an unscoped variant; a
  // second plural key across 21 locales is not worth a defensive branch the
  // lens never reaches in practice (the name comes from `/info` on mount).
  if (!projectName.trim()) return vocabularyPhrase(tags);
  const reach =
    quotes === 0
      ? i18n.t("codebook.noneApplied", { project: projectName.trim() })
      : i18n.t("codebook.appliedToQuotes", {
          count: quotes,
          project: projectName.trim(),
        });
  return `${vocabularyPhrase(tags)} \u00b7 ${reach}`;
}
