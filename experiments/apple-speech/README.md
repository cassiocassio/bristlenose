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
`SpeechTranscriber` scored 35–44%). § 9 has the reasoning and the conditions.

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
Whether that speed matters on a base 8 GB M1, where Whisper is slowest, is the one fallback
question left open.

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
with `sandbox.entitlements` and `sandbox-Info.plist` (App Sandbox check). Drivers:
`run_apple.py <bin> speech|dictation [ids or langs]`, `run_whisper.py [ids or langs]` (the
product's stage-5 path). Analysis: `analyse.py speech|dictation`, `one_sided.py` (dumps the
disagreeing stretches for reading), `tables.py`. Transcripts, dumps and per-file results stay
in the gitignored trial folder: they hold participants' speech. This note carries numbers and verdicts only.
