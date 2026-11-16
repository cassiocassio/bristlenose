/**
 * "A, B, and C" in the reader's language. The SPA's one conjunction list.
 *
 * Intl.ListFormat knows each language's word for "and" and its separators;
 * a hand-joined `" and "` is English in every locale (BR-10). Bare `en` maps
 * to `en-US` so the serial comma stays ("A, B, and C"), as before.
 */
export function conjunctionList(items: string[], language: string): string {
  if (items.length <= 1) return items.join("");
  const lng = !language || language === "en" ? "en-US" : language;
  try {
    // Intl.ListFormat is ES2021; the project's lib is ES2020, so it is named by hand.
    const ListFormat = (Intl as unknown as { ListFormat: new (l: string, o: object) => { format(i: string[]): string } }).ListFormat;
    return new ListFormat(lng, { style: "long", type: "conjunction" }).format(items);
  } catch {
    return items.join(", ");
  }
}
