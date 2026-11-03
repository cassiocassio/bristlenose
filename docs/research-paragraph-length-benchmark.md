# Paragraph length benchmark: words, sentences and clauses per paragraph

**Status:** research note, 3 Nov 2026. Numbers and method only; no article text is reproduced. It supports the line-break and "breathing marks" work in [design-quote-anchor.md](design-quote-anchor.md) §8 and §15 (phase 2): what is a natural length for a block of text, and how does that compare with the pieces a quote falls into between its cuts (`...`)?

**Provenance.** The three articles were pasted into the 3 Nov 2026 session by the owner, who chose them to span a low reading age (a UK tabloid) to a broadsheet. The reading-age description of the tabloid is the owner's, not measured here.

## 1. What was measured

| Outlet | Article (published) | Body paragraphs |
|---|---|---|
| The Sun | [Marco Pierre White slams Jamie Oliver](https://www.thesun.co.uk/tvandshowbiz/40892401/marco-pierre-white-slams-rival-jamie-oliver/) (3 Nov 2026) | 16 |
| The Guardian | [Hope Haven community mental health hub, Cumbria](https://www.theguardian.com/society/2026/nov/03/early-feedback-pilot-community-mental-health-hub-cumbria-whitehaven) (3 Nov 2026) | 18 |
| The New York Times | [Legacy of 2020 looms over Justice Dept.](https://www.nytimes.com/2026/11/02/us/politics/midterms-2020-election-justice-department.html) (2 Nov 2026) | 39 |

**What counts as a paragraph:** the article's own body paragraphs only. Headlines, standfirsts, captions, bylines, advertising and related-link blocks, the author bio and the helpline notice are left out.

**How each number was made:**
- **Words:** a regular expression over word characters and digits, after removing quotation marks and punctuation. A hyphenated word is one word; a number is one word.
- **Sentences:** a split on `.`, `?` or `!` followed by an optional closing quote and a capital, with a guard for abbreviations (Mr., Ms., Jr., initials, F.B.I., D.O.J., month abbreviations). A sentence inside a quotation counts, so a paragraph of speech can hold several.
- **Clauses:** **hand-counted finite clauses** (a clause with its own finite verb, including the speech verb in "he said"; non-finite participles and infinitives not counted). A judgement, not a parser. Done for the Sun and the Guardian only; not done for the NYT (39 paragraphs of judgement would add false precision).

## 2. Results

### 2.1 The Sun (16 paragraphs; Q = starts with a quotation mark)

| # | Words | Sentences | Clauses | Words per clause | |
|---|---|---|---|---|---|
| 1 | 26 | 1 | 3 | 8.7 | |
| 2 | 25 | 1 | 3 | 8.3 | |
| 3 | 32 | 1 | 3 | 10.7 | |
| 4 | 20 | 1 | 3 | 6.7 | |
| 5 | 44 | 5 | 7 | 6.3 | Q |
| 6 | 33 | 1 | 5 | 6.6 | |
| 7 | 13 | 1 | 2 | 6.5 | Q |
| 8 | 29 | 2 | 3 | 9.7 | Q |
| 9 | 35 | 3 | 6 | 5.8 | Q |
| 10 | 30 | 3 | 7 | 4.3 | |
| 11 | 32 | 1 | 3 | 10.7 | |
| 12 | 29 | 1 | 3 | 9.7 | |
| 13 | 16 | 1 | 2 | 8.0 | |
| 14 | 16 | 1 | 2 | 8.0 | |
| 15 | 17 | 1 | 3 | 5.7 | Q |
| 16 | 12 | 2 | 2 | 6.0 | Q |

Median **28 words** (interquartile range 17–32, range 12–44); **1 sentence** (range 1–5); **3 clauses** (range 2–7). Mean 15.7 words per sentence and 7.2 words per clause. Paragraphs 7 to 10 are one continuous spoken answer split into four: 13, 29, 35 and 30 words.

### 2.2 The Guardian (18 paragraphs)

| # | Words | Sentences | Clauses | Words per clause | |
|---|---|---|---|---|---|
| 1 | 45 | 4 | 5 | 9.0 | |
| 2 | 54 | 2 | 6 | 9.0 | |
| 3 | 49 | 1 | 6 | 8.2 | Q |
| 4 | 43 | 2 | 5 | 8.6 | |
| 5 | 49 | 3 | 5 | 9.8 | |
| 6 | 58 | 3 | 3 | 19.3 | |
| 7 | 67 | 2 | 3 | 22.3 | |
| 8 | 56 | 3 | 4 | 14.0 | |
| 9 | 60 | 3 | 5 | 12.0 | |
| 10 | 39 | 2 | 2 | 19.5 | |
| 11 | 42 | 1 | 4 | 10.5 | Q |
| 12 | 39 | 2 | 6 | 6.5 | |
| 13 | 65 | 5 | 7 | 9.3 | |
| 14 | 61 | 3 | 6 | 10.2 | Q |
| 15 | 66 | 4 | 7 | 9.4 | |
| 16 | 25 | 2 | 4 | 6.2 | Q |
| 17 | 36 | 2 | 5 | 7.2 | |
| 18 | 15 | 2 | 3 | 5.0 | Q |

Median **49 words** (range 15–67); **2 sentences** (range 1–5); **5 clauses**. Mean 18.9 words per sentence and 10.1 words per clause. The long words-per-clause figures in the factual paragraphs (6, 7, 10: 19 to 22) come from my count: those paragraphs are dense with non-finite and noun phrases, so they read as few clauses.

### 2.3 The New York Times (39 paragraphs; aggregates only)

The per-paragraph list was not saved from the session, so only the aggregates are recorded.

- Words per paragraph: median **40**, interquartile range 30–49, range 3–80.
- Sentences per paragraph: median **2**, range 1–4; **19 of 39** paragraphs are one sentence.
- Mean 23.8 words per sentence.
- 10 paragraphs start with a quotation mark: 24, 30, 35, 38, 39, 43, 44, 53, 56 and 59 words (median 41).
- Three paragraphs are 15 words or fewer: 12, 11 and **3 words** (a one-line paragraph used as a beat).

### 2.4 Side by side

| | Words per paragraph (median) | Range | Sentences per paragraph (median) | Words per sentence | Quote-led paragraphs: median (n) |
|---|---|---|---|---|---|
| The Sun | **28** | 12–44 | 1 | 15.7 | 23 (6) |
| The NYT | **40** | 3–80 | 2 | 23.8 | 41 (10) |
| The Guardian | **49** | 15–67 | 2 | 18.9 | 42 (5) |

"Quote-led" means the paragraph starts with a quotation mark, applied the same way to all three. A narrower reading of the Sun (only the four paragraphs of its one continuous spoken answer, 13, 29, 35 and 30 words) gives a median of 30. A session message reported that figure; it is not comparable with the other two rows, which is why this note uses the common rule.

## 3. What the benchmark shows

1. **The natural length of a paragraph of speech in print is about 25 to 45 words**, with the tabloid at the low end and the broadsheets at the high end. Between the Sun's 23 and the Guardian's 42 sits about **33**; the owner's guess (3 Nov 2026) is that user-research transcripts belong between the tabloid and the Guardian.
2. **There are two scales, not one.** The press paragraph (about 30 to 45 words) is a *thought*. Underneath it is a *phrase group* of about 7 to 11 words: print's words per clause (7.2 in the Sun, 10.1 in the Guardian), the pieces of a Talismanic quote between cuts (median 11 words), and the owner's hand-broken blocks in the IKEA quote (21, 11, 10 and 8 words, median 10.5). These match the two levels in the breathing-marks overlay: a line break between phrases, a half-line gap between thoughts.
3. **Spoken clauses are shorter than written ones.** In the Sun the clauses in the quoted speech run 4 to 6 words each, against 8 to 10 in the narration.
4. **A very short paragraph is a legitimate device.** The NYT's three-word paragraph is a deliberate beat. A minimum block length should be a soft default that other evidence can override, not a hard floor.
5. **Multi-paragraph quotation convention.** In the Sun and the Guardian, a quote that continues across paragraphs reopens the quotation mark at the start of each and closes only at the end of the last (the Sun's paragraphs 8 and 9, the Guardian's 13 and 14). This applies if a block is ever promoted to a full paragraph; a half-line gap inside one quote does not need it.

**Proposed defaults for the line-break lab (a hypothesis to test, not a result):** thought target about 35 words (range 20 to 50); phrase target about 10 words; minimum block length soft.

## 3a. Prior art: the Romans, and Jerome's sense-lines (searched 3 Nov 2026)

The owner's remark (3 Nov 2026) that a short block standing alone is good style, and that "the Romans knew that", points at a real tradition, and at direct prior art for this whole feature.

- **Layout *per cola et commata*.** Jerome set his Latin prophetic books out in sense-units, each starting on a new line, so that a reader could see where to pause and breathe when reading aloud. [Britannica](https://www.britannica.com/topic/per-cola-et-commata) describes it as a rhetorical system based on manuscripts of Demosthenes and Cicero, "especially designed to assist reading aloud"; [Jerome's preface to Isaiah](https://www.fourthcentury.com/?p=10916) says he applied the classical authors' arrangement to a new translation to ease reading; the [HMML lexicon](https://hmmlschool.org/lexicon/14667/) glosses it as breaking verses into separate lines by sense. One source says each unit was treated almost as "a minute paragraph". Another says Cassiodorus explained it as help for simple readers.
- **Three scales of unit.** The classical terms are *comma* (a short phrase), *colon* (a member, a longer unit) and *periodus* (a complete sentence of several of them), with the *pausa* between ([Colon (rhetoric)](https://en.wikipedia.org/wiki/Colon_(rhetoric)); a [medieval-writing overview](https://medievalwritings.atillo.com.au/literacy/reading2.htm) lists the periodus as consisting of several cola and commata). That is close to the two levels in the breathing-marks overlay: a line break between phrases, a half-line gap between thoughts.
- **What it does not settle.** Scholars disagree about whether Jerome's lines match the ancient rhetoricians' *cola* exactly, and the layout was placed by an editor's judgement of sense, which is the job an automatic placement has to do. The search found nothing specific on a one-unit line standing alone for emphasis; the owner's point is rhetorical practice, and the NYT's three-word paragraph (section 2.3) is the modern example.
- **Not searched:** the Greek and Latin treatises themselves (read only through translations and summaries, below), and modern sense-line editions.

### What the ancient rhetoricians say about the length of a unit

The Romans had no paragraph in our sense; the unit they measured was the **period** (Cicero's terms include *ambitus*, *circuitus*, *comprehensio*, *continuatio*). Searched 3 Nov 2026, through translations and secondary summaries, not the original texts:

- **Cicero: breath is the limit.** In *De Oratore* 3 he makes the largest period one that can be delivered in a single breath ([Watson's 1860 translation, 3.182](https://www.attalus.org/cicero/deoratore3C.html)). In *Orator* (section 222), as Quintilian reports it, the length is limited to about four verse-lines (translated variously as senarii or hexameters) *or* to what one breath can carry ([Quintilian 9.4](https://cts.perseids.org/read/latinLit/phi1002/phi001/perseus-eng2/9.4.123-9.4.130)). The *Orator* wording reaches us only through Quintilian's paraphrase and a translator's gloss.
- **The "four members" figure is Quintilian's observation, not Cicero's rule.** A period needs at least two cola; the usual number is about four, and often more. It describes practice, and breath and length are the prescriptive part.
- **Quintilian adds:** the period should complete the thought it expresses, be clear, and not be too long to hold in memory.
- **Aristotle, *Rhetoric* 3.9** ([text](https://www.technorhetoric.net/stasis/2017/honeycutt/aristotle/rhet3-9.html)): a period is complete in itself, divided into parts, and easily delivered in a single breath; its members and whole periods should be neither curt nor long. A member that is too short makes the listener stumble, still expecting the rhythm to go on; one that is too long leaves the hearer behind. One translation puts it as a portion of speech not too big to be taken in at a glance.
- **Demetrius, *On Style*** discusses the length of members and the number of members in a period ([Attalus](https://attalus.org/info/demetrius.html)). I found no source for a "four cola" limit in Demetrius; treat that as unverified.

**What this gives us:**
1. **Two criteria for the right length: breath and grasp.** Breath (what can be delivered at once) and closure (a complete thought, taken in at a glance, not left behind). Closure is the criterion for a thought block, and it is a semantic judgement, the model's job in the third tier.
2. **Too short is as bad as too long.** A very short unit makes a reader stumble waiting for the rhythm to resume, unless it is set apart on purpose, as in the NYT's three-word paragraph. This supports a soft floor on block length, not a hard one.
3. **A rough convergence, and only an inference.** Four verse-lines of 12 to 17 syllables is about 48 to 68 syllables, which at about 1.4 syllables per English word is roughly 35 to 50 words. That sits inside the press range for a paragraph of speech (23 to 49 words, section 2.4). A reading of the sources, not a finding: the translations disagree about senarii and hexameters, and the syllable and word conversion is mine.
4. **A hypothesis about "at a glance".** If grasp is about how much fits in one look, the target is a number of *lines*, not words. At about 11 words a line (the single column) that is a thought of about 3 to 4 lines, 33 to 44 words; at about 5 words a line (the card grid) the same 3 to 4 lines is 15 to 20 words. The lab can test whether the thought target should follow the layout's measure.

## 4. Related measurements on the Talismanic quotes (3 Nov 2026)

The Talismanic study's own 109 quotes, read read-only. Aggregates only.

- Quote length: median **57 words** (8 to 147). 62 quotes contain a cut (`...`).
- The 297 pieces between cuts: median **11 words**; 18% are 3 words or fewer; 28% are 5 words or fewer.
- **Breaking at every cut** (rough line counts, words divided by words per line): +5% taller at about 5 words a line (the card grid), +16% at about 11 words a line (single column). Concentrated in one participant: p1 +17% and +51%; p2 and p3 about +1% to +4% because they have few cuts. The most cuts in one quote: 16.
- **A length-balanced prototype** (dynamic programming over candidate break sites, an arbitrary target and a small cost per break; a prototype with arbitrary settings, not a result):

| Candidate sites | Target | Median blocks per quote | Blocks of 5 words or fewer | Quotes left unbroken | p2 quotes over 40 words left unbroken |
|---|---|---|---|---|---|
| cuts only | 12 to 20 | 1 | 1% | 58 to 65 of 109 | **15 of 20** |
| cuts + sentence ends + before *because / but / so / and / which* | 12 to 16 | 3 to 4 | 0% | 16 to 19 of 109 | **0 of 20** |

- **The IKEA quote** (owner's blocks 21, 11, 10, 8): cuts only at target 12 gives 7, 14, 8, 20; all sites at target 12 or 16 gives **20, 11, 18**, which reproduces the first two blocks and merges the last two. Those two were separated by a sentence end and a change of point, which length alone cannot see.

## 5. Limits

- **Three articles, one per outlet, all news.** News paragraphs are shaped by narrow columns and mobile reading; they are not a measure of how people read interview transcripts.
- **Paragraphs are an editorial convention**, and the sample mixes narration with speech.
- **Sentence and word counts are regular expressions**, spot-checked, not a parser. Clause counts are a hand count and a judgement.
- **The Talismanic measurements come from one study with three participants**, and the line counts are estimates that ignore half-line gaps.
- **Not searched:** readability research (reading-age formulas, line-length and paragraph-length studies), and any published benchmark for interview or oral-history transcripts.

## 6. Next steps

- Add spoken-word genres: published interview transcripts, podcast transcripts, oral-history transcripts, and transcripts a researcher has already tidied by hand.
- Save the per-paragraph vectors for every article (the NYT's were not kept) and put the counting functions in `experiments/line-break-lab/`.
- Measure how a researcher's own breaks distribute against these scales on more than one quote (the lab's ground-truth set).
