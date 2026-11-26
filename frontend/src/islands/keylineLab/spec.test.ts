/**
 * The keyline lab's "shipped" spec IS the shipped CSS.
 *
 * Colour-lab rule: retune in the lab, then change both. If someone edits the
 * tentative tokens in `tokens.css` (or the hover in `atoms/badge.css`) without
 * moving `SHIPPED` (or the reverse), the lab would open on values that never
 * shipped, and "Back to shipped" would lie. This reads the files and compares
 * every value `ruleEdits(SHIPPED)` sets with what the file says, and checks the
 * three surfaces draw the tokens rather than a copy of them.
 */

import { describe, expect, it } from "vitest";

import badgeCss from "../../../../bristlenose/theme/atoms/badge.css?raw";
import reviewCss from "../../../../bristlenose/theme/molecules/threshold-review.css?raw";
import tokensCss from "../../../../bristlenose/theme/tokens.css?raw";
import { CONSUMERS, FILES, SHIPPED, TOKENS, dropInCss, isShipped, maskUrl, parseSpec, ruleEdits, type Edit } from "./spec";

const SOURCES: Record<string, string> = { [FILES.tokens]: tokensCss, [FILES.badge]: badgeCss, [FILES.review]: reviewCss };

/** Comparable form: numbers as numbers ("0.50" is "0.5"), whitespace collapsed, no `!important` spacing. */
function norm(v: string): string {
  return v
    .replace(/\s+/g, " ")
    .replace(/\s*!important/, " !important")
    .replace(/\d*\.?\d+/g, (n) => String(Number(n)))
    .trim();
}

/** The declarations of the first top-level rule in `css` whose selector is exactly `selector`. */
function ruleBody(css: string, selector: string): Record<string, string> {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = new RegExp(`(?:^|\\n)${esc}\\s*\\{([^}]*)\\}`).exec(css);
  if (!m) throw new Error(`no rule ${selector}`);
  return declsOf(m[1]);
}

function declsOf(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of body.replace(/\/\*[\s\S]*?\*\//g, "").split(";")) {
    const i = part.indexOf(":");
    if (i > 0) out[part.slice(0, i).trim()] = norm(part.slice(i + 1));
  }
  return out;
}

/** Every value `css` declares for the custom property `name`. */
function tokenValues(css: string, name: string): string[] {
  return [...css.matchAll(new RegExp(`(?:^|[;{\\s])${name}\\s*:\\s*([^;]+);`, "g"))].map((m) => norm(m[1]));
}

function keyframes(css: string, name: string): Record<string, Record<string, string>> {
  const start = css.indexOf(`@keyframes ${name} {`);
  if (start < 0) throw new Error(`no @keyframes ${name}`);
  const body = css.slice(start, css.indexOf("\n}", start));
  const out: Record<string, Record<string, string>> = {};
  for (const m of body.matchAll(/(\d+%)\s*\{([^}]*)\}/g)) out[m[1]] = declsOf(m[2]);
  return out;
}

const normDecls = (d: Record<string, string>) => Object.fromEntries(Object.entries(d).map(([k, v]) => [k, norm(v)]));

describe("keyline lab spec", () => {
  it("SHIPPED is what the theme files say, value for value", () => {
    const edits = ruleEdits(SHIPPED);
    expect(edits.some((e) => e.kind === "new")).toBe(false); // the shipped keyline is a plain border
    for (const e of edits) {
      const css = SOURCES[e.file];
      if (e.kind === "token") {
        expect({ token: e.name, values: tokenValues(css, e.name) }).toEqual({ token: e.name, values: [norm(e.value)] });
      } else if (e.kind === "style") {
        const body = ruleBody(css, e.selector);
        for (const [prop, value] of Object.entries(normDecls(e.decls))) {
          expect({ rule: e.selector, prop, value: body[prop] }).toEqual({ rule: e.selector, prop, value });
        }
      }
    }
  });

  it("the three surfaces and both pulses draw the tokens, and keep no copy of their values", () => {
    for (const c of CONSUMERS) {
      const body = ruleBody(SOURCES[c.file], c.selector);
      for (const [prop, value] of Object.entries(c.decls)) expect({ rule: c.selector, prop, value: body[prop] }).toEqual({ rule: c.selector, prop, value });
    }
    const pulse = keyframes(badgeCss, "bn-proposed-pulse");
    expect([pulse["0%"].opacity, pulse["50%"].opacity, pulse["100%"].opacity]).toEqual([
      `var(${TOKENS.pulseLow})`,
      `var(${TOKENS.pulseHigh})`,
      `var(${TOKENS.pulseLow})`,
    ]);
    const breathe = keyframes(badgeCss, "bn-proposed-breathe");
    for (const key of ["0%", "50%", "100%"]) {
      expect(breathe[key].opacity).toContain(`var(${TOKENS.opacity})`);
      expect(breathe[key].opacity).toContain(key === "50%" ? `var(${TOKENS.pulseHigh})` : `var(${TOKENS.pulseLow})`);
      expect(breathe[key].opacity).toContain("var(--bn-proposed-pulse-depth)");
    }
    // Each token is declared once, in tokens.css, and nowhere else in the two consumers.
    for (const name of Object.values(TOKENS)) {
      expect(tokenValues(tokensCss, name)).toHaveLength(1);
      expect(tokenValues(badgeCss + reviewCss, name)).toEqual([]);
    }
  });

  it("names every token and rule it edits, in file order", () => {
    const named = ruleEdits(SHIPPED).map((e: Edit) => (e.kind === "token" ? e.name : e.selector));
    expect(named).toEqual([...Object.values(TOKENS), ".badge-proposed:hover"]);
  });

  it("a linked surface follows the tokens; an unlinked one declares its own", () => {
    const quoteLine = { ...SHIPPED.quote.line, technique: "dashed" as const };
    const spec = { ...SHIPPED, quote: { ...SHIPPED.quote, line: quoteLine } };
    const keyline = ruleEdits(spec).find((x) => x.kind === "token" && x.name === TOKENS.keyline);
    expect(keyline?.kind === "token" && keyline.value).toBe("1px dashed currentColor");
    const own = (s: typeof spec, sel: string) => {
      const e = ruleEdits(s).find((x) => x.kind === "style" && x.selector === sel);
      return e?.kind === "style" ? e.decls : undefined;
    };
    expect(own(spec, ".badge.threshold-tag-tentative")).toBeUndefined();
    const unlinked = { ...spec, row: { linked: false, line: SHIPPED.row.line } };
    expect(own(unlinked, ".badge.threshold-tag-tentative")).toEqual({ [TOKENS.keyline]: "1px dotted currentColor" });
    const counter = { ...spec, counter: { linked: false, line: quoteLine, trough: 0.6, peak: 0.9 } };
    expect(own(counter, ".threshold-zone-counter--tentative")).toEqual({
      [TOKENS.keyline]: "1px dashed currentColor",
      [TOKENS.pulseLow]: "0.6",
      [TOKENS.pulseHigh]: "0.9",
    });
  });

  it("a drawn dash keeps the 1px edge and adds a masked ::before, with ink and dash from the handles", () => {
    const line = { ...SHIPPED.quote.line, technique: "drawn" as const, dash: 3, gap: 2, ink: "text" as const, strength: 80 };
    const edits = ruleEdits({ ...SHIPPED, quote: { ...SHIPPED.quote, line } });
    const base = edits.find((e) => e.kind === "token" && e.name === TOKENS.keyline);
    expect(base?.kind === "token" && base.value).toBe("1px solid transparent");
    const before = edits.find((e) => e.kind === "new" && e.selector === ".badge-proposed::before");
    expect(before?.kind === "new" && before.decls["background-color"]).toBe("color-mix(in srgb, var(--bn-colour-text) 80%, transparent)");
    expect(maskUrl(line, { radius: 3 })).toContain("stroke-dasharray='3 2'");
    expect(maskUrl(line, { radius: 3 })).not.toMatch(/[<>#]/); // escaped for a url()
    // The row and counter are linked by default, so they get position:relative for their ::before.
    const row = edits.find((e) => e.kind === "style" && e.selector === ".badge.threshold-tag-tentative");
    expect(row?.kind === "style" && row.decls.position).toBe("relative");
  });

  it("opacity and pulse handles are the three opacity tokens", () => {
    const spec = { ...SHIPPED, quote: { ...SHIPPED.quote, rest: 0.85, trough: 0.7, peak: 0.95 } };
    const values = Object.fromEntries(ruleEdits(spec).flatMap((e) => (e.kind === "token" ? [[e.name, e.value]] : [])));
    expect(values).toMatchObject({ [TOKENS.opacity]: "0.85", [TOKENS.pulseLow]: "0.7", [TOKENS.pulseHigh]: "0.95" });
  });

  it("reads a URL spec defensively and round-trips one", () => {
    expect(parseSpec(null)).toEqual(SHIPPED);
    expect(parseSpec("not json")).toEqual(SHIPPED);
    expect(parseSpec(JSON.stringify({ quote: { rest: 7, line: { technique: "zigzag", width: -1 } } }))).toEqual({
      ...SHIPPED,
      quote: { ...SHIPPED.quote, rest: 1, line: { ...SHIPPED.quote.line, width: 0.25 } },
    });
    const custom = { ...SHIPPED, counter: { ...SHIPPED.counter, linked: false, trough: 0.6 } };
    expect(parseSpec(JSON.stringify(custom))).toEqual(custom);
    expect(isShipped(SHIPPED)).toBe(true);
    expect(isShipped(custom)).toBe(false);
  });

  it("prints CSS for the files it touches", () => {
    const css = dropInCss(SHIPPED);
    expect(css).toContain("tokens.css");
    expect(css).toContain(":root {");
    expect(css).toContain("--bn-tentative-keyline: 1px dotted currentColor;");
    expect(css).toContain("atoms/badge.css");
    expect(css).toContain(".badge-proposed:hover {");
  });
});
