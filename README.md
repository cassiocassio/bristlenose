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

Behind the scenes: transcription (Whisper, local), speaker identification, PII redaction, quote extraction and enrichment (via Anthropic or OpenAI API), thematic grouping, and HTML rendering. One command, no manual steps.

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
- **Tags** -- AI-generated badges plus your own free-text tags with auto-suggest

All interactive state (favourites, edits, tags) persists in your browser's localStorage.

### Quote format

```
05:23 "I was... trying to find the button and it just... wasn't there." -- p3
```

Filler words replaced with `...`. Editorial context in `[square brackets]`. Emotion and strong language preserved.

---

## Install

Requires ffmpeg and an API key from [Anthropic](https://console.anthropic.com/settings/keys) or [OpenAI](https://platform.openai.com/api-keys).

```bash
# macOS (Homebrew) -- recommended, handles ffmpeg + Python for you
brew install cassiocassio/bristlenose/bristlenose

# macOS / Linux / Windows (pipx)
pipx install bristlenose

# or with uv
uv tool install bristlenose
```

If using pipx or uv, you'll also need ffmpeg (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Debian/Ubuntu).

Then set your API key:

```bash
export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...
# or
export BRISTLENOSE_OPENAI_API_KEY=sk-...
```

---

## Quick start

```bash
bristlenose run ./interviews/ -o ./results/
```

That's it. Point it at a folder containing your recordings and it will produce the report in `./results/`. Expect roughly 2--5 minutes per participant on Apple Silicon, longer on CPU.

Open `results/research_report.html` in your browser.

### What goes in

Any mix of audio, video, subtitles, or transcripts:

`.wav` `.mp3` `.m4a` `.flac` `.ogg` `.wma` `.aac` `.mp4` `.mov` `.avi` `.mkv` `.webm` `.srt` `.vtt` `.docx`

Files sharing a name stem (e.g. `p1.mp4` and `p1.srt`) are treated as one session. Existing subtitles skip transcription.

### What comes out

```
results/
  research_report.html       # the report -- open this
  research_report.md         # Markdown version
  transcript_p1.html         # per-participant transcript pages
  transcript_p2.html
  ...
  bristlenose-theme.css      # stylesheet (regenerated on every run)
  bristlenose-logo.png       # project logo
  bristlenose-player.html    # popout video player (if media files present)
  people.yaml                # participant registry (edit names here)
  raw_transcripts/           # one .txt per participant
  cooked_transcripts/        # PII-redacted transcripts (only with --redact-pii)
  intermediate/              # JSON snapshots (used by `bristlenose render`)
```

### More commands

```bash
bristlenose run ./interviews/ -o ./results/ -p "Q1 Usability Study"  # name the project
bristlenose transcribe-only ./interviews/ -o ./results/              # transcribe, no LLM
bristlenose analyze ./results/raw_transcripts/ -o ./results/         # skip transcription
bristlenose render ./interviews/ -o ./results/                       # re-render from JSON, no LLM
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
pytest                       # 16 tests, should pass in <1s
ruff check .                 # lint
mypy bristlenose/            # type check (some third-party SDK errors are expected)
```

### Architecture

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full project layout, but the short version:

- `bristlenose/stages/` -- the 12-stage pipeline (ingest through render), one module per stage
- `bristlenose/stages/render_html.py` -- HTML report renderer, loads CSS + JS from theme/
- `bristlenose/theme/` -- atomic CSS design system (tokens, atoms, molecules, organisms, templates)
- `bristlenose/theme/js/` -- report JavaScript (8 modules, concatenated at render time)
- `bristlenose/llm/prompts.py` -- LLM prompt templates
- `bristlenose/pipeline.py` -- orchestrator that wires the stages together
- `bristlenose/cli.py` -- Typer CLI entry point

### Releasing

Edit `bristlenose/__init__.py` (the single source of truth for version), commit, tag, push. GitHub Actions handles CI, build, and PyPI publishing automatically. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Changelog

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

- Search-as-you-type quote filtering
- Hide/show individual quotes
- Keyboard shortcuts (j/k navigation, s to star, e to edit)
- User-generated themes
- Lost quotes -- surface what the AI didn't select
- .docx export
- Edit writeback to transcript files
- Multi-participant session support
- Native installers for Ubuntu (Snap) and Windows

Priorities may shift. If something is missing that matters to you, [open an issue](https://github.com/cassiocassio/bristlenose/issues).

---

## Licence

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
