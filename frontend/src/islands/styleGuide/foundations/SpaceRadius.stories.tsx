/**
 * Foundations / Space and radius — the spacing and corner tokens, each drawn
 * at the size the loaded theme gives it.
 */

import type { SpecimenMeta, SpecimenStory } from "../csf";
import { tokensWithPrefix } from "../themeTokens";

export default {
  title: "Foundations/Space and radius",
  description: "Spacing and corner-radius tokens from tokens.css.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Space", "Radius"] as const;

export const Space: SpecimenStory = {
  name: "Space",
  render: () => (
    <div>
      {tokensWithPrefix("--bn-space-").map((t) => (
        <div key={t} className="bn-sg-row" data-testid={`bn-sg-space-${t}`}>
          <code className="bn-sg-token">{t}</code>
          <span className="bn-sg-bar" style={{ width: `var(${t})` }} />
        </div>
      ))}
    </div>
  ),
};

export const Radius: SpecimenStory = {
  name: "Radius",
  render: () => (
    <div className="bn-sg-swatches">
      {tokensWithPrefix("--bn-radius-").map((t) => (
        <div key={t} className="bn-sg-swatch" data-testid={`bn-sg-radius-${t}`}>
          <span className="bn-sg-corner" style={{ borderRadius: `var(${t})` }} />
          <code className="bn-sg-token">{t}</code>
        </div>
      ))}
    </div>
  ),
};
