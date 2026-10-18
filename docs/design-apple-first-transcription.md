---
status: proposal
date: 18 Oct 2026
---

# Apple first, Whisper next: the first recordings on a new Mac

**Proposal, 18 Oct 2026. Nothing here is built.** Evidence:
`experiments/apple-speech/README.md` (the trial, 18 Oct 2026). Storyboard:
`docs/mockups/apple-first-first-run.html`.

## 1. The slice

When **all** of these hold, transcribe with Apple's on-device `SpeechTranscriber`
instead of waiting for Whisper, and say nothing about it:

1. the Mac app (the bundled sidecar), not the CLI;
2. macOS 26 or later (checked at run time; the app's floor stays 15.0);
3. Whisper large-v3-turbo is **not yet on disk**;
4. the app's UI language is one of Apple's nine: en, es, fr, de, it, pt, ko, ja, zh;
5. the session has no platform transcript (those already need no model).

Meanwhile Whisper downloads in the background, with a progress display that does not
lie (size, amount arrived, speed, time left). Every recording after it lands is
transcribed by Whisper. Sessions Apple transcribed **stay Apple's**.

Why this and nothing wider: the trial found Apple level with Whisper on English and
one-to-one interviews in those nine languages (98–100% of Whisper's words, 4–12%
apart, fewer inserted words, no loops, 3.2× faster), and a first run that spends
3–7 minutes on a 1.6 GB download before any report exists (README § 4,
"Time to first report"). It found Apple weaker on group talk, and its pre-macOS-26
model unusable (§ 5), so neither is in the slice.

## 2. The language guess, and how it fails

Apple needs a locale up front; Whisper detects it. v1 assumes **the interview is in
the UI language** (owner, 18 Oct 2026: right most of the time, fine for v1 if a wrong
guess is explained). Measured on five recordings (README § 4):

- English audio under the Spanish or German model came back **as English**, at mean
  word confidence 0.70–0.86. A non-English UI with English interviews degrades
  gracefully.
- German, Spanish and French audio under the English model came back as a few low
  confidence words: mean **0.10–0.38** over the first two minutes, against 0.92–0.93
  in the right language.

**Gate:** if Apple's mean word confidence over the first two minutes is below **0.5**,
discard its transcript and fall back to today's path for that session: wait for
Whisper, which detects the language. The row says *Waiting for Whisper*; the row's
popover says why in one sentence. The threshold rests on five files; check it on
more before trusting the number.

## 3. Engineering

| # | Piece | Where | Notes |
|---|---|---|---|
| A | **Speech helper** `bristlenose-speech`: WAV + locale in, JSON out (segments, words with time ranges and confidences, asset version) | new `desktop/speech-helper/`, built and signed like `desktop/mcp-helper/` | Most of it is `experiments/apple-speech/transcribe.swift`. Built at 15.0 with `if #available(macOS 26, *)`; reports *unavailable* below 26. Sandboxed with the sidecar's inherit entitlements, no network entitlement (measured: the model fetch runs in a system daemon). Releases its locale reservation after each file (limit of 5, counted per region) |
| B | **Python backend** `_init_apple_backend` in `s05_transcribe.py` | stage 5 | Chosen by `_resolve_backend` when the helper path is set (`BRISTLENOSE_SPEECH_HELPER`, via `childEnvironment`), Whisper is not cached (`preflight.whisper.cache_state`), and the UI language maps to a supported locale. Returns `TranscriptSegment`s with words; `source = "apple-speech"`. Keeps the signal gate; skips the style prompt, echo filter and inaudible marker (Whisper-specific). Applies the confidence gate (§ 2) |
| C | **Skip the blocking preflight** on that path | `pipeline.py` (the `_needs_whisper` block) | Today `preflight_whisper` downloads before stage 5 and the run waits; with B eligible, it must not run for those sessions |
| D | **Background Whisper fetch** as an app-global job | Swift host: `WhisperDownloadModel` + pill, sibling of `OllamaDownloadModel` / `OllamaDownloadPill`; Python: a hidden `bristlenose fetch-model` passthrough emitting progress lines | Starts when B is taken, or at the first welcome screen if the owner's plan for an earlier fetch lands first. Progress = partial blob size against `_DOWNLOAD_MB`, speed and time left measured. Must survive the run ending. Note hf_xet restarts from zero if interrupted |
| E | **Record the engine** | transcription-quality record (`recognition.backend`, locale, asset version), segment `source` | Diagnostics row shows it behind the diagnostics preference; nothing for everyone else |
| F | **No re-transcription** | stage-5 fingerprint unchanged | The engine must not join the fingerprint, or a later re-analyse silently re-transcribes and orphans stars, tags and edits (README § 7) |
| G | **Settings ▸ Transcription** | `TranscriptionSettingsView` | No new picker option. *Auto*'s hint is reworded to say what Auto now does; choosing MLX or faster-whisper means Whisper only, as today |
| H | **Strings** | `desktop.json`, 21 locales | Five new keys (§ 4); everything else reuses shipped keys |

**Tests.** Python: backend-resolution matrix (OS, helper present, Whisper cached, UI
language, platform transcript); the confidence gate on recorded helper JSON; the
helper's JSON contract as a fixture both sides read; `source` tagging; fingerprint
unchanged when the engine changes. Swift: `WhisperDownloadModel` progress, speed and
ETA arithmetic as a pure helper; helper argument handling. Gate script for the helper
(build, sign, entitlements, floor), like `check-mcp-helper.sh`; an app-store-police
pass for the new executable and its privacy manifest.

**Acceptance walks** (by hand, once): English UI, fresh account, English recording;
English UI, Spanish recording (gate fires, row explains); quit during the background
fetch and reopen; a sixth locale (reservation limit); macOS 15 guest (no change from
today); offline with English (works with no download, since English came with the OS
on the test Mac).

**Rough size.** Helper 1–2 days; Python backend and gate 1–2; background fetch, pill
and progress 2–3; strings, tests, gates and walks 2. About two weeks, with unmeasured
risk in the helper's signing and sandbox inheritance.

## 4. The smallest UX change

Four visible differences, all in existing places (storyboard frames in brackets):

1. **The row moves straight to real stages** (*Transcribing · 1 of 1*, then *Finding
   quotes*) instead of *Analysing · ~2 min left* while an unmentioned download runs. [1, 2]
2. **A download pill in the toolbar's status zone**, the sibling of the Ollama
   download pill, with a popover that shows size, amount, speed and time left, and
   Cancel. It disappears when Whisper is ready. [2, 3]
3. **The report arrives about three minutes sooner** on typical broadband. [3]
4. **Settings ▸ Transcription:** *Auto*'s hint says what Auto now does. [5]

And one new failure line, only when the language guess is wrong: *Waiting for
Whisper*, with one sentence of explanation in the row's popover. [4]

| Key | English | Status |
|---|---|---|
| `desktop.chrome.pipeline.stage.transcribe`, `…stage.quotes`, `…sessionsCount`, `…etaMinutes`, `…etaUnderMinute`, `…analysing` | as shipped | reused |
| `desktop.ollamaSetup.pillDownloading`, `…downloadingTitle`, `…bytesProgress`, `common.buttons.cancel` | *Downloading %@*, *%@ of %@*, *Cancel* | reused (same meaning; consider moving to a neutral `modelDownload` namespace) |
| `desktop.modelDownload.rate` | *{{rate}}/s* | **new** |
| `desktop.modelDownload.why` | *For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.* | **new, owner to word** |
| `desktop.chrome.pipeline.waitingForWhisper` | *Waiting for Whisper* | **new** |
| `desktop.pipeline.diagnostic.reason.languageGuess` | *This recording doesn't sound like {{language}}. It will be transcribed once Whisper has downloaded.* | **new, owner to word** |
| `desktop.transcriptionSettings.backendHint` | *Auto uses Apple's speech model on this Mac until Whisper has downloaded, then Whisper, which copes better with poor audio, people talking over each other, larger groups and more languages.* | **reworded** (21-locale change) |

## 5. Open questions

- **macOS 26's locale list.** The trial read macOS 27 only; check on a 26 guest.
- **Who holds the reservation**: the helper inside the app, or the app? Untested.
- **Wording** of the two new sentences (§ 4) is the owner's.
- **Start the fetch at welcome, or at the first Apple run?** This slice works with either.
