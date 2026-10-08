---
status: research
date: 6 Oct 2026
---

# Transcript readability: better Whisper text, shorter paragraphs, a readable layer

Research, 6 Oct 2026. It answers four questions the owner
raised after reading *IKEA with uxfriends* s1 in the transcript page: lower-case,
unpunctuated stretches; 60–105 s paragraphs; word lists that disagree with the
paragraph text at the edges; and whether the raw transcript should get a readable
presentation the way quotes already do.

**Status, 8 Oct 2026.** One piece is built: sentence-start capitals (recommendation #3's
second part, the capitalisation mockup's option C) shipped as display-only CSS in
`512f0846`, recorded in `design-transcript-editing.md`. Recommendations #1 and #2, and
the rest of #3, are not built. The side-by-side comparison of today's transcript against
five candidate versions is `docs/mockups/transcript-readability-versions.html`; the
scripts behind it and behind every measurement here are in
`experiments/transcript-readability/`.

Labels: **MEASURED** (run or counted for this doc, method given), **VERIFIED**
(read in source code), **DOCUMENTED** (vendor or primary source), **COMMUNITY**
(issue threads, reviews), **INFERRED** (reasoning, not tested). All measurements
were local: no paid LLM calls, and nothing was written inside a project's folders
(databases and audio were copied to a scratchpad first).

---

## Recommendation

**The main cause is upstream of the transcript page.** Whisper, as stage 5 runs it on
the Mac, chooses a fresh style for every 30-second window, and on filler-heavy
conversational speech it often chooses lower case with no punctuation. Paragraph
length, the edge disagreements and the lower-case paragraph starts all follow from
that. Fix the source first, then the paragraph rule, then the display.

| # | What | Why | Effort | Risk |
|---|---|---|---|---|
| **1** | **Give mlx-whisper a short punctuated prompt on *every* window, in the session's language.** Keep `condition_on_previous_text=False` and the 1.8 compression threshold. Needs a one-line change to mlx-whisper's decode loop (it has no `carry_initial_prompt`), a per-language prompt table, and the language decided *before* the prompt is chosen. | On s1: 72 → 280 sentences, lower-case "i" 96/172 → 0/174, longest unpunctuated run 681 → 31 words, and the moderator's question lands in its own segment. Almost deterministic across runs. Japanese: 0 → 18 full stops. | 1–2 days with tests | Prompt text can leak into the transcript (seen once, caught by the 1.8 threshold). A prompt in the wrong language is dangerous (seen: English loops on Japanese audio). Both have guards, below. |
| **2** | **Stage 6: once a paragraph passes ~60 words, end it at the next sentence end** (same speaker and gap ≤ 2 s otherwise unchanged). Count characters, not words, for languages written without spaces. Apply only to sessions transcribed after the change. | With #1's output this alone leaves no paragraph over 150 words on s1 (median 63, max 145). Without #1 it does little, because there are no sentence ends to break at. | ½–1 day | Every existing project would re-paragraph on its next run and lose replayed splits, joins and speaker moves, which are keyed by paragraph position. Hence the per-session version pin. |
| **3** | **Display layer, deterministic:** draw the stored text's own spelling with the word timings mapped onto it, capitalise where a sentence begins (the capitalisation mockup's option C), and dim a closed list of pure fillers (um, uh, er, erm, hmm; per language). No "clean read" rewriting. | The stored words stay untouched, as research norms want; scanning improves. Precedent: Descript's "Ignore", Sonix's strikethrough. | 1–2 days | Filler lists are language-specific; the ambiguous tier ("like", "you know") must be left alone. |

Not recommended now: an LLM "clean read" of the raw transcript (it rewrites the
words, which is what quotes are for); WhisperX forced alignment (a model per
language, about 1 GB, for a timing gain we have not shown we need); a separate
punctuation-restoration model (after #1 there is little left for it to do, and the
one multilingual option is weak on conversation).

Also found, separate from readability (§1.4): **this project's stored text and its
word timings come from two different Whisper runs**, joined because they agreed
well enough. Stage 5 output is not reproducible on the current settings, so any
cache that keeps one stage's copy while re-running another can do this again.

---

## 1. What was actually observed

### 1.1 The raw Whisper output alternates between two styles (MEASURED)

`session_segments.json` holds Whisper's segments before merging. Counted per project
(transcribed sessions only; Fishkeeping and most of Rockclimbing came from `.vtt`
files and are excluded):

| Project | Session(s) | Words | Lower-case pronoun "i" | Words in runs of 40+ with no `.,?!` | Words per sentence |
|---|---|---|---|---|---|
| IKEA with uxfriends | s1 | 2,681 | 76 of 167 (46%) | 64% | 25.5 |
| fossda-opensource | s2, s6 | 7,060 / 3,175 | 0% | 20% / 29% | 17.5 / 27.9 |
| fossda-opensource | other eight | 3k–14k each | 0% | 0–1% | 12–19 |
| project-ikea | s2, s3 | 418 / 316 | 20% / 27% | 33% / 25% | ~10.5 |

Two failure styles, both large-v3-turbo on mlx:

- **Lower-case, unpunctuated** (uxfriends, project-ikea; transcribed with
  `condition_on_previous_text=False`, set in `a8d12872`, 14 May 2026): the style
  flips window by window. In s1, 201 of 326 raw segments are of this kind.
- **Cased but unpunctuated** (fossda s6, transcribed 30 Apr 2026, before that commit,
  so with conditioning on): a single 652-word run with correct capitals ("ASF",
  "Apache") and no punctuation at all. With conditioning on, a style persists once
  chosen.

The unpunctuated segments are also long (5–10 s against ~1.7 s for punctuated ones)
and **run across speaker turns**: "…be emotive i guess okay what is it" is one
segment, with the moderator's "okay what is it" at the end of the participant's
line. Speaker identification labels whole segments, so the question's first words
go to the participant's paragraph. That is the edge disagreement the owner saw.

### 1.2 The current settings are not reproducible (MEASURED)

The same 5-minute excerpt of s1 (1:00–6:00), the current stage-5 settings, three
separate processes: 838, 1,051 and 831 words; 17, 14 and 20 sentences; 33–40 of
~65 segments decoded by **temperature fallback** (sampled, not greedy). On the full
18-minute file, 145 of 314 segments were fallback decodes.

Cause (VERIFIED in mlx-whisper 0.4.3, `decoding.py` and `transcribe.py`): a window
whose compression ratio exceeds `compression_ratio_threshold` (we set 1.8; the
default is 2.4) is re-decoded at temperatures 0.2…1.0, and mlx has no beam search,
so each retry is a random sample. Filler-heavy speech compresses well and trips 1.8
often. If every temperature fails, the T=1.0 result is kept.

The threshold was lowered on purpose, to break repetition loops on long audio
(`a8d12872`). §2.3 shows it still does that job, so the answer is not to raise it.

### 1.3 Paragraph lengths across the trial runs (MEASURED)

From each project's serve database (`transcript_segments`, one row per paragraph;
the `(Speaker X)` prefix stripped before counting words):

| Project | Source | Paragraphs | Seconds p50 / p90 / max | Words p50 / p90 / max | Paragraphs > 150 words | Share of all words in them |
|---|---|---|---|---|---|---|
| Fishkeeping | `.vtt` | 3,246 | 9 / 43 / 206 | 27 / 110 / 443 | 86 | 11% |
| IKEA with uxfriends | Whisper | 58 | 10 / 48 / 105 | 20 / 140 / 300 | 4 | 33% |
| Rockclimbing | mostly `.vtt` | 171 | 5 / 20 / 28 | 17 / 72 / 98 | 0 | 0% |
| fossda-opensource | Whisper | 972 | 24 / 136 / 1,412 | 49 / 323 / 3,799 | 218 | **75%** |
| project-ikea | Whisper | 93 | 5 / 11 / 16 | 7 / 18 / 24 | 0 | 0% |

Interviews with short turns (project-ikea) are fine. Long-form speech is not: in
fossda (oral history) three-quarters of all words sit in paragraphs over 150 words,
and one paragraph is 23 minutes long.

### 1.4 Why this project's text and words disagree (MEASURED)

For *IKEA with uxfriends* s1, the transcript page shows Whisper's word list
(`TranscriptPage.tsx` draws `seg.words` *in place of* `seg.text` when words exist).

- The **text** comes from the speaker-ID cache, `speaker-info/s1.json`, written
  **16 Jul 2026** by that day's Whisper run. Stage 5b's cache was reused on later runs.
- The **words** are backfilled by the importer from `session_segments.json`, written
  **27 Aug 2026** by a later Whisper run of the same audio
  (`importer._enrich_words_from_intermediate`).
- Given §1.2, the two runs differ in style. At 2:00 the text reads "Well, you know,
  a lot of like household stuff," and the words read "um well you know a lot of like
  household stuff uh so sort of you quite".
- The importer keeps words when the token sequences match at ≥ 0.9
  (`_words_read_as`, which lower-cases and drops punctuation first). Re-running its
  time-based join on this database: 45 of 58 paragraphs keep words, and 9 of those
  differ in their first or last three words.

So "the words are lower-case where the text is cased" is, in this project, two
different transcriptions shown as one. The general version: **any stage-5 re-run
under the current settings produces a different transcript**, and any cache that
pins one stage's copy can pair it with another's. Recommendation #1 makes stage 5
much more repeatable (15–17 fallback segments per file instead of 145), which
shrinks this. Pinning the words to the text's own run is the proper fix and belongs
with the pipeline-resume work, not here.

Smaller contributors, VERIFIED in code:

- `collapse_adjacent_repeats` edits the segment text, not its words
  (`s05_transcribe.py`), so a collapsed repeat appears in the words and not the text.
- `_merge_same_speaker` extends `prev.words` on a `model_copy()`, which is shallow,
  so the first segment's original `words` list is mutated too. Harmless today
  (nothing reads the pre-merge list afterwards), worth knowing.

---

## 2. Question 1 — getting better text out of Whisper

### 2.1 How stage 5 runs Whisper today (VERIFIED, `s05_transcribe.py`)

| | mlx-whisper (Apple Silicon, the Mac app) | faster-whisper (elsewhere) |
|---|---|---|
| Model | large-v3-turbo | `settings.whisper_model` |
| `condition_on_previous_text` | **False** | True (library default) |
| `compression_ratio_threshold` | **1.8** | 2.4 (default) |
| VAD | none (the signal gate drops silent stretches) | `vad_filter=True` (Silero, needs onnxruntime) |
| `initial_prompt` / `hotwords` | none | none |
| Word timings | cross-attention + DTW | same method, CTranslate2 |

### 2.2 Why Whisper drops punctuation (DOCUMENTED, COMMUNITY, VERIFIED)

- OpenAI's speech-to-text guide: the model follows the prompt's style, so it is
  "more likely to use capitalization and punctuation if the prompt does too", and
  "sometimes the model might skip punctuation". A prompt with fillers keeps fillers.
  [platform.openai.com/docs/guides/speech-to-text](https://platform.openai.com/docs/guides/speech-to-text)
- The openai/whisper maintainer describes the model getting "stuck into a
  'no-punctuation mode'" and recommends a punctuated `initial_prompt`.
  [discussions/194](https://github.com/openai/whisper/discussions/194),
  [discussions/290](https://github.com/openai/whisper/discussions/290)
- large-v3 users report missing punctuation and capitals "3 to 4 times more
  prevalent" than v2; turbo is fine-tuned from v3's data. COMMUNITY.
  [discussions/1762](https://github.com/openai/whisper/discussions/1762),
  [discussions/2363](https://github.com/openai/whisper/discussions/2363)
- Field reports with conditioning on: one podcast archive found 118 of 1,734
  episodes (6.8%) unpunctuated on faster-whisper turbo, 113 of them from the first
  word; a punctuated prompt fixed it.
  [podcast_scraper#2284](https://github.com/chipi/podcast_scraper/issues/2284)

**The prompt reaches only the first window on our settings** (VERIFIED, mlx-whisper
0.4.3 `transcribe.py`): the prompt tokens are put at the start of `all_tokens` once
(L257–259); each window decodes with `all_tokens[prompt_reset_since:]` (L296); and
when `condition_on_previous_text` is False, `prompt_reset_since` moves to the end
after every window (L532–534). faster-whisper 1.2.1 does the same with
`initial_prompt`, but its `hotwords` parameter is added to the prompt of **every**
window (`get_prompt`, L1542–1548). openai-whisper has a `carry_initial_prompt`
option; mlx-whisper does not.

### 2.3 Local experiment on s1 (MEASURED)

mlx-whisper 0.4.3, large-v3-turbo, M2 Max, `language="en"`, word timestamps on,
`no_speech_threshold=0.85` throughout. "Carried prompt" means L296 patched to
`initial_prompt_tokens + all_tokens[max(len(initial_prompt_tokens), prompt_reset_since):]`,
openai-whisper's `carry_initial_prompt` form. Prompt P1:
*"Okay, so, um, tell me about it. Well, I think it's good, you know? Yeah."*
Prompt P2: *"Hmm, okay. Well, yes, I suppose so, um, and then? Right."*

**5-minute excerpt (1:00–6:00), ~830 words of speech:**

| Setting | Sentences | Words / sentence | Lower-case "i" | Longest unpunctuated run | Fallback segments |
|---|---|---|---|---|---|
| Current (cond. off, 1.8), several runs | 14–34 | 24–55 | 9–19 of ~25 | 107–379 | 33–55 |
| Conditioning on | 19 | 44.7 | 21/26 | 647 | not recorded |
| Threshold 2.4, no prompt | 8 | 106.9 | 16/26 | 466 | 0 |
| Prompt, first window only | 15 | 55.5 | 18/27 | 339 | not recorded |
| Prompt + conditioning on | 43 | 20.1 | 7/26 | 181 | not recorded |
| P1 re-sent per 30 s chunk (cut by us) | 54 | 15.9 | 1/29 | 39 | not recorded |
| **P1 carried, 1.8** | 60 | 14.4 | 0/30 | 24 | 17 |
| P1 carried, 2.4 | 56 | 15.5 | 0/28 | 31 | 0 |
| Prompt without fillers ("Hello. Welcome, everyone. Let's begin.") carried, 1.8 | 65 | 11.3 | 0/25 | 20 | 10 |

**Full 18-minute file:**

| Setting | Time | Words | Sentences | Lower-case "i" | Longest unpunctuated run | Adjacent n-gram repeats | Fallback | Prompt leak |
|---|---|---|---|---|---|---|---|---|
| Current | 84 s | 2,753 | 72 | 96/172 | 681 | 25 | 145/314 | — |
| P1 carried, 2.4 (two runs, identical) | 34 s | 2,814 | 282 | 0/176 | 31 | 17 | 0 | **1 segment** |
| **P1 carried, 1.8** (two runs) | 46–47 s | 2,812–2,814 | 280–282 | 0/174–177 | 31 | 6 | 15–17 | 0 |
| P2 carried, 1.8 | 52 s | 2,781 | 277 | 0/169 | 24 | 6 | 23 | 0 |

What the numbers say:

- **Only a prompt on every window fixes the style.** Conditioning alone makes it
  worse (the style locks in); the prompt on the first window only does nothing
  measurable.
- **Keep 1.8.** With 2.4 the decoder was deterministic and fastest, but at 7:23 it
  replaced the moderator's real words ("give me some first impressions, tell me
  anything that stands out to you") with the prompt itself, "Tell me about it." four
  times. At 1.8 that window failed the compression check, was re-decoded, and came
  out right (and heard "IKEA.com" where the 2.4 run heard "our kid at com"). The
  loop guard from `a8d12872` is still earning its keep.
- **The prompt's content matters.** P1 contained an interview phrase ("tell me about
  it"), and that is what leaked. A prompt should be generic hesitation and assent,
  unlikely to be mistaken for a question. A post-filter that drops a segment made
  only of a prompt sentence, alone or repeated, is cheap insurance.
- **The prompt decides filler style.** P1 and P2 contain "um", and fillers then
  appear, comma-separated ("Um, it's a good one. Uh, let's say…"). The prompt with
  no fillers produced 11% fewer words on the excerpt, which suggests fillers were
  dropped. Bristlenose wants verbatim input (quote extraction turns fillers into
  "..." itself), so **the prompt should contain fillers**. INFERRED from one run.
- **Segments now end at sentences**: 125 of 140 raw segments end with `.?!` (against
  69 of 314 today), and the moderator's "Okay. What is it that you like about it?"
  is its own segment at 1:56. Speaker identification labels whole segments, so this
  should fix most edge disagreements. INFERRED; stage 5b was not re-run (its LLM
  pass is paid).
- Remaining nondeterminism at 1.8: 15–17 fallback segments, and two runs differed by
  two words. Seeding MLX's random generator before each file would make it
  repeatable. Not tested.

### 2.4 Other levers

| Lever | Verdict | Evidence |
|---|---|---|
| `condition_on_previous_text=True` | No. Locks a bad style in for the rest of the file and brings back repetition loops. | MEASURED above; the openai-whisper docstring warns of "repetition looping or timestamps going out of sync" (VERIFIED); WhisperX disables it by default (DOCUMENTED). |
| large-v3 instead of turbo | Not tested. v3 is reported worse for punctuation than v2, and turbo is trained on v3's data, so a switch is unlikely to help on its own. | COMMUNITY |
| VAD (Silero) | Worth doing later, for silence hallucination and natural chunk boundaries, not for punctuation. faster-whisper's VAD needs onnxruntime, which the Mac sidecar now ships for the voice pass (`stages/CLAUDE.md`, Stage 5b); Silero also exists as a ~2 MB PyTorch JIT model. WhisperX's VAD cut-and-merge into ~30 s chunks is the reference design. | DOCUMENTED: [silero-vad](https://github.com/snakers4/silero-vad), [WhisperX paper](https://arxiv.org/abs/2303.00747) |
| `hallucination_silence_threshold` (mlx has it; needs word timestamps) | Untested. Skips long silent stretches when a hallucination is suspected. Would complement the signal gate. | VERIFIED present in mlx 0.4.3 |
| faster-whisper path | Same style risk, with conditioning on by default. `hotwords` reaches every window, so passing the per-language prompt there is the equivalent fix. INFERRED; not run here. | VERIFIED in source |
| WhisperX (wav2vec2 forced alignment) | Not now. A model per language, ~1 GB each (estimate), and tokens with no letters ("£13.60", "2014.") cannot be aligned. Our timings are adequate for click-to-seek. | DOCUMENTED: [WhisperX](https://github.com/m-bain/whisperX) |
| Punctuation/truecasing restoration after Whisper | Not now. Only `1-800-BAD-CODE/punct_cap_seg_47_language` covers casing, sentence boundaries and many languages (Apache-2.0, ONNX, 128-token windows), and its card says it is trained on news and "unlikely to be of production quality". `deepmultilingualpunctuation` is 4 languages, no casing; NeMo's is English. All work on text, so word timings would have to be re-mapped. | DOCUMENTED, model cards |
| Fine-tunes | CrisperWhisper is verbatim with better timestamps around fillers, but **CC-BY-NC**, English and German only. distil-large-v3 is English only. Neither can be the default. | DOCUMENTED |

### 2.5 What #1 needs, concretely

1. **The carried prompt.** Either vendor mlx-whisper's `transcribe.py` with the
   one-line L296 change, or wrap the library. An mlx-whisper upgrade must re-check
   the patch; a test should fail if the line moves.
2. **A prompt per language**: short (well under the 224-token prompt budget), in
   that language's own punctuation, with that language's fillers, no interview
   phrases. One string per Whisper language we support; no prompt for the rest.
3. **Language before prompt.** With `whisper_language="auto"`, detect first (mlx's
   `detect_language` on the first window, or a short first pass), then transcribe
   with the language pinned and its prompt. Never send a prompt to audio whose
   language is unknown (§5).
4. **A leak filter**: drop a segment that is a prompt sentence, alone or repeated.
5. Transcripts change only when re-transcribed. Existing projects keep their cached
   `session_segments.json`; nothing re-transcribes on its own.

---

## 3. Question 2 — paragraph breaks

### 3.1 What others do (DOCUMENTED unless marked)

- **Every tool breaks at speaker turns.** None publishes a maximum paragraph length.
- **Deepgram `paragraphs`**: "identified based on the transcript's punctuation",
  influenced by speaker changes; no thresholds published.
  [docs](https://developers.deepgram.com/docs/paragraphs)
- **AssemblyAI `/paragraphs`**: "will attempt to semantically segment"; no
  thresholds. [docs](https://www.assemblyai.com/docs/api-reference/transcripts/get-paragraphs)
- **Rev.ai** returns speaker monologues, not paragraphs.
  [docs](https://docs.rev.ai/api/features)
- **Dresing & Pehl** (the German qualitative norm, used with MAXQDA): one paragraph
  per speaker turn, timestamp at its end.
  [PDF](https://msskapstadt.de/wp-content/uploads/2015/12/EN_Transcription-system-Dresing-Pehl-simplified1.pdf)
- **Retkowski & Waibel**, "Paragraph Segmentation Revisited": human-paragraphed TED
  talks average **4.4 sentences per paragraph**; a naive "break every 5 sentences"
  baseline scored poorly on boundary F1 but readers rated it 3.30/5, attributed to the
  visual structure. Pause-based breaking was not evaluated.
  [arXiv 2512.24517](https://arxiv.org/html/2512.24517)
- **BBC subtitle guidelines**: break at logical points, ideally a full stop, comma or
  dash; never between article and noun, or a conjunction and its clause. COMMUNITY
  summary; the canonical page did not load.
  [bbc.github.io/subtitle-guidelines](https://bbc.github.io/subtitle-guidelines/)
- Rev's style guide is reported to cap paragraphs at 8 lines. COMMUNITY, unverified.

So the defensible rule has Deepgram's shape: speaker turn first, then sentence ends,
with a length target. No vendor uses topic shifts for paragraphs; Bristlenose's
topic segmentation (stage 8) already works a level above.

### 3.2 Simulated rules (MEASURED)

Rebuilt from raw segments, with each segment's speaker taken from the existing
paragraphs by time. This is approximate: under the current rule uxfriends comes out
at 48 paragraphs against the real 42. "Sentence end" means the paragraph so far ends
in `. ? ! …`. "Hard" means break at the next raw-segment boundary regardless.

**On today's Whisper output:**

| Rule | uxfriends: words p50 / p90 / max · % of words in > 150-word paragraphs | fossda: same |
|---|---|---|
| A. Current (same speaker, gap ≤ 2 s) | 29 / 159 / 327 · 51% | 50 / 323 / 3,799 · 75% |
| B. A + end at a sentence end once ≥ 60 words | 32 / 85 / 327 · 34% | 63 / 115 / 607 · 27% |
| D. A + end at a sentence end once ≥ 30 s | 29 / 109 / 327 · 32% | 68 / 138 / 607 · 27% |
| E. Gap ≤ 1.0 s instead of 2.0 | 17 / 105 / 302 · 16% | 27 / 130 / 930 · 45% |
| H. B at 40 words + hard break at 100 | 37 / 100 / 113 · 0% | 47 / 103 / 134 · 0% |

**On the recommended Whisper output (P1 carried, 1.8), uxfriends s1:**

| Rule | Paragraphs | Words p50 / p90 / max | Seconds p90 / max | > 150 words |
|---|---|---|---|---|
| A. Current | 23 | 43 / 313 / 685 | 128 / 242 | 6 (73% of words) |
| **B. Sentence end once ≥ 60 words** | 47 | 63 / 116 / 145 | 40 / 53 | **0** |
| H. 40 soft + 100 hard | 57 | 43 / 87 / 116 | 29 / 47 | 0 |

Three readings:

- **Fixing Whisper alone makes paragraphs longer**, not shorter: punctuated segments
  are longer, and the 2 s merge swallows more of them (685-word maximum).
- **Fixing the paragraph rule alone only half works**, because the unpunctuated
  stretches have no sentence ends. Only a hard break (rule H) reaches them, and a hard
  break at a segment boundary cuts mid-sentence.
- **Together, the plain sentence-end rule is enough.** 60 words is about four
  sentences for this speaker (~15 words each), in line with the 4.4-sentence human
  norm.

### 3.3 Proposed rule for stage 6

Keep `_merge_same_speaker`'s conditions and add one:

- New paragraph on speaker change or gap > 2.0 s (unchanged).
- New paragraph when the paragraph so far is at least **60 words** (or **~150
  characters** in a language written without spaces, §5) **and** it ends a sentence.
  Seconds are a worse unit: speech rate varies by speaker and language, and what a
  reader scans is text.
- A hard ceiling only as a backstop (say 200 words), breaking at the largest pause
  between segments in the last stretch, never inside a segment. With #1 in place it
  should almost never fire; it is there for platform transcripts with no punctuation.

### 3.4 What changing paragraphs disturbs

A paragraph is not only a display unit. VERIFIED in code and docs:

- **Layout edits.** Splits, joins and the 6 Oct speaker moves are stored by
  paragraph position in reading order plus first words (`transcript_layout_edits`,
  `transcript_layout.replay`). Stage 6 always re-runs (`stages/CLAUDE.md`), so a new
  rule would re-paragraph every existing project on its next run, and every recorded
  edit from the first changed paragraph on would be refused and logged
  (`design-transcript-editing.md`: "one refused edit in a replay shifts every later
  position"). **So apply the new rule only to sessions transcribed after it ships**,
  recorded per session (a merge-rule version beside the transcript), never
  retroactively.
- **`segment_index`** is assigned in stage 6 and copied onto quotes
  (`design-quote-sequences.md`). Ordinals change; the sequence-detection gap
  threshold, still "undetermined" there, would need re-checking.
- **Quote marking in the transcript** matches a paragraph whose start falls inside
  the quote's time window (`design-people.md` §K3). Shorter paragraphs put more
  paragraph starts inside quote windows, so marking should get more precise.
  INFERRED.
- **Paragraph speaker moves and evidence** (§K6) read which paragraphs a quote
  overlaps. Shorter paragraphs make a move more surgical. INFERRED.
- **Speaker attribution is not affected**: identification runs on raw segments before
  the merge. What fixes the edges is #1, by giving it segments that end at turns.
- **The raw `.txt`/`.md` files** get more, shorter blocks. They are a round-trip
  format and the reader takes any number of blocks, so no format change.

---

## 4. Question 3 — raw versus readable

### 4.1 What research tools do (DOCUMENTED unless marked)

| Tool | Fillers | Stored text changed? |
|---|---|---|
| Descript | Detected (English only) and underlined; per filler: delete, leave a gap, **Ignore** (strikethrough, audio cut), or remove from transcript only | Ignore is display-level and reversible |
| Sonix | Account toggle; an auto-found list shown as **strikethrough** | Display-level (COMMUNITY) |
| Otter | Strips "um/uh" by default, no option (COMMUNITY) | Yes |
| Grain | "Remove filler words" on by default; turning it off needs **reprocessing** | Yes |
| Happy Scribe | Clean read by default; verbatim for human transcripts | Per job |
| NVivo | Full verbatim / clean verbatim / edited | Per job |
| MAXQDA | Verbatim or not; filler option English only | Per job |
| Reduct | Its guideline removes um/uh and filler "like"/"you know", keeps them as real words, keeps back-channels | Per transcript |
| Dovetail, Marvin, Condens, Trint | Nothing documented on fillers; Trint is paragraph-per-speaker with a "verified" tick | — |
| Looppanel | Markets "intelligent verbatim"; colours questions and sentiment in the transcript (COMMUNITY) | — |

Three models: strip at transcription time (Otter, Grain, and the Deepgram and
AssemblyAI API defaults); choose a mode per job (NVivo, Happy Scribe, MAXQDA); or
**mark over intact text** (Descript Ignore, Sonix). Only the third keeps the
rawness.

### 4.2 Research norms

- **Verbatim** keeps fillers, false starts and stutters; **clean verbatim** removes
  those "that don't affect the substance". Rev itself recommends verbatim for
  research. [rev.com](https://www.rev.com/resources/verbatim-transcription)
- **Oliver, Serovich & Mason 2005**: "naturalized" transcription (every utterance)
  versus "denaturalized" (what was said, not how).
  [paper](https://www.researchgate.net/publication/7243100_Constraints_and_Opportunities_with_Interview_Transcription_Towards_Reflection_in_Qualitative_Research)
- **McLellan, MacQueen & Neidig 2003**: there is no universal format; their protocol
  is verbatim, including hm, uh huh, um.
- **Poland 1995**: "verbatim" is an assumption more than a verified property, and
  methods should say how transcripts were made.
- **Fillers carry meaning.** "uh" signals a short expected delay and "um" a longer
  one (Clark & Fox Tree 2002,
  [PDF](http://www.columbia.edu/~rmk7/HC/HC_Readings/Clark_Fox.pdf)); keeping them
  improves prediction of a speaker's confidence (Dinkar et al., EMNLP 2020,
  [arXiv](https://arxiv.org/abs/2009.11340)). An argument for dimming, not deleting.
- **The readability evidence is mostly about perception.** Jones et al. 2003 (28
  readers): cleaned transcripts (punctuated, cased, disfluencies removed) were rated
  significantly less difficult, but comprehension and reading time did not differ
  measurably, and recognition errors mattered far more.
  [ISCA](https://www.isca-archive.org/eurospeech_2003/jones03_eurospeech.pdf)
  Morkes & Nielsen 1997 measured +47% usability for scannable web text (indirect).
  [NN/g](https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/)

Bristlenose already draws the right line: the transcript is the evidence and stays
verbatim; quotes are the edited form (`quote-extraction.md`: fillers become "...",
[clarifying words], no paraphrase). The readable layer should make the verbatim
easier to scan without becoming a second, edited transcript.

### 4.3 Options for a display layer

All of these leave `transcript_segments.text` and the word timings untouched.

| Option | Needs | What it does | Recommend |
|---|---|---|---|
| **Draw the text's spelling** | Deterministic; `transcript_layout.text_cut` already aligns drawn words to the text's words | Show the stored text's tokens, each carrying its word's timing, instead of Whisper's word strings. Casing and punctuation come from the text | **Yes**: the on-page fix for §1.4 |
| **Sentence-start capitals** | Deterministic; session language for `toLocaleUpperCase` | Capitalise a paragraph's first letter where a sentence begins (mockup option C) | **Built 8 Oct 2026** (`512f0846`) |
| **English "i" → "I"** | Deterministic, English only | Whisper's lower-case pronoun | Only if #1 is not done; after #1 it measured 0 |
| **Dim pure fillers** | Deterministic; a closed list per language | um, uh, er, erm, hmm (en); ähm, äh (de); euh (fr); えーと, えー (ja); 呃, 嗯 (zh). Back-channels ("uh-huh", "mm-hmm") stay at full strength | **Yes**, dimmed, not hidden by default |
| **Soft breaks inside a long paragraph** | Deterministic if punctuated | Extra space at a sentence end every ~60 words, inside one paragraph and one speaker badge | Only as a stopgap if stage 6 is not changed; #2 does it properly |
| **Hide-fillers toggle** ("verbatim / easier reading") | Deterministic | Hides the dimmed tokens; word timings unaffected | Perhaps later; an owner call whether two reading modes earn a control |
| **Ambiguous fillers** ("like", "you know", "I mean", "so") | An LLM or a trained classifier (smallest published ~1.3 MiB, English, Switchboard; [Rocholl et al. 2021](https://arxiv.org/abs/2104.10769)) | Mark them only where they are fillers | No: wrong marks are worse than none |
| **"Clean read" rewrite** | An LLM | A clean-verbatim version: repairs, false starts, grammar | **No.** A second transcript the researcher cannot check against the audio, and quotes already do this job |

---

## 5. Question 4 — languages

| | What breaks | What to do |
|---|---|---|
| **Wrong-language prompt** (MEASURED) | The English P2 prompt on a Japanese test recording (auto language) gave English hallucinations ("What do you think is the leading stage stage stage…", "nicely" dozens of times, "Ahh" fifty times) | Never prompt before the language is known; no prompt for a language without a reviewed one |
| **Japanese** (MEASURED) | Today's output on that recording has **no punctuation at all** (0 。, 0 、). With a Japanese prompt (えーと、はい。そうですね、それでは始めましょう。): 18 。, 38 、 and clean sentences | The per-language prompt works for ja |
| **No spaces (ja, zh; also th)** | A 60-*word* threshold is meaningless: Whisper's "words" here are single characters or morphemes (MEASURED: 私 は 臨 床 心 理 学 …). Sentence ends are 。？！ (Thai uses a space). The importer already compares CJK by characters (`_words_read_as`); Return cannot split a paragraph with no spaces (a known split limit) | Count characters for the stage-6 threshold; treat 。？！ as sentence ends; decide Thai separately |
| **No case (CJK, Arabic, Hebrew, Thai, Devanagari…)** | Sentence-start capitals do nothing, harmlessly | Nothing |
| **Turkish, Azerbaijani** | `toUpperCase("i")` gives "I", not "İ" | `toLocaleUpperCase(sessionLanguage)` (the mockup already says so). The English "i" pronoun rule must stay English-only |
| **German** | Nouns are capitalised mid-sentence, so lower-case-start heuristics read differently; ß upper-cases to SS | Only ever touch the first letter of a sentence; locale-aware upper-casing |
| **Right-to-left (ar, he, fa, ur)** | Sentence ends include ؟ and ۔; a continuation "…" (mockup option D) needs bidi isolation or it lands on the wrong side; dimming must not break Arabic shaping | `dir="auto"` per paragraph; add ؟ ۔ to the sentence-end set; test dimming on Arabic before shipping it there |
| **Fillers** | Every vendor's filler list is English-only (Descript, Deepgram, MAXQDA). Each language has a small core of pure vocalisations and an ambiguous tier (あの also means "that"; 那个/这个 are words) | Per-language lists of the pure core only, reviewed per language; no list, no dimming |

---

## 6. Not checked, or open

- Stage 5b was not re-run on the recommended Whisper output (its LLM pass may be a
  paid call), so "edges fixed by #1" is inferred from segment boundaries, not
  measured through speaker identification.
- faster-whisper was not run; the `hotwords` route is read from source only.
- large-v3 (non-turbo) and Chinese audio were not tested.
- The Japanese prompt was one run on one file.
- Whether the `(Speaker X)` prefix in stored text is drawn on the page when a
  paragraph has no word timings was not checked.
- Owner decisions: whether to offer a hide-fillers mode at all (§4.3); the stage-6
  threshold (60 words is grounded on two projects); which languages get a reviewed
  prompt first.

## 7. Reproducing the measurements

The scripts are in `experiments/transcript-readability/`, with a README naming the
inputs each one expects (copies of a project's database, intermediate JSON and
extracted audio, never the project folder itself). The method, in brief:

- **Style counts (§1.1)**: join each session's segment texts from
  `<output>/.bristlenose/intermediate/session_segments.json`; count tokens matching
  `^i('m|'ve|'d|'ll)?[.,?!]?$` by case, and runs of tokens between tokens ending in
  `.,?!;:`.
- **Paragraph table (§1.3)**: `transcript_segments` in a *copy* of
  `<output>/.bristlenose/bristlenose.db`, counting words after stripping
  `^\([^)]*\)\s*`.
- **Simulation (§3.2)**: raw segments sorted by start; speaker = the code of the
  latest existing paragraph starting at or before `start + 0.5 s`; then the merge
  rule with the extra conditions.
- **Whisper runs (§2.3)**: `mlx_whisper.transcribe` on a copy of the session's
  `s1_extracted.wav`, with the settings in the tables; the carried prompt is a copy of
  `mlx_whisper/transcribe.py` with L296 changed as quoted.
