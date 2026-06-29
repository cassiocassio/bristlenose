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

/**
 * Resolve a BCP 47 browser language tag to a supported locale.
 *
 * Chinese needs script/region awareness, not a naive prefix strip: `zh-TW`
 * must map to `zh-Hant` (Taiwan Traditional) and `zh-HK`/`zh-MO` to
 * `zh-Hant-HK`. A plain `lang.split("-")[0]` yields `zh`, which matches no
 * supported locale. Simplified tags (`zh-Hans`/`zh-CN`/`zh-SG`) and bare `zh`
 * have no supported locale yet, so they fall through rather than being forced
 * into a Traditional variant. Non-Chinese tags keep exact-or-prefix behaviour
 * (`fr-FR` → `fr`).
 */
export function resolveBrowserLang(lang: string): Locale | null {
  // Exact match first (browser may send "zh-Hant" / "zh-Hant-HK" verbatim).
  if (isSupportedLocale(lang)) return lang;

  const lower = lang.toLowerCase();
  if (lower.startsWith("zh")) {
    if (lower.includes("hans") || lower.includes("-cn") || lower.includes("-sg")) {
      return null; // Simplified — no supported locale yet
    }
    if (lower.includes("hk") || lower.includes("mo")) return "zh-Hant-HK";
    if (lower.includes("hant") || lower.includes("tw")) return "zh-Hant";
    return null; // bare "zh" is ambiguous (CLDR default is Simplified) → fall through
  }

  // Non-Chinese: exact ("ja") or prefix ("fr-FR" → "fr").
  const prefix = lang.split("-")[0];
  return isSupportedLocale(prefix) ? prefix : null;
}

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
      const resolved = resolveBrowserLang(lang);
      if (resolved) return resolved;
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
