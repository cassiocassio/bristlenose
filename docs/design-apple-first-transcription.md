---
status: proposal
date: 18 Oct 2026
revised: 18 Oct 2026, after five reviews (§7)
---

# Apple first, Whisper next: the first recordings on a new Mac

**Proposal, 18 Oct 2026. Nothing here is built.** Evidence:
`experiments/apple-speech/README.md` (the trial, 18 Oct 2026). Storyboard:
`docs/mockups/apple-first-first-run.html`.

## 1. The slice

When **all** of these hold for a run, transcribe it with Apple's on-device
`SpeechTranscriber` instead of waiting for Whisper, and say nothing about it:

1. the Mac app (the bundled sidecar), not the CLI;
2. macOS 26 or later (checked at run time; the app's floor stays 15.0);
3. Whisper is **not on disk**: `cache_state(_resolve_repo_id(settings)) != "cached"`, so a
   partial, failed or stopped download counts as absent;
4. no pinned transcription language (`whisper_language` is `auto`), and the app's UI
   language maps to one of Apple's nine (§2);
5. the session has no platform transcript (those already need no model);
6. Transcription is set to *Whisper when ready* (§4), and the experimental flag is on
   (§3 J) until the gate is measured on more files.

**The engine is chosen once per run**, as the backend is today (`s05_transcribe.py:682`):
a six-file drop goes wholly to Apple, and Whisper landing mid-run does not switch it.
Meanwhile Whisper downloads in the background as one app-wide job, with progress that does
not lie. Every run after it lands uses Whisper. Sessions Apple transcribed **stay Apple's**
(§3 F lists the paths that would re-transcribe them).

Why this and nothing wider: the trial found Apple level with Whisper on English and
one-to-one interviews in those nine languages (98–100% of Whisper's words, 4–12% apart,
fewer inserted words, no loops, 3.2× faster, ~180 MB of memory against Whisper's 9.2 GB
footprint), and a first run that spends 3–7 minutes on a 1.6 GB download before any report
exists (README § 4). It found Apple weaker on group talk, its pre-macOS-26 model unusable
(§ 5), and the small Whisper model a poorer stopgap than Apple in Apple's languages (§ 13).

## 2. The language guess, and how it fails

Apple needs a locale up front; Whisper detects it. v1 takes **the UI language as the
interview's language** (owner, 18 Oct 2026). **This reverses `cca68462` (22 Sep 2026)**,
which removed exactly that coupling because "the UI language belongs to the reader, the
spoken language belongs to the recording", and it hurt a UK study with Polish participants.
The reversal is confined to Apple's stopgap: Whisper still detects per file, a pinned
`whisper_language` always wins, and the gate below sends a wrong guess to Whisper.

Measured on five recordings (README § 4, "A wrong language guess"): English audio under
the Spanish or German model came back **as English** (confidence 0.68–0.84 over the whole
file); German, Spanish and French audio under the English model came back as a few words
at **0.10–0.30**, against 0.92–0.93 in the right language.

**Gate, per session, over the whole file** (Apple runs at ~80× real time, so this costs
seconds; the first two minutes can be silence, music or small talk in another language):
the session fails the gate when Apple's mean word confidence is under **0.5**
(`LOW_CONFIDENCE` in `transcription_quality.py`; reuse `confidence_measures()`), or when it
returns fewer than a floor of words per minute of signal (the signal gate's RMS windows),
which also catches zero words over speech. Five files are too few to trust 0.5; measure on
more before the flag comes off.

**A session that fails the gate is deferred, not lost.** The run finishes with the other
sessions; the deferred one is recorded as a stated, retryable state (a `StageFailure` of a
new deferred kind), its row says *Waiting for download* (§4), and when the download
completes the app re-runs it through the existing retry path with Whisper, which detects
the language. If the researcher stops the download, it stays visible and retryable
(failed runs must be visible and retryable). Add it to
`docs/design-lifecycle-failure-modes.md` and `tests/test_lifecycle_scenarios.py`.

**Locale mapping** is a table, not a guess: `en-*` → `en-*`; `es`, `fr`, `de`, `it`, `ko`,
`ja` → their main region; `pt-BR` → `pt-BR`, `pt-PT` → `pt-PT`; `zh-Hant` → `zh-TW`;
`zh-Hant-HK` → refuse (Cantonese vs Mandarin is the speaker's, not the UI's). Record the
locale as **assumed**, never as `detected`, so subtitles and clips don't inherit a guess.

## 3. Engineering

| # | Piece | Where | Notes |
|---|---|---|---|
| A | **Speech helper** `bristlenose-speech`: WAV + locale in, JSON out (segments, words with time ranges and confidences, asset version) | new `desktop/speech-helper/` | Most of it is `experiments/apple-speech/transcribe.swift`. **Built like `desktop/mcp-helper/`** (embedded Info.plist, `PrivacyInfo.xcprivacy`, minos = the app's 15.0 floor, `Contents/Helpers`), **signed like ffmpeg** (`sign-ffmpeg.sh`: sandbox + inherit, because the sidecar launches it; mcp-helper is sandboxed *without* inherit because a foreign app launches it). Its own gate script, not a copy of `check-mcp-helper.sh`, which asserts the opposite. `if #available(macOS 26, *)`; reports *unavailable* below. Holds its own five locale reservations and releases each after use, by the stored `Locale` object |
| B | **Engine decision + backend** | `s05_transcribe.py` | A **separate** decision function fed settings, env and the helper's availability. `_resolve_backend` stays as it is: the preflight (`whisper.py:148`) and `doctor` share it, and a third value would pick the wrong repo table. `_init_apple_backend` returns `TranscriptSegment`s with words, `source = "apple-speech"`, **re-segmented** on word gaps over ~0.7 s and sentence ends (Apple's results are long, and stage 5b labels per segment). Keeps the signal gate; skips the style prompt, echo filter and inaudible marker (Whisper-specific). Applies the gate (§2) |
| C | **No fetch from Python on the Apple path** | `pipeline.py` `_needs_whisper` block | With the helper set, Python never fetches: the app owns the one download. A deferred session waits on that job by its outcome, never by calling `ensure_hf_model` itself (two fetchers of one repo each write their own partial under hf_xet) |
| D | **The download job** | Swift `WhisperDownloadModel` (app-level `@StateObject`, sibling of `OllamaDownloadModel`), single-flight across windows; Python **`bristlenose doctor --fetch`** (already a sidecar passthrough) | `doctor --fetch` gains one structured progress line per tick from `ensure_hf_model(tqdm_class=)` (the seam `_native_download_progress` already uses), parsed like `ServeManager.handleLine`. Bytes from the wire, total from the server, not `_DOWNLOAD_MB` (which drifts) or blob growth (which hf_xet chunking distorts). Restart on relaunch when `cache_state == "partial"` (the appliance copes). Starts at the first Apple run, or at the first welcome screen if the owner prefers (§6) |
| E | **Record the engine** | transcription-quality record (`recognition.backend`, locale `assumed`, asset version), segment `source` | The Diagnostics row types `backend` but renders nothing (`TranscriptionDiagnostics.tsx:32`); render it there |
| F | **No re-transcription** | stage-5 fingerprints unchanged | The engine must not join the fingerprint, or a re-analyse silently re-transcribes and orphans stars, tags and edits (README § 7). Known paths that will re-transcribe anyway: `--clean`, a copy without `-p`, a folder moved before its first post-upgrade run. Warn on those when the engine would change |
| G | **Settings ▸ Transcription** | `TranscriptionSettingsView` | Redesigned (§4): one behaviour choice and a Whisper status row; MLX vs faster-whisper moves behind the Diagnostics preference; the interim model picker leaves the pane |
| H | **Progress wording** | Swift | Foundation's `Progress` (`kind = .file`, `fileOperationKind = .downloading`, throughput and time-remaining keys) composes "600 MB of 1.6 GB (10 MB/s) — About 2 minutes remaining" in every locale; probe the exact string before relying on it. Throughput over an 8–10 s window, *Calculating…* until it fills, minutes with hysteresis |
| I | **Honest ETAs** | `timing.py` | Key the `transcribe` timing sample by engine (`build_hardware_key` doesn't know it), or Apple's 3× pace poisons Whisper's estimate. A Mac with no history shows no ETA (`initial_estimate` returns `None`), and the storyboard follows |
| J | **Parked behind a flag** | `Config.experimental_apple_speech` (Python), mirrored in `BristlenoseFlags` | Default off for the cohort; tests for both shapes; removed once the gate is measured on more files |
| K | **Strings** | `desktop.json`, 21 locales | §4 |

**Tests.** Python: the engine-decision matrix (OS, helper present or missing or
unavailable, Whisper cached / partial / missing, pinned language, UI language, platform
transcript, flag); the gate at zero words, on a sub-two-minute file and on a code-switched
file; the helper's JSON contract as a fixture both sides read; re-segmentation; `source` and
`assumed` locale; fingerprint unchanged when the engine changes; the run does not block on
the Apple path (mutation-proved); the deferred-session lifecycle. Swift: `WhisperDownloadModel`
progress, window and hysteresis as pure helpers; single-flight; restart on relaunch. Gates:
the helper's own script (build, sign, inherit, floor, Info.plist); the fifth executable in
`tests/test_entitlements_split.py` and `check-bundle-integrity.py`; an app-store-police pass
with its privacy manifest. **Consent:** no change; audio never leaves the Mac (no network
entitlement, the model fetch is inbound, by a system daemon), so the AI disclosure's
"recordings stay on your device" stays true. Say so in About.

**Acceptance walks** (by hand, once): English UI, fresh account, English recording;
English UI, Spanish recording (deferred, then retried when Whisper lands); stop the download
and reopen; a sixth locale; macOS 15 guest (no change from today); offline with English.

**Rough size.** Helper 1–2 days; engine decision, backend, gate, deferral 3; download job,
pill and progress 3; settings pane 1–2; strings, tests, gates and walks 2–3. About three
weeks, with unmeasured risk in the helper's signing and sandbox inheritance.

## 4. The UX change

Frames refer to the storyboard.

1. **The row moves straight to real stages** (*Transcribing · 1 of 1*), with no time
   estimate on a Mac that has never run anything, instead of *Analysing · ~2 min left*
   while an uncounted 1.6 GB download runs. [1, 2]
2. **A download pill in the toolbar's status zone**, on the `StatusPill` envelope, sibling
   of the Ollama download pill. Its popover: *Downloading speech model*; Foundation's
   progress line; one sentence of why; **Stop Download**, with *Starts again from the
   beginning next time* (there is no resume, so Cancel would hide a loss). It disappears
   when Whisper is ready, so absence keeps one meaning. [2, 3]
3. **The report arrives about three minutes sooner** on typical broadband. [3]
4. **A deferred session** reads *Waiting for download*, the `.queued` row's sibling (info,
   no glyph, no door), with its one sentence in the row's tooltip. [4]
5. **Settings ▸ Transcription** becomes one behaviour choice and a status row. [5]

```
Transcribe with                                  [ Whisper when ready ⌄ ]
Apple's speech model is already on this Mac and is faster. Whisper copes better with
poor audio, people talking over each other, larger groups, and languages Apple's model lacks.
──────────────────────────────────────────────────────────────────────────────
Whisper                     ▓▓▓▓▓▓░░░░  600 MB of 1.6 GB · About 2 minutes   [Stop Download]
```

The pop-up's items: **Whisper when ready** (default: Apple until Whisper is on disk),
**Whisper only** (never Apple), **Apple's speech model** (Apple in its nine languages,
Whisper for the rest; for clean one-to-one calls and small Macs). Below macOS 26 it shows
*Whisper* alone, dimmed, with *Apple's speech model needs macOS 26.* The status row shows
**Download Now** / progress with **Stop Download** / *On this Mac · 1.6 GB*, from the same
`WhisperDownloadModel` as the pill, and posts no `.bristlenosePrefsChanged`.

| Key | English | Status |
|---|---|---|
| `desktop.chrome.pipeline.stage.*`, `sessionsCount`, `analysing` | as shipped | reused |
| `desktop.modelDownload.pill`, `.title` | *Downloading speech model* | **new** (move Ollama's `pillDownloading`/`downloadingTitle` here too, one namespace) |
| `desktop.modelDownload.why` | *For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.* | **new, owner to word** |
| `desktop.modelDownload.stop`, `.stopNote` | *Stop Download* · *Starts again from the beginning next time.* | **new** |
| `desktop.chrome.pipeline.waitingForDownload`, `…Hint` | *Waiting for download* · *This recording doesn't sound like {{language}}. It will be transcribed once Whisper has downloaded.* | **new, owner to word** |
| `desktop.transcriptionSettings.engine*`, `whisper*`, `downloadNow` | per the wireframe | **new** (replace `backendLabel`, `backendAuto`, `backendHint`) |
| progress line | Foundation's `Progress.localizedAdditionalDescription` | system, no key |

## 5. What stays as it is

The CLI (no helper), Linux and Windows, macOS 15, every run with a platform transcript,
every run once Whisper is on disk, and every pinned-language run.

## 6. Open questions for the owner

- **Show the engine per session?** README § 9 said to; this plan keeps it to the
  Diagnostics row because 98% of sessions are one-to-one. A day-one focus group would lose
  its quieter voices with no tell.
- **Start the download at the first welcome screen, or at the first Apple run?**
- **Wording**: the *why* sentence, the deferral hint, and *Waiting for download* vs
  *Waiting for Whisper*.
- **Reproducibility:** Apple updates its model silently. Recording the asset version is
  enough for now, or should the Diagnostics row flag a version change?
- **macOS 26's locale list** (the trial read 27 only); the order of the pills in the
  status zone (already open).

## 7. Reviews (18 Oct 2026)

Five reviews ran on the first draft (code paths, Bristlenose fit, plan, Mac progress taste,
the settings pane). Changes taken: the engine is per run, not per session; a separate
decision function instead of a third `_resolve_backend` value; the helper signed like
ffmpeg, not mcp-helper; `doctor --fetch` instead of a new command; Python never fetches on
the Apple path; the gate over the whole file with a words floor and a deferred, retryable
state; the `cca68462` reversal stated and bounded; locale table and *assumed* locale;
re-segmentation for the speaker pass; no ETA without history and engine-keyed timing;
Foundation's progress wording; *Stop Download*; the `StatusPill` envelope; tooltip instead
of a popover for the deferred row; the settings pane redesigned; a parked flag; and the
Diagnostics row's missing `backend` render. Also found: `desktop/CLAUDE.md` put the Whisper
model in Application Support; it lands in the container's Hugging Face cache (corrected).
