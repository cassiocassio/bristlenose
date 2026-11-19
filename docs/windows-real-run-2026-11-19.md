---
status: current — a dated record of one run, not a living design doc
last-trued: 2026-11-19
trued-against: HEAD@main on 2026-11-19
---

# Real-Windows run, 19 Nov 2026

What was run, on what, and what it showed. Two disposable Windows Server 2025
boxes on AWS (`aella`, m7i-flex.large, x64, an RDP desktop), both terminated the
same day. **Not a client edition**: SmartScreen, the Start menu and Windows on Arm
were not exercised. The design is in `docs/design-windows-port.md` and
`docs/design-winget.md`; the shipped CLI changes are in `9ae159692`.

## Results

| Claim | Expected | Actual | Evidence |
|---|---|---|---|
| The one-line installer works | uv, FFmpeg and Bristlenose installed per user | as expected | stages 1–2, ssh transcript |
| Missing FFmpeg prints a Windows banner | a `winget` row first, then "open a new terminal" | as expected, no `brew` or `apt` row | `_detect_distro()` returned `windows` |
| `setx` reaches only new windows | same window unchanged, a new window sees it | as expected | window 1 vs window 2 of the same run |
| `$env:` lasts for its window only | gone in a new window | as expected | same run |
| A bare `KEY=value` line in `.env` works | read; `export` prefix not needed | as expected | provider read back |
| `doctor` proxy hint | tells a Windows user what to type, then to open a new terminal | as expected | dead-proxy trigger |
| `doctor` auth-token hint | `Remove-Item Env:` and `[Environment]::SetEnvironmentVariable` | as expected | real trigger |
| Credential store | a protected file under `%USERPROFILE%\.config\bristlenose` | as expected, ACL checked | `state_path` and the file |
| Model-download banner shows the cache path whole | a Windows path | as expected | `_cache_root_display()` |
| winget (live, **0.36.0**) installs from the catalogue | `Successfully installed` | **fails with the bare line**, succeeds with `--id … -e --source winget` | `0x8a15005e` on msstore, then success |
| After install, the same window finds `bristlenose` | no (stale PATH) | no | `Get-Command` in the same session |
| After install, a new window finds it | yes | yes, `bristlenose 0.36.0`, FFmpeg 9.0.2 bundled | `doctor` clean |
| `bristlenose transcribe` on a spoken WAV | exit 0 | exit 0, **1m 17s** after the 1.6 GB model | RDP Terminal screenshot |
| First-run output is clean | no warnings | **Hugging Face and Xet warnings** on 0.36.0 | screenshot; 0.37.0's changelog says they are silenced, not re-run |
| Website, Windows browser (headless UA), both modes | Windows panel default, right command, one variant, PowerShell tab, tab remembered, no page error, no horizontal scroll at 375 px | 20 of 20 pass after one wrong test assertion was corrected; the page was not at fault | `wincheck.cjs` |
| Website, Edge on the box (script mode, live; winget mode via a tunnel) | PowerShell default, `$env:` sentence reads right | as expected | screenshots |

## Defects found, and where they went

1. **The bare `winget install Bristlenose.Bristlenose` is the wrong line.** It queries
   the Microsoft Store source too; here that failed, here that failed; on a client edition it is expected to prompt for Store terms (not exercised). Every page now uses `winget install --id Bristlenose.Bristlenose -e --source
   winget` (website `af39143`). Fixed.
2. **0.36.0's first run prints Hugging Face and Xet warnings.** Silenced in 0.37.0 per its changelog (not re-run on Windows); winget still serves 0.36.0. Resolved by shipping a newer version to winget
   (`docs/release-winget.md`).
3. **winget is absent in a fresh Server ssh session.** A test-harness finding, not a
   product defect: `Add-AppxPackage -RegisterByFamilyName -MainPackage
   Microsoft.DesktopAppInstaller_8wekyb3d8bbwe`, then `Add-AppxPackage -Path
   https://cdn.winget.microsoft.com/cache/source.msix`, gets it working headless
   (`0x8a15000f` otherwise).
4. **A job started with `Start-Process` over ssh dies with the session.** Harness only; run
   long jobs from the desktop.

## Not exercised

SmartScreen under `winget install --manifest` and the unsigned installer's dialog (needs
a client edition: the benbecula VMs); Windows on Arm; bare metal; the Start-menu
experience (there is none: the installer adds no shortcut and launches nothing).

## What this unblocks

The website carries both Windows variants behind `windows-install.json` (mode
`script` today). The flip to `winget` is one edit, gated by
`scripts/winget-ready.py` until winget serves **0.47.0** or newer. The next version is
a minor: 318 commits and user-facing features since 0.46.0.
