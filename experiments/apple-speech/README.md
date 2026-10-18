# Apple's on-device speech framework against Bristlenose's Whisper

_Experiment, 18 Oct 2026. No product code or shipping behaviour was changed._

**Question.** Can Apple's `SpeechAnalyzer` / `SpeechTranscriber` (new in macOS 26) match
Bristlenose's transcription (mlx-whisper, large-v3-turbo, the per-language style prompts and
the stage-5 nets), and can it make a first run work with no 1.5 GB model download? Three
outcomes count: **replace** Whisper; **work out of the box, then upgrade quietly** to Whisper
for later sessions; or **fallback** where Whisper is weak or slow.

**Verdict (18 Oct 2026).** **Work out of the box, then upgrade: yes, for nine languages.** On
English and one-to-one interviews in en, es, fr, de, it, pt, ko, ja and zh, Apple matches
Whisper (98–100% of its words, 4–12% apart, level true WER, fewer inserted words, no loops),
runs 3.2× faster, and needs no download for English on this Mac and a 140 MB, 8–16 s fetch
for the rest, with no prompt and inside the App Sandbox. **Replace: no**: it covers 9 of our
20 languages, drops the quieter or overlapping voice in group talk, marks nothing inaudible,
detects no language, and updates itself. **Fallback: no**: the only Apple route for the other
eleven languages, `DictationTranscriber`, loses most of the speech (94–97% WER where
`SpeechTranscriber` scored 35–44%); the one open exception is memory on 8 GB Macs (~180 MB
against Whisper's 9.2 GB peak footprint, not yet measured on such a Mac). § 9 has the reasoning
and the conditions.

---

## 1. What others have measured (read first, 18 Oct 2026)

There is **no independent, peer-reviewed evaluation** of `SpeechTranscriber`, and Apple
publishes no accuracy figures. Every number below comes from a vendor (often one selling a
competing engine), one developer, or an anecdote. **Nobody has published Apple against
large-v3-turbo on interview or meeting audio** — which is what our own trial had to measure.

### Apple's own material

- WWDC25 session 277, *Bring advanced speech-to-text to your app with SpeechAnalyzer* (June 2025):
  the model powers Notes, Voice Memos, Journal and call summaries; Apple calls it good for
  "long-form and distant audio, such as lectures, meetings, and conversations". It lives in
  system storage, outside the app's memory, is shared between apps, and **updates itself**
  (so a run cannot pin a model version). `DictationTranscriber` is the fallback: the older
  dictation model, more languages, and the only one with documented custom-vocabulary biasing.
  <https://developer.apple.com/videos/play/wwdc2025/277/>
- `AssetInventory` docs (current): models are "downloaded from Apple's servers and managed by
  the system … shared with other apps"; an install "may complete immediately if the assets were
  preinstalled, downloaded by another app, or used by a previous configuration"; an app holds a
  limited number of locale reservations. <https://developer.apple.com/documentation/speech/assetinventory>
- macOS 27 (WWDC26, June 2026) adds input plumbing only: `AssetInputSequenceProvider` (read an
  audio track straight from a video file), `CaptureInputSequenceProvider`, `AnalyzerInputConverter`,
  and `Options.ignoresResourceLimits`. No diarisation, no language detection, no vocabulary for
  `SpeechTranscriber`. <https://developer.apple.com/documentation/updates/speech> (confirmed against
  the macOS 27 SDK's `Speech.swiftinterface`, which marks exactly these as `anyAppleOS 27`).

### Benchmarks (all vendor or anecdotal)

| Source, date | Who | Data | Result |
|---|---|---|---|
| Argmax blog, 20 Jun 2025 | competitor (WhisperKit), macOS 26 beta 1 | earnings-22, 10% | WER Apple 14.0, whisper small.en 12.8, base.en 15.2; Apple 70× real time |
| Argmax OpenBench, Apple run 30 Dec 2025 | competitor | earnings-22 keywords | WER Apple **17.0**, large-v3-turbo **15.4**, Parakeet v2 14.7; keyword recall 0.39 vs 0.53 |
| MacStories, ~16 Jun 2025 | anecdote, one 34-min podcast | — | Apple 0:45 vs MacWhisper large-v3-turbo 1:41; "no noticeable difference" in quality, no WER |
| Lyonesse/Inscribe, 13 and 15 Jul 2026 | app vendor shipping both, M2 Pro | LibriSpeech clean/other | WER Apple 2.1/4.6, Whisper small 3.7/8.0, Parakeet v2 2.0/3.4 (no large Whisper) |
| Whisper Notes, 1 Sep 2026 | Whisper-app vendor, **macOS 27.0**, M5 | FLEURS, ~150 sentences a language | Apple vs turbo: en 8.8 vs 5.5, de 6.3 vs 4.1, fr 7.6 vs 6.0, es 5.4 vs 3.6, it 4.4 vs 2.6, pt-BR 9.4 vs 5.4, ja CER 6.4 vs 5.3, ko CER 4.3 vs 4.3, zh CER 8.0 vs 8.0; Apple 31× real time, turbo 3× |
| Desert Ant, undated | vendor of a timing fix | LibriSpeech | Apple word starts: mean error ~106–124 ms; 37% within 50 ms |

Settled well enough to rely on: on device; model shared and system-managed; **much faster than
turbo** (vendors report about 10×; 3.2× on this Mac, § 4); punctuated, cased output with optional word time ranges and confidences; no
diarisation; no language detection (one locale per transcriber); no effective custom vocabulary
on `SpeechTranscriber`; Apple silicon only. Also settled: on **read speech** it trails turbo in
most languages (one vendor, FLEURS) and on earnings calls (one competitor).

Thin or contradicted, so measured here: conversational and interview accuracy; behaviour on
silence, music and hard audio; long files; timestamp drift; which locales a macOS 27 Mac
actually offers (the only printed list is a July 2025 beta and is wrong for 27.0, § 2); asset
sizes; reservation limits; App Sandbox and permission prompts (no source at all).

## 2. What this Mac says (measured 18 Oct 2026)

Mac: M2 Max, 32 GB, macOS 27.0 (26A428), Xcode SDK 27, Swift 6.4. Probes in this folder
(`probe_locales.swift`, `transcribe.swift`, `sandbox_probe.swift`), built with `swiftc`, no project.

**Locales.** `SpeechTranscriber.supportedLocales` lists 45 locales on 27.0. Of our 20 trial
languages it covers **en, es, fr, de, it, pt (pt-BR and pt-PT), ko, ja, zh** (and yue). It does
**not** cover **ca, nl, sv, da, nb, pl, cs, ru, uk, fi, tr** — eleven of the seventeen languages in
the style-prompt corpus. The July 2025 list printed in blogs claimed da, fi, nl, nb, ru, sv and tr,
and "pt-BR only"; on 27.0 both claims are wrong. `DictationTranscriber` (the older dictation
model) lists 54 locales and covers all eleven missing ones.

**Assets.** One model per language, shared by all its regions, managed by the system under
`/System/Library/AssetsV2/com_apple_MobileAsset_UAF_Speech_AutomaticSpeechRecognition/`. Sizes
from the system's own catalogue:

| Model | Download | Unpacked |
|---|---|---|
| en | 138 MB | 206 MB |
| es, fr, de, it, pt (each) | 143 MB | 183 MB |
| zh (cmn) | 151 MB | 197 MB |
| language identification (shared) | 14 MB | 17 MB |
| _Whisper large-v3-turbo (mlx), for comparison_ | _~1.5 GB_ | _1.5 GB_ |

Fetch times on this connection (home broadband, 18 Oct 2026): 8–16 s per language
(es 16.4 s, de 9.3, it 9.2, ja 9.3, ko 8.4, zh 9.6; fr 9.9 s from inside the sandbox).
Asking for a model already on disk takes 0.07 s.

**English came with the OS.** The English model's folder finished at 22:11 on 14 Sep 2026; macOS
27.0's install is logged at 22:10, and the catalogue marks the asset as staged with the software
update. Spanish, the second language in this Mac's list and set up for dictation, was **not**
there for `SpeechTranscriber`. One Mac only: we cannot say whether every Mac gets its primary
language's model with the OS, or what decides it.

**Reservations.** An app may hold **5 reserved locales** (`maximumReservedLocales`), and the
limit counts **locales, not models**: en-GB, en-US, de-DE and de-AT took four slots for two
models. The sixth request fails with `SFSpeechErrorDomain` 11, "Too many allocated locales, 5
maximum". `release(reservedLocale:)` only works when passed the stored `Locale` object
(`Locale("de-DE")` is not equal to the stored `de_DE`, and the call returns false). Reservations
belong to the executable: a second binary saw none of the first one's.

**Status is per app.** `AssetInventory.status` answered `supported`, not `installed`, for English
while the model sat on disk and `installedLocales` listed it; the install request then completed
in 0.07 s with nothing fetched. Read `installed` as "reserved by this app", not "on the Mac".

**Downloads run in a system daemon.** A request killed 2 s into a Portuguese fetch still
completed 10 s later (asset folder created 12:10:39, finished 12:10:49). Quitting mid-download
does not lose it.

**App Sandbox.** An ad-hoc-signed probe with `com.apple.security.app-sandbox` and **no network
entitlement** (`sandbox.entitlements`; an embedded Info.plist is required, or the process dies with
SIGTRAP at launch) ran in its own container, could not list the real home folder, fetched the French model
(9.9 s) and transcribed a 15-minute file. **No permission prompt**, and none was needed:
`SFSpeechRecognizer.authorizationStatus()` stayed `notDetermined` throughout, and nothing asks for
`NSSpeechRecognitionUsageDescription`. The work runs out of process, in
`localspeechrecognition.xpc`.

**Floor.** A probe built for `arm64-apple-macos15.0` with the API behind `if #available(macOS 26, *)`
compiles, links Speech weakly, and runs. The app's 15.0 floor can stay.

**Swift only.** `SpeechAnalyzer`, `SpeechTranscriber` and `DictationTranscriber` have no
Objective-C headers (`Speech.framework/Headers` holds only the old `SF*` classes), so the pyobjc
route the screens work uses for Vision does not reach them.

## 3. Method (18 Oct 2026)

- **Corpus**: 74 files already on disk, 29.4 h, none downloaded for this trial: the
  style-prompt corpus (17 languages, public licences, kept out of git; 56 files),
  ten English oral histories (FOSSDA), five English research-style calls (Teams, Zoom, screen recordings), and three short
  Japanese and Chinese clips. Each was converted once to 16 kHz mono WAV, the product's
  own extraction format, and both engines read the same file.
- **Apple**: `SpeechTranscriber`, word time ranges and confidences on, through
  `transcribe.swift` (one process per file); the locale given up front (it cannot detect
  one), with the speakers' region where known (pt-PT, pt-BR, de-AT). For the 11 languages it
  lacks, `DictationTranscriber` (long-dictation preset, punctuation on) — § 5.
- **Whisper**: the product's own path, `s05._init_mlx_backend` (large-v3-turbo, language
  detected, shipped style prompts, signal gate, loop removal, skipped-window net, inaudible
  marker), via `run_whisper.py`. Spot-checked word for word against the 13 Oct trial outputs
  (identical), which therefore stand in for Whisper on the Dictation-only languages.
- **Measures** (`analyse.py`), the same on both engines: word counts; disagreement (WER of
  Apple against Whisper — not an error rate, a distance); true WER, with substitutions,
  deletions and insertions, where a human reference exists (es-5, es-6: Ameresco, scored as
  `score_wer.py` does); **one-sided stretches** (≥ 8 s where one engine has ≥ 1 word a second
  and the other almost none), each **read by hand** and classified; sound without words
  (the skipped-window net's own rule, on word timings); visible loops (a phrase repeated 8+
  times, or a run-on syllable, in the text a reader gets — Whisper's raw word list keeps loops
  that stage 5 collapses in the text, so only words that survive into the text are counted);
  sentence ends and fillers; word-start agreement between engines and drift over the file;
  real-time factor. Characters, not words, for Japanese, Chinese and Korean.
- The six extreme recordings (covert conversations, a street recording, field tapes) are
  reported separately and never in a headline number.

## 4. Results: `SpeechTranscriber` against Whisper

Columns: A = Apple, W = Whisper. "A vs W" is disagreement, not error. "only-W s" is time
Whisper has speech and Apple almost none, and the reverse. "debris" is visible loops plus
segments of 15 s+ holding under 4 words. Δ start is the gap between the two engines' start
times for the same word.

**Interviews and podcasts**

| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) | debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms | RTF A / W | ref WER A / W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| es-2 | 21 | 3437 / 3489 | 7.9% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 150 / 174 | 38 / 85 | 140 / 240 | 0.013 / 0.046 |  |
| es-3 | 12 | 1868 / 1882 | 12.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 153 / 138 | 8 / 10 | 140 / 220 | 0.013 / 0.049 |  |
| fr-1 | 15 | 1637 / 1681 | 15.7% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 60 / 109 | 0 / 27 | 160 / 440 | 0.012 / 0.033 |  |
| fr-2 | 18 | 1716 / 2044 | 26.0% | 25 / 0 | 8 / 9 | 0 / 0 | 0 | 147 / 343 | 0 / 25 | 160 / 474 | 0.011 / 0.037 |  |
| de-1 | 17 | 2109 / 2166 | 8.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 149 / 147 | 0 / 21 | 160 / 260 | 0.012 / 0.037 |  |
| de-2 | 28 | 4831 / 4889 | 4.4% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 361 / 368 | 0 / 0 | 180 / 240 | 0.012 / 0.042 |  |
| de-3 | 22 | 3092 / 3179 | 7.3% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 189 / 175 | 0 / 59 | 180 / 260 | 0.011 / 0.038 |  |
| it-1 | 21 | 3212 / 3140 | 7.7% | 0 / 16 | 0 / 13 | 0 / 1 | 0 | 62 / 113 | 0 / 2 | 100 / 200 | 0.013 / 0.056 |  |
| it-2 | 20 | 2969 / 3016 | 8.6% | 0 / 0 | 10 / 17 | 0 / 0 | 0 | 115 / 150 | 0 / 32 | 100 / 180 | 0.012 / 0.044 |  |
| pt-br-1 | 19 | 2134 / 2203 | 28.8% | 27 / 30 | 115 / 131 | 0 / 2 | 0 | 78 / 180 | 30 / 40 | 180 / 380 | 0.011 / 0.074 |  |
| pt-ao-1 | 15 | 1889 / 1890 | 8.6% | 0 / 0 | 0 / 10 | 0 / 0 | 0 | 80 / 96 | 2 / 7 | 160 / 280 | 0.011 / 0.041 |  |
| ko-2 | 16 | 1389 / 1420 | 15.7% | 0 / 0 | 12 / 0 | 0 / 0 | 0 | 129 / 181 | 16 / 25 | 80 / 440 | 0.009 / 0.045 |  |

_12 files, 3.7 h: Apple 30283 words, Whisper 30999 (98%); median disagreement 8.6%; one-sided 52 s Whisper-only, 46 s Apple-only._

**Group talk (meeting, press conference, family meal, chat)**

| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) | debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms | RTF A / W | ref WER A / W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pt-pt-1 | 20 | 1551 / 2278 | 47.7% | 263 / 0 | 285 / 18 | 1 / 0 | 0 | 46 / 202 | 0 / 9 | 180 / 320 | 0.010 / 0.040 |  |
| ko-1 | 16 | 1084 / 1490 | 45.2% | 69 / 0 | 54 / 12 | 0 / 0 | 0 | 61 / 325 | 34 / 42 | 100 / 544 | 0.008 / 0.046 |  |
| ko-3 | 16 | 1073 / 1116 | 20.3% | 86 / 38 | 0 / 0 | 0 / 0 | 0 | 74 / 101 | 8 / 16 | 60 / 220 | 0.009 / 0.038 |  |
| fr-3 | 13 | 1798 / 2243 | 52.5% | 0 / 0 | 0 / 0 | 0 / 0 | 1 | 114 / 316 | 0 / 13 | 160 / 340 | 0.014 / 0.080 |  |
| fr-4 | 11 | 1192 / 1483 | 37.8% | 13 / 0 | 0 / 8 | 0 / 0 | 0 | 94 / 236 | 0 / 6 | 160 / 360 | 0.013 / 0.041 |  |

_5 files, 1.3 h: Apple 6698 words, Whisper 8610 (78%); median disagreement 45.2%; one-sided 431 s Whisper-only, 38 s Apple-only._

**English (oral histories, research calls)**

| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) | debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms | RTF A / W | ref WER A / W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| en-fossda-01 | 40 | 4749 / 4738 | 5.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 257 / 269 | 0 / 0 | 100 / 300 | 0.013 / 0.032 |  |
| en-fossda-02 | 61 | 7610 / 7552 | 5.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 564 / 435 | 0 / 0 | 80 / 280 | 0.012 / 0.034 |  |
| en-fossda-03 | 94 | 14212 / 14144 | 6.8% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 976 / 897 | 0 / 0 | 80 / 260 | 0.015 / 0.035 |  |
| en-fossda-04 | 39 | 5921 / 5941 | 5.6% | 0 / 12 | 0 / 0 | 0 / 0 | 0 | 292 / 294 | 0 / 0 | 80 / 240 | 0.015 / 0.038 |  |
| en-fossda-05 | 100 | 12527 / 12507 | 5.8% | 0 / 0 | 0 / 9 | 0 / 0 | 0 | 881 / 806 | 0 / 0 | 80 / 280 | 0.012 / 0.032 |  |
| en-fossda-06 | 23 | 3366 / 3350 | 9.8% | 0 / 12 | 0 / 9 | 0 / 0 | 0 | 164 / 147 | 0 / 0 | 60 / 240 | 0.016 / 0.036 |  |
| en-fossda-07 | 22 | 3321 / 3291 | 5.7% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 220 / 183 | 0 / 0 | 80 / 260 | 0.016 / 0.036 |  |
| en-fossda-08 | 23 | 3770 / 3766 | 7.1% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 271 / 248 | 0 / 0 | 80 / 240 | 0.020 / 0.053 |  |
| en-fossda-09 | 55 | 8522 / 8541 | 3.4% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 601 / 564 | 0 / 0 | 80 / 280 | 0.015 / 0.035 |  |
| en-fossda-10 | 34 | 4870 / 4838 | 5.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 276 / 268 | 0 / 0 | 100 / 300 | 0.016 / 0.034 |  |
| en-call-1 | 1 | 96 / 96 | 13.4% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 20 / 23 | 0 / 0 | 100 / 314 | 0.011 / 0.031 |  |
| en-call-2 | 4 | 415 / 426 | 16.7% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 72 / 60 | 0 / 0 | 80 / 280 | 0.011 / 0.033 |  |
| en-call-3 | 3 | 321 / 322 | 18.8% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 61 / 49 | 0 / 0 | 80 / 282 | 0.015 / 0.030 |  |
| en-call-4 | 18 | 2768 / 2791 | 10.6% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 290 / 277 | 0 / 0 | 60 / 220 | 0.016 / 0.045 |  |
| en-call-5 | 7 | 206 / 210 | 12.7% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 14 / 14 | 0 / 0 | 80 / 220 | 0.008 / 0.024 |  |

_15 files, 8.8 h: Apple 72674 words, Whisper 72513 (100%); median disagreement 6.8%; one-sided 0 s Whisper-only, 24 s Apple-only._

**Japanese and Chinese**

| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) | debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms | RTF A / W | ref WER A / W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ja-1 | 4 | 542 / 528 | 6.9% | 0 / 0 | 14 / 14 | 0 / 0 | 0 | 0 / 0 | 0 / 0 | 80 / 140 | 0.015 / 0.075 |  |
| zh-1 | 4 | 323 / 311 | 8.0% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 0 / 0 | 0 / 0 | 60 / 100 | 0.019 / 0.037 |  |
| zh-2 | 2 | 174 / 146 | 43.1% | 0 / 0 | 0 / 0 | 0 / 0 | 0 | 0 / 0 | 0 / 0 | 80 / 328 | 0.018 / 0.035 |  |

_3 files, 0.2 h: Apple 1039 words, Whisper 985 (105%); median disagreement 8.0%; one-sided 0 s Whisper-only, 0 s Apple-only._

**Extreme (stress tests, not the yardstick)**

| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) | debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms | RTF A / W | ref WER A / W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| es-1 | 26 | 841 / 2034 | 85.6% | 352 / 145 | 241 / 216 | 1 / 12 | 1 | 178 / 223 | 2 / 14 | 220 / 10658 | 0.010 / 0.151 |  |
| es-4 | 16 | 368 / 437 | 69.8% | 45 / 73 | 292 / 197 | 0 / 7 | 0 | 66 / 75 | 1 / 4 | 180 / 440 | 0.010 / 0.096 |  |
| es-5 | 25 | 4547 / 4765 | 27.0% | 0 / 20 | 0 / 0 | 0 / 0 | 0 | 481 / 519 | 8 / 23 | 160 / 280 | 0.013 / 0.059 | 35.1% (ins 98) / 35.7% (ins 160) |
| es-6 | 24 | 3062 / 3583 | 33.2% | 12 / 16 | 18 / 29 | 0 / 0 | 0 | 442 / 540 | 3 / 13 | 160 / 360 | 0.012 / 0.043 | 44.4% (ins 37) / 42.0% (ins 93) |
| it-3 | 9 | 45 / 110 | 81.8% | 33 / 0 | 0 / 0 | 0 / 3 | 46 | 5 / 21 | 0 / 3 | – / – | 0.009 / 0.100 |  |
| pt-pt-2 | 17 | 5 / 40 | 100% | 0 / 0 | 0 / 0 | 0 / 5 | 146 | 2 / 9 | 0 / 0 | – / – | 0.009 / 0.041 |  |

_6 files, 1.9 h: Apple 8868 words, Whisper 10969 (81%); median disagreement 75.8%; one-sided 442 s Whisper-only, 254 s Apple-only._

### What the one-sided stretches were (read by hand, 78 stretches)

| Group | Apple dropped real speech | Whisper dropped or looped over real speech |
|---|---|---|
| Interviews and podcasts (3.7 h) | 4 stretches, 52 s: side-talk, a phone call off-mic, backchannel (fr-2, pt-br-1) | 2 stretches, 46 s: an interviewer's 30 s question lost to a one-word loop (pt-br-1), a run-on syllable over a sentence (it-1) |
| English (8.8 h) | none | 2 stretches, 24 s: a whole sentence skipped (fossda-04, fossda-06) |
| Group talk (1.3 h) | **28 stretches, 431 s**: the meeting's procedural back-and-forth (pt-pt-1, 263 s), reporters' questions at a press conference (ko-3, 86 s), cross-talk in a group chat (ko-1, 69 s), a second speaker (fr-4) | 2 stretches, 38 s (ko-3) |
| Extreme (1.9 h) | many; both engines garble | many; Whisper's loops ("Tr" dozens of times, a phrase a dozen times) sit over speech Apple partly heard |

**On ordinary recordings neither engine wrote words into silence** in any stretch read.
Whisper's failures there were loops and skips; Apple's were omissions. On the field tapes it
differs: over speech it could barely make out, Whisper writes fluent-looking sentences at low
confidence (mean 0.35–0.55 a stretch) where Apple writes fragments or nothing, and Whisper puts
more words where the audio never rises 10 dB above the noise floor (es-1: 111 against 24; it-3:
47 against 17; pt-pt-2: 28 against 3). Without references we cannot say how much of either is
right; by the quality bar (a guess must become a gap), Apple's silence is the more honest
failure, Whisper's guesses the more useful one when they are right.

### True word error rate (the only references we have, both extreme)

| File | Apple WER (sub / del / ins) | Whisper WER (sub / del / ins) |
|---|---|---|
| es-5, covert conversation, 25 min | **35.1%** (777 / 1,064 / 98) | 35.7% (897 / 912 / 160) |
| es-6, covert conversation, 24 min | 44.4% (454 / 1,532 / 37) | **42.0%** (752 / 1,068 / 93) |

Level overall, with different errors: Apple leaves more out and writes less that was not
said (insertions 98 vs 160, 37 vs 93).

### Style

- **Fillers**: Apple drops them in most languages (German, French, Italian: 0 against Whisper's
  21–59 a file); it keeps some in Spanish, Portuguese and Korean. (Not counted for Japanese
  and Chinese, which have no filler list; their sentence ends are not counted either, since
  the counter knows only Latin punctuation — the 0 / 0 in those rows is not data.)
- **Sentence ends**: Apple writes fewer and longer sentences, and on cross-talk sometimes
  none: pt-pt-1 came back largely lower case and unpunctuated (46 sentence ends against 202).
- **Script**: Chinese stays in the locale's script; Whisper switched from Traditional to
  Simplified partway through zh-2 (part of that file's 43% disagreement is script, not words).
- **No inaudible marker**: Apple returns nothing where it cannot hear, so a gap reads as
  silence. Whisper's net turned guesses into marked gaps on the street and market recordings
  (146 s on pt-pt-2, 46 s on it-3) and almost nowhere else (1 s on es-1 and fr-3).

### Timing

Word starts agree within a fifth of a second: median gap 60–180 ms, 90th percentile 180–470
ms on ordinary recordings. Apple is consistently about 140–180 ms later than Whisper in the
European languages, 40 ms later in Korean, 60 ms earlier in English. **No drift**: the gap's
slope over a file is noise (under ±0.3 s an hour) on files up to 100 minutes. Against the
Ameresco references' human-annotated turn starts, Whisper is a little closer (median error
250 vs 320 ms on es-5, 170 vs 240 ms on es-6; within 250 ms for 48–62% of turns against
40–50%). Either is good enough for the player and for clips, which pad.

### Speed (M2 Max, 32 GB)

| | Apple | Whisper |
|---|---|---|
| Real-time factor, median (all 41 files) | **0.012** (≈ 80× real time) | 0.040 (≈ 25×) |
| Range | 0.008–0.020 | 0.024–0.15 (the net re-decoding field tapes) |
| 15.9 h of audio | 12 min | 42 min |
| Model load per process | 0.04 s median (out of process, kept warm) | seconds, once per run |

A factor of 3.2, not the 10× the vendor benchmarks report: mlx turbo is fast on an M2 Max.
On a base M1 or M2 the gap is likely wider (not measured).

### A wrong language guess (measured 18 Oct 2026, later the same day)

Apple needs a locale up front. Five recordings were run under the wrong one; mean word
confidence over the first two minutes, then over the whole file, against the right locale:

| Audio | Locale given | Wrong: first 2 min / whole file | Right locale | Output |
|---|---|---|---|---|
| German interview (de-1) | en-US | 0.14 / 0.10 | 0.93 | 114 words instead of 2,128 |
| Spanish podcast (es-2) | en-US | 0.35 / 0.16 | 0.92 | 607 words instead of 3,441 |
| French interview (fr-1) | en-GB | 0.38 / 0.30 | 0.93 | 24 words instead of 1,640 |
| English oral history (fossda-01) | es-ES | 0.86 / 0.84 | 0.92 | 4,455 words, **in English** |
| English Teams call | de-DE | 0.70 / 0.68 | 0.80 | 1,979 words, **in English** |

So a non-English model handed English audio writes English (1,138 English function words
in the Spanish-model run, 10 Spanish), and the English model handed other languages gives
itself away by low confidence. A gate at mean confidence 0.5 over the first two minutes
separates all five; five files are too few to trust the exact number.

### Memory, several at once, determinism, video input (measured 18 Oct 2026, later the same day)

- **Memory.** One 28-minute German file (de-2): Apple's work runs in a per-client
  `localspeechrecognition` XPC service that peaked at **~180 MB resident** (the calling
  process stays small). Whisper through the product's path, measured with `/usr/bin/time -l`:
  **2.3 GB maximum resident, 9.2 GB peak memory footprint** (mlx's GPU buffers count against
  unified memory), 73 s wall including model load. On an 8 GB Mac that difference is likely to
  matter more than speed; not measured on one.
- **Several at once.** Four files at the same time (three German, one Italian; 88 minutes of
  audio) finished in 23 s wall, each at a real-time factor of 0.013–0.014 against 0.012 alone:
  near-linear, and no `insufficientResources` error at four.
- **Deterministic.** The three German files came back word for word identical to their
  earlier sequential runs. Within one asset version a transcript is reproducible; across an OS
  or asset update it may not be (§ 8).
- **Custom vocabulary does nothing.** fossda-01 re-run with six terms Whisper wrote more often
  than Apple (Debian, BusyBox, Unix, Sebastian, Macworld, Safari) supplied as
  `AnalysisContext.contextualStrings`: the transcript was byte-identical to the run without
  them (Debian 2 against Whisper's 6, BusyBox, Unix and Macworld still 0). This confirms the one
  anecdote in § 1: study context (product, guide and participant names) cannot be fed to
  `SpeechTranscriber`. `transcribe.swift --context FILE`.
- **Straight from video (macOS 27, `AssetInputSequenceProvider`).** Works on 48 kHz AAC
  (oral-history mp4s, macOS screen recordings): fossda-06 gave 3,361 words against 3,366 via
  WAV, in 21.4 s against 22.1 s. **Fails on 16 kHz AAC**, which is what the Teams recording
  carries: AVFoundation −11800 / −50, and the macOS 26 `AVAudioFile` route fails the same way
  (`ExtAudioFileRead` −50). The same Teams file re-encoded to 48 kHz worked (2,770 words against
  2,768). So an Apple engine should keep the product's ffmpeg extraction to WAV, not read video
  directly. Probe: `video_probe.swift`.

## 5. Results: `DictationTranscriber`, for the languages `SpeechTranscriber` lacks

`DictationTranscriber` is Apple's only on-device route for ca, nl, sv, da, nb, pl, cs, ru, uk,
fi and tr. Whisper here is the 13 Oct trial output of the shipped code for each language
(identical to a fresh run where checked), which kept no word timings, so only words, disagreement
and Dictation's own sound-without-words are measured.

| Language | files | min | Dictation words as % of Whisper | median disagreement | sound, no words (Dictation) | worst file |
|---|---|---|---|---|---|---|
| ca | 3 | 80 | 55% | 42% | 14.5 min | 2% of Whisper |
| cs | 3 | 143 | 59% | 48% | 28.9 min | 52% of Whisper |
| da | 3 | 69 | 39% | 75% | 30.5 min | 17% of Whisper |
| fi | 3 | 71 | 98% | 38% | 17.1 min | 95% of Whisper |
| nl | 3 | 54 | 54% | 38% | 23.5 min | 2% of Whisper |
| no | 3 | 48 | 51% | 66% | 16.6 min | 41% of Whisper |
| pl | 3 | 80 | 93% | 19% | 0.0 min | 89% of Whisper |
| ru | 3 | 91 | 88% | 73% | 10.7 min | 81% of Whisper |
| sv | 3 | 51 | 74% | 47% | 18.4 min | 63% of Whisper |
| tr | 3 | 75 | 72% | 35% | 12.6 min | 63% of Whisper |
| uk | 3 | 52 | 85% | 80% | 4.9 min | 39% of Whisper |

**Calibration** on six files `SpeechTranscriber` also ran: Dictation found 53% of Whisper's
words where `SpeechTranscriber` found 98–100%, left 13–1,258 s of sound without words where
`SpeechTranscriber` left 0–18 s, and scored **94% and 97% WER** on the two Ameresco references
(against 35% and 44%). Its results span long stretches with ~50 words each (one result covers
8–1,282 s of nl-3 with 45 words): it drops most of what it hears. Apple's
`timeIndexedLongDictation` preset and `frequentFinalization` gave the same word counts (45 and
160–162 on nl-3 and es-6), so this is the model, not how it was called. Only Polish (93% of
Whisper's words, nothing lost) comes close.

## 6. Out of the box, measured

- **English: no download at all on this Mac**: the model came with the macOS 27 update (§ 2).
  Whether every Mac gets its primary language's model with the OS is not known.
- **es, fr, de, it, pt, ja, ko, zh: one fetch of 140–150 MB, 8–16 s here, no prompt, no
  entitlement, no admin**, finished by a system daemon even if the requester quits. Against
  Whisper's 1.5 GB (about 5 minutes on a typical connection, per the backend-strategy doc).
- **Then fast**: a 20-minute interview in ~15 s, a 100-minute oral history in ~80 s.
- **The fetch and Whisper's download can run side by side**: they are separate system and
  Python paths; a first session can be transcribed by Apple ~30 s after the drop while
  Whisper's 1.5 GB arrives for later sessions (not timed end to end; each half measured alone).
- **Language must be chosen first** (no detection); the first-run flow would take it from the
  study, the Mac's language list, or Apple's 14 MB language-identification model.
- **Not available before macOS 26**, and not for 11 of the 17 non-English corpus languages
  (Dictation is no substitute, § 5). There, the first run waits for Whisper as today.
- Not tested: a clean user account (that would mean creating one, a system change), and the
  helper-inside-the-app reservation question (§ 8).


### Time to first report: what an Apple-first first run would save (estimated 18 Oct 2026)

Scenario (the owner's): a researcher drags one recording from a recent study onto a fresh
install; no platform transcript beside it; macOS 26 or later; one of Apple's nine languages;
Whisper not yet on disk. Today the 1.61 GB Whisper download happens inside that first run's
transcription stage, on the critical path, behind a banner on the CLI and a spinner in the Mac
app; nothing fetches it earlier (the lazy-download rule), and an interrupted fetch starts again
from zero (hf_xet does not resume, measured 14 Oct 2026). Inputs, all measured on this M2 Max:
Hugging Face delivered 19–25 MB/s here (two 300 MB range fetches of the real file), on a 1 Gbit/s fibre line over Wi-Fi a few metres from the router. The same fetch from PyPI's CDN ran at 32 MB/s, so the Wi-Fi caps one stream near 260 Mbit/s and Hugging Face sits a little below that: neither is the line (the product fetches through hf_xet, which may parallelise better; not measured); Apple's
models are 138–151 MB; an 18-minute Teams interview went from drop to report in 106 s with
Whisper cached (transcription 68 s, LLM stages ~38 s); Whisper RTF 0.04 and Apple's 0.012
(§ 4). Line speeds: typical home broadband taken as 100 Mbit/s (2026 national medians are
roughly 100–180), weak Wi-Fi as 50, 80% of the line reaching the download.

| First recording | Line | Today: download + Whisper + LLM | Apple-first | Saved |
|---|---|---|---|---|
| 18-min interview, English | 100 Mbit/s | 2.7 + 0.9 + 0.7 ≈ **4.3 min** | 0.3 + 0.7 ≈ **1.0 min** | **≈ 3.3 min** |
| 18-min interview, English | 50 Mbit/s | 5.4 + 0.9 + 0.7 ≈ **7.0 min** | ≈ **1.0 min** | **≈ 6.0 min** |
| 60-min interview, English | 100 Mbit/s | 2.7 + 2.4 + ~1.7 ≈ **6.8 min** | 0.7 + ~1.7 ≈ **2.4 min** | **≈ 4.4 min** |
| 60-min interview, English | 50 Mbit/s | 5.4 + 2.4 + ~1.7 ≈ **9.5 min** | ≈ **2.4 min** | **≈ 7.1 min** |
| 18-min interview, English | 1 Gbit/s (this Mac; HF-limited) | 1.2 + 0.9 + 0.7 ≈ **2.8 min** | ≈ **1.0 min** | **≈ 1.8 min** |
| 60-min interview, English | 1 Gbit/s (this Mac; HF-limited) | 1.2 + 2.4 + ~1.7 ≈ **5.3 min** | ≈ **2.4 min** | **≈ 2.9 min** |
| any of the other eight languages | 100 / 50 Mbit/s | as above | add 0.2–0.4 min for Apple's model | ≈ 0.3 min less |

The 60-minute LLM time is scaled from the 18-minute run, not measured. On a slower Apple
silicon Mac both transcription columns grow, Whisper's more (not measured). **Clicks saved:
none.** Neither the Mac app nor the CLI asks before downloading Whisper, and an Apple-first run
would add no question either; the saving is minutes of waiting, plus removing the one way a
first run can lose all its progress (quitting during the download: Apple's fetch finishes in a
system daemon, Whisper's restarts from zero).

**Where it applies:** the Mac app on macOS 26 or later only. Not on macOS 15 (no API), not on
the Linux or Windows CLI (no API, and faster-whisper downloads 1.62 GB just the same), not on
the Mac CLI unless the Swift helper ships with it, not for the eleven other corpus languages, and
not where a platform transcript is present (already no wait). Locales were read on macOS 27
only; macOS 26's list may differ.

## 7. The upgrade-later path: a study with two engines (assessed, not built)

The idea: day one, Apple transcribes with no wait while Whisper downloads in the background;
from day two, Whisper does new sessions. What follows is what the code says that would mean.

- **Nothing breaks mechanically.** Both engines hand stage 5 segments with word timings and
  confidences; stage 5b's voice pass needs only word spans, and the text splitter only text.
  Stage 5's cache fingerprints a session's files, not its engine, so a day-one session would stay
  Apple's on every later run unless the engine joins the fingerprint.
- **The two transcripts read differently** (measured in § 4: fillers, sentence ends, segment
  length), and Apple has no inaudible marker, so its sessions show silence where Whisper's show
  "Inaudible". A researcher comparing two participants would be comparing two transcription
  styles without being told.
- **Quietly re-transcribing a day-one session is safe only before the researcher touches it.**
  Quotes are anchored by participant and start second (`q-p1-123`), stars and tags hang off
  quotes, and transcript layout edits are replayed by paragraph and *refused* when the paragraph
  no longer matches (`bristlenose/server/CLAUDE.md`). A new transcript means new segment times,
  re-run speaker identification, topics and quotes — a second paid analysis of that session — and
  any star, tag, name or edit the researcher made on it is orphaned or refused. So the honest
  shapes are: (a) re-transcribe automatically only sessions nobody has opened, before analysis
  has been shown; or (b) offer it as an explicit, per-session action that says what will be lost;
  or (c) never re-transcribe, and mark which engine wrote each session.
- **The wait being bridged is short anyway.** Apple's fetch is ~140 MB and 8–16 s; the thing that
  takes minutes is Whisper's 1.5 GB. The hybrid buys time only on the first study of a new
  install, which is the moment first impressions are made — and where § 3 decides whether
  Apple's transcript is good enough to be the first impression.

## 8. What integration would cost

- **Swift only** (§ 2), so the Python sidecar cannot call it directly, and pyobjc cannot either.
  Two shapes: the Swift host transcribes and hands segments to the sidecar, or a small sandboxed
  helper executable (like `desktop/mcp-helper/`) that the sidecar spawns with a WAV and gets JSON
  back — `transcribe.swift` here is most of that helper already. The helper is the better fit:
  stage 5 stays the one place transcription happens, and the CLI on a Mac could ship the same
  binary. Cost: a fifth signed executable, its entitlements and privacy manifest, and an
  app-store-police pass.
- **App Sandbox: works**, with no network entitlement and no permission prompt (§ 2). Whether a
  helper inherits the app's reservations or holds its own five was not tested (reservations
  belong to the executable here).
- **Floor: no bump.** Behind `if #available(macOS 26, *)` the code builds at 15.0 (§ 2); on 15.x
  the app keeps Whisper only.
- **Keep the WAV step.** Both Apple input routes fail on 16 kHz AAC (Teams recordings), so the
  helper should take the WAV stage 2 already makes, not the video (§ 4, last subsection).
- **No study vocabulary**: `contextualStrings` has no effect (§ 4), so product and participant
  names cannot be supplied, unlike a Whisper prompt.
- **Parallel sessions are cheap**: four at once ran near-linearly, ~180 MB each out of process.
- **The CLI on PyPI/Homebrew** would need a prebuilt helper in the wheel or formula; the Linux and
  Windows CLI get nothing.
- **Language must be known up front.** One locale per transcriber, no detection. Bristlenose today
  lets Whisper detect the language; with Apple, the app would have to ask, guess from the user's
  locale, or run Apple's separate 14 MB language-identification model first.
- **Five-locale limit.** A study in more than five locales at once (counting regions separately)
  must release and re-reserve; harmless for the 98% one-language case, a real edge for an agency
  running a ten-country study.
- **The model is not ours to pin.** It updates itself with the OS; a re-run months later may not
  reproduce a transcript, and any measurement here has the age of the asset version
  (en 3100.50007.81403 on this Mac).

## 9. Recommendation, against the three wins

**1. Replace Whisper: no, not today.** On the core case it is a match: English and one-to-one
interviews in the nine languages it covers came back at 98–100% of Whisper's words, 4–12%
apart, with true WER level on the only references we have, fewer inserted words, and no loops.
Whisper's own failures on ordinary files (a skipped sentence in two oral histories, a question
lost to a loop, a run-on syllable; 70 s over 12.5 h) are as real as Apple's (52 s over 3.7 h of
interviews). But it covers 9 of our 20 languages; it **drops the second, quieter or overlapping
voice** in group talk (431 s of 1.3 h against Whisper's 38 s; in an interview that voice is the
moderator's or the backchannel); it marks nothing as inaudible; it cannot detect the language;
it drops fillers; and its model updates itself, so a transcript cannot be reproduced.

**2. Work out of the box, then upgrade quietly: yes — this is the win, for nine languages.**
English needs no download on this Mac and the others an 8–16 s fetch, sandbox-safe, no prompt,
no floor bump; a first study can have its report in about a minute instead of after a 1.5 GB
wait. Conditions for building it (none built): record which engine wrote each session and show
it; never re-transcribe a session the researcher has opened (quotes, stars, tags and transcript
edits are anchored to its timings, § 7) — re-transcribe automatically only untouched sessions,
or offer it per session; keep Whisper the default once it is on disk; and say plainly that a
multi-speaker recording may lose its quieter voices on day one.

**3. Fallback: no.** For languages, Apple's only route is `DictationTranscriber`, which loses
most speech in 10 of the 11 languages it would cover (§ 5). For machines, it needs the same Apple
silicon Whisper already runs on, plus macOS 26; it is faster (3.2× here), not more robust.
The one fallback that may be real is **memory**: ~180 MB for Apple against a 9.2 GB peak
footprint for Whisper on a 28-minute file, which on a base 8 GB Mac could decide whether
transcription is usable at all. That needs a measurement on such a Mac before anyone builds on
it.

## 10. Limits of this trial

- One Mac (M2 Max, 32 GB), one OS build (27.0, 26A428), one asset version per language,
  measured 18 Oct 2026. Apple updates the models silently; re-measure before building.
- Only two files have human references, and both are extreme. Everything else is agreement
  between engines plus reading the places they disagree; where both are wrong the same way,
  nothing here can see it.
- L2 and strongly regional English, overlapping speech in remote calls, and the cohort's own
  recordings were not specifically covered. The backend-strategy doc's four mismatches (noise,
  pace, accents, L2 English) are therefore half-tested: pace and ordinary accents held up in
  English and the five European languages; noise and crosstalk did not.
- Real-time factors were measured with nothing else heavy running, except brief analysis
  passes during the English Whisper files.
- The extreme recordings' numbers (es-1, es-4, es-5, es-6, it-3, pt-pt-2) are in their own table
  and in no summary.

## 11. Files and re-running

Probes (Swift, `swiftc -parse-as-library -O <file> -o <bin>`): `probe_locales.swift` (locales,
asset status), `transcribe.swift` (one file → JSON; `--list`, `--release`), `sandbox_probe.swift`
with `sandbox.entitlements` and `sandbox-Info.plist` (App Sandbox check), `video_probe.swift`
(macOS 27 direct video input). Drivers:
`run_apple.py <bin> speech|dictation [ids or langs]`, `run_whisper.py [ids or langs]` (the
product's stage-5 path). Analysis: `analyse.py speech|dictation`, `one_sided.py` (dumps the
disagreeing stretches for reading), `tables.py`. Transcripts, dumps and per-file results stay
in the gitignored trial folder: they hold participants' speech. This note carries numbers and verdicts only.

## 12. What to measure next, and a download list for approval (nothing fetched)

The two gaps that most limit the verdict are human references outside the extreme Spanish
files, and non-native English. Two public corpora cover both; each needs the owner's approval
before any download, and each licence file to be read first.

| Corpus | What it adds | Licence (as listed, 18 Oct 2026) | Proposed batch |
|---|---|---|---|
| AMI Meeting Corpus (Edinburgh; also OpenSLR 16) | group meetings, **mostly non-native English speakers**, manual transcripts **with word timings** (true WER for the group-talk failure, and a timing ground truth) | CC BY 4.0 (signals, transcription, some annotations; annotations v1.6.2 carry their own LICENCE.txt) | 4 meetings, headset mix only (~30 MB each, ~120 MB), plus the manual-annotations zip |
| Earnings-22 (Rev, `revdotcom/speech-datasets`) | calls by speakers from 27 countries in 7 language regions, references with entities | CC BY-SA 4.0 (catalogue listing; check `LICENSE.md`) | 4 calls from different regions |

Also open, needing hardware or people rather than downloads: a base 8 GB Mac (memory and
speed, § 9), and the cohort's own recordings. Sources:
<https://groups.inf.ed.ac.uk/ami/corpus/>, <https://groups.inf.ed.ac.uk/ami/download>,
<https://huggingface.co/datasets/legacy-datasets/ami>,
<https://github.com/revdotcom/speech-datasets>, <https://arxiv.org/abs/2104.11348>.

## 13. Before the large model arrives: a fallback grid (18 Oct 2026)

The owner's framing: the first run says, in effect, *"OK to get the big model?"* with one of three
reasons — **(1) it improves quality, and Apple's model covers you until then**, **(2) it is needed
for your language**, or **(3) it is needed on your system** — and fetches it. If the researcher
transcribes before it lands, give them something in as many cases as possible. Candidate stopgaps,
best first: a platform transcript; Apple's `SpeechTranscriber`; cloud transcription through the
researcher's own LLM provider; a small Whisper model. Download sizes are from
`bristlenose/preflight/whisper.py` (`_DOWNLOAD_MB`).

| Scenario | Message | Stopgap before the large model | Its download | Evidence |
|---|---|---|---|---|
| Any platform, platform transcript beside the recording | none | the platform transcript | 0 | shipped; Whisper never loads |
| Mac app, macOS 26/27, Apple silicon, one of Apple's 9 languages | (1) | Apple `SpeechTranscriber` | 0 (English came with macOS 27 here) or 138–151 MB, 8–16 s | measured here: level with Whisper on 1:1, loses quieter voices in group talk; needs the Swift helper (not built) |
| Mac app, macOS 26/27, any other language | (2) | small Whisper, or cloud via provider | small 481 MB / base 144 MB | small and base unmeasured on our corpus; Apple Dictation measured and rejected (§ 5) |
| Mac app, macOS 15.x | (3) | small Whisper, or cloud via provider | as above | no Apple API before 26 |
| Mac app, 8 GB Apple silicon (any macOS) | (1)/(3) | as the rows above, and possibly *standing*, not just first-run | — | Whisper's peak footprint was 9.2 GB on a 28-min file on a 32 GB Mac (§ 4); behaviour on 8 GB unmeasured |
| Mac CLI (PyPI, Homebrew), Apple silicon | (3) unless the helper ships | small Whisper, or cloud via provider | small 481 MB | Apple route only if the Swift helper ships in the wheel or formula |
| Mac CLI, Intel Mac (the app is arm64-only) | (3) | small Whisper on CPU, or cloud via provider | small 486 MB | mlx needs Apple silicon; faster-whisper runs on CPU, speed unmeasured; Apple's engine reported Apple-silicon only (§ 1) |
| Linux x86_64 CLI (pip, Snap, Fedora Copr), CPU | (3) | small Whisper, or cloud via provider | small 486 MB / base 148 MB | no OS speech engine; large-v3-turbo is 1.62 GB here |
| Linux or Windows with an NVIDIA GPU | (3) | as above; once downloaded, CUDA float16 makes the large model fast | as above | faster-whisper picks CUDA when present (`_init_faster_whisper_backend`) |
| Windows x86_64 CLI (pipx/uv) | (3) | small Whisper, or cloud via provider | as Linux | Windows' own speech APIs not explored |
| Any platform, offline, hotspot or Low Data Mode | — | a model already on the machine (Apple's English with macOS 27; a cached Whisper), else the platform transcript, else wait | 0 | detect with `NWPathMonitor` on the Mac |

**Cloud transcription through the researcher's provider** works on every platform with no
download, but only for some providers: ChatGPT/OpenAI and Gemini accept audio, and Azure OpenAI
does with a transcription deployment. Claude, the most common choice, does not take audio input as
far as we know (re-check before relying on it), and Ollama has no speech model. It also sends
participants' **voices**, not just transcript text, to the provider: a step up the consent
gradient (`docs/methodology/consent-gradient.md`), and a cost. None of it is built or measured in
Bristlenose.

### The small and base Whisper models, measured (18 Oct 2026, later the same day)

Both through the product's own stage-5 path (`run_whisper.py --model=small|base`, the shipped
prompts and nets) on 31 ordinary files, compared with large-v3-turbo (`compare_models.py`). The
numbers are **distance from turbo**, not error: turbo is the reference because it is what the
researcher gets once it arrives. Apple's distance from turbo on the same files is beside it.

| Group | small: median distance | base: median distance | Apple: median distance | notes |
|---|---|---|---|---|
| English (7 files) | 15.5% | 26.3% | 12.7% | small and turbo agree on word count (99%) |
| Interviews in Apple's 9 languages (11) | 16.5% | 31.8% | 8.6% | Apple is about twice as close to turbo as small |
| Group talk (2) | 40.2% | 59.7% | 34.0% | all three lose the quieter voices turbo hears |
| The 11 languages Apple lacks (11) | 32.9% (6.5–73.4%) | 54.3% | — | small: Dutch 12%, Polish 7%, Swedish 20%, Turkish 22%; Czech 44%, Ukrainian 55%, Russian 73% (22 loop segments, 11 min of sound without words in one file) |

Speed: small's real-time factor was 0.040, the same as turbo's (turbo's four-layer decoder
makes it as fast as small); base 0.025. So the small model saves only download size
(481 MB against 1.61 GB). **Verdict:** in Apple's nine languages, Apple is the better
stopgap. Elsewhere, small is a usable stopgap for Dutch, Polish, Swedish and Turkish and a
poor one for Russian, Ukrainian and Czech; base is not worth offering. One file per
language outside Apple's nine, so per-language claims are thin.
