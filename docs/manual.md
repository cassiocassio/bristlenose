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

Best quality. ~$1.50 per study.

1. Sign up at [console.anthropic.com](https://console.anthropic.com/settings/keys)
2. Create a key, copy it
3. Run: `bristlenose configure claude`

### ChatGPT

Similar quality. ~$1.00 per study.

1. Sign up at [platform.openai.com](https://platform.openai.com/api-keys)
2. Create a key, copy it
3. Run: `bristlenose configure chatgpt`

Add `--llm openai` to your commands to use ChatGPT instead of the default.

### Gemini

Budget option. ~$0.20 per study.

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

Bristlenose accepts any mix of audio (.wav, .mp3, .m4a, .flac, .ogg, .aac), video (.mp4, .mov, .avi, .mkv, .webm), subtitles (.srt, .vtt), and transcripts (.docx from Zoom, Teams, or Google Meet).

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

Bristlenose runs a 12-stage pipeline: ingest → extract audio → parse subtitles → parse transcripts → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render.

If a run is interrupted, re-running the same command resumes where it left off. Completed sessions are loaded from cache in milliseconds.

## Serve mode {#serve-mode}

```
bristlenose serve interviews
```

Opens an interactive version of your report in the browser. Everything you do is saved to a local database — star quotes, tag, hide noise, edit names, reorganise your codebook. Changes persist between sessions.

Serve mode is the primary way to work with Bristlenose. The static HTML render (`bristlenose render`) still works for offline sharing, but serve mode is where the active development happens.

### What you can do in serve mode

- **Star quotes** — mark the ones that belong in your presentation
- **Hide quotes** — dismiss noise without deleting it
- **Tag quotes** — apply your own codes, with autocomplete from your codebook
- **Edit names** — add display names for participants and moderators
- **Edit codebook** — drag-and-drop tags between groups, rename, recolour
- **AutoCode** — let the LLM propose tags, then review with a confidence threshold
- **Search** — find any quote across all interviews
- **Filter by tag** — focus on one code at a time
- **Export** — CSV for Miro/FigJam, or self-contained HTML for stakeholders

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
| `bristlenose doctor` | Check dependencies, API keys, and runtime environment. |
| `bristlenose configure <provider>` | Store an API key securely. Providers: `claude`, `chatgpt`, `gemini`, `azure`. |

### Common options

| Flag | Effect |
|------|--------|
| `-p "Project Name"` | Name your project (appears in reports) |
| `--llm openai` | Use ChatGPT instead of Claude |
| `--llm gemini` | Use Gemini |
| `--llm local` | Use Ollama (free) |
| `--llm azure` | Use Azure OpenAI |
| `--redact-pii` | Detect and redact personal information |
| `--output <dir>` | Override default output location |
| `-y` | Skip confirmation prompts |
| `-v` | Verbose terminal output (DEBUG level) |

## Privacy & security {#privacy}

### Local-first

No Bristlenose server. No accounts. No telemetry. Audio is transcribed locally using Whisper on your machine. The analysis pass sends transcript text to your chosen LLM provider — or stays entirely offline with Ollama.

### Credential storage

API keys are stored in your OS credential store (macOS Keychain, Linux Secret Service), never in plaintext. Fallback to `.env` or environment variables.

### PII redaction

The `--redact-pii` flag uses Microsoft Presidio + spaCy to detect and redact names, phone numbers, email addresses, ID numbers, and other personal data. An audit trail (`pii_summary.txt`) lists every redaction with confidence scores. Location names are deliberately excluded — they carry research context.

### Anonymisation boundary

Two layers of identity. **Speaker codes** (`p1`, `p2`) are the anonymisation boundary — used in reports by default. **Display names** (first names) help your team recall "who's Mary" during analysis. Exports use speaker codes only, preventing stakeholder bias.

### Vulnerability reporting

Email [security@bristlenose.app](mailto:security@bristlenose.app). Do not open public GitHub issues for security vulnerabilities.

## Changelog {#changelog}

Recent releases. Full history on [GitHub](https://github.com/cassiocassio/bristlenose/blob/main/CHANGELOG.md).

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
