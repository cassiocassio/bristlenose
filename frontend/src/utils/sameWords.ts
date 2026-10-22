/**
 * Whether two texts say the same words, however they are spaced.
 *
 * The report does not show spacing, so an edit that changes only spacing is no
 * edit, in either direction (decision #30, 22 Oct 2026): a quote, a section or
 * theme heading, a description. Not for names that are keys — a codebook tag or
 * group name is matched as typed, and fixing its spacing is a real change.
 */
export function sameWords(a: string, b: string): boolean {
  const spaced = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");
  return spaced(a) === spaced(b);
}
