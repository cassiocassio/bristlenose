# Development Guide

Clone the repo, get productive in 5 minutes.

## Prerequisites

- **Python 3.10+**
- **Node.js** (LTS) + npm
- **FFmpeg** (`brew install ffmpeg` / `apt install ffmpeg`)
- **git**

## Quick start

```bash
# 1. Python environment
python3 -m venv .venv
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

# Serve mode (React SPA + API — the active development experience)
.venv/bin/bristlenose serve path/to/interviews/ --dev

# Combined dev server (Vite HMR + FastAPI in one terminal)
./scripts/dev.sh path/to/interviews/
```

`scripts/dev.sh` starts Vite on `:5173` (proxying to FastAPI on `:8150`) and FastAPI with `--dev`. Ctrl-C kills both.

For serve mode without `scripts/dev.sh`, run two terminals:

```bash
# Terminal 1: Vite dev server
cd frontend && npm run dev

# Terminal 2: FastAPI
.venv/bin/bristlenose serve path/to/interviews/ --dev --no-open
```

## Testing

```bash
# Python
.venv/bin/python -m pytest tests/           # all tests (~1,800)
.venv/bin/ruff check .                      # lint (entire repo, not just bristlenose/)
.venv/bin/ruff check --fix .                # lint + auto-fix
.venv/bin/mypy bristlenose/                 # type check (informational, not gated)

# Frontend
cd frontend
npm test                                     # Vitest (~635 tests)
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
| `BRISTLENOSE_LLM_PROVIDER` | `anthropic`, `openai`, `azure`, `google`, or `local` |
| `BRISTLENOSE_ANTHROPIC_API_KEY` | Claude key (from console.anthropic.com) |
| `BRISTLENOSE_OPENAI_API_KEY` | ChatGPT key (from platform.openai.com) |
| `BRISTLENOSE_GOOGLE_API_KEY` | Gemini key (budget option, ~$0.20/study) |
| `BRISTLENOSE_WHISPER_BACKEND` | `auto`, `mlx` (Apple Silicon), `faster-whisper` (CUDA/CPU) |

For Ollama (free, no key): set `BRISTLENOSE_LLM_PROVIDER=local` and install [Ollama](https://ollama.ai). See `.env.example` for all options.

## Two render paths

| | Serve mode (`bristlenose serve`) | Static render (`bristlenose render`) |
|---|---|---|
| **Routing** | React Router (pathname: `/report/quotes/`) | Vanilla JS (hash: `#quotes`) |
| **React** | Single `RouterProvider` root | Individual `createRoot()` per island |
| **JS** | Vanilla JS loads but nav/toolbar no-op | Full vanilla JS suite active |
| **Data** | API endpoints (`/api/projects/...`) | Baked into HTML / localStorage |

Serve mode is the actively developed experience. Static render is a frozen offline fallback.

## Version bumping

```bash
./scripts/bump-version.py patch    # 0.10.3 → 0.10.4
./scripts/bump-version.py minor    # 0.10.3 → 0.11.0
./scripts/bump-version.py 0.11.0   # explicit version
```

Updates `bristlenose/__init__.py` and the man page, creates a git tag. After bumping:

1. Add changelog entry to `README.md` and `CHANGELOG.md`
2. Update version in `CLAUDE.md` "Current status" section
3. Commit and push with tags: `git push origin main --tags`

## Git worktrees

Feature branches live in separate worktrees so multiple tasks can run in parallel:

```
bristlenose/                              # main — always on main
bristlenose_branch react-router/          # react-router branch
bristlenose_branch codebook/              # codebook branch
```

```bash
# Create a new feature branch + worktree
cd /Users/cassio/Code/bristlenose
git branch my-feature main
git worktree add "../bristlenose_branch my-feature" my-feature
cd "../bristlenose_branch my-feature"
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,serve]"
```

Each worktree needs its own `.venv`. Commits are shared instantly across all worktrees.

**Never check out a feature branch inside the main `bristlenose/` directory** — use worktrees instead.

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
