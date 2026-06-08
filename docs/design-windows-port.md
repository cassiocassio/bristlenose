# Windows port — sketch (deferred / long grass)

**Status:** parked. Not on the road to TestFlight, not on the post-TF roadmap as a maintainer commitment. Written up so it's costed and ready if someone in the community wants to drive it. See [CONTRIBUTING.md](../CONTRIBUTING.md#windows-port).

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
