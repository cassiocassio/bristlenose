# Bristlenose

User-research interview analysis tool.

Point it at a folder of interview recordings: audio, video, and/or transcripts from Teams or Zoom.

Bristlenose will:
- transcribe, identify participants and moderators
- extract and lightly tidy near-verbatim quotes
- produce a browsable HTML report, grouping quotes by screen or topic, and by theme
- let you favourite and tag quotes, to pick the best evidence and gather your own insights
- suggest frustration and pain points via sentiment analysis
- let you copy blocks of quotes as CSV to clipboard, for pasting into research boards like Miro

Runs on your machine, but needs a Claude or ChatGPT API key. Recordings stay local -- transcript text is sent to the LLM API.

---

## Why

The tooling for analysing user-research interviews is either expensive SaaS platforms or manual spreadsheet work.

It's built by a practising researcher. It's free and open source under AGPL-3.0.

---

## What it does

A 12-stage pipeline: ingest files, extract audio, parse existing subtitles/transcripts, transcribe via Whisper, identify speakers, merge and normalise transcripts, redact PII (Presidio), segment topics, extract quotes, cluster by screen, group by theme, render output.

```bash
bristlenose run ./interviews/ -o ./results/
```

### Output

```
output/
  research_report.html       # browsable report
  research_report.md         # Markdown version
  bristlenose-theme.css      # stylesheet (regenerated on every run)
  bristlenose-logo.png       # project logo
  bristlenose-player.html    # popout video player
  raw_transcripts/           # one .txt per participant
  cooked_transcripts/        # cleaned transcripts after PII removal
  intermediate/              # JSON files (used by `bristlenose render`)
```

The HTML report includes: participant table, sections (by screen), themes (cross-participant), sentiment histogram, friction points, user journeys, clickable timecodes with popout video player, favourite quotes (star, reorder, export as CSV), inline editing for transcription corrections, and a tag system (AI-generated badges plus user-added tags with auto-suggest).

### Quote format

```
05:23 "I was... trying to find the button and it just... wasn't there." -- p3
```

Filler words replaced with `...`. Editorial insertions in `[square brackets]`. Emotion and strong language preserved.

---

## Install

Requires ffmpeg and an API key for Anthropic or OpenAI.

```bash
# macOS (Homebrew)
brew install cassiocassio/bristlenose/bristlenose

# macOS / Linux / Windows (pipx)
pipx install bristlenose

# or with uv (faster alternative to pipx)
uv tool install bristlenose
```

The Homebrew formula handles ffmpeg and Python automatically. If using pipx or uv, install ffmpeg separately (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Debian/Ubuntu).

Then configure your API key:

```bash
export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...
# or
export BRISTLENOSE_OPENAI_API_KEY=sk-...
```

---

## Usage

```bash
bristlenose run ./interviews/ -o ./results/
bristlenose run ./interviews/ -o ./results/ -p "Q1 Usability Study"
bristlenose transcribe-only ./interviews/ -o ./results/       # no LLM needed
bristlenose analyze ./results/raw_transcripts/ -o ./results/  # skip transcription
bristlenose render ./interviews/ -o ./results/                # re-render reports (no LLM)
```

Supported: `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`, `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.srt`, `.vtt`, `.docx` (Teams exports). Files sharing a name stem are treated as one session.

Configuration via `.env`, environment variables (prefix `BRISTLENOSE_`), or `bristlenose.toml`. See `.env.example`.

---

## Hardware

Auto-detected. Apple Silicon uses MLX on Metal GPU. NVIDIA uses faster-whisper with CUDA. Everything else falls back to CPU.

---

## Changelog

### 0.3.2

- Fix tag auto-suggest offering tags the quote already has

### 0.3.1

- Single-source version: `__init__.py` is the only file to edit when releasing
- Updated release process docs in CONTRIBUTING.md

### 0.3.0

- CI on every push/PR (ruff lint, mypy type-check, pytest)
- Automated PyPI publishing on tagged releases via OIDC trusted publishing
- No tokens needed in CI -- uses GitHub's OpenID Connect

### 0.2.0

- Extract 720-line JS from `render_html.py` into 8 standalone modules (`bristlenose/theme/js/`): storage, player, favourites, editing, tags, histogram, csv-export, main
- Atomic CSS design system (`bristlenose/theme/`): tokens, atoms, molecules, organisms, templates; concatenated at render time
- Tag system: AI-generated badges (deletable with restore) + user-added tags with auto-suggest, keyboard navigation, localStorage persistence
- Favourite quotes with FLIP animation and CSV export (separate AI/User tag columns)
- Inline quote editing with contenteditable and localStorage persistence
- Sentiment histogram: horizontal bars, side-by-side AI + user-tag charts
- `bristlenose render` command for re-rendering from intermediate JSON without LLM calls
- `render_html.py` reduced from 1,534 to 811 lines
- README, CONTRIBUTING.md, TODO roadmap

### 0.1.0

- 12-stage pipeline: ingest, extract audio, parse subtitles/docx, transcribe (Whisper), identify speakers, merge, PII redaction (Presidio), topic segmentation, quote extraction, screen clustering, thematic grouping, render
- HTML report with external CSS theme, clickable timecodes, popout video player
- Markdown report output
- Quote enrichment: intent, emotion, intensity, journey stage
- Friction points (confusion/frustration/error-recovery moments)
- User journey summary per participant
- Apple Silicon GPU acceleration (MLX on Metal)
- Cross-platform support (macOS, Linux, Windows)
- Hardware auto-detection (MLX, CUDA, CPU fallback)
- PII redaction with Presidio (narrowed entities, cooked transcripts)
- Published to PyPI and Homebrew tap
- AGPL-3.0 licence with CLA
- 16 passing tests

---

## Roadmap

Search-as-you-type filtering, hide/show quotes, keyboard shortcuts, theme management in the browser (dark mode, user-generated themes), lost quotes (surface what the AI didn't select), transcript linking, .docx export, edit writeback, multi-participant sessions.

**Packaging** -- native installers for macOS, Ubuntu/Linux, and Windows so you don't need to manage Python yourself.

Details and priorities may shift. If something is missing that matters to you, open an issue.

---

## Get involved

**Researchers** -- use it on real recordings, open issues when the output is wrong or incomplete.

**Developers** -- Python 3.10+, fully typed, Pydantic models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the CLA. Key files: `bristlenose/stages/render_html.py` (report renderer), `bristlenose/llm/prompts.py` (LLM prompts).

---

## Development setup

For contributing or working from source:

```bash
# macOS (Apple Silicon)
brew install python@3.12 ffmpeg pkg-config
cd bristlenose
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,apple]"
cp .env.example .env   # add your BRISTLENOSE_ANTHROPIC_API_KEY

# macOS (Intel)
/usr/local/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Linux
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Windows
python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"
```

```bash
pytest                       # tests
pytest --cov=bristlenose     # coverage
ruff check .                 # lint
mypy bristlenose/            # type check
```

> **If you rename or move the project directory**, the editable install breaks silently
> (absolute paths baked into `.pth` files and CLI shebangs). Fix with:
> `find . -name __pycache__ -exec rm -rf {} +` then
> `.venv/bin/python -m pip install -e ".[dev]"`

Primary development is on macOS. Feedback from Linux and Windows users is welcome.

---

## Licence

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
