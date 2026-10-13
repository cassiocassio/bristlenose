---
status: partial
date: 12 Oct 2026
last-trued: 2026-10-13
trued-against: HEAD@main on 2026-10-13
---

# Whisper style prompts for every language: brief

## Changelog

- _2026-10-13_ — trued up: batch 1 shipped (es, fr, it, de; pt held), the
  skipped-window net, the inaudible marker and loop removal recorded with the
  batch 1b evidence the code cites; pre-net reading kept below as the baseline.
  Anchors: `transcribe: style prompts for spanish, french, italian and german`,
  `transcribe: re-decode speech whisper skipped`, `inaudible segments: a gap where
  nothing was heard is data, not text`, `transcribe: remove whisper repetition loops
  spread across segments`.
- _2026-10-12_ — initial brief, batch 1 research and trials.

## Why

Since `f1ad0a4b` (0.37.0) every Whisper window gets a short punctuated "style prompt",
which stops Whisper slipping into lower-case, unpunctuated text on conversational speech
(`docs/design-transcript-readability.md` §8). It shipped for **English and Japanese**
only, because those were the only recordings we could measure on. Since 13 Oct 2026
Spanish, French, Italian and German have one too (§ Batch 1 as shipped); every other
language transcribes as before, unmeasured.

A prompt cannot be added blind. Two failures were seen in testing: an English prompt on
Japanese audio produced English loops, and a prompt containing an interview phrase
replaced a moderator's words with the prompt. So each language needs its own prompt,
written to that language's conventions and measured on real speech before it ships.

## Goal

For each of our 21 interface languages: a measured prompt or a measured "no prompt",
backed by public-domain (or openly licensed) conversational recordings, a before/after
comparison the owner can read, and a cited account of that language's punctuation and
filler conventions.

## Scope and batches

Whisper codes in brackets. Portuguese is one Whisper language for both locales, so test
both accents. Norwegian Bokmål is Whisper `no`.

| Batch | Languages | Why first |
|---|---|---|
| 1 | Spanish (es), French (fr), German (de), Italian (it), Portuguese (pt: Brazil and Portugal) | The largest European research markets we serve; the owner reads them |
| 2 | Dutch (nl), Catalan (ca), Czech (cs), Polish (pl), Swedish (sv) | |
| 3 | Danish (da), Norwegian (no), Finnish (fi), Turkish (tr), Russian (ru), Ukrainian (uk) | |
| 4 | Korean (ko) | Spaced Hangul; check the paragraph rule's counting too |
| — | Chinese (zh) | Held: the prompt's script picks Simplified or Traditional output. Owner decision first |

## Method, per batch

1. **Research** (prompt below): candidate recordings with verified licences, plus
   punctuation and filler conventions with sources. No downloads.
2. **Approval**: the owner sees the candidate list (file, source, licence, size) and
   approves downloads. Files go to the gitignored trial-run folder, never the repo.
3. **Prompt per language**: fillers in (spelled as that language's transcription
   conventions spell them), assent and hesitation only, nothing a moderator would say,
   the language's own punctuation (`¿¡` in Spanish, French spacing where it matters).
4. **Trial**: each recording transcribed twice through the shipped code path (no prompt,
   prompt), seeded so each run is repeatable. Measured: sentence ends, words per
   sentence, longest unpunctuated run, lower-case sentence starts, fallback windows, prompt
   echoes, repetition loops, detected language, word count change (are fillers dropped?).
5. **Eyeball**: a side-by-side page per batch, today against the prompt, in the
   transcript page's own typography, with the measured numbers above each pair.
6. **Decision**: a language gets its prompt only if it improves the numbers and the owner
   finds nothing wrong on the page. Otherwise it stays unprompted, and that is recorded.

## Acceptance for a language's prompt

- More sentence ends and a shorter longest unpunctuated run than no prompt, on every
  sample.
- No prompt echo, no new repetition loop, the same detected language.
- Word count within a few percent of no prompt, or higher. A large drop means Whisper is
  discarding speech.
- The owner has read the comparison page.

## Download safety

Recordings come from the public internet, so they are treated as untrusted input. Every
download goes through `experiments/transcript-readability/fetch_samples.py`, which reads
the owner-approved list:

- **HTTPS only, from the approved list's own hosts.** Each redirect hop is checked
  against them, so a link cannot bounce elsewhere.
- **A size cap (400 MB) and timeouts.** The file streams to a `.part` file and is renamed
  only when complete.
- **Content check.** The first bytes must be a known audio or video container (MP3, Ogg,
  FLAC, WAV, MP4, WebM or Matroska). Anything else is deleted, and nothing is unpacked.
- **Contained parsing.** ffprobe and ffmpeg, the only tools that read the media, run under
  macOS `sandbox-exec` with network access denied and `-protocol_whitelist file`, so a
  crafted file cannot make them fetch URLs or read other local files.
- **One plain WAV per file** (16 kHz mono), converted once. Only the WAV reaches Whisper,
  and nothing is opened in a GUI app.
- **Never committed.** The destination must be gitignored or the script stops. Files are
  written 0644, and `manifest.json` records URL, licence, size and SHA-256.

Checked 12 Oct 2026: a plain-HTTP URL, a host outside the allowlist and an HTML page
posing as a recording were all refused. ffmpeg runs under the sandbox, and a network
call made from inside it fails.

## Risks

- **Read speech is not interview speech.** Audiobooks and dictation are already
  punctuated well; the failure shows on filler-heavy conversation. Prefer interviews and
  oral history; label anything read as such and weigh it less.
- **Licences.** Public domain or CC0 first. CC BY is acceptable for local testing with
  the attribution recorded. Nothing downloaded goes into git.
- **Seeds hide variance.** One seeded run per condition is repeatable but is one sample.
  Use two or more recordings per language, and three seeds on any borderline result.
- **The prompt can teach the wrong spelling of fillers.** Spell them from the cited
  conventions, not from English habits.

## The research prompt

### Draft 1

> Find public-domain spoken-word recordings in Spanish, French, German, Italian and
> Portuguese that we can use to test Whisper transcription. Also find guides to correct
> punctuation for each language. Give links.

### What was wrong with draft 1

1. It doesn't say **conversational**. Read speech (LibriVox, Common Voice) would dominate
   the results and is the case that already works.
2. **No length, format or size bounds.** We need a single file of 5–30 minutes that ffmpeg
   reads, ideally under 200 MB, and a direct URL that is not a streaming page.
3. **No licence evidence.** "Public domain" claims on aggregator pages are often wrong. We
   need the page that states the licence, and the exact licence.
4. **It invites downloading.** Downloads need the owner's approval, file by file.
5. **No output shape.** Results from five languages have to be comparable and become a
   download list.
6. **Punctuation guides were too vague.** We need the authority each language's writers
   actually defer to, plus that language's transcription conventions for fillers. The
   prompt is built from fillers, and spelling them wrong teaches Whisper the wrong form.
7. **Nothing on what to exclude**: music-heavy audio, heavy overlap, a single speaker
   reading, sensitive personal data, YouTube (its terms forbid downloading).
8. **No stopping rule**, so it would either stop at one hit or never stop.

### Final prompt (sent for batch 1)

> You are researching test material for speech transcription. **Do not download any media
> file.** You may fetch web pages and send HEAD requests to read a file's size and type.
>
> **Languages (batch 1):** Spanish, French, German, Italian, Portuguese (find at least one
> Brazilian and one European Portuguese recording).
>
> **Part A: recordings.** For each language find **3 candidates**, ideally 4, of
> *conversational* speech:
> - Interviews, oral histories, panel discussions or podcasts with **at least two
>   speakers**, and spontaneous speech with hesitations ("um" equivalents). Read speech
>   (audiobooks, Common Voice, news read from a script, speeches) is a last resort.
>   Include it only if nothing else exists, and label it READ.
> - **Length 5–30 minutes** (one longer recording is fine if its first 15 minutes stand
>   alone). Audio or video in a format ffmpeg reads (mp3, ogg/opus, wav, flac, m4a, mp4,
>   webm). A **direct file URL**, under about 300 MB. Not YouTube, Vimeo or any page that
>   only streams.
> - **Licence:** public domain or CC0 preferred. CC BY or CC BY-SA acceptable. No
>   NonCommercial or NoDerivs unless nothing else exists, and then label it. Give the URL
>   of the page that **states** the licence. An aggregator's claim is not enough when the
>   source page says otherwise.
> - Avoid music beds, heavy crosstalk, poor phone audio, and any recording centred on
>   private individuals' sensitive personal data (health, legal cases).
> - Good places to start (verify each item's own licence): Wikimedia Commons (audio and
>   video categories for spoken word, interviews and oral history in each language),
>   Internet Archive collections with stated CC licences, national and EU institutional
>   archives that publish under open licences, university oral-history archives with CC
>   licences, and public-sector podcasts under open licences.
>
> Return a table per language with these columns: title; direct file URL; licence (exact)
> and licence page URL; duration; size (from HEAD) and format; speakers (count, and
> whether there is an interviewer); type (INTERVIEW, ORAL HISTORY, PANEL, PODCAST or
> READ); accent or region; audio quality (your judgement from any description); and one
> line on why it suits the test. Mark your top 2 per language.
>
> **Part B: conventions, per language, with sources.**
> 1. The punctuation authority writers actually follow, with a link: Spanish RAE
>    *Ortografía*; French, the Imprimerie nationale's *Lexique* and the Académie; German,
>    Duden; Italian, a standard reference such as Treccani or Accademia della Crusca;
>    Portuguese, the Acordo Ortográfico plus Brazilian and European references. Name the
>    rules that matter for transcripts: sentence-final marks (Spanish inverted `¿ ¡`),
>    spacing before `? ! : ;` (French), capitalisation (German nouns), the comma before
>    subordinate clauses (German *dass*), quotation marks (« », „ “, “ ”), ellipsis, and
>    the dash for interruptions.
> 2. **Fillers and hesitations as transcription conventions spell them** (for example the
>    German GAT2 conventions, or the conventions of French, Spanish and Italian
>    conversation corpora). List the 4–6 most common pure hesitation and backchannel
>    forms, spelled as those conventions spell them, with a source. Mark which are
>    ambiguous with real words.
> 3. Whether Whisper is known to produce the inverted Spanish marks or French
>    non-breaking spaces. Cite issues or papers if you find them; say so if you don't.
>
> **Stop** when each language has 3 good candidates and Part B is complete, or after a
> thorough search. Say plainly where you could not find enough, and what you tried.
> Label every claim VERIFIED (you read the source page) or REPORTED (secondary). Keep
> the whole answer under about 2,500 words.

## Batch 1 findings (12 Oct 2026)

**Recordings.** Every candidate is on Wikimedia Commons. Licences are VERIFIED from
each file's own page and sizes by HEAD; speaker counts are inferred from descriptions.
At least three conversational candidates per language, all interviews, oral histories,
panels or podcasts: Castilian oral history and a Spanish podcast; Paris and Alsace
interviews; Bavarian and Swabian radio interviews; Italian radio and panel; and a São
Paulo community interview for Portuguese. **European Portuguese is thin:** the only
recording made in Portugal is a low-bitrate association meeting. The fallbacks are a
Portuguese guest on Brazilian TV and an Angolan speaker. The candidate list, with URLs,
lives in the trial folder's approved list, not here.

**Punctuation authorities and transcript-relevant rules:**

| Language | Authority | Rules that matter |
|---|---|---|
| Spanish | RAE, *Ortografía* (2010), *DPD* | `¿ ¡` open every question and exclamation, even mid-sentence; « » then “ ”; ellipsis has no space before |
| French | Imprimerie nationale, *Lexique* (2002) | Narrow no-break space before `; ! ?`, no-break space before `:` and inside « » (not in Québec, varies in Switzerland) |
| German | Duden | Comma before every subordinate clause (D 118, VERIFIED); „ “; nouns capitalised |
| Italian | Accademia della Crusca | « » and “ ” interchangeable; no comma before a restrictive *che* |
| Portuguese | Acordo Ortográfico (spelling only); Ciberdúvidas | « » in Portugal, “ ” in Brazil; travessão (—) for dialogue |

**Fillers, as conversation corpora spell them** (VERIFIED from each convention):

| Language | Hesitation | Backchannel | Source | Collides with a word |
|---|---|---|---|---|
| German | äh, ähm, öh | hm, ja | GAT 2 | GAT 2 warns against *eh* |
| French | euh, hum | mh, hein, ouais | Rhapsodie | ben, bah, hein |
| Spanish | eeh, mm | uhum | PRESEEA | eh, pues, este |
| Italian | ehm, eh | mh | KIParla | eh sits next to *è* |
| Portuguese (BR) | ahn, hum | hum hum, né | C-ORAL-BRASIL | eh / é |

**What a prompt cannot do (VERIFIED in openai-whisper's `tokenizer.py`,
`non_speech_tokens`):** by default Whisper suppresses `:` and `;` written with a leading
space, straight double quotes, `<<`, `>>` and a word-initial hyphen. So French spacing
before `: ;` cannot be prompted into the output. If wanted, it would be a display
transformation. `? ! « » ¿ ¡ —` are not suppressed. Whether Whisper writes the opening
`¿ ¡` was measured in the trial: Whisper writes them with or without a prompt (55 in
es-1 with none).

## Batch 1 trial results (12 Oct 2026)

Twelve Wikimedia Commons recordings (2–3 per language, 12–28 min each), each transcribed
through the shipped mlx path with no prompt, with prompt v1 and (es, pt, it, fr) with
prompt v2. Seeded, so each run is repeatable. "Vanished" counts 30-second blocks where
the no-prompt run heard 20 or more words and the prompted run kept under a quarter of
them. Each one was checked by reading it, and they are real speech that was skipped, not
loops that were removed.

| Language | Prompt | Effect | Vanished blocks |
|---|---|---|---|
| German | v1 `Ähm, ja. Also, ich denke schon, äh, und dann? Genau.` | Longest unpunctuated run 78 → 39 (de-2); hesitations kept (0 → 21 *äh* in de-1) | 0 and 1 |
| French | v1 `Euh, bon. Oui, je pense, hein, et alors ? D'accord.` | Commas nearly double, full stops barely move: comma-chained sentences | 0, 0 |
| French | **v2** `Euh, bon, je pense que oui. Mais ça dépend, hein. Et alors ? Je ne sais pas trop.` | Full stops 73 → 125 and 242 → 331; words per sentence 23.3 → 15.5 | **0, 0** |
| Italian | v1 `Ehm, sì. Allora, penso di sì, eh, e poi? Esatto.` | Words per sentence 38.9 → 25.5 | 1, 2 |
| Italian | **v2** `Ehm, allora, mh, in realtà sì, no? Eh, più o meno, perché, ehm, dipende.` | Words per sentence 38.9 → 27.8, longest run 136 → 29 | **0, 0** |
| Spanish | v1 `Eeh, bueno. Sí, claro, mm, ¿y entonces? Vale.` | Better punctuation, but speech skipped and replaced by prompt words ("Vale.") | 8, 7, 3 |
| Spanish | v2 `Eeh, pues, mm, la verdad es que sí, ¿no? Eh, más o menos, porque, mm, depende.` | Podcast fixed (7 → 0, words 3,148 → 3,458); speech still skipped elsewhere | 18, 0, 5 |
| Portuguese | v1 `Ahn, é. Então, acho que sim, né, e depois? Certo.` | 278 words at 8:00 in pt-br-1 came back as "Certo." | 5, 1, 0 |
| Portuguese | v2 `Ahn, então, hum, na verdade é isso, né? Eh, mais ou menos, porque, ahn, depende.` | Fewer skips | 3, 2, 0 |

> **Superseded on 13 Oct 2026** by § Batch 1 as shipped. The reading and the net
> paragraph below are the 12 Oct baseline, kept as the record of why the net was built.

**Reading.** German, French v2 and Italian v2 lose no speech and are candidates to ship,
subject to the owner's reading of the comparison page. Spanish and Portuguese skip
windows with either prompt. One example: a clear 71-word passage at the start of es-3
came back as "Gracias." That is a Whisper behaviour under a prompt (a skipped window
filled with a word or two), not only a matter of the prompt's wording. Spanish was also
already reasonably punctuated without a prompt (55 opening `¿ ¡` in es-1).

**What would make Spanish and Portuguese safe: a skipped-window net.** We already measure
the audio level every 100 ms. A 30-second stretch with clear signal but almost no text
is a skipped window, and stage 5 can re-transcribe just that stretch without the prompt.
The same check catches skips with no prompt at all. Unbuilt; it would need its own
measurement.

The comparison page (`trial-runs/whisper-prompt-samples/compare.html`, built by
`compare_prompts.py`) stays out of the repo because it holds interview transcripts.

## Batch 1 as shipped (12–13 Oct 2026)

**Batch 1b.** Eight harder recordings were added to the twelve, chosen for informal
talk, crosstalk, background noise and accents: an Austrian community-radio interview
(de-3), a Portuguese street recording (pt-pt-2), an Italian field recording (it-3), two
French corpus recordings, a family meal and a conversation (fr-3, fr-4, ESLO and OFROM,
CC BY-NC-SA), a Spanish soundscape (es-4), and two covertly recorded Spanish
conversations from the Ameresco corpus (es-5, es-6, CC BY-NC-SA), which come with
reference transcripts. The owner judged the spoken Spanish ones extreme, at the far edge
of what research recordings look like, and they are used as stress tests, not as the
yardstick.

**Word error rate against the Ameresco references** (`experiments/transcript-readability/score_wer.py`;
the references' conversation-analysis markup stripped, overlapping speech kept, so the
score counts what crosstalk loses; numbers in digits cost every condition alike):

| Recording | No prompt | Prompt v2 | v2 + net |
|---|---|---|---|
| es-5 (25 min) | 42.7% | 35.7% | 35.7% |
| es-6 (24 min) | 58.4% | 42.9% | 42.0% |

**What shipped** (`STYLE_PROMPTS` in `bristlenose/stages/s05_transcribe.py`): v2 for
Spanish, French and Italian, v1 for German, measured over the sixteen recordings in those
four languages. Language names (`--whisper-language French`) reach the same prompt as the
code. Measured on mlx only; faster-whisper gets the same prompts as `hotwords`, unmeasured
for these languages.

**Portuguese followed the same day.** It was held at first because pieces of its prompt
came back over speech, but nearly all of that came from pt-pt-2, a street recording
Whisper hears 73 words of in 17 minutes without any prompt, and the inaudible marker
now handles exactly that echo. On the three interviews, with the prompt and every net:
sentences 142 → 181 (pt-br-1), 188 → 202 (pt-pt-1), 94 → 96 (pt-ao-1); longest
unpunctuated run 80 → 22, 58 → 47, 37 → 30; speech blocks lost 1, 0, 0 (es-1, shipped,
loses 9). Its fillers sound Brazilian ("né", "ahn") and Whisper has one code for both
varieties, so European Portuguese gains least; a variant is worth trying if a
Portugal-based user turns up.

**The skipped-window net, as built** (not as planned above). A stretch of at least 8 s
with fewer than 0.3 words a second, where at least 40% of the 100 ms windows sit 15 dB
above the recording's noise floor (its quietest tenth, capped at -45 dBFS so a file loud
throughout is not blind), is re-decoded on its own without the prompt, and the new text
replaces the old only at 1 word a second or more, so the net can only add speech. It
fires with no prompt too: a Portugal meeting, an Italian and a German interview and a
Mexican podcast each lost a stretch that another run heard. On es-1 it recovered 1,073
words; sound with no words went from 8:09 to 2:47.

**The inaudible marker.** Whisper also hands back *pieces* of its prompt over speech it
cannot make out ("Ainda, hum, na verdade.", "Ehm, allora, mh, in realtà sì, no?"). A line
of two or more words, at least 60% of them prompt words, with a mean word confidence
under 0.15 becomes an inaudible gap: empty text, Whisper's guess discarded, drawn in the
report as a muted "Inaudible", never as words. Calibrated on seven recordings in six
languages (pt-pt-2, it-3, es-1, es-6, fr-3, de-3 and an English interview): every line
under 0.15 was a partial echo, and real speech made of the same words sat far above it
("Ähm, genau." at 0.75, "Okay. Uh, right." at 0.97). On the twenty trial recordings it
marked 13 gaps (146 s) in pt-pt-2, 4 (46 s) in it-3 and one short line each in es-1 and
fr-3; nothing else. Prompt words alone, or low confidence alone, are ordinary speech, so
both are required.

**Repetition loops.** Whisper can loop across many separate one-line segments ("nada" 39
times in 28 s, "Gracias." every 30 s for a minute), which the within-segment repeat
filter never sees, and which the net read as speech. A run of consecutive segments with
the same text (compared after repeats collapse) is removed when it is 8 or more long, or
3 or more spanning at least 15 s. Pairs are left alone (202 in the trials, many real),
and tight bursts of real backchannel ("Sim." four times in 2.4 s, "¡No!" six times in
6 s) stay. On the twenty recordings it fired on es-1, es-4 and pt-pt-2 only. It took
four rounds on es-1, because the loop survived three ways: inside the net's own
re-decode, as lines that differ only in doubled words, and split by a line a later gate
drops.

**Order of the gates in stage 5**, and why: signal gate, then whole-prompt echoes, then
loops, so that what the net sees is the transcript the reader will get (a removed echo
or loop reads as the gap it is and is re-decoded); then the skipped-window net, which
drops loops from its own re-decodes before judging them; then the inaudible marker, so
a line the net replaced is judged on its new text; then one more loop check on the
finished transcript. The reference description is `bristlenose/stages/CLAUDE.md` § Stage 5.

**What the trials left open.** A European Portuguese variant; a clean whole-file timing of the
net; batches 2–4; and the diagnostics row and opt-in telemetry
(`docs/design-transcription-quality.md`).

## Status

- 13 Oct 2026: batch 1 shipped for es, fr, it and de, then pt once the nets were in. The net, the inaudible
  marker and loop removal shipped with it (§ Batch 1 as shipped).
- 12 Oct 2026: brief written; batch 1 researched, downloaded (12 files, approved), trialled with v1 and v2 (above). Awaiting the owner's reading of the comparison page.
