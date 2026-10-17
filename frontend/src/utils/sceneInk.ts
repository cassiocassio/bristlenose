/**
 * The label ink on scene-coloured clips in the session timeline.
 *
 * One ink for the whole screen, not one per clip (owner, 17 Oct 2026): per-clip
 * contrast made the names alternate dark and white along a lane, which read as
 * noise. Scene colours are normalised (utils/scene_colour.py), so the ink that wins
 * on most clips is rarely far off on the rest; on the Talismanic study dark won on
 * 281 of 282 clips, its weakest at 4.1:1.
 */

const DARK = "#1a1a1a";
const WHITE = "#fff";

/** WCAG relative luminance of an `#rrggbb` colour. */
export function relLuminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const lin = (c: number) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
}

const prefersWhite = (hex: string) => {
  const l = relLuminance(hex);
  return 1.05 / (l + 0.05) > (l + 0.05) / (relLuminance(DARK) + 0.05);
};

/** The ink with the higher WCAG contrast on more of these colours; dark on a tie or none. */
export function screenInk(colours: Iterable<string>): string {
  let white = 0;
  let dark = 0;
  for (const c of colours) {
    if (prefersWhite(c)) white += 1;
    else dark += 1;
  }
  return white > dark ? WHITE : DARK;
}
