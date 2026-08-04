# desktop/scripts

Build, signing, verification and reset scripts for the macOS **Bristlenose.app**
and its bundled PyInstaller `bristlenose serve` **sidecar**.

This file is the per-script index and the recipes. The *why* lives in
[`desktop/CLAUDE.md`](../CLAUDE.md) and
[`docs/design-desktop-python-runtime.md`](../../docs/design-desktop-python-runtime.md).

Every script resolves its own paths (via `$0`), so you can invoke it from
anywhere. If your shell is *inside* this folder, prefix with `./` — the folder
isn't on `PATH`.

---

## Two channels, one sidecar

This is the thing the folder gets confusing about, so read it first. Bristlenose
ships to Macs **two separate ways**, with different signing, different
verification, and almost no shared tooling above the sidecar:

| | **App Store / TestFlight** | **Developer-ID `.dmg`** |
|---|---|---|
| Artefact | `.pkg`, uploaded to App Store Connect | `.dmg`, downloaded from bristlenose.app |
| Signed with | Apple Distribution | Developer ID Application |
| Validated by | App Store Connect, server-side | Apple's notary service, then Gatekeeper on the user's Mac |
| Entry point | `build-all.sh` | `build-dmg.sh` → `upload-dmg.sh` |
| Lifespan | permanent | **expires 30 days after the cut** |
| Who it's for | the commercial channel | a disposable sampler for people who bounce off TestFlight |

**They share the sidecar and nothing else.** `build-sidecar.sh`,
`sign-sidecar.sh`, `fetch-ffmpeg.sh` and friends feed both. Every other script
belongs to exactly one channel — or to neither.

**`build-all.sh` does NOT cut the `.dmg`, and `build-dmg.sh` does NOT produce
anything App Store Connect will accept.** Running the wrong one is the single
easiest mistake here.

---

## How to use

### Ship a TestFlight build

```bash
./desktop/scripts/build-all.sh
```

Needs an Apple Distribution identity and notarytool credentials. Runs the whole
chain and bails on any non-zero exit: pre-flight → ffmpeg + sidecar (parallel) →
signing → `xcodebuild archive` → export → release gates → notarise + staple.

### Cut and publish a `.dmg`

```bash
./desktop/scripts/build-dmg.sh                    # ~40 min + two notary waits
./desktop/scripts/upload-dmg.sh --dry-run         # probes the host, changes nothing
./desktop/scripts/upload-dmg.sh                   # publishes
```

`--dry-run` is worth running every time: it checks ssh, the target directory,
remote `shasum`, free space, and shows you exactly what would change — before
you commit to a ten-minute upload. Configure the target once in a gitignored
`desktop/scripts/.ship-local.conf`:

```bash
BRISTLENOSE_DMG_REMOTE="host:/path/to/site/dmg"
```

Then deploy the website so the docs match the build. The download link is a
permalink that redirects to the versioned file — see
[`docs/design-dmg-build.md`](../../docs/design-dmg-build.md) § Publishing.

### Rebuild the sidecar for local QA

```bash
(cd frontend && npm run build)                       # build-sidecar bundles this, doesn't build it
./desktop/scripts/build-sidecar.sh                   # → desktop/Bristlenose/Resources/bristlenose-sidecar/
SIGN_IDENTITY=- ./desktop/scripts/sign-sidecar.sh    # "-" = ad-hoc; fine locally
# then in Xcode: "Bristlenose" scheme → Shift+Cmd+K → Cmd+R
```

The clean is load-bearing — *Copy Sidecar Resources* may not re-embed a fresh
bundle on an incremental build. For pure backend/frontend iteration the
**Bristlenose (Dev Sidecar)** / **(External Server)** schemes skip the bundle
entirely (`desktop/CLAUDE.md` § Dev workflow).

### Clear a wedged sandbox

```bash
./desktop/scripts/reset-sandbox-state.sh
```

### Run the cheap tests

```bash
./desktop/scripts/test-ensure-sidecar.sh
./desktop/scripts/test-upload-dmg.sh
```

Seconds each, no network, no build. Run them after touching the build gating or
the publish path.

---

## Shared foundation — feeds both channels

| Script | What it does | When it runs |
|---|---|---|
| `build-sidecar.sh` | PyInstaller `--onedir` of `bristlenose serve` → `Resources/bristlenose-sidecar/`. Per-layer incremental; `--force` (used by releases) recreates `.venv-sidecar` from scratch so the dep closure is clean. | build-all step 2, build-dmg step 2, or manual |
| `ensure-sidecar.sh` | Orchestrates build + sign + deep-verify; the Xcode *Ensure Sidecar Fresh* phase calls this so a plain Cmd+R self-heals a stale bundle. | Xcode build phase, or manual |
| `sign-sidecar.sh` | Code-signs every Mach-O (240+) in the bundle, leaf-first, via a `wait -n` pool (not `xargs -P` — BSD `xargs` drops child exit codes). | build-all step 4, build-dmg step 2 |
| `fetch-ffmpeg.sh` | Downloads pinned-SHA256 static `ffmpeg` + `ffprobe` (arm64) into `Resources/`. Gitignored output — doesn't follow worktrees. | build-all step 2, or once per worktree |
| `sign-ffmpeg.sh` | Signs the bundled `ffmpeg` + `ffprobe` (separate from the sidecar: single Mach-O, no entitlements). | build-all step 3 |
| `generate-build-info.sh` | Writes `GeneratedBuildInfo.swift` (gitignored) from git state, for the in-app Build Info diagnostic. | Xcode Run Script phase, pre-Compile |
| `sidecar-source-hash.sh` | Sourced library — the fingerprint recipe driving incremental rebuilds. Not run directly. | sourced |
| `check-bundle-manifest.sh [root]` | Every runtime-data dir under `bristlenose/` is covered by a `datas` entry in the spec — catches "in source, missing from bundle" *before* the 3-min build. | 0 clean · 1 uncovered · 2 usage |
| `check-sidecar-freshness.sh` | Fails the Xcode build if the bundle predates a Python/frontend/locale edit. | Xcode build phase |
| `check-sidecar-appstore-strings.sh` | Decompresses the PYZ and scans code-object constants for App Store §2.5.2 blockers (`itms-services`, frozen in by CPython). Invisible to `grep`/`strings`. **Always call the `.sh`, never the `.py`** — the wrapper probes for PyInstaller and falls back `.venv-sidecar` → `.venv`; a raw `.py` call under a broken venv exits 1 from an uncaught `ImportError`, which looks exactly like a real detection. | build-all step 2c |
| `check-sidecar-appstore-strings.py` | The implementation behind the wrapper above. Not called directly. | — |

> **`build-sidecar.sh` needs the frontend pre-built.** It bundles
> `bristlenose/server/static/` but does not run `npm run build`. Missing → PyInstaller
> fails with `Unable to find '.../bristlenose/server/static'`.
>
> **Prereq:** `python3.12` on `PATH` (`brew install python@3.12`).

---

## App Store / TestFlight only

| Script | What it does | Exit |
|---|---|---|
| `build-all.sh` | The whole `.pkg` chain, Apple-Distribution-signed. Bails on any non-zero exit. | — |
| `check-release-binary.sh <archive\|app\|binary>` | No dev escape-hatch literals (`BRISTLENOSE_DEV_*`) survive in the **Release** Mach-O — they live under `#if DEBUG`, so a Release compile must exclude them. | 0 clean · 1 leak |
| `check-logging-hygiene.sh [root]` | No Swift `Logger` interpolates a credential-shaped identifier without a `privacy:` marker, and no `print()` dumps env. | 0 clean · non-0 violation |
| `check-appearance-seam.sh` | The light/dark mapping isn't re-derived outside `AppAppearance.swift`, panels call `adoptHostAppearance()`, and `AppDelegate` still calls `beginApplying()`. | 0 clean · non-0 violation |
| `build-mcpb.sh` / `check-mcpb.sh` | Builds and gates the `.mcpb` agent extension bundled into the app. | — |

---

## Developer-ID `.dmg` only

| Script | What it does | Exit |
|---|---|---|
| `build-dmg.sh` | The 10-stage cut: sidecar → archive → export as Developer ID → verify → notarise + staple the `.app` → `create-dmg` → notarise + staple the `.dmg` → manifest → gates. | — |
| `check-dmg-shippable.sh <dmg>` | Is this safe to hand a stranger? Versioned filename; image signed, stapled, Gatekeeper-accepted; and — the load-bearing one — the app **inside the mounted image** is stapled and assessed `source=Notarized Developer ID`. Plus filename↔`Info.plist` version agreement and a manifest↔image sha256 check. **Call it as a precondition, not a step someone can skip.** | 0 shippable · 1 not · 2 usage |
| `upload-dmg.sh [--dry-run] [--keep N]` | Publishes: gates, stages to a dot-prefixed name **in the target dir** (so `mv` stays atomic), verifies the sha256 of what landed, `chmod 644`, swaps, repoints the permalink by redirect, reaps all but the newest N. Skips the transfer if identical bytes are already on the host. | 0 published · 1 failed · 2 not configured |

> The `.dmg` expires **30 days from its build date**, not from upload — sitting on
> a cut costs its shelf life. `check-dmg-shippable.sh` warns below 21 days.

---

## Not a shipping path

| File | What it's for |
|---|---|
| `reset-sandbox-state.sh` | Clears stale App-Sandbox container state that wedges `libsecinit` on launch (symptom: `EXC_BREAKPOINT` in `_libsecinit_appsandbox.cold.*`). Flags: `--quiet`, `--dry-run`. macOS only. |
| `reset-app-state.sh` | "Clean-ish profile" reset for UX walkthroughs; calls the above. |
| `test-ensure-sidecar.sh` | Invariant tests for the build gating + orchestrator decisions, via `--dry-run` and controlled stamp state. |
| `test-upload-dmg.sh` | Invariant tests for the publish path — the swap decision (incl. empty-vs-empty, where a bare equality test reads two *failed measurements* as a match), retention, the unconfigured refusal, and the shippability gate proven against a real notarised artefact. |
| `report.sh` | Sourced library — the event emitters every build script uses. Not run directly. |
| `build_report.py` | The Rich renderer that consumes those events. Not run directly. |
| `build_report_mock.py` | Renders sample output for iterating on the report style. |
| `REPORT-STYLE.md` | The shared CLI report style + event protocol. |
| `bundle-manifest-allowlist.md` | Allowlist consumed by `check-bundle-manifest.sh`. |
| `logging-hygiene-allowlist.md` | Allowlist for `check-logging-hygiene.sh` — add `<!-- ci-allowlist: HYG-<N> -->` + justification. |

> ⚠️ **The reset scripts destroy data on *sandboxed* builds.** The container holds
> `projects.json`, `consentLog` (the AI-disclosure audit trail — Apple 5.1.2(i)),
> and `aiConsentVersion`. Snapshot them first if they matter. Unsandboxed Debug
> builds keep their data elsewhere and are untouched.

---

## `SIGN_IDENTITY`

Both signing scripts read it:

- `-` (default) — ad-hoc. Satisfies Hardened Runtime on the signing machine so
  the bundle runs locally; **not** distributable.
- `"Apple Distribution: …"` — TestFlight / App Store.
- `"Developer ID Application: …"` — the `.dmg` channel (`build-dmg.sh` sets this
  itself; notarisation requires a real Developer ID cert, so there is no ad-hoc
  fallback there).

`TIMESTAMP_FLAG` follows suit: a real Apple TSA timestamp for a real identity,
`--timestamp=none` for ad-hoc.

---

## See also

- [`REPORT-STYLE.md`](REPORT-STYLE.md) — the shared CLI report style + event
  protocol every script here follows, so the output reads as one system
- [`desktop/CLAUDE.md`](../CLAUDE.md) — desktop app + sidecar architecture, the
  three dev schemes, and the build/signing gotchas
- [`docs/design-dmg-build.md`](../../docs/design-dmg-build.md) — the `.dmg`
  channel: signing flow, notarisation failure modes, publishing model
- [`docs/design-desktop-python-runtime.md`](../../docs/design-desktop-python-runtime.md) —
  the bundled-sidecar shipping design
