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

// ── Types ─────────────────────────────────────────────────────────────────

type Appearance = "auto" | "light" | "dark";

const STORAGE_KEY = "bristlenose-appearance";
const THEME_ATTR = "data-theme";

const APPEARANCE_KEYS: { value: Appearance; labelKey: string }[] = [
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
  label: string;
  envVar: string;
  default: string;
  file: string;
  filePath: string;
  options?: string[];
  sensitive?: boolean;
}

interface SettingCategory {
  id: string;
  label: string;
  settings: SettingRef[];
}

const CONFIG_DATA: SettingCategory[] = [
  {
    id: "llm",
    label: "LLM Provider & Model",
    settings: [
      { label: "Provider", envVar: "BRISTLENOSE_LLM_PROVIDER", default: "anthropic", file: ".env", filePath: "bristlenose/config.py", options: ["anthropic", "openai", "azure", "google", "local"] },
      { label: "Model", envVar: "BRISTLENOSE_LLM_MODEL", default: "claude-sonnet-4-20250514", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Temperature", envVar: "BRISTLENOSE_LLM_TEMPERATURE", default: "0.1", file: ".env", filePath: "bristlenose/config.py", options: ["0.0\u20131.0"] },
      { label: "Max output tokens", envVar: "BRISTLENOSE_LLM_MAX_TOKENS", default: "32768", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Concurrency", envVar: "BRISTLENOSE_LLM_CONCURRENCY", default: "3", file: ".env", filePath: "bristlenose/config.py", options: ["1\u201310"] },
      { label: "Claude API key", envVar: "BRISTLENOSE_ANTHROPIC_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { label: "ChatGPT API key", envVar: "BRISTLENOSE_OPENAI_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { label: "Gemini API key", envVar: "BRISTLENOSE_GOOGLE_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { label: "Azure API key", envVar: "BRISTLENOSE_AZURE_API_KEY", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
      { label: "Azure endpoint", envVar: "BRISTLENOSE_AZURE_ENDPOINT", default: "(not set)", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Azure deployment", envVar: "BRISTLENOSE_AZURE_DEPLOYMENT", default: "(not set)", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Azure API version", envVar: "BRISTLENOSE_AZURE_API_VERSION", default: "2024-10-21", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Ollama URL", envVar: "BRISTLENOSE_LOCAL_URL", default: "http://localhost:11434/v1", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Ollama model", envVar: "BRISTLENOSE_LOCAL_MODEL", default: "llama3.2:3b", file: ".env", filePath: "bristlenose/config.py" },
    ],
  },
  {
    id: "transcription",
    label: "Transcription",
    settings: [
      { label: "Backend", envVar: "BRISTLENOSE_WHISPER_BACKEND", default: "auto", file: ".env", filePath: "bristlenose/config.py", options: ["auto", "mlx", "faster-whisper"] },
      { label: "Model", envVar: "BRISTLENOSE_WHISPER_MODEL", default: "large-v3-turbo", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Language", envVar: "BRISTLENOSE_WHISPER_LANGUAGE", default: "en", file: ".env", filePath: "bristlenose/config.py", options: ["ISO 639 code"] },
      { label: "Device", envVar: "BRISTLENOSE_WHISPER_DEVICE", default: "auto", file: ".env", filePath: "bristlenose/config.py", options: ["auto", "cpu", "cuda"] },
      { label: "Compute type", envVar: "BRISTLENOSE_WHISPER_COMPUTE_TYPE", default: "int8", file: ".env", filePath: "bristlenose/config.py", options: ["int8", "float16", "float32"] },
      { label: "Audio extraction concurrency", envVar: "_DEFAULT_CONCURRENCY", default: "4", file: "extract_audio.py", filePath: "bristlenose/stages/extract_audio.py" },
    ],
  },
  {
    id: "privacy",
    label: "Privacy",
    settings: [
      { label: "PII redaction", envVar: "BRISTLENOSE_PII_ENABLED", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { label: "PII LLM pass", envVar: "BRISTLENOSE_PII_LLM_PASS", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { label: "Custom names to redact", envVar: "BRISTLENOSE_PII_CUSTOM_NAMES", default: "(none)", file: ".env", filePath: "bristlenose/config.py", options: ["comma-separated"] },
    ],
  },
  {
    id: "quotes",
    label: "Quotes",
    settings: [
      { label: "Min quote words", envVar: "BRISTLENOSE_MIN_QUOTE_WORDS", default: "5", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Speaker merge gap", envVar: "BRISTLENOSE_MERGE_SPEAKER_GAP_SECONDS", default: "2.0", file: ".env", filePath: "bristlenose/config.py", options: ["seconds"] },
      { label: "Quote sequence gap", envVar: "SEQUENCE_GAP_SECONDS", default: "17.5", file: "models.py", filePath: "bristlenose/analysis/models.py", options: ["seconds"] },
      { label: "LLM failure threshold", envVar: "_FAIL_THRESHOLD", default: "3", file: "quote_extraction.py", filePath: "bristlenose/stages/quote_extraction.py" },
      { label: "AutoCode batch size", envVar: "BATCH_SIZE", default: "25", file: "autocode.py", filePath: "bristlenose/server/autocode.py" },
    ],
  },
  {
    id: "analysis",
    label: "Analysis",
    settings: [
      { label: "Top N signals", envVar: "DEFAULT_TOP_N", default: "12", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Top N signals (generic)", envVar: "DEFAULT_TOP_N", default: "12", file: "generic_signals.py", filePath: "bristlenose/analysis/generic_signals.py" },
      { label: "Top N for elaboration", envVar: "DEFAULT_TOP_N", default: "10", file: "elaboration.py", filePath: "bristlenose/server/elaboration.py" },
      { label: "Min quotes per cell", envVar: "MIN_QUOTES_PER_CELL", default: "2", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Strong: concentration >", envVar: "hardcoded", default: "2", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Strong: participants \u2265", envVar: "hardcoded", default: "5", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Strong: quotes \u2265", envVar: "hardcoded", default: "6", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Moderate: concentration >", envVar: "hardcoded", default: "1.5", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Moderate: participants \u2265", envVar: "hardcoded", default: "3", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
      { label: "Moderate: quotes \u2265", envVar: "hardcoded", default: "4", file: "signals.py", filePath: "bristlenose/analysis/signals.py" },
    ],
  },
  {
    id: "autocode",
    label: "AutoCode",
    settings: [
      { label: "Default lower threshold", envVar: "DEFAULT_LOWER", default: "0.30", file: "ThresholdReviewModal.tsx", filePath: "frontend/src/components/ThresholdReviewModal.tsx", options: ["0.0\u20131.0"] },
      { label: "Default upper threshold", envVar: "DEFAULT_UPPER", default: "0.70", file: "ThresholdReviewModal.tsx", filePath: "frontend/src/components/ThresholdReviewModal.tsx", options: ["0.0\u20131.0"] },
      { label: "Slider step", envVar: "STEP", default: "0.05", file: "DualThresholdSlider.tsx", filePath: "frontend/src/components/DualThresholdSlider.tsx" },
      { label: "Slider min gap", envVar: "MIN_GAP", default: "0.05", file: "DualThresholdSlider.tsx", filePath: "frontend/src/components/DualThresholdSlider.tsx" },
      { label: "Histogram bins", envVar: "NUM_BINS", default: "20", file: "ConfidenceHistogram.tsx", filePath: "frontend/src/components/ConfidenceHistogram.tsx" },
    ],
  },
  {
    id: "display",
    label: "Display",
    settings: [
      { label: "Search min characters", envVar: "hardcoded", default: "3", file: "filter.ts", filePath: "frontend/src/utils/filter.ts" },
      { label: "Activity poll interval", envVar: "POLL_INTERVAL", default: "2000", file: "ActivityChipStack.tsx", filePath: "frontend/src/components/ActivityChipStack.tsx", options: ["ms"] },
    ],
  },
  {
    id: "pipeline",
    label: "Pipeline",
    settings: [
      { label: "Project name", envVar: "BRISTLENOSE_PROJECT_NAME", default: "User Research", file: ".env", filePath: "bristlenose/config.py" },
      { label: "Write intermediate files", envVar: "BRISTLENOSE_WRITE_INTERMEDIATE", default: "true", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { label: "Skip transcription", envVar: "BRISTLENOSE_SKIP_TRANSCRIPTION", default: "false", file: ".env", filePath: "bristlenose/config.py", options: ["true", "false"] },
      { label: "Max sessions before confirm", envVar: "_MAX_SESSIONS_NO_CONFIRM", default: "16", file: "pipeline.py", filePath: "bristlenose/pipeline.py" },
    ],
  },
  {
    id: "thumbnails",
    label: "Thumbnails",
    settings: [
      { label: "Keyframe search window", envVar: "_WINDOW_SECONDS", default: "180", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["seconds"] },
      { label: "Fallback frame time", envVar: "_FALLBACK_SECONDS", default: "60", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["seconds"] },
      { label: "Thumbnail width", envVar: "_THUMB_WIDTH", default: "384", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["px"] },
      { label: "JPEG quality", envVar: "_THUMB_QUALITY", default: "5", file: "video.py", filePath: "bristlenose/utils/video.py", options: ["2 (best) \u2013 31 (worst)"] },
    ],
  },
  {
    id: "server",
    label: "Server",
    settings: [
      { label: "Server port", envVar: "_BRISTLENOSE_PORT", default: "8150", file: "cli.py", filePath: "bristlenose/cli.py" },
      { label: "Miro access token", envVar: "BRISTLENOSE_MIRO_ACCESS_TOKEN", default: "(not set)", file: ".env", filePath: "bristlenose/config.py", sensitive: true },
    ],
  },
  {
    id: "logging",
    label: "Logging",
    settings: [
      { label: "Log level (file)", envVar: "BRISTLENOSE_LOG_LEVEL", default: "INFO", file: ".env", filePath: "bristlenose/logging.py", options: ["DEBUG", "INFO", "WARNING", "ERROR"] },
      { label: "Log file max size", envVar: "_MAX_BYTES", default: "5 MB", file: "logging.py", filePath: "bristlenose/logging.py" },
      { label: "Log backup count", envVar: "_BACKUP_COUNT", default: "2", file: "logging.py", filePath: "bristlenose/logging.py" },
    ],
  },
  {
    id: "timing",
    label: "Timing",
    settings: [
      { label: "Min runs before estimate", envVar: "_MIN_N_ESTIMATE", default: "4", file: "timing.py", filePath: "bristlenose/timing.py" },
      { label: "Min runs before \u00b1range", envVar: "_MIN_N_RANGE", default: "8", file: "timing.py", filePath: "bristlenose/timing.py" },
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
          <span className="bn-config-ref-label">{s.label}</span>
          <code className="bn-config-ref-value">
            {s.sensitive ? "\u2022\u2022\u2022\u2022\u2022\u2022" : s.default}
          </code>
          <span className="bn-config-ref-file" title={s.filePath}>
            {s.file}
          </span>
          <span className="bn-config-ref-meta">
            <code
              className={`bn-config-ref-envvar${copied === s.envVar ? " copied" : ""}`}
              onClick={() => handleCopy(s.envVar)}
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
          children: CONFIG_DATA.map((cat) => ({ id: `config-${cat.id}`, label: cat.label })),
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
