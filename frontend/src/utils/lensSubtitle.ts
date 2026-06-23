/**
 * Per-lens window subtitle — the count line that follows the project title in
 * native chrome ("163 Quotes", "3 Codebooks · 47 Tags", "13 Signals").
 *
 * The SPA owns this because the counts are live (visible quotes change as you
 * hide; tags/signals change as you edit/dismiss) and, for Signals, computed
 * only here — never stored. One string drives both surfaces: the desktop
 * window subtitle (via the bridge) and the browser tab (`document.title`).
 * Sessions/Project are handled natively (Swift DB read), not here.
 */
import i18n from "../i18n";
import type { CodebookResponse } from "./types";

/** Interpunct separator (U+00B7) — the same one the native Sessions subtitle
 * uses, and what Mail uses. */
const SEP = " · ";

/** "163 Quotes" — the count of currently-visible quotes (hidden excluded). */
export function quotesSubtitle(visibleCount: number): string {
  return i18n.t("titlebar.quotes", { count: visibleCount });
}

/** "13 Signals" — the count of currently-shown signals (dismissed excluded). */
export function signalsSubtitle(count: number): string {
  return i18n.t("titlebar.signals", { count });
}

/**
 * Codebook + tag counts. A *codebook* is a framework (Garrett, Norman, …) or
 * the default user per-project codebook that holds custom + uncategorised tags;
 * each holds codegroups, which hold tags. We count distinct frameworks plus the
 * user codebook when it carries any tags. (Long-term, client/folder-scoped
 * codebooks extend this same count — hence the explicit accumulation rather
 * than a hardcoded "frameworks + 1".)
 */
export function codebookCounts(codebook: CodebookResponse): {
  codebooks: number;
  tags: number;
} {
  const frameworks = new Set<string>();
  let frameworkTags = 0;
  let userTags = 0;
  for (const group of codebook.groups) {
    if (group.framework_id) {
      frameworks.add(group.framework_id);
      frameworkTags += group.tags.length;
    } else {
      userTags += group.tags.length;
    }
  }
  userTags += codebook.ungrouped.length;
  const codebooks = frameworks.size + (userTags > 0 ? 1 : 0);
  return { codebooks, tags: frameworkTags + userTags };
}

/** "3 Codebooks · 47 Tags" — two interpunct-joined counts. */
export function codebookSubtitle(codebooks: number, tags: number): string {
  const left = i18n.t("titlebar.codebooks", { count: codebooks });
  const right = i18n.t("titlebar.tags", { count: tags });
  return `${left}${SEP}${right}`;
}
