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
| `bristlenose/people.py` | People file: load, compute, merge, write, display names, name extraction, short name heuristic |
| `bristlenose/__main__.py` | `python -m bristlenose` entry point |
| `bristlenose/output_paths.py` | Output directory structure and path helpers (`OutputPaths` dataclass) |
| `bristlenose/status.py` | Project status: read manifest, validate cached artifacts, format resume summary |

## Analysis (`bristlenose/analysis/`)

Post-pipeline statistical analysis — matrix building and signal detection. Pure computation from existing quote/cluster/theme data, no LLM calls.

| File | Role |
|------|------|
| `models.py` | Data models: `MatrixCell`, `Matrix`, `SignalQuote`, `Signal`, `AnalysisResult` (plain dataclasses, not Pydantic) |
| `metrics.py` | 5 pure math functions: `concentration_ratio`, `simpsons_neff`, `mean_intensity`, `composite_signal`, `adjusted_residual` |
| `matrix.py` | Build section×sentiment and theme×sentiment contingency matrices from grouped quotes |
| `signals.py` | Detect notable cells, classify confidence (strong/moderate/emerging), attach quotes |

## Pipeline stages (`bristlenose/stages/`)

All 12 stages of the pipeline, from ingest to render.

| File | Role |
|------|------|
| `ingest.py` | Stage 1: discover input files |
| `extract_audio.py` | Stage 2: extract audio from video |
| `parse_subtitles.py` | Stage 3: parse SRT/VTT subtitle files |
| `parse_docx.py` | Stage 4: parse .docx transcripts |
| `transcribe.py` | Stage 5: Whisper transcription |
| `identify_speakers.py` | Stage 5b: speaker role identification + name/title extraction (`SpeakerInfo`) |
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
| `atoms/` | Smallest CSS components (badge, button, input, span-bar, etc.) |
| `molecules/` | Small groups of atoms (badge-row, bar-group, name-edit, transcript-annotations, etc.) |
| `organisms/` | Self-contained UI sections (blockquote, toolbar, etc.) |
| `templates/` | Page-level layout (report.css, transcript.css, print.css) |
| `js/` | 19 JS modules — report: storage, badge-utils, modal, codebook, player, starred, editing, tags, histogram, csv-export, view-switcher, search, tag-filter, hidden, names, focus, feedback, analysis, main; transcript: storage, badge-utils, player, transcript-names, transcript-annotations; codebook: storage, badge-utils, modal, codebook; analysis: storage, analysis |

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
| `tests/test_name_extraction.py` | Name extraction, auto-populate, short name heuristic, SpeakerRoleItem compat (26 tests) |
| `tests/test_transcript_annotations.py` | Transcript quote annotations: highlight marking, quote map, segment classes, citation marks, JS bootstrap (26 tests) |
| `tests/test_analysis_metrics.py` | Analysis math: concentration ratio, Simpson's Neff, mean intensity, composite signal, adjusted residual (32 tests) |
| `tests/test_analysis_matrix.py` | Analysis matrix builder: empty/single/multi clusters, sentiment filtering, participant counting (12 tests) |
| `tests/test_analysis_signals.py` | Signal detection: thresholds, sorting, top-n limiting, confidence classification, quote ordering (11 tests) |
| `tests/test_status.py` | Project status: manifest reading, stage detail, file validation, resume summary (14 tests) |

## Man page

| File | Role |
|------|------|
| `bristlenose/data/bristlenose.1` | Man page (troff, canonical). Bundled in wheel. Self-installs to `~/.local/share/man/man1/` on first run |
| `man/bristlenose.1` | Symlink → `../bristlenose/data/bristlenose.1`. Used by CI version check, snap build, release asset |

## Snap packaging

| File | Role |
|------|------|
| `snap/snapcraft.yaml` | Snap recipe: classic confinement, core24, Python plugin, bundles FFmpeg + spaCy model + man page |

## Design artifacts (WIP, not shipped to users)

| Directory | Contents |
|-----------|----------|
| `docs/mockups/` | Standalone HTML mockups — visual experiments for features in progress |
| `docs/design-system/` | Style guide and icon catalog — reference for contributors |
| `experiments/` | Throwaway prototypes — CSS/JS experiments, A/B comparisons |

These are working materials for contributors, not part of the application. Users never see them (no links from the report or CLI). They live in the tree for backup and collaboration — anyone working on the UI should browse them to understand design intent.

## CI/CD and docs

| File | Role |
|------|------|
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR |
| `.github/workflows/release.yml` | Release: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/snap.yml` | Snap: build → edge (on push to main) / stable (on v* tags) |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of tap repo workflow (authoritative copy lives in `homebrew-bristlenose`) |
| `docs/release.md` | Full release pipeline, secrets, Homebrew tap details, Snap Store setup |
| `docs/design-doctor-and-snap.md` | Design doc: doctor command + snap packaging (includes implementation notes and local build workflow) |
| `TODO.md` | Detailed roadmap and task tracking |
| `CONTRIBUTING.md` | Dev setup, design system docs, release process |
