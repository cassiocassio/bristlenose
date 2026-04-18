# Desktop Python Runtime — sidecar mechanics

_Written 18 Apr 2026 as Track C C0 spike output. Covers entitlements, signing, bundling trim, and runtime resource resolution for the bundled PyInstaller sidecar on macOS. Cross-channel component decisions (what ships where, and why) live in [`design-modularity.md`](./design-modularity.md) — this doc is strictly Mac-specific mechanics._

## Scope

This doc is the canonical source for:

- Which Hardened Runtime entitlements the sidecar needs and why
- How the sidecar is laid out inside `Bristlenose.app/Contents/Resources/`
- How Swift spawns and supervises it (ServeManager contract)
- How resources (FFmpeg, Whisper models, credentials) are located at runtime
- How codesigning is layered (inner `.dylib`/`.so` → outer binary → outer `.app`)

It is **not** the implementation plan — that's Track C C1, tracked in `docs/private/sprint2-tracks.md`.

## Status (C0 output, 18 Apr 2026)

- ✅ Trimmed PyInstaller spec drafted at `desktop/sidecar-c0/bristlenose-sidecar.spec` (MLX-only; ctranslate2 / faster-whisper / presidio / spaCy excluded).
- ✅ Sidecar builds, ad-hoc codesigns with Hardened Runtime, and serves HTTP on localhost under `bristlenose serve`.
- ✅ Minimum entitlement set empirically confirmed: **one key only**.
- ⚠️ Bundle size 644 MB (target ≤ 200 MB). Transitive torch / llvmlite / onnxruntime still pulled in — C1 needs a deeper excludes pass. See §"Bundle-size findings" below.
- ❌ `com.apple.security.inherit` not yet tested (App Sandbox is Track A; sidecar inherits only once parent has sandbox enabled).

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

Test rig: `desktop/sidecar-c0/build-and-sign.sh` produces a `--onedir` PyInstaller bundle, ad-hoc signs it with `codesign --force --options=runtime --entitlements …`, and runs it as `./bristlenose-sidecar --port 18150 --no-open /tmp/scratch`.

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

The C0 bundle lives at `desktop/sidecar-c0/dist/bristlenose-sidecar/` (gitignored). Shape:

```
bristlenose-sidecar/
├── bristlenose-sidecar       (the outer Mach-O, 5 MB)
└── _internal/
    ├── Python                (dyld stub → Python.framework)
    ├── Python.framework/     (CPython 3.12 runtime)
    ├── base_library.zip      (pure-Python stdlib frozen)
    ├── torch/                (288 MB — transitively pulled; C1 target)
    ├── llvmlite/             (110 MB — transitively pulled; C1 target)
    ├── onnxruntime/          (58 MB — transitively pulled; C1 target)
    ├── mlx/                  (24 MB — ours)
    ├── scipy/                (37 MB — transitively pulled; C1 target)
    ├── bristlenose/          (theme, data, locales, server/alembic)
    └── … every signed .so and .dylib
```

The flat `_internal/` layout is PyInstaller `--onedir`. Swift finds the outer binary at a fixed path; dyld resolves everything inside `_internal/` via embedded rpath.

## Bundle-size findings (C1 work item)

Target per road-to-alpha §4: ≤ 200 MB. Actual C0 bundle: **644 MB**. The gap is three transitive dependencies PyInstaller grabbed despite the `excludes`:

| Package | Size | Likely hop | C1 mitigation |
|---|---|---|---|
| `torch` | 288 MB | Probably pulled via `tiktoken` → `transformers` legacy tokenizers. We don't actually call torch at runtime. | Add `torch`, `torchvision`, `torchaudio` to `excludes`; confirm no code path imports them |
| `llvmlite` | 110 MB | Pulled via `numba` which is pulled via some audio preprocessing dep | Add `numba`, `llvmlite` to `excludes` |
| `onnxruntime` | 58 MB | Pulled via `tokenizers` or `huggingface_hub`'s optional paths | Add `onnxruntime`, `onnxruntime-genai` to `excludes` |
| `scipy` | 37 MB | Pulled via librosa or audio feature extraction | Audit whether we touch scipy at runtime in serve mode; probably excludable |

Expected post-trim: ~150 MB. C1 should end with a `scripts/check-bundle-size.sh` that fails CI if the trimmed bundle exceeds 200 MB — regressions here are easy to ship accidentally and expensive to debug.

## Bundling gotchas discovered

1. **Alembic migrations directory must be explicitly listed in `datas`.** `bristlenose/server/alembic/` is a filesystem resource read by Alembic's `ScriptDirectory.from_config`; PyInstaller doesn't detect it through `bristlenose.server.db`'s imports. Without it: `CommandError: Path doesn't exist: …/_internal/bristlenose/server/alembic` at first DB init. Added to the spec.
2. **Locales directory same story** — `bristlenose/locales/*.json` is read as data, not imported. Added to `datas`.
3. **React static bundle not present in C0.** The sidecar runs fine without `bristlenose/server/static/` but emits a WARNING log line. C1 needs a pre-build `npm run build` step that emits into the PyInstaller staging area.
4. **`--host` is not a `bristlenose serve` option.** The server hardcodes `127.0.0.1`. Fine for sidecar-over-localhost; document if we ever need to bind elsewhere (probably never).
5. **Sentiment framework YAML not found** warning at startup — cosmetic; the YAML is optional user config.
6. **Sidecar ignores `BRISTLENOSE_AUTH_TOKEN` env var** — the server always generates a fresh per-run token. If Swift wants to know the token, it has to either read stdout (current pattern) or we add env-var plumbing in C1. Defer.

## Signing strategy (C2 preview)

C0 script `build-and-sign.sh` uses a sequential `find … | while read` loop to sign each inner binary, then the outer. C2 needs:

```bash
# Parallelise per-binary signing (10× faster in CI)
find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 |
    xargs -0 -P8 -I{} codesign --force --options=runtime --timestamp \
        --entitlements "$ENT" --sign "$IDENTITY" {}
```

Ordering: inner binaries before the outer executable; outer executable before the `.app` wrapper. Each `--timestamp` call contacts Apple's TSA server — parallelisation is the only way to keep CI time reasonable.

Identity swaps: `-` (ad-hoc, local iteration) vs `"Apple Distribution: Martin Storey (Z56GZVA2QB)"` for upload. Pass via `SIGN_IDENTITY` env var.

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
- Sidecar up but on the wrong port: HTTP connection refused from Swift, no error from sidecar. C1 should have Swift read "Report: http://127.0.0.1:PORT/" line and match against the configured port.

## Open questions (resolve during C1)

- **What extra entitlements does App Sandbox need?** Track A's violation log will tell us. The sidecar itself only needs `inherit`; all user-facing entitlements (files, network, bookmarks) go on the parent `.app`.
- **Does mlx_whisper need any runtime-allow keys?** Not observed in C0 (we didn't run inference). Test in C1 with a real transcription.
- **Is the bundle size trim enough to get back to ≤ 200 MB without losing functionality?** C1 prototype target.
- **What happens when the user's Mac has no Metal GPU support** (e.g. x86_64 Mac running Rosetta on the arm64 sidecar)? The sidecar is `target_arch="arm64"`; Rosetta shouldn't apply. Still worth a compatibility matrix.

## Cross-references

- [`docs/design-modularity.md`](./design-modularity.md) — what gets bundled
- [`docs/private/sprint2-tracks.md`](./private/sprint2-tracks.md) — Track C C0–C5
- [`docs/private/road-to-alpha.md`](./private/road-to-alpha.md) §3, §4, §5 — sandbox, signing, Hardened Runtime checkpoints
- [`desktop/sidecar-c0/`](../desktop/sidecar-c0/) — spec, entitlements, build script, this spike's output
- [`desktop/v0.1-archive/bristlenose-sidecar.spec`](../desktop/v0.1-archive/bristlenose-sidecar.spec) — prior art
