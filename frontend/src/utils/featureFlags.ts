/**
 * featureFlags — parked features, kept whole but switched off.
 *
 * A flag here means: the feature is BUILT, TESTED and DOCUMENTED, but the
 * interaction isn't good enough to ship, so the affordance is withheld while
 * the code, the tests and the design rationale stay in the tree. This is
 * deliberately not a commenting-out and deliberately not a deletion — a
 * revisit should start from working code and a written record of why it was
 * parked, not from a git archaeology dig.
 *
 * Rules for this module:
 *
 * - **Flags are gates on the affordance, not on the code.** Everything behind
 *   a flag still compiles, still type-checks, and still has passing tests
 *   (the tests flip the flag on — see `resetFeatureFlags`). A flag that lets
 *   its feature rot is worse than a deletion.
 * - **Each flag names its design doc.** The doc carries the parked banner and
 *   the open questions that have to be answered before the flag flips.
 * - **Flipping a flag on is a design decision, not a cleanup.** If a revisit
 *   concludes the feature isn't worth finishing, delete the feature and the
 *   flag together in one commit.
 *
 * Mutable by design so tests can exercise the parked behaviour. Production
 * code only ever reads.
 */

export interface FeatureFlags {
  /**
   * Chevrons above/below a quote's timecode that pull in the neighbouring
   * transcript segments, growing the quote card with surrounding context.
   *
   * Parked 5 Aug 2026 — the chevrons read as decoration rather than control
   * (they're revealed on hover, sit in the timecode gutter, and carry no
   * label), and expansion is one-way: there is no gesture to collapse the
   * context back once revealed. Design doc:
   * `docs/design-quote-context-expansion.md`.
   */
  quoteContextExpansion: boolean;

  /**
   * "Question?" pill that appears after hovering the first few words of a
   * quote, revealing the moderator's preceding question above the quote.
   *
   * Parked 5 Aug 2026 — the hover target is an unmarked 14em × 1.6em zone
   * over the start of the quote text, so the affordance is undiscoverable
   * unless you happen to rest the pointer there. Design doc:
   * `docs/design-moderator-question-pill.md`.
   *
   * Note the server endpoint, the API helper and the CSS stay live and
   * tested — only the client affordance is withheld.
   */
  moderatorQuestionPill: boolean;
}

/** The shipped state. Change these to flip a feature back on. */
const DEFAULTS: FeatureFlags = {
  quoteContextExpansion: false,
  moderatorQuestionPill: false,
};

export const featureFlags: FeatureFlags = { ...DEFAULTS };

/**
 * Restore the shipped defaults.
 *
 * Test-only. Flags are module-level state, so a suite that flips one must
 * reset it — same discipline as the module-level stores (see
 * `frontend/CLAUDE.md` § Testing).
 */
export function resetFeatureFlags(): void {
  Object.assign(featureFlags, DEFAULTS);
}
