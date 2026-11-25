/**
 * Foundations / Colour — every colour token the loaded theme declares, each
 * swatch filled by the token and labelled with the colour the browser
 * resolved for this document's palette and appearance. Nothing is listed by
 * hand: the groups are prefixes, the members come from the stylesheets.
 */

import { useLayoutEffect, useRef, useState } from "react";

import type { SpecimenMeta, SpecimenStory } from "../csf";
import { tokensWithPrefix } from "../themeTokens";

export default {
  title: "Foundations/Colour",
  description:
    "Palette tokens (overridden per palette by data-color-theme) and the analytical tokens in tokens.css (sentiment, codebook sets, coverage), resolved for this document.",
  caveat:
    "Light and dark resolve per document (color-scheme is set on :root), so compare them with the Appearance control or the matrix, not side by side on one page.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Palette", "Selection", "Sentiment", "Codebook", "Coverage"] as const;

function Swatch({ token }: { token: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [resolved, setResolved] = useState("");
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setResolved(getComputedStyle(el).backgroundColor);
    read();
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, { attributes: true });
    return () => mo.disconnect();
  }, [token]);
  return (
    <div className="bn-sg-swatch" data-testid={`bn-sg-colour-${token}`}>
      <span ref={ref} className="bn-sg-chip" style={{ background: `var(${token})` }} />
      <code className="bn-sg-token">{token}</code>
      <span className="bn-sg-measure">{resolved}</span>
    </div>
  );
}

function Swatches({ tokens }: { tokens: string[] }) {
  return (
    <div className="bn-sg-swatches">
      {tokens.map((t) => (
        <Swatch key={t} token={t} />
      ))}
    </div>
  );
}

/** Colour-valued tokens only: a hue anchor or a chroma number is not a colour. */
const NOT_A_COLOUR = /-(h|chroma|l-min|l-max|duration|width)$/;

export const Palette: SpecimenStory = {
  name: "Palette (chrome and surfaces)",
  render: () => <Swatches tokens={tokensWithPrefix("--bn-colour-", NOT_A_COLOUR)} />,
};

export const Selection: SpecimenStory = {
  name: "Selection, focus and glow",
  render: () => (
    <Swatches
      tokens={[
        ...tokensWithPrefix("--bn-selection-"),
        ...tokensWithPrefix("--bn-focus-ring"),
        ...tokensWithPrefix("--bn-glow-"),
      ]}
    />
  ),
};

export const Sentiment: SpecimenStory = {
  name: "Sentiment",
  render: () => <Swatches tokens={tokensWithPrefix("--bn-sentiment-", NOT_A_COLOUR)} />,
};

export const Codebook: SpecimenStory = {
  name: "Codebook sets, group tints and bars",
  render: () => (
    <Swatches
      tokens={["--bn-ux-", "--bn-emo-", "--bn-task-", "--bn-trust-", "--bn-opp-", "--bn-custom-", "--bn-group-", "--bn-bar-", "--bn-set-"].flatMap(
        (p) => tokensWithPrefix(p, NOT_A_COLOUR),
      )}
    />
  ),
};

export const Coverage: SpecimenStory = {
  name: "Coverage",
  render: () => <Swatches tokens={tokensWithPrefix("--bn-coverage-", NOT_A_COLOUR)} />,
};
