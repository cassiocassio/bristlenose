/**
 * Retune the shipped theme in place: find the rules the lab's edits name in the
 * loaded stylesheets (the theme CSS the app links), change their declarations
 * through the CSSOM, and put every one back on `restore()`.
 *
 * No copy of a selector or a rule body lives here. A rule the lab cannot find is
 * reported, not invented: if the theme renames `.badge-proposed`, the lab says so
 * on the page instead of quietly styling nothing.
 */

import type { Edit } from "./spec";

type Parent = CSSStyleSheet | CSSGroupingRule;

/** `CSSRule.KEYFRAMES_RULE`, written out: the constant is deprecated in the DOM typings. */
const KEYFRAMES_RULE = 7;

interface Found {
  styles: Map<string, CSSStyleRule[]>;
  keyframes: Map<string, CSSKeyframesRule[]>;
}

/** Selector text as engines serialise it varies (quotes, spaces): compare a normal form. */
export function normalSelector(s: string): string {
  return s.replace(/'/g, '"').replace(/\s+/g, " ").replace(/\s*([>+~,])\s*/g, "$1").trim();
}

function rulesOf(p: Parent): CSSRuleList | null {
  try {
    return p.cssRules;
  } catch {
    return null; // a cross-origin sheet: not ours to read
  }
}

function walk(p: Parent, found: Found): void {
  const list = rulesOf(p);
  if (!list) return;
  for (const rule of Array.from(list)) {
    if (rule instanceof CSSStyleRule) {
      const key = normalSelector(rule.selectorText);
      found.styles.set(key, [...(found.styles.get(key) ?? []), rule]);
    } else if (rule.type === KEYFRAMES_RULE) {
      // By type, not instanceof: jsdom's CSSOM has the rule but not the global constructor.
      const kf = rule as CSSKeyframesRule;
      found.keyframes.set(kf.name, [...(found.keyframes.get(kf.name) ?? []), kf]);
    } else if ("cssRules" in rule) {
      walk(rule as CSSGroupingRule, found);
    }
  }
}

function findAll(doc: Document): Found {
  const found: Found = { styles: new Map(), keyframes: new Map() };
  for (const sheet of Array.from(doc.styleSheets)) walk(sheet, found);
  return found;
}

function setDecls(style: CSSStyleDeclaration, decls: Record<string, string>): void {
  for (const [prop, raw] of Object.entries(decls)) {
    const important = /\s*!important\s*$/.test(raw);
    style.setProperty(prop, raw.replace(/\s*!important\s*$/, ""), important ? "important" : "");
  }
}

function keyText(k: CSSKeyframeRule): string {
  // Engines write "0%" or "from"; the theme writes percentages.
  return k.keyText.replace(/^from$/, "0%").replace(/^to$/, "100%");
}

export class ThemeRuleEditor {
  private saved = new Map<CSSStyleRule | CSSKeyframeRule, string>();
  private inserted: Array<{ parent: Parent; rule: CSSRule }> = [];

  constructor(private doc: Document = document) {}

  /** Restore, then apply `edits`. Returns the rules it could not find. */
  apply(edits: Edit[]): string[] {
    this.restore();
    const found = findAll(this.doc);
    const missing: string[] = [];
    for (const e of edits) {
      if (e.kind === "style") {
        const rules = found.styles.get(normalSelector(e.selector)) ?? [];
        if (rules.length === 0) missing.push(e.selector);
        for (const r of rules) {
          this.save(r);
          setDecls(r.style, e.decls);
        }
      } else if (e.kind === "keyframes") {
        const rules = found.keyframes.get(e.name) ?? [];
        if (rules.length === 0) missing.push(`@keyframes ${e.name}`);
        for (const kf of rules) {
          for (const k of Array.from(kf.cssRules) as CSSKeyframeRule[]) {
            const frame = e.frames.find(([key]) => key === keyText(k));
            if (!frame) continue;
            this.save(k);
            setDecls(k.style, frame[1]);
          }
        }
      } else {
        const anchors = found.styles.get(normalSelector(e.after)) ?? [];
        if (anchors.length === 0) missing.push(e.after);
        for (const anchor of anchors) {
          const parent = (anchor.parentRule as CSSGroupingRule | null) ?? anchor.parentStyleSheet;
          if (!parent) continue;
          const index = Array.from(rulesOf(parent) ?? []).indexOf(anchor);
          const body = Object.entries(e.decls).map(([p, v]) => `${p}: ${v};`).join(" ");
          const at = parent.insertRule(`${e.selector} { ${body} }`, index + 1);
          this.inserted.push({ parent, rule: (rulesOf(parent) as CSSRuleList)[at] });
        }
      }
    }
    return missing;
  }

  /** Put the shipped theme back exactly as it was loaded. */
  restore(): void {
    for (const { parent, rule } of this.inserted.reverse()) {
      const index = Array.from(rulesOf(parent) ?? []).indexOf(rule);
      if (index >= 0) parent.deleteRule(index);
    }
    this.inserted = [];
    for (const [rule, css] of this.saved) rule.style.cssText = css;
    this.saved.clear();
  }

  private save(rule: CSSStyleRule | CSSKeyframeRule): void {
    if (!this.saved.has(rule)) this.saved.set(rule, rule.style.cssText);
  }
}
