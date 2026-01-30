# Bristlenose

Open-source user-research analysis. Runs on your laptop.

Point it at a folder of interview recordings. It transcribes, extracts verbatim quotes, groups them by screen and theme, and produces a browsable HTML report. Nothing gets uploaded. Your recordings stay on your machine.

---

## Why

The tooling for analysing user-research interviews is either expensive or manual. Bristlenose connects local recordings to AI models via API and produces structured output -- themed quotes, sentiment, friction points -- without requiring a platform subscription or hours of spreadsheet work.

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

## Built so far (0.1.x)

Full pipeline, HTML report with atomic CSS design system, clickable timecodes, popout video player, sentiment histogram (horizontal bars, side-by-side AI and user-tag charts), favourite quotes with CSV export, inline quote editing, tag system (AI-generated and user-added tags with auto-suggest, localStorage persistence, CSV export with separate AI/User columns), re-render command (`bristlenose render`), Apple Silicon GPU acceleration (MLX), cross-platform support.

## Roadmap

Search-as-you-type filtering, hide/show quotes, keyboard shortcuts, theme management in the browser (dark mode, user-generated themes), lost quotes (surface what the AI didn't select), transcript linking, .docx export, edit writeback, multi-participant sessions.

**Packaging** -- native installers for macOS, Ubuntu/Linux, and Windows so you don't need to manage Python yourself.

Details and priorities may shift. If something is missing that matters to you, open an issue.

---

## Get involved

**Researchers** -- use it on real recordings, open issues when the output is wrong or incomplete.

**Developers** -- Python 3.10+, fully typed, Pydantic models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the CLA. Key files: `bristlenose/stages/render_html.py` (report renderer), `bristlenose/llm/prompts.py` (LLM prompts).

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

## Development

```bash
pytest                       # tests
pytest --cov=bristlenose     # coverage
ruff check .                 # lint
mypy bristlenose/            # type check
```

Primary development is on macOS. Feedback from Linux and Windows users is welcome.

---

## Licence

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
