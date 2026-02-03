# Bristlenose

Open-source user-research analysis. Runs on your laptop.

Point it at a folder of interview recordings. It transcribes, extracts verbatim quotes, groups them by screen and theme, and produces a browsable HTML report. Nothing gets uploaded. Your recordings stay on your machine.

<!-- TODO: screenshot of an HTML report here -->

---

## Why

The tooling for analysing user-research interviews is either expensive or manual. Bristlenose connects local recordings to AI models via API and produces structured output -- themed quotes, sentiment, friction points -- without requiring a platform subscription or hours of spreadsheet work.

It's built by a practising researcher. It's free and open source under AGPL-3.0.

---

## What it does

You give it a folder of recordings. It gives you back a report.

Behind the scenes: transcription (Whisper, local), speaker identification with automatic name and role extraction, PII redaction, quote extraction and enrichment (via Claude or ChatGPT API), thematic grouping, and HTML rendering. One command, no manual steps.

The report includes:

- **Sections** -- quotes grouped by screen or task
- **Themes** -- cross-participant patterns, surfaced automatically
- **Sentiment** -- histogram of emotions across all quotes
- **Friction points** -- confusion, frustration, and error-recovery moments flagged for review
- **User journeys** -- per-participant stage progression
- **Per-participant transcripts** -- full transcript pages with clickable timecodes, linked from the participant table
- **Clickable timecodes** -- jump to the exact moment in a popout video player
- **Favourite quotes** -- star, reorder, export as CSV
- **Inline editing** -- fix transcription errors directly in the report
- **Editable participant names** -- click the pencil icon to name participants in-browser; export edits as YAML
- **Tags** -- AI-generated badges plus your own free-text tags with auto-suggest

All interactive state (favourites, edits, tags) persists in your browser's localStorage.

### Quote format

```
05:23 "I was... trying to find the button and it just... wasn't there." -- p3
```

Filler words replaced with `...`. Editorial context in `[square brackets]`. Emotion and strong language preserved.

---

## Install

Requires ffmpeg. For LLM analysis, you can use:
- **Local AI** (free, via [Ollama](https://ollama.ai)) — no signup, no API key needed
- **Claude** (by Anthropic) or **ChatGPT** (by OpenAI) — cloud APIs, pay per use

```bash
# macOS (Homebrew) -- recommended, handles ffmpeg + Python for you
brew install cassiocassio/bristlenose/bristlenose

# Ubuntu / Linux (snap) -- coming soon, pending Snap Store registration
# sudo snap install bristlenose --classic
# In the meantime, see "Try the snap (pre-release)" below

# macOS / Linux / Windows (pipx)
pipx install bristlenose

# or with uv
uv tool install bristlenose
```

If using pipx or uv, you'll also need ffmpeg (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Debian/Ubuntu).

---

## Getting an API key

If you've used Claude or ChatGPT before, you might only know the chat interface. Bristlenose talks to the same AI models, but through their **API** (a direct connection for software). This needs a separate API key -- a password that lets bristlenose call the AI on your behalf.

You only need one key -- **Claude or ChatGPT, not both**.

### Option A: Claude (by Anthropic)

1. Go to [console.anthropic.com](https://console.anthropic.com/settings/keys) and sign up or log in
2. Click **Create Key**, give it a name (e.g. "bristlenose"), and copy the key
3. Set it in your terminal:

```bash
export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...
```

### Option B: ChatGPT (by OpenAI)

1. Go to [platform.openai.com](https://platform.openai.com/api-keys) and sign up or log in
2. Click **Create new secret key**, give it a name, and copy the key
3. Set it in your terminal:

```bash
export BRISTLENOSE_OPENAI_API_KEY=sk-...
```

To use ChatGPT instead of the default, add `--llm openai` to your commands:

```bash
bristlenose run ./interviews/ -o ./results/ --llm openai
```

### Which should I pick?

Both work well. If you already pay for one, use that one. If you're starting fresh:

- **Claude** -- the default in bristlenose. Tends to produce nuanced qualitative analysis. Pay-as-you-go billing from the first API call (no free API tier; a typical 8-participant study costs roughly $1--3)
- **ChatGPT** -- widely used. New API accounts get a small amount of free credit (check your [usage page](https://platform.openai.com/usage) to see if you have any remaining). After that, pay-as-you-go. Similar cost per study

> **Important:** A ChatGPT Plus or Pro subscription does **not** include API access. The API is billed separately at [platform.openai.com/usage](https://platform.openai.com/usage). Likewise, a Claude Pro or Max subscription does not include API credits. API billing is separate at [console.anthropic.com](https://console.anthropic.com).

### Making your key permanent

The `export` command only lasts until you close the terminal. To make it stick, add the line to your shell profile:

```bash
# macOS / Linux -- add to the end of your shell config:
echo 'export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc

# Or for ChatGPT:
echo 'export BRISTLENOSE_OPENAI_API_KEY=sk-...' >> ~/.zshrc
```

Then open a new terminal window (or run `source ~/.zshrc`).

Alternatively, create a `.env` file in your project folder -- see `.env.example` for a template.

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
bristlenose transcribe-only ./interviews/                # transcribe, no LLM
bristlenose analyze ./interviews/bristlenose-output/     # skip transcription, run LLM analysis
bristlenose render ./interviews/bristlenose-output/      # re-render from JSON, no LLM calls
bristlenose doctor                                       # check dependencies
```

### Configuration

Via `.env` file, environment variables (prefix `BRISTLENOSE_`), or `bristlenose.toml`. See `.env.example` for all options.

### Hardware

Transcription hardware is auto-detected. Apple Silicon uses MLX on Metal GPU. NVIDIA uses faster-whisper with CUDA. Everything else falls back to CPU.

---

## Get involved

**Researchers** -- use it on real recordings, open issues when the output is wrong or incomplete.

**Developers** -- Python 3.10+, fully typed, Pydantic models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the CLA, project layout, and design system docs.

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
pip install -e ".[dev,apple]"                 # drop ,apple on Intel/Linux/Windows
cp .env.example .env                          # add your API key
```

On Linux, install `python3.12` and `ffmpeg` via your package manager. On Windows, use `python -m venv .venv` and `.venv\Scripts\activate`.

### Verify everything works

```bash
pytest                       # ~550 tests, should pass in <2s
ruff check .                 # lint
mypy bristlenose/            # type check (some third-party SDK errors are expected)
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

# 4. Run it for real (set whichever API key you have)
export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...   # for Claude
# or: export BRISTLENOSE_OPENAI_API_KEY=sk-...    # for ChatGPT (add --llm openai)
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

### 0.6.11

- Local AI support via Ollama — run bristlenose without an API key using local models like Llama 3.2; interactive first-run prompt offers Local/Claude/ChatGPT choice
- Provider registry — centralised `bristlenose/providers.py` with `ProviderSpec` dataclass, alias resolution (claude→anthropic, chatgpt→openai, ollama→local)
- Ollama integration — `bristlenose/ollama.py` with status checking, model detection, and auto-pull with consent
- Retry logic for local models — 3 retries with exponential backoff for JSON parsing failures (~85% reliability vs ~99% for cloud)
- Doctor integration for local provider — shows "Local (llama3.2:3b via Ollama)" status, helpful fix messages for Ollama not running or model missing

### 0.6.10

- Output directory inside input folder — `bristlenose run interviews/` now creates `interviews/bristlenose-output/` to avoid collisions when processing multiple projects
- New directory structure — `assets/` for static files, `sessions/` for transcript pages, `transcripts-raw/`/`transcripts-cooked/` for transcripts, `.bristlenose/` for internal files
- Report filenames include project name — `bristlenose-{slug}-report.html` so multiple reports in Downloads are distinguishable
- Coverage link fix — player.js no longer intercepts non-player timecode links
- Anchor highlight — transcript page segments flash yellow when arriving via anchor link

### 0.6.9

- Transcript coverage section — collapsible section at the end of the report showing what % of the transcript made it into quotes (X% in report · Y% moderator · Z% omitted), with expandable omitted content per session
- Transcript page fix — pages now render correctly when PII redaction is off (was failing with assertion error)

### 0.6.8

- Multi-participant session support — sessions with multiple interviewees get globally-numbered participant codes (p1–p11 across sessions); report header shows correct participant count
- Sessions table — restructured from per-participant rows to per-session rows with a Speakers column showing all speaker codes (m1, p1, p2, o1) per session
- Transcript page format — heading shows `Session N: m1 Name, p5 Name, o1`; segment labels show raw codes for consistency with the anonymisation boundary
- Session duration — now derived from transcript timestamps for VTT-only sessions (previously showed "—")
- Moderator identification (Phase 1) — per-session speaker codes (`[m1]`/`[p1]`) in transcript files, moderator entries in `people.yaml`, `.segment-moderator` CSS class for muted moderator styling

### 0.6.7

- Search enhancements — clear button (×) inside the search input, yellow highlight markers on matching text, match count shown in view-switcher label ("7 matching quotes"), ToC and Participants hidden during search, CSV export respects search filter
- Pipeline warnings — clean dim-yellow warning lines when LLM stages fail (e.g. credit balance too low), with direct billing URL for Claude/ChatGPT; deduplication and 74-char truncation
- CLI polish — "Bristlenose" in regular weight in the header line, "Report:" label in regular weight in the summary

### 0.6.6

- Cargo/uv-style CLI output — clean `✓` checkmark lines with per-stage timing, replacing garbled Rich spinner output; dim header (version · sessions · provider · hardware), LLM token usage with cost estimate, OSC 8 terminal hyperlinks for report path; output capped at 80 columns; all tqdm/HuggingFace progress bars suppressed
- Search-as-you-type quote filtering — collapsible magnifying glass icon in the toolbar; filters by quote text, speaker, and tag content; overrides view mode during search; hides empty sections/subsections; 150ms debounce
- Platform-aware session grouping — Teams, Zoom cloud, Zoom local, and Google Meet naming conventions recognised automatically; two-pass grouping (Zoom folders by directory, remaining files by normalised stem); audio extraction skipped when a platform transcript is present
- Man page — full troff man page (`man bristlenose`); bundled in the wheel and self-installs to `~/.local/share/man/man1/` for pip/pipx users on first run; wired into snap, CI version gate, and GitHub Release assets
- Page footer — "Bristlenose version X.Y.Z" colophon linking to the GitHub repo on every generated page

### 0.6.5

- Timecode typography — two-tone treatment with blue digits and muted grey brackets; `:visited` colour fix so clicked timecodes stay blue
- Hanging-indent layout — timecodes sit in a left gutter column on both report quotes and transcript pages, making them scannable as a vertical column
- Non-breaking spaces on quote attributions prevent the `— p1` from widowing onto a new line
- Transcript name propagation — name edits made in the report's participant table now appear on transcript page headings and speaker labels via shared localStorage

### 0.6.4

- Concurrent LLM calls — per-participant stages (speaker identification, topic segmentation, quote extraction) now run up to 3 API calls in parallel via `llm_concurrency` config; screen clustering and thematic grouping also run concurrently; ~2.7× speedup on the LLM-bound portion for multi-participant studies

### 0.6.3

- Report header redesign — logo top-left (flipped horizontally), "Bristlenose" logotype with project name, right-aligned document title and session metadata
- View-switcher dropdown — borderless menu to switch between All quotes, Favourite quotes, and Participant data views; replaces old button-bar pattern
- Copy CSV button with clipboard icon — single adaptive button that exports all or favourites based on the current view
- Quote attributions use raw participant IDs (`— p1`) in the report for anonymisation; transcript pages continue to show display names
- Table of Contents reorganised — Sentiment, Tags, Friction points, and User journeys moved to a dedicated "Analysis" column, separate from Themes

### 0.6.2

- Editable participant names — pencil icon on Name and Role cells in the participant table; inline editing with localStorage persistence; YAML clipboard export for writing back to `people.yaml`; reconciliation with baked-in data on re-render
- Auto name and role extraction — Stage 5b LLM prompt now extracts participant names and job titles alongside speaker role identification; speaker label metadata harvested from Teams/DOCX/VTT sources; empty `people.yaml` fields auto-populated (LLM results take priority over metadata, human edits never overwritten)
- Short name suggestion — `short_name` auto-suggested from first token of `full_name` with disambiguation for collisions ("Sarah J." vs "Sarah K."); works both in the pipeline and in-browser
- Editable section and theme headings — inline editing on section titles, descriptions, theme titles, and theme descriptions with bidirectional Table of Contents sync

### 0.6.1

- Snap packaging for Linux — `snap/snapcraft.yaml` recipe and CI workflow (`.github/workflows/snap.yml`); builds on every push to main, publishes to edge/stable when Store registration completes
- Pre-release snap testing instructions in README for early feedback on amd64 Linux
- Author identity (Martin Storey) added to copyright headers, metadata, and legal files

### 0.6.0

- `bristlenose doctor` command — checks FFmpeg, transcription backend, Whisper model cache, API key validity, network, PII dependencies, and disk space
- Pre-flight gate on `run`, `transcribe-only`, and `analyze` — catches missing dependencies before slow work starts
- First-run auto-doctor — runs automatically on first invocation, guides users through setup
- Install-method-aware fix messages — detects snap, Homebrew, or pip and shows tailored install instructions
- API key validation — cheap API call catches expired or revoked keys upfront

### 0.5.0

- Per-participant transcript pages — full transcript for each participant with clickable timecodes and video player; participant IDs in the table link to these pages
- Quote attribution deep-links — clicking `— p1` at the end of a quote jumps to the exact segment in the participant's transcript page
- Segment anchors on transcript pages for deep linking from quotes and external tools

### 0.4.1

- People file (`people.yaml`) — participant registry with computed stats (words, % words, % speaking time) and human-editable fields (name, role, persona, notes); preserved across re-runs
- Display names — set `short_name` in `people.yaml`, re-render with `bristlenose render` to update quotes and tables
- Enriched participant table in reports (ID, Name, Role, Start, Duration, Words, Source) with macOS Finder-style relative dates
- PII redaction now off by default; opt in with `--redact-pii` (replaces `--no-pii`)
- Man page updated for new CLI flags and output structure

### 0.4.0

- Dark mode — report follows OS/browser preference automatically via CSS `light-dark()` function
- Override with `color_scheme = "dark"` (or `"light"`) in `bristlenose.toml` or `BRISTLENOSE_COLOR_SCHEME` env var
- Dark-mode logo variant (placeholder; proper albino bristlenose pleco coming soon)
- Print always uses light mode
- Replaced hard-coded colours in histogram JS with CSS custom properties

### 0.3.8

- Timecode handling audit: verified full pipeline copes with sessions shorter and longer than one hour (mixed `MM:SS` and `HH:MM:SS` in the same file round-trips correctly)
- Edge-case tests for timecode formatting at the 1-hour boundary, sub-minute sessions, long sessions (24h+), and format→parse round-trips

### 0.3.7

- Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting constants and formatter functions
- Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- Participant codes in transcript segments (`[p1]` instead of `[PARTICIPANT]`) for better researcher context when copying quotes
- Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes

### 0.3.6

- Document full CI/CD pipeline topology, secrets, and cross-repo setup

### 0.3.5

- Automated Homebrew tap updates and GitHub Releases on every tagged release

### 0.3.4

- Participants table: renamed columns (ID→Session, Session date→Date), added Start time column, date format now dd-mm-yyyy

### 0.3.3

- README rewrite: install moved up, new quick start section, changelog with all versions, dev setup leads with git clone
- Links to Anthropic and OpenAI API key pages in install instructions

### 0.3.2

- Fix tag auto-suggest offering tags the quote already has
- Project logo in report header

### 0.3.1

- Single-source version: `__init__.py` is the only place to bump
- Updated release process in CONTRIBUTING.md

### 0.3.0

- CI on every push/PR (ruff, mypy, pytest)
- Automated PyPI publishing on tagged releases (OIDC trusted publishing)

### 0.2.0

- Tag system: AI-generated badges (deletable/restorable) + user tags with auto-suggest and keyboard navigation
- Favourite quotes with reorder animation and CSV export (separate AI/User tag columns)
- Inline quote editing with localStorage persistence
- Sentiment histogram (side-by-side AI + user-tag charts)
- `bristlenose render` command for re-rendering without LLM calls
- Report JS extracted into 8 standalone modules under `bristlenose/theme/js/`
- Atomic CSS design system (`bristlenose/theme/`)

### 0.1.0

- 12-stage pipeline: ingest, extract audio, parse subtitles/docx, transcribe (Whisper), identify speakers, merge, PII redaction (Presidio), topic segmentation, quote extraction, screen clustering, thematic grouping, render
- HTML report with clickable timecodes and popout video player
- Quote enrichment: intent, emotion, intensity, journey stage
- Friction points and user journey summaries
- Apple Silicon GPU acceleration (MLX), CUDA support, CPU fallback
- PII redaction with Presidio
- Cross-platform (macOS, Linux, Windows)
- Published to PyPI and Homebrew tap
- AGPL-3.0 licence with CLA

---

## Roadmap

- Hide/show individual quotes
- Keyboard shortcuts (j/k navigation, s to star, e to edit)
- User-generated themes
- Lost quotes -- surface what the AI didn't select
- .docx export
- Edit writeback to transcript files
- Cross-session moderator linking (Phase 2)
- Native installer for Windows

Priorities may shift. If something is missing that matters to you, [open an issue](https://github.com/cassiocassio/bristlenose/issues).

---

## Licence

Copyright (C) 2025-2026 Martin Storey (<martin@cassiocassio.co.uk>)

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
