# Manual {#getting-started}

Bristlenose takes a folder of interview recordings and produces organised research findings — quotes grouped by screen and theme, sentiment flagged, friction surfaced. This page covers everything from installation to daily use.

## Install {#install}

### macOS — desktop app

Download [Bristlenose.dmg](https://github.com/cassiocassio/bristlenose/releases/latest) from GitHub Releases, drag to Applications, open it. The app bundles Python, FFmpeg, and Whisper — no terminal needed.

First launch: macOS will block it. Go to **System Settings → Privacy & Security**, scroll down, click **"Open Anyway"**. One time only. Requires macOS 15 Sequoia, Apple Silicon (M1+).

### macOS — Homebrew

```
brew install cassiocassio/bristlenose/bristlenose
```

Handles Python, FFmpeg, and all dependencies.

### Windows

1. Install Python from [python.org](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"**
2. Install pipx: `python -m pip install --user pipx` then `python -m pipx ensurepath`
3. Install FFmpeg: `winget install FFmpeg`
4. Install Bristlenose: `pipx install bristlenose`

### Linux

1. Install FFmpeg: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo dnf install ffmpeg-free` (Fedora)
2. Install Bristlenose: `pipx install bristlenose` or `uv tool install bristlenose`

### Verify your setup

```
bristlenose doctor
```

Checks FFmpeg, transcription backend, API keys, network, and disk space. Shows fix commands for anything missing.

## Set up an AI provider {#ai-provider}

Bristlenose uses an LLM for the analysis pass (speaker identification, quote extraction, thematic grouping). Transcription is always local. You need one provider:

### Claude (recommended)

Best quality. Roughly $0.40 per hour of interview audio.

1. Sign up at [console.anthropic.com](https://console.anthropic.com/settings/keys)
2. Create a key, copy it
3. Run: `bristlenose configure claude`

### ChatGPT

Similar quality, similar price.

1. Sign up at [platform.openai.com](https://platform.openai.com/api-keys)
2. Create a key, copy it
3. Run: `bristlenose configure chatgpt`

Add `--llm chatgpt` to your commands to use ChatGPT instead of the default.

### Gemini

Budget option. Roughly $0.06 per hour of interview audio (5–7× cheaper than Claude or ChatGPT).

```
bristlenose configure gemini
bristlenose run interviews --llm gemini
```

### Azure OpenAI

For enterprise teams with Azure contracts.

```
export BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/
export BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name
bristlenose configure azure
```

### Ollama (free, local)

No API key, no account, no cost. Install [Ollama](https://ollama.ai), then run:

```
bristlenose run interviews --llm local
```

Bristlenose will offer to set up Ollama automatically. Trade-off: ~10 minutes vs ~2 minutes per study, lower JSON reliability (~85% vs ~99%).

### Where are keys stored?

Keys live in your operating system's secure credential store — never in plaintext. macOS: Keychain. Linux: Secret Service (GNOME Keyring / KDE Wallet). Fallback: `.env` file or environment variables.

## Languages {#languages}

The UI ships in six languages: English (`en`), Spanish (`es`), French (`fr`), German (`de`), Korean (`ko`), and Japanese (`ja`). The browser's preferred language is auto-detected; override with `--lang <code>` on the CLI or in Settings in the desktop app.

Translations live on [Hosted Weblate](https://hosted.weblate.org/projects/bristlenose/) — contributions welcome.

## Your first run {#first-run}

```
# Point at a folder of recordings
bristlenose interviews

# Output appears inside the folder
# interviews/bristlenose-output/

# Open the report in your browser
# macOS:  open interviews/bristlenose-output/bristlenose-interviews-report.html
# Linux:  xdg-open interviews/bristlenose-output/bristlenose-interviews-report.html
# Windows: start interviews\bristlenose-output\bristlenose-interviews-report.html
```

Bristlenose accepts any mix of audio (.wav, .mp3, .m4a, .flac, .ogg, .wma, .aac), video (.mp4, .mov, .avi, .mkv, .webm), subtitles (.srt, .vtt), and transcripts (.docx from Zoom, Teams, or Google Meet).

Files sharing a name stem (e.g. `p1.mp4` and `p1.srt`) are treated as one session. Existing subtitles skip transcription.

A typical study (5–8 interviews) takes 2–5 minutes on Apple Silicon.

## Core concepts {#concepts}

### Sessions and participants

Each recording is a **session**. Bristlenose identifies who's speaking: **moderators** (researchers asking questions — never quoted), **participants** (the people you're researching — primary data), and **observers** (silent attendees — excluded from quotes).

Participants get speaker codes (`p1`, `p2`) for anonymisation. You can add display names for your team's reference — these stay internal. Stakeholders see codes only.

### Quotes

Bristlenose extracts quotable moments from every interview. Filler words are removed. Meaning, emotion, and self-corrections are preserved. Editorial context is added sparingly: `[clarifying context]` only where meaning would be lost.

Each quote appears in **exactly one section** of the report — no duplicates.

### Sections and themes

**Sections** group quotes by screen or task (what the participant was looking at). **Themes** group quotes by cross-participant pattern (what kept coming up).

Screen-specific quotes go to sections. General-context quotes (job role, daily workflow, broader opinions) go to themes.

### Sentiment and signals

Every quote gets AI-generated sentiment tags: positive, negative, neutral, mixed, plus specific emotions (confusion, delight, frustration, trust, skepticism). Signal cards summarise patterns across participants — flagging wins, problems, niggles, and surprises.

### Tags and codebooks

Tags are your own codes, applied to quotes as you review them. A **codebook** organises tags into named groups with colours. You can create your own or import a standard framework:

- Bristlenose (domain-agnostic UXR codebook)
- Jesse James Garrett — Elements of User Experience
- Don Norman — Emotional Design
- Peter Morville — User Experience Honeycomb
- Nielsen's 10 Usability Heuristics
- Yablonski's Laws of UX

### The pipeline

Bristlenose runs a 12-stage pipeline: ingest → extract audio → parse subtitles → parse `.docx` transcripts → transcribe (with speaker identification) → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render.

If a run is interrupted, re-running the same command resumes where it left off. Completed sessions are loaded from cache in milliseconds. From v0.15.0, every run writes an append-only `pipeline-events.jsonl` with structured cause-of-end metadata; if a previous run died mid-flight, the next one notices and reconciles it. Per-run cost is shown as an honest estimate (e.g. `~$0.46 (est.)`).

## Serve mode {#serve-mode}

```
bristlenose serve interviews
```

Opens an interactive version of your report in the browser at `http://127.0.0.1:8150/report/`. Everything you do is saved to a local SQLite database — star quotes, tag, hide noise, edit names, edit transcripts, reorganise your codebook. Changes persist between sessions.

Serve mode is the product. To share offline, click **Export HTML** in the toolbar — it produces a self-contained file with the full React report and all your edits embedded (optionally anonymised). The legacy `bristlenose render` static HTML still exists but is deprecated.

### What you can do in serve mode

- **Star, hide, and tag quotes** with autocomplete from your codebook
- **Inspector panel** (`m`) — DevTools-style heatmaps and signal cards with Win/Problem/Niggle/Surprise direction flags
- **Sidebars** — left TOC with scroll-spy, right tag filter with codebook tree (`[`, `]`, `\`)
- **Edit codebook** — drag-and-drop tags between groups, rename, recolour
- **AutoCode** — press the ✦ button to let the LLM propose tags from your codebook, then review them in a confidence histogram (set a threshold for auto-acceptance, review borderline cases, reject the rest)
- **Edit transcripts and participant names** in place
- **Word-level transcript highlighting** — karaoke-style sync with video playback
- **Search** across all interviews; **filter by tag**
- **Export** — CSV for Miro/FigJam/Mural, video clips of starred quotes (FFmpeg stream-copy), or self-contained HTML for stakeholders

## Codebooks {#codebooks}

A codebook is an organised set of tags for analysing your quotes. Each tag belongs to a group, and each group has a colour. You can have multiple codebooks active.

### Built-in frameworks

Import a standard UXR framework from the codebook panel: **Codebook → Add Framework**. Each framework comes with pre-defined groups and tags based on published research methodology.

### Custom codebooks

Create your own groups and tags from the codebook panel. Drag tags between groups, rename groups, set colours. Your codebook is saved to the project database.

### AutoCode

Press the ✦ button on a codebook section to let the LLM propose tags for your quotes. Review proposals in a confidence histogram — set a threshold for automatic acceptance, review borderline cases one by one, reject the rest.

## Keyboard shortcuts {#keyboard-shortcuts}

| Key | Action |
|-----|--------|
| <kbd>j</kbd> / <kbd>k</kbd> | Next / previous quote |
| <kbd>s</kbd> | Star focused quote |
| <kbd>h</kbd> | Hide focused quote |
| <kbd>t</kbd> | Open tag input on focused quote |
| <kbd>r</kbd> | Repeat last tag |
| <kbd>x</kbd> | Toggle selection on focused quote |
| <kbd>/</kbd> | Focus search |
| <kbd>?</kbd> | Help |
| <kbd>Escape</kbd> | Clear (cascades: modal → search → selection → focus) |
| <kbd>[</kbd> | Toggle left sidebar (TOC) |
| <kbd>]</kbd> | Toggle right sidebar (tags) |
| <kbd>\\</kbd> | Toggle both sidebars |
| <kbd>m</kbd> | Toggle inspector panel (Analysis tab) |
| <kbd>Tab</kbd> | Commit tag and open new input (fast tagging) |
| <kbd>Shift</kbd>+<kbd>j</kbd>/<kbd>k</kbd> | Extend selection |
| <kbd>Cmd</kbd>+<kbd>click</kbd> | Multi-select |
| <kbd>Cmd</kbd>+<kbd>,</kbd> | Settings |

## CLI commands {#commands}

| Command | What it does |
|---------|--------------|
| `bristlenose run <folder>` | Full pipeline — transcribe, analyse, render. Default command: `bristlenose <folder>` does the same thing. |
| `bristlenose serve <folder>` | Interactive browser-based report with live editing and database sync. |
| `bristlenose transcribe <folder>` | Transcription only — no LLM calls. Useful for checking transcripts before analysis. |
| `bristlenose analyze <folder>` | Skip transcription, run LLM analysis on existing transcripts. |
| `bristlenose render <folder>` | Re-render HTML from existing JSON — no LLM calls. For tweaking names or formatting. |
| `bristlenose status <folder>` | Read-only project status — which stages completed, how many sessions. |
| `bristlenose doctor` | Check dependencies, API keys, and runtime environment. Add `--self-test` to verify a bundled sidecar's data files (used by the desktop app). |
| `bristlenose configure <provider>` | Store an API key securely. Providers: `claude`, `chatgpt`, `gemini`, `azure`, `miro`. |

### Common options

| Flag | Effect |
|------|--------|
| `-p "Project Name"` | Name your project (appears in reports) |
| `--llm chatgpt` | Use ChatGPT instead of Claude |
| `--llm gemini` | Use Gemini |
| `--llm local` | Use Ollama (free) |
| `--llm azure` | Use Azure OpenAI |
| `--redact-pii` | Detect and redact personal information |
| `--output <dir>` | Override default output location |
| `-y` | Skip confirmation prompts |
| `-v` | Verbose terminal output (DEBUG level) |
| `--lang <code>` | UI language: `en`, `es`, `fr`, `de`, `ko`, or `ja` |

## Privacy & security {#privacy}

### Local-first

No Bristlenose server. No accounts. No remote telemetry. Audio is transcribed locally using Whisper on your machine. The analysis pass sends transcript text to your chosen LLM provider — or stays entirely offline with Ollama.

Bristlenose does keep a **local** record of LLM calls at `<output>/.bristlenose/llm-calls.jsonl` (timing, token counts, cost estimate, prompt SHA — no transcript content). This file is treated as a re-identification key: it stays in `.bristlenose/`, is mode `0o600`, and is excluded from any export. Disable it entirely with `BRISTLENOSE_LLM_TELEMETRY=0`.

### Serve-mode access control

`bristlenose serve` listens on `127.0.0.1` only and protects its API with a localhost bearer token. Other processes on the same machine can't read your project state without the token.

### Credential storage

API keys are stored in your OS credential store (macOS Keychain, Linux Secret Service), never in plaintext. Fallback to `.env` or environment variables.

### PII redaction

The `--redact-pii` flag uses Microsoft Presidio + spaCy to detect and redact names, phone numbers, email addresses, ID numbers, and other personal data. An audit trail (`pii_summary.txt`) lists every redaction with confidence scores. Location names are deliberately excluded — they carry research context.

### Anonymisation boundary

Two layers of identity. **Speaker codes** (`p1`, `p2`) are the anonymisation boundary — used in reports by default. **Display names** (first names) help your team recall "who's Mary" during analysis. Exports use speaker codes only, preventing stakeholder bias.

### Vulnerability reporting

Email [security@bristlenose.app](mailto:security@bristlenose.app). Do not open public GitHub issues for security vulnerabilities.

## Changelog {#changelog}

Recent releases. Full history on [GitHub](https://github.com/cassiocassio/bristlenose/blob/main/CHANGELOG.md) or in the [README](https://github.com/cassiocassio/bristlenose/blob/main/README.md#changelog).

### 0.15.1 — 1 May 2026

- **Desktop alpha-readiness** — sandbox-safe API-key injection via Swift Keychain, libproc zombie cleanup, privacy manifests, per-binary signing, supply-chain provenance
- **Desktop first-run experience** — unified boot/loading view, two-variant welcome state, round-trip API-key validation, Ollama setup sheet
- Serve mode falls back to bundled theme CSS for brand-new projects, and fails loudly with a "Build incomplete" 500 page if the React bundle is missing
- `bristlenose doctor --self-test` for verifying sidecar bundle integrity
- Japanese (`ja`) locale completion — six languages now ship complete

### 0.15.0 — 26 Apr 2026

- **Pipeline resilience** — append-only `pipeline-events.jsonl` with structured cause-of-end (10 categories); stranded runs reconciled on next start
- **Honest cost estimates** — every terminus event stamped with `cost_usd_estimate`, token counts, and `price_table_version`; surfaced as `~$0.46 (est.)`
- Desktop `EventLogReader` with new `partial` and `stopped` pipeline states

### 0.14.6 — 18 Apr 2026

- E2E gate re-enabled as a blocking CI check; allowlist register for tracked test suppressions
- `bristlenose doctor` warns if `_BRISTLENOSE_AUTH_TOKEN` is set in the shell

### 0.14.3 — 27 Mar 2026

- **Video clip extraction** — export starred and featured quotes as video clips (FFmpeg stream-copy)

### 0.14.2 — 24 Mar 2026

- **Localhost bearer token** for serve-mode API access control

### 0.14.1 — 24 Mar 2026

- French, German, Korean locales — machine-translated, cross-checked against Apple and ATLAS.ti glossaries
- Tags sidebar shortcut (`⌘⌥T`)

### 0.14.0 — 20 Mar 2026

- **Inspector panel** — DevTools-style collapsible bottom panel in Analysis tab with heatmap matrices and signal card selection
- **Codebook sidebar** — available on every tab, not just Quotes
- **Finding flags** — signal cards carry Win/Problem/Niggle/Success/Surprising/Pattern flags computed from sentiment, breadth, and intensity
- **Settings & Help modals** — gear icon and ? key, shared sidebar-nav shell
- Nielsen's 10 Usability Heuristics and Yablonski's Laws of UX framework codebooks

### 0.13.6 — 16 Mar 2026

- **Single tag focus mode** — click a tag count in the sidebar to solo that tag
- Used/unused tag filter, sidebar tag click-to-assign
- Tier 1 logging, multilingual UI infrastructure, responsive signal cards

### 0.13.0 — 10 Mar 2026

- **Codebook-aware tag autocomplete** — grouped suggestions with colour-coded pills
- Sentiment tags unified into codebook framework
- Tag provenance tracking (human vs autocode)
- Quick-repeat tag shortcut (<kbd>r</kbd>)

### 0.12.1 — 1 Mar 2026

- **Word-level transcript highlighting** — karaoke-style sync with video playback

### 0.12.0 — 1 Mar 2026

- **Dual sidebar** — left TOC with scroll-spy, right tag filter with codebook tree
- Self-contained HTML export with optional anonymisation

### 0.11.0 — 28 Feb 2026

- **Full React SPA** — React Router replaces vanilla JS navigation
- Keyboard shortcuts, player integration, app shell

### 0.10.0 — 18 Feb 2026

- **Desktop app** — SwiftUI macOS launcher with folder picker and drag-and-drop
- .dmg packaging, API key onboarding, serve mode after pipeline

### 0.9.4 — 17 Feb 2026

- **Serve mode** — FastAPI + SQLite + React islands, codebook CRUD, data API
- AutoCode frontend with confidence thresholds

### 0.9.0 — 11 Feb 2026

- Tab navigation with URL hash state and browser back/forward
- Analysis tab with inline signal cards and heatmaps

### 0.8.0 — 7 Feb 2026

- **Azure OpenAI** provider for enterprise teams
- Hidden quotes (<kbd>h</kbd>), codebook standalone page, toolbar redesign
- Multi-select and bulk actions

### 0.6.11 — 3 Feb 2026

- **Ollama support** — free local AI, no API key needed
- Automated Ollama installation and auto-start
