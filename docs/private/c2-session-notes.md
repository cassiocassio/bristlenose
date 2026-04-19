# Track C C2 — Session Notes (19 Apr 2026)

**One-sentence orientation.** C2 built the code + scripts that turn Apple Distribution cert + `bristlenose serve` Python sidecar into a notarised Gatekeeper-passing `.app`. Four of five commits landed. End-to-end wasn't proved because two pre-existing `#error` gates block Release compiles (SECURITY #5 and #8 in `SecurityChecklist.swift`). That's the next track, not C2.

## What was accomplished today

- Apple Developer portal fully wired: App ID `app.bristlenose`, Apple Distribution cert `Z56GZVA2QB`, provisioning profile "Bristlenose Mac App Store" (expires 19 Apr 2027). All the portal artefacts live in `~/Code/Apple Developer/`.
- Notarytool credentials saved to login keychain as profile `bristlenose-notary` (app-specific password generated at appleid.apple.com).
- Keychain partition list updated so `codesign` can use the Apple Distribution private key without GUI prompts (`security set-key-partition-list -S apple-tool:,apple: -s ~/Library/Keychains/login.keychain-db`). Permanent per-Mac setup.
- Four commits on `sidecar-signing` branch (`fc95b99`, `857cab2`, `0db0b28`, `cd04ee9`):
  1. Split `build-sidecar.sh` into build + `sign-sidecar.sh`. Parallel signing with `wait -n` bash job pool at `SIGN_JOBS=$(sysctl -n hw.ncpu)`. Per-file logs to `desktop/build/codesign-logs/`. `sign-manifest.json` with SHA256s. Pre-flight refuses identity-swap re-sign unless `ALLOW_RESIGN=1`.
  2. `fetch-ffmpeg.sh` ported from v0.1-archive with SHA256-pinned FFmpeg 8.1. `sign-ffmpeg.sh` new — third-party static Mach-Os need Hardened Runtime too. `build-all.sh` scaffolded with pre-flight and parallel fetch+build.
  3. `ExportOptions.plist` — App Store method, manual signing. pbxproj Release config flipped to Manual + Apple Distribution cert + Bristlenose Mac App Store profile. Debug stays Automatic.
  4. Notarisation + stapling + full verification battery in `build-all.sh` (steps 7–10). `get-task-allow` scan in `check-release-binary.sh`.

## What works (proven end-to-end, solo-tested)

- `build-all.sh` pre-flight → parallel fetch-ffmpeg + build-sidecar → sign-ffmpeg → sign-sidecar → **everything up to step 5**.
- 240 inner Mach-Os + outer sidecar, real Apple Distribution cert, trusted timestamps verified per file, deep-verify passes, manifest emitted. Silent (no keychain prompts) thanks to the partition list.
- Parallel signing: 3.6 s ad-hoc, ~30 s with real-identity TSA calls at `SIGN_JOBS=12`.

## What's parked, and why

- **End-to-end archive + notarise + staple.** `xcodebuild archive` fails on two `#error` directives in `desktop/Bristlenose/Bristlenose/SecurityChecklist.swift`:
  - **SECURITY #5** — `ServeManager.killOrphanedServeProcesses` SIGINTs any PID listening on 8150–9149 without checking it's actually a bristlenose process. On a multi-user Mac that could terminate unrelated processes. Fix: match process name before kill.
  - **SECURITY #8** — WKWebView navigation policy allows any `127.0.0.1:*`. Fix: restrict to the specific serve port the project was assigned.
  - Both are genuine security bugs. Fixing them is a separate track, 30–60 min each. They block every future Release archive, so they're now gating both C2 verification AND C3 TestFlight work.
- **Empty-entitlements re-test.** Plan deliverable 7: strip inner signatures with `codesign --remove-signature`, swap `bristlenose-sidecar.entitlements` to `<dict/>`, re-sign, see if `cs.disable-library-validation` is still needed now that the whole bundle is signed by one identity. Deferred because it doesn't block C2 utility and is cheap to run later (one fresh-build + re-sign cycle). If it's green, we can drop DLV entirely — a strong procurement story.

## Gotchas burned in (things I'll forget and re-learn)

1. **macOS default bash is 3.2; scripts need bash 4.3+ for `wait -n`.** `sign-sidecar.sh` asserts this at the top. `#!/usr/bin/env bash` picks up Homebrew's bash on this Mac; a fresh Mac without it will fail loudly.
2. **`codesign -dvv | grep -q` trips `pipefail` via SIGPIPE.** `grep -q` exits on first match, codesign keeps writing, gets SIGPIPE, returns 141. Always capture codesign output into a variable first, then grep the string. Fixed in four places during the session.
3. **Keychain access-control prompts race under parallel codesign.** "Always Allow" on the first prompt doesn't short-circuit the 11 other already-queued prompts. Two fixes: (a) run `SIGN_JOBS=1` once to get a single prompt, or (b) set the keychain partition list (canonical CI incantation). Did (b).
4. **`security set-key-partition-list` with `-s` but no `-k` applies to ALL signing keys in the keychain.** Dumps metadata for each key touched — looks noisy but is expected.
5. **App Store Connect app record vs Apple Developer App ID are different things.** We have the App ID (portal). The ASC record is Track B / C3 — not needed for C2.
6. **`notarytool submit --output-format plist`** writes XML plist to stdout; the submission UUID is at `:id`. `notarytool log <UUID> <file>` writes the JSON log to the given file.
7. **Only `ditto -c -k --sequesterRsrc --keepParent` produces a notarisation-compatible zip.** Plain `zip` mangles xattrs and symlinks inside `.app`.
8. **Run-script build phase warns "will be run during every build"** because the existing "Copy Sidecar Resources" phase has no declared outputs. Not our fault; worth adding to qa-backlog as a perf nit.

## File map — where the C2 work landed

| File | Purpose |
|---|---|
| `desktop/scripts/build-sidecar.sh` | PyInstaller --onedir build only (signing extracted) |
| `desktop/scripts/sign-sidecar.sh` | Parallel inner-Mach-O sign, outer sign, strict verify, manifest |
| `desktop/scripts/fetch-ffmpeg.sh` | SHA256-pinned FFmpeg 8.1 download, cached under `desktop/build/ffmpeg-cache/` |
| `desktop/scripts/sign-ffmpeg.sh` | Sign the two FFmpeg siblings with the same identity |
| `desktop/scripts/build-all.sh` | End-to-end orchestrator: pre-flight → fetch+build → sign → archive → export → gate → profile-check → notarise → staple → verify |
| `desktop/scripts/check-release-binary.sh` | Post-archive gate: no `BRISTLENOSE_DEV_*` literals, no `get-task-allow=TRUE` in any shipped Mach-O |
| `desktop/Bristlenose/ExportOptions.plist` | App Store method, manual signing, Apple Distribution, `Bristlenose Mac App Store` profile |
| `desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj` | Release config: `CODE_SIGN_STYLE=Manual`, cert/team/profile pinned |
| `desktop/bristlenose-sidecar.entitlements` | Unchanged; still `cs.disable-library-validation` only |

Build outputs (gitignored):

- `desktop/build/codesign-logs/` — per-Mach-O sign log
- `desktop/build/sign-manifest.json` — path / SHA256 / identity per signed Mach-O
- `desktop/build/xcodebuild-{archive,export}.log`
- `desktop/build/notarytool-{submit,log}.{log,json}`
- `desktop/build/embedded-profile.plist` — decoded provisioning profile for assertions
- `desktop/build/Bristlenose.xcarchive` / `desktop/build/export/Bristlenose.app` — final artefacts

## How to come back and resume

**Goal 1 — unblock end-to-end (fix SECURITY #5 + #8).**

1. Open `desktop/Bristlenose/Bristlenose/SecurityChecklist.swift` — it tells you exactly what to do. Two `#error`s; each maps to a file + a suggested fix.
2. Fix each; delete the matching `#error` + `#warning` pair.
3. Re-run `SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" desktop/scripts/build-all.sh`. Expect it to go all the way through notarisation (1–15 min Apple queue) to a stapled `.app`.

**Goal 2 — empty-entitlements test (procurement win if it passes).**

1. Back up: `cp desktop/bristlenose-sidecar.entitlements desktop/bristlenose-sidecar.entitlements.dlv-backup`
2. Write empty: `printf '<?xml version="1.0"?>\n<plist version="1.0"><dict/></plist>\n' > desktop/bristlenose-sidecar.entitlements`
3. Fresh build: `rm -rf desktop/Bristlenose/Resources/bristlenose-sidecar && desktop/scripts/build-sidecar.sh`
4. Sign: `SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" desktop/scripts/sign-sidecar.sh`
5. Test: `desktop/Bristlenose/Resources/bristlenose-sidecar/bristlenose-sidecar --port 18150 --no-open /tmp/scratch` → separate shell → `curl -sI http://localhost:18150/` should respond (even 404 is fine; means it booted).
6. Green → commit empty file; update `docs/design-desktop-python-runtime.md` entitlement table to remove DLV justification.
7. Red → restore from backup: `mv desktop/bristlenose-sidecar.entitlements.dlv-backup desktop/bristlenose-sidecar.entitlements`; add a note in the entitlement table explaining the real reason DLV is load-bearing.

**Goal 3 — C3 (TestFlight upload).**

Prerequisites:
- Goal 1 done (end-to-end produces a notarised `.app`)
- App Store Connect app record created (separate portal — Track B)
- `.pkg` export via `xcodebuild -exportArchive` with `method=app-store` (already in ExportOptions.plist)
- Upload via `xcrun notarytool submit <pkg> --keychain-profile bristlenose-notary` OR Transporter.app

This is its own commit / track, not more C2.

## Open questions (things I couldn't answer without asking you)

- Is Martin's intent to fix SECURITY #5 + #8 as part of the next session (unblock full alpha path), or to address them in their own dedicated track with proper review?
- Is the `build.keychain` refactor (dedicated keychain for signing, login keychain untouched) wanted pre-alpha, or post-alpha?
- For the provisioning profile verification in `build-all.sh`: today it asserts bundle ID + team ID. Should it also check profile expiry and warn at ≤30 days?

## Canonical commands cheat sheet

```bash
# Full build (requires SECURITY #5 + #8 fixes):
SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" desktop/scripts/build-all.sh

# Just the sidecar sign cycle:
SIGN_IDENTITY="Apple Distribution: Martin Storey (Z56GZVA2QB)" desktop/scripts/sign-sidecar.sh

# Scan any archive/app/binary for dev env-var leaks or get-task-allow:
desktop/scripts/check-release-binary.sh desktop/build/export/Bristlenose.app

# Verify notarytool creds still work:
xcrun notarytool history --keychain-profile bristlenose-notary

# Re-set keychain partition if codesign starts prompting again:
security set-key-partition-list -S apple-tool:,apple: -s ~/Library/Keychains/login.keychain-db
```

## References

- `~/.claude/plans/from-the-setup-session-sprightly-locket.md` — the approved C2 plan (includes usual-suspects review findings)
- `~/.claude/plans/prompt-for-c2-structured-gray.md` — the original C2 prompt (superseded)
- `docs/design-desktop-python-runtime.md` — canonical shipping architecture (updated in commit 5)
- `docs/private/sprint2-tracks.md` — Track C C2 marked done
- `docs/private/qa-backlog.md` — parked items
- `desktop/v0.1-archive/scripts/` — source material for the port-forwards
- `~/Code/Apple Developer/` — portal artefacts (NDA material; not in any git repo)
- `~/Code/bristlenose-docs-private/infrastructure-and-identity.md` — cert + profile + keychain partition notes (private)
