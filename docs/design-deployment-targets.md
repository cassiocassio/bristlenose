---
status: current
last-trued: 2026-08-27
trued-against: HEAD on 2026-08-27
---

## Changelog

- _2026-08-27_ — trued for Fedora. Added target 4 (Fedora 43 x86_64), which was
  exercised end to end on real Intel hardware that day, and corrected the
  release-pipeline enumeration at target 2, which named three channels when a
  fourth exists. Front-matter added; the doc had none. Deliberately left the
  Apr-2026 Cloud VM measurements alone — "2230 tests" reads stale against
  today's 4243, but the section dates itself, so it is an honest historical
  measurement rather than rot, and nobody has re-run the suite on a Cloud VM.

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
- Release pipeline: PyPI, Snap, Homebrew tap — and a Fedora Copr, **built and
  proven but not published** (`docs/design-fedora-packaging.md` §7). Every other
  enumeration of the channel set in this repo still says three, correctly; they
  all become wrong on the day the Copr publishes.

### 3. Claude Code Cloud VM (verified Apr 2026)

**Status:** Ubuntu 24.04.4 LTS (Noble Numbat) x86_64, GNU userland, ephemeral per session. Empirically verified — full test suite green, frontend builds, `bristlenose doctor` passes.

**Real use cases (proven):**
- Full Python test suite (2230 passed, 9 skipped, 22 xfailed in ~3 min)
- Ruff on the whole repo (clean)
- Frontend Vite build (563 ms)
- CLI exploration (`bristlenose doctor`, `--help`, etc.)
- Document work and design writing (used heavily on iPad-only trip, Apr 2026)
- **Non-browser pipeline work — viable.** `ffmpeg` installs via apt, `faster-whisper` CPU backend is there, `api.anthropic.com` is reachable (~126 ms). You can transcribe + analyse a small synthetic fixture committed to a branch. The blocker is not capability — it's that real interview data lives on the laptop and ephemeral sessions can't carry it.

**Known constraints:**
- No access to user's Homebrew, `.venv`, SSH agent, or `trial-runs/`
- No MLX (x86_64 only); `apple` extra unavailable → transcription falls back to CPU `faster-whisper` (slow for long recordings, fine for tests)
- Ephemeral — no state between sessions; `.venv` must be recreated each time
- We run as root inside a gVisor sandbox (`uname` reports kernel 4.4.0 / "runsc" — that's the sandbox runtime, not the real host)
- apt works (sudo-less, we're root) — 687 packages preinstalled, anything else is a one-line install
- No `ollama` → local-LLM path is unavailable. Hosted providers (Claude, ChatGPT, Gemini) work if you set an API key
- Git fetches go through a proxy (`CCR_TEST_GITPROXY=1`, origin on `127.0.0.1`) — transparent for normal use

**Browser preview of served HTML:** unknown from inside the VM. The Claude Code-in-assistant "preview" tools (`preview_start` etc.) are explicitly banned for Bristlenose (see CLAUDE.md — they fail consistently). Whether the Claude Code *web client* on iPad offers a port-forwarding pane (à la Codespaces) is a UI-side question, not testable from here. If it does, `bristlenose serve --host 0.0.0.0 --port 8150` would be the target. Worth a manual experiment next time you're on iPad.

### 4. Fedora x86_64 (verified 27 Aug 2026)

**Status:** Fedora 43, Python 3.14.7, rpm 6.0.2, GNU userland. Empirically
verified on real Intel hardware (Xeon Platinum 8488C via `aella up --fedora`,
which reported `avx2` and `avx512f`), not emulation. That distinction is worth
keeping: `ctranslate2` picks SIMD kernels at run time, so a qemu-emulated
x86_64 box is not evidence about how transcription behaves on a real one.

**Verified there:**
- `mock` build of the RPM with **no network**, exit 0
- `dnf install` of the result, `bristlenose doctor` green bar the API key
- A real transcription end to end: Teams-shaped H.264 + AAC `.mp4` → correct
  transcript, 12.6s
- `ffmpeg-free` decodes everything the pipeline needs (§2 of the Fedora doc)

**NOT verified there, and do not assume it:** the pytest suite has never been
run on Fedora or on Python 3.14. `requires-python` allows 3.10+, and the
vendored wheels resolve for cp314, but that is an install-time fact, not a
test-suite one.

### Deferred: Windows x86_64 (CLI only, via Scoop)

Parked in the long grass. CLI port via Scoop is costed at ~1.5–2 weeks for a contributor familiar with Python packaging on Windows. No bundled Python, no codesigning, no SKU split — Scoop dep on `python` + `ffmpeg`, install-time GPU probe for CPU vs CUDA torch wheel, one universal manifest. See [design-windows-port.md](design-windows-port.md). Open invitation in [CONTRIBUTING.md](../CONTRIBUTING.md#windows-port). Windows-native GUI app is out of scope.

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

## Cloud VM spec (verified 17 Apr 2026)

- **Release:** Ubuntu 24.04.4 LTS (Noble Numbat)
- **Kernel / arch:** x86_64, gVisor sandbox (`runsc`, reports 4.4.0 — not the real host kernel)
- **User:** root (sudo-less; apt works directly)
- **Python:** 3.11.15 at `/usr/local/bin/python3` (meets `>=3.10` requirement)
- **Node:** 22.22.2, npm 10.9.7 (preinstalled)
- **ffmpeg:** not preinstalled; `apt-get install -y ffmpeg` installs 6.1.1-3ubuntu5 (takes <30 s)
- **ollama:** absent
- **Preinstalled dev tools:** `ruff`, `mypy`, `pytest` in `/root/.local/bin` (but repo install pulls its own pinned versions anyway)
- **Preinstalled apt packages:** 687
- **`python3 -m venv .venv && pip install -e '.[dev,serve]'`:** ✅ clean (~90 s)
- **`pytest tests/`:** ✅ 2230 passed, 9 skipped, 22 xfailed in 192 s. One live-LLM test file needs skipping (`test_autocode_discrimination::TestLiveLLMDiscrimination` — requires a real API key, same as CI)
- **`ruff check .`:** ✅ clean on whole repo
- **`npm ci && npm run build`:** ✅ builds in 563 ms (same `INEFFECTIVE_DYNAMIC_IMPORT` warnings as local — pre-existing)
- **Network egress:** `api.anthropic.com` reachable, 126 ms RTT. Git push/pull work via local proxy

## Use-case boundary

| Workflow | Cloud? | Reason |
|---|---|---|
| Run tests on a branch | ✅ | Verified — 2230 tests, 3 min |
| Frontend refactors / Vite build | ✅ | Verified — node 22, build in <1 s |
| Ruff / mypy sweeps | ✅ | Verified — `ruff check .` clean |
| Code review / exploration | ✅ | Read-only, no deps |
| Document and design work | ✅ | Works fine, used extensively on iPad trip |
| Prompt iteration on synthetic fixtures | ✅ | `api.anthropic.com` reachable; commit a small fixture to the branch first |
| CLI feature development (new commands, stages, render tweaks) | ✅ | Full pipeline code runs; use a tiny committed fixture instead of `trial-runs/` |
| Transcribing a short sample | ✅ (slow) | `faster-whisper` CPU only — fine for a 1-minute test clip, painful for a 90-min interview |
| `bristlenose run` on *real* interviews | ❌ | Participant recordings must not be copied onto an ephemeral VM we do not control — a governance obligation, not a local-first promise. Use a synthetic fixture if you need to exercise the pipeline |
| Browser QA of `bristlenose serve` | ⚠️ unknown | Port-forwarding from Claude Cloud VM to iPad browser not confirmed. `preview_*` in-assistant tools are banned (CLAUDE.md). Worth testing once |
| `/deploy-website` | ❌ | Needs user's SSH agent |
| Snap/Homebrew/Copr release | ❌ | Needs signing keys and tags on user's machine; the Copr additionally needs an API token there, which expires every 180 days |
| Desktop SwiftUI work | ❌ | macOS-only (Xcode) |

### Notes on "what I wish I'd known on the iPad trip"

Document-only work on Cloud is excellent. But **anything that doesn't touch private interview data or macOS-only tooling is also viable** — pipeline refactors, new-stage development, LLM prompt iteration against synthetic fixtures, render-path changes, CSS/theme work, CLI UX changes, mypy/ruff sweeps, writing tests. The only real friction is the ~90 s `pip install` at the start of each session and the need to commit any test fixtures you want to use (since `trial-runs/` is gitignored).

## Revisit trigger

- Anthropic announces changes to Cloud VM image (base release, preinstalled tooling)
- Bristlenose adds a dep that fails on Ubuntu LTS (e.g. a newer Python/Node requirement)
- User hits a "works locally, broken on Cloud" surprise worth capturing
