# Platform Text Map

Inventory of all user-facing text in Bristlenose, categorised by which platform sees it. Used by the user-documentation-review agent to verify platform correctness, by translators to know which keys need desktop variants, and by contributors to decide whether new text needs `dt()` or `ct()` wrapping.

**Last updated**: 26 Mar 2026

---

## How platform forking works

Three helpers in `frontend/src/utils/platformTranslation.ts`:

| Helper | Behaviour | Use for |
|---|---|---|
| `t()` | Standard i18next — same text everywhere | Shared content (both platforms) |
| `dt(t, key)` | Checks `desktop:` namespace first, falls back to base key | Platform-forked content (different wording per platform) |
| `ct(t, key)` | Returns translation on CLI, `null` on desktop | CLI-only content (hidden from desktop users) |

Platform detection: `isDesktop()` reads `data-platform="desktop"` from `<html>`, set by the server when launched from the macOS desktop app. Memoised after first read.

Desktop namespace: `desktop.json` locale files, loaded conditionally by `i18n/index.ts` only when `isDesktop()` is true.

---

## Shared (both platforms)

Text in `common.json`, `settings.json`, `enums.json`, and `server.json` that renders identically on CLI serve mode and the desktop app.

| Namespace | Key count | Content |
|---|---|---|
| `common.json` | ~420 | Nav labels, buttons, search, quotes UI, help sections (signals, codebook, privacy factual content, shortcuts, acknowledgements), export labels, toolbar, feedback |
| `settings.json` | ~20 | Settings modal (appearance, language), config reference headings |
| `enums.json` | ~11 | Sentiment display names, provider labels |
| `server.json` | ~5 | Server health check labels |

**i18n**: all 6 locales (en, es, fr, de, ja, ko).

---

## Desktop-only

Keys in `desktop.json` that only render inside the macOS app shell. CLI serve mode never loads the `desktop` namespace.

| Section | Key count | Content |
|---|---|---|
| `menu.*` | ~96 | macOS menu bar: App, File, Edit, View, Project, Folder, Codes, Quotes, Video, Help |
| `toolbar.*` | ~21 | Native toolbar labels with keyboard shortcut hints |
| `chrome.*` | ~11 | Server status ("Starting server..."), project panels, drag-and-drop prompts |
| `settingsTabs.*` | ~3 | Native Settings window tab labels (Appearance, LLM, Transcription) |
| `aiConsent.*` | ~15 | First-run cloud provider consent dialog |
| `help.*` (overrides) | 3 | Desktop variants for forked keys (see Forked section below) |
| `configReference.*` | 1 | Desktop variant for config reference intro |

**Total**: ~150 keys. **i18n**: all 6 locales.

---

## CLI-only

Text that only appears in terminal output. Never rendered in the web UI or desktop app.

| Source | Key count | Content | i18n? |
|---|---|---|---|
| `cli.json` | ~19 | CLI stage names, progress output, error messages | 6 locales |
| `doctor.json` | ~6 | `bristlenose doctor` health check output | 6 locales |
| `pipeline.json` | ~4 | Pipeline stage display names | 6 locales |
| `cli.py` help strings | ~30 | Typer `--help` flag descriptions | English only |
| `bristlenose.1` man page | 517 lines | Full man page | English only |

**Gap**: CLI `--help` strings and the man page are English-only and not wired through i18next. Translating these is a future task (low priority — CLI users overwhelmingly work in English).

---

## Forked via dt()

Keys where `common.json` or `settings.json` has the CLI version and `desktop.json` has a desktop override. The `dt()` helper selects the right one at render time.

| Key | Component | CLI version (common/settings) | Desktop version (desktop.json) | Why forked |
|---|---|---|---|---|
| `help.privacy.redactionIntro` | `PrivacySection.tsx:16` | References `--redact-pii` flag and `BRISTLENOSE_PII_SCORE_THRESHOLD` env var | Describes the feature neutrally without CLI flags (Settings > Privacy doesn't exist yet) | CLI users enable via flag; desktop users will use a toggle |
| `help.privacy.actionThreshold` | `PrivacySection.tsx:31` | Shows `BRISTLENOSE_PII_SCORE_THRESHOLD=0.5` | Says "try 0.5" without the env var name | Desktop users don't set env vars |
| `help.contributing.beforeBody` | `ContributingSection.tsx:13` | Inline terminal commands (`ruff check .`, `pytest tests/`, `npm run build`) | Single link to GitHub contributing guide | Desktop users aren't running terminal commands |
| `configReference.intro` | `SettingsModal.tsx:376` | "configured via environment variables or a `.env` file" | "Most settings are in the Settings window (Cmd+,)" | Different configuration paradigm |

**i18n**: all 4 keys have desktop variants in all 6 locale `desktop.json` files.

---

## CLI-hideable via ct()

The `ct()` helper is defined, tested, and ready — but has **zero production call sites**. These are candidates for future use when we add text that should only appear in CLI serve mode.

### Identified candidates (not yet implemented)

| Candidate key | Current location | Why hide on desktop |
|---|---|---|
| `help.privacy.actionReview` mentions "pii_summary.txt audit file" | `common.json` | Desktop users won't navigate to hidden files via terminal. Rewrite for desktop: "check the audit log in your project folder" |
| Any future "Run `bristlenose doctor`" help text | Not yet written | Desktop app handles health checks via the menu (Check System Health) |
| Any future "Set `BRISTLENOSE_*` in your `.env`" instructions | Not yet written | Desktop configures via Settings window |
| Any future "Use `--output` to change the output directory" | Not yet written | Desktop uses a folder picker |

---

## Coverage summary

| Category | Keys | i18n coverage | Mechanism |
|---|---|---|---|
| Shared | ~456 | 6 locales | `t()` |
| Desktop-only | ~150 | 6 locales | `desktop.json` namespace |
| CLI-only (translated) | ~29 | 6 locales | `cli.json` / `doctor.json` / `pipeline.json` |
| CLI-only (untranslated) | ~30 + man page | English only | Typer help strings / `bristlenose.1` |
| Forked | 4 | 6 locales | `dt()` + `desktop.json` override |
| CLI-hideable | 0 active | — | `ct()` (ready, unused) |

---

## Adding new help text — decision tree

```
Is this text about a platform-specific mechanism (CLI flag, env var, Settings window, Finder)?
  YES → Does the concept exist on both platforms?
    YES → Use dt(). Write shared version in common.json, desktop override in desktop.json.
    NO, CLI only → Use ct(). Write in common.json, ct() hides it on desktop.
    NO, desktop only → Write in desktop.json directly.
  NO → Use t(). Write in common.json. It's platform-agnostic.
```

When in doubt, start with `t()` (shared). Fork later when the desktop version actually diverges. Don't pre-fork speculatively.
