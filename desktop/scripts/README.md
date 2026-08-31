# desktop/scripts

Build, signing, verification and reset scripts for the macOS **Bristlenose.app**
and its bundled PyInstaller `bristlenose serve` **sidecar**.

Thirty-odd files, but you only ever type about eight of them. This README is
organised by **what you're trying to do**; the reference tables are at the
bottom. The *why* lives in [`desktop/CLAUDE.md`](../CLAUDE.md) and the design
docs.

> **The flat layout is deliberate — don't reorganise into subdirectories.**
> Considered and rejected 4 Aug 2026. About 150 references to these paths live
> *outside* this folder, concentrated in the two `CLAUDE.md` files, the xcodeproj
> build phases, and CI — so subdirectories mean a rename sweep across exactly the
> documents that steer future sessions, and every reference the sweep misses
> becomes a broken path pointing somewhere plausible. The `build-` / `check-` /
> `sign-` / `test-` / `ensure-` prefixes already group these in `ls`. What was
> actually missing was *which channel* and *which direction the calls run* — both
> documentation problems, fixed here rather than by moving files.

Every script resolves its own paths (via `$0`), so invoke it from anywhere.
Inside this folder, prefix with `./` — it isn't on `PATH`.

---

## First: two channels, and they don't mix

Bristlenose reaches Macs **two separate ways**. They share the sidecar and
almost nothing else.

| | **App Store / TestFlight** | **Developer-ID `.dmg`** |
|---|---|---|
| Artefact | `.pkg` → App Store Connect | `.dmg` → bristlenose.app |
| Signed with | Apple Distribution | Developer ID Application |
| Checked by | App Store Connect, server-side | Apple's notary, then Gatekeeper on the user's Mac |
| You run | `build-all.sh` | `build-dmg.sh` then `upload-dmg.sh` |
| Lifespan | permanent | **expires 30 days from the cut** |

**`build-all.sh` does not cut the `.dmg`. `build-dmg.sh` produces nothing App
Store Connect will accept.** Running the wrong one is the easiest mistake here.

---

## Jobs

### “Ship a TestFlight build”

```bash
./desktop/scripts/build-all.sh
./desktop/scripts/upload-testflight.sh
```

**Two commands, deliberately.** Building and sending are separate acts: different
credentials, and only one of them is irreversible. There is no `--upload` flag on
`build-all.sh` — a flag that's off in every run is configuration for the
configurable.

`build-all.sh` bails on any non-zero exit and runs the sidecar build, the
signing, the archive and its own gates — you don't invoke those separately. It
needs an Apple Distribution identity. It does **not** need notarytool
credentials: `notarytool` only accepts Developer ID, and App Store Connect
validates server-side instead (that's the `.dmg` channel's requirement, not this
one).

`upload-testflight.sh` runs `check-pkg-shippable.sh` as a precondition — there is
no flag to skip it (it does set `BN_SKIP_ASC_VALIDATE=1`, which turns the gate's
*last* check, `altool --validate-app`, into an announced skip on this path only:
the upload transfers the same bytes minutes later and Apple revalidates
server-side, so pre-validating shipped 675 MB twice per release; every local
check still runs) — then uploads, waits for a terminal state, and asks App Store
Connect independently whether the build actually arrived, because a zero exit
from `altool` is not proof that it did. **A non-zero exit from the uploader does
NOT mean the upload failed**: an unconfirmed delivery exits 1 with an
UNCONFIRMED banner precisely because the build number is spent either way — the
recovery is to look in App Store Connect, never to re-upload at that number. One-off setup, same gitignored
`.ship-local.conf`:

```bash
BRISTLENOSE_ASC_KEY_ID="<key id>"
BRISTLENOSE_ASC_ISSUER_ID="<issuer uuid>"
BRISTLENOSE_ASC_APPLE_ID="<numeric app id>"
```

Each upload spends its build number forever. A replacement needs a higher one:
`./scripts/bump-version.py --build-only`.

### “Cut a `.dmg` and publish it”

```bash
./desktop/scripts/build-dmg.sh              # ~30 min: build + ONE notary wait (app-level notarisation retired 14 Aug 2026)
./desktop/scripts/upload-dmg.sh --dry-run   # probes the host, changes nothing
./desktop/scripts/upload-dmg.sh             # publishes
```

Run the dry run every time — it checks ssh, the target dir, remote `shasum` and
free space, and shows what would change *before* you commit to an upload. One-off
setup, in a gitignored `desktop/scripts/.ship-local.conf`:

```bash
BRISTLENOSE_DMG_REMOTE="host:/path/to/site/dmg"
```

Then deploy the website so the docs match the build.

Two things about this channel that bite: the 30-day clock starts at the **build**
date, not the upload, so sitting on a cut costs its shelf life. And the download
link is a permalink that *redirects* to the versioned file — see
[`docs/design-dmg-build.md`](../../docs/design-dmg-build.md) § Publishing for why
both URLs exist.

### “I changed Python or the frontend — show me it in the app”

Usually: **just Cmd+R.** The Xcode *Ensure Sidecar Fresh* phase rebuilds a stale
sidecar for you, and the freshness gate fails the build if it can't. You only do
this by hand when you want to control the signing identity or debug the bundle:

```bash
(cd frontend && npm run build)                       # build-sidecar bundles this, doesn't build it
./desktop/scripts/build-sidecar.sh
SIGN_IDENTITY=- ./desktop/scripts/sign-sidecar.sh    # "-" = ad-hoc, fine locally
# Xcode: Shift+Cmd+K, then Cmd+R
```

Faster for pure backend/frontend iteration: the **Bristlenose (Dev Sidecar)** or
**(External Server)** schemes skip the bundle entirely (`desktop/CLAUDE.md`
§ Dev workflow).

### “Fresh worktree, nothing builds”

```bash
./desktop/scripts/fetch-ffmpeg.sh    # gitignored binaries don't follow worktrees
```

Also expect the **first** `xcodebuild` to fail with `cannot find
'GeneratedBuildInfo' in scope` — the file is generated by a build phase that
runs after the compile list is snapshotted. Re-run; it succeeds.

### “The app won't launch / the sandbox is wedged”

```bash
./desktop/scripts/reset-sandbox-state.sh
```

Symptom it fixes: `EXC_BREAKPOINT` in `_libsecinit_appsandbox.cold.*` at launch.
⚠️ **Destroys data on sandboxed builds** — the container holds `projects.json`,
`consentLog` (the AI-disclosure audit trail, Apple 5.1.2(i)) and
`aiConsentVersion`. Snapshot first if they matter. `--dry-run` to preview.

### “I'm changing the build scripts and don't want to break them”

```bash
./desktop/scripts/test-ensure-sidecar.sh
./desktop/scripts/test-upload-dmg.sh
```

Seconds each, no network, no build, no fresh cut. Run both after touching the
build gating or the publish path.

### “A gate failed and I want to run just that one”

Every `check-*.sh` is standalone and takes the thing it checks:

```bash
./desktop/scripts/check-dmg-shippable.sh desktop/build/Bristlenose-0.24.0.dmg
./desktop/scripts/check-release-binary.sh path/to/Bristlenose.app
./desktop/scripts/check-bundle-manifest.sh
```

Exit `0` = clean, `1` = violation. Add `BN_REPORT=0` in front for plain output
instead of the rendered report.

---

## What you run vs what runs itself

**You type these** — seven, realistically:

`build-all.sh` · `upload-testflight.sh` · `build-dmg.sh` · `upload-dmg.sh` ·
`build-sidecar.sh` · `sign-sidecar.sh` · `reset-sandbox-state.sh` · `test-*.sh`
<br>(plus `fetch-ffmpeg.sh` once per worktree, and any `check-*.sh` when you're
debugging a specific failure)

**Xcode runs these** — never by hand:

`generate-build-info.sh` · `ensure-sidecar.sh` · `check-sidecar-freshness.sh` ·
`build-mcpb.sh`

**Nothing runs these directly — they're dependencies:**

| File | Why it exists |
|---|---|
| `report.sh` | Sourced by every build script; emits the events. **Must stay bash-3.2-safe** — the Xcode phase runs it under `/bin/bash` 3.2. |
| `build_report.py` | The Rich renderer that consumes those events. Invoked by `report.sh`. |
| `sidecar-source-hash.sh` | Sourced; the fingerprint recipe driving incremental rebuilds. |
| `check-sidecar-appstore-strings.py` | Implementation behind the `.sh` wrapper. **Always call the `.sh`** — it probes for PyInstaller and falls back `.venv-sidecar` → `.venv`; a raw `.py` call under a broken venv exits 1 from an uncaught `ImportError`, which looks exactly like a real detection. |
| `build_report_mock.py` | Renders sample output for iterating on the report style. |
| `bundle-manifest-allowlist.md` | Consumed by `check-bundle-manifest.sh`. |
| `logging-hygiene-allowlist.md` | Consumed by `check-logging-hygiene.sh` — add `<!-- ci-allowlist: HYG-<N> -->` + justification. |
| `REPORT-STYLE.md` | The shared CLI report style + event protocol. |

---

## The map

Who calls whom. Everything indented is invoked *for* you.

```
build-all.sh ──────────────── App Store / TestFlight
  ├─ check-bundle-manifest.sh          (before the slow build)
  ├─ ensure-sidecar.sh
  │    ├─ fetch-ffmpeg.sh
  │    ├─ build-sidecar.sh ─── sidecar-source-hash.sh
  │    ├─ doctor --self-test   (PRE-SIGN, on rebuild → .selftest-stamp)
  │    ├─ sign-ffmpeg.sh
  │    └─ sign-sidecar.sh
  ├─ (step 2a: asserts .selftest-stamp matches the bundle — exit 1 if absent/stale)
  ├─ check-sidecar-appstore-strings.sh ─ …-strings.py
  ├─ build-mcpb.sh ─── check-mcpb.sh
  ├─ check-release-binary.sh
  ├─ check-logging-hygiene.sh
  └─ check-appearance-seam.sh

build-dmg.sh ──────────────── Developer-ID .dmg
  ├─ ensure-sidecar.sh                 (same subtree as above)
  ├─ check-release-binary.sh
  └─ check-dmg-shippable.sh            (step 10; the publish gate)

upload-dmg.sh ─────────────── publishes a cut .dmg
  └─ check-dmg-shippable.sh            (precondition, not a skippable step)

Xcode build phases
  ├─ generate-build-info.sh
  ├─ ensure-sidecar.sh
  ├─ check-sidecar-freshness.sh
  └─ build-mcpb.sh

reset-app-state.sh ─── reset-sandbox-state.sh

test-ensure-sidecar.sh ─── build-sidecar.sh --dry-run, sidecar-source-hash.sh
test-upload-dmg.sh ─────── upload-dmg.sh (sourced), check-dmg-shippable.sh

report.sh ─── build_report.py           (sourced by ~everything above)
```

Two things this makes visible. **`ensure-sidecar.sh` is the shared trunk** —
both channels and Xcode go through it, which is why a sidecar change affects
everything. And **`check-dmg-shippable.sh` is reachable three ways** (build step
10, upload precondition, by hand), deliberately: it's the one answer to “is this
safe to hand a stranger”, so there's no second implementation to drift.

---

## Reference

### Shared foundation — feeds both channels

| Script | What it does |
|---|---|
| `build-sidecar.sh` | PyInstaller `--onedir` of `bristlenose serve` → `Resources/bristlenose-sidecar/`. Per-layer incremental; `--force` (releases) recreates `.venv-sidecar` so the dep closure is clean. **Needs the frontend pre-built** — it bundles `bristlenose/server/static/` but doesn't run `npm run build`. Prereq: `python3.12` on `PATH`. |
| `ensure-sidecar.sh` | Orchestrates build + **pre-sign `doctor --self-test`** + sign + deep-verify. The self-test runs between build and sign because that is the *only* window it can: sign-sidecar applies `app-sandbox` unconditionally (ASC requires it on nested executables) and a sandbox-signed binary aborts standalone (exit 133) — attempting it post-sign is how the check sat dead 14 Jul → 14 Aug. Writes `.bristlenose-sidecar.selftest-stamp` beside `.sign-stamp`; build-all's step 2a asserts it. The Xcode phase calls this, which is why a plain Cmd+R self-heals a stale bundle. |
| `sign-sidecar.sh` | Signs every Mach-O (240+) leaf-first via a `wait -n` pool — not `xargs -P`, which drops child exit codes on BSD. |
| `fetch-ffmpeg.sh` | Pinned-SHA256 static `ffmpeg` + `ffprobe` (arm64). Gitignored output; doesn't follow worktrees. |
| `sign-ffmpeg.sh` | Signs those two (separate from the sidecar: single Mach-O, no entitlements). |
| `generate-build-info.sh` | Writes `GeneratedBuildInfo.swift` (gitignored) from git state. |
| `check-bundle-manifest.sh [root]` | Every runtime-data dir under `bristlenose/` is covered by a `datas` entry in the spec — catches "in source, missing from bundle" before the 3-min build. |
| `check-sidecar-freshness.sh` | Fails the Xcode build if the bundle predates a Python/frontend/locale edit. |
| `check-sidecar-appstore-strings.sh` | Decompresses the PYZ and scans code-object constants for App Store §2.5.2 blockers (`itms-services`, frozen in by CPython). Invisible to `grep`/`strings`. |

### App Store / TestFlight only

| Script | Asserts |
|---|---|
| `build-all.sh` | — (the chain itself) |
| `check-release-binary.sh <archive\|app\|binary>` | No `BRISTLENOSE_DEV_*` escape-hatch literals survive in the Release Mach-O — they live under `#if DEBUG`. |
| `check-logging-hygiene.sh [root]` | No Swift `Logger` interpolates a credential-shaped identifier without a `privacy:` marker; no `print()` dumps env. |
| `check-appearance-seam.sh` | The light/dark mapping isn't re-derived outside `AppAppearance.swift`; panels call `adoptHostAppearance()`; `AppDelegate` still calls `beginApplying()`. |
| `build-mcpb.sh` / `check-mcpb.sh` | Builds and gates the `.mcpb` agent extension bundled into the app. |
| `check-pkg-shippable.sh <pkg>` | **Interrogates the `.app` inside the `.pkg`**, not the xcarchive copy the other gates read. Installer cert is specifically `3rd Party Mac Developer Installer`; payload holds exactly one app; version agrees with the working tree; signature `--deep --strict`; `get-task-allow` absent; host + nested **executables** carry `app-sandbox` (ASC rejection #2); no auto-derived framework identifiers (rejection #3); Hardened Runtime; privacy manifests; `ITSAppUsesNonExemptEncryption` present; §2.5.2 PYZ scan re-run against the bundled sidecar; provisioning profile not expired (warns at T-30); then `altool --validate-app` last — skipped for ad-hoc, unconfigured, or `BN_SKIP_ASC_VALIDATE=1` (the uploader's announced skip; standalone runs keep it as the dry run). Check 3 fails closed since 14 Aug: an empty version extraction is fatal, version and build mismatches report separately, and the four pbxproj configs must agree. |
| `upload-testflight.sh [<pkg>]` | Runs the gate as a precondition (no skip flag), names the app record explicitly so altool never infers it, uploads with `--wait`, parses `PROCESSINGSTATE` as an allowlist, then **independently** re-asks ASC via `--build-status` because a zero exit from altool is not proof the build landed. Prints the delivery UUID on every path including failure, Apple's errors verbatim, and Transporter as the documented fallback. Since 14 Aug: an **unparsed** delivery UUID is fatal (it silently disables the independent check), and an unconfirmed delivery prints an UNCONFIRMED banner and **exits 1 — which does not mean the upload failed**; the build number is spent, check ASC, never re-upload at that number. |
| `test-check-pkg-shippable.sh` | Drives each of the above red via a synthetic signed `.pkg` — a gate that can't fail is worse than no gate. 7 cases, ~10s. |

### Developer-ID `.dmg` only

| Script | What it does |
|---|---|
| `build-dmg.sh` | The 10-stage cut: sidecar → archive → export as Developer ID → verify → `create-dmg` → notarise + staple `.dmg` (**one** round trip — app-level notarisation retired 14 Aug 2026; the dmg's ticket covers the nested app, trading offline-first-launch of a dragged-out app) → manifest → gates. |
| `check-dmg-shippable.sh <dmg>` | Versioned filename; image signed, stapled, Gatekeeper-accepted; and the load-bearing one — the app **inside the mounted image** passes `codesign --deep --strict` and reads `source=Notarized Developer ID` (the latter via **online** ticket lookup — the inner app is deliberately unstapled since 14 Aug, so this gate needs network). Plus filename↔`Info.plist` version agreement and manifest↔image sha256. |
| `upload-dmg.sh [--dry-run] [--keep N]` | Gates, stages to a dot-prefixed name **in the target dir** (so `mv` stays atomic), verifies the sha256 of what landed, `chmod 644`, swaps, repoints the permalink, reaps all but the newest N. Skips the transfer if identical bytes are already on the host. |

### Dev / QA / tests

| Script | What it does |
|---|---|
| `reset-sandbox-state.sh` | Clears stale App-Sandbox container state that wedges `libsecinit`. `--quiet`, `--dry-run`. macOS only. |
| `reset-app-state.sh` | "Clean-ish profile" reset for UX walkthroughs; calls the above. |
| `test-ensure-sidecar.sh` | Build-gating and orchestrator decisions, via `--dry-run` + controlled stamp state. |
| `test-upload-dmg.sh` | The publish path's decisions — the swap decision (incl. empty-vs-empty, where a bare equality test reads two *failed measurements* as a match), retention, the unconfigured refusal, and the shippability gate proven against a real notarised artefact. |

---

## Signing identities — there are TWO, and they are not interchangeable

The two channels want different certificates:

| variable | script | certificate | source |
|---|---|---|---|
| `SIGN_IDENTITY_APPSTORE` | `build-all.sh` | `Apple Distribution: …` | env → `.ship-local.conf` → **hard stop** |
| `SIGN_IDENTITY_DEVELOPER_ID` | `build-dmg.sh` | `Developer ID Application: …` | env → `.ship-local.conf` → **hard stop** |

Since 31 Aug 2026 both scripts source `.ship-local.conf` (env wins — the
release driver exports values it has already resolved and probed), and the
value may be a **SHA-1 fingerprint** rather than a name: Apple cert renewal
leaves two valid certs with the identical common name, and only the hash
splits the pair. Each script maps hash → common name for its type gate and
signs with the form it was given. `build-dmg.sh`'s old silent name-guess
default (interpolating `$TEAM_ID` into a personal name, unchecked until
minute 30) is retired — unset now fails loudly, mirroring `build-all.sh`.
The conf never feeds the bare `SIGN_IDENTITY` — that stays a per-invocation
parent-to-child handoff, and `release.sh run` refuses an ambient one outright.

Each entry point asserts the **type** of what it is given, so handing one the
other's certificate fails immediately rather than at the last Gatekeeper
assertion. `SIGN_IDENTITY_APPSTORE=-` is the deliberate ad-hoc local build;
`build-dmg.sh` has no ad-hoc path at all, because notarisation needs a real cert.

Child signers (`sign-sidecar.sh`, `sign-ffmpeg.sh`, `ensure-sidecar.sh`) still
read plain **`SIGN_IDENTITY`**, exported by whichever parent invoked them. That
contract is fine: the child signs with whatever its parent chose.

**The trap this replaced.** Both entry points used to read `SIGN_IDENTITY`, and
both export it. So exporting the value one of them needs silently mis-signed the
other — and on 27 Aug 2026 it did: `SIGN_IDENTITY` was exported as Apple
Distribution so `build-all.sh` would run, `build-dmg.sh` inherited it in place of
its default, and the image was rejected —

```
✓ inner app Gatekeeper   Notarized Developer ID     ← the app was perfect
✗ image Gatekeeper       rejected, origin=Apple Distribution
```

— after a full 30-minute build and a notarisation round-trip. `build-dmg.sh` no
longer falls back to an ambient `SIGN_IDENTITY`: a value exported for a different
script is not evidence anyone meant it to apply here. Legacy `SIGN_IDENTITY` still
works for `build-all.sh`, with a warning. `check-release-ready.sh` also reports a
stale exported `SIGN_IDENTITY` at preflight, so it costs a second rather than half
an hour.

`TIMESTAMP_FLAG` follows suit: a real Apple TSA timestamp for a real identity,
`--timestamp=none` for ad-hoc.

---

## See also

- [`REPORT-STYLE.md`](REPORT-STYLE.md) — the CLI report style + event protocol
  every script here follows, so the output reads as one system
- [`desktop/CLAUDE.md`](../CLAUDE.md) — app + sidecar architecture, the three dev
  schemes, and the build/signing gotchas
- [`docs/design-dmg-build.md`](../../docs/design-dmg-build.md) — the `.dmg`
  channel: signing flow, notarisation failure modes, publishing model
- [`docs/design-desktop-python-runtime.md`](../../docs/design-desktop-python-runtime.md)
  — the bundled-sidecar shipping design
