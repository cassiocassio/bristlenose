/**
 * The keyline lab's "shipped" spec IS the shipped CSS.
 *
 * Colour-lab rule: retune in the lab, then change both. If someone edits the
 * tentative keyline in `atoms/badge.css` or `molecules/threshold-review.css`
 * without moving `SHIPPED` (or the reverse), the lab would open on values that
 * never shipped, and "Back to shipped" would lie. This reads both files and
 * compares every declaration `ruleEdits(SHIPPED)` sets with what the file says.
 */

import { describe, expect, it } from "vitest";

import badgeCss from "../../../../bristlenose/theme/atoms/badge.css?raw";
import reviewCss from "../../../../bristlenose/theme/molecules/threshold-review.css?raw";
import { FILES, SHIPPED, dropInCss, isShipped, maskUrl, parseSpec, ruleEdits, type Edit } from "./spec";

const SOURCES: Record<string, string> = { [FILES.badge]: badgeCss, [FILES.review]: reviewCss };

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
  it("SHIPPED is what the two theme files say, declaration for declaration", () => {
    const edits = ruleEdits(SHIPPED);
    expect(edits.some((e) => e.kind === "new")).toBe(false); // the shipped keyline is a plain border
    for (const e of edits) {
      const css = SOURCES[e.file];
      if (e.kind === "style") {
        const body = ruleBody(css, e.selector);
        for (const [prop, value] of Object.entries(normDecls(e.decls))) {
          expect({ rule: e.selector, prop, value: body[prop] }).toEqual({ rule: e.selector, prop, value });
        }
      } else if (e.kind === "keyframes") {
        const frames = keyframes(css, e.name);
        for (const [key, decls] of e.frames) expect(frames[key]).toEqual(normDecls(decls));
      }
    }
  });

  it("names every rule it edits in the file it claims", () => {
    const named = ruleEdits(SHIPPED).map((e: Edit) => (e.kind === "keyframes" ? `@keyframes ${e.name}` : e.selector));
    expect(named).toEqual([
      "@keyframes bn-proposed-pulse",
      "@keyframes bn-proposed-breathe",
      ".badge-proposed",
      ".badge-proposed:hover",
      ".threshold-zone-counter--tentative",
      ".badge.threshold-tag-tentative",
    ]);
  });

  it("a linked surface follows the tentative tag; an unlinked one keeps its own line", () => {
    const quoteLine = { ...SHIPPED.quote.line, technique: "dotted" as const };
    const spec = { ...SHIPPED, quote: { ...SHIPPED.quote, line: quoteLine } };
    const border = (s: typeof spec, sel: string) => {
      const e = ruleEdits(s).find((x) => x.kind === "style" && x.selector === sel);
      return e?.kind === "style" ? e.decls.border : undefined;
    };
    expect(border(spec, ".badge.threshold-tag-tentative")).toBe("1px dotted currentColor");
    const unlinked = { ...spec, row: { linked: false, line: SHIPPED.row.line } };
    expect(border(unlinked, ".badge.threshold-tag-tentative")).toBe("1px dashed currentColor");
  });

  it("a drawn dash keeps the 1px edge and adds a masked ::before, with ink and dash from the handles", () => {
    const line = { ...SHIPPED.quote.line, technique: "drawn" as const, dash: 3, gap: 2, ink: "text" as const, strength: 80 };
    const edits = ruleEdits({ ...SHIPPED, quote: { ...SHIPPED.quote, line } });
    const base = edits.find((e) => e.kind === "style" && e.selector === ".badge-proposed");
    expect(base?.kind === "style" && base.decls.border).toBe("1px solid transparent");
    const before = edits.find((e) => e.kind === "new" && e.selector === ".badge-proposed::before");
    expect(before?.kind === "new" && before.decls["background-color"]).toBe("color-mix(in srgb, var(--bn-colour-text) 80%, transparent)");
    expect(maskUrl(line, { radius: 3 })).toContain("stroke-dasharray='3 2'");
    expect(maskUrl(line, { radius: 3 })).not.toMatch(/[<>#]/); // escaped for a url()
    // The row and counter are linked by default, so they get position:relative for their ::before.
    const row = edits.find((e) => e.kind === "style" && e.selector === ".badge.threshold-tag-tentative");
    expect(row?.kind === "style" && row.decls.position).toBe("relative");
  });

  it("the pulse keyframe keeps the shipped calc shape, whatever the numbers", () => {
    const spec = { ...SHIPPED, quote: { ...SHIPPED.quote, rest: 0.85, trough: 0.7, peak: 0.95 } };
    const kf = ruleEdits(spec).find((e) => e.kind === "keyframes" && e.name === "bn-proposed-breathe");
    expect(kf?.kind === "keyframes" && kf.frames.map(([, d]) => d.opacity)).toEqual([
      "calc(0.85 - 0.15 * var(--bn-proposed-pulse-depth))",
      "calc(0.85 + 0.1 * var(--bn-proposed-pulse-depth))",
      "calc(0.85 - 0.15 * var(--bn-proposed-pulse-depth))",
    ]);
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

  it("prints CSS for both files", () => {
    const css = dropInCss(SHIPPED);
    expect(css).toContain("atoms/badge.css");
    expect(css).toContain("molecules/threshold-review.css");
    expect(css).toContain("border: 1px dashed currentColor;");
    expect(css).toContain("@keyframes bn-proposed-breathe {");
  });
});
