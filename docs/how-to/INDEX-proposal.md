# Proposal — `bristlenose.app/docs/how-to/` index

**Status:** Proposal for maintainer review · read-only audit, no existing docs restructured
**Date:** 25 Jun 2026
**Scope:** Inventory of every how-to / onboarding / setup / guidance surface in the repo, plus a proposed structure for a future task-oriented how-to section on the marketing site.

> **What this is.** A map of the guidance content that exists today (across `docs/`, the codebase, and the in-product UI), classified by what it covers, where it lives, its format, and whether users can reach it. Then a proposed URL structure for `bristlenose.app/docs/how-to/` with each existing piece mapped to a slot, and the gaps that need net-new writing.
>
> **What this is *not*.** It does not move, rewrite, or restructure any existing doc. The only file it adds is this proposal. Authoring the actual how-to pages, and rendering them to the site, are follow-up steps (the latter in the separate private deploy repo — see "Boundary" below).

---

## 1. Framing — where a how-to section fits

Bristlenose already has a strong **reference** doc (`docs/manual.md` → `manual.html`) and good **explanation** content (the in-app Help modal, `SECURITY.md`, the methodology docs). What it lacks is a home for **task-oriented walkthroughs** — the "I want to do X, give me the numbered steps" guides. That is exactly the [Diátaxis](https://diataxis.fr) "how-to guide" quadrant, and it's the hole `docs/how-to/` should fill.

The design rule that falls out of this:

> **The how-to section does not duplicate the manual.** Where the manual already covers something well (install, the CLI command table, keyboard shortcuts, the privacy model), the how-to guide either doesn't exist or is a short deep-dive that **cross-links back** to the manual. The how-to section's job is the *task* walkthroughs that are missing today — overwhelmingly the **provider-key setup** and **export/share** families.

**Boundary (important).** The marketing site (`bristlenose.app`) is a **separate private deploy repo**. This public repo's job is to hold the **source-of-truth content** as Markdown — exactly as `docs/manual.md` is the source for `manual.html`. So the concrete output of this proposal is: a set of `docs/how-to/<slug>.md` files in *this* repo, which the deploy repo renders to `bristlenose.app/docs/how-to/<slug>.html`. The worked precedent is already in flight: `docs/mockups/miro-setup-help.html` → `docs/how-to/miro-setup.md` → `bristlenose.app/docs/how-to/miro-setup.html`.

**Write against the glossary.** `docs/glossary.md` is the authoritative terminology + tone guide. Provider names in user-facing text use **product** names — "Claude", "ChatGPT", "Azure OpenAI", "Gemini", "Ollama" / "Local" — never the company names. Every new how-to inherits this.

---

## 2. The format template (codified, not invented)

`docs/mockups/miro-setup-help.html` is already a complete, well-structured how-to. Rather than invent a format, the section should **standardise on its skeleton**:

```
Kicker (category)        e.g. "Export · Integrations"
H1                       e.g. "Connect Bristlenose to Miro"
Lead                     one-sentence "what you'll achieve"
"What you get"           outcome preview (screenshot / mini-mockup)
Before you start         requirements / prerequisites list
Recommended path         the one-click / easy route, if any
Manual path              numbered steps (the procedure)
Privacy callout          "where your data goes" (when data leaves the laptop)
Troubleshooting          table: symptom → fix → reference link
Footer                   trademark disclaimers + reference links
```

Not every guide needs every block (a pure local task drops the privacy callout), but the order and vocabulary should be constant so the section reads as one thing. The **Ollama** content (`ollama-setup-popovers.html`) and the **per-provider key** content map onto this skeleton cleanly; `miro-flow.html` supplies an optional "How it works" overview block.

---

## 3. The how-tos index

**Legend**

*Status* — 🟢 Mature (solid user-facing coverage) · 🟡 Partial (exists but thin / scattered / brief) · 🔴 Missing (feature ships, no task-oriented user how-to) · ⏸ Parked (feature not implemented)
*Published today* — ✅ on the site or GitHub · 📱 in-app string only · 🖥 desktop-app only · 🔧 dev-only design doc (not rendered to users) · 📐 unpublished mockup · ⛔ nowhere

### 3a. Getting started

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Install Bristlenose | macOS desktop / Homebrew / Windows / Linux, Gatekeeper, verify | `manual.md` §Install · `INSTALL.md` · `README.md` §Install | md | ✅ | 🟢 |
| Your first run / quickstart | Point at a folder → open report; file types; session pairing | `manual.md` §First run · `README.md` §Quick start · man `EXAMPLES` | md / man | ✅ | 🟢 (CLI) |
| First-run orientation (desktop) | Welcome rail (Add → Analyse → Browse), drop-folder, AI/privacy link | `WelcomeView.swift` · `desktop.welcome.*` | swift | 🖥 | 🟡 (desktop-only) |
| Verify your setup | `bristlenose doctor` health checks | `manual.md` §Verify · `doctor` command | md / cli | ✅ | 🟢 |

### 3b. Set up an AI provider — *the largest cluster, and the largest gap*

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Choose a provider | Claude vs ChatGPT vs Gemini vs Azure vs Ollama — cost / quality / privacy | scattered: `manual.md` §AI provider (lists), `help.privacy.*` (Ollama tradeoff), pipeline quality glyphs | md / 📱 | ✅/📱 | 🟡 (no consolidated comparison) |
| Set up Claude | Sign up → key → `configure claude`; cost | `manual.md` §Claude · `README.md` §Getting an API key · doctor `api_key_missing_anthropic` · `LLMProvider.swift` console link | md / doctor / swift | ✅/🖥 | 🟡 (no step-by-step key acquisition) |
| Set up ChatGPT | platform.openai.com → key → `configure chatgpt` | same pattern as Claude | md / doctor / swift | ✅/🖥 | 🟡 |
| Set up Gemini | aistudio.google.com → key → `configure gemini` | same pattern | md / doctor / swift | ✅/🖥 | 🟡 |
| Set up Azure OpenAI | Endpoint + key + deployment + API version | `manual.md` §Azure · doctor `api_key_missing_azure` · `LLMSettingsView.swift` azure fields | md / doctor / swift | ✅/🖥 | 🟡 (**worst gap** — multi-step Azure-console journey undocumented) |
| Set up Ollama / local models | Install Ollama → pull a model → point Bristlenose at it; RAM/disk tradeoffs | `manual.md` §Ollama · `ollama-setup-popovers.html` (mockup) · desktop auto-install + `AIConsentView` · doctor `ollama_*` fixes · man §Local LLM · CLI `_setup_local_provider` | md / 📐 / swift / doctor / man | ✅/🖥/📐 | 🟡 (no consolidated web how-to; model-choice guidance missing) |
| Where keys are stored / make permanent | Keychain / Secret Service / `.env`; rotation | `manual.md` §Where are keys stored · `README.md` §Making your key permanent · `design-keychain.md` | md | ✅ | 🟢 |

> In-app reality check: in the **React SPA**, a user *cannot* set a key or pick a provider through the UI — the API-Keys settings pane is a **"Coming soon" stub** (`settingsNav.apiKeysStub`); the Config pane is read-only and says "edit the file shown." The full key-setup UI exists **only in the desktop app** (`LLMSettingsView.swift`, with per-provider console deep-links). This makes a published per-provider how-to the canonical reference the SPA can't yet provide in-product.

### 3c. Run an analysis

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Prepare your interviews | Accepted file types; same-stem = one session; folder layout | `manual.md` §First run · man `INPUT FILES` · `bristlenose help workflows` | md / man / cli | ✅ | 🟡 (no narrative prep guide) |
| Run / CLI commands | `run`, `transcribe-only`, `analyze`, `serve`, `status`, `configure`, `doctor` | `manual.md` §CLI commands · man `COMMANDS` · `bristlenose --help` | md / man / cli | ✅ | 🟢 |
| Transcribe-then-analyse workflows | Split runs; smaller models; offline cache (`doctor --fetch`) | `bristlenose help workflows` · man `EXAMPLES` | cli / man | ✅ | 🟢 |
| Redact PII | `--redact-pii`; what it catches/misses; prerequisites | `--redact-pii` flag · `help.privacy.*` (concept) · doctor `spacy_model_missing` / `presidio_missing` | cli / 📱 / doctor | ✅/📱 | 🟡 (flag dead-ends on uninstalled deps; no how-to ties flag → prereqs) |

### 3d. Work with the report (serve mode)

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Read the analysis | Sections vs themes, sentiment, signals, stars/tags/filters | `HelpSection.tsx` / `SignalsSection.tsx` / `CodebookSection.tsx` (`help.*`) · `manual.md` §Core concepts | react / md | 📱/✅ | 🟢 |
| Keyboard shortcuts | Full shortcut reference | `ShortcutsSection.tsx` (`help.shortcuts.*`) · `manual.md` §Keyboard shortcuts | react / md | 📱/✅ | 🟢 |
| Edit quotes / headings / names | In-situ editing in serve mode | `manual.md` §Serve mode (bullet) · in-situ edit gestures | md | ✅ | 🟡 (named, not walked) |
| Edit transcripts | Fix transcription errors in serve mode | `manual.md` (bullet) · `design-transcript-editing.md` | md / 🔧 | ✅/🔧 | 🔴 |
| Edit speakers / roles | Moderator / participant / observer, speaker codes | `manual.md` §Core concepts (concept) · `design-speaker-editing.md` | md / 🔧 | ✅/🔧 | 🔴 |
| Codebooks & AutoCode | Built-in frameworks, custom codebooks, ✦ AutoCode, confidence threshold | `manual.md` §Codebooks · `CodebookSection.tsx` · `design-autocode.md` | md / react / 🔧 | ✅/📱 | 🟡 (no AutoCode walkthrough) |
| Merge participant names | `people.yaml` display-name merge strategy | `README.md` output tree · `SECURITY.md` (mention) · `design-html-report.md` | md / 🔧 | ✅/🔧 | 🔴 (no dedicated how-to) |

### 3e. Export & share

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Export quotes (CSV / spreadsheet) | Copy Quotes / Save as Spreadsheet → Miro / Sheets / Excel; 11 columns | `design-export-quotes.md` · `export.pasteHint` · `manual.md` (bullet) | 🔧 / 📱 | 🔧/📱 | 🔴 (shipped; no how-to) |
| Extract video clips | Selection (starred ∪ heroes), naming, padding, FFmpeg need, anonymised filenames | `design-export-clips.md` · `export.clips.*` · `manual.md` (bullet) | 🔧 / 📱 | 🔧/📱 | 🔴 (shipped v0.14.3; no how-to) |
| Share a report / Export HTML offline | Standalone zip (report + transcripts); what's embedded | `manual.md` §Serve mode (mention) · `design-export-html.md` · `export.heading`/`subtitle` | md / 🔧 / 📱 | ✅/📱 | 🟡 (mentioned; no walkthrough) |
| Anonymise before sharing | Export-time checkbox vs `--redact-pii`; what each strips/keeps | `SECURITY.md` (boundary) · `design-export-html.md` (matrix) · `export.anonymiseHint` | md / 🔧 / 📱 | ✅/📱 | 🟡 (concept covered; no task page) |
| **Connect to Miro (get a token)** | 5-step token setup; OAuth path; scopes; troubleshooting | **`miro-setup-help.html` (ready template)** · `design-miro-bridge.md` · `miro.*` · `configure miro` | 📐 / 🔧 / 📱 | 📐 | 🔴 (template ready; feature experimental, unpublished) |
| Send to Miro | The export action itself: menu → board → open | `miro-flow.html` (overview) · `MiroExportPanel.tsx` | 📐 / react | 📐/📱 | 🟡 (experimental) |
| Export slides (.pptx) | One-quote-per-slide deck, speaker notes | `design-export-slides.md` | 🔧 | 🔧 | ⏸ (parked, not implemented) |

### 3f. Privacy, governance & languages

| Topic | Covers | Current location | Format | Published | Status |
|---|---|---|---|---|---|
| Privacy model (local vs cloud) | What's sent / kept local; per-provider; not used for training | `SECURITY.md` · `PrivacySection.tsx` (`help.privacy.*`) · `AIConsentView.swift` | md / react / swift | ✅/📱/🖥 | 🟢 |
| Change the UI language | `--lang`; in-app picker; "report content isn't translated" | `manual.md` §Languages · `settings.language.*` | md / react | ✅/📱 | 🟢 |
| Translate Bristlenose (contributor) | Weblate; full locale-add playbook | `CONTRIBUTING.md` §Translating · `docs/adding-a-language.md` | md | ✅ | 🟢 (contributor, not researcher) |

---

## 4. Gaps — what needs net-new writing

Ordered by user impact. Everything here is a feature that **ships today** (unless noted) but has **no task-oriented user how-to**.

1. **"Where do I get an API key?" stops at a bare hostname.** Every prompt says "get a key from console.anthropic.com / platform.openai.com / aistudio.google.com / Azure portal" — but there is *no* sign-up → billing → create-key → copy walkthrough anywhere. This is the single biggest gap because **every user hits it on first run**. Azure is the worst (creating an OpenAI resource + deployment is a multi-step Azure-console journey with zero guidance).
2. **The export family is undocumented.** Quotes-to-CSV, video clips, and offline HTML all ship and all have rich *developer* design docs but only a one-line manual bullet for users. No walkthrough of the dialogs, the selection logic, the FFmpeg requirement, or the anonymisation matrix.
3. **Getting a Miro token is unexplained in-product.** The SPA shows only a field label ("Miro access token"); the moment OAuth is unconfigured/times out, the user is told to "paste a token" with no guidance on obtaining one. The how-to *content* is already written (`miro-setup-help.html`) — it just needs promoting and the feature is experimental.
4. **No provider comparison.** Nothing consolidates Claude vs ChatGPT vs Gemini vs Azure vs Ollama on quality / cost / privacy; the signals are scattered across the manual, the in-app Privacy section, and pipeline quality glyphs.
5. **Ollama setup for non-desktop users.** The rich auto-install/auto-pull flow is **desktop-only**. CLI/SPA users get terse doctor fixes and read-only config rows — no "install Ollama, pull a model, choose by RAM/quality" walkthrough.
6. **PII redaction is explained but not actionable.** The Privacy help is thorough on *what* redaction does, but enabling it is CLI-only and dead-ends on uninstalled deps (Presidio + spaCy model) the user only discovers when doctor fails.
7. **Transcript editing, speaker editing, people-file merge, AutoCode** — all ship, all are named in the manual, none have a step-by-step.
8. **First-run orientation is desktop-only.** The welcome rail lives in `WelcomeView.swift`; SPA/CLI users get a one-liner. A "your first analysis" tutorial would serve every channel.

---

## 5. Proposed URL structure

Source-of-truth Markdown in this repo → rendered HTML on the site:

```
docs/how-to/<slug>.md     →     bristlenose.app/docs/how-to/<slug>.html
```

**Convention** (recommended, matching the one existing precedent `miro-setup`): `<topic>-setup` for setup guides, `verb-noun` for task guides. **Flat, no category sub-directories** — matches the `miro-setup` precedent, keeps the deploy render simple, and the set is small enough. (Nesting providers under `how-to/providers/` is a clean future option if the set grows — flagged as a decision in §7.)

The **landing page** (`bristlenose.app/docs/how-to/`) groups the guides by the categories below. Source it from `docs/how-to/README.md` (mirrors the `docs/mockups/README.md` pattern); the actual index rendering is the deploy repo's job.

### Proposed slots → source material to harvest

| Slug | Category | Priority | Harvest from | Feature status |
|---|---|---|---|---|
| `first-analysis` | Get started | P1 | `manual.md` §First run + `WelcomeView.swift` rail | shipped |
| `prepare-your-interviews` | Get started | P1 | man `INPUT FILES` + `manual.md` §First run | shipped |
| `choose-a-provider` | Providers | P1 | `manual.md` §AI provider + `help.privacy.*` + pipeline glyphs | shipped |
| `claude-setup` | Providers | P1 | `README.md` §Getting an API key + doctor fixes + `LLMProvider.swift` links | shipped |
| `chatgpt-setup` | Providers | P1 | same pattern | shipped |
| `gemini-setup` | Providers | P1 | same pattern | shipped |
| `azure-openai-setup` | Providers | P1 | `manual.md` §Azure + doctor `api_key_missing_azure` + `LLMSettingsView.swift` | shipped (highest-effort) |
| `ollama-setup` | Providers | P1 | `ollama-setup-popovers.html` + desktop flow + man §Local LLM + doctor `ollama_*` | shipped |
| `export-quotes` | Export | P2 | `design-export-quotes.md` + `export.pasteHint` | shipped |
| `extract-clips` | Export | P2 | `design-export-clips.md` + `export.clips.*` | shipped |
| `share-a-report` | Export | P2 | `design-export-html.md` + `manual.md` §Serve mode | shipped |
| `anonymise-before-sharing` | Export | P2 | `SECURITY.md` boundary + `design-export-html.md` matrix | shipped |
| `miro-setup` | Export | P3 | **`miro-setup-help.html` (already drafted)** | experimental |
| `send-to-miro` | Export | P3 | `miro-flow.html` + `MiroExportPanel.tsx` | experimental |
| `edit-transcripts` | Report | P3 | `design-transcript-editing.md` | shipped |
| `edit-speakers` | Report | P3 | `design-speaker-editing.md` | shipped |
| `use-codebooks-and-autocode` | Report | P3 | `manual.md` §Codebooks + `design-autocode.md` | shipped |
| `merge-participant-names` | Report | P3 | `design-html-report.md` + README output tree | shipped |
| `redact-pii` | Privacy | P3 | `help.privacy.*` + doctor dep fixes | shipped |
| `export-slides` | Export | P4 | `design-export-slides.md` | ⏸ parked — defer until built |

**Cross-link, don't duplicate (stay in the manual):** install, the CLI command table, keyboard shortcuts, core concepts, the privacy model, where-keys-are-stored. These are mature in `manual.html` / `SECURITY.md`; the how-to guides should link to them, and the manual's brief sections should gain "→ full how-to" links once the guides exist.

---

## 6. Pre-publish accuracy fixes (flag before harvesting)

A how-to that mirrors stale source inherits its errors. Two known issues to fix *before* (or while) harvesting:

- **`bristlenose help commands` and `help workflows` are stale** (`cli.py` ~L2192–2313): they still present the removed `render` command as functional and reference old paths (`output/`, `raw_transcripts/`). The **man page is correct** — prefer it as the source. Don't seed `prepare-your-interviews` or the workflow guides from the stale `help` text.
- **`.env` is referenced but never shown.** `help config` and the man page say "see `.env.example` in the repository," but a pip/brew user has no checkout. The provider-setup guides should inline a minimal `.env` template rather than point at a repo file.

---

## 7. Decisions for the maintainer

These are genuinely your calls — options + trade-offs, not recommendations to rubber-stamp:

1. **Slug convention.** Keep `miro-setup` and use `<topic>-setup` + `verb-noun` (proposed, matches precedent)? Or switch to uniform verb-first (`set-up-miro`, `set-up-claude`) and re-slug the in-flight Miro page? Trade-off: precedent-consistency vs verb-first readability.
2. **Flat vs nested.** Flat `how-to/claude-setup.html` (proposed) or nested `how-to/providers/claude.html`? Nesting reads better with 6 provider pages but breaks the flat precedent and complicates the deploy render.
3. **How-to vs manual ownership of install + provider setup.** The manual already covers these briefly. Do the how-to guides become the *canonical* deep version (manual shrinks to a pointer), or stay as optional deep-dives (manual keeps its summary)? Affects how much you trim `manual.md`.
4. **Publish `miro-setup` while the feature is experimental?** The doc is ready, but Send-to-Miro is Phase-1/paste-token-only with OAuth "coming in v1." Ship the how-to now (with an "experimental" banner), or hold it until OAuth lands?
5. **`export-slides`** is parked — leave it out of the index entirely until built, or include a "coming soon" stub? (Recommend: leave out; stubs read as broken links.)
6. **In-app entry point.** The SPA has *no* link to `manual.html` or a how-to section today (it only links academic refs + provider docs). A new section needs a deliberate hook — the natural spots are the Help modal and the API-Keys "Coming soon" stub (which could link `claude-setup` et al. instead of dead-ending).

---

## Appendix — surfaces audited

- **docs/**: `manual.md` (full section breakdown), `README.md`, `INSTALL.md`, `SECURITY.md`, `CONTRIBUTING.md`, `adding-a-language.md`, `glossary.md`, and the setup-relevant design docs (`design-{ollama-setup,figma-setup,miro-bridge,keychain,cli-provider-selection,doctor-and-snap,export-*,help-modal}.md`).
- **docs/mockups/**: `README.md`, `miro-setup-help.html` (template), `miro-flow.html`, `ollama-setup-popovers.html`, plus a filename scan of the other ~50 (all UI/design mockups, no reusable how-to prose). **docs/walkthroughs/** is entirely dev/QA artefacts (C3 bundle/smoke-test), not user how-tos.
- **Codebase**: `HelpModal.tsx` + `about/*Section.tsx`, `SettingsModal.tsx` / `islands/SettingsPanel.tsx`, `MiroExportPanel.tsx`, `ExportDropdown.tsx`; locale namespaces `help`, `emptyState`, `miro`, `export`, `analysis`, `dashboard`, `codebook`, `settings.*` (en canonical); CLI `cli.py` (`--help`, hand-written `help` topics, interactive provider/Ollama setup), `doctor.py` + `doctor_fixes.py` (check→fix catalogue), man page `bristlenose/data/bristlenose.1`.
- **Desktop UI**: `WelcomeView.swift`, `AIConsentView.swift`, `LLMSettingsView.swift`, `LLMProvider.swift`, `TranscriptionSettingsView.swift`, `OllamaDownloadModel.swift` (`desktop.{welcome,chrome,aiConsent,llmSettings,transcriptionSettings}.*`).
