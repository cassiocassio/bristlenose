/**
 * Is this URL safe to put in an `href` we hand a researcher?
 *
 * The TypeScript half of a rule with three implementations. See
 * `bristlenose/utils/safe_url.py` for the full reasoning — the threat (URLs
 * arrive from codebook YAML, and `html.escape` does not neutralise
 * `javascript:`), the rule (allowlist the scheme, never denylist — OWASP), and
 * why there is no library (`bleach` is deprecated; DOMPurify sanitises *HTML*
 * at ~20 KB for a check that is one function).
 *
 * Swift is the third: `WebView.swift::openExternal` allows http/https/mailto
 * before handing a URL to `NSWorkspace`. All three are pinned to the same
 * answers by `tests/fixtures/safe-url-contract.json`.
 *
 * The parsing is the platform's. `new URL()` is the WHATWG parser, which
 * already strips tab/LF/CR and leading C0 controls — the normalisation a
 * hand-rolled check gets wrong, and the reason an embedded tab is not a bypass.
 */

/** Schemes we will render as a link. Must match `ALLOWED_SCHEMES` in Python. */
export const ALLOWED_SCHEMES: ReadonlySet<string> = new Set([
  "http:",
  "https:",
  "mailto:",
]);

/**
 * True when `raw` may be rendered as an `href`.
 *
 * Requires a host for http(s): a scheme with no host is not a destination.
 * `mailto` has no host by design, so it is checked on its path.
 */
export function isSafeUrl(raw: string | null | undefined): boolean {
  if (!raw || typeof raw !== "string") return false;
  let parsed: URL;
  try {
    // Absolute only — `new URL` throws without a base, which is what we want:
    // a relative path is not an external link.
    parsed = new URL(raw);
  } catch {
    return false;
  }
  if (!ALLOWED_SCHEMES.has(parsed.protocol)) return false;
  if (parsed.protocol === "mailto:") return parsed.pathname.trim().length > 0;
  return parsed.host.length > 0;
}

/**
 * The normalised URL when it is safe, else `null`.
 *
 * Returns the parser's normalisation rather than the input: if the value was
 * safe only because the parser stripped a tab out of it, render the stripped
 * form, not the original.
 */
export function safeUrlOrNull(raw: string | null | undefined): string | null {
  if (!isSafeUrl(raw)) return null;
  return new URL(raw as string).href;
}
