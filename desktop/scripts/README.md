# desktop/scripts

Build, signing, verification, and reset scripts for the macOS **Bristlenose.app**
and its bundled PyInstaller `bristlenose serve` **sidecar**.

These support the shipping architecture described in [`desktop/CLAUDE.md`](../CLAUDE.md)
and [`docs/design-desktop-python-runtime.md`](../../docs/design-desktop-python-runtime.md);
this file is the per-script index, the design docs carry the *why*.

Every script resolves its own paths (via `$0`), so you can invoke it from anywhere.
If your shell is *inside* this folder, prefix with `./` — the folder isn't on `PATH`.

## Build & package

| Script | What it does | When it runs |
|---|---|---|
| `build-all.sh` | End-to-end signed/notarised `.app`: pre-flight → fetch-ffmpeg + build-sidecar (parallel) → sign-ffmpeg → sign-sidecar → `xcodebuild archive` → `-exportArchive` → release checks → notarise/staple. Bails on any non-zero exit. | Release / TestFlight |
| `build-sidecar.sh` | PyInstaller `--onedir` of `bristlenose serve` → `desktop/Bristlenose/Resources/bristlenose-sidecar/`. Recreates a dedicated `.venv-sidecar` from scratch each run (only `.[serve,apple,desktop]`), keeping contributor-`.venv` cruft out of the bundle. | build-all step 2, or manual |
| `sign-sidecar.sh` | Code-signs every Mach-O (a tree of 240+) in the sidecar bundle, leaf-first; inner loop parallelised via a `wait -n` pool (not `xargs -P` — BSD `xargs` drops child exit codes). | build-all step 4, or manual |
| `fetch-ffmpeg.sh` | Downloads pinned-SHA256 static `ffmpeg` + `ffprobe` (macOS arm64) into `Resources/`. Gitignored output — doesn't follow worktrees. | build-all step 2, or once per worktree |
| `sign-ffmpeg.sh` | Code-signs the bundled `ffmpeg` + `ffprobe` (kept separate from the sidecar: single Mach-O, no entitlements). | build-all step 3, or manual |
| `generate-build-info.sh` | Writes `GeneratedBuildInfo.swift` (gitignored) from git state + Xcode build settings, for the in-app Build Info diagnostic. | Xcode Run Script phase, pre-Compile |

> **`build-sidecar.sh` needs the frontend pre-built.** It bundles `bristlenose/server/static/`
> but does **not** run `npm run build`. If that directory is missing, PyInstaller fails with
> `Unable to find '.../bristlenose/server/static'`. Run `(cd frontend && npm run build)` first.
> (If the SPA is unchanged on your branch you can copy in an existing build — the bundle's
> Python/theme come from the editable install regardless.)
>
> **Prereq:** `python3.12` on `PATH` (`brew install python@3.12`).

## Verification gates

| Script | Asserts | Exit |
|---|---|---|
| `check-bundle-manifest.sh [root]` | Every runtime-data dir under `bristlenose/` (yaml/json/md/html/css/js/…) is covered by a `datas` entry in `bristlenose-sidecar.spec` — catches "data file in source, missing from bundle" *before* the 3-min PyInstaller build. | 0 clean · 1 uncovered · 2 usage |
| `check-release-binary.sh <archive\|app\|binary>` | No dev escape-hatch literals (`BRISTLENOSE_DEV_EXTERNAL_PORT`, `BRISTLENOSE_DEV_SIDECAR_PATH`) survive in the **Release** Mach-O — they live under `#if DEBUG`, so a Release compile must exclude them. | 0 clean · 1 leak |
| `check-logging-hygiene.sh [root]` | No Swift `Logger` call interpolates a credential-shaped identifier without a `privacy:` marker, and no `print()` dumps env. Scans `desktop/Bristlenose/Bristlenose/*.swift`, excludes `*Tests.swift`. | 0 clean · non-0 violation |
| `bundle-manifest-allowlist.md` | Allowlist consumed by `check-bundle-manifest.sh`. | — |
| `logging-hygiene-allowlist.md` | Allowlist for `check-logging-hygiene.sh` — add `<!-- ci-allowlist: HYG-<N> -->` + justification. | — |

## Dev / QA reset (macOS only)

| Script | What it does |
|---|---|
| `reset-sandbox-state.sh` | Clears stale App-Sandbox container state (`~/Library/Containers/app.bristlenose/Data/*`, UserDefaults, bounces `cfprefsd`) that wedges `libsecinit` on launch — symptom is `EXC_BREAKPOINT` in `_libsecinit_appsandbox.cold.*`. Flags: `--quiet`, `--dry-run`. Refuses to run off macOS. |
| `reset-app-state.sh` | "Clean-ish profile" reset for UX walkthroughs; calls `reset-sandbox-state.sh`. |

> ⚠️ **These destroy data on *sandboxed* builds.** The container holds `projects.json`
> (your project list), `consentLog` (the AI-disclosure audit trail — Apple 5.1.2(i)),
> and `aiConsentVersion`. Snapshot them first if they matter. Unsandboxed Debug builds
> keep their data elsewhere and are untouched.

## Common recipes

**Local sidecar rebuild for QA** — rebuild the Python side, then run the app:

```bash
# from the repo root
(cd frontend && npm run build)                       # build-sidecar bundles this, doesn't build it
./desktop/scripts/build-sidecar.sh                   # → desktop/Bristlenose/Resources/bristlenose-sidecar/
SIGN_IDENTITY=- ./desktop/scripts/sign-sidecar.sh    # "-" = ad-hoc; fine for local runs
# then in Xcode: "Bristlenose" scheme → Shift+Cmd+K (clean) → Cmd+R
```

The clean is load-bearing — the *Copy Sidecar Resources* build phase may not re-embed a
fresh bundle on an incremental build. Faster alternative for pure backend/frontend
iteration: the **Bristlenose (Dev Sidecar)** / **(External Server)** schemes, which skip
the bundle entirely (see `desktop/CLAUDE.md` § Dev workflow).

**Full release build:** `./desktop/scripts/build-all.sh` (needs a signing identity +
notarytool credentials).

**Clear a wedged sandbox:** `./desktop/scripts/reset-sandbox-state.sh`.

## `SIGN_IDENTITY`

Both signing scripts read it:

- `-` (default) — ad-hoc signature, no Developer ID. Satisfies Hardened Runtime on the
  signing machine so the bundle runs locally; **not** distributable.
- `"Apple Distribution: …"` — a real cert, for TestFlight / release.

`TIMESTAMP_FLAG` follows suit: a real Apple TSA timestamp for a real identity,
`--timestamp=none` for ad-hoc.

## See also

- [`desktop/CLAUDE.md`](../CLAUDE.md) — desktop app + sidecar architecture, the three
  dev schemes, and the build/signing gotchas
- [`docs/design-desktop-python-runtime.md`](../../docs/design-desktop-python-runtime.md) —
  the bundled-sidecar shipping design
