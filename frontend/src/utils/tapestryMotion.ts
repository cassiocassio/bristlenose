/**
 * The session timeline's open and close, in the Sessions grid (owner, 17 Oct 2026; mockup and
 * every number: docs/mockups/sessions-timeline-strip.html).
 *
 * Opening, from a click on the row's strip or its disclosure:
 *  - the slice unfolds (height, 220 ms);
 *  - the strip's clips spring into the participant lane, at the lane's height and the open scale
 *    (320 ms, ~8% overshoot), lifting from the strip's 60% to full strength on the way;
 *  - everything else lands left to right, a quick domino: 60 ms + its place across the visible
 *    width × 150 ms, 260 ms each on the same spring — flags drop, team clips grow from their left
 *    edge, sentiment bars grow from the axis, theme chips rise, labels and ticks fade;
 *  - each word of the row's journey chain flies to the flag of its first visit, taking the flag's
 *    size and ink (380 ms, on that flag's beat); a return visit's flag has no word to catch and
 *    fades in 120 ms later. The chain's arrows fade where they stand (CSS).
 * Closing flies the words home, fades the timeline and folds the slice.
 *
 * Imperative and contained: the components render their final state, and this only animates
 * what is already drawn. Nothing runs under reduced motion, or where the Web Animations API is
 * missing (jsdom), so the open and closed states never depend on it.
 */

const SPRING = "cubic-bezier(0.34, 1.56, 0.64, 1)";
const SETTLE = "cubic-bezier(0.2, 0.8, 0.2, 1)";
const WORD = "cubic-bezier(0.3, 1.2, 0.5, 1)";

export function motionAllowed(el: Element | null | undefined): boolean {
  if (!el || typeof (el as HTMLElement).animate !== "function") return false;
  // The house switch-off as well as the system's (docs/design-motion.md, principle 5).
  if (el.closest(".bn-no-animations")) return false;
  try {
    return !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return true;
  }
}

/** A layer over the page for things in flight, clipped to the slice's visible width only. */
function flightLayer(clip: DOMRect): HTMLDivElement {
  const layer = document.createElement("div");
  layer.className = "bn-tp-flight";
  layer.setAttribute("aria-hidden", "true");
  Object.assign(layer.style, {
    left: `${clip.left + window.scrollX}px`,
    top: "0px",
    width: `${clip.width}px`,
    height: `${document.documentElement.scrollHeight}px`,
  });
  document.body.appendChild(layer);
  return layer;
}

function bbox(el: SVGGraphicsElement): DOMRect | null {
  try {
    return el.getBBox();
  } catch {
    return null;
  }
}

function setBox(el: Element, origin: string) {
  const st = (el as SVGElement).style;
  st.transformBox = "fill-box";
  st.transformOrigin = origin;
}

function clearBox(el: Element) {
  const st = (el as SVGElement).style;
  st.transformBox = "";
  st.transformOrigin = "";
}

interface FlightPair {
  label: HTMLElement;
  flag: SVGGElement;
}

/** The chain's words and their first-visit flags, matched by name: the chain is in the
 *  report's section order and the flags in time order, so the words cross where a user's
 *  path left the report's order. A word whose section has no flag (its quotes are hidden)
 *  stays out of the flight and fades with the arrows. */
function pairs(row: Element, svg: SVGSVGElement): FlightPair[] {
  const flags = new Map<string, SVGGElement>();
  svg.querySelectorAll<SVGGElement>(".bn-tp-flag[data-first]").forEach((g) => {
    if (g.dataset.label) flags.set(g.dataset.label, g);
  });
  const out: FlightPair[] = [];
  row.querySelectorAll<HTMLElement>(".bn-session-journey .bn-journey-label").forEach((label) => {
    // The grid's narrow rungs drop the chain (display: none): no box, nothing to fly from.
    const r = label.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const flag = flags.get(label.textContent ?? "");
    if (flag) out.push({ label, flag });
  });
  return out;
}

/** Where a flag's label sits on the page, from the svg's box and the label's own geometry, so a
 *  flag mid-drop (a transform) does not move the landing spot. */
function flagSpot(svg: SVGSVGElement, flag: SVGGElement): { rect: DOMRect; text: SVGTextElement | null } | null {
  const text = flag.querySelector("text");
  const shape = text ?? flag.querySelector("path");
  const bb = shape ? bbox(shape) : null;
  if (!bb) return null;
  const sb = svg.getBoundingClientRect();
  return { rect: new DOMRect(sb.left + bb.x, sb.top + bb.y, bb.width, bb.height), text };
}

function flyWords(row: Element, svg: SVGSVGElement, clip: DOMRect, dir: "out" | "in", delayOf: (flag: SVGGElement) => number): number {
  const list = pairs(row, svg);
  if (list.length === 0) return 0;
  const layer = flightLayer(clip);
  // A flag label's resolved ink and size (a token would arrive unresolved).
  const sample = svg.querySelector(".bn-tp-flag text");
  const ink = sample ? getComputedStyle(sample).fill : getComputedStyle(svg).color;
  const flagPx = sample ? parseFloat(getComputedStyle(sample).fontSize) || 13 : 13;
  let last = 0;
  for (const { label, flag } of list) {
    const spot = flagSpot(svg, flag);
    if (!spot) continue;
    const lr = label.getBoundingClientRect();
    const lcs = getComputedStyle(label);
    const px = parseFloat(lcs.fontSize) || 13;
    const word = document.createElement("span");
    word.className = "bn-tp-flight-word";
    word.textContent = label.textContent;
    Object.assign(word.style, {
      font: lcs.font,
      lineHeight: "1",
      color: lcs.color,
      left: `${lr.left - clip.left}px`,
      top: `${lr.top + lr.height / 2 + window.scrollY - px / 2}px`,
      height: `${px}px`,
    });
    layer.appendChild(word);
    // Left edges and vertical centres meet; the size changes by the font ratio. A flag too narrow
    // for its label (none drawn) takes the word at a smaller size, fading.
    const dx = spot.rect.left - lr.left;
    const dy = spot.rect.top + spot.rect.height / 2 - (lr.top + lr.height / 2);
    const atLabel = { transform: "translate(0px, 0px) scale(1)", color: lcs.color, opacity: 1 };
    const atFlag = {
      transform: `translate(${dx}px, ${dy}px) scale(${spot.text ? flagPx / px : 0.6})`,
      color: ink,
      opacity: spot.text ? 1 : 0,
    };
    const delay = dir === "out" ? delayOf(flag) : 20;
    last = Math.max(last, delay + 380);
    if (spot.text) spot.text.style.opacity = "0";
    const a = word.animate(dir === "out" ? [atLabel, atFlag] : [atFlag, atLabel],
      { duration: 380, delay, easing: WORD, fill: "both" });
    a.onfinish = () => {
      if (dir === "out" && spot.text) {
        const t = spot.text;
        t.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 80, easing: "ease" });
        t.style.opacity = "";
      }
      if (dir === "in") label.style.visibility = "visible";
      word.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 80, fill: "both" }).onfinish = () => word.remove();
    };
  }
  window.setTimeout(() => layer.remove(), last + 200);
  return last;
}

/** The strip's clips spring into the participant lane. */
function morphLane(preview: SVGSVGElement, svg: SVGSVGElement, scroll: HTMLElement) {
  const clips = preview.querySelector(".bn-tp-pv-clips");
  const track = preview.querySelector(".bn-tp-pv-track");
  const pptY = Number(svg.dataset.pptY);
  const pptH = Number(svg.dataset.pptH);
  const sPerPx = Number(svg.dataset.sPerPx);
  const pvPxPerSec = Number(preview.dataset.pxPerSec);
  const x0 = Number(preview.dataset.x0);
  if (!clips || !track || !(pptH > 0) || !(sPerPx > 0) || !(pvPxPerSec > 0)) return;
  const pr = track.getBoundingClientRect();
  const sr = svg.getBoundingClientRect();
  const clip = scroll.getBoundingClientRect();
  const layer = flightLayer(clip);
  const ghost = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  ghost.setAttribute("width", preview.getAttribute("width") ?? "0");
  ghost.setAttribute("height", String(pr.height));
  ghost.style.position = "absolute";
  ghost.style.overflow = "visible";
  ghost.style.left = `${pr.left - x0 - clip.left}px`;
  ghost.style.top = `${pr.top + window.scrollY}px`;
  const g = clips.cloneNode(true) as SVGGElement;
  g.removeAttribute("class");
  ghost.appendChild(g);
  layer.appendChild(ghost);
  // From the strip to the lane: x scales about the track's start by the ratio of the scales,
  // y by the ratio of the heights; the lane's start is the svg's gutter, wherever it scrolled.
  const kx = (1 / sPerPx) / pvPxPerSec;
  const ky = pptH / pr.height;
  const dx = sr.left + x0 - pr.left;
  const dy = sr.top + pptY - pr.top;
  g.style.transformOrigin = `${x0}px 0px`;
  const from = "translate(0px, 0px) scale(1, 1)";
  const to = `translate(${dx}px, ${dy}px) scale(${kx}, ${ky})`;
  const wrap = svg.closest(".bn-tp-wrap");
  wrap?.classList.add("bn-tp-landing");
  g.animate([{ transform: from }, { transform: to }], { duration: 320, easing: SPRING, fill: "both" });
  g.animate([{ opacity: 0.6 }, { opacity: 1 }], { duration: 200, easing: "ease-out", fill: "both" });
  window.setTimeout(() => {
    wrap?.classList.remove("bn-tp-landing");
    // The lane's names were not carried (they would squash); they fade in along it.
    svg.querySelectorAll(".bn-tp-clip-label.on-ppt").forEach((t, i) =>
      t.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: Math.min(150, i * 6), fill: "backwards" }));
    ghost.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 90, fill: "both" }).onfinish = () => layer.remove();
  }, 320);
}

interface Land {
  row: HTMLElement;
  slice: HTMLElement;
  svg: SVGSVGElement;
  preview: SVGSVGElement | null;
}

/** The open animation. Returns at once; everything it starts cleans up after itself. */
export function landTapestry({ row, slice, svg, preview }: Land): void {
  if (!motionAllowed(slice)) return;
  const scroll = svg.closest<HTMLElement>(".bn-tapestry-scroll") ?? slice;
  const view = scroll.getBoundingClientRect();
  const gutter = Number(preview?.dataset.x0) || 82;
  const delayAt = (x: number) =>
    Math.round(60 + Math.max(0, Math.min(1, (x - scroll.scrollLeft - gutter) / Math.max(1, view.width - gutter))) * 150);
  const xOf = (el: Element) => bbox(el as SVGGraphicsElement)?.x ?? 0;

  // The slice unfolds; rows below move down with it.
  const h = slice.getBoundingClientRect().height;
  const mb = getComputedStyle(slice).marginBottom;
  slice.style.overflow = "hidden";
  slice.animate([{ height: "0px", marginBottom: "0px" }, { height: `${h}px`, marginBottom: mb }],
    { duration: 220, easing: SETTLE }).onfinish = () => { slice.style.overflow = ""; };

  if (preview) morphLane(preview, svg, scroll);

  const land = (el: Element, keyframes: Keyframe[], delay: number, origin: string, easing = SPRING, duration = 260) => {
    setBox(el, origin);
    // Leave nothing behind on nodes React owns: the box and origin go when the mark has landed.
    el.animate(keyframes, { duration, delay, easing, fill: "backwards" }).onfinish = () => clearBox(el);
  };
  const fade: Keyframe[] = [{ opacity: 0 }, { opacity: 1 }];
  svg.querySelectorAll(".bn-tp-lane").forEach((el) => land(el, fade, 0, "0 0", "ease-out"));
  svg.querySelectorAll(".bn-tp-track, .bn-tp-axis, .bn-tp-strip-team").forEach((el) => land(el, fade, 20, "0 0", "ease-out"));
  svg.querySelectorAll(".bn-tp-flag").forEach((el) => {
    const first = (el as SVGGElement).dataset.first !== undefined;
    const d = delayAt(xOf(el));
    if (first) land(el, [{ opacity: 0, transform: "translateY(-7px)" }, { opacity: 1, transform: "none" }], d, "0 0");
    else land(el, fade, d + 120, "0 0", "ease-out");
  });
  svg.querySelectorAll(".bn-tp-clip-team, .bn-tp-clip-edge.team").forEach((el) =>
    land(el, [{ opacity: 0, transform: "scaleX(0.15)" }, { opacity: 1, transform: "none" }], delayAt(xOf(el)), "0 50%"));
  svg.querySelectorAll(".bn-tp-clip-label.on-team").forEach((el) => land(el, fade, delayAt(xOf(el)) + 60, "0 0", "ease-out"));
  const axis = svg.querySelector(".bn-tp-axis");
  const axisY = axis ? Number(axis.getAttribute("y1")) : 0;
  svg.querySelectorAll(".bn-tp-bar").forEach((el) => {
    const d = delayAt(xOf(el));
    const b = bbox(el as SVGGraphicsElement);
    if (el.tagName === "circle" || el.classList.contains("bn-tp-unrated") || !b) {
      land(el, [{ opacity: 0, transform: "scale(0)" }, { opacity: 1, transform: "none" }], d, "50% 50%");
    } else {
      const up = b.y + b.height <= axisY + 0.5;
      land(el, [{ opacity: 0, transform: "scaleY(0)" }, { opacity: 1, transform: "none" }], d, up ? "50% 100%" : "50% 0");
    }
  });
  svg.querySelectorAll(".bn-tp-theme").forEach((el) =>
    land(el, [{ opacity: 0, transform: "translateY(5px)" }, { opacity: 1, transform: "none" }], delayAt(xOf(el)), "0 50%"));
  svg.querySelectorAll(".bn-tp-tick").forEach((el) => land(el, fade, delayAt(xOf(el)), "0 0", "ease-out"));

  flyWords(row, svg, view, "out", (flag) => delayAt(xOf(flag)));
}

/** The close animation; resolves when the slice may be taken away. At once without motion. */
export function foldTapestry({ row, slice, svg }: Omit<Land, "preview">): Promise<void> {
  if (!motionAllowed(slice)) return Promise.resolve();
  const scroll = svg.closest<HTMLElement>(".bn-tapestry-scroll") ?? slice;
  const back = flyWords(row, svg, scroll.getBoundingClientRect(), "in", () => 20);
  // The arrows come back as the words land.
  window.setTimeout(() => row.querySelectorAll<HTMLElement>(".bn-session-journey .bn-journey-sep")
    .forEach((s) => { s.style.opacity = "1"; }), 180);
  svg.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 100, fill: "forwards" });
  const h = slice.getBoundingClientRect().height;
  const mb = getComputedStyle(slice).marginBottom;
  slice.style.overflow = "hidden";
  const fold = slice.animate([{ height: `${h}px`, marginBottom: mb }, { height: "0px", marginBottom: "0px" }],
    { duration: 220, delay: 100, easing: SETTLE, fill: "forwards" });
  return new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      resolve();
      // Hand the chain back to the stylesheet once the row has re-rendered closed; clearing it
      // first would hide the words for a frame under the open row's rule.
      requestAnimationFrame(() => requestAnimationFrame(() =>
        row.querySelectorAll<HTMLElement>(".bn-session-journey .bn-journey-label, .bn-session-journey .bn-journey-sep")
          .forEach((el) => { el.style.visibility = ""; el.style.opacity = ""; })));
    };
    let pending = 2;
    const step = () => { pending -= 1; if (pending === 0) done(); };
    fold.onfinish = step;
    window.setTimeout(step, back + 60);
    // A slice taken away mid-fold may never finish its animation: never leave the row stuck.
    window.setTimeout(done, Math.max(back, 320) + 400);
  });
}
