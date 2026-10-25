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
  /** Group names the researcher has eye-hidden (stored by name). A disabled
   *  framework's groups are NOT added here: two codebooks can have a group of the
   *  same name ("Discoverability" in Norman and CLI UX), and switching one off must
   *  not hide the other's badges. Use `isBadgeHidden` for the card badge filter. */
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
      // Disable → off means off: badge hidden AND suggestion suppressed. Both are
      // keyed by TAG name (unique across codebooks), never by the group's name.
      suppressedTagNames.add(tagNameLower);
    } else if (hiddenTagGroups.has(info.group)) {
      // Hide → still reachable: decorate the suggestion, keep it suggestable.
      decoratedTagNames.add(tagNameLower);
    }
  }

  return { hiddenGroups, decoratedTagNames, suppressedTagNames };
}

/**
 * Whether a tag badge is hidden on a quote card: its group is eye-hidden, or its
 * tag belongs to a disabled framework (`suppressedTagNames`, keyed by tag name).
 */
export function isBadgeHidden(
  vis: TagVisibility,
  tagName: string,
  groupName: string,
): boolean {
  return vis.hiddenGroups.has(groupName) || vis.suppressedTagNames.has(tagName.toLowerCase());
}
