// What the researcher reads when a build ends. Pure, so it is tested without a page.

import type { BoardPlan } from "./layout";

const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Never "built" for a partial board. */
export function summary(plan: BoardPlan, built: number): string {
  const parts = [
    built === plan.expectedQuotes
      ? `Board built: ${n(built, "quote", "quotes")}.`
      : `Built ${built} of ${n(plan.expectedQuotes, "quote", "quotes")} — some are missing.`,
  ];
  if (plan.droppedLinks) {
    parts.push(`${n(plan.droppedLinks, "clip link wasn't a web address and was", "clip links weren't web addresses and were")} left out.`);
  }
  if (plan.unknownColours) {
    parts.push(`${n(plan.unknownColours, "sticky had a colour Miro doesn't have and is", "stickies had a colour Miro doesn't have and are")} yellow.`);
  }
  return parts.join(" ");
}

/** The panel's line when a build fails part-way: how far it got, and Miro's own words. */
export function failure(plan: BoardPlan, built: number, reason: string): string {
  return `Stopped after ${built} of ${n(plan.expectedQuotes, "quote", "quotes")}. What was drawn stays on the board. Miro said: ${reason}`;
}
