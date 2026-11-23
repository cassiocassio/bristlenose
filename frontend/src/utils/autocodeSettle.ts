/**
 * After a Stop, wait for the stopped AutoCode run to settle before the lenses refresh.
 *
 * A Stop marks the job "cancelled" at once, and the chip ends there. But the batches already
 * out still answer, and the run's cut (docs/design-autocode-landing-plan.md D27, Phase 3)
 * lands after them, up to a batch's call time later. Refreshing at the Stop drew none of the
 * cut's tags. The status read says `ending` while the run's runner has not finished; this
 * waits, bounded, until it says otherwise.
 */

import { getAutoCodeStatus } from "./api";

/** How often the status is read while the run ends, and the longest wait: a batch of 25 takes
 *  about 49 s on Sonnet 4.6 (Phase 0b), so two minutes covers the batches out with room. */
export const SETTLE_POLL_MS = 2000;
export const SETTLE_LIMIT_MS = 120_000;

/** Resolves once the run has ended (or the wait runs out, or the status cannot be read: the
 *  refresh then happens anyway, as it did before). Never rejects. */
export async function waitForStoppedRunToSettle(
  frameworkId: string,
  { pollMs = SETTLE_POLL_MS, limitMs = SETTLE_LIMIT_MS }: { pollMs?: number; limitMs?: number } = {},
): Promise<void> {
  const deadline = Date.now() + limitMs;
  for (;;) {
    try {
      const status = await getAutoCodeStatus(frameworkId);
      if (!status.ending) return;
    } catch {
      return;
    }
    if (Date.now() + pollMs > deadline) return;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
}
