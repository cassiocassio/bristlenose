# Deployment targets

Where Bristlenose is expected to run, and what each target implies for deps, packaging, and dev workflow. Update as targets are added or confirmed empirically.

## Declared targets

### 1. macOS arm64 (primary dev)

- User's daily driver (Apple Silicon, macOS 26.x)
- BSD userland — see CLAUDE.md "macOS BSD userland" gotcha section
- Homebrew available for `ffmpeg`, `gsed`, etc.
- MLX whisper available (platform-gated in `pyproject.toml`)
- Installed via Homebrew tap or `pip install -e '.[dev,serve]'` in `.venv`

### 2. Linux x86_64 via GitHub Actions CI

- Ubuntu runners (see `.github/workflows/`)
- GNU userland — no BSD gotchas
- No LLM API keys, no Ollama — all environment-dependent tests must mock
- Release pipeline: PyPI, Snap, Homebrew tap

### 3. Claude Code Cloud VM (NEW — undocumented)

**Status:** presumed Ubuntu LTS x86_64, GNU userland, ephemeral per session. Not empirically verified.

**Likely use case:** code work (tests, lint, frontend build, refactors) on public code paths. **Not** pipeline runs on private interview data — interview recordings never leave the laptop, and Cloud egress contradicts the local-first product pitch.

**Known constraints:**
- No access to user's Homebrew, `.venv`, SSH agent, or `trial-runs/`
- No MLX (x86_64 only); `apple` extra unavailable
- Ephemeral — no state between sessions
- Network egress is from Anthropic infra, not the user's machine

**To confirm:** run the checklist below next Cloud session.

## Cloud VM audit checklist

Run in a fresh Claude Code Cloud session and paste output into this doc under "Cloud VM spec" below.

```bash
# Release + arch
lsb_release -a
uname -a
cat /etc/cloud/build.info 2>/dev/null

# Language runtimes
python3 --version
node --version 2>/dev/null || echo "node: absent"
ffmpeg -version 2>/dev/null | head -1 || echo "ffmpeg: absent"

# Package manager state
apt list --installed 2>/dev/null | wc -l
snap list 2>/dev/null || echo "snap: absent"

# Bristlenose install
git clone https://github.com/<user>/bristlenose.git /tmp/bn && cd /tmp/bn
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,serve]'
.venv/bin/python -m pytest tests/ -x --tb=short 2>&1 | tail -20
.venv/bin/ruff check .

# Frontend (needs node)
cd frontend && npm ci && npm run build 2>&1 | tail -10
```

## Cloud VM spec (to fill in)

- **Release:** _TBD_
- **Kernel / arch:** _TBD_
- **Python:** _TBD_
- **Node:** _TBD_ (preinstalled? version?)
- **ffmpeg:** _TBD_ (preinstalled? version?)
- **Preinstalled apt packages:** _TBD_
- **`pip install -e '.[dev,serve]'` clean?** _TBD_
- **`pytest tests/` passes?** _TBD_
- **`ruff check .` clean?** _TBD_
- **`npm run build` works?** _TBD_

## Use-case boundary

| Workflow | Cloud? | Reason |
|---|---|---|
| Run tests on a branch | ✅ | Same family as CI Ubuntu |
| Frontend refactors / Vite build | ✅ | Node + npm available (to confirm) |
| Ruff / mypy sweeps | ✅ | Pure Python |
| Code review / exploration | ✅ | Read-only, no deps |
| `bristlenose run` on real interviews | ❌ | Interview data never leaves laptop; no `trial-runs/` in VM |
| `/deploy-website` | ❌ | Needs SSH agent (same reason as sandbox) |
| Snap/Homebrew release | ❌ | Needs signing keys, tags on user's machine |
| Desktop SwiftUI work | ❌ | macOS-only (Xcode) |

## Revisit trigger

- Anthropic announces changes to Cloud VM image (base release, preinstalled tooling)
- Bristlenose adds a dep that fails on Ubuntu LTS (e.g. a newer Python/Node requirement)
- User hits a "works locally, broken on Cloud" surprise worth capturing
