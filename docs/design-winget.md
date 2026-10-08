---
status: plan v2 — step 1 done and re-proven on a box after a review (8 Oct 2026); step 2's CI job written, not yet run on GitHub
---

# Bristlenose on winget

**Goal.** `winget install Bristlenose` on a Windows machine with no Python gives a
working `bristlenose` in a new terminal; `winget upgrade` replaces it in place;
`winget uninstall` leaves nothing but the user's own data.

**Where Windows stands** (`docs/design-windows-port.md`, status section): since 0.34.0
the CLI installs and runs on Windows through pipx or uv on x64 Python, and a one-line
installer (`irm …/scripts/windows/install.ps1 | iex`) wraps the uv route. That
one-liner is the near-term way in. winget is the channel Windows itself offers,
the one IT departments recognise, and the long-term form; this plan is how to do it
properly once.

## What winget is, for us

A catalogue of YAML manifests in `microsoft/winget-pkgs`. Each manifest points at an
installer **we** build and host (a GitHub Release asset) and pins its SHA-256.
Microsoft builds nothing: it validates the manifest, scans the installer (multi-engine
antivirus, then Defender after a real non-elevated install), and a moderator approves
the first submission. It is a hash-pinned, malware-scanned index that IT recognises,
not an endorsement of what the app does. The `winget` client itself is Microsoft's and
ships with Windows 10 and 11.

So the work is ours: **a self-contained Windows build** (Windows has no system Python)
and **an installer** around it, then one manifest per release.

## Decisions

| | Decision | Why |
|---|---|---|
| Build | PyInstaller one-folder, x64, CPU only, from the **released wheel** | Fork of the Mac sidecar spec we already run. The wheel carries every data folder (SPA, export build, locales, alembic, prompts, codebooks, measured 5 Oct), so the Windows build ships exactly what PyPI ships, with no second SPA build. CPU only because the GPU path is where every faster-whisper-on-Windows report fails. x64 because `ctranslate2` has no win_arm64 wheel; Arm runs it under emulation |
| Installer | Inno Setup 7, **user scope** (`%LOCALAPPDATA%\Programs\Bristlenose`), fixed AppId, adds the folder to the **user** PATH and removes exactly that entry on uninstall | What the nearest twins ship (Buzz: PyInstaller + faster-whisper + Inno; Ollama: user-scope Inno). Not winget's "portable" zip: winget exposes portable apps through a symlink, and a PyInstaller exe cannot start through a Windows symlink (pyinstaller#8300); the workaround flag leaves the folder on PATH after uninstall (winget-cli#6160) |
| FFmpeg | Bundled, in `tools\` beside `bristlenose.exe`, pinned GyanD 9.0.2 essentials, SHA-256 checked at build | winget's dependency handling has open bugs on the upgrade paths we need (#4112, #4679, #4880). `tools\`, not the PATH folder, so ours neither shadows nor is shadowed by a user's own FFmpeg; `bundled_binary_path` looks there first in a frozen Windows build |
| PII redaction | **Not in the Windows installer build in v1.** `--redact-pii` refuses with a plain sentence pointing at the uv install | Its spaCy model cannot be downloaded into a frozen build. Opt-in, CLI-only; revisit by downloading the model to a data folder and loading it by path, which `s07` already supports |
| Upgrade while running | The installer and uninstaller **refuse** while `bristlenose.exe` is locked (a write-open check), with "Stop it, then run this again"; nothing is touched | Restart Manager closed it as Administrator (5 Oct), but as a non-admin user `RmGetList` failed and the rollback left an exe with no `_internal` (6 Oct). Refusing also never kills a long transcription. Consequence, not yet measured: `winget upgrade` with `serve` open fails until it is stopped |
| Identity | `PackageIdentifier: Bristlenose.Bristlenose`; Apps & Features Publisher **Bristlenose** | The `Ollama.Ollama` pattern. A one-way door: renaming later needs a migration |
| Signing | **Submit unsigned first; add a Certum Open Source Code Signing certificate later** | See "Signing" below |
| Arm64 | x64 installer only | Installs and runs under emulation on Windows on Arm, which is what every other route already does |

### Signing

winget accepts unsigned installers. An unsigned one meets SmartScreen's
"Windows protected your PC … Unknown publisher" on first run (seen on the test box,
5 Oct), and PyInstaller builds attract antivirus false positives. Options for Martin,
who signs as a private individual:

- **Microsoft Artifact Signing** (ex-Trusted Signing, ~$10/month): public-trust
  certificates for individuals only in the US and Canada; UK *organisations* are
  eligible. Out unless a company holds it (reported by two independent research
  passes citing Microsoft Learn's "code signing options"; re-read before relying on it).
- **SignPath Foundation's free OSS programme**: its terms require an OSI licence
  "without commercial dual-licensing", and the certificate names SignPath Foundation as
  publisher. Bristlenose's CLA exists to allow commercial or dual-licence versions, and
  Mac App Store distribution of AGPL code is commonly treated as needing one. Does not
  fit.
- **Certum Open Source Code Signing (cloud)**: ~€49 / $58 a year, issued to a natural
  person as "Open Source Developer, …", key in Certum's cloud HSM, signed through the
  SimplySign desktop app with a code from its phone app. **No CI support yet**, so each
  release is signed by hand on a Windows machine before the installer is published.

**Decision (5 Oct 2026): submit unsigned, add Certum later.** Adding signing later costs
nothing for future releases: each installer is signed before it is attached, and its
manifest carries the new hash. Published versions stay unsigned (signing changes the
bytes, and winget pins the hash). SmartScreen reputation starts accruing when signing
starts. Certum verifies identity documents first, so order a few days ahead.

**What the warning hits: winget installs too (measured 8 Oct 2026).** SmartScreen's
dialog is triggered by an unsigned executable carrying the Mark of the Web. The plan
inferred that an installer winget downloads and runs itself would carry no such mark,
so `winget install` might never show the dialog. **That was wrong.** winget applies the
mark itself (its log: "Started applying motw using IAttachmentExecute"), and on a
Windows Server 2025 desktop session `winget install --manifest` of the unsigned
installer stopped at the full-screen "Windows protected your PC — Microsoft Defender
SmartScreen prevented an unrecognized app from starting", Publisher: Unknown publisher,
with **Run anyway** behind "More info". It appeared again on `winget install --force`.
Measured with a local manifest served from 127.0.0.1; a package from the community
source is applied the same way, so the same dialog is expected there (inferred). The
uv route and the one-liner run no downloaded `.exe`, so they are unaffected.

So the unsigned period hits **every winget user**, not only people who download the
installer by hand. The decision above rested on the opposite assumption; whether to
submit unsigned anyway, or sign before the first submission, is reopened for Martin.

## What exists (on main since 5 Oct 2026; unreleased)

- `packaging/windows/bristlenose-win.spec` — the PyInstaller spec (fork of the Mac
  sidecar spec, with ctranslate2's DLLs and faster-whisper's VAD model collected
  explicitly, since no hook does).
- `packaging/windows/entry.py` — the whole CLI as the entry point, with
  `multiprocessing.freeze_support()`.
- `packaging/windows/build.ps1` — wheel → build venv (uv, Python 3.12) → PyInstaller →
  pinned FFmpeg into `tools\` → install-method marker → `smoke.ps1` → Inno →
  `-Manifest` fills the templates. Installs against `constraints.txt` (written by
  `lock.py`), refuses a wheel that is not this checkout's version, stamps the commit.
- `packaging/windows/smoke.ps1` — the 1.5 smoke tests, Python and FFmpeg off PATH.
- `packaging/windows/winget/` — the three manifest templates (schema 1.12.0).
- `packaging/windows/bristlenose.iss` — the installer.
- Product changes, each with a test that fails on any OS by recreating the Windows
  condition (`tests/test_windows_portability.py`):
  - the frozen Windows build never claims CUDA (it ships no cuBLAS/cuDNN, while
    ctranslate2 counts any NVIDIA GPU);
  - `bundled_binary_path` / `bundled_binaries_dir` prefer `tools\`;
  - doctor: "no terminal" is the Mac app only, "ships the extras" is any frozen build;
    the `winget` install method gives "reinstall with winget" fix text, never `pip`;
  - the PII refusal in a frozen Windows build speaks Windows.
- `doctor --self-test` checks the Windows transcription engine (ctranslate2,
  faster-whisper, the VAD model, ffmpeg from `tools\`).
- Contract tests in `tests/test_windows_packaging.py`: constraints match
  pyproject, the manifest's ProductCode is the Inno AppId, templates use only
  what the build fills, the smoke fixture is where `smoke.ps1` looks.

## What was measured (5 Oct 2026, fresh Windows Server 2025 x64 on aella)

| Check | Result |
|---|---|
| Build | 615 MB folder, 157 MB installer (FFmpeg's two static exes are 201 MB of it), 1,157 files, 250 PE files; deepest relative path 101 characters |
| Silent install as Administrator | exit 0; Apps & Features entry correct; user PATH gained the folder |
| `bristlenose` from a new session | `--version`, doctor (redirected to a file, prints `+`/`x`), transcribe a VTT, transcribe real audio with a kanji filename (52 s including the 1.6 GB first-run model download) |
| Upgrade in place with `serve` running | Restart Manager closed it; exit 0 in 21 s; new layout in place |
| Uninstall | exit 0; folder gone; exactly our PATH entry removed; Apps & Features entry gone; user config kept |
| Non-admin user | installs to its own AppData, PATH set, doctor and transcribe work |
| `winget validate` | succeeded (schema 1.9 for the box's winget 1.9) |
| `winget install --manifest` | succeeded |
| `winget list --id Bristlenose.Bristlenose` | not found — winget correlates installed apps against its sources, and the package is in none yet. Expected until published; re-check after |
| SmartScreen | "Unknown publisher" on a double-click from the desktop |

Testing traps found on the way (not product bugs): `Start-Process -Credential` from an
SSH session fails with 0xC0000142 even for cmd.exe; standard users on Server lack
"log on as a batch job", so scheduled tasks as them never run; `C:\Users\Public`
grants interactive but not network logons. The working route for a non-admin session
is SSH as that user (add to "OpenSSH Users", key file owned by the user).

## Reviews and where each finding landed

Two reviews of plan v1 (a design review and a parsimony review). Adopted: CUDA guard,
FFmpeg out of the PATH folder, stale files removed on upgrade (`[InstallDelete]`),
doctor's install method and frozen-build split, PII refusal text, Apps & Features
entries, pinned FFmpeg. Deferred by the parsimony review until a version is accepted:
release automation (winget-releaser), the release-board row, machine scope / MSI,
Sandbox testing, a CI Defender scan (Microsoft's validation already scans). Open and
taken into step 1 below: dependency pinning, a transcription self-test, a long-path
gate, smoke tests on the artefact, uninstall while running. Still open beyond step 1:
two installs coexisting (a uv/pipx `bristlenose` and the winget one on one PATH, and an
older install opening a database a newer one migrated), long project paths,
Smart App Control.

A third review (8 Oct 2026: correctness, silent failures, security) of the step-1
code. Fixed and re-proven on a fresh Server 2025 box the same night
(`git log --grep='review fixes' --grep='runs the engine'`):

- **Uninstall deleted `{app}` wholesale.** winget passes `--location` through as
  `/DIR=`, so `{app}` can be a folder of the user's. Now `_internal` and `tools`,
  then `{app}` only if empty; measured: a `keep.txt` in the chosen folder survives.
- **The running check refused on any open handle.** It now opens the exe sharing
  everything: a running image still refuses (exit 7), a sharing reader (Defender,
  Explorer's preview) does not; measured both ways.
- **No check ran the engine.** The self-test now runs the bundled `ffmpeg -version`
  and decodes a generated WAV through faster-whisper's decoder (PyAV).
- **The build could install unpinned packages** (`--constraint` pins only what it
  names): every installed distribution must now be in `constraints.txt` at its pin.
- **Smaller:** a stale server could pass the serve check; vcruntime was accepted
  anywhere; the moved-folder check ran only `--version`; a damaged install fell
  back to an FFmpeg on PATH (and Windows' `which` searches the current directory
  first); exit 7 now maps to winget's `packageInUse`; post-release versions, wheel
  paths with spaces, git stderr and a missing FFmpeg licence are handled.

Open from that review: dependency **hashes** (`--generate-hashes` /
`--require-hashes`; the pins stop drift but not a wheel added to a pinned version);
an `[InstallDelete]` rollback that a failure *other* than a running exe (disk full,
antivirus on a `.pyd`) can still leave half-installed; `winget` and `nvidia-smi`
still launched by bare name (`ollama.py`, `doctor_fixes.py`, `utils/hardware.py` —
`utils/safe_which.py` is the drop-in). The current-directory lookup for Ollama and
FFmpeg was fixed separately (`5f3d5ac8`, `47ee59af`).

## The road

1. **Land the work** (detailed below). ~1 day.
2. **Build it in CI before the tag.** A `workflow_dispatch` job on `windows-latest`
   runs step 1's build and smoke tests from `main` and keeps the installer as an
   artefact, so the Windows verdict exists before the irreversible act (the release
   machine's own rule). *Written 8 Oct 2026 as
   `.github/workflows/windows-installer.yml` (also on pull requests and pushes that
   touch `packaging/windows/`), with Inno Setup 7.1.0 pinned by hash and winget
   installed to validate the manifest; not yet run on GitHub.* The release then attaches that exact installer to the GitHub
   Release; it is **never rebuilt** for a published version (a rebuild changes the
   hash winget pinned).
3. **First submission by hand** with Komac or `wingetcreate`: one version per PR, sign
   Microsoft's CLA on the PR (a click-through, no country restriction), expect a
   false-positive cycle (submit to microsoft.com/wdsi/filesubmission, then
   `@wingetbot run`), days in the new-package moderator queue.
4. **Signing** (Certum) when Windows earns it; a manual SimplySign step per release.
5. **Automate** after one or two accepted versions: `winget-releaser` (classic PAT with
   `public_repo` + `workflow`, a winget-pkgs fork), a winget channel in
   `scripts/project.conf` with an expected "pending" state while moderators merge.
6. **Later, if earned:** machine scope for IT/Intune, a native Arm build once
   ctranslate2 publishes one, a shared FFmpeg build to roughly halve the size.

## Step 1 in detail: land the work

**Outcome:** on `main`, `packaging/windows/build.ps1 -Wheel <released wheel> -Installer`
on any Windows x64 machine produces an installer that passes every smoke test below;
the product changes are merged with their tests; the plan and the Windows record say
what is true.

**Where it stands (6 Oct 2026):** 1.1–1.8 are on main, and the acceptance run on a
fresh Windows Server 2025 box (aella) passed everything but the winget install:

- `build.ps1 -Installer -Manifest` from a HEAD wheel: all nine smoke checks green
  (deepest path 101, 615 MB folder, 157 MB installer), `winget validate` of the
  1.12.0 manifest passed under winget 1.29.
- Non-admin install: user PATH, a per-user Apps & Features entry (Bristlenose
  0.34.0), doctor and transcribe from a new session. Administrator install too.
- With `serve` running, install refuses (exit 7) and uninstall refuses (exit 1),
  the install intact; both are clean once it stops.
- **Settled 8 Oct 2026, on a desktop session over RDP:** `winget install
  --manifest` downloads, verifies the hash, then stops at SmartScreen's "Windows
  protected your PC / Unknown publisher" (the headless run on 6 Oct was waiting on
  exactly this, with no desktop to show it). After Run anyway it installs (exit 0);
  `winget install --force` reinstalls the same version (so doctor's reinstall advice
  works), with the dialog again. `winget list --id` and `winget uninstall --id` find
  nothing for a local manifest, which is not a source winget can match; that part is
  only testable once a version is published. See *Signing*: the dialog reopens the
  unsigned-first decision.

The run found two defects, fixed in the same commit (`git log --grep='winget
acceptance'`): the build packaged the checkout instead of the wheel when run from
the repo root, and an upgrade or uninstall over a running `serve` as a non-admin
user (Restart Manager's `RmGetList` failed) left `bristlenose.exe` without
`_internal`. The installer now refuses when the exe is locked, checked by a write
open; a WMI query was refused to that user and failed open.

### 1.1 Restore `winget-wip` onto main

Apply the branch's own diff (`git diff <base> winget-wip`) to the working tree with a
three-way merge, so anything the 0.34.0 run changed in the same files survives.
Resolve, run the gates (`pytest`, `ruff`, `check-ratchet`, `gen-test-inventory
--check`, `check-gate-policy`), commit in two parts: product changes with tests;
packaging + this doc.

### 1.2 Pin the build to what CI tested

The Mac lesson (0.30.0 #5): a build that resolves its own dependencies at release time
ships something nobody tested.
- Add `packaging/windows/constraints.txt`, generated with
  `uv pip compile pyproject.toml --extra voice --python-version 3.12
  --python-platform x86_64-pc-windows-msvc`, and have `build.ps1` install with
  `--constraint` it.
- A check that fails when `pyproject.toml` changes and the constraints file was not
  regenerated (the same shape as the inventory drift check).

### 1.3 Build from the released wheel, and say which

- `build.ps1` takes the wheel the release already builds (`Build wheel + sdist`), so
  the Windows bundle and PyPI carry the same code and the same SPA.
- It refuses a wheel whose version differs from `bristlenose.__version__` at the
  checkout, and writes `bristlenose/_build_info.py` into the build venv (commit SHA,
  build time) so `--version` and doctor's banner name the build, as the Mac sidecar's do.

### 1.4 A self-test for the Windows transcription engine

`doctor --self-test` checks the bundle's data but not transcription, because the Mac
build excludes it. Add `check_bundle_transcription` (frozen Windows build only):
import ctranslate2 so its DLL loop runs, assert faster-whisper's
`assets/silero_vad_v6.onnx` resolves, assert `bundled_binary_path("ffmpeg")` and
`("ffprobe")` resolve to `tools\` ahead of PATH. Unit-tested with the platform
patched, as the other frozen-build tests are. This lets a broken build fail in seconds
instead of at a user's first recording.

### 1.5 Smoke tests on the built folder (in `build.ps1`, also what CI runs)

Run with PATH stripped of Python and FFmpeg:
1. `bristlenose --version` and `--help`, each redirected to a file (the cp1252 case).
2. `bristlenose doctor --self-test`.
3. `bristlenose transcribe` on the smoke VTT fixture, from a folder with a space and a
   kanji in its name.
4. `bristlenose serve` on that output → `GET /report/` returns 200 with
   `bn-app-root` → stop it.
5. Copy the whole folder to a path with spaces and non-ASCII characters and rerun 1.
6. Gates: the deepest relative path in the bundle is at most 150 characters (101
   today); no CUDA DLL beyond ctranslate2's `cudnn64_9.dll` stub; `vcruntime140*.dll`
   present.

Not in v1: a real-audio transcription (needs the 1.6 GB model; the measured run above
stands in until CI caches a small model).

### 1.6 Installer hardening

- **Uninstall while running.** Check that the uninstaller closes a running
  `bristlenose` too (Restart Manager), so "uninstall leaves no folder" holds with
  `serve` open; if Inno does not, add an `InitializeUninstall` check that says
  "close Bristlenose first".
- **`DisplayVersion` = `PackageVersion` = `__version__`**, asserted by `build.ps1`
  after the installer is built (read back from the Inno script's `AppVersion`).
- Keep `[InstallDelete]` for `_internal` and `tools`.

### 1.7 The manifest lives in the repo

`packaging/windows/winget/` holds the three manifest templates (current schema for
submission), and `build.ps1 -Manifest` fills version, URL and SHA-256 from the built
installer. One source for what the manual submission (step 3) and the later automation
(step 5) send.

### 1.8 Docs

- This plan: mark step 1 done with what was measured.
- `docs/design-windows-port.md`: winget status line.
- `INSTALL.md`: nothing until a version is on winget.

### Acceptance for step 1

On a fresh aella Windows Server box: `build.ps1 -Wheel <0.34.x wheel> -Installer
-Manifest` passes every gate in 1.5; the installer installs as a non-admin user and as
Administrator; upgrade with `serve` running and uninstall with `serve` running both
leave the expected state; `winget validate` and `winget install --manifest` succeed.
On a stock Windows 11 machine (the UTM VM): `winget install --manifest` of the unsigned
installer, recording whether SmartScreen's dialog appears (the Mark-of-the-Web question
above), and the same installer double-clicked after a browser download, for comparison.
Then `aella down`.

## Who to lean on

- **The winget-pkgs docs** — Authoring.md, Policies.md, Validation.md,
  ValidationFailureGuide.md, the manifest schema. The authority; no credible agent skill
  for winget packaging exists (searched 5 Oct 2026).
- **Moderators** whose manifests and reviews set the practice: @Trenly, @russellbanks
  (author of Komac), @mdanish-kh, @ItzLevvie; Microsoft's @denelon.
- **Buzz** (`chidiwilliams/buzz`, `Buzz.spec`, manifest `c/ChidiWilliams/Buzz`) — the
  nearest twin: PyInstaller, faster-whisper, Inno, winget.
- **Ollama** (`o/Ollama/Ollama`) — user-scope Inno for a CLI plus server.
- **GitHub CLI** (`g/GitHub/cli`) — how a CLI offers an MSI for IT beside a zip.
