# Bristlenose

Open-source user-research transcript analysis.

Point Bristlenose at a folder of interview recordings – videos, audio or transcripts from Zoom, Teams or Google Meet. 

It transcribes, identifies moderators and participants, extracts good verbatim quotes, groups them by screen and theme. Filler words are stripped, editorial context is (sparingly) added `[thus]`. Emotion and strong language are preserved.

The (HTML) report aggregates all your interview quotes.

Click a timecode to watch the video of that quote. 

You can check a summary of unused quotes - to ensure nothing crucial was trimmed by the AI - typically ~20% or less of the original.

You can tag and star quotes to organise them. It auto-tags with sentiment analysis to help you identify moments of frustration or delight.

Filter your quotes, and export via CSV to your boards in Miro, Figjam, Mural or Lucidspark, or spreadsheet - for further analysis.   

Bristlenose transcribes locally, and can do the thematic analysis on a (built in) local LLM — but for speedy results you'll want an API key from Claude, ChatGPT, Gemini, or Azure OpenAI. For commercial work, check your org's policies on public LLM use.

Expect about $0.40 per hour of interview audio with Claude — provider costs vary.

Pre-release software, without warranty. All feedback welcome.  
<!-- TODO: screenshot of an HTML report here -->

Bristlenose is built by me, Martin Storey, a practising user researcher. It's free and open source under AGPL-3.0.

Help translate Bristlenose into your language on [Weblate](https://hosted.weblate.org/projects/bristlenose/) — see [TRANSLATING.md](TRANSLATING.md) for details.

Sidequest: [what is a Bristlenose?](https://www.theaquariumwiki.com/wiki/Ancistrus_sp)

---

## What it does

The report includes:    

- **Sections** -- quotes grouped by screen or task
- **Themes** -- cross-participant patterns, surfaced automatically
- **Tags** -- your own free-text tags with auto-suggest
- **Sentiment** -- AI-generated badges per quote
- **Charts** -- histogram of emotions across all quotes
- **User journeys** -- per-participant stage progression
- **Per-participant transcripts** -- full transcript pages with clickable timecodes, linked from the participant table
- **Clickable timecodes** -- jump to the exact moment in a **popout video player**
- **Starred quotes** -- star, reorder
- **Inline editing** -- fix transcription errors directly in the report
- **Editable participant names** -- click the pencil icon to name participants in-browser; export edits as YAML
- Filter and **export as CSV** into **Miro** and more
- **Keyboard shortcuts** -- j/k navigation, s to star, t to tag, / to search, ? for help; multi-select with Cmd+click or Shift+j/k for bulk actions
- **Codebook frameworks** -- import Nielsen's 10 Heuristics, Yablonski's Laws, Don Norman, Jesse James Garrett, or the Morville honeycomb, or build your own
- **AutoCode** -- LLM proposes tags from your codebook; review with a confidence threshold
- **Inspector panel** -- DevTools-style heatmaps and signal cards with Win/Problem/Niggle/Surprise flags
- **Word-level transcript highlighting** -- karaoke-style sync with video playback
- **Video clip extraction** -- export starred quotes as video clips (FFmpeg stream-copy)
- **Self-contained HTML export** -- one-click bundle for stakeholders, optional anonymisation
- **21 UI languages** -- en, es, fr, de, ko, ja, cs, it, pt-BR, pt-PT, zh-Hant, zh-Hant-HK, nl, fi, pl, ru, uk, da, sv, nb, tr (`--lang` flag; the nine most recent are machine-seeded community previews awaiting native review on [Weblate](https://hosted.weblate.org/projects/bristlenose/))


## Install

For LLM analysis, you can use **Claude**, **ChatGPT**, **Azure OpenAI**, **Gemini**, or **Local AI** (free, via [Ollama](https://ollama.ai)) — see [Getting an API key](#getting-an-api-key) below.

### macOS (desktop app) — easiest

Download **[Bristlenose.dmg](https://github.com/cassiocassio/bristlenose/releases/latest)**, drag to Applications, open it. The app prompts for your Claude API key on first launch and bundles everything else (Python, FFmpeg, Whisper). No terminal needed.

First launch: macOS will block it — go to **System Settings → Privacy & Security**, scroll down, click **"Open Anyway"**. One time only.

Requires macOS 15 Sequoia, Apple Silicon (M1+).

### macOS (Homebrew), Linux, Windows

Requires Python 3.10 or newer.

```bash
# macOS (Homebrew) -- handles ffmpeg + Python for you
brew install cassiocassio/bristlenose/bristlenose

# Linux / macOS / Windows (pipx or uv)
pipx install bristlenose
uv tool install bristlenose    # alternative
```

If using pipx or uv, you'll also need FFmpeg (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu, `winget install FFmpeg` on Windows).

If you have Anaconda installed, its bundled Python may shadow newer system Pythons. Either `conda deactivate` before running pip/pipx, or install via Homebrew (which uses its own bundled Python 3.12).

After installing, run `bristlenose doctor` to verify your setup.

See the **[installation guide](INSTALL.md)** for detailed step-by-step instructions for your platform, including Python/FFmpeg setup and AI provider configuration.

---

## Getting an API key

If you've used Claude or ChatGPT before, you might only know the chat interface. Bristlenose talks to the same AI models, but through their **API** (a direct connection for software). This needs a separate API key -- a password that lets bristlenose call the AI on your behalf.

You need one key:

### Option A: Claude (by Anthropic)

1. Go to [console.anthropic.com](https://console.anthropic.com/settings/keys) and sign up or log in
2. Click **Create Key**, give it a name (e.g. "bristlenose"), and copy the key
3. Store it securely:

```bash
bristlenose configure claude    # validates the key and stores it in your system credential store
```

### Option B: ChatGPT (by OpenAI)

1. Go to [platform.openai.com](https://platform.openai.com/api-keys) and sign up or log in
2. Click **Create new secret key**, give it a name, and copy the key
3. Store it securely:

```bash
bristlenose configure chatgpt    # validates the key and stores it in your system credential store
```

To use ChatGPT instead of the default, add `--llm chatgpt` to your commands:

```bash
bristlenose run interviews -o results/ --llm chatgpt
```

### Option C: Azure OpenAI (enterprise)

If your organisation has a Microsoft Azure contract that includes Azure OpenAI Service:

```bash
export BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/
export BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name
bristlenose configure azure    # validates the key and stores it in your system credential store
bristlenose run interviews --llm azure
```

You'll need your endpoint URL, API key, and deployment name from the [Azure portal](https://portal.azure.com).

### Option D: Gemini (by Google)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign up or log in
2. Click **Create API key**, give it a name, and copy the key
3. Store it securely:

```bash
bristlenose configure gemini    # validates the key and stores it in your system credential store
```

To use Gemini instead of the default, add `--llm gemini` to your commands:

```bash
bristlenose run interviews -o results/ --llm gemini
```

**Budget option:** Gemini is 5–7× cheaper than Claude or ChatGPT — roughly $0.06 per hour of interview audio instead of $0.40.

### Option E: Local AI (via Ollama) — free, no signup

Run analysis entirely on your machine using open-source models. No account, no API key, no cost.

1. Install [Ollama](https://ollama.ai) (one download, no signup)
2. Run bristlenose — it will offer to set up local AI automatically:

```bash
bristlenose interviews

# Or explicitly:
bristlenose run interviews --llm local
```

If Ollama isn't installed, bristlenose will offer to install it for you (via Homebrew on macOS, snap on Linux).

**Trade-offs:** Local models are slower (~10 min vs ~2 min per study) and less accurate (~85% vs ~99% JSON reliability). Good for trying the tool; use cloud APIs for production quality.

Use whichever provider you already have an API key for. If you don't have one yet, Option A (Claude) is the default. A typical 8-participant study costs roughly $1--3 with any cloud provider ($0.20 with Gemini).

> **Note:** A ChatGPT Plus/Pro or Claude Pro/Max subscription does **not** include API access. The API is billed separately — you need an API key from [console.anthropic.com](https://console.anthropic.com) or [platform.openai.com](https://platform.openai.com).

### Making your key permanent

**macOS and Linux:** The recommended way is `bristlenose configure` (shown in Options A--D above). It validates your key and stores it in your operating system's secure credential store:

- **macOS** — saved to your **login keychain**. You can view or delete it in the Keychain Access app (search for "Bristlenose")
- **Linux** — saved via **Secret Service** (GNOME Keyring / KDE Wallet). Requires `secret-tool` to be installed (included by default on most desktop Linux distributions)

The key is loaded automatically on every run — no environment variables needed. Run `bristlenose doctor` to verify your key is detected (it will show "(Credential Store)" next to the API key check).

**Windows:** Credential store storage is not yet supported. Set the key permanently with `setx` (built into Windows):

```
setx BRISTLENOSE_ANTHROPIC_API_KEY "sk-ant-..."
```

For ChatGPT, use `BRISTLENOSE_OPENAI_API_KEY`; for Gemini, use `BRISTLENOSE_GOOGLE_API_KEY`. Close and reopen your terminal after running `setx` — the variable only takes effect in new windows.

**Alternative: shell profile (macOS/Linux).** If you prefer environment variables over the credential store, add the export to your shell startup file:

```bash
# macOS (zsh is the default shell):
echo 'export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc

# Linux (bash is the default shell on most distributions):
echo 'export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

Then open a new terminal window (or run `source ~/.zshrc` / `source ~/.bashrc`).

**Alternative: `.env` file.** Create a `.env` file in your project folder -- see `.env.example` for a template.

**Troubleshooting:** Run `bristlenose doctor` at any time to check your setup — it verifies your API key, FFmpeg, transcription backend, and other dependencies.

---

## Quick start

```bash
bristlenose interviews
```

That's it. Point it at a folder containing your recordings and it will produce the report inside that folder. Expect roughly 2--5 minutes per participant on Apple Silicon, longer on CPU.

Open `interviews/bristlenose-output/bristlenose-interviews-report.html` in your browser.

### What goes in

Any mix of audio, video, subtitles, or transcripts:

`.wav` `.mp3` `.m4a` `.flac` `.ogg` `.wma` `.aac` `.mp4` `.m4v` `.mov` `.avi` `.mkv` `.webm` `.srt` `.vtt` `.docx`

Files sharing a name stem (e.g. `p1.mp4` and `p1.srt`) are treated as one session. Existing subtitles skip transcription.

### What comes out

Output goes inside the input folder by default:

```
interviews/                              # your input folder
├── Session 1.mp4
├── Session 2.mp4
└── bristlenose-output/                  # output folder (created inside input)
    ├── bristlenose-interviews-report.html   # the report -- open this
    ├── bristlenose-interviews-report.md     # Markdown version
    ├── people.yaml                          # participant registry
    ├── assets/                              # static files (CSS, logos, player)
    ├── sessions/                            # per-session transcript pages
    │   ├── transcript_s1.html
    │   └── transcript_s2.html
    ├── transcripts-raw/                     # one .txt + .md per session
    ├── transcripts-cooked/                  # PII-redacted (only with --redact-pii)
    └── .bristlenose/                        # internal files
        └── intermediate/                    # JSON snapshots (re-readable by `bristlenose serve`)
```

Override the output location with `--output`: `bristlenose run interviews/ -o /elsewhere/`

### More commands

```bash
bristlenose run interviews -p "Q1 Usability Study"    # name the project
bristlenose transcribe interviews                        # transcribe, no LLM
bristlenose analyze interviews/bristlenose-output/transcripts-raw/   # skip transcription, run LLM analysis
bristlenose serve interviews                             # open a previous report (no analysis)
bristlenose status interviews                            # check project status (read-only)
bristlenose doctor                                       # check dependencies
bristlenose codebooks                                    # list AutoCode framework templates
bristlenose pipeline                                     # show which AI models each stage uses
```

### Configuration

Via `.env` file, environment variables (prefix `BRISTLENOSE_`), or `bristlenose.toml`. See `.env.example` for all options.

### Hardware

Transcription hardware is auto-detected. Apple Silicon uses MLX on Metal GPU. NVIDIA uses faster-whisper with CUDA. Everything else falls back to CPU.

---

## Roadmap

### Analysis

- **Your own themes** -- create, rename and reorder themes manually, not just the AI-generated ones

### Sharing

- **.docx export** -- download the report as a Word document
- **Edit writeback** -- save your in-browser corrections back to the transcript files on disk

### Platform

- **Windows installer** -- native setup wizard so you don't need Python or the command line
- **Cross-session moderator linking** -- recognise the same moderator across sessions (currently each session tracks moderators independently)
- **Snap Store** -- deferred. CI build is currently broken; will revisit after the macOS desktop alpha

Priorities may shift. If something is missing that matters to you, [open an issue](https://github.com/cassiocassio/bristlenose/issues).

---

## Get involved

**Researchers** -- use it on real recordings, open issues when the output is wrong or incomplete.

**Developers** -- Python 3.10+, fully typed, Pydantic models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the CLA, project layout, and design system docs.

**Help us test** -- we'd love feedback from people using bristlenose with:
- **Gemini** -- budget option at ~$0.06 per hour of interview audio
- **Azure OpenAI** -- enterprise deployments
- **Windows** -- the pipeline works but hasn't been widely tested
- **Linux** -- pipx works today; snap is deferred (CI build is currently broken)

---

## Development setup

Clone the repo, create a virtual environment, and install in editable mode:

```bash
# Prerequisites (macOS)
brew install python@3.12 ffmpeg pkg-config

# Clone and set up
git clone https://github.com/cassiocassio/bristlenose.git
cd bristlenose
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,serve,apple]"            # serve extra adds FastAPI/SQLAlchemy/uvicorn; apple adds MLX for Apple Silicon GPU acceleration (omit on other platforms)
cp .env.example .env                          # add your API key
```

On Linux, install `python3.12` and `ffmpeg` via your package manager. On Windows, use `python -m venv .venv` and `.venv\Scripts\activate`.

### Verify everything works

```bash
.venv/bin/python -m pytest tests/    # ~3500 Python tests; frontend has ~1300 Vitest tests (`npm test` in frontend/)
.venv/bin/ruff check .               # lint
.venv/bin/mypy bristlenose/          # type check (some third-party SDK errors are expected)
```

> **If you rename or move the project directory**, the editable install breaks silently
> (absolute paths baked into `.pth` files and CLI shebangs). Fix with:
> `find . -name __pycache__ -exec rm -rf {} +` then
> `.venv/bin/python -m pip install -e ".[dev]"`

### Architecture

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full project layout, but the short version:

- `frontend/` -- Vite + React + TypeScript SPA (the product UI in serve mode)
- `bristlenose/server/` -- FastAPI + SQLite + SQLAlchemy data layer behind serve mode
- `bristlenose/stages/` -- 12-stage pipeline (ingest through render), one module per stage
- `bristlenose/llm/` -- multi-provider client + prompt templates (Markdown)
- `bristlenose/locales/` -- 21 UI locales (en, es, fr, de, ko, ja, cs, it, pt-BR, pt-PT, zh-Hant, zh-Hant-HK, nl, fi, pl, ru, uk, da, sv, nb, tr)
- `desktop/` -- SwiftUI macOS shell that bundles a signed PyInstaller sidecar
- `bristlenose/pipeline.py` -- orchestrator that wires the stages together
- `bristlenose/cli.py` -- Typer CLI entry point
- `bristlenose/stages/s12_render/` and `bristlenose/theme/js/` -- legacy static-render scaffolding from the React migration; deprecated, on the deletion path

### Releasing

Edit `bristlenose/__init__.py` (the single source of truth for version), commit, tag, push. GitHub Actions handles CI, build, and PyPI publishing automatically. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Changelog

**0.19.1** — _10 Jul 2026_

- **Feedback survives a failed run.** When a run is cancelled or fails, the report gives way to a status page whose "Send feedback" link used to dead-end at "Method not allowed." Now the macOS app opens a native feedback sheet and the browser opens an inline form on the page — both sending the same anonymous `{rating, message}`, and both reporting "sent" only when the server confirms receipt, so a captive-portal `200 OK` can't silently swallow it; unconfirmed sends fall back to the clipboard. The reliability fix reaches the in-report form too. Browser form + reliability on PyPI; native sheet with the next bundled build.
- **Help opens the live docs.** The in-app Help overlay is retired in favour of the online documentation, which supersedes it. Help → Bristlenose Help and Keyboard Shortcuts open `bristlenose.app/docs` in the browser; Acknowledgements opens the open-source credits. Help you read _beside_ the report, not a modal over it (the `?` key reuses a single tab). Ships on PyPI and in the desktop app.

**0.19.0** — _4 Jul 2026_

- **Nine new locales — twenty-one languages in total.** Dutch (`nl`), Finnish (`fi`), Polish (`pl`), Russian (`ru`), Ukrainian (`uk`), Danish (`da`), Swedish (`sv`), Norwegian Bokmål (`nb`), and Turkish (`tr`) join the roster across the desktop app, web report, and CLI. Each is a machine-seeded community preview — complete against all nine namespaces, offered for native speakers to refine on [Weblate](https://hosted.weblate.org/projects/bristlenose/), with `fill-empty-only` seeding so contributed translations always win. Slavic 1/few/many/other plurals, East-Slavic `_one` retaining `{{count}}` because the form recurs at 21/31, Turkish formal register with `Vazgeç` for Cancel. New tooling — placeholder-union check, `_one` gate, pytest classification guard — catches regressions. Norwegian ships as Bokmål only (the `no → nb` fallback is an open follow-up).
- **Shoal — a live word-flock while your interviews are being analysed.** During a run, a SpriteKit flock of the words the pipeline is currently extracting drifts across the detail pane in the desktop app. Colour-graded by sentiment, respects Reduce Motion and a dedicated Appearance toggle. If the sidecar feed stalls it falls back to a canned word pool so the pane's never empty. Desktop-only; the Python-side sampler + i18n strings ship on PyPI.
- **Palette picker + Edo, end to end.** Settings → Display picks between **Default** (re-grounded on Apple's system values — system-blue accent, the neutral-grey AppKit selection capsule, 6 px corners, native inactive-window dimming) and **Edo** (Prussian-blue accent from the pigment's brilliant undertone, paper-white paper, passport-navy ink, warmer paper in dark mode). Native macOS pulldown, no restart, live switch via WKWebView bridge. Paints before first render (no flash). New `--palette` CLI flag boots straight into your preference. Ships on PyPI and in the desktop app.
- **Terminology fixes across four locales.** A glossary-consistency pass corrected drift in Japanese (Quotes 引用 → 発言), Korean (a typo, Accept 승인, Signals 시그널), German (Sessions → Interview, undo → Widerrufen, three _du_ → formal _Sie_), and Spanish (dropping the over-literal _Tubería_). Values only, verified against the locale-key tests. Ships on PyPI.
- **Supply-chain hardening.** Every release now attaches runtime-scoped CycloneDX SBOMs (Python + frontend) as GitHub Release assets, and binds the Python SBOM to the wheel + sdist with a Sigstore attestation. A gitleaks history scan runs on every push and PR; a tracked-vs-gitignore guard catches the class of `.env`-shaped accidents. No user-facing surface.
- **Lighter first paint.** Report tab views code-split into lazy per-tab chunks; landing bundle drops to ~213 kB.

**0.17.0** — _30 Jun 2026_

- **Five new locales — Portuguese, Italian, and Traditional Chinese.** Brazilian & European Portuguese (`pt-BR` / `pt-PT`), Italian (`it`), and Traditional Chinese for Taiwan and Hong Kong (`zh-Hant` / `zh-Hant-HK`) across the desktop app, web report, and CLI (Settings → Language) — twelve locales in all. Portuguese and Chinese each ship as a deliberate *pair* (a single code reads as foreign to one side — arquivo / ficheiro, _salvando_ vs. _a guardar_; Chinese is Traditional only, not Simplified). Each is a machine-seeded **community preview** for native speakers to refine on [Weblate](https://hosted.weblate.org/projects/bristlenose/); the seed is _fill-empty-only_, so contributed translations always win. Apple-HIG verbs + the research glossary seeded per language; new guard tests pin key parity, placeholders, and plural completeness.

**0.16.1** — _28 Jun 2026_

- **Send to Miro becomes a native macOS sheet, and shows exactly where the board will land.** On the desktop app the export moves into a native sheet with its own Keychain-held Miro connection, and names the connected account, workspace, and organisation plus the destination team before you push. The web report's Miro panel gains the same connected-account / workspace identity — `serve` users see it too. Desktop sheet next bundled-sidecar build; Miro-panel changes ship on PyPI.
- **Desktop Quotes toolbar: a native search field and a starred-only toggle.** The Quotes search and "starred only" filter are now native macOS toolbar controls (the tag dropdown is gone). Desktop-only — next bundled-sidecar build.
- **Fix: the native Miro export no longer 401s after switching projects.** The serve process resets its bearer token on a cold start, so the desktop app's token stays in sync with the freshly-booted server. The `serve` change ships on PyPI; the symptom was desktop-only.
- **Desktop embedded report hides the web sidebar rails and close-×**, since the native sidebar owns navigation. Ships on PyPI; only takes effect embedded in the app.
- **Contributor tooling:** a dev-only Run Inspector (`serve --dev`) over instrumentation the pipeline already captures, a native Debug menu (⌃⌘R), and a build-time sidecar-staleness gate. Developer-facing; no change to the report or exports.

**0.16.0** — _27 Jun 2026_

- **Send to Miro — push your analysed quotes onto a Miro board.** A new export builds a first-draft research wall: a fresh board per export, one column per section then per theme, pink section headers and yellow quote stickies coloured by sentiment. Connect by pasting a Miro access token (guided setup at `bristlenose.app/docs/send-to-miro.html`), preview credential-free, then push. Participant display names never leave your machine — codes only; hidden quotes excluded. Experimental, phase 1 (paste-token). SPA export menu now; macOS native menu next build.
- **Desktop: native SF Pro typography, with a Typography setting (SF Pro / Inter).** The macOS app renders on a calibrated SF Pro type scale aligned to Apple's text styles, with a setting to switch fonts. Includes WKWebView type-parity fixes so the in-app report matches.

**0.15.19** — _24 Jun 2026_

- **Desktop: the macOS project sidebar is rebuilt on native AppKit.** Off SwiftUI's `List` (which hit selection/tap dead-ends on macOS 26) onto a native `NSOutlineView`, bringing two-line project rows (icon · name · session count + a live status subtitle), activity/copy rings with hover-to-cancel on the row, can't-find and iCloud status glyphs, the failure → diagnostic popover, project/folder context menus, and Finder folder drops into the sidebar.
- **Desktop: the five report views become a lens rail, with a native window title + session subtitle.** Project · Sessions · Quotes · Codebook · Analysis move from the toolbar picker into a lens rail; switching lens updates a native window title and session subtitle (the toolbar title pill is gone). Desktop-only — ships to the alpha cohort with the next bundled-sidecar build; the package gains the supporting interface strings in all seven languages.

**0.15.18** — _21 Jun 2026_

- **Desktop: copy progress moved onto the project row, and switching back to a recent project is near-instant.** Copy progress (a determinate ring + "Copying · N%" + hover-to-cancel) now rides the project's sidebar row instead of a separate toolbar pill; and switching back to the immediately-previous project re-points to its still-running ("parked") server instead of restarting it (the "warm-sidecar pool").

**0.15.17** — _18 Jun 2026_

- **Default Claude runs no longer break when Anthropic retires a model.** The built-in Claude default pointed at `claude-sonnet-4-20250514`, retired by Anthropic on 15 June — so a plain `bristlenose run` on Claude (no `--model`) failed at topic segmentation with a `404 model_not_found`. Defaults now track current aliases (`claude-sonnet-4-6`, plus `claude-opus-4-8` where Opus is offered), so the next retirement is a one-line change. Pin a model with `--model` and nothing changes. Ships on PyPI.
- **Quote cards pack tighter on the report, where the browser supports it.** The quote grid uses CSS Grid Lanes masonry (Safari 26.4+ / the desktop WebKit) so variable-height cards settle into the shortest column — a progressive enhancement that falls back cleanly elsewhere, with reading order intact for keyboard and screen-reader users.
- **The desktop sidebar shows real progress on cached and first-time runs, not a frozen "Analysing…".** The per-stage verb ladder was driven only by the timing estimator, so cache-verified / transcript-only runs and every new user's first few runs (the estimator needs ~4 runs of history) never advanced it. An estimator-independent signal now fires at each stage entry, carrying the last-known ETA so warm runs are unchanged and cached / cold-start runs advance the verb with the ETA simply absent. Python-only — ships on PyPI and in the desktop sidecar.

**0.15.16** — _10 Jun 2026_

- **Quote extraction no longer fails on dense interviews when the model has a small output limit.** Some models cap a single response (ChatGPT's gpt-4o at 16,384 tokens; small local models far less), and on a long, quote-rich transcript the quote-extraction stage could hit that ceiling mid-response — the reply came back truncated and the whole run failed, on roughly one dense ChatGPT run in three. Bristlenose now detects the truncation, splits the transcript at a natural topic boundary (or even halves when there's no confident one), extracts each piece separately, and merges — recursing up to three levels deep (≤8 chunks). Duplicate quotes straddling a split are de-duplicated by verbatim text, and the split is all-or-nothing per interview so a partial failure never leaves a half-analysed session. New typed `TruncatedResponseError` / `OUTPUT_TRUNCATED` cause (mirrored on desktop), plus up-to-six retries on rate-limit bursts. Every quote still lands in exactly one report section. Ships on PyPI — benefits every provider with a tight output cap.

**0.15.15** — _9 Jun 2026_

- **Čeština — Bristlenose now speaks Czech.** Czech (`cs`) joins Spanish, Japanese, French, German, and Korean across the desktop app, web report, and settings (Settings → Language → Čeština). A volunteer signed up to translate Bristlenose into Czech on [Weblate](https://hosted.weblate.org/projects/bristlenose/) before we'd shipped the language — the first organic demand signal for a locale — so we machine-seeded a complete baseline (all 8 namespaces + `preflight`, ~950 strings, with proper Czech four-form plurals) for them to react to and refine. Fill-empty-only: the seed never overwrites a contributed string. Apple-HIG Czech glossary terms added.
- **A coverage sweep so more of the app translates — settings, codebook, transcripts, accessibility labels, the desktop pipeline — plus the first Czech-correct plurals.** Adding Czech surfaced strings still hard-coded in English (reaching none of the seven languages); this pass wired them through i18n, including the Settings config reference, ~30 screen-reader labels and tooltips, and the desktop pipeline status. The headline fix is grammatical: a hardcoded `count == 1 ? one : other` selector in the desktop overflow text could never reach Czech's `few` form (counts 2–4), so a new `I18n.pluralCategory()` now picks the right CLDR form (proven by a Swift test). Guard tests pin key parity, placeholder consistency, the CLI↔GUI mirror, and four-form completeness. Quality refinement stays the native-speaker community's; this is the mechanical groundwork.

**0.15.14** — _7 Jun 2026_

- **Desktop runs the provider you chose, and stops blaming transcription for LLM errors.** Four provider-resolution defects closed: the consent resolver no longer reverts a deliberately-chosen ChatGPT / Gemini / Azure account to Claude when its cached verdict is merely absent; spawn-time overlay injects provider **and** model as a matched pair (fixes `gpt-4o` 404'ing under the Anthropic endpoint); the failure classifier checks LLM markers before Whisper and names the provider, so an out-of-credit / bad-key failure no longer reads as "Transcription failed"; and the Settings status board paints eagerly from cache + silently reconfirms instead of lazily, with out-of-credit (402) as its own sticky state. Reviewed by six agents + William. Desktop-only.
- **Desktop status polish.** Provider explanations are now selectable markdown with one-click copyable shell-command rows (silent copy, Finder/Safari idiom); `⌘,` opens native Settings from report focus too (WKWebView was claiming the key equivalent); offline caption softened "Your key is fine" → "Your key was fine"; status vocabulary settled on colour + label, no per-state glyphs. Design docs trued to the data-protection-keychain + eager-status-board reality. Desktop-only; reaches the alpha cohort with the next bundled-sidecar build.

**0.15.13** — _4 Jun 2026_

- **`bristlenose pipeline` gains per-(provider, model) grain.** The pipeline view (0.15.11) now renders a row per (provider, model) pair — each LLM stage shows Claude / ChatGPT / Gemini / Azure with their individual models, per-model quality ratings, and a `recommended` axis split from `default` (Opus 4, gpt-4o). CLI + React Settings → Pipeline tab share a sectioned matrix with quality glyphs, a compact symbol key, fixed column alignment across stage tables, and the current row marked by the selection wash + `aria-current` rather than a loud badge. Payload `schema_version` 3 → 4; feature rungs and schema are decoupled both ways. Ships on PyPI.
- **Desktop: model-first Ollama setup (flow B) + consent activates the chosen provider.** A toolbar pill drives the on-device setup popovers (choose model → get Ollama → wait → download), with an honesty rule — static hourglass while waiting on the human, motion only while Bristlenose is working, red only for genuine failure. The AI-consent sheet's Continue/Done now actually activates the chosen provider (was leaving a validated cloud key inert and routing to a stale backend); Stay-local applies the RAM-aware default and pulls the model ambiently so the fetch survives sheet dismissal. 43-key locale layer across 6 locales. Desktop-only.
- **CI hardening.** Job timeouts on e2e + perf-gate with a bounded-retry around the Playwright install, SHA-pinned third-party actions that touch secrets, read-only default `permissions:` blocks, and a six-class fragility map in `docs/design-ci.md`. Workflow + docs only.

**0.15.12** — _23 May 2026_

- **Anthropic credit-exhausted now reports "out of credit", not "model unavailable".** Preflight's BadRequestError classifier was substring-matching on `credit_balance_too_low` (an `error.type` token that doesn't appear in `str(exc)`) — the live SDK message is `Your credit balance is too low to access the Claude API. ...`, so the branch silently fell through to the model-unavailable copy. Substring widened to `credit balance`; regression-pinned with the real SDK message. Runtime path was already correct; preflight-only miss.
- **Desktop: ⌘⌫ no longer beeps on placeholder projects or multi-selection.** Project-menu disable gates were over-broad — `hasProject` required either a non-empty path OR an unavailable project, so brand-new placeholders (empty path, available) and multi-selections (path cleared) both failed and hit AppKit's disabled-shortcut beep. Gates dropped; receivers were already total over empty/mismatched selection. Rename and Move-to-folder kept a narrower gate so they dim correctly on multi-select rather than silently no-op. Desktop-only; reaches the alpha cohort with the next bundled sidecar build.

**0.15.11** — _21 May 2026_

- **`bristlenose pipeline` + read-only Pipeline tab in Settings.** New CLI verb (`bristlenose pipeline`, with `--json` and `--stage <id>` filter) and a matching last-position tab in the React Settings modal render the mixture of models Bristlenose actually uses across its pipeline stages: MLX/faster-whisper for transcription, the chosen LLM provider × model for speaker identification / topic segmentation / quote extraction / quote clustering / thematic grouping, Presidio (or "Off") for anonymisation, and an Apple Foundation Models row that returns `Unknown from CLI` until the Swift-side probe ships. Read-only on purpose — to change a backend you still edit settings or `.env`. Host context strip shows OS · arch · RAM · keys present · ollama status. Cross-language schema lock at `tests/fixtures/pipeline-view-contract.json` keeps the Python emit and React consumer in agreement. 28 new tests.

**0.15.10** — _17 May 2026_

- **Release pipeline actually fixed (test-only — wheel unchanged).** PyPI had been stuck at 0.15.3 since ~10 May — six tag pushes (0.15.4-0.15.10) reached GitHub but the perf-gate CI job failed on each one, blocking the release workflow. Root cause: the server-rendered status page interceptor was returning "Nothing to see here, yet." against the Playwright smoke fixture because the fixture had never carried a `pipeline-events.jsonl`. `#bn-app-root` mounted empty, perf-gate's DOM-nodes test timed out, and the cascade silently masked the cause for five releases. Fix: ship a `RunCompletedEvent` line in the smoke fixture, plus a mount-precondition test at the pytest layer and a standalone Playwright mount gate so the next silent regression fails loudly. CLAUDE.md release flow grows a post-push PyPI verification step — pushing a tag is not the same as shipping a release. Test-only fix; v0.15.10's wheel is byte-identical with or without it.
- **`--codebook=<slug>` flag + `bristlenose codebooks` subcommand.** Pick an AutoCode codebook framework from the command line. `bristlenose codebooks` lists the nine available templates with title and author; `--codebook=<slug>` on `run` and `analyze` validates the slug against the YAML inventory and exits cleanly with the available list on a typo. Validation only for now — the pipeline doesn't auto-run AutoCode yet; the flag stores the preference for a follow-up branch to wire the consumer.

**0.15.9** — _16 May 2026_

- **Multi-project Phase 2 #11 + #14 — drag-onto-folder copy + folder watcher.** Drag-onto-existing-project now uses a copy path (`CopyMachinery`) with progress pill, `NewFilesSheet` stub, and collision-rename + folder-name-preservation regression tests. Folder watcher: `NSFilePresenter` + SQLite ingested-set, count pill on the row, delta sheet for triage. Two review passes for visual + i18n polish (cloud-evicted glyph swap to `icloud` outline, pointing-hand cursor on delta button, `.footnote` typography for session count, `.secondary` text uniformly, F59 / F62 i18n).
- **Sidebar honesty wave 2.** `.ready` now requires disk evidence — re-opened completed projects read "Ready" instantly instead of briefly flashing "analysing…". cantFind glyph specialises per reason (`.moved` / `.cloudEvicted` / `.permissionDenied` / `.removed`). Volume remount no longer regresses to `.moved`. AppleDouble (`._*`) + `.DS_Store` skipped across every directory scanner — closes a 16 May ExFAT SD-card crash where `._s1.txt` looked like a transcript and broke utf-8 decode.
- **Pipeline subtitle i18n across 6 locales.** Sidebar in-flight stage subtitles ("Transcribing…", "Extracting quotes…", "Clustering themes…", etc.) now translated in es / fr / de / ko / ja.
- **Keychain hardening.** API keys in the macOS Keychain now require Touch ID (or password fallback) to read — biometric ACL on the keychain item. Debug builds switched from Apple Distribution to Apple Development signing so ACLs persist across rebuilds (was un-dogfoodable; every debug Run re-prompted for access).
- **HIG corpus mirror.** Local Apple HIG mirror so `what-would-gruber-say` cites by path + paragraph anchor instead of paraphrasing. Generic scraper for future public release.
- **Misc.** `Window > Bristlenose` menu item to reopen the closed main window. Session start time no longer floored to midnight on the dashboard. In-flight switch modal: "Continue analysing" reframed as the cancel role (default-action stays non-destructive per HIG).

**0.15.8** — _14 May 2026_

- **Honesty everywhere — the pipeline, the install path, and the sidebar all stop faking success.** Walks-fix-walks groundwork across three currents:
  - **CLI honesty (A-stream).** `bristlenose doctor` hard-errors with a brew/pipx/pip-aware fix message when `[serve]` extras are missing (zsh-glob-safe quoted); `bristlenose run` / `serve` / `analyze` gate `serve_deps` in preflight; mid-run abandons surface a researcher-facing banner (QUOTA, AUTH, NETWORK, API_SERVER, DISK, MISSING_INPUT, MISSING_BINARY) instead of a generic "Failed". The static-render naming is sealed: `bristlenose render` removed, `--static` deleted, `--no-serve` restored as a hidden flag for the desktop sidecar's auto-serve suppression.
  - **Stage-cache honesty (A4).** Failed analysis stages no longer cache empty output and silently re-serve it on the next run; `mark_stage_complete` refuses empty `content_hash`; `s10`/`s11` hard-fail at the LLM call site before fallback runs. Privacy contract on `cause.message` (class name + provider + stage, never `str(exc)`).
  - **Long-audio quality (B1).** `collapse_adjacent_repeats()` post-processor catches Whisper looping ("thanks thanks thanks") without harming natural interjection doubling. Three Whisper params tuned for mlx-whisper. Speaker-propagation regression-pin tests + INFO log surfacing the LLM-splitter's sample-window limit.
- **Multi-project foundation (Phase 0 through Phase 2 partial).** `ProjectAvailability` enum (`ready` / `not-found` / `cloud-evicted` / `permission-denied`) with `last_seen_at`; undoable Remove via 5-second toast; "Locate…" flow for `not-found` projects (Spotlight 2-second one-shot → NSOpenPanel fallback → security-scoped bookmark capture). Phase 2 #1/#2/#3 landed: sidebar-clicking a different project tears down + respawns the sidecar with HIG-correct in-flight-run confirm sheet; drag-onto-existing-project adds files via `addFiles`; project-onto-project drops surface a non-modal toast pointing at the two right gestures. Sidebar drop hit-test refactored to native per-row `.dropDestination` (since macOS 13) — replaces ~209 lines of bespoke `.onDrop` + `GeometryReader` + `DropDelegate` coordinate-space machinery. `Cache-Control: no-store` on `/api/projects/*` belt-and-braces against WKWebView HTTP cache surviving the `.id()` rebuild.
- **Pipeline-failure trust-UX.** Re-running an already-analysed project no longer reads as "project is broken" — new `outputExists` failure category, researcher-register copy ("Already analysed — re-analysing would replace the existing results"), Retry button replaced by destructive-confirm "Re-analyse…" that spawns with `--clean`.
- **Locales reach the host bundle under sandbox.** "Copy Sidecar Resources" script phase marked `alwaysOutOfDate=1` so non-anchor locale edits actually trigger the rsync — closes the "raw `desktop.chrome.*` key strings in alerts" surface.
- **CI hygiene.** `.tool-versions` pins node 24.6.0 + python 3.12.13 (mise/asdf/rtx + CI workflows derive from the same file); `no-red-CI-merges` policy in `CONTRIBUTING.md`.
- **Workflow tooling.** `/end-session` sign-off sentinel + `/close-branch` drift check; `/new-feature --print-launch-url`; new `/sitrep` skill (situation-report with sprint-aware grid format).
- **Agent ecosystem.** New `what-would-james-bach-say` reviewer agent (test-placement / context-driven-testing tradition). `/true-the-docs` v2 with `--claude-pointers` mode.
- **Sidecar build.** PyInstaller bundle now ships `inflect` + `typeguard` `.py` sources for `inspect.getsource()`; resource-copy switched to `rsync -aL` (was `cp -RL` — broke mlx metallib rpath symlinks under sandbox).
- **Frontend bundle ceiling 210 → 215 kB.** Node 24's zlib re-baseline; runtime currency outweighs sub-1% size headroom.

**0.15.7** — _12 May 2026_

- **Release-pipeline fix** — three CI failures had stacked up since 10 May, leaving PyPI + Homebrew on 0.15.3 while source was on 0.15.6. No new source features in 0.15.7; on upgrade you pick up everything from v0.15.4 / v0.15.5 / v0.15.6 (preflight block, server-rendered status page, SPA auto-refetch, sandbox-safe Export, structured failure causes). The fixes: ffmpeg preflight bypass in the pipeline-abandon test; stub SPA bundle in the cookie auth test; CI Node 20 → 24 (the bundle-size "overage" was an older-zlib measurement artefact, not a real regression)

**0.15.6** — _11 May 2026_

- **Server-rendered status page for runs the SPA can't render** — `bristlenose serve` now serves a server-rendered page (no React mount) when the project has no completed run, or the latest run failed or was cancelled. The SPA's invariant becomes: it only mounts when there's data to render. Three states surfaced — no-run-yet (CLI vs desktop copy), failed (with cause + log tail in a `<details>` block, sourced from `pipeline-events.jsonl`), cancelled. Reuses the five-kind `MessageKind` taxonomy — no sixth kind invented. Styling lives at `bristlenose/theme/templates/status-page.css` and uses the design system's tokens exclusively. Event-watcher startup seed also widened to seed `failed` and `cancelled` termini, not just `completed`, so non-happy-path runs survive a server restart. English-only in v1; locale fills batched into the next translation pass

**0.15.5** — _11 May 2026_

- **First-run preflight block** — Whisper / ffmpeg / API-key / spaCy preflights all fire between ingest and audio extraction, surfacing every "would this run actually work?" question up front. Whisper banner + native HF Hub progress with hardcoded `~1.5 GB`; per-distro ffmpeg install table with macOS-brew auto-install offer (default N); paid single-token API-key validation against billing (Anthropic + OpenAI; 24h TTL cached in `~/Library/Application Support/Bristlenose/state.json` mode 0600). Closing line "No more questions. ~X min to your report. Ctrl+C anytime." after which no prompt fires
- **`--no-fetch` flag** on `run` / `transcribe` / `analyze` — aborts cleanly instead of fetching missing models. Pair with `bristlenose doctor --fetch` to pre-warm the Whisper cache before going offline
- **`BRISTLENOSE_SKIP_PREFLIGHT=1`** — defence-in-depth env-var escape hatch for spoofed-TTY CI runners
- **`bristlenose/preflight/{whisper,ffmpeg,api_key}.py`** new package; **`bristlenose/llm/billing_hints.py`** code-owned provider URLs / minimums / recovery copy; new `preflight.*` i18n namespace across all six locales (English source; es/fr/de/ko/ja mirror en pending native review)
- **Documentation truing** — design doc carries a post-implementation Status table; SECURITY.md adds preflight bullet + "What Bristlenose writes to your machine" appendix + HF Hub LFS-hash integrity caveat; man page gains a doctor-options section plus `--no-fetch` / `--fetch` / `--yes` / `--static` / `--dev` (the last three pre-existing gaps), `state.json` under FILES, and exit code 2

**0.15.4** — _10 May 2026_

- **SPA: auto-refetch on pipeline completion** — new `GET /api/projects/{id}/last-run` endpoint and `LastRunStore` (3 s poll, visibility-paused, single timer). Browser SPA now refreshes content within ~3 s of pipeline completion instead of going silent. All four content tabs and five island consumers wired
- **SPA: trust-UX layer** — manual refresh button in the NavBar (serve-mode only, hidden in the desktop app), refetch overlay on Quotes / Sessions / Dashboard while a refetch is in flight, post-zero-quotes empty state on the Quotes tab
- **Desktop: Export downloads route via `WKDownload` + `NSSavePanel`** — sandbox-safe Export. The previous synthetic `<a download>` click was silently dropped by the App Sandbox; the shell now intercepts the request, hands the response to `WKDownload`, and prompts via `NSSavePanel`. Six locales updated for the save dialog
- **Desktop: structured failure category surfaced in the failure pill** — `EventLogReader` now exposes the categorised `Cause` from the events log (10 categories: missing input, missing binary, all-LLM-failed, etc.). The failure pill renders the category-appropriate glyph + label instead of the generic "Failed" badge
- **Pipeline: structured per-stage failure summaries + abandon path** — every terminus event (`run_completed` / `run_failed` / `run_cancelled`) now carries an optional `PipelineSummary` rollup. When every transcription session fails or every quote-extraction LLM call fails, the pipeline now raises `PipelineAbandonedError` instead of silently writing an empty report. Two new `Cause.category` values (`MISSING_INPUT`, `MISSING_BINARY`)
- **Sidecar: sandbox compliance for the bundled FFmpeg `$PATH`, the libproc start-time check, and the React-bundle static serving** — three fixes that unblock the sandboxed desktop sidecar (`mlx_whisper`'s bare `"ffmpeg"` shellout now resolves; `/bin/ps` exec replaced with `proc_pidinfo`; Starlette `StaticFiles` mmap replaced with in-memory `read_bytes` for the React bundle)
- **CLI: glyphs and colours sourced from a single `MessageKind` table** — CLI, popover, and toast now consult `bristlenose.ui_kinds.cli_prefix(kind)` instead of ~20 ad-hoc `console.print("[colour]...[/colour]")` calls
- **Desktop: i18n sweep + locale delegated to System Settings** — extracted hardcoded English literals from `LLMProvider.swift`, `TranscriptionSettingsView`, `BuildInfoSheet`, default project name (all six locale `desktop.json` files updated). The in-app language picker is removed on macOS; selection flows through System Settings → Apps → Bristlenose. Web/CLI serve picker unchanged

**0.15.3** — _4 May 2026_

- **Desktop: provider-switching hardened end-to-end** — Change-provider flow now activates the new provider across Keychain, sidecar env, and UI; Ollama choice persists before consent log; sidecar key injection scoped to the active provider only; LLM Settings lazy-loads Keychain per row
- **Prompt-injection sentinel-tag boundary (Phase A)** — defence-in-depth boundary that lets the LLM structurally distinguish transcript content from prompt instructions
- **Sidecar bundle trim (S1+S2+S3)** — `mlx_whisper.torch_whisper` excluded, dedicated build venv, `torch` + `onnxruntime` evicted, mlx-whisper assets shipped via `collect_all`. Significantly smaller sidecar
- **Doctor**: recognises `mlx-whisper` as a complete backend on Apple Silicon
- **Desktop**: trusts log tail on sidecar exit-1-after-success; sandbox-on Debug builds load locales + resize correctly on macOS Tahoe

**0.15.2** — _2 May 2026_

- **Bundled FFmpeg/ffprobe discovery for sandboxed sidecar** — new `bristlenose/utils/bundled_binary.py` resolves FFmpeg/ffprobe from a bundle-relative path before falling back to `$PATH`, so the sandboxed desktop sidecar can find ship-with-app binaries. CLI users see no behaviour change
- **`bristlenose/server/lifecycle.py`** — serve-mode lifecycle factored out (parent-death detection, sandbox-friendly bind(0), graceful shutdown)
- **PipelineRunner `SidecarMode.resolve` migration** (PR #96) and **TLS→certifi redirect under sandbox** (PR #97). Desktop-only impact
- **Frontend size budget** re-baselined to live-SPA gzipped (lazy locales excluded). Budget remains 320 kB
- **Docs**: manual + README reconciled with shipped bundled-binary-helper; pricing reframed per hour of audio

**0.15.1** — _1 May 2026_

- **Desktop alpha-readiness (Sprint 2 Track C C2–C5)** — sandbox-safe API-key injection via Swift Keychain → env vars (no more `/usr/bin/security` exec from Python), libproc-based zombie cleanup, `os.Logger` with privacy redaction, key-shape stdout redactor, `SidecarMode.resolve` + three Xcode schemes, privacy manifests for host + sidecar, per-binary signing, supply-chain provenance. Desktop-only
- **Desktop first-run experience (Sprint 2 Track B Branch 1)** — `BootView` unified boot/loading/failed surface, `WelcomeView` two-variant empty state, Beat 3 round-trip API key validation, Beat 3b Ollama setup sheet for local AI install, `boot.*` + `welcome.*` translation blocks across all 6 desktop locales. Desktop-only
- **`bristlenose serve` fall-back to bundled theme CSS** — fixes brand-new projects rendering as raw HTML inside WKWebView when no per-project CSS has been generated yet
- **`bristlenose doctor --self-test`** — verify sidecar bundle integrity (spec → bundle file presence)
- **`bristlenose serve` fail-loud on missing React bundle** — returns a "Build incomplete" 500 page instead of silently falling back to the static render
- **Japanese (`ja`) locale completion** — ~614 strings across 8 namespaces, alpha gate cleared
- **i18n: tag sidebar** — 11 keys across all 6 locales

**0.15.0** — _26 Apr 2026_

- **Pipeline resilience: run-level event log + honest run state** — pipelines now write `pipeline-events.jsonl` recording how each run ended, with a structured `Cause` (10 categories). Replaces the desktop's old inference path that mis-classified interrupted runs as ready
- **Cost as honest estimate** — `cost_usd_estimate` + `price_table_version` + `input_tokens` + `output_tokens` stamped on every terminus event. Surfaced as `"~$0.46 (est.)"` — never bare dollars
- **Stranded-run reconciliation** — prior runs that died mid-flight are now noticed on the next `bristlenose run` and synthesised as `failed` with cause `unknown` ("Analysis stopped unexpectedly.")
- **Desktop: `EventLogReader`** — Swift consumer of the events log; new `PipelineState.partial` / `.stopped` cases. UI verb wiring (Resume / Retry / Re-analyse…) lands in a follow-up iteration
- **Desktop: Swift test target wired up** — `xcodebuild test` runs 90 tests including new `EventLogReaderTests`

**0.14.6** — _18 Apr 2026_

- CI: e2e gate re-enabled as a blocking check (three P3 items cleared)
- Fix: Analysis "Show all N quotes" toggle now a proper `<button>` (was an `<a>` without href)
- Fix: `playwright.config.ts` shell-quotes paths so worktrees with spaces in the name work
- `SECURITY.md`: corrected auth-token description (env-override path is real and used by CI fixtures / uvicorn reload; future hardening tracked)
- `bristlenose doctor`: new `Auth token` check warns if `_BRISTLENOSE_AUTH_TOKEN` is set in the shell
- CI: allowlist register at `e2e/ALLOWLIST.md` — every test suppression categorised and tracked; prevents silent accumulation

**0.14.5** — _17 Apr 2026_

- CI unblock release: no user-facing changes
- Fix `eslint-plugin-react-hooks` 7.0.1 → 7.1.0 (eslint 10 peer-range)
- Pin `jsdom` to 27.x (29 dropped localStorage shims, 140+ test failures)
- Fix stale Vitest mocks after `api.ts` and i18n changes
- Regenerate `e2e/package-lock.json` (lighthouse was added without `npm install`)
- Exclude `perf-stress.spec.ts` from default Playwright discovery
- e2e CI gate temporarily informational; three P3 findings parked to sprint 2

**0.14.4** — _16 Apr 2026_

- Pipeline resilience: input change detection (added/removed/modified files trigger re-run)
- Alembic migration infrastructure replaces manual schema migrations
- CI: multi-python matrix (3.10–3.13), split lint from test jobs

**0.14.3** — _27 Mar 2026_

- Export: video clip extraction from starred and featured quotes (FFmpeg stream-copy)
- Fix: video player "Cannot play" error caused by bearer token on `/media/` routes
- Fix: `safe_filename()` path traversal reassembly vulnerability

**0.14.2** — _24 Mar 2026_

- Localhost bearer token for serve mode API access control
- Fix: TOC sidebar empty after auth middleware added

**0.14.1** — _24 Mar 2026_

- French, German, Korean locales — machine-translated across all 8 namespace files, cross-checked against Apple and ATLAS.ti glossaries
- Contextual left-panel labels — desktop toolbar shows Contents/Codes/Signals per tab
- Tags sidebar shortcut (`⌘⌥T`), keyboard shortcuts design doc

**0.14.0** — _20 Mar 2026_

- Inspector panel — DevTools-style collapsible bottom panel in Analysis tab with heatmap matrices, signal card selection sync, drag-resize, and `m` keyboard shortcut
- Codebook sidebar — left-hand navigation panel on every tab with tag groups, counts, and micro-bars
- Finding flags — Win/Problem/Niggle/Success/Surprising/Pattern direction labels on signal cards, computed from sentiment valence, breadth, and intensity
- Settings modal (`⌘,`) and Help modal (`?`) — sidebar-nav modals with shared ModalNav organism
- Activity chips persist across tab navigation; new framework codebooks (Nielsen 10, Yablonski Laws)
- Fixes: codebook tab sidebar with trailing slash, codebook grid width, autocode toast behaviour

**0.13.7** — _16 Mar 2026_

- Spanish locale — machine-translated 102 UI strings across 8 locale files, ready for native-speaker review

**0.13.6** — _16 Mar 2026_

- Single tag focus mode — click a tag count to solo that tag (mixing-desk style), click again or Escape to exit. Sidebar dims non-focused tags; focused tag row stays at full brightness. "You are here" blue wash highlight on the active count matches TOC sidebar style
- Fix circular dependency crash in production build (SidebarStore → QuotesContext import cycle caused "Cannot access uninitialized variable" error)
- Used/unused tag filter toggle — quickly show only tags that appear on quotes
- Sidebar tag click-to-assign — select quotes then click a tag badge to apply it
- Tier 1 logging instrumentation and PII hardening
- Multilingual UI infrastructure (i18next + Python i18n module, browser language auto-detection)
- Responsive signal cards — grid layout with narrow-screen stacking
- Cache `system_profiler` results with 24h TTL to avoid slow macOS startup

**0.13.4** — _14 Mar 2026_

- Fix import FK constraint — delete AutoCode proposals before removing stale quotes during re-import
- Sessions sidebar with live-resize content-adaptive breakpoints

**0.13.3** — _14 Mar 2026_

- Help modal polish — platform-aware shortcuts (⌘/Ctrl), keycap typography, entrance animation, custom tooltips with shortcut badges
- Bulk actions respect multi-selection on click (star, hide, tag). Shift+click range selection fix
- Sidebar: push animations, 4× faster transitions, rail drag-to-open, drag handle hover-intent, scroll spy Safari fix
- Pipeline CLI: red ✗ for failed stages, yellow ⚠ for partial success
- Speaker badge wrap fix, scroll-margin fix for sticky navbar, TOC overlay clip-path animation

**0.13.2** — _11 Mar 2026_

- Render refactor — `render_html.py` (2,903 lines) broken into `bristlenose/stages/s12_render/` package with 8 submodules. Static render path formally deprecated (`DeprecationWarning`). No behaviour change

**0.13.1** — _10 Mar 2026_

- Responsive layout playground, sidebar TOC overlay mode, minimap component, responsive quote grid CSS

**0.13.0** — _10 Mar 2026_

- Codebook-aware tag autocomplete — suggestions grouped by codebook section with colour pills and headers, IDE-style
- Sentiment tags unified into the codebook framework system (proper `sentiment.yaml` codebook)
- Tag provenance tracking — `"human"` vs `"autocode"` source on every tag, preserved across edits
- Hidden-group tag UX — eye-closed icon in autocomplete, auto-unhide on accept
- Quick-repeat tag shortcut (`r`) — re-apply the last-used tag on a focused quote
- Fix: context expansion crash (infinite re-render loop on up chevron)
- Doctor offers interactive MLX install on Apple Silicon for GPU-accelerated transcription
- Sidebar accessibility improvements (focus management, ARIA, reduced-motion support)
- Dashboard stat cards now open in new tab on Cmd+click

**0.12.2** — _2 Mar 2026_

- Footer feedback restored in React serve mode: "Feedback" now opens a dedicated feedback modal (not the Help modal), and "Report a bug" remains a direct GitHub issue link
- Feedback submit flow parity with legacy behavior: POST to configured endpoint when available, with clipboard fallback + toast if endpoint submit is unavailable
- Health API now includes footer config (`links.github_issues_url`, `feedback.enabled`, `feedback.url`) while preserving `status` and `version`
- Exported reports now embed the same health/footer config shape as serve mode for consistent footer behavior

**0.12.1** — _1 Mar 2026_

- Word-level transcript highlighting — individual words highlight in sync with video playback (karaoke-style). Whisper sessions get per-word timing; VTT/SRT imports fall back to segment-level glow

**0.12.0** — _1 Mar 2026_

- Dual sidebar for Quotes tab — left: TOC with scroll-spy, right: tag filter with codebook tree and eye toggles for badge hiding. Drag-to-resize, keyboard shortcuts (`[` `]` `\` `⌘.`)
- Frontend CI — ESLint, TypeScript typecheck, and Vitest in GitHub Actions

**0.11.2** — _1 Mar 2026_

- Self-contained HTML export — download button bundles all data as embedded JSON with hash router for `file://`, optional anonymisation
- About panel redesign — sidebar layout with 5 sections (About, Signals, Codebook, Developer, Design)
- Configuration reference panel — read-only grid of all 63 configurable values with defaults, env var names, and valid options
- Morville honeycomb codebook — 7 groups, 28 tags with discrimination prompts and cross-codebook references

**0.11.1** — _28 Feb 2026_

- Fix video player broken by double URL encoding and missing subdirectory in source file paths

**0.11.0** — _28 Feb 2026_

- Full React SPA in serve mode — React Router replaces vanilla JS tab navigation, all 26 vanilla JS modules retired from serve path
- Player integration — `PlayerContext` manages popout video player lifecycle, glow sync, and progress bar from React
- Keyboard shortcuts — j/k navigation, multi-select, bulk star/hide/tag, `?` help modal, Escape cascade
- React app shell — `Header`, `Footer`, `HelpModal` components; serve mode serves Vite-built SPA directly
- Video player links on sessions page and dashboard open the popout player
- Importer finds source files in subdirectories (mirrors ingest scan pattern)
- Speaker display names in sessions grid use normal font size

**0.10.3** — _21 Feb 2026_

- Split speaker badges — two-tone code+name pills across all surfaces, with "Code and name / Code only" settings toggle
- Always-on sticky transcript header with session selector; serve-mode session links navigate to React transcript pages
- `bristlenose status` command — read-only project status from the manifest with session counts, intermediate file validation, and `-v` per-session detail
- Pre-run resume summary — one-line status message when resuming an interrupted pipeline run
- AutoCode frontend — ✦ button triggers LLM tag application, progress toast, confidence-aware threshold review dialog, proposed badges on quotes with accept/deny
- Transcript page — non-overlapping span bars, topic-change label dedup, speaker badge styling, back link stays in serve mode
- Journey chain — sticky header shows full journey with revisits, active step highlighted with hover-tint pill, index-based click-to-jump
- Resilient transcript discovery — serve-mode importer searches four locations instead of one
- Generic analysis matrix and signals API for serve mode
- Man page and docs updated for `status` and `serve` commands
- Fix: transcript back link no longer escapes from serve mode to raw static HTML

**0.10.2** — _21 Feb 2026_

- Pipeline crash recovery — interrupted runs resume automatically, only re-processing unfinished sessions
- Per-session tracking for topic segmentation and quote extraction with transparent cache + fresh merge
- CLI resume guard — re-run into existing output without `--clean`, manifest detected automatically

**0.10.1** — _19 Feb 2026_

- Desktop app API key onboarding — first-run setup screen, Keychain storage, Settings panel (⌘,)
- `.dmg` packaging — ad-hoc signed, drag-to-Applications, one-command build via `build-all.sh`
- Serve mode after pipeline — auto-launches `bristlenose serve`, report at `http://127.0.0.1:8150/report/`
- Deployment target updated to macOS 15 Sequoia

**0.10.0** — _18 Feb 2026_

- Desktop app v0.1 — SwiftUI macOS launcher with folder picker, drag-and-drop, pipeline streaming, View Report in browser
- Xcode 26 project with 4-state UI (ready → selected → running → done), ANSI stripping, report path detection

**0.9.4** — _17 Feb 2026_

- `bristlenose serve` — local dev server with SQLite persistence, React islands, live JS reload
- 5 React islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel) + 16 reusable primitives (182 Vitest tests)
- Codebook CRUD — drag-and-drop, inline editing, tag merge, pentadic colours, MicroBar frequency bars
- Data API — 6 endpoints sync researcher state from localStorage to SQLite (94 tests)
- Desktop app scaffold — SwiftUI macOS shell with sidecar architecture

**0.9.3** — _13 Feb 2026_

- Interactive dashboard — clickable stat cards, featured quotes with video playback, session row drill-down, cross-tab navigation
- Fix: logo dark/light swap on appearance toggle

**0.9.2** — _12 Feb 2026_

- Sessions table redesign — speaker badges, user journey paths, video thumbnails, per-session sentiment sparklines
- Appearance toggle — system/light/dark mode in settings tab
- User journeys — derived from screen clusters, shown in sessions table and sortable journeys table
- Time estimates — upfront pipeline duration estimate after ingest, recalculated as stages complete
- Clickable logo — navigates to project tab
- Fix: `llm_max_tokens` truncation causing silent 0-quote extraction
- Fix: sentiment sparkline bars now align with video thumbnail baseline

**0.9.1** — _11 Feb 2026_

- Moderator and observer names shown in Project tab stats row (Oxford comma lists, observer box only when observers exist)
- Fix: clicking [+] to add a tag on a quote now tags that quote, not the previously-focused quote

**0.9.0** — _11 Feb 2026_

- Tab navigation remembers position across reloads via URL hash; browser back/forward navigates between tabs
- Analysis tab — inline signal cards and heatmaps in the main report (no longer just a placeholder)
- Codebook tab — fixed empty grid bug caused by JS function name collision in the concatenated bundle

**0.8.2** — _9 Feb 2026_

- Transcript annotations — transcript pages highlight selected quotes with margin labels, sentiment colours, span bars, and playback-synced glow
- Gemini provider — `--llm gemini` for budget-conscious teams (~$0.20/study, 5–7× cheaper than Claude or ChatGPT); `bristlenose configure gemini` stores your key in the system credential store
- Jinja2 templates — report renderer migrated from f-strings to 13 Jinja2 templates (internal refactor, no output changes)

**0.8.1** — _7 Feb 2026_

- Hidden quotes — press `h` to hide volume quotes from your working view; per-subsection badge with dropdown previews; bulk hide via multi-select
- Codebook — standalone page for organising tags into groups with drag-and-drop, inline editing, and colour-coded badges
- Toolbar redesign — unified round-rect button styling
- Python 3.14 compatibility fix for PII check

**0.8.0** — _7 Feb 2026_

- Azure OpenAI provider — `--llm azure` for enterprise users with Microsoft Azure contracts
- Install smoke tests — new CI workflow verifies install instructions on clean VMs

**0.7.1** — _6 Feb 2026_

- Bar chart alignment — sentiment and user-tag charts use CSS grid so bar left edges align within each chart; labels hug text with variable gap to bars
- Histogram delete — hover × on user tag labels in the histogram to remove that tag from all quotes (with confirmation modal)
- Surprise placement — surprise sentiment bar now renders between positive and negative sentiments
- Quote exclusivity in themes — each quote assigned to exactly one theme (pick strongest fit)

**0.7.0** — _5 Feb 2026_

- Multi-select — Finder-like click selection (click, Shift-click, Cmd/Ctrl-click) with bulk starring (`s` key) and bulk tagging; selection count shown in view-switcher label; CSV export respects selection
- Tag filter — toolbar dropdown between search and view-switcher filters quotes by user tags; checkboxes per tag with "(No tags)" for untagged quotes; per-tag quote counts, search-within-filter for large tag lists, dropdown chevron, ellipsis truncation for long names

**0.6.15** — _4 Feb 2026_

- Unified tag close buttons — AI badges and user tags now use the same floating circle "×" style
- Tab-to-continue tagging — pressing Tab commits the current tag and immediately opens a new input for adding another tag (type, Tab, type, Tab, Enter for fast keyboard-only tagging)
- Render command path fix — `bristlenose render <input-dir>` now auto-detects `bristlenose-output/` inside the input directory

**0.6.14** — _4 Feb 2026_

- Doctor fixes — improved Whisper model detection and PII capability checking

**0.6.13** — _3 Feb 2026_

- Keychain credential storage — `bristlenose configure claude` (or `chatgpt`) validates and stores API keys securely in macOS Keychain or Linux Secret Service; keys are loaded automatically with priority keychain → env var → .env; `bristlenose doctor` now shows "(Keychain)" suffix when key comes from system credential store; `--key` option available for non-interactive use

**0.6.12** — _3 Feb 2026_

- File-level transcription progress — spinner now shows "(2/4 sessions)" during transcription
- Improved Ollama start command detection — uses `brew services start ollama` for Homebrew installs, `open -a Ollama` for macOS app, platform-appropriate commands for snap/systemd
- Doctor displays "(MLX)" accelerator — when mlx-whisper is installed on Apple Silicon, doctor now shows "(MLX)" instead of "(CPU)"
- Provider header fix — pipeline header now shows "Local (Ollama)" instead of "ChatGPT" when using local provider

[Older versions →](CHANGELOG.md)

---

## Licence

Copyright (C) 2025-2026 Martin Storey (<martin@cassiocassio.co.uk>)

AGPL-3.0. See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md).
