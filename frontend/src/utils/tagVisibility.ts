/**
 * Tag visibility — the hide/disable split (design-codebook-state-model.md §5).
 *
 * Two controls hide a codebook's badges, with OPPOSITE reachability:
 *
 *   • HIDE (the eye toggle, per group) — a tactical, in-the-moment declutter.
 *     Badges are hidden, but the tags stay reachable: they still autocomplete
 *     (shown with a closed-eye hint) and auto-unhide when picked.
 *
 *   • DISABLE (the lens switch, per framework) — "off means off". Badges are
 *     hidden AND the tags drop out of autocomplete entirely (suppressed), so the
 *     "invisible add" (accept a suggestion the filter then hides) can't happen.
 *
 * Same badge-hide, opposite reachability. This module is the single place that
 * keeps the two apart — conflating them is exactly the bug §5 warns about.
 */

export interface TagGroupMeta {
  /** Group name this tag belongs to. */
  group: string;
  /** Framework id, or null/undefined for the hand-made floor codebook. */
  frameworkId?: string | null;
}

export interface TagVisibility {
  /** Group names whose badges are hidden on quote cards — eye-hidden groups ∪
   *  every group belonging to a disabled framework. Drives the card badge filter. */
  hiddenGroups: Set<string>;
  /** Lowercased tag names that still autocomplete but show a closed-eye hint —
   *  eye-hidden groups only. Drives TagInput's decorate + auto-unhide. */
  decoratedTagNames: Set<string>;
  /** Lowercased tag names dropped from autocomplete entirely — disabled
   *  frameworks. Merged into TagInput's exclude. */
  suppressedTagNames: Set<string>;
}

/**
 * Partition every known tag into hidden-badge / decorated-suggestion /
 * suppressed-suggestion buckets. Disable takes precedence over hide: a group that
 * is both eye-hidden and belongs to a disabled framework is suppressed (off means
 * off), not merely decorated.
 */
export function deriveTagVisibility(
  tagGroupMap: Record<string, TagGroupMeta>,
  hiddenTagGroups: Set<string>,
  disabledFrameworks: Set<string>,
): TagVisibility {
  // All eye-hidden groups hide their badges regardless of whether any of their
  // tags appear in tagGroupMap.
  const hiddenGroups = new Set(hiddenTagGroups);
  const decoratedTagNames = new Set<string>();
  const suppressedTagNames = new Set<string>();

  for (const [tagNameLower, info] of Object.entries(tagGroupMap)) {
    const disabled =
      info.frameworkId != null && disabledFrameworks.has(info.frameworkId);
    if (disabled) {
      // Disable → off means off: badge hidden AND suggestion suppressed.
      hiddenGroups.add(info.group);
      suppressedTagNames.add(tagNameLower);
    } else if (hiddenTagGroups.has(info.group)) {
      // Hide → still reachable: decorate the suggestion, keep it suggestable.
      decoratedTagNames.add(tagNameLower);
    }
  }

  return { hiddenGroups, decoratedTagNames, suppressedTagNames };
}
