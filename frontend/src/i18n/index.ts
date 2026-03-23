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

export const SUPPORTED_LOCALES = ["en", "es", "ja", "fr", "de", "ko"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export function isSupportedLocale(v: unknown): v is Locale {
  return typeof v === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(v);
}

const NAMESPACES = ["common", "settings", "enums"] as const;

/**
 * Lazily load a non-English locale's translation bundles.
 * Returns a resources object keyed by namespace.
 */
async function loadLocaleResources(
  locale: Locale,
): Promise<Record<string, Record<string, unknown>>> {
  const resources: Record<string, Record<string, unknown>> = {};
  for (const ns of NAMESPACES) {
    try {
      const mod = await import(`../../../bristlenose/locales/${locale}/${ns}.json`);
      resources[ns] = mod.default ?? mod;
    } catch {
      // Missing file — English fallback will be used for this namespace.
    }
  }
  return resources;
}

/**
 * Load and register a locale with i18next. No-op for English (bundled).
 */
export async function ensureLocaleLoaded(locale: Locale): Promise<void> {
  if (locale === "en") return;
  if (i18n.hasResourceBundle(locale, "common")) return;

  const resources = await loadLocaleResources(locale);
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
      },
    },
    fallbackLng: "en",
    defaultNS: "common",
    ns: [...NAMESPACES],
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

export default i18n;
