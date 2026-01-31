# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Anthropic or OpenAI APIs.

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates. All values via `--bn-*` custom properties in `tokens.css`, never hard-coded
- **JS modules** in `bristlenose/theme/js/` — 8 standalone files concatenated at render time (same pattern as CSS)
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
| `bristlenose/stages/` | All 12 pipeline stages |
| `bristlenose/stages/render_html.py` | HTML report renderer, loads CSS/JS from theme/ |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/llm/structured.py` | Pydantic schemas for structured LLM output |
| `bristlenose/llm/client.py` | Anthropic/OpenAI client abstraction |
| `bristlenose/theme/tokens.css` | Design tokens (`--bn-*` custom properties) |
| `bristlenose/theme/atoms/` | Smallest CSS components (badge, button, input, etc.) |
| `bristlenose/theme/js/` | 8 JS modules (storage, player, favourites, editing, tags, histogram, csv-export, main) |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection (MLX, CUDA, CPU fallback) |
| `tests/` | pytest test suite |
| `TODO.md` | Detailed roadmap and task tracking |
| `CONTRIBUTING.md` | Dev setup, design system docs, release process |

## How to release

1. Edit version in `bristlenose/__init__.py`
2. `git commit && git tag vX.Y.Z && git push origin main --tags`
3. GitHub Actions handles CI, build, and PyPI publish (OIDC trusted publishing)
4. Homebrew tap update is manual: update url + sha256 in `Formula/bristlenose.rb`

## CI gates

- **Ruff**: hard gate
- **pytest**: hard gate
- **mypy**: informational (continue-on-error due to third-party SDK type issues)

## LLM provider setup

API keys via env vars (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), `.env` file, or `bristlenose.toml`. Prefix with `BRISTLENOSE_` for namespaced variants.

## Current status (v0.3.3, Jan 2026)

Core pipeline complete and published to PyPI + Homebrew. Active roadmap is UI polish and report interactivity improvements. See `TODO.md` for full task list.

## Working preferences

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- Run `ruff check bristlenose/` before committing
- Run `pytest` to verify changes
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")
- The repo directory is `/Users/cassio/Code/gourani` (legacy name, package is bristlenose)
