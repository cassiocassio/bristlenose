# Desktop Python Runtime — sidecar mechanics

_Written 18 Apr 2026 as Track C C0 spike output; updated the same day with the C1 resolver contract. Covers entitlements, signing, bundling, and runtime resource resolution for the bundled PyInstaller sidecar on macOS. Cross-channel component decisions (what ships where, and why) live in [`design-modularity.md`](./design-modularity.md) — this doc is strictly Mac-specific mechanics._

## Scope

This doc is the canonical source for:

- Which Hardened Runtime entitlements the sidecar needs and why
- How the sidecar is laid out inside `Bristlenose.app/Contents/Resources/`
- How Swift spawns and supervises it (ServeManager contract)
- How resources (FFmpeg, Whisper models, credentials) are located at runtime
- How codesigning is layered (inner `.dylib`/`.so` → outer binary → outer `.app`)

It is **not** the implementation plan — the C1 implementation work was tracked in `docs/private/sprint2-tracks.md` (now marked done) and `~/.claude/plans/when-you-have-done-encapsulated-conway.md`.

## Status (C2, 19 Apr 2026)

- ✅ Trimmed PyInstaller spec at `desktop/bristlenose-sidecar.spec` (MLX-only; ctranslate2 / faster-whisper / presidio / spaCy excluded).
- ✅ Sidecar builds, real-identity codesigns with Hardened Runtime, serves HTTP on localhost under `bristlenose serve`.
- ✅ Minimum entitlement set empirically confirmed: **one key only** (`cs.disable-library-validation`). Empty-entitlements re-test post-unified-identity signing is parked; see `docs/private/c2-session-notes.md` Goal 2.
- ✅ **Sidecar resolution** refactored to pure `SidecarMode.resolve(…)` (C1).
- ✅ **Parallel per-Mach-O signing** via bash `wait -n` pool, SHA256 manifest, trusted-timestamp assertion per file (C2).
- ✅ **ExportOptions.plist + pbxproj Manual signing** — Release flipped to Apple Distribution + Bristlenose Mac App Store profile + Team `Z56GZVA2QB`; Debug stays Automatic (C2).
- ✅ **Notarisation + stapling flow** wired in `build-all.sh` (C2). Notarytool credentials: profile `bristlenose-notary` in login keychain.
- ✅ **Strings gate + `get-task-allow` gate** on every archived Mach-O (`check-release-binary.sh`, C2).
- 🟡 **End-to-end verification blocked** (19 Apr 2026) by pre-existing `#error` directives in `desktop/Bristlenose/Bristlenose/SecurityChecklist.swift` (SECURITY #5 + #8 — unrelated to signing). Unblocks both C2 verification and C3.
- ⏸️ Bundle size 644 MB. Deferred to Background Assets. See §"Bundle-size findings".
- ❌ `com.apple.security.inherit` not yet tested (App Sandbox is Track A).

## Entitlement table

Each row: what the sidecar requests, which dependency forces it, and how to justify it to App Review.

| Key | Status | Triggered by | App Review justification |
|---|---|---|---|
| `com.apple.security.cs.disable-library-validation` | **Required** | PyInstaller bundle: ad-hoc signed outer binary loads `Python.framework` and 100+ `.so` files with a different (or empty) Team ID. Library validation rejects with "mapping process and mapped file have different Team IDs". | "Our app bundles a Python runtime (CPython 3.12) and its C-extension dependencies. These binaries are signed at build time by our own signing pipeline with our team identifier, but dyld's library validation check fires because CPython's internal layering treats the framework as a separately signed object. Disabling library validation is the standard pattern for embedded-Python apps on macOS; our own signing step ensures every loaded binary is trusted by us." |
| `com.apple.security.cs.allow-unsigned-executable-memory` | ❌ Not needed | Would be required if Python used W+X pages, but CPython 3.12 and the modules we ship don't. Included in v0.1's spec defensively; empirically unnecessary. | — (don't request) |
| `com.apple.security.cs.allow-jit` | ❌ Not needed | Would be required if ctranslate2 / faster-whisper were in the bundle (they emit CPU JIT). Both are excluded; MLX runs on Metal GPU kernels. | — (don't request) |
| `com.apple.security.cs.allow-dyld-environment-variables` | ❌ Not needed | PyInstaller `--onedir` bundles don't need `DYLD_*` tweaks; rpath is embedded by the installer. | — (don't request) |
| `com.apple.security.cs.debugger` | ❌ Not needed | Only useful for attaching debuggers; shipping code doesn't need it. | — (don't request) |
| `com.apple.security.inherit` | ⬜ Future (Track A) | Required once the parent `.app` enables App Sandbox, so the sidecar inherits the parent's sandbox rather than being evaluated standalone. | "The sidecar runs as a child of the sandboxed parent process. Inheriting the parent's sandbox is the standard pattern for a non-UI helper binary; the sidecar requests no additional entitlements of its own." |

**Summary.** Track C C0 reduces the expected entitlement footprint from road-to-alpha §5's three-item guess (`allow-unsigned-executable-memory`, `disable-library-validation`, `allow-jit`) to a **single entitlement**. Each removed key is one fewer line of justification at App Review.

### How this was determined

Test rig: `desktop/scripts/build-sidecar.sh` produces a `--onedir` PyInstaller bundle, signs it (default ad-hoc for local iteration; `SIGN_IDENTITY="Apple Distribution: …"` for TestFlight) with `codesign --force --options=runtime --entitlements …`, and runs it as `./bristlenose-sidecar --port 18150 --no-open /tmp/scratch`.

Four signing runs:

| Entitlements | Outcome |
|---|---|
| `cs.disable-library-validation` + `cs.allow-unsigned-executable-memory` (v0.1 set) | HTTP 404 on `/` at t=1s — alive |
| `cs.allow-unsigned-executable-memory` only | HTTP 404 at t=1s — alive (library validation didn't fire despite entitlement absent, but this turned out to be because we hadn't first `--remove-signature`'d the outer binary; the inner re-signs still had full entitlements from the previous run. After `codesign --remove-signature` + re-sign, this config DIES at load with "different Team IDs") |
| `cs.disable-library-validation` only | HTTP 404 at t=2s — alive |
| Empty `<dict/>` | `[PYI-XXXX:ERROR] Failed to load Python shared library … code signature … not valid for use in process: mapping process and mapped file (non-platform) have different Team IDs` |

Clean outcome: `cs.disable-library-validation` is the only load-bearing key.

### What wasn't tested

- **App Sandbox.** Hardened Runtime fires without the sandbox; the sandbox only engages when the parent `.app` opts in. Track A will re-exercise the MVP flow with sandbox on and enumerate file/network/bookmark entitlements from Console `deny(1) …` entries.
- **Grandchildren.** FFmpeg launched by Python launched by Swift — signed separately per C2; their entitlement requirements will be audited when the trimmed FFmpeg build lands.
- **Actual transcription.** The spike exercised `bristlenose serve` only — DB init, static routing, auth middleware. MLX inference was not run. If mlx-whisper turns out to need an extra key at model-load time, it'll surface in C1 when the integration test harness runs a real 10 s clip through.

## Spike bundle layout

The sidecar bundle builds into `desktop/Bristlenose/Resources/bristlenose-sidecar/` (gitignored). Xcode's "Copy Sidecar Resources" build phase stages it into `Bristlenose.app/Contents/Resources/bristlenose-sidecar/`. Shape:

```
bristlenose-sidecar/
├── bristlenose-sidecar       (the outer Mach-O, 5 MB)
└── _internal/
    ├── Python                (dyld stub → Python.framework)
    ├── Python.framework/     (CPython 3.12 runtime)
    ├── base_library.zip      (pure-Python stdlib frozen)
    ├── torch/                (288 MB — transitive; Background Assets candidate)
    ├── llvmlite/             (110 MB — transitive; Background Assets candidate)
    ├── onnxruntime/          (58 MB — transitive; Background Assets candidate)
    ├── mlx/                  (24 MB — ours)
    ├── scipy/                (37 MB — transitive; Background Assets candidate)
    ├── bristlenose/          (theme, data, locales, server/alembic)
    └── … every signed .so and .dylib
```

The flat `_internal/` layout is PyInstaller `--onedir`. Swift finds the outer binary at a fixed path; dyld resolves everything inside `_internal/` via embedded rpath.

## Bundle-size findings (deferred to Background Assets)

C0 bundle: **644 MB**. Transitive deps PyInstaller pulled despite the `excludes`:

| Package | Size | Likely hop |
|---|---|---|
| `torch` | 288 MB | Via `tiktoken` → `transformers` legacy tokenizers |
| `llvmlite` | 110 MB | Via `numba` → audio preprocessing dep |
| `onnxruntime` | 58 MB | Via `tokenizers` / `huggingface_hub` optional paths |
| `scipy` | 37 MB | Via librosa / audio feature extraction |

**C1 decision (18 Apr 2026): size optimisation deferred.** Per `design-modularity.md` §"Acquisition strategy: trickle to full capability", the alpha story is Apple Background Assets — Whisper models and large optional deps trickle in post-install (Wi-Fi-opportunistic, Apple-hosted, OS-scheduled) rather than bloating the initial `.app` download. Build-time trimming before that story lands would be premature optimisation.

What we ship in the alpha: whatever the trimmed-by-explicit-excludes-only spec produces. Size is a soft constraint when the user's install flow is "tap install in TestFlight, app opens, heavy bits download in the background while they pick their first project." Track C C5 (post-alpha) may revisit excludes if TestFlight reports cite bundle size as a friction point; more likely the work moves straight to Background Assets integration.

## Bundling gotchas discovered

1. **Alembic migrations directory must be explicitly listed in `datas`.** `bristlenose/server/alembic/` is a filesystem resource read by Alembic's `ScriptDirectory.from_config`; PyInstaller doesn't detect it through `bristlenose.server.db`'s imports. Without it: `CommandError: Path doesn't exist: …/_internal/bristlenose/server/alembic` at first DB init. Added to the spec.
2. **Locales directory same story** — `bristlenose/locales/*.json` is read as data, not imported. Added to `datas`.
3. **React static bundle must be pre-built.** The sidecar runs without `bristlenose/server/static/` but emits a WARNING log line. Still unresolved in C1 — `desktop/scripts/build-sidecar.sh` does not yet invoke `npm run build` before PyInstaller. Slated for C2 / the build-all orchestration script.
4. **`--host` is not a `bristlenose serve` option.** The server hardcodes `127.0.0.1`. Fine for sidecar-over-localhost; document if we ever need to bind elsewhere (probably never).
5. **Sentiment framework YAML not found** warning at startup — cosmetic; the YAML is optional user config.
6. **Sidecar ignores `BRISTLENOSE_AUTH_TOKEN` env var** — the server always generates a fresh per-run token. If Swift wants to know the token, it has to either read stdout (current pattern) or we add env-var plumbing in C1. Defer.

## SidecarMode resolution contract (C1 output)

`ServeManager` no longer searches the filesystem for a `bristlenose` binary. Mode is decided once at init by `SidecarMode.resolve(externalPortRaw:sidecarPathRaw:bundleResourceURL:fileManager:)` — a pure function in `desktop/Bristlenose/Bristlenose/SidecarMode.swift` — returning one of:

- `.bundled(path:)` — `Bundle.main.resourceURL/bristlenose-sidecar/bristlenose-sidecar`. What TestFlight ships.
- `.devSidecar(path:)` — a dev-specified binary (Debug-only, via `BRISTLENOSE_DEV_SIDECAR_PATH`).
- `.external(port:)` — an externally-running `bristlenose serve` on localhost (Debug-only, via `BRISTLENOSE_DEV_EXTERNAL_PORT`).

Both dev env vars are read only inside `#if DEBUG` guards in `ServeManager.init`; in Release, the resolver receives `nil`/`nil` and can only return `.bundled`. `desktop/scripts/check-release-binary.sh` asserts the env-var string literals are absent from the Release Mach-O — a refactor that moves a read outside `#if DEBUG` fails the gate rather than silently shipping.

Three Xcode shared schemes wrap the env vars so developers see the choice in the Run-button dropdown:

| Scheme | Env var set | Mode |
|---|---|---|
| Bristlenose | _(none)_ | `.bundled` |
| Bristlenose (Dev Sidecar) | `BRISTLENOSE_DEV_SIDECAR_PATH` | `.devSidecar` |
| Bristlenose (External Server) | `BRISTLENOSE_DEV_EXTERNAL_PORT` | `.external` |

Both env vars set at once → `SidecarResolveError.bothDevEnvVarsSet` → `.failed` state at init (no fatalError; the app renders a SwiftUI error card via `LocalizedError.errorDescription`).

## Signing strategy (C2, 19 Apr 2026)

Four-script chain, orchestrated by `desktop/scripts/build-all.sh`:

- `build-sidecar.sh` — PyInstaller `--onedir` only.
- `sign-sidecar.sh` — parallel inner-Mach-O sign, sequential outer sign, strict + deep verify, SHA256 manifest. Inner loop is a bash `wait -n` job pool, not `xargs -P`: BSD `xargs` on macOS drops child exit codes under concurrent jobs, so a single failed codesign would be masked in interleaved stderr.
- `fetch-ffmpeg.sh` — SHA256-pinned FFmpeg 8.1 download. Cache under `desktop/build/ffmpeg-cache/`.
- `sign-ffmpeg.sh` — signs the two FFmpeg siblings with the same identity and Hardened Runtime. Notarisation rejects the outer bundle otherwise.

`SIGN_IDENTITY` defaults to `-` (ad-hoc). For release: `"Apple Distribution: Martin Storey (Z56GZVA2QB)"`. `SIGN_JOBS` defaults to `$(sysctl -n hw.ncpu)`; override if Keychain contention matters at `SIGN_JOBS≥16`.

Ordering: inner `.dylib`/`.so` first and in parallel, then outer `bristlenose-sidecar`, then outer `.app` via `xcodebuild archive`. Every codesign call uses `--options=runtime`. Timestamps come from Apple's TSA per-binary via `--timestamp`.

Inner Mach-Os do **not** receive `--entitlements`. The kernel ignores inner entitlements for Hardened Runtime; passing the flag on every binary cluttered `codesign -d` audit output with DLV-granted noise on 240 dylibs.

Output manifest (`desktop/build/sign-manifest.json`): path + SHA256 + identity + UTC timestamp per signed Mach-O. C2's sliver of the SBOM story (full CycloneDX is C5).

### One-time Mac setup before signing works silently

**Partition list ACL.** `codesign`'s Keychain access races against "Always Allow" when run in parallel — `SIGN_JOBS=12` can trigger twelve prompts. The canonical fix (every CI uses this):

```bash
security set-key-partition-list -S apple-tool:,apple: -s ~/Library/Keychains/login.keychain-db
```

Prompts once for the login password, then all Apple-signed tools (including `codesign`) can use signing keys without further GUI prompts. Re-run if the cert is rotated or reinstalled. On a single-user dev Mac this is the documented indie pattern; a dedicated `build.keychain` is the CI/shared-machine equivalent (post-alpha refactor).

**Note on output:** the command above dumps metadata for every signing key it touches (one `keychain: …` block per key). That's expected, not an error.

### Timestamp assertion (guards against silent TSA failure)

After every successful `codesign --sign`, `sign-sidecar.sh` and `sign-ffmpeg.sh` assert `codesign -dvv | grep "Timestamp="`. If the Apple TSA is unreachable, `codesign` succeeds silently with `--timestamp=none` — producing an un-notarisable signature that would surface as a notarisation failure hours later. The assertion fails fast.

Implementation gotcha: `codesign -dvv | grep -q` trips `pipefail` via SIGPIPE. `grep -q` exits on first match, `codesign` keeps writing, gets SIGPIPE, returns 141. Pipeline is non-zero → false "no timestamp" alarm. The scripts capture codesign output into a variable first, then grep the here-string.

### Notarisation + stapling

`build-all.sh` steps 9–10:

1. `ditto -c -k --sequesterRsrc --keepParent <app> <app>.zip` — **never** plain `zip`, which mangles xattrs and symlinks inside `.app`.
2. `xcrun notarytool submit <zip> --keychain-profile bristlenose-notary --wait --output-format plist` — captures submission UUID from `:id`.
3. `xcrun notarytool log <UUID> --keychain-profile bristlenose-notary <log.json>` — assert `status == "Accepted"` explicitly. Don't trust `notarytool history` — it can show cached prior runs.
4. `xcrun stapler staple <app>`.

Credentials live as a `bristlenose-notary` profile in the login keychain. One-time setup:

```bash
xcrun notarytool store-credentials "bristlenose-notary" \
  --apple-id martin_storey@mac.com \
  --team-id Z56GZVA2QB \
  --password <app-specific-password>
```

App-specific password generated at [appleid.apple.com](https://appleid.apple.com) — revocable and regeneratable; no need to save outside the keychain.

**Deferred.** App Store Connect API key (`.p8` + key ID + issuer ID) is more scopeable and audit-friendly than Apple-ID + app-specific password. Parked in qa-backlog for post-alpha — the ASP path is simpler for alpha-1.

### Final verification battery (`build-all.sh` step 10)

Run after `stapler staple`:

- `xcrun stapler validate <app>` — ticket present and valid.
- `spctl -a -t exec -vv <app>` — Gatekeeper accepts; "source=Notarized Developer ID" is the expected phrase for Apple Distribution–signed chains.
- `codesign --verify --deep --strict --verbose=2 <app>` — seals match through every nested Mach-O.
- `codesign -d --entitlements :- <outer>` — assert **no** `get-task-allow=TRUE` (Debug debuggability entitlement, silently App-Store-rejected).
- `codesign -d --requirements - <outer>` — assert designated requirement includes Team ID `Z56GZVA2QB`.

### Pre-archive gate (`check-release-binary.sh`)

Scans every Mach-O in the archived/exported `.app` for two Release-forbidden conditions:

1. `BRISTLENOSE_DEV_*` string literals — the Debug-only dev escape-hatch env vars. A Release build that references them means a `#if DEBUG` guard was accidentally removed.
2. `get-task-allow=TRUE` entitlement — Debug-only debuggability.

Skips `Contents/Resources/bristlenose-sidecar/*` (Python strings expected; no Swift `#if DEBUG` invariant applies). Wired into `build-all.sh` post-export (not as an Xcode Run Script phase — merge-hostile pbxproj pollution, and the build-all script is the canonical release path anyway).

### `get-task-allow` "<false/>" entries

Xcode sometimes emits `<key>get-task-allow</key><false/>` in the entitlements dict (rather than omitting the key). That's fine — the check in `check-release-binary.sh` only fires on `<true/>`.

## Resource resolution (forward reference)

Per `design-modularity.md`, single-source lookup functions live in the Python code. For the sidecar path specifically:

- **FFmpeg** — Swift reads `Bundle.main.resourceURL/bin/ffmpeg`, passes via `BRISTLENOSE_FFMPEG_PATH` env var. Python `find_binary("ffmpeg")` checks env → `shutil.which`. (CLI users skip the env var, fall through to `which`.)
- **Whisper models** — env var `BRISTLENOSE_WHISPER_MODEL_DIR` → `~/Library/Application Support/Bristlenose/models/` → HuggingFace cache. Background Assets writes to Application Support in public beta; alpha bundles the `small.en` model directly.
- **Credentials** — Swift reads Keychain (via Security framework), passes per-provider env vars (`BRISTLENOSE_ANTHROPIC_KEY`, etc.). No Mac-specific Python dep.
- **Auth token** — server prints once at startup; Swift greps the token out of the sidecar's stdout. C1 may add structured-stdout (JSON line for handshake) if scraping proves fragile.

All four patterns are "Swift resolves via platform API, passes via env var, Python reads env." That's the no-fork principle from `design-modularity.md`.

## Failure modes observed during C0

- Without `cs.disable-library-validation`: Python.framework fails to dlopen; `[PYI-XXXX:ERROR] Failed to load Python shared library`. Exit code 0 (PyInstaller swallows). Silent failure on the Swift side unless it polls health.
- Alembic path missing: `CommandError` at first DB init, process exits 0 with a Rich traceback on stderr. Caught by `datas` fix.
- Sidecar up but on the wrong port: HTTP connection refused from Swift, no error from sidecar. C1 shipped the `ServeManager.handleLine` "Report: http://…" readiness parser with a generation-guarded port-poll before state transitions to `.running`.

## Open questions (C2 onwards)

- **What extra entitlements does App Sandbox need?** Track A's violation log will tell us. The sidecar itself only needs `inherit`; all user-facing entitlements (files, network, bookmarks) go on the parent `.app`.
- **Does mlx_whisper need any runtime-allow keys?** Not observed in C0 (no inference run). Surface in C2 integration test.
- **What happens when the user's Mac has no Metal GPU support** (e.g. x86_64 Mac running Rosetta on the arm64 sidecar)? The sidecar is `target_arch="arm64"`; Rosetta shouldn't apply. Still worth a compatibility matrix.

## Cross-references

- [`docs/design-modularity.md`](./design-modularity.md) — what gets bundled
- [`docs/private/sprint2-tracks.md`](./private/sprint2-tracks.md) — Track C C0–C5
- [`docs/private/road-to-alpha.md`](./private/road-to-alpha.md) §3, §4, §5 — sandbox, signing, Hardened Runtime checkpoints
- [`desktop/bristlenose-sidecar.spec`](../desktop/bristlenose-sidecar.spec), [`desktop/bristlenose-sidecar.entitlements`](../desktop/bristlenose-sidecar.entitlements), [`desktop/sidecar_entry.py`](../desktop/sidecar_entry.py) — sidecar packaging
- [`desktop/scripts/build-all.sh`](../desktop/scripts/build-all.sh) — C2 end-to-end orchestrator
- [`desktop/scripts/build-sidecar.sh`](../desktop/scripts/build-sidecar.sh), [`desktop/scripts/sign-sidecar.sh`](../desktop/scripts/sign-sidecar.sh), [`desktop/scripts/fetch-ffmpeg.sh`](../desktop/scripts/fetch-ffmpeg.sh), [`desktop/scripts/sign-ffmpeg.sh`](../desktop/scripts/sign-ffmpeg.sh) — C2 build + sign chain
- [`desktop/scripts/check-release-binary.sh`](../desktop/scripts/check-release-binary.sh) — post-archive gate (strings + `get-task-allow`)
- [`desktop/Bristlenose/ExportOptions.plist`](../desktop/Bristlenose/ExportOptions.plist) — `xcodebuild -exportArchive` options
- [`desktop/Bristlenose/Bristlenose/SidecarMode.swift`](../desktop/Bristlenose/Bristlenose/SidecarMode.swift) — mode resolution contract
- [`desktop/v0.1-archive/bristlenose-sidecar.spec`](../desktop/v0.1-archive/bristlenose-sidecar.spec) — prior art
- [`docs/private/c2-session-notes.md`](./private/c2-session-notes.md) — C2 session notes, gotchas, resume-cold guide
