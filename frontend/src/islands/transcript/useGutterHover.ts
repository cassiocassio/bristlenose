/**
 * The transcript's hover: what the pointer is on lights what it is paired with.
 * (docs/design-transcript-gutter.md, "Hover".)
 *
 * A quote's words, its gutter mark and its margin title are one thing: hovering any of them
 * marks the margin entry hot (mark blue, title underlined) and draws a 0.5px ink keyline round
 * the quote's words. The paragraph's own lift to white is CSS (`:hover` on the row).
 *
 * The keyline is one block per paragraph the quote crosses: each line box is padded, adjacent
 * lines meet halfway, every line runs the paragraph's full measure except where the first line
 * starts and the last line ends — so a quote is a rectangle with a notch at each end.
 */
import { useEffect, type RefObject } from "react";

const PAD_X = 4;
const PAD_Y = 2;

const esc = (s: string) =>
  typeof CSS !== "undefined" && typeof CSS.escape === "function" ? CSS.escape(s) : s.replace(/["\\]/g, "\\$&");

/** The text a target names: `q:<dom_id>` → that quote's words. */
function targetElements(root: HTMLElement, target: string): HTMLElement[] {
  if (target.startsWith("q:")) {
    const id = esc(target.slice(2));
    return Array.from(root.querySelectorAll<HTMLElement>(`.transcript-body [data-q="${id}"]`));
  }
  if (target.startsWith("p:")) {
    const at = esc(target.slice(2));
    return Array.from(root.querySelectorAll<HTMLElement>(`.transcript-body .segment-body[data-position="${at}"]`));
  }
  return [];
}

interface Line { l: number; r: number; t: number; b: number }

/** An SVG path round `els` (all in one paragraph), relative to `origin`. */
export function keylinePath(els: HTMLElement[], column: DOMRect, origin: DOMRect): string {
  const lines: Line[] = [];
  for (const el of els) {
    for (const r of Array.from(el.getClientRects())) {
      if (r.width < 1 || r.height < 0) continue;
      const line = lines.find((x) => Math.abs(x.t - r.top) < 4);
      if (line) {
        line.l = Math.min(line.l, r.left); line.r = Math.max(line.r, r.right); line.b = Math.max(line.b, r.bottom);
      } else {
        lines.push({ l: r.left, r: r.right, t: r.top, b: r.bottom });
      }
    }
  }
  if (lines.length === 0) return "";
  lines.sort((a, b) => a.t - b.t);
  const L = lines.map((x) => ({
    l: x.l - origin.left - PAD_X, r: x.r - origin.left + PAD_X,
    t: x.t - origin.top - PAD_Y, b: x.b - origin.top + PAD_Y,
  }));
  for (let i = 0; i < L.length - 1; i++) {
    const m = (L[i].b + L[i + 1].t) / 2;
    L[i].b = m; L[i + 1].t = m;
  }
  const minL = column.left - origin.left - PAD_X;
  const maxR = Math.max(column.right - origin.left + PAD_X, ...L.map((x) => x.r));
  L.forEach((x, i) => {
    if (i > 0) x.l = minL;
    if (i < L.length - 1) x.r = maxR;
  });
  const px = (v: number) => Math.round(v * 2) / 2 + 0.25; // a .5px hairline on the device grid
  let d = `M${px(L[0].l)},${px(L[0].t)} H${px(L[0].r)}`;
  for (let i = 0; i < L.length; i++) {
    d += ` V${px(L[i].b)}`;
    if (i + 1 < L.length) d += ` H${px(L[i + 1].r)}`;
  }
  d += ` H${px(L[L.length - 1].l)}`;
  for (let i = L.length - 1; i > 0; i--) d += ` V${px(L[i].t)} H${px(L[i - 1].l)}`;
  return `${d} Z`;
}

/** What the pointer is on: the target it names, or null. */
function hoverTarget(el: Element | null): string | null {
  if (!el) return null;
  const words = el.closest<HTMLElement>(".transcript-body [data-q]");
  if (words?.dataset.q) return `q:${words.dataset.q}`;
  const handle = el.closest(".bn-gutter-mark, .bn-gutter-title, .bn-gutter-thumb, .bn-gutter-topic");
  const entry = handle?.closest<HTMLElement>(".bn-gutter-entry");
  return entry?.dataset.target ?? null;
}

export function useGutterHover(
  sheetRef: RefObject<HTMLElement | null>,
  /** Changes when the transcript (re)renders: the sheet does not exist while it loads. */
  ready: unknown,
): void {
  useEffect(() => {
    const sheet = sheetRef.current;
    if (!sheet) return;
    // The layer the keyline is drawn into, over the sheet. Made here rather than in JSX: it is a
    // drawing surface, not an icon, and the page draws no inline <svg> of its own
    // (tests/test_no_improvised_icons.py).
    const layer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    layer.setAttribute("class", "bn-keylines");
    layer.setAttribute("aria-hidden", "true");
    sheet.appendChild(layer);
    let current: string | null = null;

    const show = (target: string | null) => {
      if (target === current) return;
      current = target;
      sheet.querySelectorAll(".bn-gutter-entry.is-hot").forEach((e) => e.classList.remove("is-hot"));
      layer.replaceChildren();
      if (!target) return;
      const entries = sheet.querySelectorAll<HTMLElement>(`.bn-gutter-entry[data-target="${esc(target)}"]`);
      entries.forEach((e) => e.classList.add("is-hot"));
      const hidden = Array.from(entries).some((e) => e.hasAttribute("data-hidden"));
      // One block per paragraph the target crosses.
      const byParagraph = new Map<HTMLElement, HTMLElement[]>();
      for (const el of targetElements(sheet, target)) {
        const body = el.closest<HTMLElement>(".segment-body") ?? el;
        const list = byParagraph.get(body);
        if (list) list.push(el);
        else byParagraph.set(body, [el]);
      }
      const origin = sheet.getBoundingClientRect();
      for (const [body, els] of byParagraph) {
        const d = keylinePath(els, body.getBoundingClientRect(), origin);
        if (!d) continue;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        if (hidden) path.setAttribute("class", "is-hidden");
        layer.appendChild(path);
      }
    };
    const onOver = (e: MouseEvent) => show(hoverTarget(e.target as Element | null));
    const onLeave = () => show(null);
    sheet.addEventListener("mouseover", onOver);
    sheet.addEventListener("mouseleave", onLeave);
    return () => {
      sheet.removeEventListener("mouseover", onOver);
      sheet.removeEventListener("mouseleave", onLeave);
      show(null);
      layer.remove();
    };
  }, [sheetRef, ready]);
}
