/**
 * Read the design tokens from the theme CSS the page has actually loaded, so
 * the foundations sections list what ships rather than a hand-kept copy.
 * A token added to `bristlenose/theme/` appears here with no edit; a token
 * removed disappears. (The hand-written style guide drifted exactly here.)
 */

function collect(rules: CSSRuleList, into: Set<string>): void {
  for (const rule of Array.from(rules)) {
    if (rule instanceof CSSStyleRule) {
      for (const prop of Array.from(rule.style)) {
        if (prop.startsWith("--bn-")) into.add(prop);
      }
    }
    // @supports / @media / @layer blocks hold the light-dark() definitions.
    if ("cssRules" in rule && (rule as CSSGroupingRule).cssRules) {
      collect((rule as CSSGroupingRule).cssRules, into);
    }
  }
}

/** Every `--bn-*` custom property declared in a loaded stylesheet, sorted. */
export function declaredTokens(doc: Document = document): string[] {
  const names = new Set<string>();
  for (const sheet of Array.from(doc.styleSheets)) {
    try {
      collect(sheet.cssRules, names);
    } catch {
      // A cross-origin sheet (Google Fonts) refuses cssRules; it holds no tokens.
    }
  }
  return [...names].sort();
}

/** Tokens starting with `prefix`, excluding any whose name matches `exclude`. */
export function tokensWithPrefix(prefix: string, exclude?: RegExp, doc: Document = document): string[] {
  return declaredTokens(doc).filter((n) => n.startsWith(prefix) && !(exclude && exclude.test(n)));
}
