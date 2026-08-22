/**
 * i18n — i18next initialisation for the Bristlenose frontend.
 *
 * English is bundled inline (zero-latency). Other locales are loaded lazily
 * via dynamic import() when the user changes locale in Settings.
 *
 * @module i18n
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import enCommon from "@locales/en/common.json";
import enSettings from "@locales/en/settings.json";
import enEnums from "@locales/en/enums.json";
import enDesktop from "@locales/en/desktop.json";
import { getExportData } from "../utils/exportData";
import { loadLocaleResources } from "./localeLoader";

export const SUPPORTED_LOCALES = ["en", "es", "ca", "ja", "fr", "de", "ko", "cs", "it", "pl", "ru", "uk", "da", "sv", "nb", "tr", "nl", "fi", "pt-BR", "pt-PT", "zh-Hant", "zh-Hant-HK"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export function isSupportedLocale(v: unknown): v is Locale {
  return typeof v === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(v);
}

const NAMESPACES = ["common", "settings", "enums"] as const;

/** Desktop mode detected from `data-platform="desktop"` on `<html>`. */
const _isDesktopMode = document.documentElement.dataset.platform === "desktop";

/** Namespaces to load for non-English locales — includes `desktop` in desktop mode. */
const LAZY_NAMESPACES: readonly string[] = _isDesktopMode
  ? [...NAMESPACES, "desktop"]
  : [...NAMESPACES];

/**
 * Register the locale resources an exported report carries with it.
 *
 * The server embeds the chosen language and its whole fallback chain — never
 * the leaf alone, since `zh-Hant-HK` is a thin override fork that ships no
 * `enums.json` at all and would render raw keys on its own. Registering every
 * locale in the embed (not just the requested one) is what lets i18next's
 * `fallbackLng` resolve as it does online.
 *
 * Returns true when the embed supplied something, so the caller can skip the
 * network path that an offline `file://` artefact has no way to use.
 */
function registerEmbeddedResources(locale: Locale): boolean {
  const embedded = getExportData()?.localeResources;
  if (!embedded) return false;
  let registered = false;
  for (const [loc, namespaces] of Object.entries(embedded)) {
    for (const [ns, bundle] of Object.entries(namespaces)) {
      i18n.addResourceBundle(loc, ns, bundle, true, true);
      if (loc === locale) registered = true;
    }
  }
  // A chain whose leaf contributes nothing still counts: the resources needed
  // to render `locale` are present, they are just under its fallbacks.
  return Object.keys(embedded).length > 0 || registered;
}

/**
 * Load and register a locale with i18next. No-op for English (bundled).
 */
export async function ensureLocaleLoaded(locale: Locale): Promise<void> {
  if (locale === "en") return;
  if (i18n.hasResourceBundle(locale, "common")) return;

  if (registerEmbeddedResources(locale)) return;

  const resources = await loadLocaleResources(locale, LAZY_NAMESPACES);
  for (const [ns, bundle] of Object.entries(resources)) {
    i18n.addResourceBundle(locale, ns, bundle, true, true);
  }
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        settings: enSettings,
        enums: enEnums,
        ...(_isDesktopMode ? { desktop: enDesktop } : {}),
      },
    },
    // Region/script variants borrow from a base locale before English.
    // zh-Hant-HK (Hong Kong) → zh-Hant (Taiwan Traditional) → en; all others → en.
    fallbackLng: { "zh-Hant-HK": ["zh-Hant", "en"], default: ["en"] },
    defaultNS: "common",
    ns: [...LAZY_NAMESPACES],
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "bn-locale",
      caches: [], // We manage persistence ourselves in LocaleStore
    },
    // Suppress missing key warnings in test — they clutter output.
    saveMissing: false,
    missingKeyHandler: false,
  });

// Keep <html lang> in sync so screen readers use the correct pronunciation engine.
i18n.on("languageChanged", (lng: string) => {
  document.documentElement.lang = lng;
});

export default i18n;
