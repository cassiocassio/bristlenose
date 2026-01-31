# File Map

Quick reference for finding things in the bristlenose codebase.

## Core package

| File | Role |
|------|------|
| `bristlenose/__init__.py` | Version — **single source of truth** (`__version__`) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/models.py` | Data models and enums |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/__main__.py` | `python -m bristlenose` entry point |

## Pipeline stages (`bristlenose/stages/`)

All 12 stages of the pipeline, from ingest to render.

| File | Role |
|------|------|
| `ingest.py` | Stage 1: discover input files |
| `extract_audio.py` | Stage 2: extract audio from video |
| `parse_subtitles.py` | Stage 3: parse SRT/VTT subtitle files |
| `parse_docx.py` | Stage 4: parse .docx transcripts |
| `transcribe.py` | Stage 5: Whisper transcription |
| `identify_speakers.py` | Stage 6: speaker diarisation |
| `merge_transcript.py` | Stage 7: merge and write transcripts |
| `pii_removal.py` | Stage 8: PII redaction |
| `topic_segmentation.py` | Stage 9: segment by topic |
| `quote_extraction.py` | Stage 10: extract quotes via LLM |
| `quote_clustering.py` | Stage 11: cluster quotes |
| `thematic_grouping.py` | Stage 12a: group into themes |
| `render_html.py` | Stage 12b: HTML report renderer, loads CSS/JS from theme/ |
| `render_output.py` | Markdown report + JSON snapshots for `render` command |

## LLM layer (`bristlenose/llm/`)

| File | Role |
|------|------|
| `prompts.py` | LLM prompt templates |
| `structured.py` | Pydantic schemas for structured LLM output |
| `client.py` | Anthropic/OpenAI client abstraction |

## Theme / design system (`bristlenose/theme/`)

| File | Role |
|------|------|
| `tokens.css` | Design tokens (`--bn-*` custom properties) |
| `images/` | Static assets (light + dark logos) |
| `atoms/` | Smallest CSS components (badge, button, input, etc.) |
| `molecules/` | Small groups of atoms (badge-row, bar-group, etc.) |
| `organisms/` | Self-contained UI sections (blockquote, toolbar, etc.) |
| `templates/` | Page-level layout (report.css, print.css) |
| `js/` | 8 JS modules (storage, player, favourites, editing, tags, histogram, csv-export, main) |

## Utilities (`bristlenose/utils/`)

| File | Role |
|------|------|
| `markdown.py` | **Markdown style template** — single source of truth for all markdown formatting. Change formatting here, not in stage files |
| `text.py` | Text processing (smart quotes, disfluency removal) |
| `timecodes.py` | Timecode parsing and formatting |
| `hardware.py` | GPU/CPU auto-detection (MLX, CUDA, CPU fallback) |
| `audio.py` | Audio extraction helpers |

## Tests

| File | Tests |
|------|-------|
| `tests/test_markdown.py` | `utils/markdown.py` — constants, formatters, quote blocks, friction items (25 tests) |
| `tests/test_transcript_writing.py` | Transcript writers (.txt, .md) and parser round-trips, incl. mixed timecodes (22 tests) |
| `tests/test_models.py` | Timecode format/parse, round-trips, ExtractedQuote (12 tests) |
| `tests/test_dark_mode.py` | Dark mode: CSS tokens, HTML attributes, logo switching, config (17 tests) |
| `tests/test_text_utils.py` | Smart quotes, disfluency removal, text cleanup (11 tests) |

## CI/CD and docs

| File | Role |
|------|------|
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR |
| `.github/workflows/release.yml` | Release: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of tap repo workflow (authoritative copy lives in `homebrew-bristlenose`) |
| `docs/release.md` | Full release pipeline, secrets, Homebrew tap details |
| `TODO.md` | Detailed roadmap and task tracking |
| `CONTRIBUTING.md` | Dev setup, design system docs, release process |
