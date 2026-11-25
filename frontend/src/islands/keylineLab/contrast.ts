/**
 * Contrast of a drawn keyline, from the colours the browser resolved.
 *
 * A colour is read back through a 1×1 canvas, so whatever the theme writes
 * (oklch, light-dark(), color-mix()) arrives as the sRGB the screen shows. The
 * tag is a group with an opacity, so a keyline pixel is the line over the fill,
 * then that layer at the tag's opacity over what the tag sits on.
 *
 * A figure here assumes a pixel fully covered by the line. A 0.5px line on a 1x
 * screen, or a dash's antialiased end, is lighter than that on screen: the
 * figure is the formula's, the screenshot is the renderer's
 * (frontend/gotchas.md, "a contrast figure for a blurred edge").
 */

export type Rgba = [number, number, number, number]; // 0–255, alpha 0–1

let ctx: CanvasRenderingContext2D | null | undefined;

function canvas(): CanvasRenderingContext2D | null {
  if (ctx !== undefined) return ctx;
  try {
    const c = document.createElement("canvas");
    c.width = c.height = 1;
    ctx = c.getContext("2d", { willReadFrequently: true });
  } catch {
    ctx = null;
  }
  return ctx;
}

/** A computed CSS colour as sRGB, or null where there is no canvas (jsdom). */
export function resolve(css: string): Rgba | null {
  const g = canvas();
  if (!g) return null;
  g.clearRect(0, 0, 1, 1);
  g.fillStyle = "rgba(0, 0, 0, 0)";
  g.fillStyle = css;
  g.fillRect(0, 0, 1, 1);
  const [r, gr, b, a] = g.getImageData(0, 0, 1, 1).data;
  return [r, gr, b, a / 255];
}

/** `top` over `bottom` with `top`'s alpha times `alpha`; the result is opaque if `bottom` is. */
export function over(top: Rgba, bottom: Rgba, alpha = 1): Rgba {
  const a = top[3] * alpha;
  const outA = a + bottom[3] * (1 - a);
  if (outA === 0) return [0, 0, 0, 0];
  const ch = (i: number) => (top[i] * a + bottom[i] * bottom[3] * (1 - a)) / outA;
  return [ch(0), ch(1), ch(2), outA];
}

function luminance([r, g, b]: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG contrast ratio of two opaque colours. */
export function ratio(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

export interface Reading {
  /** The keyline against the tag's own fill (what the dash gaps and the inside edge show). */
  onFill: number;
  /** The keyline against what the tag sits on (the outside edge). */
  onPage: number;
}

/** How a keyline reads at a given tag opacity, from the resolved colours. */
export function reading(line: Rgba, fill: Rgba, page: Rgba, opacity: number): Reading {
  const linePx = over(over(line, fill), page, opacity);
  const fillPx = over(fill, page, opacity);
  return { onFill: ratio(linePx, fillPx), onPage: ratio(linePx, page) };
}

/** The first opaque background at or above `el` (the page, if nothing paints). */
export function surround(el: Element): Rgba | null {
  for (let n: Element | null = el.parentElement; n; n = n.parentElement) {
    const c = resolve(getComputedStyle(n).backgroundColor);
    if (c && c[3] > 0.99) return c;
  }
  return resolve(getComputedStyle(document.body).backgroundColor);
}
