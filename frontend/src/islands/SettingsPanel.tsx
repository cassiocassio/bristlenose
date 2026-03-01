/**
 * SettingsPanel — React island for the Settings tab.
 *
 * Top section: appearance radio buttons (auto/light/dark).
 * Bottom section: read-only configuration reference — every configurable
 * constant, environment variable, and default value in the codebase,
 * grouped by category with file paths and valid options.
 */

import { useCallback, useEffect, useRef, useState } from "react";

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
// Configuration reference data
// ---------------------------------------------------------------------------

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
      {
        label: "Provider",
        envVar: "BRISTLENOSE_LLM_PROVIDER",
        default: "anthropic",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["anthropic", "openai", "azure", "google", "local"],
      },
      {
        label: "Model",
        envVar: "BRISTLENOSE_LLM_MODEL",
        default: "claude-sonnet-4-20250514",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Temperature",
        envVar: "BRISTLENOSE_LLM_TEMPERATURE",
        default: "0.1",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["0.0\u2013" + "1.0"],
      },
      {
        label: "Max output tokens",
        envVar: "BRISTLENOSE_LLM_MAX_TOKENS",
        default: "32768",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Concurrency",
        envVar: "BRISTLENOSE_LLM_CONCURRENCY",
        default: "3",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["1\u201310"],
      },
      {
        label: "Claude API key",
        envVar: "BRISTLENOSE_ANTHROPIC_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        label: "ChatGPT API key",
        envVar: "BRISTLENOSE_OPENAI_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        label: "Gemini API key",
        envVar: "BRISTLENOSE_GOOGLE_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        label: "Azure API key",
        envVar: "BRISTLENOSE_AZURE_API_KEY",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
        sensitive: true,
      },
      {
        label: "Azure endpoint",
        envVar: "BRISTLENOSE_AZURE_ENDPOINT",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Azure deployment",
        envVar: "BRISTLENOSE_AZURE_DEPLOYMENT",
        default: "(not set)",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Azure API version",
        envVar: "BRISTLENOSE_AZURE_API_VERSION",
        default: "2024-10-21",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Ollama URL",
        envVar: "BRISTLENOSE_LOCAL_URL",
        default: "http://localhost:11434/v1",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Ollama model",
        envVar: "BRISTLENOSE_LOCAL_MODEL",
        default: "llama3.2:3b",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
    ],
  },
  {
    id: "transcription",
    label: "Transcription",
    settings: [
      {
        label: "Backend",
        envVar: "BRISTLENOSE_WHISPER_BACKEND",
        default: "auto",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["auto", "mlx", "faster-whisper"],
      },
      {
        label: "Model",
        envVar: "BRISTLENOSE_WHISPER_MODEL",
        default: "large-v3-turbo",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Language",
        envVar: "BRISTLENOSE_WHISPER_LANGUAGE",
        default: "en",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["ISO 639 code"],
      },
      {
        label: "Device",
        envVar: "BRISTLENOSE_WHISPER_DEVICE",
        default: "auto",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["auto", "cpu", "cuda"],
      },
      {
        label: "Compute type",
        envVar: "BRISTLENOSE_WHISPER_COMPUTE_TYPE",
        default: "int8",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["int8", "float16", "float32"],
      },
      {
        label: "Audio extraction concurrency",
        envVar: "_DEFAULT_CONCURRENCY",
        default: "4",
        file: "extract_audio.py",
        filePath: "bristlenose/stages/extract_audio.py",
      },
    ],
  },
  {
    id: "privacy",
    label: "Privacy",
    settings: [
      {
        label: "PII redaction",
        envVar: "BRISTLENOSE_PII_ENABLED",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        label: "PII LLM pass",
        envVar: "BRISTLENOSE_PII_LLM_PASS",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        label: "Custom names to redact",
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
    label: "Quotes",
    settings: [
      {
        label: "Min quote words",
        envVar: "BRISTLENOSE_MIN_QUOTE_WORDS",
        default: "5",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Speaker merge gap",
        envVar: "BRISTLENOSE_MERGE_SPEAKER_GAP_SECONDS",
        default: "2.0",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["seconds"],
      },
      {
        label: "Quote sequence gap",
        envVar: "SEQUENCE_GAP_SECONDS",
        default: "17.5",
        file: "models.py",
        filePath: "bristlenose/analysis/models.py",
        options: ["seconds"],
      },
      {
        label: "LLM failure threshold",
        envVar: "_FAIL_THRESHOLD",
        default: "3",
        file: "quote_extraction.py",
        filePath: "bristlenose/stages/quote_extraction.py",
      },
      {
        label: "AutoCode batch size",
        envVar: "BATCH_SIZE",
        default: "25",
        file: "autocode.py",
        filePath: "bristlenose/server/autocode.py",
      },
    ],
  },
  {
    id: "analysis",
    label: "Analysis",
    settings: [
      {
        label: "Top N signals",
        envVar: "DEFAULT_TOP_N",
        default: "12",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Top N signals (generic)",
        envVar: "DEFAULT_TOP_N",
        default: "12",
        file: "generic_signals.py",
        filePath: "bristlenose/analysis/generic_signals.py",
      },
      {
        label: "Top N for elaboration",
        envVar: "DEFAULT_TOP_N",
        default: "10",
        file: "elaboration.py",
        filePath: "bristlenose/server/elaboration.py",
      },
      {
        label: "Min quotes per cell",
        envVar: "MIN_QUOTES_PER_CELL",
        default: "2",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Strong: concentration >",
        envVar: "hardcoded",
        default: "2",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Strong: participants \u2265",
        envVar: "hardcoded",
        default: "5",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Strong: quotes \u2265",
        envVar: "hardcoded",
        default: "6",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Moderate: concentration >",
        envVar: "hardcoded",
        default: "1.5",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Moderate: participants \u2265",
        envVar: "hardcoded",
        default: "3",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
      {
        label: "Moderate: quotes \u2265",
        envVar: "hardcoded",
        default: "4",
        file: "signals.py",
        filePath: "bristlenose/analysis/signals.py",
      },
    ],
  },
  {
    id: "autocode",
    label: "AutoCode",
    settings: [
      {
        label: "Default lower threshold",
        envVar: "DEFAULT_LOWER",
        default: "0.30",
        file: "ThresholdReviewModal.tsx",
        filePath: "frontend/src/components/ThresholdReviewModal.tsx",
        options: ["0.0\u20131.0"],
      },
      {
        label: "Default upper threshold",
        envVar: "DEFAULT_UPPER",
        default: "0.70",
        file: "ThresholdReviewModal.tsx",
        filePath: "frontend/src/components/ThresholdReviewModal.tsx",
        options: ["0.0\u20131.0"],
      },
      {
        label: "Slider step",
        envVar: "STEP",
        default: "0.05",
        file: "DualThresholdSlider.tsx",
        filePath: "frontend/src/components/DualThresholdSlider.tsx",
      },
      {
        label: "Slider min gap",
        envVar: "MIN_GAP",
        default: "0.05",
        file: "DualThresholdSlider.tsx",
        filePath: "frontend/src/components/DualThresholdSlider.tsx",
      },
      {
        label: "Histogram bins",
        envVar: "NUM_BINS",
        default: "20",
        file: "ConfidenceHistogram.tsx",
        filePath: "frontend/src/components/ConfidenceHistogram.tsx",
      },
    ],
  },
  {
    id: "display",
    label: "Display",
    settings: [
      {
        label: "Search min characters",
        envVar: "hardcoded",
        default: "3",
        file: "filter.ts",
        filePath: "frontend/src/utils/filter.ts",
      },
      {
        label: "Activity poll interval",
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
    label: "Pipeline",
    settings: [
      {
        label: "Project name",
        envVar: "BRISTLENOSE_PROJECT_NAME",
        default: "User Research",
        file: ".env",
        filePath: "bristlenose/config.py",
      },
      {
        label: "Write intermediate files",
        envVar: "BRISTLENOSE_WRITE_INTERMEDIATE",
        default: "true",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        label: "Skip transcription",
        envVar: "BRISTLENOSE_SKIP_TRANSCRIPTION",
        default: "false",
        file: ".env",
        filePath: "bristlenose/config.py",
        options: ["true", "false"],
      },
      {
        label: "Max sessions before confirm",
        envVar: "_MAX_SESSIONS_NO_CONFIRM",
        default: "16",
        file: "pipeline.py",
        filePath: "bristlenose/pipeline.py",
      },
    ],
  },
  {
    id: "thumbnails",
    label: "Thumbnails",
    settings: [
      {
        label: "Keyframe search window",
        envVar: "_WINDOW_SECONDS",
        default: "180",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["seconds"],
      },
      {
        label: "Fallback frame time",
        envVar: "_FALLBACK_SECONDS",
        default: "60",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["seconds"],
      },
      {
        label: "Thumbnail width",
        envVar: "_THUMB_WIDTH",
        default: "384",
        file: "video.py",
        filePath: "bristlenose/utils/video.py",
        options: ["px"],
      },
      {
        label: "JPEG quality",
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
    label: "Server",
    settings: [
      {
        label: "Server port",
        envVar: "_BRISTLENOSE_PORT",
        default: "8150",
        file: "cli.py",
        filePath: "bristlenose/cli.py",
      },
      {
        label: "Miro access token",
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
    label: "Logging",
    settings: [
      {
        label: "Log level (file)",
        envVar: "BRISTLENOSE_LOG_LEVEL",
        default: "INFO",
        file: ".env",
        filePath: "bristlenose/logging.py",
        options: ["DEBUG", "INFO", "WARNING", "ERROR"],
      },
      {
        label: "Log file max size",
        envVar: "_MAX_BYTES",
        default: "5 MB",
        file: "logging.py",
        filePath: "bristlenose/logging.py",
      },
      {
        label: "Log backup count",
        envVar: "_BACKUP_COUNT",
        default: "2",
        file: "logging.py",
        filePath: "bristlenose/logging.py",
      },
    ],
  },
  {
    id: "timing",
    label: "Timing",
    settings: [
      {
        label: "Min runs before estimate",
        envVar: "_MIN_N_ESTIMATE",
        default: "4",
        file: "timing.py",
        filePath: "bristlenose/timing.py",
      },
      {
        label: "Min runs before \u00b1range",
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
            {cat.label}
          </button>
        ))}
      </div>

      {CONFIG_DATA.map((cat) => (
        <section
          key={cat.id}
          ref={(el) => { sectionRefs.current[cat.id] = el; }}
          className="bn-config-ref-section"
        >
          <h3>{cat.label}</h3>
          {cat.settings.map((s, i) => (
            <div key={`${cat.id}-${i}`} className="bn-config-ref-row">
              <span className="bn-config-ref-label">{s.label}</span>
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
                <code
                  className={`bn-config-ref-envvar${copied === s.envVar ? " copied" : ""}`}
                  onClick={() => handleCopy(s.envVar)}
                  title="Click to copy"
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

      <hr />

      <h2>Configuration reference</h2>
      <ConfigReference />
    </>
  );
}
