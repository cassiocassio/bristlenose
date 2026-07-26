/**
 * codebookDot — the sidebar status-dot state for a codebook row.
 *
 * The dot echoes the framework enable/disable **switch** (blue on / grey off),
 * not a network-style traffic light: a codebook is binary on/off, and the
 * control beside it in CodebookPanel is the standard macOS switch. So:
 *
 *   on        → imported & enabled   → blue dot  (--bn-colour-accent)
 *   off       → imported & disabled  → grey dot  (--bn-colour-border-hover)
 *   available → not imported         → transparent (slot reserved so the text
 *                                       left-edges align with imported rows)
 *
 * The floor (the researcher's own project codebook) has no switch, so it gets
 * no dot at all — the caller renders a bare transparent slot for it directly,
 * never calling this helper. See design-codebook-library.md § "Sidebar row".
 *
 * @module codebookDot
 */

export type CodebookDotState = "on" | "off" | "available";

/**
 * Resolve a codebook row's dot state from its import + disabled status.
 *
 * @param imported            whether the codebook is imported into the project
 * @param frameworkId         the codebook's framework id (key in disabledFrameworks)
 * @param disabledFrameworks  the set of framework ids the researcher has switched off
 */
export function codebookDotState(
  imported: boolean,
  frameworkId: string,
  disabledFrameworks: Set<string>,
): CodebookDotState {
  if (!imported) return "available";
  return disabledFrameworks.has(frameworkId) ? "off" : "on";
}
