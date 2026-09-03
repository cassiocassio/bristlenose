# Platform Text Map

Inventory of all user-facing text in Bristlenose, categorised by which platform sees it. Used by the user-documentation-review agent to verify platform correctness, by translators to know which keys need desktop variants, and by contributors to decide whether new text needs `dt()` or `ct()` wrapping.

**Last updated**: 21 Aug 2026 — **counts regenerated from `bristlenose/locales/en/*.json`**, which is what the previous note asked for and nobody had done. Every number below is measured, not estimated; the Desktop-only table is now the full 22-section inventory rather than an 8-row sample. Regenerate the same way after any locale change (`scripts/check-locales.py` will not tell you these have drifted — it diffs locale key sets against en, and a stale count in a doc is invisible to it).

---

## How platform forking works

Three helpers in `frontend/src/utils/platformTranslation.ts`:

| Helper | Behaviour | Use for |
|---|---|---|
| `t()` | Standard i18next — same text everywhere | Shared content (both platforms) |
| `dt(t, key)` | Checks `desktop:` namespace first, falls back to base key | Platform-forked content (different wording per platform) |
| `ct(t, key)` | Returns translation on CLI, `null` on desktop | CLI-only content (hidden from desktop users) |

Platform detection: `isDesktop()` reads `data-platform="desktop"` from `<html>`, set by the server when launched from the macOS desktop app. Memoised after first read.

Desktop namespace: `desktop.json` locale files, loaded conditionally by `i18n/index.ts` only when `isDesktop()` is true — **and loaded natively by `I18n.swift` too** (`namespaces = ["common", "settings", "enums", "desktop"]`), which is the half that matters most here. Several sections in the table below have **zero** React call sites and exist only for Swift (`chrome.*`, `aiConsent.*`, `sessionsPopover.*`, `settingsTabs.*`, `accounts.*`). Reading this doc as React-scoped is how the Settings ▸ Accounts pane shipped unlocalised on 18 Aug 2026: a native-only view whose author had no reason to think this map applied. It does — the decision tree at the end terminates at "desktop only → write in `desktop.json` directly", and that branch is where native panes land.

---

## Shared (both platforms)

Text in `common.json`, `settings.json`, `enums.json`, and `server.json` that renders identically on CLI serve mode and the desktop app.

| Namespace | Key count | Content |
|---|---|---|
| `common.json` | 539 | Nav labels, buttons, search, quotes UI, help sections (signals, codebook, privacy factual content, shortcuts, acknowledgements), export labels, toolbar, feedback, the New badge |
| `settings.json` | 179 | Settings modal (appearance, language), config reference headings — **and the whole `pipeline.reasons.*` / `pipeline.quality.*` block the pipeline view renders**, which is why this is 179 and not the ~20 previously claimed |
| `enums.json` | 11 | Sentiment display names, provider labels |
| `server.json` | 16 | Server health check labels, plus the `statusPage.*` block behind "Nothing to see here, yet." |

**i18n**: all 21 full locales (+ the `zh-Hant-HK` override fork).

---

## Desktop-only

Keys in `desktop.json` that only render inside the macOS app shell. CLI serve mode never loads the `desktop` namespace.

All 22 sections, measured 21 Aug 2026. **635 keys.**

| Section | Key count | Content |
|---|---|---|
| `menu.*` | 128 | macOS menu bar: App, File, Edit, View, Project, Folder, Codes, Quotes, Video, Help |
| `cloudImport.*` | 122 | Teams / Google Meet / Zoom import window: sources, filters, plan refusals, batch outcomes, the restored-empty state |
| `chrome.*` | 103 | Server status ("Starting server…"), project panels, drag-and-drop prompts, re-analyse confirmations, name placeholders |
| `ollamaSetup.*` | 43 | Local-model download and setup flow |
| `llmSettings.*` | 33 | Provider pane: keys, models, Azure fields |
| `pipeline.*` | 35 | Run status pills, diagnostic popover categories, tooltips, overflow plurals |
| `mcpAgents.*` | 31 | Settings ▸ MCP Agents: the projects register, exposure states, extension install |
| `toolbar.*` | 23 | Native toolbar labels with keyboard shortcut hints |
| `aiConsent.*` | 20 | First-run cloud provider consent dialog |
| `accounts.*` | 20 | Settings ▸ Accounts: connection states, disconnect alert, section footers |
| `connectAgent.*` | 16 | Connect-an-agent sheet |
| `welcome.*` | 13 | Welcome screen title, subtitle, drop card, three how-it-works steps |
| `miro.*` | 9 | Miro board export sheet |
| `boot.*` | 7 | Launch / sidecar boot states |
| `settingsTabs.*` | 6 | Native Settings window tab labels (General, Appearance, LLM Provider, Transcription, Accounts, MCP Agents) |
| `transcriptionSettings.*` | 5 | Whisper model picker |
| `outOfCredit.*` | 5 | Billing-exhaustion pill and popover |
| `sessionsPopover.*` | 5 | Native session-switcher popover: "All Sessions" row, count subtitle (plural forms; cs/pl/ru/uk carry `_few`/`_many`), empty and failure states. Row title reuses `common.autocode.sessionLabel`; the unnamed-speaker placeholder reuses `common.sessions.speakerPlaceholder.*`; Retry reuses `common.buttons.retry` |
| `availability.*` | 4 | Unmounted-volume / missing-project subtitles |
| `help.*` (overrides) | 3 | Desktop variants for forked keys — **all three are now dead** (see Forked section below) |
| `unsupportedSubset.*` | 3 | Content-area state for a project built from individual files rather than a folder |
| `configReference.*` | 1 | Desktop variant for config reference intro |

**i18n**: all 21 full locales, plus `zh-Hant-HK` as a thin override that inherits via `zh-Hant → en`.

> **Nothing obliges an update when a new `desktop.*` section lands, so this table drifts silently** — the same failure class as the locale allow-lists in `tests/test_pipeline_diagnostic_locale_keys.py`. It went three sweeps stale before this regeneration, at which point it named 8 of 22 sections and undercounted `menu.*` by 32, `chrome.*` by 92, and the namespace total by 40. Regenerate from `bristlenose/locales/en/desktop.json`, don't hand-edit a cell.

---

## CLI-only

Text that only appears in terminal output. Never rendered in the web UI or desktop app.

| Source | Key count | Content | i18n? |
|---|---|---|---|
| `cli.json` | 19 | CLI stage names, progress output, error messages | 21 locales |
| `doctor.json` | 6 | `bristlenose doctor` health check output | 21 locales |
| `pipeline.json` | 4 | Pipeline stage display names | 21 locales |
| `cli.py` help strings | ~30 | Typer `--help` flag descriptions | English only |
| `bristlenose.1` man page | 517 lines | Full man page | English only |
| `preflight.json` | 33 | First-run preflight banners, prompts, error recovery (Whisper download, ffmpeg install table, API-key validation, closing line) | 21 locales (en source; machine-seeded locales pending native review). Reachable in a non-English locale via `bristlenose --lang=<code>` — `cli.py:_lang_callback`. de/es/fr/ja/ko carried raw English here until 21 Aug 2026 |

**Gap**: CLI `--help` strings and the man page are English-only and not wired through i18next. Translating these is a future task (low priority — CLI users overwhelmingly work in English).

---

## Forked via dt()

Keys where `common.json` or `settings.json` has the CLI version and `desktop.json` has a desktop override. The `dt()` helper selects the right one at render time.

| Key | Component | CLI version (common/settings) | Desktop version (desktop.json) | Status |
|---|---|---|---|---|
| `configReference.intro` | `SettingsModal.tsx:456` | "configured via environment variables or a `.env` file" | "Most settings are in the Settings window (Cmd+,)" | **live** — the only surviving `dt()` call site |
| `help.privacy.redactionIntro` | ~~`PrivacySection.tsx`~~ | References `--redact-pii` and `BRISTLENOSE_PII_SCORE_THRESHOLD` | Describes the feature without CLI flags | **dead** — component gone |
| `help.privacy.actionThreshold` | ~~`PrivacySection.tsx`~~ | Shows `BRISTLENOSE_PII_SCORE_THRESHOLD=0.5` | Says "try 0.5" without the env var name | **dead** — component gone |
| `help.contributing.beforeBody` | ~~`ContributingSection.tsx`~~ | Inline terminal commands | Single link to the GitHub contributing guide | **dead** — component gone |

**Three of the four rows are dead** (verified 21 Aug 2026). `3f49d170` retired the SPA help modal and deleted `PrivacySection.tsx` / `ContributingSection.tsx`; the keys stayed, in `en` and in all 20 locale `desktop.json` files, and nothing reported it — a key that exists on both sides and is read by nobody is invisible to `check-locales.py` from either direction. The only remaining references are a doc comment in `platformTranslation.ts` and its test fixture, which is also why a call-site sweep that matches on the bare leaf name will not flag them.

**Decision owed**: delete the three dead `help.*` overrides (and their 20 locale copies), or restore the surface that read them. Leaving them is the option that keeps translators maintaining strings no user can reach.

---

## CLI-hideable via ct()

`ct()` has **one** production call site: `CodebookPanel.tsx:1059` (`ct(t, "codebook.browseCodebooks")` — the Codebook Library entry point, hidden on desktop). The rest below are still candidates.

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
| Shared | 745 | 21 locales (+ HK override) | `t()` |
| Desktop-only | 638 | 21 locales (+ HK override) | `desktop.json` namespace |
| CLI-only (translated) | 62 | 21 locales | `cli.json` / `doctor.json` / `pipeline.json` / `preflight.json` |
| CLI-only (untranslated) | ~30 + man page | English only | Typer help strings / `bristlenose.1` |
| Forked | 4 declared / **1 live** | 21 locales (+ HK override) | `dt()` + `desktop.json` override |
| CLI-hideable | 1 active | 21 locales | `ct()` |

**Total translated keys: 1,445** across the nine namespaces (measured 21 Aug 2026). Shared = `common` 539 + `settings` 179 + `enums` 11 + `server` 16. CLI-only translated = `cli` 19 + `doctor` 6 + `pipeline` 4 + `preflight` 33.

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
