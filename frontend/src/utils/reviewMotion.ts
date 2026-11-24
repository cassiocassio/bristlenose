/**
 * The AutoCode review's rows moving to where a decision puts them (owner, 24 Nov 2026).
 *
 * A tick or a cross moves its row to another zone once the server has answered. The row
 * glides from where it was to where it lands, and the rows around both places glide to
 * close the gap and open the space (FLIP: measure, let React draw the new state, then
 * play each element from its old place to its new one). A zone that is closed has its
 * rows in the DOM but clipped to nothing, so a row landing there cannot be seen arrive: a
 * copy of it flies towards the zone's header instead and fades, and the header's count
 * rolls.
 *
 * Imperative and contained, like utils/tapestryMotion.ts: React draws the final state and
 * this only animates what is already drawn. Nothing runs under the system's reduced
 * motion, or without the Web Animations API (jsdom).
 *
 * The markup's part: `data-flip="<key>"` on everything that may move, `data-flip-zone` on
 * each zone, `data-flip-landing` on its header, `data-flip-collapsed` on a zone body that
 * is closed or still opening. The scroll container passed in must be positioned (the copy
 * is placed in it). While an element glides it carries `data-flip-moving` (its buttons
 * rest: a click must not land on a row passing under the pointer) and the row that was
 * decided also `data-flip-lifted`; both are attributes, not classes, because React owns
 * the row's className.
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

/** Done gliding, however it ended. */
function settle(el: HTMLElement): void {
  delete el.dataset.flipMoving;
  delete el.dataset.flipLifted;
}

/** A copy that is only a picture: nothing in it can be found, measured or focused. */
function inert(copy: HTMLElement): HTMLElement {
  for (const el of [copy, ...copy.querySelectorAll<HTMLElement>("*")]) {
    el.removeAttribute("id");
    el.removeAttribute("data-testid");
    el.removeAttribute("data-flip");
    delete el.dataset.flipMoving;
    delete el.dataset.flipLifted;
    if (el.matches("button, a, [tabindex]")) el.setAttribute("tabindex", "-1");
  }
  copy.classList.remove("report-row--deciding");
  return copy;
}

/** Where everything is now, and a copy of each row about to move. Null when motion is off. */
export function captureLayout(root: HTMLElement | null, moving: string[]): Layout | null {
  if (!root || !motionAllowed(root)) return null;
  const rects = new Map<string, DOMRect>();
  root.querySelectorAll("[data-flip]").forEach((el) => {
    // A row in a closed zone is never played, so it is not measured either. Mid-glide,
    // the rect is where the element is on screen, so a second move carries on from there.
    if (!collapsed(el)) rects.set(key(el), el.getBoundingClientRect());
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
  const els = Array.from(root.querySelectorAll<HTMLElement>("[data-flip]"));

  // Stop whatever is still gliding from an earlier move, so every read below is of the
  // laid-out place, not a frame of an old animation.
  for (const el of els) {
    settle(el);
    el.getAnimations().forEach((a) => a.cancel());
  }

  // Read everything, then write: one layout, not one per row.
  const box = root.getBoundingClientRect();
  const moves: { el: HTMLElement; dx: number; dy: number }[] = [];
  for (const el of els) {
    const was = from.rects.get(key(el));
    if (!was || collapsed(el)) continue;
    const now = el.getBoundingClientRect();
    const dx = was.left - now.left;
    const dy = was.top - now.top;
    if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) moves.push({ el, dx, dy });
  }
  const flights: { ghost: Ghost; to: DOMRect | null }[] = [];
  for (const [k, ghost] of from.ghosts) {
    const el = root.querySelector<HTMLElement>(`[data-flip="${k}"]`);
    if (el && !collapsed(el)) continue; // it glides, below
    const landing = el?.closest("[data-flip-zone]")?.querySelector("[data-flip-landing]");
    flights.push({ ghost, to: landing?.getBoundingClientRect() ?? null });
  }

  for (const { el, dx, dy } of moves) {
    el.dataset.flipMoving = "";
    // The row that was decided is lifted, so it reads as one line crossing the others.
    if (from.ghosts.has(key(el))) el.dataset.flipLifted = "";
    const a = el.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
      { duration: GLIDE_MS, easing: SETTLE },
    );
    a.onfinish = () => settle(el);
    a.oncancel = () => settle(el);
  }
  for (const { ghost, to } of flights) fly(root, box, ghost, to);
}

/**
 * A copy of the row flies from where it was towards the closed zone's header, and fades.
 * A header outside the scroll's view is aimed at the view's edge on its side, so the copy
 * leaves that way rather than crossing the zones in between; it passes under a stuck
 * header (threshold-review.css), never over it.
 */
function fly(root: HTMLElement, box: DOMRect, ghost: Ghost, to: DOMRect | null): void {
  const layer = document.createElement("div");
  layer.className = "bn-flip-ghost";
  layer.setAttribute("aria-hidden", "true");
  layer.style.top = `${ghost.rect.top - box.top + root.scrollTop}px`;
  layer.style.left = `${ghost.rect.left - box.left + root.scrollLeft}px`;
  layer.style.width = `${ghost.rect.width}px`;
  let copy = inert(ghost.copy);
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
  layer.appendChild(copy);
  root.appendChild(layer);
  const from = ghost.rect.top + ghost.rect.height / 2;
  const target = to ? to.top + to.height / 2 : from;
  const dy = Math.min(Math.max(target, box.top), box.bottom) - from;
  const a = layer.animate(
    [
      { transform: "none", opacity: 1 },
      { transform: `translateY(${dy}px) scale(0.97)`, opacity: 0 },
    ],
    { duration: GLIDE_MS, easing: SETTLE, fill: "both" },
  );
  a.onfinish = () => layer.remove();
  a.oncancel = () => layer.remove();
}
