# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Anthropic or OpenAI APIs.

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates. All values via `--bn-*` custom properties in `tokens.css`, never hard-coded
- **JS modules** in `bristlenose/theme/js/` — 8 standalone files concatenated at render time (same pattern as CSS)
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting (headings, quotes, badges, transcript segments). Change formatting here, not in stage files
- **Licence**: AGPL-3.0 with CLA

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls).

## File map

| File | Role |
|------|------|
| `bristlenose/__init__.py` | Version (single source of truth) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/models.py` | Data models and enums |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/__main__.py` | `python -m bristlenose` entry point |
| `bristlenose/stages/` | All 12 pipeline stages |
| `bristlenose/stages/parse_docx.py` | Parse .docx transcripts |
| `bristlenose/stages/render_html.py` | HTML report renderer, loads CSS/JS from theme/ |
| `bristlenose/stages/render_output.py` | Markdown report + JSON snapshots for `render` command |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/llm/structured.py` | Pydantic schemas for structured LLM output |
| `bristlenose/llm/client.py` | Anthropic/OpenAI client abstraction |
| `bristlenose/theme/tokens.css` | Design tokens (`--bn-*` custom properties) |
| `bristlenose/theme/images/` | Static assets (project logo) |
| `bristlenose/theme/atoms/` | Smallest CSS components (badge, button, input, etc.) |
| `bristlenose/theme/js/` | 8 JS modules (storage, player, favourites, editing, tags, histogram, csv-export, main) |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection (MLX, CUDA, CPU fallback) |
| `bristlenose/utils/audio.py` | Audio extraction helpers |
| `bristlenose/utils/markdown.py` | **Markdown style template** — single source of truth for all markdown formatting (constants + formatter functions) |
| `bristlenose/utils/text.py` | Text processing (smart quotes, disfluency removal) |
| `bristlenose/utils/timecodes.py` | Timecode parsing and formatting |
| `tests/` | pytest test suite |
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR |
| `.github/workflows/release.yml` | Release: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of tap repo workflow (authoritative copy lives in `homebrew-bristlenose`) |
| `TODO.md` | Detailed roadmap and task tracking |
| `CONTRIBUTING.md` | Dev setup, design system docs, release process |

## How to release

1. Edit version in `bristlenose/__init__.py`
2. Update changelog in `README.md` (## Changelog section)
3. `git commit && git tag vX.Y.Z && git push origin main --tags`
4. GitHub Actions handles the rest: CI → PyPI publish → GitHub Release → Homebrew tap update

The full release pipeline runs in two repos:

| Step | Where | Trigger |
|------|-------|---------|
| CI (ruff, mypy, pytest) | `bristlenose` repo, `ci.yml` | `release.yml` calls it via `workflow_call` |
| Build sdist + wheel | `bristlenose` repo, `release.yml` `build` job | After CI passes |
| Publish to PyPI | `bristlenose` repo, `release.yml` `publish` job | After build, via OIDC trusted publishing |
| Create GitHub Release | `bristlenose` repo, `release.yml` `github-release` job | After publish |
| Dispatch to Homebrew tap | `bristlenose` repo, `release.yml` `notify-homebrew` job | After publish, sends `repository_dispatch` |
| Update formula | `homebrew-bristlenose` repo, `update-formula.yml` | Receives dispatch, fetches sha256 from PyPI, patches formula, pushes |

## CI/CD secrets and cross-repo setup

| Secret | Stored in | Purpose |
|--------|-----------|---------|
| `HOMEBREW_TAP_TOKEN` | bristlenose repo → Settings → Secrets → Actions | Classic PAT with `repo` scope; used by `notify-homebrew` to dispatch to the tap repo |
| PyPI OIDC | pypi.org trusted publisher config | No token needed — `release.yml` uses `id-token: write` permission |
| `GITHUB_TOKEN` | automatic | Used by `github-release` job to create GitHub Releases |

The Homebrew tap is a **separate repo**: [`cassiocassio/homebrew-bristlenose`](https://github.com/cassiocassio/homebrew-bristlenose). It contains `Formula/bristlenose.rb` and `.github/workflows/update-formula.yml`. A reference copy of `update-formula.yml` is kept in this repo at `.github/workflows/homebrew-tap/update-formula.yml` for convenience — the authoritative copy is in the tap repo.

## CI gates

- **Ruff**: hard gate
- **pytest**: hard gate
- **mypy**: informational (continue-on-error due to third-party SDK type issues)

## LLM provider setup

API keys via env vars (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), `.env` file, or `bristlenose.toml`. Prefix with `BRISTLENOSE_` for namespaced variants.

## Current status (v0.3.7, Jan 2026)

Core pipeline complete and published to PyPI + Homebrew. v0.3.7 adds a markdown style template system, per-session `.md` transcripts, and participant codes in transcript output. Active roadmap is UI polish and report interactivity improvements. See `TODO.md` for full task list.

## Working preferences

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- Run `.venv/bin/ruff check bristlenose/` before committing (no global ruff install)
- Run `.venv/bin/python -m pytest tests/` to verify changes
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")
- The repo directory is `/Users/cassio/Code/gourani` (legacy name, package is bristlenose)
