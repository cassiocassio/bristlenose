/**
 * Shared colour helpers — mirror COLOUR_SETS from codebook.js.
 *
 * Extracted so QuoteCard, AutoCodeReportModal, and CodebookPanel
 * can all resolve codebook colours without duplication.
 */

export const COLOUR_SETS: Record<
  string,
  { slots: number; groupBg: string; barVar: string; bgVar: string }
> = {
  ux:    { slots: 5, groupBg: "--bn-group-ux",    barVar: "--bn-bar-ux",    bgVar: "--bn-ux-" },
  emo:   { slots: 6, groupBg: "--bn-group-emo",   barVar: "--bn-bar-emo",   bgVar: "--bn-emo-" },
  task:  { slots: 5, groupBg: "--bn-group-task",   barVar: "--bn-bar-task",  bgVar: "--bn-task-" },
  trust: { slots: 5, groupBg: "--bn-group-trust",  barVar: "--bn-bar-trust", bgVar: "--bn-trust-" },
  opp:   { slots: 5, groupBg: "--bn-group-opp",    barVar: "--bn-bar-opp",   bgVar: "--bn-opp-" },
};

export function getGroupBg(colourSet: string): string {
  const set = COLOUR_SETS[colourSet];
  return set ? `var(${set.groupBg})` : "var(--bn-group-none)";
}

export function getBarColour(colourSet: string): string {
  const set = COLOUR_SETS[colourSet];
  return set ? `var(${set.barVar})` : "var(--bn-bar-none)";
}

export function getTagBg(colourSet: string, index: number): string {
  const set = COLOUR_SETS[colourSet];
  if (!set) return "var(--bn-custom-bg)";
  return `var(${set.bgVar}${(index % set.slots) + 1}-bg)`;
}
