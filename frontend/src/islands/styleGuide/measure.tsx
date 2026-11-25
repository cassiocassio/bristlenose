/**
 * What the browser drew, read back from the page: the style guide's answer to
 * "which value actually applies here?". A token's name says what was meant; a
 * computed style says what a reader sees (the tag specimen's `Measured` line
 * found quote-card tags at a 17.28px line height and every other context's at
 * 16.70px, which no source file says). Re-read whenever the `<html>` theme
 * attributes change, since the style guide changes them under the page.
 */

import { useLayoutEffect, useRef, useState, type RefObject } from "react";

export interface Measurement {
  size: string;
  lineHeight: string;
  weight: string;
  family: string;
  padding: string;
  background: string;
}

function read(el: Element): Measurement {
  const cs = getComputedStyle(el);
  return {
    size: cs.fontSize,
    lineHeight: cs.lineHeight,
    weight: cs.fontWeight,
    family: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(),
    padding: `${cs.paddingTop} ${cs.paddingRight} ${cs.paddingBottom} ${cs.paddingLeft}`,
    background: cs.backgroundColor,
  };
}

/** Measure the element a ref lands on, or (with `selector`) the first match inside it. */
export function useMeasured<T extends HTMLElement>(
  selector?: string,
  deps: unknown[] = [],
): [RefObject<T | null>, Measurement | null] {
  const ref = useRef<T>(null);
  const [m, setM] = useState<Measurement | null>(null);
  useLayoutEffect(() => {
    const host = ref.current;
    if (!host) return;
    const update = () => {
      const el = selector ? host.querySelector(selector) : host;
      setM(el ? read(el) : null);
    };
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true });
    // A theme change starts the element's own transitions (the quote card
    // fades its background over --bn-transition-slow), so a read at the
    // mutation is the first frame; read again when each transition lands.
    host.addEventListener("transitionend", update);
    return () => {
      mo.disconnect();
      host.removeEventListener("transitionend", update);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selector, ...deps]);
  return [ref, m];
}

function MeasuredLine({ host, selector }: { host: RefObject<HTMLElement | null>; selector: string }) {
  const [m, setM] = useState<Measurement | null>(null);
  useLayoutEffect(() => {
    const root = host.current;
    if (!root) return;
    const update = () => {
      const el = root.querySelector(selector);
      setM(el ? read(el) : null);
    };
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true });
    root.addEventListener("transitionend", update);
    return () => {
      mo.disconnect();
      root.removeEventListener("transitionend", update);
    };
  }, [host, selector]);
  return (
    <p className="bn-sg-measure bn-sg-measured" data-testid={`bn-sg-measured-${selector}`}>
      {selector}:{" "}
      {m
        ? `${m.size} / ${m.lineHeight} · ${m.weight} · ${m.family} · padding ${m.padding} · ${m.background}`
        : "none drawn"}
    </p>
  );
}

/** Captions under a specimen: what each selector's first match inside `children` was drawn at. */
export function Measured({ selectors, children }: { selectors: string[]; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div>
      <div ref={ref}>{children}</div>
      {selectors.map((s) => (
        <MeasuredLine key={s} host={ref} selector={s} />
      ))}
    </div>
  );
}
