/**
 * The Discussion lens's one data seam.
 *
 * Today it returns the SYNTHETIC fixture the Phase 1a spike produced (an
 * invented study — no participant data), so the lens can be built and
 * reviewed before the pipeline stage exists. Phase 3 replaces the body with a
 * fetch of the project's discussion record; nothing else in the lens changes.
 */

import type { DiscussionData } from "./types";

export async function loadDiscussion(): Promise<DiscussionData> {
  const mod = await import("./fixture.json");
  const data = (mod.default ?? mod) as unknown as DiscussionData;
  if (data.version !== 1) {
    throw new Error(`Discussion data version ${String(data.version)} is not supported`);
  }
  return data;
}
