# Windows port

## Status — 5 Oct 2026: the CLI installs and runs; not a channel

**What holds, and how we know.** The command-line tool installs through pipx or uv
on **x64 Python** and runs on Windows. Proved three ways on 5 Oct 2026:

- **CI**: `test (3.12, windows-latest)` in `ci.yml` runs the full suite (6080 passed,
  0 failed on `0061f566`) and **blocks** since `87c09842`. Its hard step also runs a
  real `bristlenose transcribe` into a cp1252 pipe, deliberately without
  `PYTHONIOENCODING`.
- **A Windows 11 VM** (UTM, Arm64 hardware, x64 Python 3.14.8): install, doctor,
  `transcribe` of audio and of a kanji filename, redirected output, a keyed `run` on a
  folder with a space in its name, the report in Edge (stars and renames persist,
  audio plays at a timecode), and Export Report opening offline from `file://`.
- **A fresh Windows Server 2025 x64 box** (`aella up --windows`): the same install
  path, the redirect cases, and `configure` against a fresh root store.

**What it is not.** Not a release channel: there is no Windows artifact, no release
step and no verify row. Windows users get the same `pipx`/`uv` install as any Python
user. The 0.33.1 changelog says exactly that.

**Never exercised on Windows:** `run --clean` twice on a real project; `serve` alone
then Ctrl-C; OneDrive or network-share project folders; long paths; the voice-model
download; Windows 11 on x64 hardware; the GUI clicks of python.org's install manager.

### What was broken, and is fixed

Every item has a test that fails on any OS by recreating the Windows condition
(most in `tests/test_windows_portability.py`). PyPI **0.33.0 is unusable on Windows**:
item 1 crashes every `transcribe`. 0.33.1 is the first release that works there.

1. **The first event write of every run** named `os.O_NOFOLLOW`, which Windows lacks
   (`b6553a8f`: `utils.fs.open_private`).
2. **A run died at its second stage**: the manifest `rename` refused an existing
   target (`7ad88c78`: `replace`).
3. **A live run read as dead**, so a second run on the same folder was not refused
   (`b6553a8f`: `GetProcessTimes`).
4. **A recording named in kanji crashed ingest**: text-mode subprocess output was
   decoded as cp1252, while ffprobe writes UTF-8 (`7c3a2b74`).
5. **`run --clean` always wrote over the old report, and a failed run could not
   restore it**: Windows will not rename a folder holding an open file, and our log
   was open inside the output folder (`10c39eb3`: `release_log_file`).
6. **Every run crashed at its end** once a project's LLM log passed 1,000 calls: the
   trim called `os.fchmod` (`b38b8fdc`).
7. **Burned-in subtitles never ran**: a `C:\` temp path was refused as filter-unsafe
   (`5e694a4c`: ffmpeg runs inside the temp folder).
8. **Any redirected or piped output** (`> out.txt`, `| Out-Host`) crashed on ✓
   before printing anything (`afa99a8a`).
9. **On a fresh machine the Claude and ChatGPT APIs were unreachable from urllib**:
   both chain to Google Trust Services, which Windows fetches only for CryptoAPI
   clients (curl, Edge), and Python never asks. Doctor said the network was down and
   `configure` could not validate a key (`0061f566`: `utils.tls.https_context`, which
   adds certifi's roots to the system store).
10. **Doctor and setup copy**: Unix-shaped fix text (`b6553a8f`); `[voice]` eaten as
    Rich markup; single-quoted install specs that cmd.exe passes literally; a
    Homebrew row; "stores it securely" for a plain `.env`; `~/` glued to backslashes;
    the exact winget id for FFmpeg; a voice hint that cannot work on Windows +
    Python 3.14 (`afa99a8a`, `2bc5e23e`, `ad6936bf`, `a2f8d774`, `fb360f4a`).

**Gates that keep these closed** (all run on every OS): every text-mode subprocess
call names an encoding; every text file read/write names one; every `https` `urlopen`
passes `context=https_context()`; no module names `os.O_NOFOLLOW`; install specs are
double-quoted. Thirteen tests skip on Windows where it has no equivalent (POSIX mode
bits, signals by `os.kill`, `O_NOFOLLOW`, the exec bit, replacing a file serve holds
open); `docs/testing/ratchet.json` names each.

### Learnings

- **The real bugs were few and each blocked a common step.** 489 first-run failures
  were mostly the tests; about ten were product defects, listed above.
- **They come in families**: encodings (cp1252 for pipes and files), file locking
  (no rename or delete of an open file), signals, drive letters (`relpath` across
  C: and D:), and process launch (`CreateProcess` tries System32 first, so a bare
  `bash` is WSL's). A source gate per family beats a fix per site.
- **CI's environment hid the two worst.** `PYTHONIOENCODING=utf-8` masked the redirect
  crash; the runner image already holds every root certificate. Both only showed on
  real machines. A Windows-native probe of an API host (curl, Invoke-WebRequest)
  installs the root as a side effect, so test TLS before touching those hosts.
- **Case sensitivity was a non-issue**: path identity uses `os.path.samefile`.
- **Windows on Arm runs x64 Python only.** python.org's install manager installs x64
  by default; native arm64 Python cannot resolve, because `ctranslate2` publishes no
  win_arm64 wheel (pipx misreports it as "failed to build av"). Transcription under
  emulation is slow: about 2 min for 11 s of audio.
- **The voice extra cannot install on Windows + Python 3.14**: kaldi-native-fbank has
  no cp314 Windows wheel. The dev extra fails there for the same reason.
- **The install path has drifted from older guides**: python.org's button is now the
  install manager (no PATH checkbox; y/N prompts, defaults vary); on Server 2025,
  winget needs registering and a fresh source, and plain `winget install FFmpeg`
  fails on the msstore source where the exact id works.
- **The test VM is friendlier than a real machine**: UTM's unattended install turns
  UAC off.

### Open, in order

1. **uv is the primary Windows route** (INSTALL.md, published after the 0.33.1 tag; pipx kept as the
   alternative): `winget install` uv and FFmpeg, a new terminal, then
   `uv tool install --python 3.13 bristlenose`. Verified first time on the Arm VM:
   uv fetched its own x64 Python 3.13 without being told (no x64 pin needed), doctor
   was all clear, and the voice extra installed. Still unverified on a never-touched
   machine: whether uv's tool folder is on PATH (the guide says what to do if not),
   and a never-used winget's first-run prompt. Don't publish the guide before
   0.33.1 is on PyPI.
2. **The two unrun checks**: `run --clean` twice, and `serve` then Ctrl-C.
3. **Plain-ASCII symbols when output is not a UTF-8 console.** Redirected logs show
   `?` for ✓ and ✗, so a saved doctor log cannot tell a pass from a fail, and `–`
   becomes `ù` in a PowerShell pipe.
4. **Decisions for the maintainer**: whether `run` with no provider should exit
   non-zero (it exits 0 in a terminal by design); `CONTRIBUTING.md` still calls this
   port "parked"; `configure local` offers no Ollama install on Windows; the website's
   Windows install steps predate all of this.
5. **Every platform, seen first on Windows**: warning log lines interleave with the
   run UI (including a developer note); Hugging Face warnings print twice and the
   1.6 GB Whisper download shows no progress; the player does not seek when an
   already-open window has ended; the MCP hint says `pip` to pipx users; session
   times render UTC as local (H9 in `docs/time-defects.md`); the transcript header
   floors a duration the CLI rounds.
6. **A Windows channel**, only if Windows earns it: a winget package backed by a
   PyInstaller build in a Windows release job (the Copr analogue, vendoring Python),
   code-signed so SmartScreen does not warn. Scoop and an MSI were considered and set
   aside: researchers will not have Scoop, and an installer is further from a
   two-line install.

---

*The sketch below is the June 2026 plan. Where it disagrees with the status above —
Scoop as the channel, "no bundled Python", Arm out of scope — the status wins.*

## Why deferred

Bristlenose's primary distribution is the signed macOS desktop app (via TestFlight, then the Mac App Store). The CLI on PyPI / Homebrew / Snap is a near-free byproduct because macOS-arm64 and Linux-x86_64 share BSD/POSIX userland, the Python ecosystem, and similar packaging conventions. Windows is a different OS family — different process model, no system Python, no cheap codesigning story, different package conventions. None of that is impossible, but it's a separate piece of work with its own audience.

## Audience and scope

This sketch is **CLI only, distributed via Scoop**. A Windows-native GUI app is a year-scale project (no SwiftUI equivalent — would need Tauri / WPF / Electron) and is explicitly out of scope.

The audience for the CLI-on-Scoop path is the unix-diaspora subset of Windows users: developers who already have Scoop installed, or are happy to install it. Comparable status to a Linux user who runs `apt install python3` before `pip install bristlenose`. This is **not** the path for a Windows-native researcher who expects a double-click installer — that audience needs the (out-of-scope) GUI app.

## Decisions locked in

1. **CLI only.** No desktop GUI.
2. **Scoop is the distribution channel.** Sidesteps SmartScreen / UAC by running user-mode from a manifest.
3. **No bundled Python.** Scoop manifest declares a dependency on `python`; user runs `scoop install python` if they don't have it. Same gesture as the Linux path.
4. **No code signing.** Scoop's manifest model doesn't need it. We don't pay for an EV cert.
5. **Universal-binary-style install.** One manifest. GPU detected at install time (NVIDIA → CUDA torch wheel; otherwise CPU). User runs `scoop install bristlenose`, the right thing happens. No `bristlenose-cuda` SKU split — the Mac mental model (one binary, hardware detected at runtime) is the right default; the conventional Scoop pattern of separate SKUs would be a regression.
6. **ffmpeg via Scoop dependency**, not bundled in the wheel. Scoop's main bucket has ffmpeg; the manifest declares it.
7. **spaCy `en_core_web_lg` pulled by post-install hook**, not bundled. ~400 MB download, one-time.

## Components

| Component | Source | Notes |
|---|---|---|
| Python 3.10+ | Scoop dep | `scoop install python` if missing |
| ffmpeg / ffprobe | Scoop dep | from Scoop main bucket |
| `bristlenose` package | PyPI (existing) | already publishes a pure-Python wheel |
| `torch` wheel (CPU or cu121) | Install-time probe | `nvidia-smi` decides |
| `faster-whisper` | PyPI, via bristlenose deps | runtime-detects torch flavour |
| spaCy `en_core_web_lg` | Post-install download | `python -m spacy download` |
| Scoop manifest | New, ~50 lines JSON | hosted in our own bucket initially |

## Step-by-step

### Phase 1 — make the CLI actually run on Windows (~1 week)

1. Add `windows-latest` cell to `.github/workflows/ci.yml` test matrix. Expect 10–30 failures on first run.
2. Triage failures. Most likely categories:
   - Path-separator assumptions in tests and string-built paths
   - `subprocess` calls relying on POSIX shell quoting
   - File-locking and atomic-rename semantics in `manifest.py` and `events.jsonl` writers
   - Encoding — set `PYTHONUTF8=1` or pass `encoding="utf-8"` explicitly at every text-mode open
   - Signal handling — `SIGTERM` doesn't exist; serve-mode shutdown needs `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT`
3. Extend `is_os_metadata()` in `bristlenose/utils/fs.py` to filter `Thumbs.db` and `desktop.ini` (Windows analogues to `.DS_Store` / `._foo`).
4. Fix `bundled_binary.py` — `prepend_bundled_to_path()` needs the Windows path-separator branch (`;` instead of `:`). Probably unused on Windows if ffmpeg comes from Scoop, but keep correct.
5. Audit slug / safe-filename helpers for Windows reserved names: `CON`, `PRN`, `AUX`, `NUL`, `COM1–9`, `LPT1–9`. An interview file called `con.mp4` would otherwise explode.
6. Long-path opt-in: most modern Windows installs support paths over 260 chars, but it's a registry / manifest flag. Document the requirement; don't try to engineer around it.
7. Get `pytest tests/` green on Windows CI.

> **Note on filesystem case-sensitivity.** Linux ext4 is case-sensitive; macOS APFS and Windows NTFS are both case-insensitive by default. The case-sensitive Linux CI cell is the strict gate — if it's green there, Windows is fine for that property. No extra audit needed.

### Phase 2 — serve mode and frontend (~3 days)

8. Test `bristlenose serve` on Windows manually. Process-group lifecycle (cleanly killing the Vite subprocess on Ctrl-C) is the likely sharp edge.
9. Run Playwright E2E on Windows. New `e2e/ALLOWLIST.md` section if any allowlist entries legitimately differ on Windows.

### Phase 3 — doctor and GPU detection (~2 days)

10. Extend `bristlenose doctor` with Windows-aware checks: ffmpeg from Scoop on PATH, Python version, NVIDIA driver version if a GPU is present, torch build flavour matches GPU presence.
11. Smoke-test on a real Windows machine — both with and without an NVIDIA GPU. Cohort tester or borrowed laptop.

### Phase 4 — Scoop packaging (~half day)

12. Write `bristlenose.json` Scoop manifest:
    - `depends`: `python`, `ffmpeg`
    - `installer.script`: probe `nvidia-smi`, pip-install bristlenose plus the correct torch wheel, download the spaCy model
    - `bin`: `bristlenose.exe` (from the wheel's entry point)
13. Host in our own Scoop bucket initially: `scoop bucket add bristlenose https://github.com/cassiocassio/scoop-bristlenose`.
14. Document install in README: `scoop bucket add bristlenose … && scoop install bristlenose`.
15. Later, once stable: submit to Scoop's `main` or `extras` bucket for lower friction and discoverability.

## Realistic total

**~1.5–2 weeks** of focused work for a contributor familiar with Python packaging on Windows. Phase 1 is the bulk; everything else is small once the CLI runs cleanly. Adds a Windows CI cell to keep it from rotting.

## Out of scope (for this milestone)

- Windows desktop GUI app
- Code-signed `.msi` / Microsoft Store listing
- ARM64 Windows support (Surface Pro X audience is too small to weight)
- Other Windows package managers (winget, Chocolatey) — easy follow-ons once Scoop works

## Open questions for whoever picks this up

- Is `nvidia-smi` reliably present when an NVIDIA driver is installed? If not, the install-time GPU probe needs a fallback (e.g. WMI query for display adapters).
- Does `faster-whisper` with the CPU torch wheel give acceptable transcription latency on a typical Windows researcher laptop? Worth a benchmark before committing to "CPU is fine as default."
- Scoop's `installer.script` runs PowerShell. How much can we move into a Python install helper invoked from that script vs keeping it in PowerShell?

## How to get involved

See [CONTRIBUTING.md](../CONTRIBUTING.md#windows-port). Open an issue first to coordinate — the maintainer's bandwidth for reviewing Windows-specific changes is small, so it works best if a contributor owns the port end-to-end.
