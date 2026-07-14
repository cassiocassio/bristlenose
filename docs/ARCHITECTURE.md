# Architecture

A map of how Bristlenose fits together. It's an **index**, not an encyclopaedia — each
section points at the design doc that owns the detail rather than repeating it. Two
questions to answer: *how do the pieces connect*, and *how does a release get cut*.

For where individual files live, see [file-map.md](file-map.md). For the project
layout and dev setup, see [CONTRIBUTING.md](../CONTRIBUTING.md). For per-area conventions,
the nested `CLAUDE.md` files (`bristlenose/`, `frontend/`, `desktop/`,
`bristlenose/server/`, `bristlenose/stages/`, `bristlenose/llm/`, `bristlenose/theme/`)
are the source of truth.

---

## The one thing to understand first

Bristlenose is **one Python codebase distributed through several channels**. The exact
same pipeline code that runs when you type `bristlenose run interviews/` in a terminal
also runs inside the macOS app — there, it's a bundled Python process (the "sidecar")
that the SwiftUI shell spawns and talks to over local HTTP.

> **CLI ≡ desktop sidecar.** There is no code fork between the command line and the Mac
> app. Differences live only in *packaging* (what pip installs, what the app bundles,
> where a file is looked up at runtime) — never in separate stage logic or Mac-only
> Python modules. This is a load-bearing rule; the canonical statement of it is
> [design-modularity.md](design-modularity.md).

So there are really three things layered on top of that shared core:

- **The CLI** — Typer commands (`run`, `serve`, `analyze`, `status`, `doctor`, …),
  shipped on PyPI, Homebrew, and Snap.
- **The web SPA** — a React app served by `bristlenose serve`. This *is* the product UI.
- **The macOS app** — a SwiftUI shell that wraps the SPA in a WKWebView and spawns the
  Python core as a bundled sidecar. Distributed via TestFlight / the Mac App Store.

```
                        ┌──────────────────────────────────────────┐
                        │  bristlenose/  — the Python core            │
                        │  12-stage pipeline · LLM providers · FastAPI│
                        │  serve mode · SQLite · analysis math        │
                        └──────────────────────────────────────────┘
                            ▲                              ▲
              same code     │                              │   same code,
              via pip/brew  │                              │   bundled by PyInstaller
                            │                              │
                ┌───────────┴──────────┐        ┌──────────┴─────────────────┐
                │  CLI                  │        │  macOS app (desktop/)       │
                │  `bristlenose run …`  │        │  SwiftUI shell + WKWebView  │
                │  `bristlenose serve …`│        │  spawns sidecar:            │
                └───────────┬──────────┘        │  `bristlenose serve` on      │
                            │                    │  127.0.0.1:<port>           │
                            │                    └──────────┬─────────────────┘
                    serves  │                               │  loads
                            ▼                               ▼
                ┌────────────────────────────────────────────────────┐
                │  frontend/  — React + TypeScript SPA (the product UI)│
                │  browser tab (serve mode)  ·  WKWebView (desktop)    │
                └────────────────────────────────────────────────────┘
```

---

## How it fits together

### 1. The pipeline core (`bristlenose/`)

The heart of the app is a **12-stage pipeline** that turns a folder of recordings into a
browsable report:

```
ingest → extract audio → parse subtitles → parse docx → transcribe →
identify speakers → merge transcript → PII removal → topic segmentation →
quote extraction → quote clustering → thematic grouping → render
```

One module per stage under [`bristlenose/stages/`](../bristlenose/stages/)
(`s01_ingest.py` … `s12_render/`), wired together by
[`bristlenose/pipeline.py`](../bristlenose/pipeline.py). Transcription runs locally
(Whisper via MLX on Apple Silicon, faster-whisper elsewhere); the analysis stages call
an LLM provider.

- **Pipeline conventions, resume, caching, quote exclusivity** →
  [`bristlenose/stages/CLAUDE.md`](../bristlenose/stages/CLAUDE.md)
- **Pipeline resilience** (manifest, event sourcing, resume, provenance) →
  [design-pipeline-resilience.md](design-pipeline-resilience.md)
- **LLM providers** (Claude, ChatGPT, Azure OpenAI, Gemini, local Ollama) →
  [`bristlenose/llm/CLAUDE.md`](../bristlenose/llm/CLAUDE.md)
- **Analysis math** (signal concentration, pure computation, no LLM) →
  [design-analysis-future.md](design-analysis-future.md)

### 2. Serve mode: the FastAPI + SQLite backend

`bristlenose serve` boots a FastAPI server that imports the pipeline's JSON output into
SQLite, exposes a REST API for researcher edits (tags, stars, hidden quotes, name
corrections), and serves the React SPA. Everything binds to `127.0.0.1` — nothing
listens on an external interface.

- **Server architecture, routes, importer, data model** →
  [`bristlenose/server/CLAUDE.md`](../bristlenose/server/CLAUDE.md)
- **Multi-project scope rules** → [design-multi-project.md](design-multi-project.md)

### 3. The React SPA (`frontend/`)

The interactive report is a Vite + React + TypeScript + React Router SPA. **This is the
product.** In serve mode `app.py` swaps `<!-- bn-app -->` markers in the rendered HTML
for a `<div id="bn-app-root">`, and the SPA mounts a single `RouterProvider` there. The
same bundle renders in a browser tab (serve mode) and in the desktop app's WKWebView
(embedded mode).

> The Jinja2 static renderer in `bristlenose/stages/s12_render/` is a **deprecated,
> sealed byproduct** — new features and design changes go to the React SPA only. See the
> static-render rules in the root [CLAUDE.md](../CLAUDE.md).

- **Frontend architecture, gotchas, bundle-size gate, code-splitting** →
  [`frontend/CLAUDE.md`](../frontend/CLAUDE.md)
- **Design system** (atomic CSS tokens under `bristlenose/theme/`) →
  [`bristlenose/theme/CLAUDE.md`](../bristlenose/theme/CLAUDE.md) and the design-system
  section in [CONTRIBUTING.md](../CONTRIBUTING.md)
- **React migration plan** → [design-react-migration.md](design-react-migration.md)

### 4. The macOS app (`desktop/`)

A SwiftUI shell that wraps the SPA in a WKWebView, with a native project sidebar, native
toolbar, and native Settings window. In the shipping (alpha / TestFlight) configuration
it carries a **bundled, signed PyInstaller sidecar** — the Python core packaged as a
self-contained `--onedir` bundle inside `Bristlenose.app/Contents/Resources/`. The shell
spawns it (`bristlenose serve` on a kernel-assigned localhost port), scrapes the port and
per-run auth token from its stdout, and points the WKWebView at it.

- **Desktop working notes** (schemes, sandbox iteration, native chrome) →
  [`desktop/CLAUDE.md`](../desktop/CLAUDE.md)
- **Sidecar mechanics** — entitlements, bundle layout, `ServeManager` spawn/supervise
  contract, runtime resource resolution (FFmpeg, Whisper models, credentials) →
  [design-desktop-python-runtime.md](design-desktop-python-runtime.md) *(the canonical
  Mac-specific mechanics doc)*
- **Overall app design** → [design-desktop-app.md](design-desktop-app.md)
- **WKWebView ↔ Swift messaging** → [design-wkwebview-messaging.md](design-wkwebview-messaging.md)

**Credential flow** is a good example of the no-fork principle in action: Swift reads the
API key from the macOS Keychain and injects it as an environment variable at sidecar
launch; the Python side just reads the env var via pydantic-settings, with no Mac-specific
code. Same pattern for the bundled FFmpeg path. Details in
[design-modularity.md](design-modularity.md) §"Credential stores" and
[design-desktop-python-runtime.md](design-desktop-python-runtime.md).

### 5. Model delivery (planned): Background Assets

Whisper models and large optional dependencies (PII / spaCy) are big enough that we don't
want them in the initial `.app` download. The plan is Apple **Background Assets** —
OS-scheduled, Wi-Fi-opportunistic, Apple-hosted downloads that "trickle in" after install
while the user is already productive. The acquisition strategy (and its many network
failure modes) is captured in
[design-modularity.md](design-modularity.md) §"Acquisition strategy: trickle to full
capability". Implementation is planned, not shipped — the working design lives in a
maintainer-only handoff kept outside the public repo.

---

## How a release is cut

There are two release paths, because there are two kinds of artefact.

### CLI release (PyPI / Homebrew / Snap)

Ordinary day-to-day: commit to `main`, and when you want to ship, bump the version and
tag. Version lives in exactly one place — `bristlenose/__init__.py`
(`__version__`) — and `./scripts/bump-version.py` updates it plus the man page and creates
the tag. GitHub Actions then does the rest: CI → PyPI publish → GitHub Release → Homebrew
tap dispatch; the Snap workflow builds edge on push and stable on a `v*` tag.

The full pipeline, secrets, cross-repo topology, and the mandatory **post-push PyPI
verification** step live in [release.md](release.md) and the "Releasing" section of
[CONTRIBUTING.md](../CONTRIBUTING.md). (PyPI immutability, tag-redelivery quirks, and the
minor-vs-patch bump rule are all in the root [CLAUDE.md](../CLAUDE.md).)

### macOS app release (TestFlight / Mac App Store)

The Mac app is built and signed by `desktop/scripts/build-all.sh`, which orchestrates a
chain of smaller scripts. At a level you can follow:

1. **Pre-flight gates** — logging-hygiene scan, and `check-bundle-manifest.sh` asserting
   every runtime-data directory under `bristlenose/` is declared in the PyInstaller spec
   (PyInstaller only traces `.py` imports; data files must be listed explicitly).
2. **Build + sign the sidecar** (`ensure-sidecar.sh`, which drives `fetch-ffmpeg.sh` +
   `build-sidecar.sh` + `sign-ffmpeg.sh` + `sign-sidecar.sh`): download the SHA-pinned
   static FFmpeg/ffprobe, run PyInstaller against a clean from-scratch venv, then codesign
   every Mach-O — hundreds of `.so`/`.dylib` files, the FFmpeg binaries, and the framework
   — under one Apple Distribution identity.
3. **Self-test + inventory** (`doctor --self-test`) — spawn the just-built sidecar and
   confirm the bundle can actually serve.
4. **Archive** — `xcodebuild archive`. The Xcode "Copy Sidecar Resources" phase stages the
   signed sidecar into the `.app`.
5. **Export** — `xcodebuild -exportArchive` with `method=app-store-connect`, which produces
   a `.pkg` (App Store upload format). Downstream gates that need a `.app` fall back to the
   one inside the `.xcarchive` — same signed bundle, unwrapped.
6. **Verification battery** — `check-release-binary.sh` (no `get-task-allow`, designated
   requirement pins the Team ID), `codesign --verify --deep --strict`, and
   `pkgutil --check-signature` on the `.pkg`.
7. **Upload** — `xcrun altool --upload-app` (or Transporter.app) to App Store Connect.

Notarisation + stapling are **skipped** on this path — `notarytool` only accepts the
Developer ID cert family, and App Store submissions are validated server-side after
upload. The Developer-ID / notarised-`.dmg` / Sparkle flow is deferred (not rejected);
its scripts are preserved as a future-state spec in
[design-desktop-python-runtime.md](design-desktop-python-runtime.md).

#### Nested-binary signing requirements

The Mac app is a **nested binary** — an app bundle that contains other executables (the
sidecar, FFmpeg, ffprobe, and CPython's `Python.framework`). Apple's *server-side*
validation enforces rules that a local `codesign --verify` cannot catch, because they're
App Store *policy*, not signature validity (see commit `4c549c36` on the `testflight-prep`
branch for the fixes, and the `app-store-police` review agent for how they're checked).
The rules:

- **Every nested executable needs `com.apple.security.app-sandbox` *and*
  `com.apple.security.inherit`.** The sidecar, FFmpeg, and ffprobe each carry these in
  their entitlements files (`desktop/bristlenose-sidecar.entitlements`,
  `desktop/bristlenose-ffmpeg.entitlements`). The Hardened-Runtime `cs.*` keys the sidecar
  needs are `inherit`-compatible and coexist with these.
- **The framework's main Mach-O must be signed with `--identifier` = its
  `CFBundleIdentifier`.** `Python.framework`'s main binary is literally named `Python`, so
  an inner-loop glob matching only `*.dylib`/`*.so` silently misses it — a dedicated
  framework pass in `sign-sidecar.sh` signs it with the right identifier.
- **`LSApplicationCategoryType` must be set** in Info.plist
  (`public.app-category.productivity`) — a missing category is an outright upload
  rejection.
- **App Sandbox makes the sidecar unrunnable standalone**, so `build-all.sh`'s self-test
  step (2a) is guarded to skip the standalone exec on sandbox-signed builds.

The single Hardened-Runtime *exception* Bristlenose ships is
`com.apple.security.cs.disable-library-validation`, forced empirically by the way
`Python.framework` carries its own nested `_CodeSignature/` seal. The full justification
(and the App Review talking points) is the entitlement table in
[design-desktop-python-runtime.md](design-desktop-python-runtime.md).

#### Maintainer-only specifics

Signing identities, the Apple Developer account and Team ID, App Store Connect field
values, provisioning profiles, and the submission checklist are **not** in the public
repo. They live in the maintainer's private planning notes, kept outside the public
tree, and are referenced here only as *maintainer-only*. This split is deliberate:
architecture and local-dev instructions are public; release credentials and
account-specific values are not.

---

## Related maps

- [file-map.md](file-map.md) — where individual files live
- [CONTRIBUTING.md](../CONTRIBUTING.md) — dev setup, project layout, design system, release quick-start
- [ROADMAP.md](ROADMAP.md) — where things are going
- [design-modularity.md](design-modularity.md) — the canonical cross-channel component strategy
- [design-deployment-targets.md](design-deployment-targets.md) — macOS / Linux CI / Cloud VM boundaries
