# Design: CLI / desktop "just works" defaults

**Status:** post-implementation (Mon 11 May 2026). Initially drafted during A1 brew-formula closeout after a 2-hour first-run call with a friendly CTO. Slices A–H shipped on the `cli-just-works` branch; deferred items called out below per section.

**Scope:** primarily the CLI channel (`bristlenose run`, `bristlenose serve`, `bristlenose doctor`), but the same principle and several of the same primitives apply to the macOS desktop. Cross-channel notes inline.

## Status (post-Slices A–H)

The handoff's eight sequenced slices all landed in one branch; the friendly-CTO blockers below are all addressed. What follows is the shipped-vs-deferred map so this doc can be read after-the-fact without diffing against `cli-just-works`.

| Item | Status | Where |
|---|---|---|
| Three install helpers (`ensure_wheel`, `ensure_spacy_model`, `ensure_hf_model`) | ✅ shipped (two of three — `ensure_wheel` deleted as unused, see Slice A note) | `bristlenose/utils/package_install.py` |
| spaCy lazy fetch wired into Presidio | ✅ shipped | `bristlenose/stages/s07_pii_removal.py` `_ensure_spacy_model` |
| Whisper preflight (banner, native HF Hub progress, `--no-fetch`, `doctor --fetch`) | ✅ shipped | `bristlenose/preflight/whisper.py` |
| ffmpeg preflight (distro table, brew auto-install on macOS) | ✅ shipped (consent default flipped to N) | `bristlenose/preflight/ffmpeg.py` |
| API-key preflight + `billing_hints.py` (Anthropic + OpenAI rich; Azure/Gemini fall-through) | ✅ shipped (validate-existing-key) | `bristlenose/preflight/api_key.py`, `bristlenose/llm/billing_hints.py` |
| Front-loaded preflight block + closing line | ✅ shipped (inlined — Rule of Three did not fire) | `bristlenose/pipeline.py` (block runs after ingest, before stage 2) |
| Quarterly drift cron on `billing_hints.py` | ✅ armed (`trig_01BtVXKG5hBnhPF4bGwR78CR`) | external |
| i18n namespace (`preflight.*` in all 6 locales) | ✅ shipped (es/fr/de/ko/ja mirror en for the translation review pass) | `bristlenose/locales/<loc>/preflight.json` |
| No-account-yet flow (numbered URL + getpass + Keychain persist) | 🟡 deferred | see Decisions block in `.claude/plans/cli-just-works.md` |
| `pipeline-events.jsonl` Cause entries on preflight abort | 🟡 deferred | aborts go through `typer.Exit(2)` for now |
| Whitelist enforcement for read-only commands | 🟡 deferred | preflight is only wired into LLM-touching commands so no leak today |
| Keychain-source attribution refinement | 🟡 deferred | labels are `env` / `stored` (cannot distinguish Keychain) |
| Preflight registry / `Preflight` dataclass / lint rule | ⛔ parked (Rule of Three did not fire; inline block is simpler) |
| Rich-bridge tqdm class | ⛔ parked (Option B / native HF Hub progress won the spike) |
| `cli/messages.py` framed renderer, `prompt_yes_no` generaliser, paste-flow factor | ⛔ parked (one consumer each — kept inline) |
| Machine-capability fallback for Whisper | ⛔ parked (no real cohort signal of OOM/thrash) |

---

## Philosophy

> A first-run user is **not** the audience that should learn the tool's plumbing. They should reach the report.

Two sentences, in priority order:

1. **It just works** — if there's a sensible default, take it without asking. Whisper model, transcription backend, output location, default project name, language, audio extraction, ffmpeg detection: choose, don't ask.
2. **Or it offers to do the right thing** — if a step *must* be a decision (download a 1.5 GB model, fetch a missing dependency, paste an API key, install Homebrew packages), surface the decision with the right answer pre-selected, a one-line "why," and a `[Y/n]` (default Y). Never error-and-exit when a one-prompt continuation would unblock 95 % of users.

A first-run user's burden should be: "press Enter, watch progress, read the report." Nothing else.

### What this is reacting against

The two-hour CTO call (anonymised). A skilled engineer, motivated to try the tool, with a folder of real interviews. He hit, in order:

1. `bristlenose serve` failed because `[serve]` extras weren't pulled in by the brew formula.
2. `bristlenose run` hung silently for ~10 minutes during transcription (it was downloading the Whisper model — no message, no progress bar).
3. He hit Ctrl+C thinking it was wedged. The cache half-resumed but he couldn't tell.
4. `--redact-pii` failed because `en_core_web_sm` wasn't installed and the error pointed at `python -m spacy download` rather than just doing it.
5. He got to the report — eventually, with hand-holding, on a video call, with both of us debugging in real time. A less patient user (or one without the call) would have closed the terminal somewhere around step 2.

The tool is good. The first-run path is the bug. Every one of those four was a one-prompt-or-one-progress-bar away from working — and the gap between "got there with help" and "got there alone" is exactly what this doc closes.

### What A1 actually fixed, and what's still ahead

A1 (brew formula fix; branch pushed, verification + merge pending at time of writing):

- ✅ **Fixes call-blocker #1** — `[serve]` extras now ship by default, so `bristlenose serve` works on a fresh brew install. Also restores `man bristlenose` (orthogonal to the four numbered call-blockers, but on the same handoff).

Untouched by A1 — all design surface ahead in this doc:

- ❌ **Call-blocker #2** (Whisper silent download) — needs the preflight + banner + native progress (sequencing item 4).
- ❌ **Call-blocker #3** (Ctrl+C resumption opacity) — falls out of the Whisper fix; same work as #2.
- ❌ **Call-blocker #4** (`--redact-pii` fails without `en_core_web_sm`) — A1 explicitly chose *not* to re-add a brew `post_install` spaCy line, in favour of the lazy-fetch-through-helper approach in sequencing items 2 + 5.

Plus the preflight registry, ffmpeg detection, API-key paste flow, default-tier auto-select, channel-mix telemetry, and the two debates — none touched. A1 is 1/4 of the call's symptoms; this doc is the other 3/4 plus the structural fixes that prevent the next equivalent call.

---

## UX goals

The first-run experience must:

1. **Never go silent for more than ~5 seconds without surfacing why.** Either it's working (spinner + stage name) or it's downloading (progress bar + size + ETA) or it's waiting for the user (prompt with default).
2. **Pre-empt foreseeable blockers** before the long-running stages start, so the user isn't 8 minutes into transcription before discovering the model isn't on disk.
3. **Translate machine truths into human framing.** "First run on this machine — Bristlenose needs to download the Whisper transcription model (~1.5 GB, one-off)" beats "model not found in HF cache at ~/.cache/huggingface/hub/models--…".
4. **Make Ctrl+C safe and resumption obvious.** Pipeline resume is already in place (Phase 1c/1d — see [`docs/design-pipeline-resilience.md`](design-pipeline-resilience.md) for the manifest + per-session cache mechanics this builds on); the same must hold for model downloads (HF Hub's built-in resume is fine; the UX must say "resuming download").
5. **Be the same shape across CLI and desktop — each authentic to its medium.** A user moving between channels shouldn't relearn the vocabulary, defaults, or recovery semantics. Glyphs and colours come from one taxonomy (`MessageKind`); copy stays consistent; defaults match. But the *chrome* is channel-appropriate by design — CLI is authentically CLI (terminal text, `[Y/n]`, "re-run with"); desktop is authentically Mac-native (SwiftUI sheets, buttons, modal flow). The same *question* may surface as a paste prompt in one channel and a sheet with a text field in the other; that's correct, not a failure to harmonise.
6. **Tell the user where bytes went and how to evict them.** Disk-conscious users are owed a one-line "cached at `<path>` — delete with `bristlenose doctor --evict-models`."
7. **Never require reading the manual to complete a first run.** The man page and `--help` are reference, not curriculum.

---

## Architectural principle: front-load all decisions

A pipeline run is a 20–60 minute operation. The whole point of Bristlenose is that the user starts it, walks away, and comes back to a report. **Any prompt that fires partway through the run violates that contract.** Even if each prompt individually is reasonable, the cumulative effect is "you sit there in case I need you, user" — tied-to-your-desk, exactly the anti-pattern of a tool that takes work-shaped time.

The fix is structural, not per-prompt:

> **Enumerate every question that might need user input, ask them all in one block at the start, then execute fully autonomously.**

Concretely: ingest runs first (fast, ~0.2 s — just a directory scan). Based on what ingest found, the tool compiles the *full list* of user-input questions that this particular run will need:

- ffmpeg missing + Homebrew detected → "install via brew?" question
- No API key in keychain/env → "paste your key?" question
- Whisper model missing AND `needs_transcription` is non-empty → no question, just inform (banner)
- spaCy model missing AND `--redact-pii` set → no question, just inform
- More than 16 sessions → "found N sessions, continue?" question (existing guard)
- Any other Shape 2 or Shape 3 blocker → its own question

These are asked **one at a time**, conversational, terse — matching the `gh auth login` / `cargo new` / `aws configure` idiom rather than a heavy "this is a wizard" framing. After the final question is answered, a single closing line confirms there are no more interruptions:

```
$ bristlenose interviews/

✓ Discovering files          [0.2s]  10 files

⊘ ffmpeg not found.
  Bristlenose needs it to read your video files.
  Homebrew detected — run `brew install ffmpeg` now? [Y/n] _

⠋ Installing ffmpeg via Homebrew...
✓ ffmpeg installed              [42s]

⊘ No API key configured.
  Bristlenose uses Claude to extract quotes from your transcripts.
  Paste your key (or "later" to skip analysis this run).
  Verifies: ~$0.0001, no transcript content.
  > _

✓ Key validated · saved to Keychain

No more questions. ~25 min to your report. Ctrl+C anytime.

⠋ Downloading transcription model
  [progress]
...
```

The closing line is the consent boundary. Plain, honest, terse:

> **No more questions. ~25 min to your report. Ctrl+C anytime.**

That single line is doing all the structural work:
- **"No more questions"** — explicit promise of no further interruption. The user can walk away with certainty.
- **"~25 min to your report"** — actionable ETA. Better than "Pipeline starting" because it answers the only question the user actually has ("when can I come back?").
- **"Ctrl+C anytime"** — reassures cancellability without belabouring the point.

After this line, **no prompt fires again** for the rest of this run. Downloads, installs, transcription, LLM calls — all autonomous. Errors that emerge mid-flow surface via the existing `Cause` taxonomy and the diagnostic popover; they don't ask the user new questions.

**Why one-at-a-time, not a numbered block:** the numbered "1/3, 2/3, 3/3" framing makes a routine "answer two questions" interaction feel like an enterprise setup wizard. One-at-a-time matches CLI conventions the user already knows (the `gh` family, `cargo`, `aws configure`, `git config --global` first-run) and stays out of the way. The ETA in the closing line is what carries the "you can walk away" message — no need to advertise it upfront.

**Why this matters more than any individual question's design:** the *placement* of prompts is doing more UX work than the *wording* of prompts. A perfectly-worded prompt mid-pipeline is still a tied-to-your-desk violation. A roughly-worded prompt at the start, with the user fully aware that everything after Enter is autonomous, is a "just works" win.

**What if a question reveals an unrecoverable problem?** Then we say so up front, before the user has invested any time. "ffmpeg missing, no Homebrew available, here's how to install it manually, re-run when ready." Exit cleanly with a non-zero status. The user has lost 30 seconds, not 30 minutes.

**What if a state actually emerges mid-pipeline that needs decision?** Treat it as a hard failure with a `Cause`, not a prompt. Bail with a clear message; user re-runs after fixing. Examples: API credit exhausted mid-pipeline (already covered by existing `Cause` category), LLM provider unavailable, disk full. None of these should drop the user into a prompt at minute 35; they should bail with an error and surface in the diagnostic popover.

**Implementation pattern (as shipped, Slice F):** preflight callers fire in a single inline block in `pipeline.py` immediately after ingest, before stage 2 starts. The collector / `UserQuestion` dataclass / registry didn't get factored because the Rule-of-Three didn't fire (one interactive prompt today: `brew install [Y/n]`). No stage code calls `input()` or `getpass()` outside that block today; the discipline is enforced by code review rather than a lint rule for now.

**Exception:** the existing session-count guard ("Found 47 sessions in dir/. Continue? [Y/n]") fires at the end of ingest, which is technically before the rest of the pipeline. It belongs in the upfront question block conceptually, just rendered after the discovery line. Keep it where it is; treat it as the prototype for this pattern, not an exception to it.

## The shape of the problem — pattern catalogue

Every "just works" blocker we have or will have fits one of five shapes. Knowing the shape tells you which primitive solves it.

### Shape 1: missing on-disk asset, fetchable

A model, a vocab file, a binary. Knowable to be missing before the long stage starts. Fetchable from a known URL with known size and resumable transfer.

**Pattern:** preflight check → human-framed pre-message → resumable download with real progress → continue. Default `[Y/n]` answer is `Y` for "yes, download." Skip the prompt entirely when total size is under a threshold (say, 50 MB) — just do it with a progress bar.

**Instances:**
- Whisper model (mlx-whisper or faster-whisper, ~150 MB to ~1.5 GB depending on tier)
- spaCy `en_core_web_sm` (~12 MB) for PII redaction
- Ollama model pulls (variable, 1–30 GB)

### Shape 2: missing system binary, installable via package manager

ffmpeg, ffprobe, Ollama itself. The user can't install it from within Bristlenose, but Bristlenose knows what to tell them and can copy a one-line command into their clipboard.

**Pattern:** preflight detect → friendly explanation → offer copy-paste command → on macOS, optionally offer `brew install <pkg>` directly if Homebrew is detected. Never silently fall through; always frame the missing dep in product terms ("Bristlenose needs ffmpeg to read your video files") not error terms ("FileNotFoundError: 'ffmpeg'").

**Instances:**
- ffmpeg / ffprobe on `pip install bristlenose` from any OS. brew handles it via `depends_on "ffmpeg"`; Snap encapsulates its own (when CI's unbroken); desktop bundles it in `Resources/`. The unhandled channel is **pip** — pip can't install system binaries, so the user is on the hook regardless of OS. Most-affected audience is Python-fluent Linux devs (likeliest to pip-install rather than use a system wrapper), but pip-on-Mac is the same shape with a different fix-command.
- Ollama daemon when "Local" provider is selected
- (Future) Apple Speech framework availability check on macOS for platform-transcripts path

### Shape 3: missing credential, user must paste

API keys for Claude / ChatGPT / Azure / Gemini. Bristlenose cannot fetch this for the user; only the user can. But the prompt for it should be in-product, not in a man page.

**Pattern:** preflight detect missing key → ask interactively, in-context, at run time (not "set this env var and retry"). Validate the pasted key with a small live API call before continuing. Persist to Keychain (desktop) or print one shell-export line (CLI) on success. Link to the provider's console URL.

**Instances:**
- BRISTLENOSE_ANTHROPIC_API_KEY (default provider)
- Same for OpenAI, Azure, Gemini
- (Adjacent) provider-selection prompt if no key is set for any provider

### Shape 4: ambiguous default, but Bristlenose can pick well

Project name from folder, output location, default language, whisper backend (mlx vs faster-whisper), default model tier, sentiment vs theme balance. Decisions that *could* be configurable but don't need to be asked.

**Pattern:** pick the obvious default silently. Print the choice in the run header so the user knows what was assumed. Provide a flag for override; never block on the question.

**Examples currently handled well:** whisper backend auto-detect (Apple Silicon → mlx, else faster-whisper), output dir auto-creation inside input folder, project name from folder slug, language default to `en`. These are the model for the rest.

**Examples not yet handled:** machine-capability fallback for whisper (`large-v3-turbo` is the locked default; *if* it turns out to OOM or thrash on low-RAM machines, auto-downshift to `medium` or `small` and print the choice). That's a fallback behaviour, not a question about *the* default — the default is settled.

### Shape 5: real failure, but the error is unhelpful

The actual exception is meaningful to a Python dev and inert to a researcher. `KeyError: 'audio'` from a corrupt video file. `OSError [Errno 2]` for a path that has a space. `JSONDecodeError` from a truncated LLM response.

**Pattern:** the `Cause` taxonomy (10 categories, [`bristlenose/ui_kinds.py`](../bristlenose/ui_kinds.py) and per-stage `categorise_exception`) already exists. Goal here is to make sure every shape-5 surface goes through it and translates to a `MessageKind` with a glyph, colour, and a recovery hint — not a bare traceback. This is mostly already shipped (v0.15.4 added structured per-stage summaries); the work is auditing remaining bare exceptions and rounding them up into the taxonomy.

---

## Per-blocker spec (worked examples)

### Whisper model first-fetch (Shape 1, current pain point)

**Current state:** `_init_mlx_backend()` and `_init_faster_whisper_backend()` in [`bristlenose/stages/s05_transcribe.py`](../bristlenose/stages/s05_transcribe.py) log "MLX backend initialised (model will be loaded on first use)" and then let HuggingFace Hub download on the first `mlx_whisper.transcribe()` call. HF progress bars are explicitly disabled ([line 209-212](../bristlenose/stages/s05_transcribe.py#L209)) because they conflict with the Rich spinner. Net effect: 5–30 minutes of silence, then transcription starts.

**Default model:** `large-v3-turbo` (`config.py:74`). Roughly 1.5 GB for mlx-community's quantised version.

**Spec:**

```
✓ Discovering files          [0.2s]  10 files
✓ Extracting audio           [4.3s]  5 video files
✓ Parsing subtitles          [0.1s]  0 files
✓ Parsing docx               [0.0s]  0 files

  First run on this machine — Bristlenose needs the transcription
  model (~1.5 GB, one-off). Downloads to ~/.cache/huggingface/.
  Cancellable with Ctrl+C; resumes cleanly next run.

⠋ Downloading transcription model
  config.json:        ████████████████████ 2.1 kB
  tokenizer.json:     ████████████████████ 2.4 MB
  model.safetensors:  █████████░░░░░░░░░░░ 642 MB / 1.5 GB · 14 MB/s
✓ Downloaded transcription model  [1m43s]  1.5 GB

⠋ Transcribing (1/5)...
```

**No `[Y/n]` prompt.** The walk-away-make-coffee case *is* the intended use case for a 1.5 GB download. A prompt requires the user to be present to type Y; coming back 5 minutes later to find the terminal sitting at a prompt with nothing done is the worst outcome we could ship. The command itself (`bristlenose interviews/`) is the consent.

**Peer-tool convention** — Bristlenose's neighbours in the LLM-tools space all auto-proceed:

| Tool | Fetch size | Confirmation? |
|---|---|---|
| `huggingface-cli download` | Multi-GB | No — banner + progress + done |
| `ollama pull` | ~2 GB | No — banner + progress + done |
| `pip install <heavy>` | Hundreds of MB | No |
| `cargo install` | Compile minutes | No |
| `brew install <pkg>` | ~80 MB + deps | No |
| `gh repo clone <big>` | GB scale | No |
| `apt install <heavy>` | GB scale | **Yes** — outlier; system-package mutation with dependency cascades |

Bristlenose's posture matches HF CLI / Ollama / brew, not apt. User-scope, named target (they typed `bristlenose <folder>`), fully reversible (delete the cache), no surprise dependency cascades. Match the LLM-tools convention.

**Escape hatches for CI / air-gapped / explicit-prep:**

- `--no-fetch` flag — refuses any auto-download. Prints what *would* have been fetched, exits cleanly. For CI smoke runs, air-gapped machines, debugging.
- `bristlenose doctor --fetch` — explicit pre-download path. Researcher pre-loads everything before a flight / conference / known offline period. Same machinery as the runtime preflight, just invoked deliberately.

**Not designed for: metered connections.** Researchers using Bristlenose at a hotel know hotel wifi varies and tether or wait — it's a cost of doing work, not Bristlenose's problem to solve. Anyone running a work tool that does LLM inference and transcription has decided their connection is good enough for the task. Cancellability (Ctrl+C, resumable next run) is sufficient. Don't add metered-wifi-aware branches; they obscure the common case to protect an edge that the user already manages.

**Why Ctrl+C is genuinely safe** (and worth the banner reassurance): HF Hub's `snapshot_download` writes `.incomplete` files during download. On Ctrl+C, the partial files stay in cache. Next invocation detects them and resumes from the byte where the previous run stopped — no corruption, no manual cleanup, no `.tmp` hunt. Same for pip wheels via PEP 658 metadata. The banner says this explicitly so a user who wants to interrupt knows it's safe.

**Implementation:**

1. New helper `bristlenose/utils/hf_cache.py:model_is_cached(repo_id) -> bool` using `huggingface_hub.try_to_load_from_cache` (returns sentinel `_CACHED_NO_EXIST` if not found, a path if found, `None` if uncached).
2. Call it from `_init_mlx_backend` / `_init_faster_whisper_backend` *before* the Rich `console.status()` spinner opens — these are called inside `transcribe_sessions()`, so the preflight has to lift into `pipeline.py`. **Shipped placement:** the call lives in the front-loaded preflight block immediately after ingest (Slice F), not between stages 4 and 5 as originally sketched. Same effect, surfaced earlier.
3. If missing: close the spinner, print the framed pre-message, prompt, then call `snapshot_download(repo_id, tqdm_class=<rich-bridge>)` outside the spinner context. Reopen the spinner for actual transcription.
4. `--yes` / `-y` already exists (session-count guard). Re-use it to skip the prompt for CI / scripts.
5. **Resume:** HF Hub handles partial downloads automatically. The pre-message should say "Resuming download" instead of "Downloading" when `~/.cache/huggingface/hub/models--…/blobs/` contains partial files.

**Rich-bridge tqdm class:** there's a `rich.progress.Progress` adapter pattern in the Rich docs — a small wrapper class that implements tqdm's interface and forwards to a Rich progress bar. We need this in `bristlenose/utils/rich_tqdm.py`; potentially also useful for faster-whisper's internal progress bars and any future HF download.

**Estimating size before download:** tempting to use `huggingface_hub.HfApi().model_info(repo_id).siblings` to make the "~1.5 GB" number data-driven. **Don't.** It's a network call that runs *before* the banner — on slow / captive-portal connections, 2–10 s of silent stall recreates the exact problem this section is solving. Hardcode `~1.5 GB` in the banner; staleness is fine over model releases. Updating the constant when the default model changes is a one-line maintenance step (and the quarterly drift-audit cron can verify the published size matches our constant).

**Default tier:** locked at `large-v3-turbo` (~1.5 GB). Settled in a prior conversation: turbo is *good enough* that the quality win justifies the size hit, the size is surfaced in the framed banner so the user isn't ambushed, and eviction is one command (`bristlenose doctor --evict-models` once it exists). Don't reopen — the cost of revisiting the model choice repeatedly is higher than the cost of carrying 1.5 GB on disk.

### spaCy `en_core_web_sm` (Shape 1, A1 sidebar)

**Current state:** `bristlenose/stages/s07_pii_removal.py:_init_presidio()` calls `AnalyzerEngine()` which internally calls `spacy.load("en_core_web_sm")`; missing model raises `OSError`. The current brew formula no longer downloads it (autobump overwrote the spaCy `post_install` line), and `--redact-pii` errors out.

**Spec:** **it's tiny — just get it.** No prompt, no banner, no native pip output redirect, no production. Single inline status line that mutates in place; ~4 seconds on a normal connection. The user shouldn't notice it happened beyond a flicker of text.

```
⠋ Removing PII...
  Downloading PII model en_core_web_sm (~12 MB, one-off)... done [4.2s]
⠋ Removing PII (2/5)...
```

This is a *deliberate departure* from Debate 1 / Option B's "step aside and let the library print" framing — which is right for Whisper (1.5 GB, real progress bars are informative) but wrong for spaCy (12 MB, library output is more noise than signal). The principle: **fetch UX should scale with fetch size.** A useful cutoff:

| Size | Treatment |
|---|---|
| < 50 MB / < 10 s expected | Single inline status line; suppress library output |
| 50 MB – 500 MB | Framed banner + native progress (Option B) |
| > 500 MB | Framed banner + native progress + cache-path callout (Option B with extra context) |

The cutoff is fuzzy; the principle isn't. Tiny things should feel tiny.

**Implementation:**

```python
def _ensure_spacy_model() -> None:
    import spacy
    try:
        spacy.load("en_core_web_sm")
        return
    except OSError:
        pass
    logger.info("Downloading PII model en_core_web_sm (~12 MB, one-off)...")
    subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        check=True,
    )
```

**Desktop:** out of scope for this doc. The sandboxed sidecar can't write into its own read-only site-packages at runtime, so desktop solves this by **bundling the spaCy model into the sidecar at build time** alongside every other Python dep — the standard sidecar packaging story, no runtime fetch needed. Lives with the sidecar bundle work (`desktop/bristlenose-sidecar.spec`, `desktop/scripts/build-sidecar.sh`, and the bundle-manifest checks in `docs/design-modularity.md` / sprint Track C), not here. This doc owns the CLI-channel runtime-fetch UX only.

### ffmpeg / ffprobe (Shape 2)

**Current state:** brew pulls ffmpeg via `depends_on "ffmpeg"` in the formula — handled. Snap bundles its own ffmpeg inside the snap — handled (in snap's own way; gated on the snap CI being un-stuck). Desktop bundle ships ffmpeg + ffprobe in `.app/Contents/Resources/` — handled. The **only unhandled channel is `pip install bristlenose`**, because pip can't install system binaries. That hits hardest on Linux (Python-fluent devs likeliest to pip-install rather than use a system wrapper), but pip-on-Mac and any future pip-on-Windows have the same shape with different fix-commands. Without preflight, the user hits `FileNotFoundError` deep inside Stage 2 (audio extraction) after a chunk of work has already happened.

**Spec for CLI on pip + macOS (Homebrew detected) — the happy path:**

```
✓ Discovering files          [0.2s]  10 files

  Bristlenose needs ffmpeg to read your video files. Not detected.
  Homebrew is installed — happy to fetch it for you (~80 MB).

  Run `brew install ffmpeg` now? [Y/n]

⠋ Installing ffmpeg via Homebrew...
  [brew's native output — package resolution, downloads, taps, etc]
✓ ffmpeg installed                [42s]
✓ Discovering files (continuing)
```

**This is the whole point of brew.** A pip-on-Mac user who has brew (i.e., almost any developer on macOS) shouldn't have to leave the terminal, read instructions, and re-run — Bristlenose can just offer to do it and shell out. Same Option B move as the Whisper download: we don't try to redraw brew's output, we step aside and let brew print, framed with our own banner above and ✓ below. User is always in control (`[Y/n]` with default Y), and bailing out drops them into the printed-instructions table below.

**Spec for CLI on pip + (any OS without an auto-install we own) — the fallback path:**

```
✓ Discovering files          [0.2s]  10 files

  Bristlenose needs ffmpeg to read your video files. Not detected.

  Install with:
    macOS:        brew install ffmpeg
    Ubuntu/Deb:   sudo apt install ffmpeg
    Fedora/RHEL:  sudo dnf install ffmpeg
    Arch:         sudo pacman -S ffmpeg
    Other:        https://ffmpeg.org/download.html

  After installing, re-run `bristlenose <folder>`.

⊘ Stage halted — install ffmpeg and retry.
```

Detect the platform / distro (`platform.system()`, `/etc/os-release`) and surface the matching line first, with the others below as fallback. This is Shape 2 (Bristlenose can't install for you on most platforms), so for the fallback case we frame it and stop early — *before* Stage 2 fails with a Python traceback 30 seconds in. The check belongs in `bristlenose doctor` and as a preflight before Stage 2 in `pipeline.py`.

**Why macOS-with-brew gets the auto-install offer and Linux doesn't:** typing the user's `sudo` password into a Python subprocess is a privilege-escalation surface we don't want to own. brew runs as the user, no sudo, no privilege boundary crossed — it's safe to shell out. apt/dnf/pacman aren't. Linux users are well-served by the printed command; macOS-with-brew users get the auto-install because brew explicitly exists for this kind of "let me handle it" task and asking them to copy-paste a command Bristlenose could have just run is the wrong default.

**Already shipped (don't redo):** the bundled-binary discovery for desktop ([`bristlenose/utils/bundled_binary.py`](../bristlenose/utils/bundled_binary.py), v0.15.2). The PATH-prepend in `bristlenose/__init__.py` handles transitive bare-name shellouts. Both stay; this design doc is about the pip-install gap only.

### Missing API key (Shape 3)

**Current state:** if no provider env var is set, `LLMClient` raises an opaque error during Stage 8 or 9 — minutes into the run, after transcription has finished. The user has spent time and disk on transcription before discovering they can't analyse. Worse, the *first* time anyone runs `bristlenose <folder>` on a machine, they may not yet have an Anthropic account at all — and we're asking them to deal with that mid-pipeline.

**Two sub-cases hiding inside "missing key":**

1. **User has a key, just hasn't pasted it / set the env var.** ~30 seconds to fix once asked.
2. **User has no key yet.** Needs to create a provider account, add a payment method, generate the key, possibly read safety / acceptable-use docs. **5–20 minutes in a browser** with billing decisions in the middle. This is the dangerous case — it's where a "let me try this tool for 10 minutes" researcher decides whether to bother.

#### Timing: ask earlier than Stage 1

Asking during `bristlenose run` is too late for case (2). By that point the user has chosen a folder, typed the command, watched ingest spin up — and we're now interrupting with "actually first, 20 minutes of side-quest." That's a drop-off cliff.

Better: surface the key requirement at **first invocation of anything**, including `bristlenose --help`, `bristlenose doctor`, `bristlenose <folder>`. Detect first-ever-on-this-machine via the absence of a marker file (macOS: `~/Library/Application Support/Bristlenose/state.json`; Linux: `$XDG_DATA_HOME/Bristlenose/state.json`, defaulting to `~/.local/share/Bristlenose/state.json`). On detection, print one line up-front:

```
$ bristlenose interviews/

  First run on this machine. Bristlenose needs
  an API key for Claude (or another provider) to extract quotes.
  Set one up now? (~30s if you have a key, ~10 min if you need to
  create an account and add billing.) [Y/n]
```

`[Y]` drops into the paste/account-create flow below. `[n]` proceeds (so the user can keep exploring), but flags that analysis will block at Stage 8 with the same prompt — and the marker file is *not* written, so the prompt fires again on next invocation. The principle: the user shouldn't be ambushed by a 20-minute side-quest mid-pipeline. Get the question on the table at minute zero.

#### Detection order and source attribution

Before prompting at all, check in this order:

1. **Env var** (`BRISTLENOSE_<PROVIDER>_API_KEY`) — session-scoped, intentional, wins.
2. **Keychain** (macOS) / `~/.config/bristlenose/keys` (Linux) — persistent fallback.
3. **Paste flow** — last resort, only fires if 1 and 2 are both empty.

When a key is found in 1 or 2, announce the source the *first time it's used* (on a fresh machine or after marker reset). Quiet on subsequent runs within the 24h TTL — once announced, trust the user to remember.

| Scenario | What user sees |
|---|---|
| First run, env var set | `✓ Found key in env var · validated` |
| First run, Keychain has entry | `✓ Found key in Keychain · validated` |
| First run, nothing set, user pastes | `✓ Key validated · saved to Keychain` |
| Subsequent run within 24h TTL | Silent — no key line shown |
| Run after 24h TTL (re-validates) | Silent on success; surfaces only if validation fails |
| **Conflict: env var AND Keychain both present, different keys** | `✓ Using key from env var (Keychain entry also present — env var wins)` |
| `bristlenose status` / `bristlenose doctor` | Always shows the active source explicitly |

The conflict case matters: a researcher with an old `BRISTLENOSE_ANTHROPIC_API_KEY` in `.zshrc` AND a fresh Keychain entry from a recent setup would otherwise have no way to know which is winning. Standard 12-factor convention is "env wins"; we honour that, but say so on first use so they can fix the surprise (delete the env var, or update the Keychain entry).

**The principle:** *announce the source the first time it's used; trust the user to remember after.* Silent magic on a credential surface is worse than verbosity — see anti-patterns.

#### Branch (1): has-a-key flow

```
  Paste your Claude API key (starts with sk-ant-) and press Enter.
  Verifies: ~$0.0001, no transcript content.
  > ********************************************

  Validating... ✓ Key works · saved to Keychain
```

Key persistence is automatic: Keychain on macOS, `~/.config/bristlenose/keys` (0600) on Linux, Credential Manager on Windows — all via Python's `keyring` library, same path the desktop already uses. No "persist to your shell?" prompt; that's an extra question for zero benefit. A researcher who wants the `~/.zshrc` export-line behaviour can opt in via `--persist=shell`, which is an alternative *for advanced users*, not a question for the median user.

**Validation must exercise billing, not just auth.** A pure auth ping (e.g. listing models, or some providers' `/whoami`) returns 200 for keys that are valid-but-unfunded. We need to know whether the key can *actually do inference*, which means a minimal real call — a `/messages` request with `max_tokens=1` and a one-character prompt. Cost: roughly **$0.0001** on Claude Sonnet, similar order on every provider. Functionally free, but enough to surface the billing state.

This catches the **single most common first-run trap**: the user has a valid key that's connected to a billing-empty account. The CTO call hit this exactly — key was correct, but he assumed his Claude.ai subscription covered API usage. **It doesn't.** This confusion is not Anthropic-specific — it's identical with OpenAI (ChatGPT Plus ≠ API credit), Google (AI Studio free tier ≠ Vertex billing), Azure (subscription ≠ deployment quotas). Every provider has the same shape, and every first-time API user trips it.

What good failure messages look like for the billing-empty case — provider-specific copy, same shape:

```
  ⊘ Key works, but your Claude account has no API credit yet.

  Heads up: your Claude.ai subscription does _not_ fund API usage.
  API credit is separate — you load it as prepay on the console.

  1. Open  https://console.anthropic.com/settings/billing
  2. Add a payment method and prepay credit ($5 minimum;
     ~$5 typically covers analysing a small study from end to end)
  3. Re-run `bristlenose <folder>` — your key still works, no re-paste needed.
```

The "subscription ≠ API credit" sentence is doing the real work — without it, a user with Claude.ai Pro genuinely thinks the tool is broken because they're already paying. The dollar floor sets the expectation that this is a "load $5 and forget" decision, not a "configure a monthly bill" decision.

**Design principle — early honest abandon beats late frustrated abandon.** The provider minimums are not negotiable by us. A user who decides "$5 to try this isn't worth it" and walks away at the API-key preflight has lost five minutes; a user who transcribes a 90-minute session, then discovers they need to add credit before analysis can proceed, has lost an hour and feels lied to. **Telling them the truth up-front is the kindest thing we can do**, even when the truth is "this costs real money on a credit card." The framing isn't apology, it's information: "Here's what it'll cost to try; here's where you add it; we'll wait while you decide." Users who walk away at minute five aren't lost — they're saved from a worse experience. Users who stay are now informed buyers, not ambush victims.

**Per-provider billing table** — owned in code (a small registry in `bristlenose/llm/billing_hints.py` or similar) so the URLs, minimums, and copy stay synchronised when providers change pricing or UX. The CLI preflight reads the active provider's row and renders the right message:

| Provider | Shape of "add money" | Minimum | URL | Subscription confusion |
|---|---|---|---|---|
| **Claude** (Anthropic) | Prepay credit on console | $5 | `https://console.anthropic.com/settings/billing` | Claude.ai Pro/Team subscription does _not_ fund API |
| **ChatGPT** (OpenAI) | Prepay credit on platform | $5 | `https://platform.openai.com/account/billing` | ChatGPT Plus / Team / Enterprise subscription does _not_ fund API |
| **Gemini** (Google) | Two-mode — AI Studio free tier, then Google Cloud billing | Free tier first, then post-paid via GCP project | `https://aistudio.google.com/apikey` / `https://console.cloud.google.com/billing` | Google One / Workspace / Gemini Advanced subscription does _not_ fund API |
| **Azure OpenAI** | Azure subscription billing — pay against an Azure account, no separate prepay | Azure subscription minimums (varies; many users have $$ via existing employer/student credits) | `https://portal.azure.com/#blade/Microsoft_Azure_Billing/SubscriptionsBlade` | n/a — there's no "Azure subscription that doesn't cover API"; if Azure is set up at all, billing works |
| **Local** (Ollama) | Free, runs on your machine | n/a — free | n/a | n/a — confusion vector is "do I have enough RAM," handled separately |

Notes baked into that table:
- **Claude and OpenAI are isomorphic** — same prepay shape, same minimum, same "regular subscription doesn't count" confusion. Copy can share a template.
- **Gemini is bimodal.** First-time users probably want AI Studio's free tier; that's the easy path. Heavy users need Google Cloud billing, which is a different (more involved) flow. The CLI should surface AI Studio first and only mention GCP if the user hits the free-tier rate cap. *Note: the AI Studio path's exact "got no credit but key is valid" error class needs verifying — Google's billing semantics differ enough from Anthropic/OpenAI that the validation logic may need a provider-specific branch.*
- **Azure is enterprise-shaped.** Users who pick Azure already have an Azure subscription (or they wouldn't have an Azure OpenAI key). The "no money" failure mode is rarer; the more common failure is "model not deployed in this resource" (`403 deployment_not_found`) — different error-class translation. *Confirm with someone who's used Azure OpenAI before locking copy.*
- **Local has none of this.** Worth saying out loud in the doc so future-Claude doesn't accidentally graft a billing prompt onto Ollama.

Table belongs in code (`billing_hints.py`), not in this doc — when Anthropic moves the billing URL or raises the minimum, we update one constant, not three messages and a man page.

**Maintenance: quarterly audit.** Provider URLs, minimum prepay amounts, billing-page UX, and subscription-confusion sentences *drift*. Anthropic's console reorg in 2024 moved the keys page twice; OpenAI raised the minimum prepay floor at one point; Google's AI Studio / Vertex split keeps evolving. **A stale `billing_hints.py` makes Bristlenose look careless — exactly the trust-cost we cannot afford on a tool that asks for API keys.** Schedule a recurring quarterly task (calendar / cron / scheduled-agent) that walks the table and verifies:

1. Each URL still resolves (no 301/404 — `curl -ILso /dev/null -w "%{http_code}" <url>`).
2. The pages still describe the flow we claim (paste credit, set minimum amount, generate key).
3. Minimum prepay amounts still match what the provider docs say.
4. Subscription names (Claude.ai Pro, ChatGPT Plus, Google One, Gemini Advanced) still exist and the "doesn't fund API" claim still holds.
5. No new provider has joined the four (e.g. xAI Grok API, Mistral La Plateforme) that we should add.

Output: one PR against `bristlenose/llm/billing_hints.py` per provider that changed, or a "no changes — verified 2026-QN" commit if everything's stable. Quarterly cadence is the floor; if a cohort member surfaces a stale message between audits, file an interrupt and update.

Cheapest way to operationalise: a scheduled Claude agent (see `/schedule` skill) that fires the first of every third month, reads `billing_hints.py`, WebFetches each URL, and opens the PR or files a "no drift detected" note. Doesn't replace human judgment on copy changes — flags drift, doesn't auto-merge.

Other error-class translations, same shape (translate the provider's error class into a recovery hint with a URL):

- `401 invalid_api_key` → "Key looks wrong. Check for stray spaces / quotes when you copied it. Re-paste below."
- `403 permission_denied` → "Key works, but doesn't have permission for the model Bristlenose uses. Visit `<keys URL>` to check the key's allowed models."
- `429 rate_limit_exceeded` → "Account is rate-limited right now — wait 60s and re-run, or visit `<rate-limits URL>` to see usage tier."

Validation runs in <1 s for typical providers. Worth every millisecond.

#### Branch (2): doesn't-have-a-key-yet flow

> **Status:** 🟡 deferred to follow-up. The shipped `preflight_api_key` covers the *has-a-key, validate-it-now* path; the numbered-URL flow below has not landed. The existing `_maybe_prompt_for_provider` path in `cli.py` covers the simpler "missing-key → prompt" case. Full deferral rationale + concrete follow-up steps are in the Decisions block of `.claude/plans/cli-just-works.md`.

```
  No account yet? Here's the path — open in a browser:

    1. https://console.anthropic.com/login         (create account)
    2. https://console.anthropic.com/settings/billing  (add payment, ~$5 minimum)
    3. https://console.anthropic.com/settings/keys (create key, copy it)

  This usually takes 5–10 minutes. Bristlenose will wait here.
  When you've copied the key, paste it below and press Enter.
  (Or Ctrl+C to exit and come back later — your next `bristlenose`
  invocation will pick up where you left off.)

  > _
```

Then drop into Branch (1)'s paste/validate/persist flow.

**Why list URLs not screenshots:** brittle. Anthropic's console changes UI; URL paths have been stable for years. Plus: copy-paste-able into a terminal a user can ⌘-click in any modern terminal emulator.

**Resumability:** if the user Ctrl+C's mid-flow, the marker file isn't written, so re-running `bristlenose <anything>` re-prompts. Pasting a key into an env var manually also works — the next preflight finds it via `os.environ` and just writes the marker file silently. If the validation fails with a "no credit" error, the marker file is *also* not written (because the key isn't actually usable yet) — so after the user adds credit and re-runs, the preflight re-validates and proceeds without another paste.

**Desktop:** same flow lives in the existing first-run Beat 3 sheet (shipped in v0.15.1 Track B Branch 1). Goal here is parity on CLI — *and* parity in timing (Beat 3 is at app launch, not at first-analyse). The CLI's first-invocation prompt is the equivalent moment.

**Out-of-scope:** offering to *generate* a key, paying for the user, signing AUP docs on their behalf. Not our job, never will be.

### Ollama / Local provider (Shape 2 + Shape 1 combined)

If the user picks `--provider local` (or Local in the desktop picker), three things might be missing in order: (a) Ollama not installed, (b) Ollama daemon not running, (c) the chosen model not pulled. Each is its own preflight; each gets a framed message + offered fix:

- Not installed → "Install Ollama from https://ollama.com (free, no account). Run `brew install ollama` on macOS." (Shape 2)
- Not running → "Start Ollama with `ollama serve` (or open the menu-bar app). Bristlenose will wait." (Shape 2 with auto-retry)
- Model not pulled → "Pull `llama3.2:3b` now? (~2 GB, free) [Y/n]" with real progress (Shape 1 — Ollama has its own progress API)

Detailed: a separate `docs/design-local-provider-first-run.md` once we know more from cohort feedback.

### Default whisper model tier (Shape 4)

Currently hardcoded to `large-v3-turbo`. Sensible default for quality. Could be smarter:

- If machine has < 16 GB RAM: prefer `small` (still good, much faster, much smaller download). Surface in run header: "Whisper model: small (auto-selected for your machine; override with `--whisper-model large-v3-turbo`)".
- If user has previously chosen, remember.
- Hard-coded `medium` on the desktop alpha is probably the right call — let cohort feedback choose.

This is a Shape 4 ("pick well, print the choice, don't ask"), not a prompt.

---

## Design debates — resolve before building

Two open debates surfaced while sketching this. Both deserve a 30-minute–to–1-hour spike before either is locked. The primitives below assume one resolution; the other reshapes them.

### Debate 1 — Roll our own download UX vs. let libraries print native progress

The honest framing: "HF Hub's progress bar doesn't fit our Rich spinner" is us bending the world to our spinner, not solving the user's problem. The current code suppresses HF Hub's bars explicitly (`disable_progress_bars()` in `s05_transcribe.py:209`) because the spinner and tqdm fight for the same terminal lines. So we have a choice about which way to bend.

#### Option A — Roll our own (Rich-bridge tqdm class)

Implement a `bristlenose/utils/rich_tqdm.py` adapter that exposes tqdm's protocol while forwarding to a Rich `Progress`. Inject into HF Hub via `snapshot_download(tqdm_class=...)`, into faster-whisper similarly where it exposes the hook, and into any future downloader.

- **Pros:** pixel-perfect, brand-consistent with the rest of the CLI, identical look in light/dark/narrow terminals, behaves predictably in log files (we control the redraw cadence), single visual vocabulary across every Shape-1 blocker.
- **Cons:** every library has a different tqdm-injection point (HF Hub's `tqdm_class` parameter, pip's `--progress-bar`, Ollama's HTTP stream, spaCy via pip's installer) — the shim grows. We are now in the progress-bar business. Maintenance cost recurs whenever those libraries upgrade.

#### Option B — Step aside; let the library print

Detect the cache miss, print one labelled banner ("First-run setup: downloading Whisper turbo, ~1.5 GB, one-off"), exit the Rich spinner context, call the library with its defaults, re-enter the spinner once it returns, print a ✓ line.

- **Pros:** zero shim, zero maintenance. HF Hub's stacked-per-file bars are a familiar idiom to anyone who's ever pulled a model. pip's single aggregate bar is the universal Python idiom. We don't fight upstream changes. Code cost drops from "tqdm shim + Progress + non-TTY fork" to "five lines of banner + ✓".
- **Cons:** we lose pixel-control on those one-off fetches. Style is inconsistent across blockers — HF stacked file bars look nothing like pip's aggregate bar look nothing like Ollama's. Brand voice ("Bristlenose is fetching X") only at the banner edges; the middle is upstream voice.

**Working call (from the prior session):** Option B, because *it's a one-off per machine*. On every run we'd insist on control; once-per-machine the cost/benefit flips. Recording it here so future-Claude doesn't re-open the debate from scratch.

#### Option C — Hybrid

Option B's banner + ✓ outer frame; Option A's Rich-bridge *inside* the banner for any blocker where the library exposes a clean injection point. Best of both: brand at the edges, library idiom in the bytes, *except* where we have a cheap hook for consistency.

- **Pros:** if the Rich-bridge turns out to cost ~50 lines, this is the right answer — eats most of Option A's win without B's inconsistency cost.
- **Cons:** still need to detect-before-start; spinner enter/exit ordering is fiddly; partial consistency may feel worse than fully-native or fully-rolled.

#### Option D — Pre-fetch elsewhere, never in-pipeline

Move all Shape-1 fetches out of the pipeline entirely. `bristlenose doctor --fetch-models` is the official path; the first `bristlenose run` on a cold machine errors with "Run `bristlenose doctor --fetch-models` first."

- **Pros:** the pipeline UX is always "models present"; no in-pipeline download UX needed.
- **Cons:** pushes the question to `doctor`'s UX (we still have to render *something* there). The user who skips `doctor` hits a hard error instead of a working tool. Conflicts with the philosophy at the top of this doc — and the error copy here ("Run `bristlenose doctor --fetch-models` first") is itself an anti-pattern: a tool telling the user to run a different command before the one they typed actually works is exactly the friction the doc opens by ruling out. Listed as a debate alternative for completeness, not adopted.

#### Side-by-side: Whisper vs spaCy native progress (Option B output)

The asymmetry is worth seeing before deciding — Option B accepts that these two look noticeably different mid-banner.

|  | Whisper (HF Hub) | spaCy (pip wheel) |
|---|---|---|
| Mechanism | Snapshot into user cache | pip-installs a wheel into site-packages |
| Progress style | Stacked per-file bars | Single aggregate bar |
| Cache visibility | Shows `~/.cache/huggingface/hub` | None (lives inside the venv) |
| Extra noise | Clean | `Collecting…` / `Installing…` / `Successfully installed` + spaCy's own ✔ line |
| Desktop-channel approach | Same runtime fetch, writes to `~/Library/Caches` | **Different — bundled into sidecar at build time, no runtime fetch.** Out of scope here |

Whisper output under Option B:

```
  First-run setup: downloading Whisper turbo (~1.5 GB, one-off)
  Cache: ~/.cache/huggingface/hub
  config.json:        ████████████████████ 2.1 kB
  tokenizer.json:     ████████████████████ 2.4 MB
  model.safetensors:  █████████░░░░░░░░░░░ 642 MB / 1.5 GB · 14 MB/s
  ✓ Whisper turbo ready
```

spaCy output under Option B *as the library prints by default* (this is **not** the recommended treatment — see the spaCy spec below; included here only to show what stepping aside would actually look like for a 12 MB fetch):

```
  First-run setup: downloading PII detection model (~12 MB, one-off)
  Collecting en-core-web-sm==3.7.1
    Downloading https://github.com/explosion/spacy-models/.../en_core_web_sm-3.7.1.whl (12.8 MB)
       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 12.8/12.8 MB 14.2 MB/s eta 0:00:00
  Installing collected packages: en-core-web-sm
  Successfully installed en-core-web-sm-3.7.1
  ✔ Download and installation successful
  ✓ PII model ready
```

That's eight lines of pip chrome for a four-second download. **Tiny things should feel tiny** — see the cutoff table in the spaCy spec below. The bet Option B makes is that the framing carries the consistency even when the bytes don't — *for big enough downloads to justify the chrome*. spaCy isn't one. Whisper is.

**Spike to run before locking:**
- 30 min: implement Option B for Whisper-only on a fresh machine; capture screenshots in light/dark, narrow window (80 cols), and a log file (no TTY). Does it read?
- 30 min: same for spaCy. Does pip's "Successfully installed" line break the framing, or sit cleanly inside the banner?
- 1 hour: try Option A's Rich-bridge against HF Hub's `tqdm_class=` and faster-whisper. Is the shim 50 lines or 250? That number determines whether Option C is viable.

### Debate 2 — Install backend: pip-in-venv vs uv

Adjacent to the rendering debate, raised on a separate call with the same CTO: would the brew formula (and the developer workflow, and CI) be simpler under [`uv`](https://docs.astral.sh/uv/)? `uv` is Astral's Rust-written drop-in for pip/venv/pyenv, and the CTO felt it more familiar than the `python -m venv` + `pip install` dance.

#### Option α — Stay on pip + venv

What the brew formula does today: `python3.12 -m venv libexec`, then `libexec/bin/pip install bristlenose[serve]==<v>` in `post_install`. Same pattern in CI and contributor docs.

- **Pros:** stdlib (`ensurepip`), universal, no extra binary to install or version-pin. Every Python dev knows it. Brew already gates on `python@3.12`, which brings pip with it. Contributor docs across the Python ecosystem assume pip — no special-casing needed.
- **Cons:** slow cold installs (30-60 s typical for our dep set). `ensurepip` is brittle on the wrong CLT version — we hit exactly that during the A1 verification this session, and the project's CLAUDE.md already calls out the Python 3.14 `ensurepip` regression as a real papercut. Resolver is older / weaker than uv's PubGrub-style one.

#### Option β — Switch to uv

Replace `python -m venv` with `uv venv`; replace `pip install` with `uv pip install`. Brew formula declares `depends_on "uv"`. Same in CI and `.venv` setup for contributors.

- **Pros:** 10-100× faster cold installs (rust binary, parallel downloads, smarter caching). Bypasses `ensurepip` entirely — sidesteps the CLT-breaks-venv class of bug. Drop-in `uv pip install` interface (same args, same lockfile-free workflow), so most existing scripts work unchanged. Single static binary, no Python-bootstrap chicken-and-egg. Resolver is materially better on conflicts. Lockfile (`uv.lock`) when we want reproducibility, opt-in. Astral has shipped momentum; this is not a hobby project.
- **Cons:** newer (2024 GA) — less battle-tested in obscure environments. Adds a dependency on Astral / one more binary. License is Apache-2.0 (fine, but yet-another). For end-users installing via brew, the gain is largely invisible — they don't see install time, they don't see the resolver. For contributors and CI, the gain is real. pip is the lowest-common-denominator in every Python tutorial on Earth; uv adds a "what's that?" beat for new contributors.

#### Where uv would actually help us, and where it wouldn't

| Surface | Win from uv? |
|---|---|
| Brew formula's `post_install` (end-user install) | Marginal — bypasses the `ensurepip` brittleness (real), but install time isn't user-visible enough to matter |
| Developer venv (`.venv/bin/python -m pip install -e '.[dev,serve]'`) | Real — cold install drops from ~45 s to ~3 s. New-contributor experience improves materially. `/new-feature` and worktree setup get faster |
| CI cold installs | Real — every GH Actions run is currently dominated by `pip install`; uv would cut a meaningful slice |
| Snap / Linux pip install path | Real — same install-time win, plus dodges the ensurepip class of bugs we hit on macOS today |
| Desktop sidecar bundling (PyInstaller spec) | None — PyInstaller is the bundler, uv would just be the install step inside the build venv |
| End-user perceived UX | Near-zero — they brew install once, never see the install backend |

#### Who actually benefits — channel-mix reality check

uv's wins concentrate on **contributor venv + CI cold installs**, not end-user installs. End-user brew install time is invisible (one-off, backgrounded, nobody times it). And the channel mix at this stage is heavily macOS / brew:

| Channel | Best guess today | uv-visible benefit |
|---|---|---|
| brew (macOS) | ~85–90 % | None — install time invisible to end user |
| pip on macOS | ~5 % | Small — these users do see install time |
| pip on Linux | ~3–5 % | Small — same |
| snap (Ubuntu) | ~0–2 % (CI broken since 17 Apr) | None — snap bundles its own |
| Contributors | small fixed pool, high per-touch | **Real** — cold venv setup drops ~45 s → ~3 s |
| CI | every PR + release | **Real** — meaningful slice of build time |

So uv is a **developer-experience question, not an end-user-experience question** at the current mix. Worth doing — slow contributor onboarding is a real cost, the `/new-feature` and worktree dance bit us this session — but framing it as a first-run UX win would be misreading the audience. End users will not notice.

**Third audience — evaluators / advisors / tech-aware decision influencers.** The "uv vibe" the CTO surfaced (the friendly CTO, friendly-CTO call, May 2026: "newer, better, what I'd expect") is one data point *in a class* that's becoming a direction of travel. uv is from the same outfit that shipped `ruff`, which won the lint category outright in ~18 months — Bristlenose itself defaults to `ruff` for exactly this reason. uv hit 1.0 mid-2024 and the discourse flipped from "what's uv?" to "why aren't you on uv?" inside 12 months. Pydantic, Polars, FastAPI docs recommend it. The convergence on a single cargo/npm-shaped tool is the Python ecosystem fixing its longstanding embarrassment. Against pure direction-of-travel: pip is in stdlib via `ensurepip` and won't disappear; Poetry was the "newer better" answer 2018-2022 and lost, so "newer" isn't destiny; Astral is VC-backed with unclear long-term governance.

The skew: end-user researchers won't have heard of uv. But the people who *evaluate* Bristlenose for adoption — friend-who-codes advisors, CTO contacts at UXR teams' parent companies, OSS contributors deciding whether to engage — are exactly the cohort where uv-expectation is rising. The credibility tax for "still on pip" rises in *that* class over the next 18 months. So Debate 2's real framing isn't "does uv help users" (no) or "does it help contributors" (yes) — it's "does it help the people who decide whether Bristlenose looks like a credible modern tool." That class is small but disproportionately influential; it's the same class that adopted ruff first and pulled everyone along. the friendly CTO is one data point, and probably an early one rather than an outlier.

#### Working call

**Lean: switch. Question is when, not if — skate to where the puck is going.**

The direction-of-travel argument carries this even before the spikes. Three audiences, one says no, two say yes — and the "yes" from the evaluator/advisor class is the strategically expensive one to be on the wrong side of. uv is following the ruff curve; staying on pip when ruff-adopters expect uv is the same shape as staying on flake8 in 2024. Doable, but each month the credibility cost goes up while the migration cost stays flat.

The spikes are still worth doing — not to decide *whether*, but to size the migration and pick the timing:

- 30 min: replace the brew formula's `python -m venv` + `pip install` with `uv venv` + `uv pip install` on the `a1-brew-formula-fixes` branch. Measure install time. Confirm `[serve]` extras resolve. Confirm the wrapper script still works. *(End-user surface — likely "works, no perceptible win." That's fine — the win isn't here.)*
- 30 min: same in CI on a throwaway branch. Measure cold-run time delta. *(Real signal — sizes the dev-experience win.)*
- 30 min: `.venv` setup in `/new-feature` — does `uv venv .venv && uv pip install -e '.[dev,serve]'` come up cleaner than the current incantation? Does it sidestep the Python-3.14 `ensurepip` papercut documented in CLAUDE.md? *(Real signal — sizes the contributor win.)*

Output of the spikes: a sized handoff with a timing recommendation. Likely "after alpha cohort settles" — pre-alpha is the wrong moment to swap a foundational tool, but the 6–12 months after is the right window, before the credibility tax compounds and before the contributor pool grows enough that migrating docs is a real cost.

**Bail-out condition:** if the spikes uncover a hard incompatibility (a dep that uv can't resolve, a wheel that won't install, sandbox-build implications for the desktop sidecar bundler), revisit. Stay on pip until uv catches up. But absent a real blocker, the migration is "when," not "if."

#### Should uv migration come *before* the first-run UX work?

Tempting (foundation-first reflex), but **no** — and the reasoning is worth recording because it'll get re-asked.

The two streams are nearly orthogonal at the code level. Walking the first-run UX file list against the uv-touch surface, the only overlap is **one subprocess call** in `s07_pii_removal.py` — the spaCy lazy fetch. Everything else (Whisper preflight, ffmpeg preflight, API-key flow, preflight registry, framed message renderer) is downstream of "the venv exists with deps in it" and doesn't care which tool put them there. `uv venv` produces a standard PEP 405 venv, so site-packages layout is identical.

Sequencing arguments for "UX first, uv after":

1. **Audience clocks.** First-run UX helps the alpha cohort that's about to land — weeks-out payoff. uv helps contributors and evaluators on a 6–12 month horizon — months-out payoff. Doing the slow-clock thing before the fast-clock thing is the wrong order.
2. **Stability for the cohort.** Pre-alpha is the wrong moment to swap a foundational tool. Alpha needs the stack stable, not in the middle of an install-backend migration. The CTO call already showed how fragile first-run is; adding "and we just changed how installs work" is a known way to make it worse.
3. **Migration sprawl is bigger than it looks.** uv touches the brew formula, the snap recipe (currently broken anyway), CI workflows, contributor skill scripts, CLAUDE.md, sidecar build, possibly `pyproject.toml`. First-run UX is contained to a handful of files in `bristlenose/`. Doing the sprawling thing first to "lay foundation" only makes sense if it's actually foundation — and it isn't here, because they live in different layers.
4. **The one bug uv would prevent (`ensurepip`-on-wrong-CLT) hit us once.** Once is not a pattern. If it bit five times during first-run UX implementation, that'd change the calculation. It didn't.

**One thing worth doing now to make the eventual uv switch cheap:** write the spaCy lazy fetch through a small `bristlenose/utils/package_install.py:ensure_package(name)` helper that hides the actual install command behind a stable interface. Today the helper shells out to `python -m pip install` (or `python -m spacy download`); at migration time it becomes a one-line change to use `uv pip install`. ~10 minutes of indirection; pays back regardless of when uv lands. The same helper handles any future Shape-1 blocker that needs a wheel installed (vs a model fetched), so it's not over-engineering for one case.

Net sequence: first-run UX now (with the abstracted helper), uv spike + migration after alpha cohort signal lands.

**Open coupling with Debate 1:** uv has its own progress style (Rust-side bars, similar shape to cargo's). Under Option B for Debate 1, uv's bars would be a *third* visual idiom alongside HF Hub and pip — but since uv only appears on contributor/CI surfaces, that's invisible to end users and doesn't reopen the debate. Under Option A (rolled), uv's progress would need a tqdm-compatible hook — does uv expose one? (15-min spike — I don't know offhand.) The answer changes Option A's cost.

---

## Implementation primitives

Things to build once, reuse across blockers. **Note:** primitive (2) — the Rich-bridge tqdm class — only exists under Debate 1 / Option A or C. If Option B wins the spike, delete that line item and pocket the savings.

### 1. Preflight registry (`bristlenose/preflight.py`)

A list of `Preflight` records, each with: a check function, a message renderer, a fix function or instruction, a "skip in CI" flag, and a stage-position marker (run before stage N). The pipeline calls `run_preflights(stage_position)` between stages. Each preflight is independent and resumable.

Bonus: `bristlenose doctor` invokes the same registry, so `doctor` is "run all preflights, report status." Doctor and run share the same vocabulary.

### 2. Rich-bridge tqdm class (`bristlenose/utils/rich_tqdm.py`)

A tqdm-protocol-compatible wrapper around `rich.progress.Progress`. Plug it into HF Hub's `snapshot_download(tqdm_class=...)`, faster-whisper's download paths (where it accepts one), and any future downloader. Removes the "we have to suppress all progress bars because Rich + tqdm fight" trap.

### 3. Framed pre-message renderer (`bristlenose/cli/messages.py`)

A small renderer that takes a `Preflight` and produces the boxed/indented "First run on this machine — …" block, with consistent indentation, colour, and prompt formatting. Same renderer used in `doctor`. Reuses the existing `MessageKind` taxonomy.

### 4. Interactive prompt with `--yes` fallback

We have `--yes` / `-y` for the session-count guard. Generalise to a `prompt_yes_no(question, default=True, force_yes=settings.skip_confirm)` helper, with a `prompt_choice(question, choices, default=...)` for shape-3 picker cases. CI uses `--yes`; interactive users see prompts.

### 5. Resumable download wrapper

Wrap `snapshot_download` to: detect partial cache, render "Resuming download…" vs "Downloading…", show byte-level progress, handle Ctrl+C without corrupting cache (HF Hub already handles this; just don't undo it).

### 6. Provider-key paste flow (CLI)

Echo-suppressed input (`getpass` is fine), validate with a tiny call, optionally persist via a shell-rc edit. Worth factoring so all four providers share one flow.

---

## Glyph discipline

Glyphs are for **state changes**, not narrative. Plain text is the default. The CLI inherits the same `MessageKind`-derived glyph set the desktop uses, but only on state-event lines:

| Surface | Glyph | Used for |
|---|---|---|
| In-progress action | `⠋` (Rich spinner frame) | something is working |
| Successful step or check | `✓` | passed |
| Hard error / halt | `⊘` (or existing error glyph) | failed; user must act |
| Warning | `⚠` | caution; non-blocking |
| Plain explanation, banner, context | *none — just text* | not a state event |
| Input prompts | optionally `>` if REPL-shaped, else nothing | the `[Y/n]` brackets carry meaning |

The "i-in-a-blue-circle" affordance familiar from GUIs is doing work that plain text already does in CLI. A line that starts with no glyph and just says something *is* self-evidently info. Adding a glyph for it would be CLI-as-GUI cosplay.

**This means:** the existing 5-kind `MessageKind` taxonomy is sufficient for CLI preflight surfaces. No new `PROMPT` kind, no preflight-specific glyph extensions. Preflight rendering composes existing glyph atoms (`✓`, `⊘`, `⠋`, `⚠`) for state lines and plain text for everything else. Saves a taxonomy extension and a renderer module file.

## Anti-patterns (things to refuse to ship)

- **Silent magic on credential surfaces.** When the tool picks up a key from somewhere the user didn't necessarily expect (an old env var, a synced Keychain entry, a previous-install config), it must say so the first time. "Using key from env var" / "Using key from Keychain" is one line of trust; silently using a key the user can't see is one line of WTF-just-happened. Same goes for any credential or secret-shaped state.
- **Silent waits longer than ~5 s.** No matter how brief the pre-message would feel, "nothing" is worse.
- **Errors that point at internal commands.** "Run `python -m spacy download en_core_web_sm`" is what the tool should run, not what the user should run. Same for `pip install bristlenose[serve]` — that should be in the formula, not in an error message.
- **"Set this env var and retry."** If we know the env var is needed, ask for the value now and proceed.
- **Asking questions with no good default.** Every prompt has a pre-selected answer that works for the median user. If you don't know the median, don't ship the prompt.
- **Five-question first-run wizards.** Aim for zero prompts ideal, one prompt typical, two prompts max. More than two means you haven't picked enough defaults.
- **Different vocabulary on CLI and desktop.** The first-run user is one person across both surfaces; the tool isn't two products.
- **Surfacing model paths, cache paths, or env vars in the main flow.** Those belong in `doctor`, in `--verbose`, and in the man page — not in the path to the report.

---

## Cross-channel notes

**CLI:** the surfaces above are the primary target. Most preflights are interactive; `--yes` is the CI bypass.

**Desktop (macOS):** shares the *philosophy* with this doc, not the implementation. The equivalent surfaces are first-run sheets (Beats 1–3, shipped in v0.15.1), the pipeline diagnostic popover ([`docs/design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md)), and the Settings panel. Same vocabulary, different chrome. Where the CLI fetches at runtime, desktop generally **bundles at build time** — spaCy ships in the sidecar, ffmpeg/ffprobe ship in Resources, etc. The one runtime-download case that survives on desktop is the Whisper model (lives in the user's HF cache, sandbox-safe) — the only place where this doc's primitives carry over more or less verbatim. Sidecar packaging mechanics, sandbox entitlements, and build-time bundling decisions all live in the sidecar / Track C docs, not here.

**Snap / Linux:** snap bundles ffmpeg and most deps; the missing-ffmpeg flow is dormant. spaCy and Whisper flows behave like CLI. Worth one cohort run on Linux before assuming parity.

---

## i18n implications

All preflight strings live in the `preflight` namespace under
`bristlenose/locales/<locale>/preflight.json` and route through
`bristlenose.i18n.t()`. English is the source of truth; the five other
locales (`es`, `fr`, `de`, `ko`, `ja`) fall through to English via the
existing fallback path until a translator copies and adapts each section.

**Namespace shape** (`bristlenose/locales/en/preflight.json`):

- `whisper.*` — banner intro, reassurance line, verb (`Downloading` / `Resuming download`), fetching template, ready line, `--no-fetch` abort copy
- `ffmpeg.*` — banner, brew prompt, ready line, abort copy, five install-table rows (one per distro)
- `api_key.*` — source attribution, four error-class messages (`invalid_key`, `billing_empty`, `model_unavailable`, `rate_limit`), generic fall-through
- `closing.*` — "No more questions" line with/without estimate

**Channel-fork inventory** — all preflight strings are CLI-only. The
desktop sidecar bundles spaCy + Whisper + ffmpeg at build time and uses a
Swift-side Keychain flow, so none of `preflight.whisper.*`,
`preflight.ffmpeg.*`, or `preflight.api_key.*` fire under the desktop
runtime. The `dt()`/`ct()` channel-fork helpers in `frontend/` don't
apply because these strings are consumed only from Python; the equivalent
on the Python side is "this whole namespace is CLI-only," documented
here.

**Code-owned (not translated):**

- URLs in `bristlenose/llm/billing_hints.py` (`console.anthropic.com/...`, `platform.openai.com/...`, etc.) — factual provider properties
- `minimum_note` string in `ProviderBilling` (the "$5 minimum, subscription does not fund API" sentence) — interpolated into translated wrappers but the factual content is static
- The locked validation prompt (`_VALIDATION_PROMPT = "."`) and `User-Agent` header — never user-visible
- The Whisper repo IDs (`mlx-community/whisper-large-v3-turbo`, `Systran/faster-whisper-large-v3`) — registry keys, not prose
- Hardcoded size string (`~1.5 GB` for Whisper) — see formatting rules below

**Formatting rules:**

- ICU-style `{placeholder}` interpolation. Placeholders that are factual
  (URLs, model repo IDs, shell commands like `brew install ffmpeg`,
  `bristlenose doctor --fetch`, `--no-fetch`) pass through unchanged in
  every locale.
- USD provider amounts stay USD (`$5`); locales may adapt the *separator*
  (e.g. `$5,00` in fr-FR) but never the currency. Bristlenose itself
  doesn't transact; we're echoing the provider's pricing in the
  provider's currency.
- Size strings (`~1.5 GB`) currently ship as a literal English string.
  A future pass can route these through `babel` for locale-appropriate
  separators (`~1,5 Go` in fr); the placeholder name (`{size}`) is
  already in the template so the swap is single-call.
- Backtick-wrapped shell commands and file paths in messages are
  treated as code spans and shouldn't be translated even when nested
  inside translated prose.

**Translator workflow:** copy `en/preflight.json` to each target locale,
translate prose around the `{placeholder}` markers, keep the JSON
structure identical. See CLAUDE.md → "i18n — single source of truth" for
the JSON round-trip gotcha (don't re-dump existing locale files; this
namespace is fresh so it's a non-issue for the first translation pass).

---

## Open questions

See **Design debates** above for the two big ones (rendering ownership and install backend). The rest:

- ~~First-run default tier — settled, `large-v3-turbo`.~~ Kept as a strikethrough so future-Claude doesn't re-derive the question. The only adjacent live question is whether to auto-downshift on machines that can't handle turbo cleanly — and even that's "fallback if it bites us," not a default-tier question.
- **Pre-warm during `doctor`:** should `bristlenose doctor` offer "fetch the Whisper model now? [Y/n]" so the first real run never blocks? Cheap to add once the preflight registry exists; reuses the same primitives. Lands under Debate-1 Option D as the *main* path; under A/B/C as a *backup* path.
- **API-key persistence path:** writing to `~/.zshrc` is one option, but a `~/.config/bristlenose/keys` file readable only by user, with `bristlenose doctor` documenting where it lives, may be cleaner than mutating the shell rc.
- **Cancellation semantics during model download:** Ctrl+C should leave the cache resumable, not corrupt. HF Hub handles this by default — confirm under load. Same question for uv if Debate-2 / Option β wins.
- ~~Sandbox + spaCy — runtime download path under App Sandbox.~~ Resolved: desktop bundles the spaCy model into the sidecar at build time (standard packaging), so there is no runtime download on desktop. Lives with sidecar bundle work, not here. Kept as strikethrough so future-Claude doesn't re-derive it.
- **Telemetry hooks:** the alpha telemetry system (Phase 1 plumbing on main) could measure how often each preflight fires and how often users abort. Worth wiring once the registry is in place.
- **Channel-mix telemetry (one-evening slice).** Cheapest single ping that would unlock multiple prioritisation decisions: a one-off, opt-out, anonymised first-launch marker carrying channel only — `brew` / `pip-macos` / `pip-linux` / `snap` / `desktop-mac`. Never repeated. Lets every subsequent call (Debate 2 weight, ffmpeg-preflight scope, snap-fix urgency, where to invest first-run polish) be made with data instead of guessing 85 % brew. Currently *guessing* is fine; once there's a cohort, this is one of the highest-ROI telemetry items to wire. Skips ahead of full Phase 2 telemetry — single-purpose ping.
- **Does uv expose a tqdm-compatible progress hook?** Direct input into Debate 1 Option A's cost estimate. Spike-able in 15 min.

---

## Sequencing — what to build first

Two spikes first; they reshape everything below them.

0a. **Spike Debate 1.** Implement Option B for Whisper-only on a fresh machine. Capture screenshots in light/dark, narrow window, log file. ~1 hour. Output: a one-paragraph "B works / B doesn't / try C" call appended to this doc.

0b. **Spike Debate 2.** Replace `python -m venv` + `pip install` with `uv venv` + `uv pip install` on a throwaway brew-formula branch and in CI. Measure install time. ~1 hour. Output: a one-paragraph "switch / stay / stay-for-now-revisit" call appended to this doc.

Both spikes are independent; run in parallel sessions.

Then, smallest-useful-first (helper-first per Debate-2 / finding 36 design call; registry/collector emerges later if Rule of Three fires):

1. **`bristlenose/utils/package_install.py` — three helpers, not one.** Per finding 10 design call: `ensure_wheel(pip_spec)`, `ensure_spacy_model(model_name)`, `ensure_hf_model(repo_id)`. Each call site already knows which verb it needs; the apparent shared interface is over-abstraction. Each helper hides its own install command (today `pip install` / `python -m spacy download` / `huggingface_hub.snapshot_download`; tomorrow `uv pip install` for the wheel helper if Debate 2 lands a switch). Resume / error / target-dir semantics documented per-helper, not in a single shared docstring. ~1 h to write three small focused functions; pays back if/when a fourth install-shaped operation arrives (let it be its own helper too).
2. **spaCy lazy fetch.** Ships value within hours. Goes through the helper from (1). (State writes use a small in-house path resolver — `state_path()` in `bristlenose/preflight/api_key.py` — rather than adding `platformdirs` as a dep.) ~1 h.
3. **Whisper preflight (conditional on `needs_transcription`).** Per finding 39 design call — only fires if any session needs transcription. Teams/Zoom users never see this. Banner + auto-proceed (no Y/n per finding 5). Hardcode `~1.5 GB` in banner (finding 3 — no `model_info()` network call). ~half-day.
4. **ffmpeg preflight on pip-installed channels.** Distro-aware install instructions; macOS-with-brew gets `[Y/n]` auto-install offer. ~half-day.
5. **API-key preflight + first-invocation marker.** Keychain on macOS (finding 1), `~/Library/Application Support/Bristlenose/` for marker (finding 2), validation-exercises-billing (paid `/messages` call, locked inert prompt content per finding 15), 24-hour TTL on successful validation (finding 7), three-tier validation policy (LLM commands validate, read-only don't, billing-empty has separate attempted-marker). Has-a-key branch + no-account-yet branch with URLs. Whitelist `--help` / `--version` / `status` / `render` / non-TTY (finding 4). ~1.5 days.
6. **Front-loaded question collector.** After items 2–5 ship as own implementations, factor the "enumerate all user-input questions upfront, ask in one block, then execute autonomously" pattern (per the §Architectural principle section). Rule of Three: items 3, 4, 5 each have questions or banners; if their shape rhymes, factor. If they're too different, leave them as bespoke per-blocker and accept that the *philosophy* is enforced by code review rather than by a shared abstraction. ~half-day to factor, or 0 if Rule of Three doesn't fire.
7. **Quarterly drift audit on `billing_hints.py`.** Recurring scheduled task. Walks provider URLs, verifies minimums + subscription-confusion claims still hold. Already scheduled (cron `0 9 1 1,4,7,10 *`, routine `trig_01BtVXKG5hBnhPF4bGwR78CR`). ~30 min to land the code once `billing_hints.py` exists; cron is already armed.
8. **Machine-capability fallback for Whisper.** Only if `large-v3-turbo` is shown to OOM / thrash on real low-RAM cohort machines. Likely a no-op; park until a real signal arrives. *(The default tier itself is settled — turbo. This item is fallback-only.)*

9. **Rich-bridge tqdm class.** *Only if* Debate 1 / Option A or C wins post-spike. Skip under Option B. ~half-day if needed; default expectation is "skip."

Total: roughly a week of focused work, all of which is "lift first-run completion rate from `<50 %` to `>90 %`." The CTO call was the lower bound; the upper bound is what shipped.

---

## See also

- [`docs/design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md) — `MessageKind` taxonomy and length budgets (the failure-side counterpart to this doc's success-side flow).
- [`docs/design-cli-improvements.md`](design-cli-improvements.md) — existing CLI polish backlog.
- [`docs/design-doctor-and-snap.md`](design-doctor-and-snap.md) — doctor command and Snap packaging context.
- [`docs/design-pipeline-resilience.md`](design-pipeline-resilience.md) — resume / manifest / `Cause` plumbing this builds on.
- [`docs/design-modularity.md`](design-modularity.md) — cross-channel component strategy (CLI ≡ macOS code path).
- `bristlenose/stages/s05_transcribe.py` — current Whisper-fetch silence.
- `bristlenose/stages/s07_pii_removal.py` — current spaCy hard-fail.
- `bristlenose/utils/bundled_binary.py` — already-shipped ffmpeg discovery for the desktop bundle.
