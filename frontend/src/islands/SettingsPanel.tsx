/**
 * SettingsPanel — React island for the Settings tab.
 *
 * Top section: appearance radio buttons (auto/light/dark).
 * Bottom section: read-only configuration reference — every configurable
 * constant, environment variable, and default value in the codebase,
 * grouped by category with file paths and valid options.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LOCALES, type Locale } from "../i18n";
import { setLocale, useLocaleStore } from "../i18n/LocaleStore";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Appearance = "auto" | "light" | "dark";

const STORAGE_KEY = "bristlenose-appearance";
const THEME_ATTR = "data-theme";

const OPTIONS: { value: Appearance; labelKey: string }[] = [
  { value: "auto", labelKey: "appearance.auto" },
  { value: "light", labelKey: "appearance.light" },
  { value: "dark", labelKey: "appearance.dark" },
];

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

// ---------------------------------------------------------------------------
// Configuration reference data
// ---------------------------------------------------------------------------

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
      {
        labelKey: "configReference.settings.llm.provider",
        envVar: "BRISTLENOSE_LLM_PROVIDER",
        default: "anthropic",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["anthropic", "openai", "azure", "google", "local"],
      },
      {
        labelKey: "configReference.settings.llm.model",
        envVar: "BRISTLENOSE_LLM_MODEL",
        default: "claude-sonnet-4-20250514",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.temperature",
        envVar: "BRISTLENOSE_LLM_TEMPERATURE",
        default: "0.1",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["0.0\u2013" + "1.0"],
      },
      {
        labelKey: "configReference.settings.llm.maxTokens",
        envVar: "BRISTLENOSE_LLM_MAX_TOKENS",
        default: "32768",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.concurrency",
        envVar: "BRISTLENOSE_LLM_CONCURRENCY",
        default: "3",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["1\u201310"],
      },
      {
        labelKey: "configReference.settings.llm.claudeKey",
        envVar: "BRISTLENOSE_ANTHROPIC_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        labelKey: "configReference.settings.llm.chatgptKey",
        envVar: "BRISTLENOSE_OPENAI_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        labelKey: "configReference.settings.llm.geminiKey",
        envVar: "BRISTLENOSE_GOOGLE_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        labelKey: "configReference.settings.llm.azureKey",
        envVar: "BRISTLENOSE_AZURE_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        labelKey: "configReference.settings.llm.azureEndpoint",
        envVar: "BRISTLENOSE_AZURE_ENDPOINT",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.azureDeployment",
        envVar: "BRISTLENOSE_AZURE_DEPLOYMENT",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.azureApiVersion",
        envVar: "BRISTLENOSE_AZURE_API_VERSION",
        default: "2024-10-21",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.ollamaUrl",
        envVar: "BRISTLENOSE_LOCAL_URL",
        default: "http://localhost:11434/v1",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.llm.ollamaModel",
        envVar: "BRISTLENOSE_LOCAL_MODEL",
        default: "llama3.2:3b",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
    ],
  },
  {
    id: "transcription",
    labelKey: "configReference.categories.transcription",
    settings: [
      {
        labelKey: "configReference.settings.transcription.backend",
        envVar: "BRISTLENOSE_WHISPER_BACKEND",
        default: "auto",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["auto", "mlx", "faster-whisper"],
      },
      {
        labelKey: "configReference.settings.transcription.model",
        envVar: "BRISTLENOSE_WHISPER_MODEL",
        default: "large-v3-turbo",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.transcription.language",
        envVar: "BRISTLENOSE_WHISPER_LANGUAGE",
        default: "en",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["ISO 639 code"],
      },
      {
        labelKey: "configReference.settings.transcription.device",
        envVar: "BRISTLENOSE_WHISPER_DEVICE",
        default: "auto",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["auto", "cpu", "cuda"],
      },
      {
        labelKey: "configReference.settings.transcription.computeType",
        envVar: "BRISTLENOSE_WHISPER_COMPUTE_TYPE",
        default: "int8",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["int8", "float16", "float32"],
      },
      {
        labelKey: "configReference.settings.transcription.audioConcurrency",
        envVar: "_DEFAULT_CONCURRENCY",
        default: "4",
        file: "extract_audio.py",
        filePath: "bristlenose/stages/extract_audio.py",
      },
    ],
  },
  {
    id: "privacy",
    labelKey: "configReference.categories.privacy",
    settings: [
      {
        labelKey: "configReference.settings.privacy.piiRedaction",
        envVar: "BRISTLENOSE_PII_ENABLED",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        labelKey: "configReference.settings.privacy.piiLlmPass",
        envVar: "BRISTLENOSE_PII_LLM_PASS",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        labelKey: "configReference.settings.privacy.customNames",
        envVar: "BRISTLENOSE_PII_CUSTOM_NAMES",
        default: "(none)",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["comma-separated"],
      },
    ],
  },
  {
    id: "quotes",
    labelKey: "configReference.categories.quotes",
    settings: [
      {
        labelKey: "configReference.settings.quotes.minQuoteWords",
        envVar: "BRISTLENOSE_MIN_QUOTE_WORDS",
        default: "5",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.quotes.speakerMergeGap",
        envVar: "BRISTLENOSE_MERGE_SPEAKER_GAP_SECONDS",
        default: "2.0",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["seconds"],
      },
      {
        labelKey: "configReference.settings.quotes.quoteSequenceGap",
        envVar: "SEQUENCE_GAP_SECONDS",
        default: "17.5",
        file: "models.py",
        filePath: "bristlenose/analysis/models.py",
        options: ["seconds"],
      },
      {
        labelKey: "configReference.settings.quotes.llmFailureThreshold",
        envVar: "_FAIL_THRESHOLD",
        default: "3",
        file: "quote_extraction.py",
        filePath: "bristlenose/stages/quote_extraction.py",
      },
      {
        labelKey: "configReference.settings.quotes.autocodeBatchSize",
        envVar: "BATCH_SIZE",
        default: "25",
        file: "autocode.py",
        filePath: "bristlenose/server/autocode.py",
      },
    ],
  },
  {
    id: "analysis",
    labelKey: "configReference.categories.analysis",
    settings: [
      {
        labelKey: "configReference.settings.analysis.topNSignals",
        envVar: "DEFAULT_TOP_N",
        default: "12",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.topNSignalsGeneric",
        envVar: "DEFAULT_TOP_N",
        default: "12",
        file: "generic_signals.py",
        filePath: "bristlenose/analysis/generic_signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.topNElaboration",
        envVar: "DEFAULT_TOP_N",
        default: "10",
        file: "elaboration.py",
        filePath: "bristlenose/server/elaboration.py",
      },
      {
        labelKey: "configReference.settings.analysis.minQuotesPerCell",
        envVar: "MIN_QUOTES_PER_CELL",
        default: "2",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.strongConcentration",
        envVar: "hardcoded",
        default: "2",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.strongParticipants",
        envVar: "hardcoded",
        default: "5",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.strongQuotes",
        envVar: "hardcoded",
        default: "6",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.moderateConcentration",
        envVar: "hardcoded",
        default: "1.5",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.moderateParticipants",
        envVar: "hardcoded",
        default: "3",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        labelKey: "configReference.settings.analysis.moderateQuotes",
        envVar: "hardcoded",
        default: "4",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
    ],
  },
  {
    id: "autocode",
    labelKey: "configReference.categories.autocode",
    settings: [
      {
        labelKey: "configReference.settings.autocode.defaultLower",
        envVar: "DEFAULT_LOWER",
        default: "0.30",
        file: "ThresholdReviewModal.tsx",
        filePath: "frontend/src/components/ThresholdReviewModal.tsx",
        options: ["0.0\u20131.0"],
      },
      {
        labelKey: "configReference.settings.autocode.defaultUpper",
        envVar: "DEFAULT_UPPER",
        default: "0.70",
        file: "ThresholdReviewModal.tsx",
        filePath: "frontend/src/components/ThresholdReviewModal.tsx",
        options: ["0.0\u20131.0"],
      },
      {
        labelKey: "configReference.settings.autocode.sliderStep",
        envVar: "STEP",
        default: "0.05",
        file: "DualThresholdSlider.tsx",
        filePath: "frontend/src/components/DualThresholdSlider.tsx",
      },
      {
        labelKey: "configReference.settings.autocode.sliderMinGap",
        envVar: "MIN_GAP",
        default: "0.05",
        file: "DualThresholdSlider.tsx",
        filePath: "frontend/src/components/DualThresholdSlider.tsx",
      },
      {
        labelKey: "configReference.settings.autocode.histogramBins",
        envVar: "NUM_BINS",
        default: "20",
        file: "ConfidenceHistogram.tsx",
        filePath: "frontend/src/components/ConfidenceHistogram.tsx",
      },
    ],
  },
  {
    id: "display",
    labelKey: "configReference.categories.display",
    settings: [
      {
        labelKey: "configReference.settings.display.searchMinChars",
        envVar: "hardcoded",
        default: "3",
        file: "filter.ts",
        filePath: "frontend/src/utils/filter.ts",
      },
      {
        labelKey: "configReference.settings.display.activityPollInterval",
        envVar: "POLL_INTERVAL",
        default: "2000",
        file: "ActivityChipStack.tsx",
        filePath: "frontend/src/components/ActivityChipStack.tsx",
        options: ["ms"],
      },
    ],
  },
  {
    id: "pipeline",
    labelKey: "configReference.categories.pipeline",
    settings: [
      {
        labelKey: "configReference.settings.pipeline.projectName",
        envVar: "BRISTLENOSE_PROJECT_NAME",
        default: "User Research",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        labelKey: "configReference.settings.pipeline.writeIntermediate",
        envVar: "BRISTLENOSE_WRITE_INTERMEDIATE",
        default: "true",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        labelKey: "configReference.settings.pipeline.skipTranscription",
        envVar: "BRISTLENOSE_SKIP_TRANSCRIPTION",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        labelKey: "configReference.settings.pipeline.maxSessionsBeforeConfirm",
        envVar: "_MAX_SESSIONS_NO_CONFIRM",
        default: "16",
        file: "pipeline.py",
        filePath: "bristlenose/pipeline.py",
      },
    ],
  },
  {
    id: "thumbnails",
    labelKey: "configReference.categories.thumbnails",
    settings: [
      {
        labelKey: "configReference.settings.thumbnails.keyframeSearchWindow",
        envVar: "_WINDOW_SECONDS",
        default: "180",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["seconds"],
      },
      {
        labelKey: "configReference.settings.thumbnails.fallbackFrameTime",
        envVar: "_FALLBACK_SECONDS",
        default: "60",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["seconds"],
      },
      {
        labelKey: "configReference.settings.thumbnails.thumbnailWidth",
        envVar: "_THUMB_WIDTH",
        default: "384",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["px"],
      },
      {
        labelKey: "configReference.settings.thumbnails.jpegQuality",
        envVar: "_THUMB_QUALITY",
        default: "5",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["2 (best) \u2013 31 (worst)"],
      },
    ],
  },
  {
    id: "server",
    labelKey: "configReference.categories.server",
    settings: [
      {
        labelKey: "configReference.settings.server.serverPort",
        envVar: "_BRISTLENOSE_PORT",
        default: "8150",
        file: "cli.py",
        filePath: "bristlenose/cli.py",
      },
      {
        labelKey: "configReference.settings.server.miroAccessToken",
        envVar: "BRISTLENOSE_MIRO_ACCESS_TOKEN",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
    ],
  },
  {
    id: "logging",
    labelKey: "configReference.categories.logging",
    settings: [
      {
        labelKey: "configReference.settings.logging.logLevel",
        envVar: "BRISTLENOSE_LOG_LEVEL",
        default: "INFO",
        file: ".env",
        filePath: "bristlenose/logging.py",
        options: ["DEBUG", "INFO", "WARNING", "ERROR"],
      },
      {
        labelKey: "configReference.settings.logging.logFileMaxSize",
        envVar: "_MAX_BYTES",
        default: "5 MB",
        file: "logging.py",
        filePath: "bristlenose/logging.py",
      },
      {
        labelKey: "configReference.settings.logging.logBackupCount",
        envVar: "_BACKUP_COUNT",
        default: "2",
        file: "logging.py",
        filePath: "bristlenose/logging.py",
      },
    ],
  },
  {
    id: "timing",
    labelKey: "configReference.categories.timing",
    settings: [
      {
        labelKey: "configReference.settings.timing.minRunsEstimate",
        envVar: "_MIN_N_ESTIMATE",
        default: "4",
        file: "timing.py",
        filePath: "bristlenose/timing.py",
      },
      {
        labelKey: "configReference.settings.timing.minRunsRange",
        envVar: "_MIN_N_RANGE",
        default: "8",
        file: "timing.py",
        filePath: "bristlenose/timing.py",
      },
    ],
  },
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
// ConfigReference — read-only reference grid
// ---------------------------------------------------------------------------

function ConfigReference() {
  const { t } = useTranslation("settings");
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});
  const [copied, setCopied] = useState<string | null>(null);

  const handleChipClick = useCallback((id: string) => {
    const el = sectionRefs.current[id];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(text);
      setTimeout(() => setCopied(null), 1500);
    }).catch(() => {
      // Clipboard unavailable — ignore.
    });
  }, []);

  return (
    <div className="bn-config-ref">
      <p className="bn-config-ref-intro">
        All settings below are configured via environment variables or
        a <code>.env</code> file. They are shown here for reference &mdash; to
        change a value, edit the file shown in each row.
      </p>

      <div className="bn-config-ref-chips">
        {CONFIG_DATA.map((cat) => (
          <button
            key={cat.id}
            className="bn-config-ref-chip"
            onClick={() => handleChipClick(cat.id)}
          >
            {t(cat.labelKey)}
          </button>
        ))}
      </div>

      {CONFIG_DATA.map((cat) => (
        <section
          key={cat.id}
          ref={(el) => { sectionRefs.current[cat.id] = el; }}
          className="bn-config-ref-section"
        >
          <h3>{t(cat.labelKey)}</h3>
          {cat.settings.map((s, i) => (
            <div key={`${cat.id}-${i}`} className="bn-config-ref-row">
              <span className="bn-config-ref-label">{t(s.labelKey)}</span>
              <code className="bn-config-ref-value">
                {s.sensitive ? "\u2022\u2022\u2022\u2022\u2022\u2022" : s.default}
              </code>
              <span
                className="bn-config-ref-file"
                title={s.filePath}
              >
                {s.file}
              </span>
              <span className="bn-config-ref-meta">
                {/* <code> preserves the monospace env-var styling; role=button + keyboard handler make it operable. */}
                <code
                  className={`bn-config-ref-envvar${copied === s.envVar ? " copied" : ""}`}
                  // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role
                  role="button"
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
        </section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SettingsPanel() {
  const { t } = useTranslation("settings");
  const [appearance, setAppearance] = useState<Appearance>(readSaved);
  const { locale } = useLocaleStore();

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

  const handleLocaleChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (SUPPORTED_LOCALES.includes(value as Locale)) {
      void setLocale(value as Locale);
    }
  }, []);

  return (
    <>
      <h2>{t("heading")}</h2>
      <fieldset className="bn-setting-group">
        <legend>{t("appearance.legend")}</legend>
        {OPTIONS.map((opt) => (
          <label key={opt.value} className="bn-radio-label">
            <input
              type="radio"
              name="bn-appearance"
              value={opt.value}
              checked={appearance === opt.value}
              onChange={() => handleChange(opt.value)}
            />
            {" "}{t(opt.labelKey)}
          </label>
        ))}
      </fieldset>

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

      <hr />

      <h2>{t("configReference.heading")}</h2>
      <ConfigReference />
    </>
  );
}
