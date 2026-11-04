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

- **The CLI** — Typer commands (`run`, `transcribe`, `analyze`, `serve`, `status`, `use`,
  `configure`, `doctor`, …), shipped on PyPI, Homebrew, Snap, and a Fedora Copr (plus
  winget as a follower channel).
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
[`bristlenose/pipeline.py`](../bristlenose/pipeline.py). Transcription runs on the user's
machine (Whisper via MLX on Apple Silicon, faster-whisper elsewhere); the analysis stages
make an outbound **cloud LLM call** to the researcher's chosen provider — that is the
normal path, with local Ollama a supported minority option.

- **Pipeline conventions, resume, caching, quote exclusivity** →
  [`bristlenose/stages/CLAUDE.md`](../bristlenose/stages/CLAUDE.md)
- **Pipeline resilience** (manifest, event sourcing, resume, provenance) →
  [design-pipeline-resilience.md](design-pipeline-resilience.md)
- **LLM providers** (Claude, ChatGPT, Azure OpenAI, Gemini, local Ollama; no vendor default —
  see [design-cli-provider-selection.md](design-cli-provider-selection.md)) →
  [`bristlenose/llm/CLAUDE.md`](../bristlenose/llm/CLAUDE.md)
- **Analysis math** (signal concentration, pure computation, no LLM) →
  [design-signals-future.md](design-signals-future.md)

### 2. Serve mode: the FastAPI + SQLite backend

`bristlenose serve` boots a FastAPI server that imports the pipeline's JSON output into
SQLite, exposes a REST API for researcher edits (tags, stars, hidden quotes, name
corrections), and serves the React SPA. Everything binds to `127.0.0.1` — nothing
listens on an external interface.

Two more things hang off serve mode:

- **Assistant surfaces** — the in-app **chat lens** (a cited question box) and the
  **MCP endpoint** at `/mcp/` (`server/mcp_server.py`; read-only, four tools, scoped
  bearer) for external agents. Both ground in one shared core,
  [`server/grounding.py`](../bristlenose/server/grounding.py), never parallel copies. On
  the Mac the MCP transport is a `.mcpb` extension (`desktop/mcpb/`, with a sandboxed
  native helper in `desktop/mcp-helper/`); exposure is per project. See
  [design-mcp-server.md](design-mcp-server.md), [design-mcp-extension.md](design-mcp-extension.md)
  and [design-chat-lens.md](design-chat-lens.md).
- **Export** — a self-contained HTML leave-behind (the SPA plus inlined API data, opened
  offline from `file://`), built by a dedicated single-file Vite build
  (`frontend/vite.export.config.ts`) and assembled by `server/routes/export.py`. See
  [design-export-html.md](design-export-html.md).

Project identity — a study is its database plus a marker id (`study_marker.py`), a recording
is a content fingerprint (`utils/fingerprint.py`), a path is only a hint — is specified in
[design-project-identity.md](design-project-identity.md).

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
- **Overall app design** → [archive/design-desktop-app.md](archive/design-desktop-app.md)
- **WKWebView ↔ Swift messaging** → [design-wkwebview-messaging.md](design-wkwebview-messaging.md)

**Credential flow** is a good example of the no-fork principle in action: Swift reads the
API key from the macOS Keychain and injects it as an environment variable at sidecar
launch; the Python side just reads the env var via pydantic-settings, with no Mac-specific
code. Same pattern for the bundled FFmpeg path. Details in
[design-modularity.md](design-modularity.md) §"Credential stores" and
[design-desktop-python-runtime.md](design-desktop-python-runtime.md).

### 5. Model delivery: Background Assets (partly built)

Whisper models and large optional dependencies (PII / spaCy) are big enough that we don't
want them in the initial `.app` download. The plan is Apple **Background Assets** —
OS-scheduled, Wi-Fi-opportunistic, Apple-hosted downloads that "trickle in" after install
while the user is already productive. The acquisition strategy (and its many network
failure modes) is captured in
[design-modularity.md](design-modularity.md) §"Acquisition strategy: trickle to full
capability" — a plan, not a record. What exists in code today is the **handoff half** for
the PII model pack (`PIIModelPack.swift`: given a pack that has arrived, tell the sidecar
where it is); the per-channel acquirers (Background Assets for TestFlight/App Store, plain
HTTPS for the `.dmg`) land separately. Whisper-model delivery has no Background Assets code
yet. See [release-channels.md](release-channels.md) for the pack as an artefact.

### 6. Cross-cutting mechanisms

The sections above are the pieces; these are the mechanisms that run *through* them. Each
names where it lives and which doc owns the detail.

**Where state lives (four stores, one direction of trust).**

| Store | What it holds | Lives in |
|---|---|---|
| Files in the output folder | Pipeline output: transcripts, intermediate JSON, `pipeline-manifest.json`, `pipeline-events.jsonl`, logs | `<input>/bristlenose-output/` (`output_paths.py`) |
| SQLite (WAL, FKs on) | Pipeline JSON imported idempotently, plus every researcher edit (tags, stars, hidden quotes, names). Schema by SQLAlchemy models, migrated by Alembic | `<output>/.bristlenose/bristlenose.db`, one per project (`server/db.py`, `server/importer.py`, `server/alembic/`) |
| Browser stores | UI state: selection, focus, inspector, sidebar, undo; researcher edits are written through to the API | `frontend/src/contexts/` |
| macOS app state | Project index, run queue, bookmarks, Keychain credentials, handshake file | `desktop/Bristlenose/` (`ProjectIndex`, `RunQueue`, `KeychainHelper`, `MCPHandshake`) |

A study is identified by its database plus a marker id, not by a path — see
[design-project-identity.md](design-project-identity.md) and
[design-lifecycle-failure-modes.md](design-lifecycle-failure-modes.md) for what happens
across stash, restore, crash, rename and move.

**Run lifecycle and resilience.** Stages write a manifest as they complete so an interrupted
run resumes (`manifest.py`); `events.py` appends every run-level outcome to an NDJSON event
log that is the single source of truth for "what state is this run in"; `run_lifecycle.py`
and `server/lifecycle.py` own process start, signal handling and cleanup. The desktop
`ServeManager` supervises the sidecar and reaps orphans. Detail:
[design-pipeline-resilience.md](design-pipeline-resilience.md) and
[design-analysis-lifecycle.md](design-analysis-lifecycle.md) (analyse / re-analyse /
incremental).

**Reporting status honestly.** Messages that reach the user (pill, popover, sidebar glyph,
toast) use a fixed five-kind taxonomy (`ui_kinds.py`, mirrored by `MessageKind.swift`) so a
new failure fits an existing vocabulary instead of inventing a glyph —
[design-pipeline-diagnostic-popover.md](design-pipeline-diagnostic-popover.md).
`bristlenose doctor` and `preflight/` check the environment before a run.

**The trust boundary and auth.** Serve binds to `127.0.0.1` only, and a loopback-host
middleware refuses any other `Host` header (the DNS-rebinding gate). API routes require a
per-run bearer token (`server/middleware.py`; the SPA gets the same token injected, with a
cookie fallback for its own navigations only). `/media/` is deliberately outside the bearer
rule, because `<video>` cannot send the header; it is guarded by an extension allowlist and
path containment instead. `/mcp/` is bearer-only and, on the Mac, takes a separate scoped token that
opens nothing else — it is the one credential that deliberately leaves the trust boundary.
API keys sit in the Keychain on macOS (`credentials_macos.py`; Linux has
`credentials_linux.py`) and reach Python as environment variables. Participant data has its
own rules: PII redaction (stage 7, Presidio), and re-identification keys that never go into an
export — [consent-gradient.md](methodology/consent-gradient.md).

**LLM calls.** One client layer (`llm/client.py`) over six providers — Claude, ChatGPT, Azure
OpenAI, Gemini, local Ollama, and any-llm as an optional sixth — with structured output and
repair (`structured.py`), failure classification, per-call telemetry, cost and pricing, and an
untrusted-input boundary against prompt injection (`boundary.py`). Prompts are Markdown files
in `llm/prompts/`, versioned with an archive. Detail: `bristlenose/llm/CLAUDE.md`.

**Analysis layers on top of quotes.** `signals/` (pure-math concentration metrics, no LLM);
the codebook system (YAML frameworks in `server/codebook/`, `codebook_sync.py`, and the
AutoCode engine in `server/autocode.py` that proposes tags the researcher accepts or
denies); the discussion lens (`discussion/`, moderator questions and guide structure); and
the journey and sentiment views. Quote exclusivity — every quote in exactly one report
section — is enforced across stages 9–11.

**Media and screens.** FFmpeg for audio extraction and thumbnails; Whisper for transcription;
an optional voice pass to tell speakers apart (`s05b_voice.py`, the `voice` extra); on macOS
26+ an Apple Speech helper (`desktop/speech-helper/`) that the sidecar launches. The Screens
lens (`screen_text/`, Apple Vision through pyobjc) reads what was on the participant's shared
screen; the session tapestry draws scene colours and strips, which **serve** computes in the
background, never the pipeline. Screens never leave the machine on Bristlenose's own
initiative — [design-screens.md](design-screens.md).

**Import and export edges.** Cloud import from Zoom, Teams and Google Meet runs through native
OAuth (PKCE, `AuthenticationServices`) in the Mac app — [design-cloud-import.md](design-cloud-import.md);
file-provider placeholders are read with a bound, never skipped
([design-cloud-files.md](design-cloud-files.md)). Outbound: HTML export, CSV/XLS quotes,
clips, slides, Miro boards (`miro_client.py`, `MiroAPI.swift`), and FigJam
(`routes/figjam.py`, `figjam-plugin/`).

**Localisation.** The report and apps are localised through one set of locale files in
`bristlenose/locales/` (22 locale directories; `zh-Hant-HK` takes only real overrides),
consumed by i18next in the SPA, by Python at render time, and by Swift in the shell.
CLI terminal text is English by design. One language per exported deliverable —
[design-i18n.md](design-i18n.md), [design-export-locale.md](design-export-locale.md).

**Design system.** Atomic CSS (tokens, atoms, molecules, organisms, templates) in
`bristlenose/theme/`, shared with the desktop shell, with one appearance seam for light and
dark. The vanilla JS modules there are frozen, kept only for the sealed static renderer.

**Feature gating.** Five mechanisms, chosen by the question the gate answers: SPA parked-feature
flags, Swift compile-time conditions and `DistributionChannel`, runtime host detection,
`BRISTLENOSE_DEBUG_*` seeds, and the diagnostics preference —
[design-feature-flags.md](design-feature-flags.md).

**Quality gates.** Python (pytest, Hypothesis, Ruff, mypy), frontend (Vitest, ESLint with
jsx-a11y, a bundle-size budget), end-to-end (Playwright on Chromium and WebKit), the Swift
suite, and lifecycle and acceptance suites. Soft gates must declare a disposition (ratchet,
expiry or conditional) in `docs/testing/soft-gates.json`, enforced by
`scripts/check-gate-policy.py`; the release train is checked by `scripts/check-release-ready.sh`.
Map of what runs where: [docs/testing/README.md](testing/README.md) and
[design-ci.md](design-ci.md).

---

## How a release is cut

There are two release paths, because there are two kinds of artefact.

### CLI release (PyPI / Homebrew / Snap / Copr)

Ordinary day-to-day: commit to `main`, and when you want to ship, bump the version and
tag. Releases land after 9pm London on working days (any time on weekends and UK bank
holidays); the tag push is the act that publishes, so it goes last. While a
`release.sh run` is alive, a pre-commit hook freezes `main` locally, and work that must not
go live before the version is on PyPI waits on an `after-pypi/<version>` branch. Version lives in exactly one place — `bristlenose/__init__.py`
(`__version__`) — and `./scripts/bump-version.py` updates it plus the man page and the
pbxproj, and **stages them without committing or tagging** — it cannot tag
correctly, because the commit the tag belongs on does not exist yet (the
CHANGELOG and README prose come after the bump). It stopped tagging on 14 Aug
2026. You commit, then `git tag v<X.Y.Z>`, then push `main` and the tag as two
separate pushes — never `--tags`. `./scripts/release.sh plan|run|verify` does this in order.
GitHub Actions then does the rest: CI → PyPI publish → GitHub Release → Homebrew
tap dispatch → Copr build (after PyPI is verified fetchable — Source0 comes from there). Snap is
run by hand: the workflow's ref is the channel (`main` → edge, a `vX.Y.Z` tag → stable).

The full pipeline, secrets, cross-repo topology, and the mandatory **post-push PyPI
verification** step live in [release.md](release.md), the one-page channel map in
[release-channels.md](release-channels.md) (eight lockstep channels plus winget), and the "Releasing" section of
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
App Store *policy*, not signature validity (the `app-store-police` review agent checks them).
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

## Addendum: the tech stack, long tail

Everything the project depends on or builds with, grouped by layer. Versions are floors from
`pyproject.toml` and `frontend/package.json` as of this writing — read those for the live
values, and the comments beside the pinned ones for why they are capped.

### Python core

- **Language and shape:** Python 3.10+ (3.12 pinned in `.tool-versions`), Pydantic v2 models
  and `pydantic-settings` for config, Typer + Rich for the CLI, `inflect` for plurals,
  Jinja2 and PyYAML for the static renderer and codebooks.
- **Transcription and audio:** `faster-whisper` (CTranslate2) with PyAV (`av<19`) as the
  decoder; `mlx` + `mlx-whisper` on Apple Silicon (the `apple` extra); `huggingface-hub<2`
  for model downloads; FFmpeg and ffprobe as external binaries.
- **Voice pass (optional `voice` extra):** `onnxruntime` and `kaldi-native-fbank`.
- **Subtitles and documents:** `pysrt`, `webvtt-py`, `python-docx`, `openpyxl`.
- **PII:** `presidio-analyzer`, `presidio-anonymizer` with spaCy's `en_core_web_lg`
  weights (acquired on demand on the Mac, via `spacy download` on the CLI).
- **LLM SDKs:** `anthropic` (>=1, <2), `openai`, `google-genai`; optional `any-llm-sdk` with
  `mistralai`; Ollama over HTTP.
- **Serve mode:** FastAPI, Uvicorn (standard), SQLAlchemy 2 (asyncio extra), Alembic,
  SQLAdmin (dev-only browser), SQLite; optional `mcp>=2` for the MCP endpoint.
- **Text and layout:** `budoux` for Japanese and Chinese phrase breaks on boards; `certifi`
  as the trust store.
- **Screens (macOS):** `pyobjc-framework-Vision` and `-Quartz`.
- **Packaging extras:** `pyinstaller` (the `desktop` extra), `pip-licenses` and
  `cyclonedx-bom` (the `release` extra, for licences and the SBOM).

### Frontend

React 19, React Router 7, TypeScript 6, Vite 8 with a second, single-file Vite build for the
export. i18next with `react-i18next` and the browser language detector, `lucide-react`
icons, `lodash.deburr` for accent-folding search. Tests: Vitest, Testing Library, jsdom.
Lint: ESLint 9 with typescript-eslint, `jsx-a11y` and react-hooks rules. No UI framework or
state library: state is hand-rolled stores in `contexts/`.

### macOS app

SwiftUI plus AppKit, with WebKit's WKWebView hosting the SPA. Also Security (Keychain),
`AuthenticationServices` and PKCE for OAuth, CryptoKit, OSLog, AVFoundation, and a SQLite
Swift package. Two small Swift executables ship inside the bundle: the Apple Speech helper
and the MCP helper. The Node `.mcpb` proxy is the fallback. App Sandbox plus Hardened
Runtime, signed with an Apple Distribution identity for TestFlight and the App Store, with a
Developer-ID `.dmg` as a second lane. Sparkle is not used.

### Build and packaging

PyInstaller `--onedir` for the sidecar; `xcodebuild` archive and export; `altool` or
Transporter for upload; Hatch as the build backend; Homebrew tap (formula updated by a
workflow), Snap (`snap/`), Fedora Copr (`rpm/`, `.copr/`), Inno Setup and winget for
Windows (`packaging/windows/`), and a `.mcpb` bundle build.

### CI, security and supply chain

GitHub Actions: CI, release, CodeQL, secret and privacy scan (gitleaks), install smoke tests
on clean VMs, Mac build and release-archive rehearsals, perf (post-merge), i18n check,
mockup-register check, ratchet-tighten, Windows installer, Snap. Dependabot with a pin
register and the `cassandra` pre-mortem for bumps ([design-platform-policy.md](design-platform-policy.md)).
Pre-commit hooks: gitleaks, a tracked-vs-gitignore check, and the release freeze. Ruff and mypy
run in CI and by hand; `pip-licenses` and CycloneDX generate the licence list and SBOM.

### Testing and measurement

pytest (with xdist, asyncio and coverage), Hypothesis for round-trip and format contracts,
Playwright for end-to-end, and a Swift test target. Paid LLM tests are opt-in behind the
`slow` marker. `experiments/` holds throwaway research (colour lab, Apple speech, board
layout); `scripts/` holds the release machine, gate checkers and the perf harness.

### Repository layout, in one screen

`bristlenose/` Python core · `frontend/` SPA · `desktop/` Swift app, sidecar spec, helpers and
build scripts · `e2e/` Playwright · `tests/` pytest · `scripts/` release and gates ·
`docs/` design and methodology · `packaging/`, `snap/`, `rpm/`, `.copr/` channel packaging ·
`figjam-plugin/` FigJam export · `experiments/` prototypes · `trial-runs/` and
`docs/private/` (gitignored). Per-file detail: [file-map.md](file-map.md).

---

## Related maps

- [file-map.md](file-map.md) — where individual files live
- [CONTRIBUTING.md](../CONTRIBUTING.md) — dev setup, project layout, design system, release quick-start
- [ROADMAP.md](ROADMAP.md) — where things are going
- [design-modularity.md](design-modularity.md) — the canonical cross-channel component strategy
- [design-deployment-targets.md](design-deployment-targets.md) — macOS / Linux CI / Cloud VM boundaries
