/**
 * Native display names for the supported locales — the single copy.
 *
 * Always in the locale's own language: a reader looking for their language
 * scans for "Deutsch", not "German". This is the same reasoning `I18n.swift`'s
 * picker follows on the native side.
 *
 * Extracted 23 Aug 2026, when the export dialog became a third consumer.
 * It had been duplicated in `SettingsPanel.tsx` and `SettingsModal.tsx`, and
 * adding a language already costs ten registration sites (`docs/adding-a-language.md`
 * Step 8) — a third hand-maintained copy of the same 22 rows is one more place
 * for a language to be half-added, which is the failure mode that file exists
 * to prevent.
 *
 * @module i18n/localeLabels
 */

import type { Locale } from "./index";

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  es: "Español",
  ca: "Català",
  ja: "日本語",
  fr: "Français",
  de: "Deutsch",
  ko: "한국어",
  cs: "Čeština",
  it: "Italiano",
  pl: "Polski",
  ru: "Русский",
  uk: "Українська",
  da: "Dansk",
  sv: "Svenska",
  nb: "Norsk bokmål",
  tr: "Türkçe",
  nl: "Nederlands",
  fi: "Suomi",
  "pt-BR": "Português (Brasil)",
  "pt-PT": "Português (Portugal)",
  "zh-Hant": "繁體中文",
  "zh-Hant-HK": "繁體中文（香港）",
};
