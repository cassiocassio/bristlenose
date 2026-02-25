/**
 * SettingsPanel — React island for the Settings tab.
 *
 * Replaces settings.js (105 lines of vanilla JS). Three radio buttons
 * for appearance: system (auto), light, dark. Persists to localStorage,
 * applies data-theme attr + colorScheme on <html>, and swaps the header
 * logo between light/dark variants.
 */

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Appearance = "auto" | "light" | "dark";

const STORAGE_KEY = "bristlenose-appearance";
const THEME_ATTR = "data-theme";

const OPTIONS: { value: Appearance; label: string }[] = [
  { value: "auto", label: "Use system appearance" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isAppearance(v: unknown): v is Appearance {
  return v === "auto" || v === "light" || v === "dark";
}

function readSaved(): Appearance {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return "auto";
    // The vanilla JS store (createStore in storage.js) JSON-encodes values,
    // so localStorage contains '"dark"' not 'dark'.  Parse first, then
    // validate.  If the value is already a bare string (legacy or direct
    // write), fall through to the raw check.
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isAppearance(parsed)) return parsed;
    } catch {
      // Not valid JSON — check if it's a bare appearance string.
    }
    return isAppearance(raw) ? raw : "auto";
  } catch {
    return "auto";
  }
}

function applyTheme(value: Appearance): void {
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

/**
 * Logo dark/light swap.
 *
 * The header logo uses <picture><source media="(prefers-color-scheme: dark)">
 * which works for "auto" mode. But forced light/dark via Settings sets the
 * theme attr on <html> — <picture> <source> media queries only respond to the
 * OS-level prefers-color-scheme, not page-level overrides.
 *
 * Workaround: physically remove the <source> element when forcing light/dark
 * (so the <img> src wins), stash it, and restore when switching back to auto.
 */
let stashedSource: Element | null = null;

function updateLogo(value: Appearance): void {
  const img = document.querySelector<HTMLImageElement>(".report-logo");
  if (!img) return;
  const picture = img.parentElement;
  if (!picture || picture.tagName !== "PICTURE") return;

  const src = img.getAttribute("src") || "";
  const darkSrc = src.replace("bristlenose-logo.png", "bristlenose-logo-dark.png");
  const lightSrc = src.replace("bristlenose-logo-dark.png", "bristlenose-logo.png");

  // Stash the <source> on first call so we can restore it later.
  if (!stashedSource) {
    stashedSource = picture.querySelector("source");
  }

  if (value === "light" || value === "dark") {
    const existing = picture.querySelector("source");
    if (existing) existing.remove();
    img.src = value === "dark" ? darkSrc : lightSrc;
  } else {
    // Auto — restore <source> and let browser media query decide.
    if (stashedSource && !picture.querySelector("source")) {
      picture.insertBefore(stashedSource, img);
    }
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    img.src = isDark ? darkSrc : lightSrc;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SettingsPanel() {
  const [appearance, setAppearance] = useState<Appearance>(readSaved);

  // Apply theme on mount and whenever the value changes.
  useEffect(() => {
    applyTheme(appearance);
  }, [appearance]);

  const handleChange = useCallback((value: Appearance) => {
    setAppearance(value);
    try {
      // JSON-encode to match the vanilla JS store format (createStore.set
      // in storage.js calls JSON.stringify).  Without this, transcript pages
      // fail to parse the raw string and fall back to "auto" (light mode).
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      // localStorage may be unavailable — ignore.
    }
  }, []);

  return (
    <>
      <h2>Settings</h2>
      <fieldset className="bn-setting-group">
        <legend>Application appearance</legend>
        {OPTIONS.map((opt) => (
          <label key={opt.value} className="bn-radio-label">
            <input
              type="radio"
              name="bn-appearance"
              value={opt.value}
              checked={appearance === opt.value}
              onChange={() => handleChange(opt.value)}
            />
            {" "}{opt.label}
          </label>
        ))}
      </fieldset>
    </>
  );
}
