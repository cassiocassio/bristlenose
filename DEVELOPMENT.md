# Development Guide

Clone the repo.

## Prerequisites

- **Python 3.12** — the version pinned in `.tool-versions`, what CI's primary cells and the macOS sidecar build use. The package supports 3.10+ (CI tests 3.10 to 3.14; `.github/workflows/ci.yml` says which cells ship to users), but build a contributor venv on 3.12.
- **Node.js 24** (also pinned in `.tool-versions`) + npm
- **FFmpeg** (`brew install ffmpeg` / `apt install ffmpeg`)
- **git**

## Quick start

```bash
# 1. Python environment — name 3.12 explicitly; a bare `python3` picks up
#    whatever your shell resolves to and silently forks the env off the pin
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev,serve]"

# 2. Frontend
cd frontend && npm install && cd ..

# 3. Environment (set at least one LLM provider key)
cp .env.example .env
# Edit .env — fill in BRISTLENOSE_ANTHROPIC_API_KEY (or another provider)
```

Done. You can now run the pipeline or the dev server.

## Running the app

```bash
# Full pipeline (transcribe + analyse + render)
.venv/bin/bristlenose run path/to/interviews/

# Serve mode with dev tooling (FastAPI + React SPA + Vite HMR — the active development experience)
.venv/bin/bristlenose serve path/to/interviews/ --dev
```

`--dev` starts FastAPI on `:8484` with auto-reload AND spawns Vite on `:5173` for React HMR. Theme CSS is served live from source files (no render step needed). Ctrl-C kills both.

## Testing

```bash
# Python
.venv/bin/python -m pytest tests/           # ~9,000 tests; free, never calls a paid LLM (`-m slow` opts in)
.venv/bin/ruff check .                      # lint (entire repo, not just bristlenose/)
.venv/bin/ruff check --fix .                # lint + auto-fix
.venv/bin/mypy bristlenose/                 # type check (informational, not gated)

# Frontend
cd frontend
npm test                                     # Vitest (3,000+ tests)
npm run build                                # tsc type-check + Vite build
```

**Important:** Always run `npm run build` before committing frontend changes — `tsc -b` catches type errors that Vitest's looser context misses.

## Before committing

```bash
.venv/bin/python -m pytest tests/            # 1. All Python tests pass
.venv/bin/ruff check .                       # 2. No lint errors (whole repo — CI checks tests/ too)
cd frontend && npm run build && npm test     # 3. Frontend types + tests
```

CI runs `ruff check .` (including `tests/`), not just `bristlenose/`. Lint errors in test files go unnoticed if you only check `bristlenose/`.

## Environment variables

Copy `.env.example` to `.env`. You only need one LLM provider key:

| Variable | What |
|----------|------|
| `BRISTLENOSE_LLM_PROVIDER` | `anthropic`, `openai`, `azure`, `google`, `local` or `anyllm` (the CLI normally gets this from `bristlenose configure` / `use`) |
| `BRISTLENOSE_ANTHROPIC_API_KEY` | Claude key (from console.anthropic.com) |
| `BRISTLENOSE_OPENAI_API_KEY` | ChatGPT key (from platform.openai.com) |
| `BRISTLENOSE_GOOGLE_API_KEY` | Gemini key (from aistudio.google.com) |
| `BRISTLENOSE_ANYLLM_MODEL` | any-llm model as `provider:model`, e.g. `mistral:mistral-large-latest` (needs the `any-llm` extra) |
| `BRISTLENOSE_WHISPER_BACKEND` | `auto`, `mlx` (Apple Silicon), `faster-whisper` (CUDA/CPU) |

For Ollama (free, no key): set `BRISTLENOSE_LLM_PROVIDER=local` and install [Ollama](https://ollama.com). See `.env.example` for all options.

## Two render paths

| | Serve mode (`bristlenose serve` — the product) | Static render (sealed byproduct) |
|---|---|---|
| **Routing** | React Router (pathname: `/report/quotes/`) | Vanilla JS (hash: `#quotes`) |
| **React** | Single `RouterProvider` root | Individual `createRoot()` per island |
| **JS** | Vanilla JS loads but nav/toolbar no-op | Full vanilla JS suite active |
| **Data** | API endpoints (`/api/projects/...`) | Baked into HTML / localStorage |
| **User-facing** | Yes — `bristlenose run` opens it automatically; `bristlenose serve <folder>` re-opens an existing project | No (post-A3, 12 May 2026 — `render` command + `--static` flag both removed). Stage 12 still writes the file but its path is never surfaced. Future: repurpose as markdown deliverable (`docs/design-cli-improvements.md` §Future direction) |

Serve mode is the actively developed experience. The static render is a sealed byproduct — written to disk by stage 12 but never surfaced as a user-facing command after A3 (12 May 2026).

## Version bumping

```bash
./scripts/bump-version.py patch    # 0.10.3 → 0.10.4
./scripts/bump-version.py minor    # 0.10.3 → 0.11.0
./scripts/bump-version.py 0.11.0   # explicit version
```

Updates `bristlenose/__init__.py`, the man page and the pbxproj; stages them. It does not commit or tag. After bumping:

1. Add changelog entry to `README.md` and `CHANGELOG.md`
2. Update version in `CLAUDE.md` "Current status" section
3. Commit, then `git tag vX.Y.Z` (after the commit, so it points at it)
4. Push `main` and the tag as two commands — `git push origin main` then
   `git push origin vX.Y.Z` (never one `--tags`; it debounces the release
   workflow). The tag push is what publishes: there is no approval step, and
   it waits for after 9pm London on a working day (CLAUDE.md § Release
   timing). `scripts/release.sh` drives the whole chain; see docs/release.md

## Branches and worktrees

The maintainer works on `main`, in one checkout, committing at each green checkpoint: no branch or worktree per feature. A branch is a free pointer (`git branch -f checkpoint` before risky work, `git revert <sha>` to undo); a worktree costs a whole environment build. A worktree is the exception, for when two environments must be live at once (a long pipeline run while you code something else), and it is made with the `/new-branch` skill, never by hand, because a hand-made one ships without the extras, the frontend build and the symlinks. The rules, with the rollback recipes: [`.claude/branch-workflow.md`](.claude/branch-workflow.md) and `CLAUDE.md` § Working preferences.

Outside contributors fork the repo and branch in their own fork as usual; see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Troubleshooting

**Stale `__pycache__` after branch switch:**
```bash
find . -name __pycache__ -exec rm -rf {} +
.venv/bin/pip install -e ".[dev,serve]"
```

**Broken venv after renaming the repo directory:**
Python editable installs write absolute paths into `.pth` files. If you `mv` the directory, the venv silently breaks. Fix:
```bash
find . -name __pycache__ -exec rm -rf {} +
.venv/bin/python -m pip install -e ".[dev,serve]"
```
Or delete `.venv` and recreate.

**Venv drifted off the pinned Python:**
```bash
.venv/bin/python -V          # must match the `python` line in .tool-versions
```
A venv built by something other than `python3.12 -m venv` — a bare `python3`, or a `uv venv` picked up during crash recovery — can land on a neighbouring minor and stay there indefinitely. Nothing fails loudly: the suite passes on 3.10–3.13, so the only symptom is a dev box that disagrees with CI's primary cell and the macOS sidecar (both 3.12). Rebuild rather than patch:
```bash
rm -rf .venv
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev,serve]"
```
The same accident can drop packages: check `presidio-analyzer` is importable afterwards — it's a core dependency (stage 7, PII removal), but its tests mock or skip, so its absence doesn't redden the suite.

**Debug logging:**
```bash
bristlenose run path/ -v              # verbose terminal output
BRISTLENOSE_LOG_LEVEL=DEBUG bristlenose run path/   # verbose log file
```

**Video thumbnail placeholders (layout testing):**
```bash
BRISTLENOSE_FAKE_THUMBNAILS=1 bristlenose serve path/ --dev
```

**Tests must not depend on local environment.** CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions in tests.

## Further reading

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — code style, project layout, design system, releasing
- [`INSTALL.md`](INSTALL.md) — end-user installation guide
- [`bristlenose/server/CLAUDE.md`](bristlenose/server/CLAUDE.md) — serve mode architecture, API endpoints
- [`bristlenose/theme/CLAUDE.md`](bristlenose/theme/CLAUDE.md) — CSS conventions, dark mode, JS gotchas
- [`docs/design-react-migration.md`](docs/design-react-migration.md) — React SPA migration plan (10 steps)
