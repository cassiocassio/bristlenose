---
status: current
last-trued: 2026-04-30
trued-against: HEAD@first-run on 2026-04-30
---

## Changelog

- _2026-04-30_ — Trued §"Local LLM" against Beat 3b shipped reality. Desktop GUI hardwires the Ollama URL to `localhost:11434` (commit `dbd54ec`) — editable field removed as a trust-boundary closure (paste-an-attacker-URL → silent transcript exfil). CLI/CI override path preserved via parent-process `BRISTLENOSE_LOCAL_URL` env var only. First-run detection / install / model-pull lives in `OllamaSetupSheet.swift` (Beat 3b, `07ee058`) — HTTP-only daemon probe, no `Process()` exec, no filesystem polling.

# Modular Packaging and Optional Components (CLI + macOS)

_Written 18 Apr 2026. Update when components are added, extras are restructured, or a platform mechanism changes._

## Purpose

Bristlenose ships as **one Python codebase** that is distributed via multiple channels: pip, Homebrew, Snap (Linux), and a macOS `.app` bundle (internal TestFlight today, Mac App Store later). Each channel has different capabilities for splitting the download into "essential now" and "optional later." This doc lists every splittable component, identifies which platform mechanism should acquire it, and enforces a load-bearing rule: **components are packaged differently per channel, but the Python code that uses them is single-source.**

## Glossary

- **Sidecar pattern** — the architecture choice: Python runs in a separate child process spawned by the Swift app, communicating via IPC (HTTP on localhost in our case).
- **Sidecar bundle** — the artefact: a PyInstaller `--onedir` directory shipped inside `Bristlenose.app/Contents/Resources/bristlenose-sidecar/`.
- **Sidecar binary** — the executable inside the bundle: `bristlenose-sidecar/bristlenose-sidecar`, the Python entry point that runs `bristlenose serve`.
- **Launcher pattern** — the alternative the v0.2 dev shell currently uses: the Swift app searches the user's `$PATH` and venv directories for an installed `bristlenose` CLI rather than carrying its own. Useful for dev iteration; not shippable to TestFlight or App Store.
- **External dev server** — a `bristlenose serve` process started independently (e.g. in a terminal via `bristlenose serve --dev`). The Mac app can connect to it instead of spawning its own sidecar by setting the `BRISTLENOSE_DEV_EXTERNAL_PORT` env var (or picking the "Bristlenose (External Server)" scheme in Xcode). Debug-only; stripped from Release via `#if DEBUG`. Used for fast CSS/React iteration with live endpoints + Vite HMR. See `desktop/CLAUDE.md` "Dev workflow."
- **Dev sidecar** — a developer's venv-installed `bristlenose` binary that the Mac app spawns instead of the bundled sidecar. Set via `BRISTLENOSE_DEV_SIDECAR_PATH` env var (or the "Bristlenose (Dev Sidecar)" scheme). Debug-only. Exercises the full subprocess-spawn flow against Python code you can edit in place, without rebuilding the PyInstaller bundle on every save.

## Principle

**No code fork between CLI and desktop.** Differences live in:

- `pyproject.toml` extras (what pip installs)
- PyInstaller spec (what gets bundled in the `.app`)
- Runtime resource-lookup functions (where to find Whisper models, FFmpeg, etc.)
- Platform-native acquisition UI (Background Assets vs. first-run download vs. pip install)

They do **not** live in separate stage logic, separate pipeline branches, or Mac-only Python modules. If a feature requires Mac-only Python code, the fix is to move the platform difference into Swift (env-var injection, bundle path resolution) rather than fork the Python.

**Prefer macOS-native mechanisms when available**, but only when they don't force duplication. If CLI needs the same optionality and there's a good cross-platform pattern, use one pattern and layer macOS chrome on top.

## Component inventory

### Always essential (every channel, every platform)

| Component | Size | Notes |
|---|---|---|
| Python runtime (3.10+) | ~30 MB | Bundled in Mac `.app`; system Python for CLI |
| `bristlenose` package | ~2 MB | The source code |
| `pydantic`, `pydantic-settings` | ~5 MB | All data models |
| `typer[all]` + `rich` | ~8 MB | CLI chrome and progress |
| `jinja2` | ~1 MB | HTML rendering |
| `pyyaml` | ~1 MB | Config and codebook formats |
| `pysrt`, `webvtt-py`, `python-docx` | ~3 MB | Subtitle + document parsing |
| `anthropic`, `openai`, `google-genai` SDKs | ~15 MB combined | User picks a provider at runtime; all three ship because switching is per-project |
| React bundle (static HTML/JS/CSS) | ~2 MB gzipped | Built at release time, shipped as assets |

**Total essential baseline:** ~65–70 MB.

### Serve mode (essential for desktop, optional for CLI)

| Component | Size | Mechanism |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | ~15 MB | `[serve]` extra on CLI; bundled in Mac sidecar |
| `sqlalchemy`, `sqladmin`, `alembic` | ~15 MB | Same |
| `openpyxl` | ~10 MB | Quotes export to `.xlsx` |

CLI users who only run `bristlenose run <folder>` don't need these. Mac desktop requires them (serve is the sidecar entry point).

### Transcription backends (optional, hardware-dependent)

| Backend | Platforms | Size | Acquisition |
|---|---|---|---|
| `faster-whisper` + `ctranslate2` | All | ~60 MB code (ex-models) | Base dependency on CLI. **Excluded from Mac sidecar PyInstaller spec** — Mac uses MLX. |
| `mlx` + `mlx-whisper` | Apple Silicon only | ~25 MB | `[apple]` extra on CLI; bundled in Mac sidecar |
| External APIs (OpenAI Whisper API, Groq) | All | 0 (HTTP only) | Base — no extra deps |

Backend selection at runtime (`BRISTLENOSE_WHISPER_BACKEND=auto`) picks whichever is importable. Same selector code on CLI and desktop — the sidecar just doesn't include ctranslate2 to import.

### Transcription models (large, optional)

| Model | Size | Acquisition (Mac) | Acquisition (CLI) |
|---|---|---|---|
| `small.en` | 461 MB | **Background Assets — Essential** (downloads before first launch) | HuggingFace on first transcription |
| `small` (multilingual) | 480 MB | **Background Assets — Essential** (if user's UI language ≠ English) | Same |
| `medium` | 1.5 GB | **Background Assets — Non-Essential** (Settings → "Use medium model") | Same |
| `large-v3-turbo` | 1.5 GB | **Background Assets — Non-Essential** | Same |

**Model lookup function** (single-source, platform branches inside): env var `BRISTLENOSE_WHISPER_MODEL_DIR` → Mac `~/Library/Application Support/Bristlenose/models/<model>` → Linux `$XDG_DATA_HOME/bristlenose/models/<model>` → HuggingFace cache `~/.cache/huggingface/hub/` → download. Call sites don't know which branch fires.

### PII removal (opt-in, heavy)

| Component | Size | Acquisition (Mac) | Acquisition (CLI) |
|---|---|---|---|
| `presidio-analyzer`, `presidio-anonymizer` | ~100 MB | **Background Assets — Non-Essential**, acquired when user enables PII | `pip install bristlenose[pii]` |
| `spacy` code | ~50 MB | Same | Same |
| `en_core_web_lg` spaCy model | ~400 MB | Same (or bundled inside the PII asset pack) | Installed via spaCy on CLI |

**Migration needed:** today presidio + spaCy are in `dependencies` (base install). Move them to a new `[pii]` extra so CLI users opt in, and exclude them from the Mac sidecar PyInstaller spec by default.

Awkwardness: Background Assets natively targets data files, not Python packages. Mechanism for Mac: ship presidio + spaCy as a pre-built wheel-archive asset pack; unpack into a writable Application Support path; extend `sys.path` from the sidecar's startup. Complex but doable. For alpha (friends only), just bundle them unconditionally and accept the download size — defer the on-demand work to public beta.

### Media tools

| Component | Size | Acquisition (Mac) | Acquisition (CLI) |
|---|---|---|---|
| FFmpeg + ffprobe (trimmed: h264/aac/opus/prores) | ~25 MB | **Bundled in `.app`** at `Contents/Resources/bin/` | User installs via Homebrew/apt/dnf |
| FFmpeg + ffprobe (kitchen-sink, all codecs) | ~70 MB | Not used — trimmed build is enough | System install on CLI |

**Path lookup function** (single-source): env var `BRISTLENOSE_FFMPEG_PATH` → Mac `Bundle.main.resourceURL/bin/ffmpeg` (Swift passes this via env) → `shutil.which("ffmpeg")`. CLI falls through to `shutil.which`; desktop sidecar gets the bundle path via env var from Swift. No platform branching in the call sites.

### Local LLM (optional, both platforms)

| Component | Size | Acquisition (Mac) | Acquisition (CLI) |
|---|---|---|---|
| Ollama binary | ~2 GB | **Not bundled.** User installs from ollama.com | Same |
| Ollama models (llama3, etc.) | 4–70 GB | Downloaded by user via `ollama pull` | Same |

**Code side:** detect Ollama via HTTP GET `http://localhost:11434/api/tags` on both platforms. Drop all `subprocess.run(["ollama", …])` calls (sandbox blocks on Mac, no benefit on Linux). UX if not detected: the Mac desktop ships `OllamaSetupSheet.swift` (Beat 3b) which opens `https://ollama.com/download` in the system browser and polls daemon reachability with a 120 s timeout + URLError catalogue (no internet / timed out / cannot connect). The CLI surfaces the same probe via `bristlenose doctor`. Single HTTP code path; sandbox-clean and Homebrew-friendly.

**Desktop URL hardwire (alpha):** the Mac GUI's Settings tab shows the Ollama URL as a static read-only display (`http://localhost:11434/v1`) — no editable field. CLI users keep the override via the `BRISTLENOSE_LOCAL_URL` env var; the Mac sidecar honours it only when present in the *parent process* environment (`ServeManager.swift:351-357`). This closes the trust-boundary footgun where a social-engineered user could be tricked into pasting an attacker URL — see `design-desktop-security-audit.md` Finding #12.

### UI locales

Tiny (~100 KB per language). Bundle all 6 (en, es, fr, de, ko, ja) on every channel. No optionality needed.

### Credential stores (platform-native, no fork)

| Platform | Mechanism | Python code |
|---|---|---|
| macOS desktop sidecar | Swift reads Keychain via `SecItemCopyMatching`; injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars at subprocess launch (C3, Apr 2026) | Python reads via pydantic-settings, no Keychain call |
| macOS CLI | `/usr/bin/security` CLI wrapper in `credentials_macos.py` | Unchanged |
| Linux CLI | `libsecret` via `secretstorage` package | Platform-conditional import |
| Windows CLI | Future — `keyring` package's win32 backend | Same pattern |

The **env-var injection** pattern for the desktop sidecar is the key insight: it keeps the Python side free of Mac-specific code. Credential lookup function: env var → platform-native CLI (Mac `security`, Linux libsecret). Desktop doesn't need to import `pyobjc-framework-Security`. See [`design-desktop-python-runtime.md`](./design-desktop-python-runtime.md) §"Credential flow" for the end-to-end sequence (Keychain → Swift → env → pydantic-settings) and residual risks.

### Development / testing deps

`[dev]` extras (`pytest`, `ruff`, `mypy`). Never bundled. Installed by contributors only.

## Acquisition mechanisms by channel

> **Distribution decision (28 Apr 2026).** The macOS `.app` ships **App Store only** (alpha, beta, and early commercial). Direct download via Developer ID + notarytool + Sparkle is **not** maintained as a parallel channel — it's deferred until the App Store cut becomes material relative to the cost of running a parallel direct-distribution channel (memo trigger: ~10k paying users, or first enterprise MDM ask). Today's `desktop/scripts/build-all.sh` produces a `.pkg` for App Store Connect upload via Transporter / `xcrun altool --upload-app`. No `.dmg`. No Sparkle. Pricing via Apple In-App Purchase, not Stripe — App Store handles payments, tax, refunds, chargebacks, IAP infrastructure, and a chunk of trust signal that an indie can't manufacture cheaply.

### macOS `.app` (TestFlight / App Store)

| Mechanism | When | Size limit | Used for |
|---|---|---|---|
| Bundled in `.app` | Initial download | — (but affects install-time footprint) | Python runtime, bristlenose code, FFmpeg, core Python deps, small.en Whisper if shipping offline-first, UI locales |
| [Background Assets — Essential](https://developer.apple.com/documentation/BackgroundAssets/downloading-essential-assets-in-the-background) | Before first launch (parallel to install) | `BAEssentialDownloadAllowance` (typically 2 GB or more; Apple-tunable) | Whisper `small.en` model if not bundled |
| Background Assets — Non-Essential | On user action (e.g. Settings toggle) | Per-asset-pack limits apply | Larger Whisper models, PII asset pack, future add-ons |
| [Apple-Hosted Background Assets](https://developer.apple.com/help/app-store-connect/manage-asset-packs/overview-of-apple-hosted-asset-packs/) | Any of the above | Apple's hosting quota | All of the above — no CDN required |
| First-run `~/Library/Application Support/` download | Any time | None | Fallback only — Background Assets is preferred on App Store distribution |

**Rule:** if Apple can host it, let Apple host it. Apple-Hosted Background Assets wins on signing, trust, CDN, resumability, storage management, and Privacy Manifest posture. Roll-your-own downloads are for cases Background Assets can't cover (e.g. extending `sys.path` with downloaded Python packages — still needs manual unpack but the asset can still be delivered via Background Assets).

### macOS `.dmg` — deferred (not "rejected"; revisit at ~10k paying users)

Would have shipped via Developer ID + notarytool + Sparkle for in-app updates. Status updated 28 Apr 2026 from "rejected" to "deferred" per the distribution-decision callout above. The Sparkle/notarytool flow is preserved as a future-state subsection in `docs/design-desktop-python-runtime.md` §"Deferred — Developer ID flow". Re-add this row to the active mechanisms table when the trigger conditions fire.

### macOS Homebrew (CLI)

Formula installs with `[apple]` extras by default → Mac CLI users get MLX without thinking. FFmpeg is a Homebrew bottle dependency. Whisper models download on first transcription via `huggingface_hub`. Optional PII via `brew install bristlenose --with-pii` (custom option, or separate `bristlenose-pii` formula).

### Linux Snap (CLI)

Snap base install. FFmpeg via `snap install ffmpeg` or strict-confinement `slots`. No MLX (no Apple Silicon Linux). Whisper via `huggingface_hub`. PII via `pip install --user bristlenose[pii]` inside the snap — awkward in classic confinement, fine in strict mode if we plumb it.

### pip (any platform)

`pip install bristlenose` base + extras: `[serve]`, `[apple]` (Mac Apple Silicon), `[pii]`, `[dev]`. Users compose what they need. Whisper via `huggingface_hub` on first use.

## Decision matrix: which mechanism for which component

| Component | macOS alpha (TestFlight) | macOS App Store | Homebrew (Mac) | pip (any) | Snap (Linux) |
|---|---|---|---|---|---|
| Python runtime | Bundled | Bundled | System Python | System Python | Snap-confined Python |
| Core `bristlenose` | Bundled | Bundled | Formula | Base install | Snap base |
| `[serve]` deps | Bundled | Bundled | Formula | `[serve]` extra | Snap base |
| MLX + mlx-whisper | Bundled | Bundled | Formula (`[apple]` default) | `[apple]` extra | — |
| faster-whisper + ctranslate2 | **Excluded from bundle** | Excluded | Formula | Base install | Snap base |
| FFmpeg | Bundled (trimmed) | Bundled (trimmed) | Bottle dep | User install | Snap connection |
| Whisper small.en | Bundled or Essential Background Asset | Essential Background Asset | `huggingface_hub` on first use | Same | Same |
| Whisper medium / large-v3-turbo | Non-Essential Background Asset | Non-Essential Background Asset | Same | Same | Same |
| presidio + spaCy + en_core_web_lg | Bundled for alpha; Non-Essential Background Asset for public beta | Non-Essential Background Asset | `[pii]` extra | `[pii]` extra | Same |
| Ollama | Not bundled, HTTP-detected | Same | Same | Same | Same |
| UI locales | Bundled | Bundled | Bundled | Bundled | Bundled |

**Reading the table:** the row is a component, the column is a distribution channel, the cell is the acquisition mechanism. Every cell in a row should be *possible with the same Python code* — only the acquisition differs.

## Implementation rules

1. **Single lookup function per resource.** `find_whisper_model()`, `find_binary("ffmpeg")`, `get_credential("anthropic")`. Platform branching lives inside these functions, not at call sites.
2. **Env-var injection first.** If Swift can fetch / resolve / locate something and pass it via env var, let Swift do it. Python reads env. No Mac-specific Python code.
3. **PyInstaller spec decides what's bundled.** Drop deps the desktop doesn't need from the `hiddenimports` list. Don't add a Mac-specific import-branch in Python.
4. **Extras are the CLI equivalent of "optional bundle components".** Every feature that's Non-Essential on Mac should be an extra on CLI (`[pii]`, `[whisper-fat]` for larger models if we end up needing one, etc.).
5. **Prefer `huggingface_hub` cache paths on Linux/Windows, Background Assets on Mac.** The lookup function checks Application Support → HuggingFace cache → download in that order. CLI never touches Application Support (empty); Mac finds it there first.
6. **No new Mac-only Python dependency without reviewing this doc first.** If you're tempted to add `pyobjc-framework-Security` or similar, first ask whether Swift can do the work and hand the result to Python.

## Migration from current state (18 Apr 2026)

`pyproject.toml` today:
- `dependencies` includes `faster-whisper`, `presidio-analyzer`, `presidio-anonymizer` as base
- `[apple]`: mlx, mlx-whisper
- `[serve]`: FastAPI + SQLAlchemy stack
- `[dev]`: testing + mlx (conditional on platform)

Proposed:
- Move `presidio-analyzer`, `presidio-anonymizer` out of base into new `[pii]` extra
- Keep `faster-whisper` in base (cross-platform CLI default)
- Exclude `faster-whisper` + `ctranslate2` from Mac sidecar PyInstaller spec via `excludes` rather than removing from base deps
- Exclude `presidio-*` + `spacy` from Mac sidecar PyInstaller spec for alpha (bundle them), and for public beta move to Non-Essential Background Asset
- Add `[whisper-external]` extra for thin HTTP-only Whisper API clients if we ever want a no-local-transcription install path
- Add docs on which channel uses which extra set

**Order of work:**
1. (Track C C1) Write PyInstaller spec that includes only `[apple]`-style transcription, excludes presidio/spaCy — targeted bundle ≤ 200 MB before Whisper. **Reality check (C0, 18 Apr 2026):** the shipped spec landed at **644 MB**, not 200 MB — torch (288 MB), llvmlite (110 MB), onnxruntime (58 MB), and scipy (37 MB) came in as transitive pulls via `tiktoken`/`transformers`/`numba`/`librosa`. The gap is absorbed by the trickle-to-full-capability strategy below (Background Assets for Whisper models + future optional deps) rather than by build-time trimming. Revisit if TestFlight reports cite install size as friction; for alpha, the bundle ships as-is. See `design-desktop-python-runtime.md` §"Bundle-size findings" for the transitive-pull table.
2. (Track C C1) Write `bristlenose-sidecar[pii]` asset pack for Background Assets — deferred to public beta.
3. (separate pyproject refactor) Move presidio to `[pii]` extras. Update Homebrew formula to install without PII by default.
4. (post-100-days) Implement runtime `sys.path` extension for downloaded PII asset pack on Mac.

## Open questions

- **Whisper base model choice.** `small.en` (English only, 461 MB) or `small` (multilingual, 480 MB)? For alpha friends, `small.en` is fine — they're English-speaking. For public beta with multi-language UI, default to `small` and offer `small.en` as a download for English-only users who want the ~5 % accuracy bump.
- **PII asset-pack Python-packages-as-data problem.** Bundling presidio + spaCy as a wheel-archive Background Asset needs a startup hook that extracts and extends `sys.path`. Prototype before committing. Fallback: bundle presidio in `.app` for public beta too, accept the extra 600 MB. Decide during Track C C1.
- **Snap optional extras.** Snap strict confinement makes `pip install --user` awkward. Either add every optional component to the snap base (defeats the point) or design a confinement-compatible opt-in mechanism. Defer to post-100-days.
- **App Store reviewer stance on Background Assets for PII ML models.** Apple may flag a 500 MB spaCy model as "non-public ML model of user-controlled inference." Worth a spike before committing the public-beta design.
- **Homebrew `[pii]` flag mechanism.** Homebrew doesn't natively support feature flags — convention is separate formulae (`bristlenose` vs `bristlenose-pii`) or post-install `pip install bristlenose[pii]` into the brew-installed venv. Decide when the PII extras land.

## Acquisition strategy: trickle to full capability

**Headline metric: time from "see" to "try."** How long between the user deciding to install Bristlenose and them doing something real with it — opening a project, reading a report, entering an API key, kicking off an analysis. That's the number we optimise. PlayStation-style "wait 20 minutes for the update to finish" is the anti-pattern — nobody cares that the console did updates while they slept, they just remember the time they couldn't play.

**The canonical reference is Naughty Dog on the original PlayStation.** Crash Bandicoot streamed later-level graphics off the CD during earlier levels — the disc was spinning the whole time the player was jumping on crates, and by the time they reached a new area the textures and geometry were already in RAM. Load screens existed but were shortened to near-invisibility because the boring data-moving work happened behind the gameplay. That's the pattern: the user is already playing while the rest of the app arrives.

**The same principle inside the running app.** Modern apps (Sketch, Linear, Things, Notion, today's Photoshop) open into a usable state in under a second and lazy-load extra capability on demand. The 2003-Photoshop pattern — multi-minute cold start while every filter, brush engine, and codec loads up front "in case you need it" to crop a photo — is what we're explicitly avoiding. Inside the sidecar, this means **lazy-importing heavy provider SDKs** (`anthropic`, `openai`, `google-genai`, `mlx_whisper`) inside the functions that use them, not at module top. See `bristlenose/llm/CLAUDE.md` for the convention.

Everything else in this section follows from that metric. We minimise install-time footprint so the App Store → launch → doing-something sequence is short, we let the heavy bits arrive in the background while the user is already productive, and we don't load anything in-process until the user reaches for it.

**Strategy.** First install is the "starter" — just enough to launch the app and do something useful. The rest of the app's capabilities **trickle in automatically** over minutes to an hour after install, exploiting Background Assets' ability to schedule downloads at opportune times (Wi-Fi, on charger, low system load). By the time the user has finished onboarding, entered their Claude API key, and picked their first project folder, the heavy components (Whisper model, maybe PII) are already on disk. If they never use those features, nothing was wasted because the downloads are OS-scheduled and respect system constraints.

This is how Apple's own apps behave — Logic Pro ships with a basic sound library and trickles in additional orchestral packs, jam packs, drummer loops over hours-to-days on good Wi-Fi. iMovie is similar with effects. Neither asks the user to wait.

### Tiering

| Tier | Component | Size | Acquisition | When |
|---|---|---|---|---|
| **0** (install-time) | Python runtime, bristlenose core, provider SDKs, React bundle, FFmpeg (trimmed), UI locales | ~100 MB | Bundled in `.app` | At App Store / TestFlight install |
| **1** (BA Essential) | Whisper `small.en` if UI locale is English, `small` multilingual otherwise | ~460 MB | [Background Assets — Essential](https://developer.apple.com/documentation/BackgroundAssets/downloading-essential-assets-in-the-background) | In parallel with install; app launches when ready |
| **2** (BA Non-Essential, auto-triggered) | Opposite-locale Whisper (e.g. `small` if English Tier 1, `small.en` if not), presidio+spaCy for PII if user enabled it pre-first-launch | ~600 MB each | Background Assets — Non-Essential, system-scheduled | Trickled over minutes-to-hours post-install, good Wi-Fi, opportune times |
| **3** (on-demand, user-initiated) | `medium`, `large-v3-turbo` Whisper models | 1.5 GB each | Background Assets — Non-Essential, manually queued | User toggles in Settings → "Use larger model" |

Tier 0 is the only tier that's definitely on disk the moment the app opens. Tiers 1+ may be in-flight; the served HTML or a native banner communicates status if the user tries a feature before its tier is resolved.

### Conditions Background Assets honours automatically

- **Wi-Fi vs cellular.** System's "Low Data Mode" and per-network metered flags defer non-essential downloads off cellular/metered automatically.
- **Power state.** Large downloads can be deferred until on charger via `NSURLSessionConfiguration.networkServiceType` and BA's scheduling hints.
- **System load.** OS picks quiet moments.
- **Thermal state.** Hot Mac → defer.
- **User-initiated override.** "Download now" button bypasses the scheduler for Tier 2/3.

We should not reimplement any of this. Checking `NWPath.isExpensive` / `isConstrained` in Python is a fork-principle violation — Swift already reads those signals and BA respects them.

### User controls (one-time setup + Settings panel)

Proposed Settings → Advanced → Downloads (native SwiftUI, not HTML):

- **Download optional components automatically on Wi-Fi** (default: on)
- **Allow automatic downloads on cellular / metered networks** (default: off)
- **Only download while charging** (default: off)
- **Manage downloaded content** (list + delete per-item)

macOS already exposes these as system-level preferences (Wi-Fi → Low Data Mode, per-network "Consider as metered"), so BA honours them without us implementing the policy. The Settings panel exposes *app-local* preferences on top (e.g. "don't auto-download models I haven't chosen").

### First-run permission

Apple's pattern (Logic Pro, iMovie): show a sheet on first launch — "Bristlenose will download additional components over the next hour to give you full transcription capability. Use Wi-Fi only by default. Change in Settings." Single Got it button. No further pestering.

Don't ask per-asset — too noisy. Default to "yes, auto-download on Wi-Fi" because that's the least-surprise behaviour; users who want more control find the Settings panel.

### CLI equivalent

No trickle mechanism — CLI install is fixed at `pip install` time. The `bristlenose doctor` command can suggest post-install acquisitions ("Whisper `small.en` not found — download now? [Y/n]") but that's reactive, not scheduled.

This is a packaging difference, not a code fork. The model-lookup function returns the same "not available" result on both platforms; the *reaction* differs (Mac silently waits for BA; CLI prompts on next `doctor` run or next transcription attempt).

### Interaction with failure modes (see below)

Trickle doesn't eliminate the failure modes — it amortises them. Over an hour of opportunistic downloads, most transient problems (slow network, corporate firewall) will either resolve or become a persistent issue the user is aware of by the time they try to transcribe. Silent-until-needed is the right default; Settings surfaces the state if the user asks.

## Failure modes (capture only, don't design here)

Acquiring optional components over a network is a nightmare of partial states. The full UX design is deferred to a separate doc when implementation begins. The list below exists so future-us can't pretend the failures don't happen. **Invariant across all of them:** out-of-the-box functionality must not be compromised — if a non-essential asset is unavailable for any reason, the user should still be able to do *something* useful with the app (LLM-only analysis on a pre-existing transcript, browse a previous report, edit codebooks, export). Only features that genuinely require the missing asset should fail, and they should fail with a clear, recoverable error.

### Network absent or unusable

- **No network at all.** Aeroplane mode, ethernet unplugged, Wi-Fi off. Distinguish from "tried but failed" — different message.
- **Captive portal.** Hotel / café Wi-Fi shows a login page instead of the resource. HTTP returns 200 but body is HTML, not the asset. Hard to detect without trying.
- **Corporate firewall — outbound blocked.** Whitelist-only environments. Apple's CDN may or may not be on the list. HuggingFace, GitHub, almost certainly aren't.
- **Corporate firewall — TLS interception (MITM).** Org-issued root CA in the trust store. Some Python TLS stacks honour it, others don't. Background Assets honours system trust by default.
- **Proxy required (no auth, with auth, transparent, PAC-file).** All four are different. Apple BA respects system proxy; `huggingface_hub` may or may not depending on env vars.
- **VPN dropped mid-download.** Network "still there" but routing shifted; in-flight TCP connections die.
- **Network changed mid-download** (Wi-Fi → Ethernet, joined new SSID). BA generally handles; ad-hoc downloads may not.
- **Metered connection (cellular tether, mobile hotspot).** User may not want a 600 MB download right now. macOS has a "low data mode" signal we should respect for non-essentials.

### Network present but slow / silent

- **Slow network looks like nothing is happening.** Need progress indication that distinguishes "downloading slowly" from "stuck."
- **No ETA possible.** First few KB are unreliable for predicting total time. Show "Downloading… (X MB of Y MB)" without false-precision time estimate until ≥30 s of data.
- **Stalled download.** Bytes-per-second drops to zero for N minutes. BA may eventually retry; user wants to know now.
- **Background-only progress.** User quit app mid-download, BA continued, user re-opens → progress should reflect actual state, not start from zero.
- **"Try again later" UX.** Some downloads are non-urgent (larger Whisper). User dismisses; we don't pester. System should know not to retry constantly.

### Endpoint problems (server-side)

- **DNS moved or unreachable.** `huggingface.co` → `huggingface.com` cutover, NS resolution failure, ISP DNS blocking.
- **Endpoint dead.** Apple BA CDN regional outage, HuggingFace down, our own CDN gone (we don't have one — Apple-hosted protects us here).
- **Endpoint exists but returns 5xx.** Transient overload. Retry later.
- **Endpoint exists but returns 4xx.** Resource missing, renamed, requires new auth, deprecated path.
- **TLS cert expired on endpoint side.** Rare for Apple, common for self-hosted. If our `fetch-ffmpeg.sh` URL's cert expires, fetch script breaks.
- **Edge propagation delay.** Newly published asset hasn't reached every CDN node. User in region X gets 404; user in region Y is fine.

### Resource problems (the file itself)

- **Resource missing.** URL was correct yesterday, gone today. SHA256-pinned downloads will fail loudly (good); unpinned will silently get a redirect to an error page (bad — looks like a real download until parsing fails).
- **Resource renamed.** HuggingFace model moved from `Systran/faster-whisper-small.en` to `mobiuslabsgmbh/faster-whisper-small.en`. Hard-coded URLs go stale.
- **Resource version mismatch.** App expects v3 of the model format; HF only has v2 or v4 now. Format-aware code should handle gracefully.
- **Newer version available.** App is happy with v3 but v4 is better — should we tell the user? Auto-upgrade? Prompt? Defer to next app release? (Apple BA handles this for asset-pack-versioned content; not for ad-hoc HF downloads.)
- **Signature mismatch / corruption.** Bytes arrived but SHA256 doesn't match. Retry once; if still wrong, surface as integrity error (could be supply-chain attack).
- **Apple-hosted asset still uploading.** Just-published asset pack hasn't propagated to all edge nodes — first few users may 404.

### Local environment problems

- **Disk full mid-download.** Partial file on disk; need cleanup + clear message.
- **Disk full at write-final-file step.** Download succeeded into temp; rename to final path fails.
- **Sandbox blocks the write path.** Should never happen on Mac if we use Application Support, but a regression in the entitlement set could re-introduce.
- **User deletes the asset manually.** Finder, `rm -rf`, "free up storage" tool. Next use should re-acquire transparently.
- **System purged the asset.** macOS storage pressure → BA evicted non-essential. Same recovery as above.
- **iCloud account rotated.** Sandbox container path may change; old downloads orphaned.
- **macOS version too old for BA APIs we use.** Deployment-target check should catch at install; runtime should refuse gracefully if it sneaks through.
- **App update changed the expected asset format.** Old downloaded model not compatible with new app code. Detect at load, re-acquire with new manifest.

### Time-based problems

- **Clock skew / wrong system time.** TLS certificate validation fails ("not yet valid" or "expired"). Both BA and `huggingface_hub` choke. User-visible error needs to suggest fixing the clock, not the network.
- **Apple Developer cert expired.** Codesigned app refuses to launch. Not a download failure but the user-visible symptom is similar.

### Mac-specific Background Assets quirks (per Apple forums)

- **`progress.cancel()` fails on second cancellation attempt** in some macOS versions. Re-trigger requires app restart in worst case.
- **Essential asset failed to download before first launch.** App opens, user expects functionality, asset isn't there. Need a graceful "still arriving" state.
- **Background Assets extension crashed.** Rare but possible; downloads stop silently. System will retry on next opportunity but no immediate user signal.
- **Asset pack uploaded but App Store Connect hasn't approved it.** Per-version validation can take hours. New users on app v1.4 trying to download a pack only approved for v1.5 → 404.

### CLI-specific failure modes

- **PyPI down or rate-limited.** `pip install` fails. User stuck.
- **HuggingFace Hub down.** First-use Whisper download fails. Existing users with cached models unaffected.
- **Snap store outage.** `snap install` fails on Linux.
- **Homebrew bottle 404.** Formula update referencing a not-yet-published bottle.
- **Python version mismatch.** User upgraded to Python 3.15; binary wheels not yet published. `pip install` fails to build.
- **Python venv corrupted by user action.** Out of our control; surface a `bristlenose doctor` recovery hint.
- **`huggingface_hub` cache permissions wrong.** User installed under sudo once, now their normal-user invocation can't write. Common after migration scripts.

### Cross-platform integrity invariants

- **Out-of-the-box functionality preserved.** App must launch, browse existing reports, accept LLM API keys, run LLM-only analysis on already-transcribed data, export reports — all without any optional download succeeding. Only transcription itself requires the Whisper model; only PII removal requires presidio.
- **Failed downloads are silent until they're not.** Don't pop a modal every retry. Surface only when (a) user explicitly initiated, (b) auto-retries exhausted, or (c) blocking a foreground action.
- **No silent corruption.** A failed download must not leave a half-file that gets used. Atomic rename or fail loudly.
- **Recoverable from any state.** "Reset all downloads" / "Re-acquire model" must always work. No state where the user has to reinstall the app.

### What this list isn't

This is not a design. The Track C C0/C1 work needs a separate UX-design pass (likely `docs/design-modular-acquisition-ux.md`) that maps each failure mode to a specific surface (native SwiftUI alert, served HTML banner, terminal stderr, silent retry) and a specific recovery path. Capture now so we can't pretend later we didn't know.

## Cross-references

- [`docs/design-desktop-python-runtime.md`](./design-desktop-python-runtime.md) — canonical desktop sidecar architecture (written 18 Apr 2026 as Track C C0 output; updated through C3). Read this for the credential flow, bundle-data requirements, validation gates, and fail-loud contracts
- [`desktop/CLAUDE.md`](../desktop/CLAUDE.md) — desktop app working notes; points here for cross-channel component decisions
- [`docs/private/sprint2-tracks.md`](./private/sprint2-tracks.md) — Track C scope
- [`docs/private/road-to-alpha.md`](./private/road-to-alpha.md) — TestFlight path
- [`docs/design-homebrew-packaging.md`](./design-homebrew-packaging.md) — Mac CLI formula
- [`docs/design-doctor-and-snap.md`](./design-doctor-and-snap.md) — Snap packaging
- [`docs/archive/design-llm-providers.md`](./archive/design-llm-providers.md) — provider SDKs (historical roadmap; all 5 phases shipped)
- [Apple Background Assets framework](https://developer.apple.com/documentation/backgroundassets)
- [Apple-Hosted Background Assets overview](https://developer.apple.com/help/app-store-connect/manage-asset-packs/overview-of-apple-hosted-asset-packs/)
