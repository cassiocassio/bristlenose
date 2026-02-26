/**
 * SettingsPanel — React island for the Settings tab.
 *
 * Three radio buttons for appearance: system (auto), light, dark. Persists to
 * localStorage, applies data-theme attr + colorScheme on <html>. The logo uses
 * a transparent-background PNG that works on both themes — no image swapping
 * needed. In serve mode the logo is an animated <video>; this component handles
 * pausing it when the user prefers reduced motion.
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
 * Transparent-background logo works on both themes — no image swap needed.
 * Only concern: pause the animated <video> for reduced-motion users.
 */
function updateLogo(_value: Appearance): void {
  const video = document.querySelector<HTMLVideoElement>("video.report-logo");
  if (!video) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    video.pause();
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

  // Pause/play animated logo when reduced-motion preference changes.
  useEffect(() => {
    const video = document.querySelector<HTMLVideoElement>("video.report-logo");
    if (!video) return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motionQuery.matches) video.pause();

    const handler = (e: MediaQueryListEvent) => {
      if (e.matches) { video.pause(); } else { void video.play(); }
    };
    motionQuery.addEventListener("change", handler);
    return () => motionQuery.removeEventListener("change", handler);
  }, []);

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
