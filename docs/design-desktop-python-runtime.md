# Desktop Python Runtime — sidecar mechanics

_Written 18 Apr 2026 as Track C C0 spike output; updated through C3 (21 Apr 2026) with post-smoke-test bundle-data requirements, validation gates, and fail-loud contracts. Trued 28 Apr 2026 against the empty-ents retest (RED), the App-Store-flow `build-all.sh` end-to-end fixes, and the App-Store-only / Developer-ID-deferred distribution decision. Covers entitlements, signing, bundling, and runtime resource resolution for the bundled PyInstaller sidecar on macOS. Cross-channel component decisions (what ships where, and why) live in [`design-modularity.md`](./design-modularity.md) — this doc is strictly Mac-specific mechanics._

> **Trued 28 Apr 2026 against `sidecar-signing` HEAD `8cfd2ee`.** Status block, entitlement-table justification, and verification battery updated to reflect: empty-ents retest result (RED — Python.framework's nested `_CodeSignature/` seal is the empirical reason DLV stays); `build-all.sh` end-to-end working for App Store flow (Mac Installer Distribution cert added; notarisation + stapling + spctl correctly skipped because notarytool only accepts Developer ID); SECURITY #5/#8 unblocker shipped; libproc-only zombie cleanup. New §"App Store distribution flow" section. §"Notarisation + stapling" preserved verbatim under a "Deferred — Developer ID flow" header (revisit at ~10k paying users per memory `project_developer_id_revisit.md`).

## Scope

This doc is the canonical source for:

- Which Hardened Runtime entitlements the sidecar needs and why
- How the sidecar is laid out inside `Bristlenose.app/Contents/Resources/`
- How Swift spawns and supervises it (ServeManager contract)
- How resources (FFmpeg, Whisper models, credentials) are located at runtime
- How codesigning is layered (inner `.dylib`/`.so` → outer binary → outer `.app`)

It is **not** the implementation plan — per-checkpoint work was tracked in `docs/private/sprint2-tracks.md` and session-specific `~/.claude/plans/*.md` files (C1 implementation plan, C3 closeout, C3 empty-ents retest, C4 privacy manifests). Session notes for the finished tracks live in `docs/private/c2-session-notes.md` and `docs/private/c3-session-notes.md`.

## Status (C2–C3 + post-C3 hardening, 28 Apr 2026)

- ✅ Trimmed PyInstaller spec at `desktop/bristlenose-sidecar.spec` (MLX-only; ctranslate2 / faster-whisper / presidio / spaCy excluded).
- ✅ Sidecar builds, real-identity codesigns with Hardened Runtime, serves HTTP on localhost under `bristlenose serve`.
- ✅ **Minimum entitlement set empirically confirmed:** one key only (`cs.disable-library-validation`). Empty-entitlements retest ran 28 Apr 2026 — RED. PyInstaller's bundled `Python.framework/Versions/3.12/Python` carries an internal `_CodeSignature/` seal distinct from the per-binary signatures applied by `sign-sidecar.sh`. AMFI reads the framework's nested seal at dlopen, not the per-binary resign — so unified-identity signing across individual Mach-Os does not reach the framework's identifier. DLV stays. Path forward (parked): treat Python.framework as a unit with `codesign --force` on the directory itself, properly resealing the internal `_CodeSignature`. The empirical comment block in [`desktop/bristlenose-sidecar.entitlements`](../desktop/bristlenose-sidecar.entitlements) is the canonical record (commit `8cfd2ee`).
- ✅ **Sidecar resolution** refactored to pure `SidecarMode.resolve(…)` (C1).
- ✅ **Parallel per-Mach-O signing** via bash `wait -n` pool, SHA256 manifest, trusted-timestamp assertion per file (C2).
- ✅ **ExportOptions.plist + pbxproj Manual signing** — Release flipped to Apple Distribution + Bristlenose Mac App Store profile + Team `Z56GZVA2QB`; Debug stays Automatic (C2). `installerSigningCertificate` (`3rd Party Mac Developer Installer`) added 28 Apr (`1ee30eb`) to sign the `.pkg` wrapper; required for App Store upload.
- ✅ **`build-all.sh` end-to-end** for the App Store flow (28 Apr 2026, `1ee30eb`). See §"App Store distribution flow" below for the dual-cert ExportOptions, the xcarchive-`.app` fallback when `method=app-store` exports only a `.pkg`, and the `pkgutil --check-signature` replacement for `spctl`.
- ✅ **Strings gate + `get-task-allow` gate** on every archived Mach-O (`check-release-binary.sh`, C2).
- ✅ **Keychain credential flow** — Swift reads Keychain via `Security.framework` and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars at sidecar launch (C3). Python `credentials_macos.py` subprocess-exception broadened to cover sandbox-denied cases. Runtime log redactor + source-level `check-logging-hygiene.sh` CI gate for Anthropic/OpenAI/Google key shapes.
- ✅ **Bundle-data coverage** — BUG-3/4/5 fixed in C3 (React SPA `static/`, codebook YAMLs, llm/prompts all now hard-required in the spec). `check-bundle-manifest.sh` regression gate (BUG-6) added as `build-all.sh` pre-flight. `bristlenose doctor --self-test` gives the sidecar a runtime self-check path.
- ✅ **Fail-loud on missing React bundle** — `_mount_prod_report` returns HTTP 500 with a clear error page rather than silently falling back to the deprecated static-render HTML (which masked BUG-3 in the C3 smoke test).
- ✅ **SECURITY #5 + #8 unblocked** (26 Apr 2026, commits `823f9be` `fdf90dc` `92a1d36` `38808fe`). Both `SecurityChecklist.swift` `#error` directives gone; Release archives compile.
- ✅ **Zombie cleanup is libproc-only** (`5471b35`, 28 Apr 2026). `proc_listpids` + `proc_pidfdinfo(PROC_PIDFDSOCKETINFO)` replace the `lsof` exec; combined with the earlier `proc_pidpath` replacement for `/bin/ps` (`38808fe`), the entire supervisor path survives the Track A sandbox flip with no further changes.
- 🟡 **C3 smoke test (manual, Step 6)** parked for human — Xcode Cmd+R with a throwaway Anthropic key; procedure in `~/.claude/plans/c3-closeout.md`.
- ⏸️ Bundle size 644 MB. Deferred to Background Assets. See §"Bundle-size findings".
- ✅ **`com.apple.security.inherit`** verified end-to-end through Track A — A1 added the key (`cd4a5c6` on `sandbox-debug`), A1c confirmed the bundled sidecar spawns under inherited sandbox, A2 (`49cb600` on `track-a-a2-network-server`) confirmed FastAPI `bind()` on 127.0.0.1:9131 succeeds with the parent's `network.server` reaching the child via `inherit`. Sidecar requests no sandbox keys of its own.
- ✅ **Host App Sandbox set (Debug-only)** — empirical floor as of A2: `app-sandbox` + `network.client` (LLM HTTPS + Ollama localhost) + `network.server` (sidecar `bind()`) + `files.user-selected.read-write` (folder picker + bookmark XPC bootstrap). All four are build-setting-driven in `Bristlenose.xcodeproj/project.pbxproj` (`ENABLE_APP_SANDBOX`, `ENABLE_OUTGOING_NETWORK_CONNECTIONS`, `ENABLE_INCOMING_NETWORK_CONNECTIONS`, `ENABLE_USER_SELECTED_FILES`); no host `.entitlements` file. Release config keeps sandbox off pending the rest of Track A.
- 🟢 **Sandbox iteration helper** — `desktop/scripts/reset-sandbox-state.sh` (`ff96766` / `ff57801` / `730367d`). Wipes `~/Library/Containers/app.bristlenose/Data/*`, drops UserDefaults, kills zombies, frees ports. Required because stale Container state reproducibly trips `EXC_BREAKPOINT` in `_libsecinit_appsandbox.cold.*` between launches even when entitlements are correct. Documented in `desktop/CLAUDE.md` "Sandbox iteration" gotcha.

## Entitlement table

Each row: what the sidecar requests, which dependency forces it, and how to justify it to App Review.

| Key | Status | Triggered by | App Review justification |
|---|---|---|---|
| `com.apple.security.cs.disable-library-validation` | **Required** (empirically, 28 Apr 2026 retest) | PyInstaller's bundled `Python.framework/Versions/3.12/Python` carries an internal `_CodeSignature/` seal distinct from the per-binary signatures applied by `sign-sidecar.sh`. AMFI reads the framework's nested seal at dlopen, not the per-binary resign. Result: even after a full remove-then-resign cycle across all 240+1 inner+outer Mach-Os under one Apple Distribution identity (`Z56GZVA2QB`), the framework's `Python` binary is rejected with "mapping process and mapped file (non-platform) have different Team IDs". | "Our app bundles a Python runtime (CPython 3.12) inside Apple's Framework structure. We sign every Mach-O in the bundle — including every `.so`, every `.dylib`, FFmpeg, and the framework's own `Python` binary — with our Apple Distribution identity (Team ID `Z56GZVA2QB`). However, `Python.framework` carries an internal `_CodeSignature/` seal as part of the macOS framework convention, and AMFI's library-validation check at dlopen reads that nested seal rather than the per-binary signature. The framework's internal identifier does not match our Team ID, so dyld rejects the load. Disabling library validation is the standard pattern for embedded-Python apps on macOS — Apple Developer Support documents it explicitly. The mitigation is robust: every loaded binary is signed by us under one identity, our Hardened Runtime is otherwise enabled, App Sandbox (when Track A flips it on) constrains the process. Future work to drop this entitlement is `codesign --force` on the framework directory as a unit (parked; non-trivial — Apple's framework versioned-symlink layout is fussy)." |
| `com.apple.security.cs.allow-unsigned-executable-memory` | ❌ Not needed | Would be required if Python used W+X pages, but CPython 3.12 and the modules we ship don't. Included in v0.1's spec defensively; empirically unnecessary. | — (don't request) |
| `com.apple.security.cs.allow-jit` | ❌ Not needed | Would be required if ctranslate2 / faster-whisper were in the bundle (they emit CPU JIT). Both are excluded; MLX runs on Metal GPU kernels. | — (don't request) |
| `com.apple.security.cs.allow-dyld-environment-variables` | ❌ Not needed | PyInstaller `--onedir` bundles don't need `DYLD_*` tweaks; rpath is embedded by the installer. | — (don't request) |
| `com.apple.security.cs.debugger` | ❌ Not needed | Only useful for attaching debuggers; shipping code doesn't need it. | — (don't request) |
| `com.apple.security.inherit` (sidecar) | ✅ **Required** (verified Track A: A1 add `cd4a5c6`, A1c spawn, A2 bind `49cb600`) | Required once the parent `.app` enables App Sandbox, so the sidecar inherits the parent's sandbox rather than being evaluated standalone. | "The sidecar runs as a child of the sandboxed parent process. Inheriting the parent's sandbox is the standard pattern for a non-UI helper binary; the sidecar requests no additional entitlements of its own." |
| `com.apple.security.app-sandbox` (host, Debug-only) | ✅ **Required** (Track A baseline) | Top-level App Sandbox enable. Build-setting `ENABLE_APP_SANDBOX = YES` in Debug; Release stays NO pending Track A completion. | "Standard App Sandbox enable for the host UI process. Sidecar inherits this scope via `com.apple.security.inherit`." |
| `com.apple.security.network.client` (host, Debug-only) | ✅ **Required** (Track A baseline) | LLM provider HTTPS calls (Anthropic / OpenAI / Azure / Gemini) + Ollama localhost loopback probe. Build-setting `ENABLE_OUTGOING_NETWORK_CONNECTIONS = YES`. | "Outgoing connections to user-configured LLM provider APIs over HTTPS, and to user-installed Ollama on 127.0.0.1. No connections to Bristlenose-controlled servers." |
| `com.apple.security.network.server` (host, Debug-only) | ✅ **Required** (verified A2 `49cb600`, 1 May 2026) | The bundled sidecar runs `uvicorn.run(host="127.0.0.1", port=…)` for the local FastAPI report server. Without `network.server`, kernel logs `Sandbox: bristlenose-sidecar deny(1) network-bind local:*:9131` and the sidecar crashes at startup. Loopback-only — Python pins `host="127.0.0.1"`. Build-setting `ENABLE_INCOMING_NETWORK_CONNECTIONS = YES`. | "Bristlenose's local report viewer is a FastAPI server bound to 127.0.0.1 (loopback only — verified by `uvicorn.run(host=\"127.0.0.1\")` in `bristlenose/cli.py`). The host's WKWebView connects via `http://127.0.0.1:<port>/report/`. No external listening; no firewall surface. The entitlement is required because macOS's sandbox treats `bind()` as a server operation regardless of the bind address." |
| `com.apple.security.files.user-selected.read-write` (host, Debug-only) | ✅ **Required** (verified A1) | User-picked interview folders via `NSOpenPanel` and drag-and-drop; security-scoped bookmarks for re-launch persistence. Without it, A1 saw `Sandbox: Bristlenose deny(1) mach-lookup com.apple.scopedbookmarksagent.xpc` on first folder pick. Build-setting `ENABLE_USER_SELECTED_FILES = readwrite`. | "Researchers pick a folder of interview recordings via the standard macOS folder picker. The entitlement grants access to that user-selected folder only; we do not request broad disk access. Bookmarks let researchers re-open the project across launches without re-authorising." |

**Summary.** Track C C0 reduces the expected entitlement footprint from the original three-item guess (`allow-unsigned-executable-memory`, `disable-library-validation`, `allow-jit`) to a **single entitlement**. Each removed key is one fewer line of justification at App Review. The 28 Apr 2026 retest confirmed this is the empirical floor, not a defensive caveat — see the next subsection for the C0 four-run table that established the floor, and §"Why DLV survives unified-identity signing" below for the framework-nested-seal finding from the post-C2 retest.

### How this was determined (C0 spike, 18 Apr 2026 — historical baseline)

> **Status: superseded as a justification but retained as evidence.** The four-run table below was produced at C0 against an ad-hoc-signed bundle, before the C2 unified-identity sign chain existed. The clean outcome ("only DLV is load-bearing") was correct in shape but its *reason* was not the one we hypothesised. The §"Why DLV survives unified-identity signing" subsection below replaces the reasoning while keeping the original evidence visible.

Test rig: `desktop/scripts/build-sidecar.sh` produces a `--onedir` PyInstaller bundle, signs it (default ad-hoc for local iteration; `SIGN_IDENTITY="Apple Distribution: …"` for TestFlight) with `codesign --force --options=runtime --entitlements …`, and runs it as `./bristlenose-sidecar --port 18150 --no-open /tmp/scratch`.

Four signing runs:

| Entitlements | Outcome |
|---|---|
| `cs.disable-library-validation` + `cs.allow-unsigned-executable-memory` (v0.1 set) | HTTP 404 on `/` at t=1s — alive |
| `cs.allow-unsigned-executable-memory` only | HTTP 404 at t=1s — alive (library validation didn't fire despite entitlement absent, but this turned out to be because we hadn't first `--remove-signature`'d the outer binary; the inner re-signs still had full entitlements from the previous run. After `codesign --remove-signature` + re-sign, this config DIES at load with "different Team IDs") |
| `cs.disable-library-validation` only | HTTP 404 at t=2s — alive |
| Empty `<dict/>` | `[PYI-XXXX:ERROR] Failed to load Python shared library … code signature … not valid for use in process: mapping process and mapped file (non-platform) have different Team IDs` |

Clean outcome: `cs.disable-library-validation` is the only load-bearing key.

### Why DLV survives unified-identity signing (28 Apr 2026 retest)

Hypothesis going into the retest: now that `desktop/scripts/sign-sidecar.sh` runs a full remove-then-resign cycle across every Mach-O in the bundle (240 inner + 1 outer) under one Apple Distribution identity (`Z56GZVA2QB`), the per-binary Team-ID mismatch that originally forced `cs.disable-library-validation` should be gone, and we should be able to drop the entitlement.

Procedure: cleared `desktop/bristlenose-sidecar.entitlements` to `<dict/>`, ran `desktop/scripts/build-all.sh`, exercised the bundle.

Result: **RED.** First sidecar `dlopen` failed with kernel AMFI library validation rejection on `Python.framework/Versions/3.12/Python`:

> `'.../bristlenose-sidecar/_internal/Python.framework/Versions/3.12/Python' not valid for use in process: mapping process and mapped file (non-platform) have different Team IDs`

Root cause (no longer hypothetical): macOS frameworks carry their own internal `_CodeSignature/` seal at `Python.framework/Versions/3.12/_CodeSignature/`, distinct from the per-Mach-O signatures applied by `sign-sidecar.sh`. AMFI's library-validation check at dlopen reads the framework's nested seal, not the per-binary resign — so the unified-identity cycle, however thorough across individual Mach-Os, doesn't reach the framework's internal identifier. The framework continues to present whatever identifier upstream PyInstaller's framework copy carried, and AMFI rejects.

Implications:

- **DLV stays.** The empirical comment block in [`desktop/bristlenose-sidecar.entitlements`](../desktop/bristlenose-sidecar.entitlements) (commit `8cfd2ee`) is the canonical record. App Review justification text is in the entitlement table above and reflects this empirical reasoning.
- **Path forward (parked).** Drop DLV by treating `Python.framework` as a unit: `codesign --force --options=runtime --sign "Apple Distribution: …"` on the framework directory itself, properly resealing the internal `_CodeSignature`. Non-trivial — Apple's framework versioned-symlink layout is fussy, and `codesign` requires the version structure to be coherent before it will reseal. Future `sign-sidecar.sh` enhancement; not on the alpha critical path.
- **Procurement talking point.** "Bristlenose's only Hardened Runtime exception is `cs.disable-library-validation`, empirically forced by Apple's framework seal layout for embedded-Python apps. Every Mach-O in the bundle is signed under our Apple Distribution identity. The exception is documented in our entitlements file with the specific framework path that triggers it." Clean answer for a security questionnaire.

### What wasn't tested

- **App Sandbox.** ~~Hardened Runtime fires without the sandbox; the sandbox only engages when the parent `.app` opts in. Track A will re-exercise the MVP flow with sandbox on and enumerate file/network/bookmark entitlements from Console `deny(1) …` entries.~~ **Updated 1 May 2026:** Track A has now exercised the MVP flow with sandbox on for Debug builds — A1 (29 Apr) added the `app-sandbox` + `inherit` baseline and cleared the bookmark XPC deny via `files.user-selected.read-write`; A1c (30 Apr) verified bundled-sidecar spawn under inherited sandbox and surfaced the `network-bind` deny on 9131; A2 (1 May, this branch) granted `network.server` and verified `bind()` succeeds. Beats 1 + 3 reachable end-to-end under sandbox-on Debug. **Still not tested under sandbox-on:** beats 6+ (pipeline run — gated by an unrelated stale code path in `PipelineRunner.findBristlenoseBinary()` that wasn't migrated to `SidecarMode.resolve()` when C1 landed); FFmpeg subprocess; Whisper model download; LLM call telemetry path; Release config sandbox flip.
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

## Bundle data requirements

PyInstaller's `Analysis` traces Python imports but doesn't discover non-`.py` files. Every runtime data directory must appear explicitly in `datas` in `desktop/bristlenose-sidecar.spec`. The C3 smoke test (20–21 Apr 2026) uncovered three missing entries that produced functional (not cosmetic) breakage in the bundled sidecar. All three are now hard requirements.

| Source dir | Purpose | How it broke before the fix |
|---|---|---|
| `bristlenose/theme/` | CSS + JS assets for the static render scaffold | Cosmetic only |
| `bristlenose/data/` | Built-in codebook and sample data | Cosmetic only |
| `bristlenose/locales/` | i18n JSON (en, es, fr, de, ko, ja) | Translation fallback to key names |
| `bristlenose/llm/prompts/` | Markdown prompt templates loaded by every LLM-using stage (topic-segmentation, quote-extraction, thematic-grouping, autocode, …) | **BUG-5** (`08a0664`) — every LLM call raised `FileNotFoundError` before reaching the provider |
| `bristlenose/server/alembic/` | Migration scripts read by `server/db.py` via `ScriptDirectory.from_config` | `CommandError: Path doesn't exist: …/_internal/bristlenose/server/alembic` at first DB init |
| `bristlenose/server/static/` | React SPA build output (`cd frontend && npm run build`) | **BUG-3** (`5aae47c`) — sidecar served the deprecated static-render HTML for everything. Now a hard requirement with a fail-loud contract (see below) |
| `bristlenose/server/codebook/` | YAML codebook templates (garrett, morville, norman, uxr, plato) loaded by `routes/codebook.py` and exposed via the Browse Codebooks modal | **BUG-4** (`08a0664`) — `CODEBOOK FRAMEWORKS` list empty |

The regression gate `desktop/scripts/check-bundle-manifest.sh` (BUG-6, `673ddee`) is now the `build-all.sh` pre-flight step 2a: it AST-parses the spec, walks `bristlenose/` for any directory containing runtime-data file extensions (yaml, yml, json, md, html, css, js, txt, png, svg, ico, csv, toml, mako, 1, sqlite, bin, pt, onnx, ttf, woff2), and asserts every uncovered dir appears in `datas` or in `desktop/scripts/bundle-manifest-allowlist.md`. Unit tests can't catch this class of bug — they run against an editable install where every source dir is present — so the gate is source-vs-spec, not source-vs-runtime.

### Lesson

PyInstaller's Analysis only picks up `.py` imports. Any runtime data dir — even obvious ones like a React SPA build output — has to be listed explicitly. Manual end-to-end smoke tests are the only audit that surfaces this class of issue; the bundle-manifest gate now enforces the pattern at build time so we can't regress silently.

## Smaller bundling notes

- **`--host` is not a `bristlenose serve` option.** The server hardcodes `127.0.0.1`. Fine for sidecar-over-localhost.
- **Sentiment framework YAML not found** warning at startup — cosmetic; the YAML is optional user config.
- **Sidecar ignores `BRISTLENOSE_AUTH_TOKEN` env var** — the server always generates a fresh per-run token. Swift scrapes the token out of the sidecar's stdout (see "Resource resolution" below).

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
- `sign-sidecar.sh` — parallel inner-Mach-O sign, sequential outer sign, strict + deep verify, SHA256 manifest. Inner loop is a bash `wait -n` job pool, **not `xargs -P`**: BSD `xargs` on macOS drops child exit codes under concurrent jobs, so a single failed codesign would be masked in interleaved stderr (the script would "succeed" while shipping an unsigned dylib). Requires bash 4.3+ for `wait -n`; Apple's default `/bin/bash` is 3.2, so the shebang is `#!/usr/bin/env bash` + a Homebrew bash in `$PATH`.
- `fetch-ffmpeg.sh` — SHA256-pinned FFmpeg 8.1 download (arm64 static builds from evermeet.cx). Cache under `desktop/build/ffmpeg-cache/`. Mismatched SHA256 fails closed — supply-chain-attack defence.
- `sign-ffmpeg.sh` — signs the two FFmpeg siblings with the same identity and Hardened Runtime. Notarisation rejects the outer bundle otherwise.

### `codesign --force` entitlement trap

Noted during C0 (commit `8bd6883`). When probing minimum entitlement sets, `codesign --force --entitlements <file>` without a preceding `codesign --remove-signature` is unreliable: if the outer binary already carried a signature that granted (say) `disable-library-validation`, re-signing with `--force` and a trimmed entitlements file will appear to succeed (`codesign -dv` reports the new entitlements) but the process still runs because the inner `.dylib` / `.so` / `Python.framework` files retain their own signatures with the old entitlements. To genuinely test a minimum set:

```bash
codesign --remove-signature <binary>
codesign --force --options=runtime --entitlements <file> --sign - <binary>
```

The production `sign-sidecar.sh` flow doesn't hit this trap because it signs fresh PyInstaller output, but every entitlement-spike run has to start from `--remove-signature`.

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

### App Store distribution flow (28 Apr 2026, `1ee30eb`)

`build-all.sh` ships an alpha-ready `.pkg` end-to-end via the App Store path. Three structural pieces, all guarded by `method=app-store` in [`desktop/Bristlenose/ExportOptions.plist`](../desktop/Bristlenose/ExportOptions.plist):

**Dual signing identities in `ExportOptions.plist`.** App Store submissions need two certs because Mac apps are uploaded as `.pkg` installers (not raw `.app` bundles):

```xml
<key>signingCertificate</key>
<string>Apple Distribution</string>
<key>installerSigningCertificate</key>
<string>3rd Party Mac Developer Installer</string>
```

The first signs every Mach-O in the `.app` bundle. The second signs the `.pkg` wrapper. `xcodebuild -exportArchive` looks both up by name in the login keychain (`security find-identity -v -p basic` lists them; the installer cert appears under the legacy display name `3rd Party Mac Developer Installer` — same cert family).

**xcarchive-`.app` fallback for downstream gates.** With `method=app-store`, the export step produces only a `.pkg` (276 MB at this version). The script's downstream gates (release-binary scan, embedded-profile sanity, signing battery) need a `.app` to inspect. `build-all.sh` falls back to the `.app` inside the xcarchive at `desktop/build/Bristlenose.xcarchive/Products/Applications/Bristlenose.app` — same signed bundle, just unwrapped:

```bash
EXPORTED_APP=$(find "$EXPORT_DIR" -maxdepth 2 -name "*.app" -type d | head -1)
if [ -z "$EXPORTED_APP" ]; then
    ARCHIVE_APP=$(find "$ARCHIVE_PATH/Products/Applications" -maxdepth 1 -name "*.app" -type d | head -1)
    if [ -n "$ARCHIVE_APP" ] && [ -n "$EXPORTED_PKG" ]; then
        EXPORTED_APP="$ARCHIVE_APP"
        echo "    note: app-store export produced .pkg only — using .app from xcarchive for downstream gates"
    fi
fi
```

Methods that emit `.app` directly (`developer-id`, `mac-application`) keep using `$EXPORT_DIR` as before — the fallback is conditional.

**`pkgutil --check-signature` replaces `spctl` for App Store builds.** `spctl -a -t exec` on a non-stapled Apple Distribution `.app` always rejects with "rejected" — Gatekeeper's `exec` policy expects either App Store provenance OR notarised Developer ID, neither of which applies pre-upload. The replacement is `pkgutil --check-signature` on the `.pkg`:

```bash
pkgutil --check-signature "$EXPORTED_PKG"
# Status: signed by a developer certificate issued by Apple (Development)
# Certificate Chain:
#   1. 3rd Party Mac Developer Installer: Martin Storey (Z56GZVA2QB)
#   2. Apple Worldwide Developer Relations Certification Authority
#   3. Apple Root CA
```

The `(Development)` label in pkgutil output is misleading nomenclature — the Mac Installer Distribution cert is a production cert, but pkgutil's status string categorises it under "developer certificate issued by Apple". The success string we assert against is `signed by a developer certificate issued by Apple`.

**Notarisation + stapling are skipped on this path.** `notarytool` rejects Apple Distribution-signed binaries with "not signed with a valid Developer ID certificate" — it accepts only the Developer ID cert family. App Store submissions are validated server-side by App Store Connect after upload (which includes notarisation as a subset of the review pipeline), so notarytool isn't part of the App Store flow. `build-all.sh` guards steps 9 (notarise) and 10[a] (stapler validate) by export method:

```bash
case "$EXPORT_METHOD" in
    app-store|app-store-connect) SKIP_NOTARISE=1 ;;
    *) SKIP_NOTARISE=0 ;;
esac
```

**Standalone-launch constraint.** Apple Distribution-signed `.app` bundles with App Store provisioning profiles refuse to launch standalone on any user account — even on the dev's own Mac. The error: `RBSRequestErrorDomain Code=5 "Launch failed."` with `NSPOSIXErrorDomain Code=163` (Launchd job spawn failed). Profile expects App Store provenance; standalone double-click doesn't satisfy. To run the bundle locally for empirical work (e.g., the empty-ents retest), use the Xcode Debug Swift host (ad-hoc-signed, launchable) wrapping the empty-ents-signed sidecar from `desktop/Bristlenose/Resources/bristlenose-sidecar/`. AMFI's library-validation check happens at sidecar-internal `dlopen`, independent of the Swift host's signing identity, so the result is valid.

**Upload command.** From `build-all.sh`'s end-of-run banner:

```bash
xcrun altool --upload-app -f "desktop/build/export/Bristlenose.pkg" --type macos \
    --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>
```

(Track B's job. Transporter.app is the GUI alternative.)

### Deferred — Developer ID flow (revisit at ~10k paying users)

> **Section status: deferred to future commercial scale.** Distribution decision (28 Apr 2026): the App Store flow above is Bristlenose's only distribution channel for alpha + beta + early commercial. Developer ID (direct download with notarisation + stapling + Sparkle updates) is **not** a parallel path being maintained alongside — it's deferred until ~10k paying users when the App Store cut becomes material relative to the engineering+ops cost of running a parallel direct-distribution channel. Trigger conditions, cost model, and a quick how-to for adding the cert when we revisit live in the user's `project_developer_id_revisit.md` memory note.
>
> **The Notarisation + stapling subsection below is preserved verbatim** as the design baseline for the eventual revisit. None of these scripts run today; `build-all.sh` skips them when `method=app-store` (the only method we use). Reading guide: treat the subsection as **specification of a future flow**, not a description of current behaviour.

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

Different battery per export method. App Store flow (current shipping path):

- `pkgutil --check-signature <pkg>` — assert `Status: signed by a developer certificate issued by Apple` on the `.pkg` wrapper. Replaces `spctl -a -t exec` because Gatekeeper's `exec` policy rejects Apple Distribution-signed `.app` bundles standalone (they require App Store provenance, which only arrives after upload).
- `codesign --verify --deep --strict --verbose=2 <app>` — seals match through every nested Mach-O.
- `codesign -d --entitlements :- <outer>` — assert **no** `get-task-allow=TRUE` (Debug debuggability entitlement, silently App-Store-rejected).
- `codesign -d --requirements - <outer>` — assert designated requirement includes Team ID `Z56GZVA2QB`.

Developer ID flow (deferred — would run instead of `pkgutil` if `method=developer-id`):

- `xcrun stapler validate <app>` — ticket present and valid.
- `spctl -a -t exec -vv <app>` — Gatekeeper accepts; expected phrase is "source=Notarized Developer ID".

The `SKIP_NOTARISE` guard in `build-all.sh` selects between the two batteries based on `method` in `ExportOptions.plist`.

### Privacy manifest coverage (C4, 28 Apr 2026)

Apple requires `PrivacyInfo.xcprivacy` on App Store / TestFlight uploads since 1 May 2024. App Store Connect parses each manifest at upload time and rejects (`ITMS-91056`/`ITMS-91061`) on invalid reason codes or missing manifests for SDKs on Apple's named hard-rejection list.

**Two manifests** cover the entire bundle:

- **Host** at `Contents/Resources/PrivacyInfo.xcprivacy` (Xcode Copy Bundle Resources from `desktop/Bristlenose/Bristlenose/PrivacyInfo.xcprivacy`). Covers the SwiftUI shell **and** FFmpeg + ffprobe (which ship at `Contents/Resources/`, the host bundle level). Declares `CA92.1` (UserDefaults / `@AppStorage`), `C617.1` + `DDA9.1` (FileTimestamp — sidebar "last opened" display + FFmpeg source-mtime reads), `E174.1` (DiskSpace — FFmpeg statfs), `35F9.1` (SystemBootTime — FFmpeg `mach_absolute_time` for encode-speed timeline).
- **Sidecar** at `Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy` (copied by `desktop/scripts/build-sidecar.sh` from `desktop/bristlenose-sidecar.PrivacyInfo.xcprivacy` post-PyInstaller). Single bundle-root manifest covering the embedded `Python.framework` and 222 `.so` files. Declares `DDA9.1`, `E174.1`, `35F9.1`. **No `UserDefaults`** — the sidecar is pure Python; a 244-Mach-O `nm` sweep found zero `NSUserDefaults` / `CFPreferences` symbols.

**Why one sidecar manifest, not 222.** Apple's bar is API-category coverage at the bundle level, not one manifest per vendored library. The named-SDK list that triggers `ITMS-91061` (~90 entries: Firebase, Adjust, Branch, OneSignal, etc.) does not include any of Bristlenose's Python deps. Per-package sub-manifests would be gold-plating without a rejection lever to defend against.

**Why two manifests, not one.** The host signs and ships under one Apple Distribution identity; the sidecar is a separable PyInstaller `--onedir` bundle that's bootloader-launched as a child process. Mirroring the framework convention (manifest at the embedded bundle's root) keeps the two scopes parseable independently — useful for procurement reviewers grepping the `.pkg`, and a clean structural fit with how `codesign --deep` walks the bundle.

**Triage method (Phase 1, kept for repeatability):**

```bash
SIDECAR="desktop/Bristlenose/Resources/bristlenose-sidecar"
APP="desktop/build/Bristlenose.xcarchive/Products/Applications/Bristlenose.app"
find "$SIDECAR" -type f \( -name "*.so" -o -name "*.dylib" -o -name "Python" -o -name "bristlenose-sidecar" \) > /tmp/macho-list.txt
find "$APP/Contents/Resources" -maxdepth 1 -type f \( -name "ffmpeg" -o -name "ffprobe" \) >> /tmp/macho-list.txt
while IFS= read -r f; do nm -u "$f" 2>/dev/null | awk -v F="$f" '{print F"\t"$NF}'; done < /tmp/macho-list.txt > /tmp/symbols-raw.txt
# Then grep for the four required-reason symbol families:
#   FileTimestamp:    _stat _fstat _lstat _fstatat _getattrlist _getattrlistbulk _fgetattrlist _getattrlistat
#   DiskSpace:        _statfs _fstatfs _statvfs _fstatvfs
#   SystemBootTime:   _mach_absolute_time _mach_continuous_time _clock_gettime_nsec_np
#   UserDefaults:     _NSUserDefaults _CFPreferences*
```

**Build-time enforcement.** `desktop/scripts/build-all.sh` step [f] runs `find ... -name PrivacyInfo.xcprivacy` (always-echo for debuggability) then asserts presence at the two expected paths and `plutil -lint` clean. Any new release archive that lacks either manifest fails the gate before the `.pkg` is exported.

**Re-audit triggers** — situations that may invalidate the current manifest set and require a fresh sweep:

- Sandbox flip (Track A): file-access entitlements may bring new required-reason API categories into scope.
- Dependency upgrades adding new symbol families (`pip install --upgrade torch` etc.). A periodic `nm`-vs-reason-codes regression script is parked as a low-priority follow-up — would catch this class automatically rather than relying on next-upload App Store rejection.
- New bundled binaries (e.g. a custom-built FFmpeg with different codec set).

**Out of scope (post-alpha):**

- Per-Python-package sub-manifests inside `_internal/<package>/` — promote only if a future dep lands on Apple's named-SDK list.
- `NSPrivacyCollectedDataTypes` — currently empty in both manifests, defensible because Bristlenose collects nothing first-party. The user-configured LLM passthrough is third-party data flow under the user's own provider account, disclosed in `AIConsentView.swift` (Apple Guideline 5.1.2(i)). A pre-written reply for the App Store reviewer who asks about this is kept with the rest of the launch-time notes.

### Supply-chain provenance (C5, 28 Apr 2026)

`THIRD-PARTY-BINARIES.md` at the repo root is the canonical inventory of everything non-Bristlenose that ships in `Bristlenose.app/Contents/Resources/`. Three sections:

1. **Native binaries (hand-curated)** — FFmpeg, ffprobe, `Python.framework`, the PyInstaller bootloader. Origin URL, version, SHA256 (where pinned in `desktop/scripts/fetch-ffmpeg.sh`), and licence per row.
2. **Python wheels (auto-generated)** — every package the venv install pulls in, minus the PyInstaller spec excludes (parsed from `desktop/bristlenose-sidecar.spec`) minus an obvious-tooling deny-list. Regenerated by `scripts/generate-third-party-binaries.py` (requires the `[release]` extra: `pip install -e '.[dev,serve,apple,release]'`).
3. **First-run downloads** — Whisper model from HuggingFace; verification delegated to `hf_hub_download`'s built-in SHA chain.

The Python-wheel section is **slightly over-inclusive** by design: a small number of transitive deps of excluded packages (e.g. some spaCy dependencies) remain in the venv even though PyInstaller's modulegraph won't pull them into the bundle. Over-estimating is the safer error direction for procurement-readiness. Rerun `scripts/generate-third-party-binaries.py --check` before each release; CI can wire the `--check` flag to fail the build when the file is stale relative to the venv.

**CVE-monitoring cadence.** Dependabot auto-PRs known CVEs against Python deps; the FFmpeg security mailing list covers the native side; a quarterly manual review (`pip list --outdated` + `pip-licenses` re-run) covers everything else. No automated gate beyond Dependabot; the cadence is the gate.

**Deferred (honest disclosure):** wheel hash pinning (`pip install --require-hashes`) and CycloneDX SBOM emission. Both have a stated path forward in `THIRD-PARTY-BINARIES.md` §"Deferred decisions". Flagging them here so a procurement reviewer asking the questions gets a yes/no with reasoning rather than silence.

### Pre-archive gate (`check-release-binary.sh`)

Scans every Mach-O in the archived/exported `.app` for two Release-forbidden conditions:

1. `BRISTLENOSE_DEV_*` string literals — the Debug-only dev escape-hatch env vars. A Release build that references them means a `#if DEBUG` guard was accidentally removed.
2. `get-task-allow=TRUE` entitlement — Debug-only debuggability.

Skips `Contents/Resources/bristlenose-sidecar/*` (Python strings expected; no Swift `#if DEBUG` invariant applies). Wired into `build-all.sh` post-export (not as an Xcode Run Script phase — merge-hostile pbxproj pollution, and the build-all script is the canonical release path anyway).

### `get-task-allow` "<false/>" entries

Xcode sometimes emits `<key>get-task-allow</key><false/>` in the entitlements dict (rather than omitting the key). That's fine — the check in `check-release-binary.sh` only fires on `<true/>`.

## Resource resolution (forward reference)

Per `design-modularity.md`, single-source lookup functions live in the Python code. For the sidecar path specifically:

- **FFmpeg + ffprobe** — Swift's `BristlenoseShared.bundledBinaryEnvironment(for:)` reads `Contents/Resources/{ffmpeg,ffprobe}` (siblings of the sidecar dir, not under a `/bin/` subdir) and passes them via `BRISTLENOSE_FFMPEG` / `BRISTLENOSE_FFPROBE` env vars at sidecar spawn time. Python's `bristlenose.utils.bundled_binary.bundled_binary_path(name)` resolves in three branches: env var → bundle-relative path under `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` → `shutil.which`. CLI users skip the env vars and fall through to `which`. Shipped `bundled-binary-helper` merge `670a002`.
- **Whisper models** — env var `BRISTLENOSE_WHISPER_MODEL_DIR` → `~/Library/Application Support/Bristlenose/models/` → HuggingFace cache. Background Assets writes to Application Support in public beta; alpha bundles the `small.en` model directly.
- **Credentials (implemented, C3)** — `ServeManager.overlayAPIKeys()` reads Keychain via Security.framework (`SecItemCopyMatching`) at sidecar launch and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars (`ANTHROPIC`, `OPENAI`, `AZURE`, `GOOGLE` — Miro descoped from alpha). Python reads them via pydantic-settings before `_populate_keys_from_keychain` runs. **The sidecar does not call `SecItemCopyMatching`, does not exec `/usr/bin/security`, and does not need any keychain-access-groups or Security.framework entitlement.** It reads plain env vars. See the "Credential flow" section below for details, residual risks, and rationale vs. `pyobjc-framework-Security`.
- **Auth token** — server prints once at startup; Swift greps the token out of the sidecar's stdout. C1 may add structured-stdout (JSON line for handshake) if scraping proves fragile.

All four patterns are "Swift resolves via platform API, passes via env var, Python reads env." That's the no-fork principle from `design-modularity.md`.

## Credential flow (C3, Apr 2026)

The sidecar never touches the macOS Keychain. Instead:

1. User enters an LLM API key via the app's Settings (Cmd+,) → LLM pane.
2. `LLMSettingsView` writes the key to login Keychain via `KeychainHelper.set()` (Security.framework, `SecItemAdd`/`SecItemUpdate`). Service names: "Bristlenose Anthropic API Key", "Bristlenose OpenAI API Key", etc. — kept in sync with `MacOSCredentialStore.SERVICE_NAMES` in `bristlenose/credentials_macos.py`.
3. On project open, `ServeManager.start(projectPath:)` builds a minimal env dict (`PATH`, `HOME`, locale, preferences overlay) and calls `overlayAPIKeys(into:using:)`.
4. `overlayAPIKeys` iterates the four supported LLM providers. For each where `KeychainStore.get(provider:)` returns a non-empty value, it sets `BRISTLENOSE_<PROVIDER>_API_KEY` on the env dict and logs one `Logger.info("injected API key for provider=\(provider, privacy: .public)")` line — presence only, never the value.
5. The env dict is attached to a `Process`, which spawns the sidecar. Foundation copies the strings into `posix_spawn` argv.
6. Python's pydantic-settings reads each `BRISTLENOSE_*_API_KEY` into the corresponding `BristlenoseSettings.*_api_key` field before `_populate_keys_from_keychain` runs. The keychain-fallback path in `credentials_macos.py` never triggers in the sandboxed sidecar because the field is already populated.

**The sidecar requires no `keychain-access-groups` entitlement, no Security.framework linkage, and no temporary-exception entitlements.** It is a consumer of env vars. Under App Sandbox this path just works.

**Why env-var injection instead of `pyobjc-framework-Security`:**
- Adding `pyobjc-framework-Security` to `pyproject.toml` would either (a) break CLI install on Linux/Windows, or (b) sit in a `[macos]` extra that CLI users must remember to add — both violate the no-fork principle from `design-modularity.md`.
- Env var injection is symmetric with the existing `ServeManager.overlayPreferences` pattern (LLM provider, model, Azure endpoint etc. are already passed this way).
- Keys live in-process only; no disk write.

**Residual risks (documented, not fixed in alpha):**
- `ps -E <pid>` shows the full env block to any same-UID process. An attacker with same-UID code execution can therefore scrape keys from the sidecar's environment while it runs. But that same attacker can also call `SecItemCopyMatching` directly against the login keychain, so the net attack-surface delta is small. Honest framing in SECURITY.md: keys "never persist to disk," not "never leave Keychain."
- Crash dumps may contain the Swift-side `env` dictionary. Zeroing Swift `String` memory is not reliably possible without dropping to C; we rely on the same-process-access-equals-keychain-access argument above.
- **Log redaction is two-layered (C3, `8a41f60` + `c17954d`):**
  - **Runtime regex** — `ServeManager.handleLine` applies `redactKeys(in:)` before appending lines to `outputLines`. Three key shapes matched: Anthropic (`sk-ant-...`), OpenAI (`sk-proj-...` and classic `sk-...`), and Google (`AIza...`). Azure is deliberately skipped — its 32-char hex format collides with UUIDs and SHAs producing too many false positives; a pre-beta re-audit is tracked in `docs/private/100days.md`. Auth-token parse runs *before* redaction so base64url tokens can't collide.
  - **Source-level grep** — `desktop/scripts/check-logging-hygiene.sh` scans `.swift` files under `desktop/Bristlenose/Bristlenose/` (excluding `*Tests.swift`) for logger calls and `print()`/`os_log`/`NSLog` calls that interpolate credential-shaped identifiers (`key|secret|token|credential|password`) without a `privacy: .private|.sensitive` marker, and for `print(env ...)` dumps. Allowlist at `desktop/scripts/logging-hygiene-allowlist.md` uses `HYG-<N>` markers. Wired as `build-all.sh` pre-flight step 1a — fails fast before archive. Runtime and source gates are belt-and-braces: one catches active regressions, the other prevents them being introduced.

**Post-alpha knobs (not scheduled):**
- Biometric gate on Keychain access (`kSecAttrAccessControl` + `.biometryCurrentSet`) — post-alpha Settings toggle.
- Key rotation / revocation flow — manual today (re-enter in Settings → `bristlenosePrefsChanged` notification → `ServeManager.restartIfRunning()` → fresh env dict on next spawn).

## Validation gates

Four gates run at different points in the build. Each exists because a specific class of defect shipped or nearly shipped, and can't be caught by unit tests against the editable install.

| Gate | Stage | Commit | Catches |
|---|---|---|---|
| `check-logging-hygiene.sh` | `build-all.sh` pre-flight (step 1a) | `c17954d` (C3) | Swift logger / `print` / `os_log` calls that interpolate credential-shaped identifiers without `privacy: .private|.sensitive` marker; `print(env ...)` env-dict dumps |
| `check-bundle-manifest.sh` | `build-all.sh` pre-flight (step 2a) | `673ddee` (C3, BUG-6) | Runtime-data directories (yaml/md/json/etc.) present in `bristlenose/` but absent from `datas` in the PyInstaller spec. AST-parses the spec; walks the source tree; requires every covered dir or an allowlist entry (`BMAN-<N>` marker) |
| `check-release-binary.sh` | Post-archive + post-export | `73093ff` (C1), extended `cd04ee9` (C2) | `BRISTLENOSE_DEV_*` string literals in any Release Mach-O (a `#if DEBUG` guard accidentally removed); `get-task-allow=TRUE` entitlement (Debug-only debuggability, silently App-Store-rejected). Skips the Python sidecar's `Contents/Resources/bristlenose-sidecar/*` subtree — Python strings are expected there and no Swift `#if DEBUG` invariant applies |
| `bristlenose doctor --self-test` | Runtime (sidecar self-check) | `52024f8` (C3) | Bundle-integrity drift at deployment time — the sidecar verifies its own `datas` payload is present and shaped as expected. Gives the `doctor` command a sidecar-aware path rather than assuming a CLI install |

Ordering matters. The logging-hygiene and bundle-manifest gates fail fast (seconds) before the 3-minute PyInstaller build. The strings/`get-task-allow` gate runs after archive because it's scanning the built artefact.

## Fail-loud contracts

The C3 smoke test surfaced that **silent fallback to the deprecated static render masked a functional regression (BUG-3)**. The architectural response: fail loud at every layer where a missing or malformed bundle component could hide a real bug.

| Contract | Enforced by | What used to happen instead |
|---|---|---|
| **React bundle missing** → HTTP 500 + clear error page | `bristlenose/server/app.py:_mount_prod_report` (`3a9bc6a`) | Silently served the deprecated Jinja2 static-render HTML. Masked the BUG-3 regression — the C3 smoke test saw a plausible-looking Bristlenose UI without noticing it wasn't the React SPA |
| **Bundle data missing** → `build-all.sh` fails pre-PyInstaller | `check-bundle-manifest.sh` | Bundle would build successfully, sidecar would crash at runtime with `FileNotFoundError` on first use of the missing data (BUG-4, BUG-5 class) |
| **Dev env-var leak into Release Mach-O** → archive gate fails | `check-release-binary.sh` | Release binary would carry `BRISTLENOSE_DEV_*` string literals readable via `strings <binary>`. Potentially exploitable; certainly an App-Store-review smell |
| **Log hygiene violation** → pre-flight fails | `check-logging-hygiene.sh` | Swift-side API-key interpolation without a `privacy: .private` marker would ship into production and leak keys to Console.app / unified logging archives |
| **Both dev env vars set** → `SidecarMode.resolve` returns `.failed` | `SidecarMode.swift` | Silent misconfiguration; mode selection would have been ambiguous |
| **`codesign --timestamp` silently degrades to `--timestamp=none`** → sign-script asserts and fails | `sign-sidecar.sh` / `sign-ffmpeg.sh` post-sign `grep "Timestamp="` | Un-notarisable signature; notarisation failure hours later |

Lesson from the smoke test: treat "the pipeline produced an artefact" as weak evidence. A gate that fails loud at the earliest layer prevents a downstream audit (human or reviewer) from being the first thing to notice.

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
- [`desktop/scripts/check-bundle-manifest.sh`](../desktop/scripts/check-bundle-manifest.sh) — C3 source→spec coverage gate (BUG-6)
- [`desktop/scripts/check-logging-hygiene.sh`](../desktop/scripts/check-logging-hygiene.sh) — C3 Swift-side credential-string hygiene gate
- [`desktop/Bristlenose/ExportOptions.plist`](../desktop/Bristlenose/ExportOptions.plist) — `xcodebuild -exportArchive` options
- [`desktop/Bristlenose/Bristlenose/SidecarMode.swift`](../desktop/Bristlenose/Bristlenose/SidecarMode.swift) — mode resolution contract
- [`desktop/Bristlenose/Bristlenose/ServeManager.swift`](../desktop/Bristlenose/Bristlenose/ServeManager.swift) — `overlayAPIKeys` + `handleLine` redactor (C3)
- [`desktop/v0.1-archive/bristlenose-sidecar.spec`](../desktop/v0.1-archive/bristlenose-sidecar.spec) — prior art
- [`docs/private/c2-session-notes.md`](./private/c2-session-notes.md) — C2 session notes, gotchas, resume-cold guide
- [`docs/private/c3-session-notes.md`](./private/c3-session-notes.md) — C3 session notes (Keychain injection, redactor, BUG-3..6 smoke-test findings)
