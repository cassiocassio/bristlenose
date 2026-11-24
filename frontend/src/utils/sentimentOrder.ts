/**
 * The order sentiments are listed in on screen, declared once (D15): the Sessions grid's
 * sparkline draws its bars in it, and the tag sidebar and the Codebook lens list the
 * sentiment group's rows in it. Negative to positive, with surprise in the middle.
 *
 * On screen only, by name (D36): `sentiment.yaml` keeps its own order, a tag's colour slot
 * travels with the tag (`colour_index`), and Signals' columns are not touched.
 */
export const SENTIMENT_ORDER = [
  "frustration",
  "confusion",
  "doubt",
  "surprise",
  "confidence",
  "delight",
  "satisfaction",
] as const;

/**
 * A group's tags in the order they are listed. A sentiment group (colour set `sentiment`)
 * takes SENTIMENT_ORDER, and a tag it does not name keeps its place after the listed ones;
 * every other group is returned as it came, the same array.
 */
export function inSentimentOrder<T extends { name: string }>(
  colourSet: string,
  tags: readonly T[],
): readonly T[] {
  if (colourSet !== "sentiment") return tags;
  const rank = (tag: T) => {
    const i = (SENTIMENT_ORDER as readonly string[]).indexOf(tag.name.toLowerCase());
    return i === -1 ? SENTIMENT_ORDER.length : i;
  };
  return [...tags].sort((a, b) => rank(a) - rank(b));
}
