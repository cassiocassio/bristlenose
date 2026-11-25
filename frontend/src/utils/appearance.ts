/**
 * Appearance (auto / light / dark) applied to the document — moved out of
 * `SettingsModal.tsx` (25 Nov 2026) so the style-guide specimen route sets
 * the appearance by the very function Settings uses, rather than a copy of it.
 * Behaviour is unchanged: `data-theme` and `color-scheme` on `<html>`, and the
 * logo's `<source>` removed while light or dark is forced.
 */

export type Appearance = "auto" | "light" | "dark";

const THEME_ATTR = "data-theme";

export function isAppearance(v: unknown): v is Appearance {
  return v === "auto" || v === "light" || v === "dark";
}

export function applyTheme(value: Appearance): void {
  const root = document.documentElement;
  if (value === "light" || value === "dark") {
    root.setAttribute(THEME_ATTR, value);
    root.style.colorScheme = value;
  } else {
    root.removeAttribute(THEME_ATTR);
    root.style.colorScheme = "light dark";
  }
  updateLogo(value);
}

let stashedSource: Element | null = null;

function updateLogo(value: Appearance): void {
  const img = document.querySelector<HTMLImageElement>(".report-logo");
  if (!img) return;
  const picture = img.parentElement;
  if (!picture || picture.tagName !== "PICTURE") return;

  const src = img.getAttribute("src") || "";
  const darkSrc = src.replace("bristlenose-logo.png", "bristlenose-logo-dark.png");
  const lightSrc = src.replace("bristlenose-logo-dark.png", "bristlenose-logo.png");

  if (!stashedSource) {
    stashedSource = picture.querySelector("source");
  }

  if (value === "light" || value === "dark") {
    const existing = picture.querySelector("source");
    if (existing) existing.remove();
    img.src = value === "dark" ? darkSrc : lightSrc;
  } else {
    if (stashedSource && !picture.querySelector("source")) {
      picture.insertBefore(stashedSource, img);
    }
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    img.src = isDark ? darkSrc : lightSrc;
  }
}
