---
status: built, on by default since 22 Oct 2026 (§8)
date: 18 Oct 2026
revised: 12 Nov 2026 (Settings pane, §4 amendment, §8); first revised 18 Oct 2026, after five reviews (§7)
last-trued: 2026-11-13
trued-against: main at b9effa628, 13 Nov 2026 (the Settings work of 12 Nov, committed 13 Nov, and its third review pass)
---

# Apple first, Whisper next: the first recordings on a new Mac

**Built 18 Oct 2026; unparked 22 Oct 2026 (owner: unpark now, without the wider
gate measurement). `BristlenoseAppleSpeech` (Mac) and `experimental_apple_speech`
(Python) are now default-on kill switches. §8 records what was built, where it
departs from §1–§4, and what is still owed.** Evidence:
`experiments/apple-speech/README.md` (the trial, 18 Oct 2026). Storyboard:
`docs/mockups/apple-first-first-run.html`.

> **Trued 13 Nov 2026** against the tree. **Changed:** §1 item 6 and the engine-chosen-once line
> (the pop-up is *Whisper* / *Apple's speech model* since 12 Nov); §3 D (probe coalescing), G and J
> (G superseded, J now default-on) and the Tests paragraph (the helper's gate); the §4 key table;
> §5; §6 (answered questions marked in place); §7 and §8 (a dated 12 Nov entry, the Debug-only
> bullet, the still-owed list). **Kept as the record:** the 18 Oct wireframe, row G's body and the
> pre-12-Nov wording, each marked superseded beside it. **Re-checked later on 13 Nov** after the
> third review pass (§3 D, §7; no re-audit: the delta was four commits of this subject). **Not
> verified:** the Notes for Review paragraph; the macOS 26 walk of the 12 Nov pane is partly done
> (dark mode, five states) and still owed for the failed and checking states, light mode and
> long locales.

## 1. The slice

When **all** of these hold for a run, transcribe it with Apple's on-device
`SpeechTranscriber` instead of waiting for Whisper, and say nothing about it:

1. the Mac app (the bundled sidecar), not the CLI;
2. macOS 26 or later (checked at run time; the app's floor stays 15.0);
3. Whisper is **not on disk**: `cache_state(_resolve_repo_id(settings)) != "cached"`, so a
   partial, failed or stopped download counts as absent (under the default engine; *Apple's
   speech model* skips this condition, §4);
4. no pinned transcription language (`whisper_language` is `auto`), and the app's UI
   language maps to one of Apple's nine (§2);
5. the session has no platform transcript (those already need no model);
6. Transcription engine is *Whisper* (the default; stored as `whisperWhenReady`, Python
   `until-whisper`; called *Whisper when ready* until 12 Nov 2026) or *Apple's speech model*
   (§4), and the `experimental_apple_speech` kill switch has not been turned off (§3 J).

**The engine is chosen once per run**, as the backend is today (`decide_engine` in `s05_transcribe.py`):
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
| A | **Speech helper** `bristlenose-speech`: WAV + locale in, JSON out (segments, words with time ranges and confidences, asset version) | new `desktop/speech-helper/` | Most of it is `experiments/apple-speech/transcribe.swift`. **Built like `desktop/mcp-helper/`** (embedded Info.plist, no privacy manifest of its own (§8), minos = the app's 15.0 floor, `Contents/Helpers`), **signed like ffmpeg** (`sign-ffmpeg.sh`: sandbox + inherit, because the sidecar launches it; mcp-helper is sandboxed *without* inherit because a foreign app launches it). Its own gate script, not a copy of `check-mcp-helper.sh`, which asserts the opposite. `if #available(macOS 26, *)`; reports *unavailable* below. Holds its own five locale reservations and releases each after use, by the stored `Locale` object |
| B | **Engine decision + backend** | `s05_transcribe.py` | A **separate** decision function fed settings, env and the helper's availability. `_resolve_backend` stays as it is: the preflight (`whisper.py:148`) and `doctor` share it, and a third value would pick the wrong repo table. `_init_apple_backend` returns `TranscriptSegment`s with words, `source = "apple-speech"`, **re-segmented** on word gaps over ~0.7 s and sentence ends (Apple's results are long, and stage 5b labels per segment). Keeps the signal gate; skips the style prompt, echo filter and inaudible marker (Whisper-specific). Applies the gate (§2) |
| C | **No fetch from Python on the Apple path** | `pipeline.py` `_needs_whisper` block | With the helper set, Python never fetches: the app owns the one download. A deferred session waits on that job by its outcome, never by calling `ensure_hf_model` itself (two fetchers of one repo each write their own partial under hf_xet) |
| D | **The download job** | Swift `WhisperDownloadModel` (app-level `@StateObject`, sibling of `OllamaDownloadModel`), single-flight across windows; Python **`bristlenose doctor --fetch`** (already a sidecar passthrough) | `doctor --fetch` gains one structured progress line per tick from `ensure_hf_model(tqdm_class=)` (the seam `_native_download_progress` already uses), parsed like `ServeManager.handleLine`. Bytes from the wire, total from the server, not `_DOWNLOAD_MB` (which drifts) or blob growth (which hf_xet chunking distorts). Restart on relaunch when `cache_state == "partial"` (the appliance copes). **One probe of "is Whisper on disk"** (and, since 12 Nov 2026, one *running* at a time: a request that arrives during a probe makes it ask again with the preferences as they are by then, a probe that began before a download cannot overwrite its outcome, `downloadEpoch`; a probe overtaken by a newer ask is not applied or announced; one still running after 60 s is killed, SIGTERM then SIGKILL at +5 s): Swift asks Python (the job's answer, or `doctor`), never computes the Hugging Face cache path itself; and reconcile the two Python probes that already disagree (`doctor` uses `scan_cache_dir`, which reads a config-only partial as cached; the preflight's `cache_state` checks the heavy blob). Starts at launch once the AI disclosure is acknowledged, with at least 10 GB free (owner, 18 and 22 Oct 2026; lowered from 20 GB on 30 Oct 2026 after the download measured 1,539 MB at its peak; built 22 Oct, `WhisperDownloadModel.checkAtLaunch`), and also at the first Apple run |
| E | **Record the engine** | transcription-quality record (`recognition.backend`, locale `assumed`, asset version), segment `source` | The Diagnostics row types `backend` but renders nothing (`TranscriptionDiagnostics.tsx:32`); render it there |
| F | **No re-transcription** | stage-5 fingerprints unchanged | The engine must not join the fingerprint, or a re-analyse silently re-transcribes and orphans stars, tags and edits (README § 7). Known paths that will re-transcribe anyway: `--clean`, a copy without `-p`, a folder moved before its first post-upgrade run. Warn on those when the engine would change |
| G | **Settings ▸ Transcription** | `TranscriptionSettingsView` | **Superseded in part, see the §4 amendment and §8 (12 Nov 2026).** As planned 18 Oct: redesigned (§4): one behaviour choice and a Whisper status row; MLX vs faster-whisper moves behind the Diagnostics preference; the interim model picker leaves the pane (update `tests/test_interim_model_pickers.py`; `BRISTLENOSE_WHISPER_MODEL` stays as an env override). *Whisper when ready* and *Whisper only* both write `whisperBackend = auto`; *Whisper only* also withholds the helper path from `childEnvironment` (or sets `BRISTLENOSE_APPLE_SPEECH=0`), which is all the engine decision needs. The status row changes height between its states, so the pane calls `SettingsWindow.refitToContent()` on a height signature of the state |
| H | **Progress wording** | Swift | Foundation's `Progress` (`kind = .file`, `fileOperationKind = .downloading`, throughput and time-remaining keys) composes "600 MB of 1.6 GB (10 MB/s) — About 2 minutes remaining" in every locale; probe the exact string before relying on it. Throughput over an 8–10 s window, *Calculating…* until it fills, minutes with hysteresis |
| I | **Honest ETAs** | `timing.py` | Key the `transcribe` timing sample by engine (`build_hardware_key` doesn't know it), or Apple's 3× pace poisons Whisper's estimate. A Mac with no history shows no ETA (`initial_estimate` returns `None`), and the storyboard follows |
| J | **Behind a kill switch** | `Config.experimental_apple_speech` (Python), mirrored in `BristlenoseFlags` | Planned 18 Oct as parked, default off, removed once the gate is measured on more files. **Default on since 22 Oct 2026** (owner: unparked without the wider gate measurement) and kept as a kill switch: `defaults write app.bristlenose BristlenoseAppleSpeech -bool NO`, `BRISTLENOSE_EXPERIMENTAL_APPLE_SPEECH=0`. Tests for both shapes |
| K | **Strings** | `desktop.json`, 21 locales | §4 |

**Tests.** Python: the engine-decision matrix (OS, helper present or missing or
unavailable, Whisper cached / partial / missing, pinned language, UI language, platform
transcript, flag); the gate at zero words, on a sub-two-minute file and on a code-switched
file; the helper's JSON contract as a fixture both sides read; re-segmentation; `source` and
`assumed` locale; fingerprint unchanged when the engine changes; the run does not block on
the Apple path (mutation-proved); the deferred-session lifecycle. Swift: `WhisperDownloadModel`
progress, window and hysteresis as pure helpers; single-flight; restart on relaunch. Gates:
the helper's own script (build, sign, inherit, floor, Info.plist), required by the pkg, dmg
and release-binary gates and asserted by `TestTheSpeechHelperShipsAndIsGated` in
`tests/test_entitlements_split.py` (not the entitlement and bundle-integrity checks, which
never see `Contents/Helpers`); an app-store-police pass (no privacy manifest of its own,
§8). **Consent:** no change; audio never leaves the Mac (no network entitlement, the model
fetch is inbound, by a system daemon), so the AI disclosure's line that recordings stay on
the device (`aiConsent.localSummary`) stays true. Whether to say so in About is the
owner's call.

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
   no glyph, no ring, no door), with its one sentence in the row's tooltip. Swift learns the
   gate fired from a new field on `RunProgressEvent` (Python, `PipelineSummary.swift` /
   `EventLogReader`, and the fixture). [4]
5. **Settings ▸ Transcription** becomes one behaviour choice and a status row. [5]

*The wireframe, the three-item list and the below-macOS-26 sentence that follow are the 18 Oct
plan, kept as the record. Superseded 12 Nov 2026: see the amendment below and
`docs/mockups/transcription-settings-states.html`.*

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

**Amended 12 Nov 2026** (the wireframe above is the original; `docs/mockups/transcription-settings-states.html`
is the current picture). The row is *Transcription engine*. The pop-up has two items,
**Whisper** (the old *Whisper when ready*) and **Apple's speech model**: *Whisper only* is
gone, because it meant no transcription at all when Whisper failed and Apple's model was a
viable stand-in (a stored `whisperOnly` reads as the default). The Whisper status shares the
pop-up's row, is silent when Whisper is on disk, and otherwise speaks without repeating the
word *Whisper* (it keeps it under Apple's choice, where "Not on this Mac" alone would read
as Apple's model). Backend is a read-only line, *Apple silicon detected / MLX*, behind
Diagnostics; the Mac sidecar carries MLX only, so `overlayPreferences` exports only `mlx`
and the macOS 15-25 picker offers Auto and MLX. Model stays behind Diagnostics, indented,
and does not dim for the engine choice (Model, and the macOS 15-25 Backend picker, are
locked while a download runs, so the progress cannot describe a model just changed). While
the status is being probed it reads *Checking for Whisper…*, and the pane re-fits when the
status row appears or goes and when the engine choice changes. Row G's "write
`whisperBackend = auto`" was never built: the stored preference stands, and only `mlx` goes
out. The dimmed one-item pop-up below macOS 26 was never built either: those Macs, and any
Mac with the flag off or the helper missing, get the macOS 15-25 pane (Backend Auto/MLX,
Model, and the Whisper row shown even when on disk).

| Key | English | Status |
|---|---|---|
| `desktop.chrome.pipeline.stage.*`, `sessionsCount`, `analysing` | as shipped | reused |
| `desktop.modelDownload.title`, `.failedTitle` | *Downloading Whisper* · *Whisper didn't download* (planned as *Downloading speech model* with a `.pill` key; renamed, §8) | shipped (moving Ollama's `pillDownloading`/`downloadingTitle` here is still not built) |
| `desktop.modelDownload.why` | *For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.* | shipped as a first draft in 21 locales; owner's wording call open |
| `desktop.modelDownload.stop` | *Stop* (was *Stop Download*; the `.stopNote` line *Starts again from the beginning next time.* was removed on 17 Nov 2026 by the owner, see `docs/design-whisper-delivery.md` §11) | shipped; renamed |
| `desktop.chrome.pipeline.waitingForWhisper`, `…Hint` | *Waiting for Whisper* · *Apple's speech model wasn't sure of what it heard, so Whisper will transcribe it once it's on this Mac.* (planned as `waitingForDownload` with a language in the hint; §8) | shipped, first draft; owner's wording call open |
| `desktop.transcriptionSettings.*` | `engineLabel` *Transcription engine*, `engineWhenReady` *Whisper*, `engineApple`, `engineHint`, `whisperLabel`/`OnDisk`/`Missing`/`Failed`/`Checking`, `backendDetectedAppleSilicon`, `downloadNow`; `backendLabel`/`backendAuto`/`backendHint` stay for the macOS 15-25 pane; `engineWhisperOnly` removed 12 Nov | shipped; native review owed for cs, fi, pl, tr, uk |
| progress line | Foundation's `Progress.localizedAdditionalDescription` | system, no key |

## 5. What stays as it is

The CLI (no helper), Linux and Windows, macOS 15's behaviour (its Settings pane changed only
on 12 Nov, in dropping faster-whisper), every run with a platform transcript, every run
once Whisper is on disk under the default engine (not under *Apple's speech model*), and
every pinned-language run.

## 6. Open questions for the owner

- **Show the engine per session?** README § 9 said to; this plan keeps it to the
  Diagnostics row because 98% of sessions are one-to-one. A day-one focus group would lose
  its quieter voices with no tell.
- **Start the download at the first welcome screen, or at the first Apple run?**
  *Answered 22 Oct 2026 (owner): at launch, once the AI disclosure is acknowledged (§3 D).*
- **Wording**: the *why* sentence, the deferral hint, and *Waiting for download* vs
  *Waiting for Whisper*. *Partly answered: Waiting for Whisper (18 Oct, §8); the pop-up
  labels, 12 Nov 2026 (owner): Whisper / Apple's speech model. The why sentence and the
  deferral hint shipped as first drafts and are still the owner's call.*
- **Reproducibility:** Apple updates its model silently. Recording the asset version is
  enough for now, or should the Diagnostics row flag a version change?
- **macOS 26's locale list** (the trial read 27 only); the order of the pills in the
  status zone (already open).
- **Today's shipped time wording** (*~2 min left*, *<1 min left*) uses a tilde and a
  less-than sign where Apple writes words (*About 2 min left*, *Under a minute*). Separate
  from this slice; worth its own small change across 21 locales.

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
Diagnostics row's missing `backend` render; then one cache probe instead of a third, the
settings pane's refit and the interim-picker test, the *Whisper only* wire, no ring on a
deferred row, and the shipped tilde wording as its own question. Also found: `desktop/CLAUDE.md` put the Whisper
model in Application Support; it lands in the container's Hugging Face cache (corrected).

**Reviews (12 Nov 2026), the Settings pane.** Two multi-agent passes on the pane and its
mockup (correctness, silent failures, Mac taste, test placement, i18n, fidelity), then a
compose-check and a parsimony pass. Taken: the *Whisper only* item removed; the status in
the pop-up's row, silent when on disk; the MLX-only backend export; the read-only
*Apple silicon detected* line; probe coalescing; the pickers locked during a download;
the stock labelled Picker. A third pass on 13 Nov, over the committed code and the locale
seeds, found no high-severity issue (taken: an overtaken probe is not applied, a hung one is
killed, the sidebar hint's apostrophe, three locale cells). Open: whether the refit fires
while another Settings pane is in front, a failed status probe shown as a failed download,
Ukrainian's apostrophe (U+02BC, an owner ruling), and the rest of the macOS 26 walk (the
failed and checking states, light mode, long locales). (The findings themselves are in the
maintainer's private notes.)

## 8. As built (18 Oct 2026; updated 22 Oct, 2 Nov, 12 Nov)

Built the same day as the plan, on branch `apple-first-transcription`, and parked:
nothing ran unless `BristlenoseAppleSpeech` was set on the Mac **and** the helper was in
the bundle (`BristlenoseFlags.appleSpeechAvailable`), which while parked meant a Debug
build, and Python's `experimental_apple_speech` was off by default too. **Unparked 22 Oct
2026:** both are default-on kill switches and the helper ships in every build. The CLI
never has the helper, so it never takes the path.

**Where it is.** Python: `bristlenose/apple_speech.py` (locale table, engine decision,
re-segmentation, gate, helper runner); stage 5's `decide_engine`, `_init_apple_backend` and
`_with_whisper_fallback`; the pipeline's engine pin and preflight skip; `doctor --fetch
--progress-lines` and `doctor --whisper-status`. Swift: `desktop/speech-helper/` (the
helper, its build script) and `desktop/scripts/check-speech-helper.sh`;
`WhisperDownloadModel.swift`, `WhisperDownloadPill.swift`, the Transcription pane, the
`.waitingForWhisper` row, `BristlenoseShared.appleSpeechEnvironment`. The JSON contract
between the two is `tests/fixtures/apple-speech/`. Tests: `tests/test_apple_speech.py`,
`tests/test_lifecycle_deferred_transcription.py`, `BristlenoseTests/WhisperDownloadTests.swift`.

**Measured on the real helper** (unsandboxed copy, synthetic speech, 18 Oct 2026): English
under en-GB kept, mean confidence 0.94; German under en-GB deferred at **0.46**, just under
the 0.5 bar, while words per minute of signal (185) did not trip. The trial's real
wrong-locale recordings scored 0.10–0.30, so clean audio narrows the margin a lot. The code
review also ran the gate over the trial's 42 right-locale outputs: it defers **3**
(es-1 at 0.476, it-3, pt-pt-2). es-1 is arguably right to defer (Apple 841 words against
Whisper's 2,034). So the gate is as much a quality gate as a language gate, and the copy
no longer names a language or a cause (below).

**Where it departs from §1–§4, and why.**

- **A deferred session goes to Whisper in the same run when Whisper is on disk** (it landed
  mid-run, or the mode is *Apple's speech model*). Otherwise it waits. §1's "engine chosen
  once per run" holds for every session Apple keeps. Without this, *Apple's speech model*
  mode deferred the same session for ever. Any helper failure (crash, timeout, offline
  locale fetch) takes the same route instead of being recorded as a Whisper failure, and
  after an engine-level exit (3, 4, 5) later sessions skip the helper.
- **Zero words over any sound defers**, however short the file: kept, it was cached as
  *no speech* and never reached Whisper.
- **Apple only when the UI language is the researcher's**: picked in Settings, or among the
  Mac's preferred languages (`BRISTLENOSE_SPEECH_UI_MATCHED`). A Greek or Hindi Mac, which
  the app shows in English, keeps Whisper's detection, as `cca68462` intended.
- **Swift learns about a deferral from the run's summary**, not a new `RunProgressEvent`
  field (§4.4): the `run_completed` summary already carries it, and that is what the row
  and the re-run read.
- **The row says *Waiting for Whisper*, not *Waiting for download***: the download may have
  failed or been stopped, and the first wording would then be false. Its tooltip (both
  sidebars) says *Apple's speech model wasn't sure of what it heard, so Whisper will
  transcribe it once it's on this Mac.* No language and no cause, because the gate knows
  neither. The tooltip builder's own rule says "do not grow this"; this is the row's own
  line said whole, as the running ladder is, not a further condition. Reviewers suggested a
  per-session note in the report instead (open, below).
- **The pill says *Downloading Whisper*** (one name for one thing; Apple's model is also a
  speech model). It stays up after a failure with Retry, and goes after a deliberate Stop. **From 2 Nov 2026 the failed popover and the Settings row name the cause when it is one of three a researcher can act on** (disk full, the connection dropped and did not come back, a security certificate not trusted: `WhisperFailureCause`, read from the job's last stderr lines) in place of "The download didn't finish."; an unrecognised cause keeps that sentence and **no raw Python error is ever shown** (decision, `7675848e0`). The job also waits out a dropped network and restarts by itself (an outage over about 15 s used to end the download and Retry began at zero); how that was measured, on which OSes, and the traps: `experiments/whisper-download-battery/README.md`.
- **A deliberate Stop Download is remembered** across launches: the app does not restart
  1.6 GB on its own until Download Now. A download the app quits on stops with it, and the
  sidecar's parent-death watcher is the backstop.
- **The re-run is level, not edge**: any project that reads *waiting* while Whisper is on
  disk runs again, once per launch, so the usual case (Whisper lands while the run is still
  in its LLM stages) is caught when the run ends, and a launch catches what the last
  session missed.
- **The helper shipped in Debug builds only** while parked (the archive path refused the
  override, and `check-pkg-shippable.sh` / `check-dmg-shippable.sh` failed if a copy was
  ever in a release bundle). **Since 22 Oct 2026 it ships in every build** and both gates
  now *require* it and run `check-speech-helper.sh` on each copy. It needs no `PrivacyInfo.xcprivacy` (§3 A said one): a bare Mach-O
  cannot carry one, the app's manifest covers first-party code, and the helper calls no
  required-reason API. No `NSSpeechRecognitionUsageDescription` either: the trial measured
  no prompt, and Apple scopes that permission to server recognition.
- **Settings** (amended 12 Nov 2026, see §4): with the flag on and macOS 26 or later,
  *Transcribe with* (now *Transcription engine*) and the Whisper row; the engine and model pickers move behind the Diagnostics preference (still
  reachable, because the model a run uses is still that preference). Below 26, or with the
  flag off, the pane is as it shipped (less faster-whisper, since 12 Nov), so
  `tests/test_interim_model_pickers.py` stands.
- **12 Nov 2026, the Settings pane.** The row is *Transcription engine* and its first item
  *Whisper*; *Whisper only* is removed (owner: it meant no transcription at all when Whisper
  failed and Apple's model was a viable stand-in), and a stored `whisperOnly` reads as the
  default. The status shares the pop-up's row (a grouped Form's keyline cannot be hidden
  with `.listRowSeparator(.hidden)`; probed on macOS 27) and is silent when Whisper is on
  disk. Backend is the read-only *Apple silicon detected / MLX*; the model row stays
  *Model* (owner). `overlayPreferences` exports only `mlx`, so a stored `faster-whisper`
  (which the Mac sidecar cannot run) can no longer make every run fail. A stored raw value
  this build does not know selects the default instead of a blank pop-up. Status probes
  run one at a time. Committed 13 Nov 2026; seen by the owner in dark mode on macOS 26 ("qa ok").
- **§3 E was already there**: the Diagnostics panel always rendered the engine. What it
  lacked was Apple's fields; it now shows *Apple speech model*, the locale as *assumed* and
  the gate's verdict, and drops Whisper's rows.

**Fixed on the way, flag or not.** A session whose transcription **failed** was marked
complete in the manifest, so every later run served its empty result from the cache and
the recording never came back. Failed sessions are now recorded FAILED and retried, and a
retry is not counted as a new session (lifecycle register rows 51–52). `doctor` now asks
the preflight's own probe, so it no longer calls a stopped download cached.

**Reviews** (18 Oct 2026, four, on the built code: correctness, silent failures, App
Store, Mac taste). Everything above under *departs* came from them, plus: the helper is
killed on any abnormal exit and a timeout is named; `@download-done` is printed only when
the run will find the model; the status probe has a timeout and logs its failures; the
download's stderr tail is logged; an unknown total shows the bytes; pipes are split on
newline bytes; the moderator checks now include Apple transcripts; the probe runs only
when the cheap cache check says it is needed.

**Still owed, or the owner's call.**

- **Owner:** ~~the pop-up labels (a reviewer proposed *Automatic* / *Whisper Only* /
  *Apple's Model First*)~~ *answered 12 Nov 2026: Whisper / Apple's speech model*; whether the row shows a count (*2 interviews waiting for
  Whisper*, needs plural keys) and a per-session note in the report; whether re-running a
  waiting project unasked is the appliance coping or a cost to approve (each re-run
  re-transcribes only the deferred sessions, then re-runs the LLM stages); the wording of
  the *why* sentence and the deferral hint, which all 21 locales carry as first drafts for
  native review (the 12 Nov Settings strings are the owner's; native review is owed for cs,
  fi, pl, tr and uk).
- **Measure** the gate on more files, real ones, before the flag comes off; the margin above
  is thin.
- **Run the helper in its shipping position** once, a signed release or TestFlight build with
  the sidecar launching it, to confirm no prompt and no sandbox denial (it now ships
  everywhere). Only a standalone sandboxed launcher has been measured. Also owed: a manual
  walk of the 12 Nov pane on macOS 26 with Diagnostics on.
- ~~**Two fetchers are still possible** in one case: a run on the Whisper path (*Whisper
  only*, or a language Apple lacks) while the app's job is downloading.~~ **Closed:** a run
  waits on the app's download (`whisperFetchEnvironment(pid:)` in Swift, which sets
  `_BRISTLENOSE_WHISPER_FETCH_PID`; `_wait_for_host_fetch` in `preflight/whisper.py`). The
  case is now a language Apple lacks, a pinned language, macOS 15-25 or the kill switch off.
- **At graduation:** ~~the helper's checks belong in `check-pkg-shippable.sh`,
  `check-dmg-shippable.sh` and `check-release-binary.sh`~~ *done 22 Oct 2026 (the commit
  "mac app: a first analysis transcribes with apple's model while whisper downloads")*;
  still owed: replace the stale "four executables" counts with one list, and write the
  Notes for Review paragraph. The flag is kept as a kill switch, not removed (owner, 22 Oct).
- **Not built:** §3 F's warning when a `--clean`, an un-`-p` copy or a moved folder would
  re-transcribe an Apple session under Whisper; a Remove action for Whisper on disk; moving
  the Ollama pill strings into the shared `modelDownload` namespace.
