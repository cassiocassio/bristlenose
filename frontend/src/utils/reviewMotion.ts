/**
 * The AutoCode review's rows moving to where a decision puts them (owner, 24 Nov 2026).
 *
 * A tick or a cross moves its row to another zone. The row glides from where it was to
 * where it lands, and the rows around both places glide to close the gap and open the
 * space (FLIP: measure, let React draw the new state, then play each element from its
 * old place to its new one). A zone that is closed has its rows in the DOM but clipped
 * to nothing, so a row landing there cannot be seen arrive: a copy of it flies into the
 * zone's header instead and fades, and the header's count rolls.
 *
 * Imperative and contained, like utils/tapestryMotion.ts: React draws the final state and
 * this only animates what is already drawn. Nothing runs under reduced motion, with the
 * house animations off, or without the Web Animations API (jsdom).
 *
 * The markup's part: `data-flip="<key>"` on everything that may move, `data-flip-zone` on
 * each zone, `data-flip-landing` on its header, `data-flip-collapsed` on a closed zone's
 * body. The scroll container passed in must be positioned (the copy is placed in it).
 */

import { motionAllowed } from "./tapestryMotion";

const SETTLE = "cubic-bezier(0.2, 0.8, 0.2, 1)";
const GLIDE_MS = 260;

interface Ghost {
  copy: HTMLElement;
  rect: DOMRect;
  cellWidths: number[];
  tableClass: string;
}

export interface Layout {
  rects: Map<string, DOMRect>;
  ghosts: Map<string, Ghost>;
}

const key = (el: Element) => (el as HTMLElement).dataset.flip ?? "";
const collapsed = (el: Element) => el.closest("[data-flip-collapsed]") !== null;

/** Where everything is now, and a copy of each row about to move. Null when motion is off. */
export function captureLayout(root: HTMLElement | null, moving: string[]): Layout | null {
  if (!root || !motionAllowed(root)) return null;
  const rects = new Map<string, DOMRect>();
  root.querySelectorAll("[data-flip]").forEach((el) => {
    // Mid-glide, this is where it is on screen, so a second click carries on from there.
    rects.set(key(el), el.getBoundingClientRect());
  });
  const ghosts = new Map<string, Ghost>();
  for (const k of moving) {
    const el = root.querySelector<HTMLElement>(`[data-flip="${k}"]`);
    if (!el || collapsed(el)) continue;
    ghosts.set(k, {
      copy: el.cloneNode(true) as HTMLElement,
      rect: el.getBoundingClientRect(),
      cellWidths: Array.from(el.children, (c) => c.getBoundingClientRect().width),
      tableClass: el.closest("table")?.className ?? "",
    });
  }
  return { rects, ghosts };
}

/** Play each element from where `from` saw it to where it is now. */
export function playLayout(root: HTMLElement | null, from: Layout): void {
  if (!root) return;
  root.querySelectorAll<HTMLElement>("[data-flip]").forEach((el) => {
    const was = from.rects.get(key(el));
    if (!was || collapsed(el)) return;
    el.getAnimations().forEach((a) => a.cancel());
    const now = el.getBoundingClientRect();
    const dx = was.left - now.left;
    const dy = was.top - now.top;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
    const moving = from.ghosts.has(key(el));
    // The row that moved is lifted, so it reads as one line crossing the others.
    if (moving) el.classList.add("bn-flip-lifted");
    el.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
      { duration: GLIDE_MS, easing: SETTLE },
    ).onfinish = () => el.classList.remove("bn-flip-lifted");
  });
  for (const [k, ghost] of from.ghosts) {
    const el = root.querySelector<HTMLElement>(`[data-flip="${k}"]`);
    if (el && !collapsed(el)) continue; // it glided, above
    const landing = el?.closest("[data-flip-zone]")?.querySelector("[data-flip-landing]");
    fly(root, ghost, landing?.getBoundingClientRect() ?? null);
  }
}

/** A copy of the row flies from where it was into the closed zone's header, and fades. */
function fly(root: HTMLElement, ghost: Ghost, to: DOMRect | null): void {
  const box = root.getBoundingClientRect();
  const layer = document.createElement("div");
  layer.className = "bn-flip-ghost";
  layer.setAttribute("aria-hidden", "true");
  layer.style.top = `${ghost.rect.top - box.top + root.scrollTop}px`;
  layer.style.left = `${ghost.rect.left - box.left + root.scrollLeft}px`;
  layer.style.width = `${ghost.rect.width}px`;
  let copy: HTMLElement = ghost.copy;
  if (copy.tagName === "TR") {
    // A row out of its table keeps its columns only if they are given back.
    Array.from(copy.children).forEach((cell, i) => {
      (cell as HTMLElement).style.width = `${ghost.cellWidths[i] ?? 0}px`;
    });
    const table = document.createElement("table");
    table.className = ghost.tableClass;
    table.style.tableLayout = "fixed";
    const body = document.createElement("tbody");
    body.appendChild(copy);
    table.appendChild(body);
    copy = table;
  }
  copy.querySelectorAll("button, a, [tabindex]").forEach((c) => c.setAttribute("tabindex", "-1"));
  layer.appendChild(copy);
  root.appendChild(layer);
  const dy = to ? to.top + to.height / 2 - (ghost.rect.top + ghost.rect.height / 2) : 0;
  layer.animate(
    [
      { transform: "none", opacity: 1 },
      { transform: `translateY(${dy}px) scale(0.97)`, opacity: 0 },
    ],
    { duration: GLIDE_MS, easing: SETTLE, fill: "both" },
  ).onfinish = () => layer.remove();
}
