/**
 * SettingsModal — settings dialog with sidebar navigation.
 *
 * Five sections:
 *   1. General (default) — appearance, language, default provider
 *   2. Project — per-project prefs (PII redaction) — stubbed
 *   3. Profile — name, email, whisper backend — stubbed
 *   4. API Keys — credential CRUD — stubbed
 *   5. Config — disclosure group with 12 sub-categories (read-only reference)
 *
 * Phase 1: General is functional (appearance + language), Config shows
 * the existing ConfigReference grid. Other sections are stubs.
 *
 * @module SettingsModal
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LOCALES, type Locale } from "../i18n";
import { setLocale, useLocaleStore } from "../i18n/LocaleStore";
import { ModalNav, type NavItem } from "./ModalNav";
import { isEmbedded } from "../utils/embedded";
import { dt } from "../utils/platformTranslation";
import { PALETTES, isPalette, readSavedPalette, type Palette } from "../utils/bootPalette";

// ── Types ─────────────────────────────────────────────────────────────────

type Appearance = "auto" | "light" | "dark";

const STORAGE_KEY = "bristlenose-appearance";
const THEME_ATTR = "data-theme";

const APPEARANCE_KEYS: { value: Appearance; labelKey: string }[] = [
  { value: "auto", labelKey: "appearance.auto" },
  { value: "light", labelKey: "appearance.light" },
  { value: "dark", labelKey: "appearance.dark" },
];

// Colour palette — orthogonal to appearance (light/dark). Radios like appearance
// while the set is small; derive from PALETTES so it extends automatically.
const PALETTE_KEY = "bristlenose-palette";
const PALETTE_ATTR = "data-color-theme";
const PALETTE_KEYS = PALETTES.map((value) => ({ value, labelKey: `palette.${value}` }));

/** Display labels for supported locales. Always in the locale's own language. */
const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  es: "Español",
  ja: "日本語",
  fr: "Français",
  de: "Deutsch",
  ko: "한국어",
  cs: "Čeština",
  it: "Italiano",
  pl: "Polski",
  ru: "Русский",
  uk: "Українська",
  "pt-BR": "Português (Brasil)",
  "pt-PT": "Português (Portugal)",
  "zh-Hant": "繁體中文",
  "zh-Hant-HK": "繁體中文（香港）",
};

// ── Appearance helpers ────────────────────────────────────────────────────

function isAppearance(v: unknown): v is Appearance {
  return v === "auto" || v === "light" || v === "dark";
}

function readSaved(): Appearance {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return "auto";
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isAppearance(parsed)) return parsed;
    } catch {
      // Not valid JSON — check bare string.
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

// ── Configuration reference data ──────────────────────────────────────────

interface SettingRef {
  labelKey: string;
  envVar: string;
  default: string;
  file: string;
  filePath: string;
  options?: string[];
  sensitive?: boolean;
}

interface SettingCategory {
  id: string;
  labelKey: string;
  settings: SettingRef[];
}

const CONFIG_DATA: SettingCategory[] = [
  {
    id: "llm",
    labelKey: "configReference.categories.llm",
    settings: [
      { labelKey: "configReference.settings.llm.provider", envVar: "BRISTLENOSE_LLM_PROVIDER", default: "anthropic", file: ".env", filePath: "bristlenose/config.py", options: ["anthropic", "openai", "azure", "google", "local"] },
      { labelKey: "configReference.settings.llm.model", envVar: "BRISTLENOSE_LLM_MODEL", default: "claude-sonnet-4-20250514", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.temperature", envVar: "BRISTLENOSE_LLM_TEMPERATURE", default: "0.1", file: ".env", filePath: "bristlenose/config.py", options: ["0.0\u20131.0"] },
      { labelKey: "configReference.settings.llm.maxTokens", envVar: "BRISTLENOSE_LLM_MAX_TOKENS", default: "32768", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.concurrency", envVar: "BRISTLENOSE_LLM_CONCURRENCY", default: "3", file: ".env", filePath: "bristlenose/config.py", options: ["1\u201310"] },
      { labelKey: "configReference.settings.llm.claudeKey", envVar: "BRISTLENOSE_ANTHROPIC_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { labelKey: "configReference.settings.llm.chatgptKey", envVar: "BRISTLENOSE_OPENAI_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { labelKey: "configReference.settings.llm.geminiKey", envVar: "BRISTLENOSE_GOOGLE_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { labelKey: "configReference.settings.llm.azureKey", envVar: "BRISTLENOSE_AZURE_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { labelKey: "configReference.settings.llm.azureEndpoint", envVar: "BRISTLENOSE_AZURE_ENDPOINT", default: "(not set)", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.azureDeployment", envVar: "BRISTLENOSE_AZURE_DEPLOYMENT", default: "(not set)", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.azureApiVersion", envVar: "BRISTLENOSE_AZURE_API_VERSION", default: "2024-10-21", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.ollamaUrl", envVar: "BRISTLENOSE_LOCAL_URL", default: "http://localhost:11434/v1", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.llm.ollamaModel", envVar: "BRISTLENOSE_LOCAL_MODEL", default: "llama3.2:3b", file: ".env", filePath: "bristlenose/config.py" },
    ],
  },
  {
    id: "transcription",
    labelKey: "configReference.categories.transcription",
    settings: [
      { labelKey: "configReference.settings.transcription.backend", envVar: "BRISTLENOSE_WHISPER_BACKEND", default: "auto", file: ".env", filePath: "bristlenose/config.py", options: ["auto", "mlx", "faster-whisper"] },
      { labelKey: "configReference.settings.transcription.model", envVar: "BRISTLENOSE_WHISPER_MODEL", default: "large-v3-turbo", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.transcription.language", envVar: "BRISTLENOSE_WHISPER_LANGUAGE", default: "en", file: ".env", filePath: "bristlenose/config.py", options: ["ISO 639 code"] },
      { labelKey: "configReference.settings.transcription.device", envVar: "BRISTLENOSE_WHISPER_DEVICE", default: "auto", file: ".env", filePath: "bristlenose/config.py", options: ["auto", "cpu", "cuda"] },
      { labelKey: "configReference.settings.transcription.computeType", envVar: "BRISTLENOSE_WHISPER_COMPUTE_TYPE", default: "int8", file: ".env", filePath: "bristlenose/config.py", options: ["int8", "float16", "float32"] },
      { labelKey: "configReference.settings.transcription.audioConcurrency", envVar: "_DEFAULT_CONCURRENCY", default: "4", file: "extract_audio.py", filePath: "bristlenose/stages/extract_audio.py" },
    ],
  },
  {
    id: "privacy",
    labelKey: "configReference.categories.privacy",
    settings: [
      { labelKey: "configReference.settings.privacy.piiRedaction", envVar: "BRISTLENOSE_PII_ENABLED", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { labelKey: "configReference.settings.privacy.piiLlmPass", envVar: "BRISTLENOSE_PII_LLM_PASS", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { labelKey: "configReference.settings.privacy.customNames", envVar: "BRISTLENOSE_PII_CUSTOM_NAMES", default: "(none)", file: ".env", filePath: "bristlenose/config.py", options: ["comma-separated"] },
    ],
  },
  {
    id: "quotes",
    labelKey: "configReference.categories.quotes",
    settings: [
      { labelKey: "configReference.settings.quotes.minQuoteWords", envVar: "BRISTLENOSE_MIN_QUOTE_WORDS", default: "5", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.quotes.speakerMergeGap", envVar: "BRISTLENOSE_MERGE_SPEAKER_GAP_SECONDS", default: "2.0", file: ".env", filePath: "bristlenose/config.py", options: ["seconds"] },
      { labelKey: "configReference.settings.quotes.quoteSequenceGap", envVar: "SEQUENCE_GAP_SECONDS", default: "17.5", file: "models.py", filePath: "bristlenose/analysis/models.py", options: ["seconds"] },
      { labelKey: "configReference.settings.quotes.llmFailureThreshold", envVar: "_FAIL_THRESHOLD", default: "3", file: "quote_extraction.py", filePath: "bristlenose/stages/quote_extraction.py" },
      { labelKey: "configReference.settings.quotes.autocodeBatchSize", envVar: "BATCH_SIZE", default: "25", file: "autocode.py", filePath: "bristlenose/server/autocode.py" },
    ],
  },
  {
    id: "analysis",
    labelKey: "configReference.categories.analysis",
    settings: [
      { labelKey: "configReference.settings.analysis.topNSignals", envVar: "DEFAULT_TOP_N", default: "12", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.topNSignalsGeneric", envVar: "DEFAULT_TOP_N", default: "12", file: "generic_signals.py", filePath: "bristlenose/analysis/generic_signals.py" },
      { labelKey: "configReference.settings.analysis.topNElaboration", envVar: "DEFAULT_TOP_N", default: "10", file: "elaboration.py", filePath: "bristlenose/server/elaboration.py" },
      { labelKey: "configReference.settings.analysis.minQuotesPerCell", envVar: "MIN_QUOTES_PER_CELL", default: "2", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.strongConcentration", envVar: "hardcoded", default: "2", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.strongParticipants", envVar: "hardcoded", default: "5", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.strongQuotes", envVar: "hardcoded", default: "6", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.moderateConcentration", envVar: "hardcoded", default: "1.5", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.moderateParticipants", envVar: "hardcoded", default: "3", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { labelKey: "configReference.settings.analysis.moderateQuotes", envVar: "hardcoded", default: "4", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
    ],
  },
  {
    id: "autocode",
    labelKey: "configReference.categories.autocode",
    settings: [
      { labelKey: "configReference.settings.autocode.defaultLower", envVar: "DEFAULT_LOWER", default: "0.30", file: "ThresholdReviewModal.tsx", filePath: "frontend/src/components/ThresholdReviewModal.tsx", options: ["0.0\u20131.0"] },
      { labelKey: "configReference.settings.autocode.defaultUpper", envVar: "DEFAULT_UPPER", default: "0.70", file: "ThresholdReviewModal.tsx", filePath: "frontend/src/components/ThresholdReviewModal.tsx", options: ["0.0\u20131.0"] },
      { labelKey: "configReference.settings.autocode.sliderStep", envVar: "STEP", default: "0.05", file: "DualThresholdSlider.tsx", filePath: "frontend/src/components/DualThresholdSlider.tsx" },
      { labelKey: "configReference.settings.autocode.sliderMinGap", envVar: "MIN_GAP", default: "0.05", file: "DualThresholdSlider.tsx", filePath: "frontend/src/components/DualThresholdSlider.tsx" },
      { labelKey: "configReference.settings.autocode.histogramBins", envVar: "NUM_BINS", default: "20", file: "ConfidenceHistogram.tsx", filePath: "frontend/src/components/ConfidenceHistogram.tsx" },
    ],
  },
  {
    id: "display",
    labelKey: "configReference.categories.display",
    settings: [
      { labelKey: "configReference.settings.display.searchMinChars", envVar: "hardcoded", default: "3", file: "filter.ts", filePath: "frontend/src/utils/filter.ts" },
      { labelKey: "configReference.settings.display.activityPollInterval", envVar: "POLL_INTERVAL", default: "2000", file: "ActivityChipStack.tsx", filePath: "frontend/src/components/ActivityChipStack.tsx", options: ["ms"] },
    ],
  },
  {
    id: "pipeline",
    labelKey: "configReference.categories.pipeline",
    settings: [
      { labelKey: "configReference.settings.pipeline.projectName", envVar: "BRISTLENOSE_PROJECT_NAME", default: "User Research", file: ".env", filePath: "bristlenose/config.py" },
      { labelKey: "configReference.settings.pipeline.writeIntermediate", envVar: "BRISTLENOSE_WRITE_INTERMEDIATE", default: "true", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { labelKey: "configReference.settings.pipeline.skipTranscription", envVar: "BRISTLENOSE_SKIP_TRANSCRIPTION", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { labelKey: "configReference.settings.pipeline.maxSessionsBeforeConfirm", envVar: "_MAX_SESSIONS_NO_CONFIRM", default: "16", file: "pipeline.py", filePath: "bristlenose/pipeline.py" },
    ],
  },
  {
    id: "thumbnails",
    labelKey: "configReference.categories.thumbnails",
    settings: [
      { labelKey: "configReference.settings.thumbnails.keyframeSearchWindow", envVar: "_WINDOW_SECONDS", default: "180", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["seconds"] },
      { labelKey: "configReference.settings.thumbnails.fallbackFrameTime", envVar: "_FALLBACK_SECONDS", default: "60", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["seconds"] },
      { labelKey: "configReference.settings.thumbnails.thumbnailWidth", envVar: "_THUMB_WIDTH", default: "384", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["px"] },
      { labelKey: "configReference.settings.thumbnails.jpegQuality", envVar: "_THUMB_QUALITY", default: "5", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["2 (best) \u2013 31 (worst)"] },
    ],
  },
  {
    id: "server",
    labelKey: "configReference.categories.server",
    settings: [
      { labelKey: "configReference.settings.server.serverPort", envVar: "_BRISTLENOSE_PORT", default: "8150", file: "cli.py", filePath: "bristlenose/cli.py" },
      { labelKey: "configReference.settings.server.miroAccessToken", envVar: "BRISTLENOSE_MIRO_ACCESS_TOKEN", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
    ],
  },
  {
    id: "logging",
    labelKey: "configReference.categories.logging",
    settings: [
      { labelKey: "configReference.settings.logging.logLevel", envVar: "BRISTLENOSE_LOG_LEVEL", default: "INFO", file: ".env", filePath: "bristlenose/logging.py", options: ["DEBUG", "INFO", "WARNING", "ERROR"] },
      { labelKey: "configReference.settings.logging.logFileMaxSize", envVar: "_MAX_BYTES", default: "5 MB", file: "logging.py", filePath: "bristlenose/logging.py" },
      { labelKey: "configReference.settings.logging.logBackupCount", envVar: "_BACKUP_COUNT", default: "2", file: "logging.py", filePath: "bristlenose/logging.py" },
    ],
  },
  {
    id: "timing",
    labelKey: "configReference.categories.timing",
    settings: [
      { labelKey: "configReference.settings.timing.minRunsEstimate", envVar: "_MIN_N_ESTIMATE", default: "4", file: "timing.py", filePath: "bristlenose/timing.py" },
      { labelKey: "configReference.settings.timing.minRunsRange", envVar: "_MIN_N_RANGE", default: "8", file: "timing.py", filePath: "bristlenose/timing.py" },
    ],
  },
];

// ── Navigation structure ──────────────────────────────────────────────────

// Nav item keys — labels resolved at render time via t().
const NAV_KEYS: { id: string; labelKey: string; hasChildren?: boolean }[] = [
  { id: "general", labelKey: "settingsNav.general" },
  { id: "project", labelKey: "settingsNav.project" },
  { id: "profile", labelKey: "settingsNav.profile" },
  { id: "api-keys", labelKey: "settingsNav.apiKeys" },
  { id: "config", labelKey: "settingsNav.config", hasChildren: true },
  // Pipeline is last on purpose — "for the interested" placement. See
  // pipeline-view-v1 plan and docs/design-cli-improvements.md §Captured design.
  { id: "pipeline", labelKey: "settingsNav.pipeline" },
];

// ── Section components ────────────────────────────────────────────────────

function GeneralSection() {
  const { t } = useTranslation("settings");
  const [appearance, setAppearanceState] = useState<Appearance>(readSaved);
  const { locale } = useLocaleStore();

  useEffect(() => {
    applyTheme(appearance);
  }, [appearance]);

  const handleAppearance = useCallback((value: Appearance) => {
    setAppearanceState(value);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      // localStorage may be unavailable.
    }
  }, []);

  // Colour palette. Initial = saved pref, else the server-injected attribute
  // (desktop → edo), else "default".
  const [palette, setPaletteState] = useState<Palette>(() => {
    const saved = readSavedPalette(localStorage);
    if (saved) return saved;
    const attr = document.documentElement.getAttribute(PALETTE_ATTR);
    return isPalette(attr) ? attr : "default";
  });
  // Only (re)apply once the user has actively chosen — never clobber the server
  // default for a user who hasn't touched the control.
  const paletteChosen = useRef(readSavedPalette(localStorage) !== null);
  useEffect(() => {
    if (paletteChosen.current) {
      document.documentElement.setAttribute(PALETTE_ATTR, palette);
    }
  }, [palette]);

  const handlePalette = useCallback((value: Palette) => {
    paletteChosen.current = true;
    setPaletteState(value);
    document.documentElement.setAttribute(PALETTE_ATTR, value);
    try {
      localStorage.setItem(PALETTE_KEY, JSON.stringify(value));
    } catch (err) {
      // Applied for the session but not persisted (private mode / quota).
      console.warn("bristlenose: could not persist palette preference", err);
    }
  }, []);

  const handleLocaleChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (SUPPORTED_LOCALES.includes(value as Locale)) {
      void setLocale(value as Locale);
    }
  }, []);

  return (
    <>
      <fieldset className="bn-setting-group">
        <legend>{t("appearance.legend")}</legend>
        {APPEARANCE_KEYS.map((opt) => (
          <label key={opt.value} className="bn-radio-label">
            <input
              type="radio"
              name="bn-settings-appearance"
              value={opt.value}
              checked={appearance === opt.value}
              onChange={() => handleAppearance(opt.value)}
            />
            {" "}{t(opt.labelKey)}
          </label>
        ))}
      </fieldset>

      <fieldset className="bn-setting-group">
        <legend>{t("palette.legend")}</legend>
        <p className="bn-setting-description">{t("palette.description")}</p>
        {PALETTE_KEYS.map((opt) => (
          <label key={opt.value} className="bn-radio-label">
            <input
              type="radio"
              name="bn-settings-palette"
              value={opt.value}
              checked={palette === opt.value}
              onChange={() => handlePalette(opt.value)}
            />
            {" "}{t(opt.labelKey)}
          </label>
        ))}
      </fieldset>

      {!isEmbedded() && (
        <fieldset className="bn-setting-group">
          <legend>{t("language.legend")}</legend>
          <p className="bn-setting-description">
            {t("language.description")}
          </p>
          <select
            className="bn-locale-select"
            value={locale}
            onChange={handleLocaleChange}
          >
            {SUPPORTED_LOCALES.map((loc) => (
              <option key={loc} value={loc}>
                {LOCALE_LABELS[loc]}
              </option>
            ))}
          </select>
          <p className="bn-setting-description" style={{ marginTop: "0.5rem" }}>
            {t("language.helpTranslate")}{" "}
            <a
              href="https://hosted.weblate.org/projects/bristlenose/"
              target="_blank"
              rel="noopener noreferrer"
            >
              Weblate
            </a>
          </p>
        </fieldset>
      )}
    </>
  );
}

function StubSection({ description }: { description: string }) {
  return (
    <p className="bn-setting-description">{description}</p>
  );
}

function ConfigSection({ categoryId }: { categoryId: string }) {
  const { t } = useTranslation("settings");
  const cat = CONFIG_DATA.find((c) => `config-${c.id}` === categoryId);
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(text);
      setTimeout(() => setCopied(null), 1500);
    }).catch(() => {});
  }, []);

  if (!cat) return null;

  return (
    <div className="bn-config-ref">
      <p className="bn-config-ref-intro"
        dangerouslySetInnerHTML={{ __html: dt(t, "configReference.intro") }}
      />
      {cat.settings.map((s, i) => (
        <div key={`${cat.id}-${i}`} className="bn-config-ref-row">
          <span className="bn-config-ref-label">{t(s.labelKey)}</span>
          <code className="bn-config-ref-value">
            {s.sensitive ? "\u2022\u2022\u2022\u2022\u2022\u2022" : s.default}
          </code>
          <span className="bn-config-ref-file" title={s.filePath}>
            {s.file}
          </span>
          <span className="bn-config-ref-meta">
            {/* Click-to-copy env var; keyboard-accessible via tabIndex/onKeyDown, kept as <code> for styling. */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
            <code
              className={`bn-config-ref-envvar${copied === s.envVar ? " copied" : ""}`}
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
              tabIndex={0}
              onClick={() => handleCopy(s.envVar)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleCopy(s.envVar);
                }
              }}
              title={t("configReference.clickToCopy")}
            >
              {s.envVar}
            </code>
            {s.options && (
              <span className="bn-config-ref-options">
                {s.options.join(" \u00b7 ")}
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Pipeline section ──────────────────────────────────────────────────────

type QualityLevel = "excellent" | "good" | "marginal" | "avoid";

// Mirrors `ModelAvailability` in bristlenose/pipeline_view/render.py (schema v4).
// One row per (provider, model) cell, plus synthesised rows for runtime-detected
// models. Field-for-field parity is pinned by tests/fixtures/pipeline-view-contract.json.
interface ModelAvailability {
  provider_id: string;
  model_id?: string | null;
  display: string;
  display_key?: string | null;
  provider_display: string;
  provider_display_key?: string | null;
  publisher?: string | null;
  available: boolean;
  reason_key?: string | null;
  action_key?: string | null;
  quality?: QualityLevel | null;
  quality_note?: string | null;
  quality_source?: string | null;
  default: boolean;
  recommended: boolean;
  synthesised: boolean;
}

interface PipelineStageView {
  id: string;
  name: string;
  kind: string;
  chosen: string;
  chosen_id?: string | null;
  chosen_model_id?: string | null;
  notes: string;
  available: boolean;
  alternatives?: ModelAvailability[];
}

interface PipelineViewResponse {
  schema_version?: number;
  catalogue: PipelineStageView[];
  host: {
    os: string;
    arch: string;
    os_version?: string | null;
    memory_gb: number | null;
    keys_present: Record<string, boolean>;
    installed_packages?: Record<string, boolean>;
    ollama_running: boolean;
    network_reachable: boolean;
    apple_fm_status: string;
  };
}

// Editorial quality glyphs — distinct vocabulary from MessageKind by design
// (a cell's fitness is orthogonal to whether it can run). Mirrors cli.py's
// _QUALITY_GLYPH; untested (?) is handled separately (quality === null).
const QUALITY_GLYPH: Record<QualityLevel, string> = {
  excellent: "●",
  good: "○",
  marginal: "⚠",
  avoid: "✗",
};

interface StageGroup {
  names: string[];
  sel: PipelineStageView;
}

// Stage-profile clustering — mirrors cli.py's _cluster_signature. LLM stages
// whose per-model availability + quality *level* columns are byte-identical
// merge under one heading; quality_note is deliberately excluded so the three
// synthesis stages (distinct notes) still merge. Non-LLM stages never merge.
function clusterSignature(stage: PipelineStageView): string {
  return JSON.stringify(
    (stage.alternatives ?? []).map((a) => [
      a.provider_id,
      a.model_id ?? null,
      a.available,
      a.reason_key ?? null,
      a.quality ?? null,
      a.default,
      a.recommended,
    ]),
  );
}

function buildStageGroups(catalogue: PipelineStageView[]): StageGroup[] {
  const llmGroups: StageGroup[] = [];
  const llmIndex = new Map<string, StageGroup>();
  const nonLlmGroups: StageGroup[] = [];
  for (const stage of catalogue) {
    if (!stage.alternatives || stage.alternatives.length === 0) continue;
    if (stage.kind === "llm") {
      const sig = clusterSignature(stage);
      const existing = llmIndex.get(sig);
      if (existing) {
        existing.names.push(stage.name);
      } else {
        const group: StageGroup = { names: [stage.name], sel: stage };
        llmIndex.set(sig, group);
        llmGroups.push(group);
      }
    } else {
      nonLlmGroups.push({ names: [stage.name], sel: stage });
    }
  }
  return [...llmGroups, ...nonLlmGroups];
}

// Bucket a flat alternatives list into per-provider groups (order-preserving).
// Mirrors cli.py's _by_provider.
function byProvider(alts: ModelAvailability[]): ModelAvailability[][] {
  const groups: ModelAvailability[][] = [];
  let currentPid: string | null = null;
  let bucket: ModelAvailability[] = [];
  for (const a of alts) {
    if (a.provider_id !== currentPid) {
      if (bucket.length) groups.push(bucket);
      bucket = [a];
      currentPid = a.provider_id;
    } else {
      bucket.push(a);
    }
  }
  if (bucket.length) groups.push(bucket);
  return groups;
}

// Collapse-when-uniform (F49) — mirrors cli.py's _collapse. A provider renders
// as a single row when it has no model granularity, or when no model is
// available AND every failure shares one provider-level reason.
function collapseProvider(rows: ModelAvailability[]): {
  collapsed: boolean;
  rep: ModelAvailability;
} {
  if (rows.length === 1 && rows[0].model_id == null) {
    return { collapsed: true, rep: rows[0] };
  }
  if (rows.every((r) => !r.available)) {
    const reasons = new Set(rows.map((r) => r.reason_key ?? null));
    if (reasons.size === 1) return { collapsed: true, rep: rows[0] };
  }
  return { collapsed: false, rep: rows[0] };
}

function authToken(): string | undefined {
  return (window as unknown as Record<string, unknown>)
    .__BRISTLENOSE_AUTH_TOKEN__ as string | undefined;
}

function PipelineSection() {
  const { t } = useTranslation("settings");
  const [data, setData] = useState<PipelineViewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const token = authToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    fetch("/api/pipeline", { headers })
      .then((res) => {
        if (!res.ok) throw new Error(`GET /api/pipeline ${res.status}`);
        return res.json() as Promise<PipelineViewResponse>;
      })
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p className="bn-setting-description">{t("pipeline.error")}: {error}</p>;
  }
  if (!data) {
    return <p className="bn-setting-description">{t("pipeline.loading")}</p>;
  }

  const host = data.host;
  const keysOn = Object.entries(host.keys_present)
    .filter(([, on]) => on)
    .map(([p]) => p);

  const providerLabel = (row: ModelAvailability): string =>
    row.provider_display_key
      ? t(row.provider_display_key, { defaultValue: row.provider_display })
      : row.provider_display;

  // Availability glyph cell — MessageKind vocabulary (cli.py _avail_glyph):
  // ✓ available, ✗ fixable failure (action_key present), — structural skip.
  const availCell = (row: ModelAvailability) => {
    let glyph: string;
    let cls: string;
    let label: string;
    if (row.available) {
      glyph = "✓";
      cls = "bn-pipeline-avail-ok";
      label = t("pipeline.glyph.available");
    } else if (row.action_key != null) {
      glyph = "✗";
      cls = "bn-pipeline-avail-error";
      label = t("pipeline.glyph.unavailable");
    } else {
      glyph = "—";
      cls = "bn-pipeline-avail-skip";
      label = t("pipeline.glyph.skipped");
    }
    return (
      <>
        <span aria-hidden="true" className={`bn-pipeline-glyph ${cls}`}>
          {glyph}
        </span>
        <span className="bn-sr-only">{label}</span>
      </>
    );
  };

  // Quality glyph cell — empty when the row can't run (cli.py _quality_glyph).
  const qualityCell = (row: ModelAvailability) => {
    if (!row.available) return null;
    if (row.quality == null) {
      return (
        <>
          <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-untested">
            ?
          </span>
          <span className="bn-sr-only">{t("pipeline.quality.glyph.untested")}</span>
        </>
      );
    }
    return (
      <>
        <span
          aria-hidden="true"
          className={`bn-pipeline-glyph bn-pipeline-quality-${row.quality}`}
        >
          {QUALITY_GLYPH[row.quality]}
        </span>
        <span className="bn-sr-only">
          {t(`pipeline.quality.glyph.${row.quality}`, { defaultValue: row.quality })}
        </span>
      </>
    );
  };

  // Why text — failure reason (✗/—), editorial caveat (✓⚠), untested
  // explanation (✓?), or empty for ✓●/✓○ (cli.py _why_text).
  const whyText = (row: ModelAvailability): string => {
    if (!row.available) {
      return row.reason_key ? t(row.reason_key, { defaultValue: row.reason_key }) : "";
    }
    if (row.quality == null) return t("pipeline.quality.untested");
    if ((row.quality === "marginal" || row.quality === "avoid") && row.quality_note) {
      return t(row.quality_note, { defaultValue: row.quality_note });
    }
    return "";
  };

  // Visible qualifier badge — "default" only. "current" is carried visually by
  // the selection wash (.bn-pipeline-model-row[aria-current="true"]) plus
  // aria-current; an sr-only "current" rides the row name for AT robustness
  // (aria-current on a <tr> is unreliably announced).
  const defaultBadge = (row: ModelAvailability): string =>
    row.default ? ` (${t("pipeline.qualifier.default")})` : "";

  const groups = buildStageGroups(data.catalogue);

  return (
    <div className="bn-pipeline-view">
      <p className="bn-setting-description">{t("pipeline.intro")}</p>
      <div className="bn-pipeline-key">
        <div className="bn-pipeline-key-group">
          <span className="bn-pipeline-key-label">{t("pipeline.column.availability")}</span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-avail-ok">✓</span>{" "}
            {t("pipeline.glyph.available")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-avail-error">✗</span>{" "}
            {t("pipeline.glyph.unavailable")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-avail-skip">—</span>{" "}
            {t("pipeline.glyph.skipped")}
          </span>
        </div>
        <div className="bn-pipeline-key-group">
          <span className="bn-pipeline-key-label">{t("pipeline.column.quality")}</span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-excellent">●</span>{" "}
            {t("pipeline.quality.glyph.excellent")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-good">○</span>{" "}
            {t("pipeline.quality.glyph.good")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-marginal">⚠</span>{" "}
            {t("pipeline.quality.glyph.marginal")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-avoid">✗</span>{" "}
            {t("pipeline.quality.glyph.avoid")}
          </span>
          <span className="bn-pipeline-key-item">
            <span aria-hidden="true" className="bn-pipeline-glyph bn-pipeline-quality-untested">?</span>{" "}
            {t("pipeline.quality.glyph.untested")}
          </span>
        </div>
        <div className="bn-pipeline-key-group">
          <span className="bn-pipeline-key-item">
            <em className="bn-pipeline-key-italic">{t("pipeline.key.italic_label")}</em> ={" "}
            {t("pipeline.key.synthesised")}
          </span>
        </div>
      </div>
      {groups.map(({ names, sel }, gi) => (
        <section className="bn-pipeline-stage-group" key={sel.id}>
          <h3
            className="bn-pipeline-stage-group-heading"
            id={`pipeline-group-${sel.id}`}
          >
            {names.join(", ").toUpperCase()}
          </h3>
          <table
            className="bn-pipeline-matrix"
            aria-labelledby={`pipeline-group-${sel.id}`}
          >
            <colgroup>
              <col className="bn-pipeline-col-model" />
              <col className="bn-pipeline-col-avail" />
              <col className="bn-pipeline-col-quality" />
              <col className="bn-pipeline-col-notes" />
            </colgroup>
            <thead>
              <tr>
                {/* Visible Model/Notes labels on the first table only; the glyph
                    columns stay sr-only (the key above explains ✓ / ● etc.).
                    table-layout:fixed aligns these over every table below. */}
                <th
                  scope="col"
                  className={gi === 0 ? "bn-pipeline-col-head" : "bn-sr-only"}
                >
                  {t("pipeline.column.model")}
                </th>
                <th scope="col" className="bn-sr-only">
                  {t("pipeline.column.availability")}
                </th>
                <th scope="col" className="bn-sr-only">
                  {t("pipeline.column.quality")}
                </th>
                <th
                  scope="col"
                  className={gi === 0 ? "bn-pipeline-col-head" : "bn-sr-only"}
                >
                  {t("pipeline.column.notes")}
                </th>
              </tr>
            </thead>
            {byProvider(sel.alternatives ?? []).map((rows, gi) => {
              const { collapsed, rep } = collapseProvider(rows);
              const pid = rep.provider_id;
              if (collapsed) {
                const isCurrent =
                  rep.provider_id === sel.chosen_id &&
                  rep.model_id === sel.chosen_model_id;
                const badge = defaultBadge(rep);
                return (
                  <tbody key={`${pid}-${gi}`}>
                    <tr
                      className="bn-pipeline-model-row"
                      aria-current={isCurrent ? "true" : undefined}
                    >
                      <th
                        scope="row"
                        className="bn-pipeline-row-name bn-pipeline-row-name-provider"
                      >
                        {providerLabel(rep)}
                        {badge && <span className="bn-pipeline-badge">{badge}</span>}
                        {isCurrent && (
                          <span className="bn-sr-only">
                            {" "}
                            ({t("pipeline.qualifier.current")})
                          </span>
                        )}
                      </th>
                      <td className="bn-pipeline-avail-cell">{availCell(rep)}</td>
                      <td className="bn-pipeline-quality-cell">{qualityCell(rep)}</td>
                      <td className="bn-pipeline-why-cell">{whyText(rep)}</td>
                    </tr>
                  </tbody>
                );
              }
              return (
                <tbody key={`${pid}-${gi}`}>
                  <tr className="bn-pipeline-provider-heading">
                    <th scope="rowgroup" colSpan={4}>
                      {providerLabel(rep)}
                    </th>
                  </tr>
                  {rows.map((row, ri) => {
                    const isCurrent =
                      row.provider_id === sel.chosen_id &&
                      row.model_id === sel.chosen_model_id;
                    const badge = defaultBadge(row);
                    return (
                      <tr
                        key={`${pid}-${row.model_id ?? "—"}-${ri}`}
                        className={`bn-pipeline-model-row${
                          row.synthesised ? " bn-pipeline-synthesised-row" : ""
                        }`}
                        aria-current={isCurrent ? "true" : undefined}
                      >
                        <th scope="row" className="bn-pipeline-row-name">
                          {row.display}
                          {badge && <span className="bn-pipeline-badge">{badge}</span>}
                          {isCurrent && (
                            <span className="bn-sr-only">
                              {" "}
                              ({t("pipeline.qualifier.current")})
                            </span>
                          )}
                          {row.synthesised && row.provider_id === "azure" && (
                            <span className="bn-sr-only">
                              {" "}
                              ({t("pipeline.qualifier.your_deployment")})
                            </span>
                          )}
                        </th>
                        <td className="bn-pipeline-avail-cell">{availCell(row)}</td>
                        <td className="bn-pipeline-quality-cell">{qualityCell(row)}</td>
                        <td className="bn-pipeline-why-cell">{whyText(row)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              );
            })}
          </table>
        </section>
      ))}
      <p className="bn-pipeline-host">
        {host.os} {host.arch}
        {host.memory_gb !== null ? ` · ${host.memory_gb} GB` : ""}
        {" · "}
        {t("pipeline.keys")}: {keysOn.length > 0 ? keysOn.join(", ") : t("pipeline.keysNone")}
        {" · "}
        {t("pipeline.ollama")}: {host.ollama_running ? t("pipeline.running") : t("pipeline.notDetected")}
      </p>
    </div>
  );
}

// ── SettingsModal ─────────────────────────────────────────────────────────

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const { t } = useTranslation("settings");
  const [activeId, setActiveId] = useState("general");

  // Reset to General when reopening.
  const prevOpen = useRef(open);
  useEffect(() => {
    if (open && !prevOpen.current) {
      setActiveId("general");
    }
    prevOpen.current = open;
  }, [open]);

  // Build translated nav items.
  const navItems: NavItem[] = NAV_KEYS.map((k) =>
    k.hasChildren
      ? {
          id: k.id,
          label: t(k.labelKey),
          children: CONFIG_DATA.map((cat) => ({ id: `config-${cat.id}`, label: t(cat.labelKey) })),
        }
      : { id: k.id, label: t(k.labelKey) },
  );

  let content: React.ReactNode;
  if (activeId === "general") {
    content = <GeneralSection />;
  } else if (activeId === "project") {
    content = <StubSection description={t("settingsNav.projectStub")} />;
  } else if (activeId === "profile") {
    content = <StubSection description={t("settingsNav.profileStub")} />;
  } else if (activeId === "api-keys") {
    content = <StubSection description={t("settingsNav.apiKeysStub")} />;
  } else if (activeId.startsWith("config-")) {
    content = <ConfigSection categoryId={activeId} />;
  } else if (activeId === "pipeline") {
    content = <PipelineSection />;
  } else {
    content = null;
  }

  return (
    <ModalNav
      open={open}
      onClose={onClose}
      title={t("heading")}
      items={navItems}
      activeId={activeId}
      onSelect={setActiveId}
      className="settings-modal"
      testId="bn-settings-overlay"
      titleId="settings-modal-title"
    >
      {content}
    </ModalNav>
  );
}
