/**
 * Foundations / Type — the type ladder and weights, read from the loaded
 * theme CSS. Each sample is set by the token itself (`var(--bn-text-…)`), and
 * the numbers beside it are what the browser computed from that token, so a
 * web page shows the Inter ladder and the Mac app (or `?platform=desktop`)
 * shows the SF ladder from `tokens-desktop.css`, with no copy of either here.
 */

import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { SectionHeading } from "../../../components/SectionHeading";
import type { SpecimenMeta, SpecimenStory } from "../csf";
import { tokensWithPrefix } from "../themeTokens";

export default {
  title: "Foundations/Type",
  description:
    "The type tokens from tokens-typography.css (web, Inter) or tokens-desktop.css (Mac, SF), whichever this document resolves.",
  caveat:
    "Switch Platform to compare the two ladders, or open the matrix. SF Pro renders only on Apple platforms; elsewhere the desktop stack falls back to the system font.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Ladder", "Weights", "Headings"] as const;

const SAMPLE = "Researchers keep the report they own";

interface Measured {
  size: string;
  lineHeight: string;
  weight: string;
  family: string;
}

/** Computed values of the element the ref lands on, re-read when `deps` change. */
function useMeasured<T extends HTMLElement>(deps: unknown[]): [React.RefObject<T | null>, Measured | null] {
  const ref = useRef<T>(null);
  const [m, setM] = useState<Measured | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => {
      const cs = getComputedStyle(el);
      setM({
        size: cs.fontSize,
        lineHeight: cs.lineHeight,
        weight: cs.fontWeight,
        family: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(),
      });
    };
    read();
    // The theme attributes on <html> change under us when the controls move.
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, { attributes: true });
    return () => mo.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return [ref, m];
}

function Row({ token, style, children }: { token: string; style: CSSProperties; children: ReactNode }) {
  const [ref, m] = useMeasured<HTMLParagraphElement>([token]);
  return (
    <div className="bn-sg-row" data-testid={`bn-sg-type-${token}`}>
      <code className="bn-sg-token">{token}</code>
      <p ref={ref} style={{ margin: 0, ...style }}>
        {children}
      </p>
      <span className="bn-sg-measure">
        {m ? `${m.size} / ${m.lineHeight} · ${m.weight} · ${m.family}` : ""}
      </span>
    </div>
  );
}

/** A token's computed value in px (rem resolved against the root), for ordering. */
function tokenNumber(name: string): number {
  const root = document.documentElement;
  const raw = getComputedStyle(root).getPropertyValue(name).trim();
  const n = parseFloat(raw);
  if (Number.isNaN(n)) return 0;
  return raw.endsWith("rem") ? n * (parseFloat(getComputedStyle(root).fontSize) || 16) : n;
}

/** Smallest first, as a ladder reads; ties keep their name order. */
function byValue(names: string[]): string[] {
  return names
    .map((n) => ({ n, v: tokenNumber(n) }))
    .sort((a, b) => a.v - b.v || a.n.localeCompare(b.n))
    .map(({ n }) => n);
}

function sizeSteps(): string[] {
  return byValue(tokensWithPrefix("--bn-text-", /-lh$/));
}

export const Ladder: SpecimenStory = {
  name: "Size ladder",
  render: () => (
    <div>
      {sizeSteps().map((t) => (
        <Row
          key={t}
          token={t}
          style={{ fontFamily: "var(--bn-font-body)", fontSize: `var(${t})`, lineHeight: `var(${t}-lh)` }}
        >
          {SAMPLE}
        </Row>
      ))}
    </div>
  ),
};

export const Weights: SpecimenStory = {
  name: "Weights",
  render: () => (
    <div>
      {byValue(tokensWithPrefix("--bn-weight-")).map((t) => (
        <Row
          key={t}
          token={t}
          style={{
            fontFamily: t.includes("-mono") ? "var(--bn-font-mono)" : "var(--bn-font-body)",
            fontSize: "var(--bn-text-body)",
            fontWeight: `var(${t})`,
          }}
        >
          {SAMPLE}
        </Row>
      ))}
    </div>
  ),
};

export const Headings: SpecimenStory = {
  name: "Headings and body, as the report sets them",
  render: () => (
    <div>
      <SectionHeading>Section heading (SectionHeading)</SectionHeading>
      <h3>Subsection heading (h3)</h3>
      <p>
        Body copy in the report's own paragraph style. The participant said the checkout felt slow
        and that she abandoned the basket twice before finding the delivery options.
      </p>
    </div>
  ),
};
