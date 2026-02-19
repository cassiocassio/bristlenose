# Bristlenose

Open-source user-research transcript analysis.

Point Bristlenose at a folder of interview recordings – videos, audio or transcripts from Zoom, Teams or Google Meet. 

It transcribes, identifies moderators and participants, extracts good verbatim quotes, groups them by screen and theme. Filler words are stripped, editorial context is (sparingly) added `[thus]`. Emotion and strong language are preserved.

The (HTML) report aggregates all your interview quotes.

Click a timecode to watch the video of that quote. 

You can check a summary of unused quotes - to ensure nothing crucial was trimmed by the AI - typically ~20% or less of the original.

You can tag and favourite, to organise the most powerful quotes. It auto-tags with a sentiment-analysis to help you identify moments of frustration or delight.

Filter your quotes, and export via CSV to your boards in Miro, Figjam, Mural or Lucidspark, or spreadsheet - for further analysis.   

Bristlenose transcribes locally, and can do the thematic analysis on a (built in) local LLM –– but for speedy results you'll want an API key from Anthropic, OpenAI, Google or Azure. For commercial work, obviously check your org's policies on public LLM use.

For a typical study, e.g. 5–8 participant-hours, you'd be looking at roughly $1.50–$2.50 total cost from your LLM provider.

Take care. Bristlenose is very alpha, without warranty. All feedback welcome.  
<!-- TODO: screenshot of an HTML report here -->

Bristlenose is built by me, Martin Storey, a practising user researcher. It's free and open source under AGPL-3.0.

Sidequest: [what is a Bristlenose?](https://www.theaquariumwiki.com/wiki/Ancistrus_sp)

---

## What it does

The report includes:    

- **Sections** -- quotes grouped by screen or task
- **Themes** -- cross-participant patterns, surfaced automatically
- **Tags** -- your own free-text tags with auto-suggest
- **Sentiment** -- AI-generated badges plus y
- **Charts** -- histogram of emotions across all quotes
- **Friction points** -- confusion, frustration, and error-recovery moments flagged for review
- **User journeys** -- per-participant stage progression
- **Per-participant transcripts** -- full transcript pages with clickable timecodes, linked from the participant table
- **Clickable timecodes** -- jump to the exact moment in a **popout video player**
- **Favourite quotes** -- star, reorder
- **Inline editing** -- fix transcription errors directly in the report
- **Editable participant names** -- click the pencil icon to name participants in-browser; export edits as YAML
- Filter and **export as CSV** into **Miro** and more
- **Keyboard shortcuts** -- j/k navigation, s to star, t to tag, / to search, ? for help; multi-select with Cmd+click or Shift+j/k for bulk actions


## Install

For LLM analysis, you can use **Claude**, **ChatGPT**, **Azure OpenAI**, **Gemini**, or **Local AI** (free, via [Ollama](https://ollama.ai)) — see [Getting an API key](#getting-an-api-key) below.

```bash
# macOS (Homebrew) -- recommended, handles ffmpeg + Python for you
brew install cassiocassio/bristlenose/bristlenose

# Windows (pipx) -- requires Python, see install guide for details
pipx install bristlenose

# Linux (snap) -- coming soon
# sudo snap install bristlenose --classic

# Linux / macOS / Windows (pipx or uv)
pipx install bristlenose
uv tool install bristlenose    # alternative
```

If using pipx or uv, you'll also need FFmpeg (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu, `winget install FFmpeg` on Windows).

After installing, run `bristlenose doctor` to verify your setup.

See the **[installation guide](INSTALL.md)** for detailed step-by-step instructions for your platform, including Python/FFmpeg setup and AI provider configuration.

---

## Getting an API key

If you've used Claude or ChatGPT before, you might only know the chat interface. Bristlenose talks to the same AI models, but through their **API** (a direct connection for software). This needs a separate API key -- a password that lets bristlenose call the AI on your behalf.

You need one key:

### Option A: Claude (by Anthropic)

1. Go to [console.anthropic.com](https://console.anthropic.com/settings/keys) and sign up or log in
2. Click **Create Key**, give it a name (e.g. "bristlenose"), and copy the key
3. Store it securely:

```bash
bristlenose configure claude    # validates the key and stores it in your system credential store
```

### Option B: ChatGPT (by OpenAI)

1. Go to [platform.openai.com](https://platform.openai.com/api-keys) and sign up or log in
2. Click **Create new secret key**, give it a name, and copy the key
3. Store it securely:

```bash
bristlenose configure chatgpt    # validates the key and stores it in your system credential store
```

To use ChatGPT instead of the default, add `--llm openai` to your commands:

```bash
bristlenose run ./interviews/ -o ./results/ --llm openai
```

### Option C: Azure OpenAI (enterprise)

If your organisation has a Microsoft Azure contract that includes Azure OpenAI Service:

```bash
export BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/
export BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name
bristlenose configure azure    # validates the key and stores it in your system credential store
bristlenose run ./interviews/ --llm azure
```

You'll need your endpoint URL, API key, and deployment name from the [Azure portal](https://portal.azure.com).

### Option D: Gemini (by Google)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign up or log in
2. Click **Create API key**, give it a name, and copy the key
3. Store it securely:

```bash
bristlenose configure gemini    # validates the key and stores it in your system credential store
```

To use Gemini instead of the default, add `--llm gemini` to your commands:

```bash
bristlenose run ./interviews/ -o ./results/ --llm gemini
```

**Budget option:** Gemini is 5–7× cheaper than Claude or ChatGPT — roughly $0.20 per study instead of $1–3.

### Option E: Local AI (via Ollama) — free, no signup

Run analysis entirely on your machine using open-source models. No account, no API key, no cost.

1. Install [Ollama](https://ollama.ai) (one download, no signup)
2. Run bristlenose — it will offer to set up local AI automatically:

```bash
bristlenose run ./interviews/

# Or explicitly:
bristlenose run ./interviews/ --llm local
```

If Ollama isn't installed, bristlenose will offer to install it for you (via Homebrew on macOS, snap on Linux).

**Trade-offs:** Local models are slower (~10 min vs ~2 min per study) and less accurate (~85% vs ~99% JSON reliability). Good for trying the tool; use cloud APIs for production quality.

Use whichever provider you already have an API key for. If you don't have one yet, Option A (Claude) is the default. A typical 8-participant study costs roughly $1--3 with any cloud provider ($0.20 with Gemini).

> **Note:** A ChatGPT Plus/Pro or Claude Pro/Max subscription does **not** include API access. The API is billed separately — you need an API key from [console.anthropic.com](https://console.anthropic.com) or [platform.openai.com](https://platform.openai.com).

### Making your key permanent

**macOS and Linux:** The recommended way is `bristlenose configure` (shown in Options A--D above). It validates your key and stores it in your operating system's secure credential store:

- **macOS** — saved to your **login keychain**. You can view or delete it in the Keychain Access app (search for "Bristlenose")
- **Linux** — saved via **Secret Service** (GNOME Keyring / KDE Wallet). Requires `secret-tool` to be installed (included by default on most desktop Linux distributions)

The key is loaded automatically on every run — no environment variables needed. Run `bristlenose doctor` to verify your key is detected (it will show "(Credential Store)" next to the API key check).

**Windows:** Credential store storage is not yet supported. Set the key permanently with `setx` (built into Windows):

```
setx BRISTLENOSE_ANTHROPIC_API_KEY "sk-ant-..."
```

For ChatGPT, use `BRISTLENOSE_OPENAI_API_KEY`; for Gemini, use `BRISTLENOSE_GOOGLE_API_KEY`. Close and reopen your terminal after running `setx` — the variable only takes effect in new windows.

**Alternative: shell profile (macOS/Linux).** If you prefer environment variables over the credential store, add the export to your shell startup file:

```bash
# macOS (zsh is the default shell):
echo 'export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc

# Linux (bash is the default shell on most distributions):
echo 'export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

Then open a new terminal window (or run `source ~/.zshrc` / `source ~/.bashrc`).

**Alternative: `.env` file.** Create a `.env` file in your project folder -- see `.env.example` for a template.

**Troubleshooting:** Run `bristlenose doctor` at any time to check your setup — it verifies your API key, FFmpeg, transcription backend, and other dependencies.

---

## Quick start

```bash
bristlenose run ./interviews/
```

That's it. Point it at a folder containing your recordings and it will produce the report inside that folder. Expect roughly 2--5 minutes per participant on Apple Silicon, longer on CPU.

Open `interviews/bristlenose-output/bristlenose-interviews-report.html` in your browser.

### What goes in

Any mix of audio, video, subtitles, or transcripts:

`.wav` `.mp3` `.m4a` `.flac` `.ogg` `.wma` `.aac` `.mp4` `.mov` `.avi` `.mkv` `.webm` `.srt` `.vtt` `.docx`

Files sharing a name stem (e.g. `p1.mp4` and `p1.srt`) are treated as one session. Existing subtitles skip transcription.

### What comes out

Output goes inside the input folder by default:

```
interviews/                              # your input folder
├── Session 1.mp4
├── Session 2.mp4
└── bristlenose-output/                  # output folder (created inside input)
    ├── bristlenose-interviews-report.html   # the report -- open this
    ├── bristlenose-interviews-report.md     # Markdown version
    ├── people.yaml                          # participant registry
    ├── assets/                              # static files (CSS, logos, player)
    ├── sessions/                            # per-session transcript pages
    │   ├── transcript_s1.html
    │   └── transcript_s2.html
    ├── transcripts-raw/                     # one .txt + .md per session
    ├── transcripts-cooked/                  # PII-redacted (only with --redact-pii)
    └── .bristlenose/                        # internal files
        └── intermediate/                    # JSON snapshots for `bristlenose render`
```

Override the output location with `--output`: `bristlenose run interviews/ -o /elsewhere/`

### More commands

```bash
bristlenose run ./interviews/ -p "Q1 Usability Study"    # name the project
bristlenose transcribe ./interviews/                     # transcribe, no LLM
bristlenose analyze ./interviews/bristlenose-output/     # skip transcription, run LLM analysis
bristlenose render ./interviews/bristlenose-output/      # re-render from JSON, no LLM calls
bristlenose doctor                                       # check dependencies
```

### Configuration

Via `.env` file, environment variables (prefix `BRISTLENOSE_`), or `bristlenose.toml`. See `.env.example` for all options.

### Hardware

Transcription hardware is auto-detected. Apple Silicon uses MLX on Metal GPU. NVIDIA uses faster-whisper with CUDA. Everything else falls back to CPU.

---

## Roadmap

### Analysis

- **Codebook** -- define your own tags (codes) with descriptions; apply them consistently across quotes
- **Your own themes** -- create, rename and reorder themes manually, not just the AI-generated ones
- **Hide/show quotes** -- dismiss irrelevant quotes from the report without losing them
- **Tag definitions** -- explain what each sentiment tag means (and its theoretical basis) inside the report
- **Clickable histogram** -- click a sentiment bar to filter the report to just those quotes

### Sharing

- **Save curated report** -- export your starred, tagged, edited report as a standalone file you can share with stakeholders
- **.docx export** -- download the report as a Word document
- **Edit writeback** -- save your in-browser corrections back to the transcript files on disk

### Platform

- **Snap Store** -- publish to the Snap Store for one-command install on Ubuntu and other Linux distros
- **Windows installer** -- native setup wizard so you don't need Python or the command line
- **Cross-session moderator linking** -- recognise the same moderator across sessions (currently each session tracks moderators independently)

Priorities may shift. If something is missing that matters to you, [open an issue](https://github.com/cassiocassio/bristlenose/issues).

---

## Get involved

**Researchers** -- use it on real recordings, open issues when the output is wrong or incomplete.

**Developers** -- Python 3.10+, fully typed, Pydantic models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the CLA, project layout, and design system docs.

**Help us test** -- we'd love feedback from people using bristlenose with:
- **Gemini** -- newly added; budget option at ~$0.20/study
- **Azure OpenAI** -- enterprise deployments
- **Windows** -- the pipeline works but hasn't been widely tested
- **Linux** -- snap package coming soon, looking for testers on various distros

---

## Development setup

Clone the repo, create a virtual environment, and install in editable mode:

```bash
# Prerequisites (macOS)
brew install python@3.12 ffmpeg pkg-config

# Clone and set up
git clone https://github.com/cassiocassio/bristlenose.git
cd bristlenose
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,apple]"                 # apple extra installs MLX for Apple Silicon GPU acceleration; omit on other platforms
cp .env.example .env                          # add your API key
```

On Linux, install `python3.12` and `ffmpeg` via your package manager. On Windows, use `python -m venv .venv` and `.venv\Scripts\activate`.

### Verify everything works

```bash
.venv/bin/python -m pytest tests/    # ~550 tests (approximate), should pass in <2s
.venv/bin/ruff check .               # lint
.venv/bin/mypy bristlenose/          # type check (some third-party SDK errors are expected)
```

> **If you rename or move the project directory**, the editable install breaks silently
> (absolute paths baked into `.pth` files and CLI shebangs). Fix with:
> `find . -name __pycache__ -exec rm -rf {} +` then
> `.venv/bin/python -m pip install -e ".[dev]"`

### Try the snap (pre-release)

The snap isn't in the Store yet, but you can grab the CI-built `.snap` from GitHub Actions and test it on any amd64 Linux box:

```bash
# 1. Download the snap artifact from the latest CI run
#    Go to https://github.com/cassiocassio/bristlenose/actions/workflows/snap.yml
#    Click the latest successful run → Artifacts → snap-amd64 → download and unzip

# 2. Install it (--dangerous bypasses Store signature, --classic gives filesystem access)
sudo snap install --dangerous --classic ./bristlenose_*.snap

# 3. Verify
bristlenose --version
bristlenose doctor

# 4. Run it for real (store whichever API key you have)
bristlenose configure claude      # validates and saves to system credential store
# or: bristlenose configure chatgpt
bristlenose run ./interviews/ -o ./results/
```

FFmpeg, Python, faster-whisper, and spaCy are all bundled — no system dependencies needed. Feedback welcome via [issues](https://github.com/cassiocassio/bristlenose/issues).

### Architecture

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full project layout, but the short version:

- `bristlenose/stages/` -- the 12-stage pipeline (ingest through render), one module per stage
- `bristlenose/stages/render_html.py` -- HTML report renderer, loads CSS + JS from theme/
- `bristlenose/theme/` -- atomic CSS design system (tokens, atoms, molecules, organisms, templates)
- `bristlenose/theme/js/` -- report JavaScript (12 modules, concatenated at render time)
- `bristlenose/llm/prompts.py` -- LLM prompt templates
- `bristlenose/pipeline.py` -- orchestrator that wires the stages together
- `bristlenose/cli.py` -- Typer CLI entry point

### Releasing

Edit `bristlenose/__init__.py` (the single source of truth for version), commit, tag, push. GitHub Actions handles CI, build, and PyPI publishing automatically. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Changelog

**0.10.1** — _19 Feb 2026_

- Desktop app API key onboarding — first-run setup screen, Keychain storage, Settings panel (⌘,)
- `.dmg` packaging — ad-hoc signed, drag-to-Applications, one-command build via `build-all.sh`
- Serve mode after pipeline — auto-launches `bristlenose serve`, report at `http://127.0.0.1:8150/report/`
- Deployment target updated to macOS 15 Sequoia

**0.10.0** — _18 Feb 2026_

- Desktop app v0.1 — SwiftUI macOS launcher with folder picker, drag-and-drop, pipeline streaming, View Report in browser
- Xcode 26 project with 4-state UI (ready → selected → running → done), ANSI stripping, report path detection

**0.9.4** — _17 Feb 2026_

- `bristlenose serve` — local dev server with SQLite persistence, React islands, live JS reload
- 5 React islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel) + 16 reusable primitives (182 Vitest tests)
- Codebook CRUD — drag-and-drop, inline editing, tag merge, pentadic colours, MicroBar frequency bars
- Data API — 6 endpoints sync researcher state from localStorage to SQLite (94 tests)
- Desktop app scaffold — SwiftUI macOS shell with sidecar architecture

**0.9.3** — _13 Feb 2026_

- Interactive dashboard — clickable stat cards, featured quotes with video playback, session row drill-down, cross-tab navigation
- Fix: logo dark/light swap on appearance toggle

**0.9.2** — _12 Feb 2026_

- Sessions table redesign — speaker badges, user journey paths, video thumbnails, per-session sentiment sparklines
- Appearance toggle — system/light/dark mode in settings tab
- User journeys — derived from screen clusters, shown in sessions table and sortable journeys table
- Time estimates — upfront pipeline duration estimate after ingest, recalculated as stages complete
- Clickable logo — navigates to project tab
- Fix: `llm_max_tokens` truncation causing silent 0-quote extraction
- Fix: sentiment sparkline bars now align with video thumbnail baseline

**0.9.1** — _11 Feb 2026_

- Moderator and observer names shown in Project tab stats row (Oxford comma lists, observer box only when observers exist)
- Fix: clicking [+] to add a tag on a quote now tags that quote, not the previously-focused quote

**0.9.0** — _11 Feb 2026_

- Tab navigation remembers position across reloads via URL hash; browser back/forward navigates between tabs
- Analysis tab — inline signal cards and heatmaps in the main report (no longer just a placeholder)
- Codebook tab — fixed empty grid bug caused by JS function name collision in the concatenated bundle

**0.8.2** — _9 Feb 2026_

- Transcript annotations — transcript pages highlight selected quotes with margin labels, sentiment colours, span bars, and playback-synced glow
- Gemini provider — `--llm gemini` for budget-conscious teams (~$0.20/study, 5–7× cheaper than Claude or ChatGPT); `bristlenose configure gemini` stores your key in the system credential store
- Jinja2 templates — report renderer migrated from f-strings to 13 Jinja2 templates (internal refactor, no output changes)

**0.8.1** — _7 Feb 2026_

- Hidden quotes — press `h` to hide volume quotes from your working view; per-subsection badge with dropdown previews; bulk hide via multi-select
- Codebook — standalone page for organising tags into groups with drag-and-drop, inline editing, and colour-coded badges
- Toolbar redesign — unified round-rect button styling
- Python 3.14 compatibility fix for PII check

**0.8.0** — _7 Feb 2026_

- Azure OpenAI provider — `--llm azure` for enterprise users with Microsoft Azure contracts
- Install smoke tests — new CI workflow verifies install instructions on clean VMs

**0.7.1** — _6 Feb 2026_

- Bar chart alignment — sentiment and user-tag charts use CSS grid so bar left edges align within each chart; labels hug text with variable gap to bars
- Histogram delete — hover × on user tag labels in the histogram to remove that tag from all quotes (with confirmation modal)
- Surprise placement — surprise sentiment bar now renders between positive and negative sentiments
- Quote exclusivity in themes — each quote assigned to exactly one theme (pick strongest fit)

**0.7.0** — _5 Feb 2026_

- Multi-select — Finder-like click selection (click, Shift-click, Cmd/Ctrl-click) with bulk starring (`s` key) and bulk tagging; selection count shown in view-switcher label; CSV export respects selection
- Tag filter — toolbar dropdown between search and view-switcher filters quotes by user tags; checkboxes per tag with "(No tags)" for untagged quotes; per-tag quote counts, search-within-filter for large tag lists, dropdown chevron, ellipsis truncation for long names

**0.6.15** — _4 Feb 2026_

- Unified tag close buttons — AI badges and user tags now use the same floating circle "×" style
- Tab-to-continue tagging — pressing Tab commits the current tag and immediately opens a new input for adding another tag (type, Tab, type, Tab, Enter for fast keyboard-only tagging)
- Render command path fix — `bristlenose render <input-dir>` now auto-detects `bristlenose-output/` inside the input directory

**0.6.14** — _4 Feb 2026_

- Doctor fixes — improved Whisper model detection and PII capability checking

**0.6.13** — _3 Feb 2026_

- Keychain credential storage — `bristlenose configure claude` (or `chatgpt`) validates and stores API keys securely in macOS Keychain or Linux Secret Service; keys are loaded automatically with priority keychain → env var → .env; `bristlenose doctor` now shows "(Keychain)" suffix when key comes from system credential store; `--key` option available for non-interactive use

**0.6.12** — _3 Feb 2026_

- File-level transcription progress — spinner now shows "(2/4 sessions)" during transcription
- Improved Ollama start command detection — uses `brew services start ollama` for Homebrew installs, `open -a Ollama` for macOS app, platform-appropriate commands for snap/systemd
- Doctor displays "(MLX)" accelerator — when mlx-whisper is installed on Apple Silicon, doctor now shows "(MLX)" instead of "(CPU)"
- Provider header fix — pipeline header now shows "Local (Ollama)" instead of "ChatGPT" when using local provider

[Older versions →](CHANGELOG.md)

---

## Licence

Copyright (C) 2025-2026 Martin Storey (<martin@cassiocassio.co.uk>)

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
