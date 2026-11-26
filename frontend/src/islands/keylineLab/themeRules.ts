/**
 * Retune the shipped theme in place: find the rules the lab's edits name in the
 * loaded stylesheets (the theme CSS the app links), change their declarations
 * through the CSSOM, and put every one back on `restore()`. A token is changed
 * where it is declared: the `:root` rules that carry it (in `tokens.css`).
 *
 * No copy of a selector or a rule body lives here. A rule the lab cannot find is
 * reported, not invented: if the theme renames `.badge-proposed`, the lab says so
 * on the page instead of quietly styling nothing.
 */

import type { Edit } from "./spec";

type Parent = CSSStyleSheet | CSSGroupingRule;

interface Found {
  styles: Map<string, CSSStyleRule[]>;
  /** Custom property name → the rules that declare it. */
  tokens: Map<string, CSSStyleRule[]>;
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
      for (const prop of Array.from(rule.style)) {
        if (prop.startsWith("--")) found.tokens.set(prop, [...(found.tokens.get(prop) ?? []), rule]);
      }
    } else if ("cssRules" in rule) {
      walk(rule as CSSGroupingRule, found);
    }
  }
}

function findAll(doc: Document): Found {
  const found: Found = { styles: new Map(), tokens: new Map() };
  for (const sheet of Array.from(doc.styleSheets)) walk(sheet, found);
  return found;
}

function setDecls(style: CSSStyleDeclaration, decls: Record<string, string>): void {
  for (const [prop, raw] of Object.entries(decls)) {
    const important = /\s*!important\s*$/.test(raw);
    style.setProperty(prop, raw.replace(/\s*!important\s*$/, ""), important ? "important" : "");
  }
}

export class ThemeRuleEditor {
  private saved = new Map<CSSStyleRule, string>();
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
      } else if (e.kind === "token") {
        // The declaring rule only: a token set on a surface's own rule (an unlinked surface)
        // arrives as a "style" edit, so it never counts here.
        const rules = (found.tokens.get(e.name) ?? []).filter((r) => normalSelector(r.selectorText) === ":root");
        if (rules.length === 0) missing.push(e.name);
        for (const r of rules) {
          this.save(r);
          setDecls(r.style, { [e.name]: e.value });
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

  private save(rule: CSSStyleRule): void {
    if (!this.saved.has(rule)) this.saved.set(rule, rule.style.cssText);
  }
}
