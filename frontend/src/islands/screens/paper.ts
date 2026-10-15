/**
 * A screengrab's paper: the colour its page is printed on, and what a leader crossing it should be
 * drawn in (R3, `experiments/screens-lens/leader-styles.md` §7; the owner, 15 Oct 2026).
 *
 * Over the screengrab a leader is the accent with a soft halo in the paper's own colour: the halo
 * cannot be seen over plain page, and shows only where the line crosses ink. Which half of the
 * palette's light-dark() accent it uses follows the paper, not the board, because a white site on
 * a dark board is the common case and the board's accent half is the wrong one there.
 *
 * The paper is sampled once, when a still arrives (fetchStill), never during a render.
 */
import { Lru } from "./carousel";

export type Rgb = [number, number, number];

export interface PaperChoice {
  /** The halo's colour, a literal rgb(): inside a forced-scheme group a token would resolve against
   *  the paper's scheme and stop being a choice. */
  casing: string;
  /** Which half of the palette's light-dark() accent the line uses over this screengrab. */
  scheme: "light" | "dark";
  /** No accent half clears the bar against the paper itself, so the halo is white or near-black. */
  midtone: boolean;
}

/** The leader's contrast floor (WCAG 1.4.11). */
const MIN_RATIO = 3;
/** The blurred halo keeps about 82% of the paper beside the core, so a paper must clear the floor
 *  by that much to stand in for a hard casing (3 / 0.82). Without the blur the floor is the floor. */
const BLURRED_RATIO = 3.65;

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}
export function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}
export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
const css = ([r, g, b]: Rgb) => `rgb(${r}, ${g}, ${b})`;

/**
 * The accent half, and the halo, for a paper. The half with the better contrast against the paper
 * wins; if even that one misses the bar the paper is a midtone, and the halo becomes white or
 * #111111 — whichever of the four pairings reads best — with the scheme taken from the accent half
 * chosen, never from the paper.
 */
export function choosePaper(paper: Rgb, accents: { light: Rgb; dark: Rgb }, blurred = true): PaperChoice {
  const bar = blurred ? BLURRED_RATIO : MIN_RATIO;
  const halves = [["light", accents.light], ["dark", accents.dark]] as const;
  const [scheme, accent] = halves.reduce((a, b) => (contrast(b[1], paper) > contrast(a[1], paper) ? b : a));
  if (contrast(accent, paper) >= bar) return { casing: css(paper), scheme, midtone: false };
  const casings: Rgb[] = [[255, 255, 255], [17, 17, 17]];
  let best = { ratio: -1, scheme: scheme as "light" | "dark", casing: casings[0] };
  for (const [s, a] of halves) for (const c of casings) {
    const ratio = contrast(a, c);
    if (ratio > best.ratio) best = { ratio, scheme: s, casing: c };
  }
  return { casing: css(best.casing), scheme: best.scheme, midtone: true };
}

/** Parse a computed colour ("rgb(10, 132, 255)" or "rgba(…)"). */
export function parseRgb(s: string): Rgb | null {
  const m = s.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/);
  return m ? [Math.round(+m[1]), Math.round(+m[2]), Math.round(+m[3])] : null;
}

/** Both halves of the palette's accent, read from a probe under each forced scheme. */
export function readAccents(): { light: Rgb; dark: Rgb } | null {
  if (typeof document === "undefined") return null;
  const read = (scheme: string) => {
    const el = document.createElement("span");
    el.style.cssText = `position:absolute;visibility:hidden;color-scheme:${scheme};color:var(--bn-colour-accent)`;
    document.body.appendChild(el);
    const rgb = parseRgb(getComputedStyle(el).color);
    el.remove();
    return rgb;
  };
  const light = read("light"), dark = read("dark");
  return light && dark ? { light, dark } : null;
}

/**
 * The paper of a still: the commonest colour in thin full-resolution strips along its left, right
 * and bottom edges, inset 4px. Not the top, which after the crop may be a browser's tab bar; not a
 * downscale, which would alias ink into the paper. Null where there is no canvas (jsdom) or the
 * image will not decode.
 */
export async function samplePaper(src: string): Promise<Rgb | null> {
  if (typeof Image === "undefined" || typeof document === "undefined") return null;
  const img = new Image();
  if (typeof img.decode !== "function") return null;
  img.src = src;
  try {
    await img.decode();
  } catch {
    return null;
  }
  const w = img.naturalWidth, h = img.naturalHeight;
  if (w < 16 || h < 16) return null;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0);
  const top = Math.round(h * 0.12), inset = 4, strip = 2;
  const regions = [
    ctx.getImageData(inset, top, strip, h - top - inset),
    ctx.getImageData(w - inset - strip, top, strip, h - top - inset),
    ctx.getImageData(inset, h - inset - strip, w - 2 * inset, strip),
  ];
  // Commonest colour at 4 bits a channel, then the mean of the pixels in that bucket.
  const buckets = new Map<number, { n: number; r: number; g: number; b: number }>();
  for (const { data } of regions) {
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      const key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4);
      const e = buckets.get(key) ?? { n: 0, r: 0, g: 0, b: 0 };
      e.n++;
      e.r += r;
      e.g += g;
      e.b += b;
      buckets.set(key, e);
    }
  }
  let top1: { n: number; r: number; g: number; b: number } | null = null;
  for (const e of buckets.values()) if (!top1 || e.n > top1.n) top1 = e;
  // Alpha is forced to 1: a still is opaque, and a transparent edge reads as the paper it sits on.
  return top1 ? [Math.round(top1.r / top1.n), Math.round(top1.g / top1.n), Math.round(top1.b / top1.n)] : null;
}

/** Each board still's paper, by still URL, sized like the board's stills (24). */
export const papers = new Lru<Rgb>(24);
