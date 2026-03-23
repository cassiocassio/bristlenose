/**
 * LocaleStore — module-level store for the active UI locale.
 *
 * Uses the same pattern as SidebarStore: plain module-level state +
 * useSyncExternalStore. Locale preference is persisted to localStorage
 * as "bn-locale".
 *
 * Detection priority:
 *   1. localStorage("bn-locale") — explicit user choice
 *   2. navigator.languages / navigator.language — browser preference
 *   3. "en" fallback
 *
 * @module LocaleStore
 */

import { useSyncExternalStore } from "react";
import i18n from "./index";
import { ensureLocaleLoaded, isSupportedLocale } from "./index";
import type { Locale } from "./index";

// ── Constants ────────────────────────────────────────────────────────────

const LS_KEY = "bn-locale";

// ── State shape ──────────────────────────────────────────────────────────

export interface LocaleState {
  locale: Locale;
  ready: boolean;
}

// ── Module-level store ───────────────────────────────────────────────────

function detectLocale(): Locale {
  // 0. URL query param — set by native macOS shell for synchronous detection.
  // Prevents language flash on first render (native locale pushed before
  // the React SPA mounts, without waiting for bridge "ready" message).
  try {
    const params = new URLSearchParams(window.location.search);
    const urlLocale = params.get("locale");
    if (urlLocale && isSupportedLocale(urlLocale)) return urlLocale;
  } catch {
    // URL parsing unavailable
  }

  // 1. Explicit user choice in localStorage
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw && isSupportedLocale(raw)) return raw;
  } catch {
    // localStorage unavailable
  }

  // 2. Browser language (navigator.language / navigator.languages)
  try {
    const langs = navigator.languages ?? [navigator.language];
    for (const lang of langs) {
      // Match exact ("ja") or prefix ("fr-FR" → "fr")
      const code = lang.split("-")[0];
      if (isSupportedLocale(code)) return code;
    }
  } catch {
    // navigator.languages unavailable (e.g. SSR)
  }

  return "en";
}

let state: LocaleState = { locale: detectLocale(), ready: true };
const listeners = new Set<() => void>();

function getSnapshot(): LocaleState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify(): void {
  listeners.forEach((l) => l());
}

// ── Actions ──────────────────────────────────────────────────────────────

/**
 * Change the active locale. Loads translation bundles lazily, then updates
 * state and persists to localStorage.
 */
export async function setLocale(locale: Locale): Promise<void> {
  state = { locale, ready: false };
  notify();

  await ensureLocaleLoaded(locale);
  await i18n.changeLanguage(locale);

  // Set the lang attribute on <html> — critical for CJK glyph selection.
  document.documentElement.lang = locale;

  try {
    localStorage.setItem(LS_KEY, locale);
  } catch {
    // localStorage full or unavailable
  }

  state = { locale, ready: true };
  notify();
}

/** Reset to defaults. Used for test isolation. */
export function resetLocaleStore(): void {
  state = { locale: "en", ready: true };
  notify();
}

// ── React hook ───────────────────────────────────────────────────────────

/** Subscribe to the locale store. Re-renders on locale change. */
export function useLocaleStore(): LocaleState {
  return useSyncExternalStore(subscribe, getSnapshot);
}

// ── Startup sync ─────────────────────────────────────────────────────────
// If the detected locale is non-English, load its bundles and switch i18next.
// This runs once at module load time.

if (state.locale !== "en") {
  void setLocale(state.locale);
}
