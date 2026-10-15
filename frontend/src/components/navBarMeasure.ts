/**
 * The browser tab bar measuring its own one-row width, for the fit cascade
 * (SidebarStore "Fit to width"): how wide its tabs and its icon tabs are in
 * the normal spacing and in the condensed one, whichever spacing they are in
 * now.
 *
 * Each item's content width is its border box less its own padding, which does
 * not depend on the spacing; the padding each spacing adds is read from two
 * empty probes of the same class (one inside `.bn-global-nav--condensed`), so
 * the CSS stays the only place the paddings are written. Measured at once, in
 * whatever font is showing, and again when an item resizes (the web font
 * arriving, a zoom, a language). Waiting for the web font was tried first and
 * was worse: the first paint showed every panel and then closed one, on every
 * fresh load. The fallback is close to Inter's width, so measuring early can
 * only move something when the window sits within a few pixels of a step.
 */

import { useEffect, useLayoutEffect, type RefObject } from "react";
import type { BarWidths } from "../contexts/SidebarStore";

export function useBarMeasure(
  root: RefObject<HTMLElement | null>,
  itemSelector: string,
  probeFull: RefObject<HTMLElement | null>,
  probeCondensed: RefObject<HTMLElement | null>,
  report: (widths: BarWidths | null) => void,
  key: string,
  clearOnUnmount = true,
): void {
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    let live = true;
    const items = () => [...el.querySelectorAll<HTMLElement>(itemSelector)];
    const measure = () => {
      if (!live) return;
      const list = items();
      if (list.length === 0) {
        report(null);
        return;
      }
      let content = 0;
      for (const item of list) {
        const cs = getComputedStyle(item);
        content += item.getBoundingClientRect().width - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
      }
      const full = probeFull.current?.getBoundingClientRect().width ?? 0;
      const condensed = probeCondensed.current?.getBoundingClientRect().width ?? 0;
      report({ full: content + list.length * full, condensed: content + list.length * condensed });
    };
    measure();
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
    fonts?.ready?.then(measure).catch(() => {});
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    const observe = () => {
      if (!ro) return;
      ro.disconnect();
      for (const item of items()) ro.observe(item);
    };
    observe();
    // An item can arrive or leave on its own (the refresh tab appears once a
    // run exists): re-observe and re-measure when the children change.
    const mo = typeof MutationObserver !== "undefined"
      ? new MutationObserver(() => { observe(); measure(); })
      : null;
    mo?.observe(el, { childList: true, subtree: true });
    return () => {
      live = false;
      ro?.disconnect();
      mo?.disconnect();
    };
    // `key` names what changes the item list (labels, which tools exist).
  }, [root, itemSelector, probeFull, probeCondensed, report, key]);

  // Nothing to fit once the bar is gone (the embedded app never mounts it, and
  // tests unmount it). Not for the icon tabs: they unmount from the bar and
  // mount in the header when they move up, and this cleanup runs after the new
  // copy has measured, so clearing would forget them and move them straight back.
  useEffect(() => () => {
    if (clearOnUnmount) report(null);
  }, [report, clearOnUnmount]);
}
