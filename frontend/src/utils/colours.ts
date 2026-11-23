/**
 * Shared colour helpers — mirror COLOUR_SETS from codebook.js.
 *
 * Extracted so every surface that renders a codebook colour resolves it from
 * one place. Deliberately not a consumer list: the previous one named three
 * files, one of which (`CodebookPanel`) was deleted in 0.29.0 while the comment
 * went on claiming it. `grep -rn "utils/colours" frontend/src` is the answer
 * that cannot go stale.
 */

export const COLOUR_SETS: Record<
  string,
  { slots: number; groupBg: string; barVar: string; bgVar: string }
> = {
  ux:        { slots: 5, groupBg: "--bn-group-ux",        barVar: "--bn-bar-ux",        bgVar: "--bn-ux-" },
  emo:       { slots: 6, groupBg: "--bn-group-emo",       barVar: "--bn-bar-emo",       bgVar: "--bn-emo-" },
  task:      { slots: 5, groupBg: "--bn-group-task",      barVar: "--bn-bar-task",      bgVar: "--bn-task-" },
  trust:     { slots: 5, groupBg: "--bn-group-trust",     barVar: "--bn-bar-trust",     bgVar: "--bn-trust-" },
  opp:       { slots: 5, groupBg: "--bn-group-opp",       barVar: "--bn-bar-opp",       bgVar: "--bn-opp-" },
  sentiment: { slots: 7, groupBg: "--bn-group-sentiment", barVar: "--bn-bar-sentiment", bgVar: "--bn-sentiment-" },
};

export function getGroupBg(colourSet: string): string {
  const set = COLOUR_SETS[colourSet];
  return set ? `var(${set.groupBg})` : "var(--bn-group-none)";
}

export function getBarColour(colourSet: string): string {
  const set = COLOUR_SETS[colourSet];
  return set ? `var(${set.barVar})` : "var(--bn-bar-none)";
}

/**
 * A tag's bar colour. Every codebook's bars take their group's one colour; a
 * sentiment's bar takes its own (`--bn-sentiment-<name>`), as the Sessions grid's
 * sparkline, the tapestry and the transcripts draw it. Owner, 23 Nov 2026: those
 * colours read at a glance as who was grumpy and how the study leans, and the tag
 * sidebar and the Codebook lens were the odd ones out. Keyed by name, not slot, so
 * a reordered codebook keeps frustration orange; an unknown name falls back to the
 * group colour.
 */
export function getTagBarColour(colourSet: string, tagName: string): string {
  if (colourSet === "sentiment") {
    const name = tagName.toLowerCase().replace(/[^a-z-]/g, "");
    return `var(--bn-sentiment-${name}, ${getBarColour(colourSet)})`;
  }
  return getBarColour(colourSet);
}

export function getTagBg(colourSet: string, index: number): string {
  const set = COLOUR_SETS[colourSet];
  if (!set) return "var(--bn-custom-bg)";
  return `var(${set.bgVar}${(index % set.slots) + 1}-bg)`;
}
