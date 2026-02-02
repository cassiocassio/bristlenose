# Design: `bristlenose doctor` and Snap packaging

Status: Part 1 (doctor) implemented in v0.6.0. Part 2 (snap) implemented in v0.6.0. (Feb 2026)

---

## Part 1: `bristlenose doctor` — dependency health and guided recovery

### Motivation

Bristlenose has a complex runtime dependency surface: FFmpeg (external binary),
faster-whisper + ctranslate2 (native ML libraries), Whisper model files
(~1.5 GB downloaded at first use), API keys (user-configured), optional PII
redaction (spaCy + language model), and optional Apple Silicon GPU acceleration
(MLX). Users arrive via snap, Homebrew, or pip — each leaves different gaps.

The #1 UX failure mode is: user installs bristlenose, runs it on their interview
recordings, and hits a wall partway through a long pipeline. Transcription took
30 minutes, then the API key is missing. They leave and use Otter or Dovetail.

The fix: **never let them waste time.** Check everything upfront, before any
slow work begins. Guide them to fix what's missing with clear, terse
instructions tailored to their install method.

### Design principles

1. **Pre-flight catches everything catchable before pipeline work starts.** If
   FFmpeg is missing, the user finds out in <2 seconds, not after attempting to
   process 10 video files.

2. **First run triggers auto-doctor.** Most users won't run `doctor` unprompted.
   On first-ever invocation of any pipeline command, doctor runs automatically.
   If it finds blocking issues, the pipeline doesn't start.

3. **Subsequent runs show only the specific failure, not the full doctor
   output.** Terse: one problem, one fix, escape hatches. Suggest
   `bristlenose doctor` at the bottom for full diagnostics.

4. **Never give false reassurance.** If the pipeline fails 30 minutes in, the
   user is gone. The pre-flight exists so this doesn't happen. For the rare
   cases that can't be pre-flighted (network drops mid-run, model corruption
   discovered during loading), the error message focuses on the fix, not on
   comforting the user.

5. **Respect the user's intelligence.** Show the fix command, not a paragraph
   explaining what went wrong. Linux users want to know *how* to fix it, not
   have it done for them.

6. **Colour is restrained.** Uses Rich. `ok` = dim green. `!!` = bold yellow
   (not red — yellow means "action needed", red means "something broke right
   now"). `--` = dim grey (informational/not applicable). No emoji. No boxes.
   Feels like `git status`, not a dashboard.

### The seven checks

Each check returns one of three states: **ok**, **warn** (works but suboptimal),
**fail** (will block the pipeline).

| # | Check | What it tests |
|---|---|---|
| 1 | FFmpeg | `shutil.which("ffmpeg")` — is it in PATH? |
| 2 | Transcription backend | `import faster_whisper` succeeds, ctranslate2 version |
| 3 | Whisper model | Is the configured model already cached? (uses `huggingface_hub.scan_cache_dir()` or `WhisperModel(..., local_files_only=True)`) |
| 4 | API key | Is an API key configured for the selected LLM provider? Also validates the key with a cheap API call (e.g. Anthropic's count_tokens or model list endpoint) to catch expired/revoked keys |
| 5 | Network | Quick HTTPS HEAD to the API endpoint (api.anthropic.com or api.openai.com) |
| 6 | PII redaction | presidio importable + spaCy model installed. Only checked when `--redact-pii` is active |
| 7 | Disk space | `shutil.disk_usage()` — enough room for model download + working files |

### Command-to-check matrix

Not every command checks everything. Pre-flight is tailored to the command:

```
Check             run   run --skip-tx   transcribe-only   analyze   render
-------------------------------------------------------------------------
FFmpeg             *                          *
faster-whisper     *                          *
Whisper model      *                          *
API key            *         *                               *
Network (API)      *         *                               *
spaCy model       (1)       (1)
Disk space         *         *                *              *
-------------------------------------------------------------------------

(1) only if --redact-pii
render: no pre-flight at all — it reads JSON, writes HTML, needs nothing external
```

### Pre-flightable vs not

| Check | Pre-flightable? | How |
|---|---|---|
| FFmpeg installed | Yes | `shutil.which("ffmpeg")` |
| faster-whisper importable | Yes | try/except import |
| ctranslate2 loads | Yes | try/except import, version check |
| API key present | Yes | `settings.anthropic_api_key != ""` |
| API key valid | Yes | Cheap API call (~0.1s, catches expired/revoked keys) |
| Whisper model cached | Yes | `huggingface_hub.scan_cache_dir()` or `local_files_only=True` |
| Network reachable | Yes | Quick HTTPS HEAD |
| spaCy model installed | Yes (if --redact-pii) | `spacy.load("en_core_web_sm")` |
| Disk space | Yes | `shutil.disk_usage()` |
| Model download mid-stream | No | Can only discover during download |
| API rate limits mid-run | No | Transient |
| Transient network drops | No | Transient |

### First-run detection

Sentinel file: `~/.config/bristlenose/.doctor-ran` (or `$SNAP_USER_COMMON/.doctor-ran` in a snap).

Contents: single line with the bristlenose version, e.g. `0.6.0`.

Logic:
- If sentinel missing or version doesn't match `bristlenose.__version__` → auto-doctor triggers on next `run`/`transcribe-only`/`analyze`
- If auto-doctor passes (no `fail` results) → sentinel written, won't auto-run again until version changes
- If auto-doctor finds `fail` results → sentinel NOT written, pipeline doesn't start, auto-doctor triggers again next time
- `bristlenose doctor` (explicit) always runs regardless of sentinel
- `render` never triggers auto-doctor (it doesn't need external deps)

### Architecture

```
bristlenose/doctor.py           # Check logic (pure, no UI)
  CheckResult(status, label, detail, fix_key)
  check_ffmpeg() -> CheckResult
  check_backend() -> CheckResult
  check_whisper_model(settings) -> CheckResult
  check_api_key(settings) -> CheckResult
  check_network(settings) -> CheckResult
  check_pii(settings) -> CheckResult
  check_disk_space(settings) -> CheckResult
  run_all(settings) -> list[CheckResult]
  run_preflight(settings, command, flags) -> list[CheckResult]

bristlenose/doctor_fixes.py     # Fix instructions per install method
  detect_install_method() -> "snap" | "brew" | "pip" | "unknown"
  get_fix(fix_key, install_method) -> str

bristlenose/cli.py              # Wiring
  doctor command (explicit)
  _maybe_auto_doctor() called before run/transcribe-only/analyze
  _run_preflight() called on every pipeline command
```

`detect_install_method()`:
- `$SNAP` env var set → `"snap"`
- Python executable under `/opt/homebrew/` or `/usr/local/Cellar/` → `"brew"`
- Otherwise → `"pip"`

### Sample dialogs

#### First run, no API key (most common first-run scenario)

```
$ bristlenose run ./interviews/ -o ./output/

First run — checking your setup.

  FFmpeg          ok
  Transcription   ok   faster-whisper 1.2.1
  Whisper model   --   large-v3-turbo not cached (will download ~1.5 GB on first run)
  API key         !!   No Anthropic API key
  Network         ok

bristlenose needs an API key to analyse transcripts.
Get one from console.anthropic.com, then:

  export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...

Or add it to a .env file in your project directory.

To use OpenAI instead:  bristlenose run ./interviews/ --llm openai
To only transcribe:     bristlenose transcribe-only ./interviews/
```

#### First run, everything OK

```
$ bristlenose run ./interviews/ -o ./output/

First run — checking your setup.

  FFmpeg          ok
  Transcription   ok
  Whisper model   --   large-v3-turbo will download (~1.5 GB) on first run
  API key         ok   Anthropic (sk-ant-...xyz)
  Network         ok

All clear.

Downloading Whisper model large-v3-turbo...
████████████████████████████████████ 1.5 GB   2m 13s

Processing 3 recordings...
```

#### Subsequent run, API key gone (pre-flight, terse)

```
$ bristlenose run ./interviews/ -o ./output/

No API key configured.

  export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...
  Or add to .env file in your project directory.

To only transcribe (no API key needed):
  bristlenose transcribe-only ./interviews/
```

#### Subsequent run, API key invalid

```
$ bristlenose run ./interviews/ -o ./output/

API key rejected (401 Unauthorized).

Your Anthropic key starting with sk-ant-...89f was not accepted.
Check it at console.anthropic.com/settings/keys.
```

#### FFmpeg missing (pip install on Linux)

```
$ bristlenose run ./interviews/ -o ./output/

FFmpeg not found.

bristlenose needs FFmpeg to extract audio from video files.

  Ubuntu/Debian:  sudo apt install ffmpeg
  Fedora:         sudo dnf install ffmpeg
  Arch:           sudo pacman -S ffmpeg
  macOS:          brew install ffmpeg
```

#### FFmpeg missing (snap — should not happen)

```
$ bristlenose run ./interviews/ -o ./output/

FFmpeg not found — this is a bug in the snap package.
  sudo snap refresh bristlenose
If it persists: github.com/cassiocassio/bristlenose/issues
```

#### faster-whisper won't load (ctranslate2 issue)

```
$ bristlenose run ./interviews/ -o ./output/

Transcription backend failed to load.

  Error: libctranslate2.so: cannot enable executable stack

  pip install --upgrade ctranslate2 faster-whisper

If that doesn't help: github.com/cassiocassio/bristlenose/issues
```

#### Network unreachable

```
$ bristlenose run ./interviews/ -o ./output/

Can't reach api.anthropic.com.

Check your internet connection. If you're behind a proxy:
  export HTTPS_PROXY=http://proxy:port
```

#### PII redaction needs spaCy model (pip/brew)

```
$ bristlenose run ./interviews/ -o ./output/ --redact-pii

PII redaction needs a spaCy language model.

  python3 -m spacy download en_core_web_sm

Then re-run. Or drop --redact-pii if you don't need it.
```

For Brew installs specifically:
```
  $(brew --prefix bristlenose)/libexec/bin/python -m spacy download en_core_web_sm
```

#### PII redaction issue in snap (should not happen — model bundled)

```
$ bristlenose run ./interviews/ -o ./output/ --redact-pii

spaCy model not found — this is a bug in the snap package.
  sudo snap refresh bristlenose
If it persists: github.com/cassiocassio/bristlenose/issues
```

#### Insufficient disk space

```
$ bristlenose run ./interviews/ -o ./output/

Low disk space (800 MB free).

bristlenose needs approximately 2 GB for the Whisper model download
and working files. Free up space or use a smaller model:

  bristlenose run ./interviews/ -w tiny      (75 MB model)
  bristlenose run ./interviews/ -w small     (500 MB model)
```

#### Model download fails mid-stream (can't be pre-flighted)

```
Downloading Whisper model large-v3-turbo...
████████████░░░░░░░░░░░░░░░░░░░░░░░ 412 MB

Download failed: connection reset.

Try again — the download resumes from where it stopped.
Or use a smaller model: bristlenose run ./interviews/ -w small
```

#### CUDA detected but not working (warn, not fail)

```
$ bristlenose doctor

  Transcription   warn  faster-whisper 1.2.1 (NVIDIA GPU detected
                        but CUDA runtime not available — using CPU)

NVIDIA GPU found (RTX 4090) but CUDA libraries aren't accessible.
Transcription will work on CPU but will be slower.

To enable GPU acceleration:
  1. Install CUDA 12.x: nvidia.com/cuda-downloads
  2. Set: export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

#### Apple Silicon without MLX (warn, not fail — Brew/pip only)

```
$ bristlenose doctor

  Transcription   warn  faster-whisper 1.2.1 (Apple Silicon, CPU mode)

Apple Silicon detected but MLX not installed. Transcription will
use CPU (works fine, GPU is faster).

  $(brew --prefix bristlenose)/libexec/bin/pip install 'bristlenose[apple]'
```

#### Explicit `bristlenose doctor` — all OK

```
$ bristlenose doctor

bristlenose 0.6.0

  FFmpeg          ok   6.1.1 (/usr/bin/ffmpeg)
  Transcription   ok   faster-whisper 1.2.1, ctranslate2 4.6.3 (CPU)
  Whisper model   ok   large-v3-turbo cached (1.5 GB)
  API key         ok   Anthropic (sk-ant-...xyz)
  Network         ok   api.anthropic.com reachable (210ms)
  PII redaction   ok   presidio 2.2.360, spaCy en_core_web_sm 3.8.0
  Disk space      ok   42 GB free

All clear.
```

#### Explicit `bristlenose doctor` — mixed results

```
$ bristlenose doctor

bristlenose 0.6.0

  FFmpeg          ok   6.1.1 (/snap/bristlenose/current/usr/bin/ffmpeg)
  Transcription   ok   faster-whisper 1.2.1, ctranslate2 4.6.3 (CPU)
  Whisper model   --   large-v3-turbo not cached (~1.5 GB download)
  API key         !!   No API key configured
  Network         ok   api.anthropic.com reachable (85ms)
  PII redaction   ok   presidio 2.2.360, spaCy en_core_web_sm 3.8.0
  Disk space      ok   18 GB free

1 issue:

  API key: Get one from console.anthropic.com, then:
    export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...

1 note:

  Whisper model: Will download automatically on first run (~1.5 GB).
  Pre-download it now with:
    bristlenose transcribe-only --prefetch-model
```

### Install-method-specific fix table

Most fix messages are install-method-agnostic (API key, network, disk, model
cache). Only these differ:

| fix_key | snap | brew | pip (Linux) | pip (macOS) |
|---|---|---|---|---|
| ffmpeg_missing | "Bug in snap, file issue" | `brew install ffmpeg` | `sudo apt install ffmpeg` (+ Fedora/Arch variants) | `brew install ffmpeg` |
| spacy_model_missing | "Bug in snap, file issue" | `$(brew --prefix bristlenose)/libexec/bin/python -m spacy download en_core_web_sm` | `python3 -m spacy download en_core_web_sm` | `python3 -m spacy download en_core_web_sm` |
| mlx_not_installed | N/A (Linux snap) | `$(brew --prefix bristlenose)/libexec/bin/pip install 'bristlenose[apple]'` | N/A (Linux pip) | `pip install 'bristlenose[apple]'` |
| backend_import_fail | "File issue" | `pip install --upgrade ctranslate2 faster-whisper` | same | same |

### Brew formula improvements

The Homebrew formula should be updated to:

1. Add `post_install` to download the spaCy model into the venv:
   ```ruby
   def post_install
     system libexec/"bin/python", "-m", "spacy", "download", "en_core_web_sm"
   end
   ```

2. Improve caveats:
   ```ruby
   def caveats
     <<~EOS
       API key required for analysis (not needed for transcribe-only):
         export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...

       First run downloads a speech recognition model (~1.5 GB).

       Apple Silicon GPU acceleration (optional):
         #{libexec}/bin/pip install 'bristlenose[apple]'
     EOS
   end
   ```

### Future: `--prefetch-model` flag

A flag on `transcribe-only` (or a standalone command) that downloads the Whisper
model and exits. Useful for:
- Users on slow connections who want to download overnight
- CI/automated setups
- Making `bristlenose doctor` show `ok` for the model check

---

## Part 2: Snap packaging (implemented)

### Research summary

Extensive research was done on snap confinement, build strategies, testing on
macOS, dependency sizes, and channel management. Key sources:

- Snapcraft Python plugin: https://snapcraft.io/docs/python-plugin
- Classic confinement process: https://snapcraft.io/docs/reviewing-classic-confinement-snaps
- CTranslate2 execstack fix: https://github.com/OpenNMT/CTranslate2/issues/1698
- CTranslate2 glibc 2.41 issue: https://github.com/OpenNMT/CTranslate2/issues/1849
- Ruff classic request (Jan 2026): https://forum.snapcraft.io/t/classic-confinement-request-ruff/50175
- Argos Translate (ML snap with ctranslate2): https://github.com/argosopentech/argos-translate
- Snap size discussion: https://forum.snapcraft.io/t/snap-package-file-size-limit-on-the-store/37450

### Decision: classic confinement

Strict confinement is not viable for bristlenose because:

1. The `home` interface excludes dotfiles — `.env` files (the primary config
   discovery mechanism) are invisible in strict mode
2. Paths outside `$HOME` (USB drives, `/tmp`, NAS mounts) require
   `removable-media` (manual `snap connect`) or `system-files` (hard to get
   approved)
3. CUDA/GPU support has no first-class snap interface
4. In strict mode, `$HOME` is remapped to `~/snap/bristlenose/current/`, breaking
   huggingface_hub model caching expectations

Classic confinement is standard for CLI tools that operate on user-specified
filesystem paths. Precedent: aws-cli, google-cloud-cli, heroku, node, go, code
(VS Code). Approval takes 3-5 business days.

### Decision: full-featured snap (not lean/split)

The 99% use case is users bringing video files. Shipping without transcription
would be like shipping PowerPoint without slides. The snap must include
faster-whisper, ctranslate2, presidio, spaCy, and the spaCy language model.

### Estimated snap size: ~130-160 MB (acceptable)

Earlier estimates of 700 MB-1.3 GB were wrong because they included macOS-only
dependencies. The actual Linux dependency footprint:

**On Linux, no torch needed.** faster-whisper uses ctranslate2 (39 MB wheel),
not PyTorch. Torch is only pulled in by mlx-whisper (Apple Silicon only).

**No mlx/mlx-metal.** Apple Silicon only.

**Smaller spaCy model.** `en_core_web_sm` (15 MB) instead of `en_core_web_lg`
(425 MB) — Presidio works with either. PII is opt-in anyway.

Breakdown:

| Category | Estimated size (uncompressed) |
|---|---|
| Core (pydantic, typer, rich, anthropic, openai, etc.) | ~88 MB |
| Transcription (faster-whisper, ctranslate2, onnxruntime, numpy, huggingface-hub) | ~124 MB |
| PII (presidio, spaCy, en_core_web_sm, thinc) | ~53 MB |
| FFmpeg (stage-package) | ~50 MB |
| **Total uncompressed** | **~315 MB** |
| **Squashfs compressed (40-50%)** | **~130-160 MB** |

Comparable to VS Code's snap (~150 MB). Normal for the Store.

Note: Whisper model files (1-3 GB depending on model size) are NOT bundled.
They download at first use to `~/.cache/huggingface/`. This is the same
behaviour as pip/brew installs.

### Known risk: ctranslate2 and glibc

The ctranslate2 executable stack flag issue was fixed in PR #1852 (Feb 2025).
CTranslate2 4.6.3 (Jan 2026) has the fix. However, there are lingering glibc
2.41 compatibility issues on some distros (Arch-based mainly). The snap builds
against a specific Ubuntu base (core24 = Ubuntu 24.04) which has glibc 2.39, so
this should not be an issue inside the snap. Monitor upstream:
https://github.com/OpenNMT/CTranslate2/issues/1849

### Known risk: Presidio and spaCy model in a classic snap

In a classic snap, `en_core_web_sm` should be bundled at build time. The
snapcraft.yaml should include a build step that downloads it into the snap's
Python site-packages. This way `--redact-pii` works without the user installing
anything extra. If the model is somehow missing at runtime, doctor reports it as
a snap bug (not a user action item).

### Build strategy

**Primary: GitHub Actions** with `snapcore/action-build` + `snapcore/action-publish`.

- Builds amd64 snaps on ubuntu-latest runners
- Auto-publishes to `edge` channel from main branch
- Publishes to `stable` on tagged releases
- Private (unlike `snapcraft remote-build` which uploads source to Launchpad publicly)

**Secondary: `snapcraft remote-build`** for quick local iteration on
snapcraft.yaml changes. Acceptable since bristlenose is open source (the
public upload is fine).

**Avoid: Multipass local builds on macOS** — fragile, and on Apple Silicon can
only build arm64 snaps (most Linux users are amd64).

### Testing from macOS

**Use Multipass** (not MicroK8s — it's for Kubernetes, not snap testing):

```bash
multipass launch --name snap-test --cpus 2 --memory 4G --disk 20G
multipass transfer bristlenose_*.snap snap-test:
multipass shell snap-test
sudo snap install --dangerous --classic ./bristlenose_*.snap
bristlenose --version
bristlenose doctor
```

**Architecture caveat on Apple Silicon:** Multipass creates arm64 VMs. Can test
arm64 builds locally. For amd64 testing, use a cloud VM or rely on CI.

### Channel strategy

```
edge      <- every push to main (CI auto-publishes)
beta      <- manual promotion when feature-complete
candidate <- release candidates
stable    <- tagged releases (what `snap install bristlenose --classic` gets)
```

Testers install from edge:
```bash
sudo snap install bristlenose --edge --classic
```

Channels are public — anyone can install from any channel. For private testing,
distribute the .snap file directly:
```bash
sudo snap install --dangerous --classic ./bristlenose_0.6.0_amd64.snap
```

### Snapcraft.yaml sketch

```yaml
name: bristlenose
version: '0.6.0'  # updated by CI from bristlenose/__init__.py
base: core24
confinement: classic
grade: stable
license: AGPL-3.0-only

summary: User-research transcription and quote extraction engine
description: |
  Bristlenose takes a folder of interview recordings and produces a
  browsable HTML report with extracted quotes, themes, and user journeys.
  Everything runs locally. LLM calls go to Anthropic or OpenAI APIs.

apps:
  bristlenose:
    command: bin/bristlenose
    environment:
      LANG: C.UTF-8
      LC_ALL: C.UTF-8

parts:
  bristlenose:
    plugin: python
    source: .
    python-packages:
      - .
    stage-packages:
      - ffmpeg
      - libsndfile1
    build-packages:
      - python3-dev
      - build-essential
    override-build: |
      craftctl default
      # Download spaCy model into the snap's Python environment
      $CRAFT_PART_INSTALL/bin/python3 -m spacy download en_core_web_sm

platforms:
  amd64:
    build-on: [amd64]
  arm64:
    build-on: [arm64]
```

Note: this was a sketch. See `snap/snapcraft.yaml` for the final version. Key
differences from the sketch and lessons learned during implementation below.

### Implementation notes and gotchas

**Python path wiring (critical).** The snapcraft Python plugin generates a
`bin/bristlenose` shim with `#!/usr/bin/env python3`. In a classic snap this
finds the **system** Python, not the snap's bundled Python. The snap's packages
are in `$SNAP/lib/python3.12/site-packages` but the system Python doesn't know
about them → `ModuleNotFoundError: No module named 'bristlenose'`. Fix: three
environment variables in the `apps.bristlenose.environment` block:

```yaml
environment:
  PATH: $SNAP/usr/bin:$SNAP/bin:$PATH          # snap's Python found first
  PYTHONPATH: $SNAP/lib/python3.12/site-packages  # packages visible
  PYTHONHOME: $SNAP/usr                         # stdlib rooted correctly
```

Without all three, the snap installs fine but crashes on launch. This is the
single most important gotcha in the entire snap build.

**Version via adopt-info.** The sketch hardcoded `version: '0.6.0'`. The final
version uses `adopt-info: bristlenose` + `craftctl set version=...` in
`override-build` to read the version from `bristlenose/__init__.py` at build
time. This keeps the single-source-of-version convention intact.

**Stage-packages for Python stdlib.** The sketch only had `ffmpeg` and
`libsndfile1` as stage-packages. The build also needs `python3-minimal`,
`python3.12-minimal`, `libpython3.12-stdlib`, `libpython3.12-minimal`, and
`python3-venv` to provide a working Python runtime inside the snap.

**Actual snap size: ~307 MB.** Larger than the estimated 130-160 MB. The
estimate was based on squashfs compression of the Python packages alone. The
full FFmpeg dependency tree (libavcodec, libavformat, x264, x265, libvpx,
opus, and ~100 transitive libs) accounts for the difference. Still within
normal range for the Store (VS Code snap is ~150 MB but has no ML deps).

**Linter warnings (all cosmetic, non-blocking):**
- `classic: ELF rpath should be set to...` — hundreds of these for every shared
  library. Standard for classic confinement snaps that bundle system libraries.
  The snap works correctly despite these warnings.
- `library: unused library...` — FFmpeg bundles more codecs than bristlenose
  uses directly. Harmless.
- `library: missing dependency 'libGLU.so.1'` — only for `caca/libgl_plugin.so`
  (a libcaca OpenGL plugin). Never loaded at runtime.

**Building locally on macOS (Multipass):**
- Multipass 1.13.0 on Apple Silicon was broken (VMs created but never booted,
  stuck in "Unknown" state forever). **Requires Multipass 1.16.1+.**
- `multipass launch noble` may not work — use `multipass launch lts` instead
  (the alias is more reliable across Multipass versions).
- `--destructive-mode` needs `sudo` because it runs `apt install` for
  build-packages.
- Apple Silicon Multipass creates arm64 VMs only. For amd64, rely on CI.

**Local build and test workflow (macOS with Multipass):**

```bash
# Launch VM (4 CPU, 4 GB RAM, 20 GB disk)
multipass launch lts --name snap-test --cpus 4 --memory 4G --disk 20G

# Mount source and copy (mount alone won't work — snapcraft needs local files)
multipass mount /path/to/bristlenose snap-test:/home/ubuntu/bristlenose
multipass exec snap-test -- bash -c \
  "rsync -a --exclude='.venv' --exclude='.git' --exclude='__pycache__' \
   /home/ubuntu/bristlenose/ /home/ubuntu/build/"

# Install snapcraft and build
multipass exec snap-test -- sudo snap install snapcraft --classic
multipass exec snap-test -- bash -c \
  "cd /home/ubuntu/build && sudo snapcraft --destructive-mode"

# Install and test
multipass exec snap-test -- sudo snap install --dangerous --classic \
  /home/ubuntu/build/bristlenose_*.snap
multipass exec snap-test -- bristlenose --version
multipass exec snap-test -- bristlenose doctor

# Clean up when done
multipass delete snap-test --purge
```

**`$SNAP` env var for install method detection.** Inside the snap runtime,
`$SNAP` is set to `/snap/bristlenose/x<revision>`. This is how
`detect_install_method()` in `doctor_fixes.py` identifies a snap install and
shows snap-specific fix messages (e.g. "Bug in snap, file issue" for missing
FFmpeg, which should never happen).

**Verified checks from snap:**
- `bristlenose --version` → `bristlenose 0.6.0` ✓
- `bristlenose doctor` → FFmpeg found at `/snap/bristlenose/current/usr/bin/ffmpeg` ✓
- faster-whisper 1.2.1 + ctranslate2 4.6.3 (CPU) ✓
- `$SNAP` detected → install method = snap ✓
- `bristlenose --help` → all commands visible ✓

### GitHub Actions workflow sketch

```yaml
name: Snap Build & Publish

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: snapcore/action-build@v1
        id: snapcraft
      - uses: actions/upload-artifact@v4
        with:
          name: snap-amd64
          path: ${{ steps.snapcraft.outputs.snap }}

  publish-edge:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: snap-amd64
      - uses: snapcore/action-publish@v1
        env:
          SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
        with:
          snap: "*.snap"
          release: edge

  publish-stable:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: snap-amd64
      - uses: snapcore/action-publish@v1
        env:
          SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
        with:
          snap: "*.snap"
          release: stable
```

### Pre-launch checklist

1. Register snap name: `snapcraft register bristlenose`
2. Request classic confinement approval on forum.snapcraft.io (3-5 days)
3. Export store credentials: `snapcraft export-login --snaps=bristlenose --channels=edge,beta,candidate,stable credentials.txt`
4. Add `SNAPCRAFT_STORE_CREDENTIALS` to GitHub repo secrets
5. Build and test locally with Multipass
6. Push to main, verify edge channel build
7. Have Linux testers install from edge: `sudo snap install bristlenose --edge --classic`
8. When validated, promote to stable: `snapcraft release bristlenose <revision> stable`

---

## Implementation order

These two workstreams are mostly independent but doctor landed first:

### Phase 1: `bristlenose doctor` ✅ (v0.6.0)

1. ✅ Create `bristlenose/doctor.py` — seven check functions, `run_all()`,
   `run_preflight()`
2. ✅ Create `bristlenose/doctor_fixes.py` — `detect_install_method()`, fix text
   lookup table
3. ✅ Add `doctor` command to `bristlenose/cli.py`
4. ✅ Wire first-run auto-doctor into `run`, `transcribe-only`, `analyze` commands
5. ✅ Wire pre-flight into the same commands (runs on every invocation, not just
   first run)
6. Update Homebrew formula: add `post_install` for spaCy model, improve caveats
7. ✅ Tests for doctor checks (mock imports, mock shutil.which, etc.)

### Phase 2: Snap packaging ✅ (v0.6.0)

1. ✅ Write `snap/snapcraft.yaml`
2. ✅ Test locally with Multipass (arm64 on Apple Silicon)
3. Register snap name and request classic confinement (pre-launch, manual)
4. ✅ Write `.github/workflows/snap.yml` CI workflow
5. Add `SNAPCRAFT_STORE_CREDENTIALS` secret (pre-launch, manual)
6. Build, test from edge channel (pending store registration)
7. Promote to stable (pending classic confinement approval)
8. ✅ Update README.md and TODO.md

### Phase 3: Polish

1. `--prefetch-model` flag for pre-downloading Whisper models
2. Improve mid-pipeline error messages for non-pre-flightable failures
   (download interruptions, transient API errors)
3. Consider progress bar improvements for model downloads (currently delegated
   to huggingface_hub's default progress)
