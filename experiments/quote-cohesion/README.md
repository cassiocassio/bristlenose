# Quote-cohesion lab

Does stage 9 cut one passage into one quote, or into a quote per line? Built 21 Nov 2026,
after project-ikea's quotes came back fragmented on ChatGPT. One p2 paragraph was split
into four quotes in the transcript, and the Quotes view had no quote long enough to break
into paragraphs.

A quote is meant to be one passage on one point, of one or more paragraphs, with filler cut
to `...`. The report breaks long quotes into readable paragraphs itself (`breakIntoBlocks`,
`frontend/src/utils/breakParagraphs.ts`). That only shows on quotes of about 50 words or
more, so a run of 15-word quotes looks like a list of fragments.

## What is here

| Path | What it is |
|---|---|
| `fixture/transcripts/s1.txt` | Synthetic think-aloud session: one participant buys a kettle on a made-up shop site. 24 lines, 4 tasks, no researcher turns. No real person's words. |
| `fixture/topic_boundaries.json` | The topic map stage 8 would give it: one boundary per task. |
| `fixture/tasks.json` | The expected task boundaries, in seconds, and the cap of 3 quotes per task. |
| `score.py` | Scorer. Fragmentation for any study, plus task cohesion where a `tasks.json` exists. No network. |
| `run.py` | Harness. Runs the real `extract_quotes` with a chosen provider, model and prompt. **Paid.** |
| `results/` | The eight synthetic runs scored below: prompt 0.2.0 and 0.3.0, two each per provider. |

## Running it

```bash
cd experiments/quote-cohesion
../../.venv/bin/python score.py fixture results/*.json
```

Scoring is free. A new run costs about a cent on the fixture:

```bash
cd experiments/quote-cohesion
../../.venv/bin/python run.py --provider openai --out results/v0.3.0-openai-3.json
```

By default the harness uses the repo's prompt as it stands. `--prompt <file.md>` runs any
other version of the quote-extraction prompt, such as an archived one from
`bristlenose/llm/prompts-archive/` or a draft: it copies the repo prompts to a temporary
folder and puts that file in place of `quote-extraction.md`, so only quote extraction changes. To run a real study, give `--study` a folder holding `transcripts/*.txt` and
`topic_boundaries.json`, copied from a project's `transcripts-raw/` and
`.bristlenose/intermediate/`. Pass an `--out` outside this folder: the harness refuses to
write a real study's quotes into the public tree.

## What the scorer measures

- **Same-topic touching pairs.** Two quotes from the same speaker whose source passages sit
  side by side, with at most 4 participant words between them and no researcher words, under
  the same topic label. Each one is a passage cut in two. Some are expected on think-aloud with
  no researcher (the 2–3 quotes allowed in one task touch each other), so read this one
  against prompt 0.2.0 rather than against zero.
- **Coverage.** The share of participant words inside some quote's `verbatim_excerpt`. A fix
  for fragmentation must not get there by dropping material.
- **Task cohesion** (fixture only). Quotes per task, quotes whose time span crosses into a
  second task, and tasks with no quote. **PASS** means every task is quoted, none has more
  than 3 quotes, and none is crossed.

## Results

### Synthetic fixture

| Run | Quotes | Median words | Per task | Crossing | Coverage | Verdict |
|---|---|---|---|---|---|---|
| 0.2.0, ChatGPT ×2 | 24, 24 | 13, 13 | 6·6·6·6 both | 0 | 1.00, 0.99 | FAIL, FAIL |
| 0.2.0, Claude ×2 | 24, 13 | 12.5, 22 | 6·6·6·6, 3·3·3·4 | 0 | 0.99 | FAIL, FAIL |
| 0.3.0, ChatGPT ×2 | 8, 9 | 42.5, 37 | 2·2·2·2, 2·3·2·2 | 0 | 1.00 | PASS, PASS |
| 0.3.0, Claude ×2 | 10, 11 | 28, 29 | 3·2·2·3, 3·3·2·3 | 0 | 0.99 | PASS, PASS |

Prompt 0.2.0 gave exactly one quote per transcript line in three runs of four: 24
quotes from 24 lines. 0.3.0 gave 2–3 quotes per task on both providers, without crossing a task
or losing coverage.

### Real studies (scored outside the tree)

Measured with the same scorer on copies of two projects. The quotes themselves are kept out
of this folder, so only the counts are here. Medians are in words; each 0.3.0 cell is two runs.

| Study, provider | 0.2.0: quotes / median / same-topic touching / coverage | 0.3.0 |
|---|---|---|
| project-ikea, ChatGPT | 42 / 16 / 19 / 0.84 | 21 / 37 / 5 / 0.83 and 18 / 42 / 3 / 0.83 |
| project-ikea, Claude | 22 / 35 / 5 / 0.87 | 20 / 37 / 6 / 0.90 and 20 / 37 / 5 / 0.88 |
| Talismanic, ChatGPT | 89 / 48 / 22 / 0.83 | 73 / 66 and 71 / 54 |
| Talismanic, Claude | 112 / 57 / 34 / 0.83 | 82 / 75 and 70 / 89 |

On think-aloud (IKEA) 0.3.0 brings ChatGPT up to Claude. On interviews (Talismanic) it gives
25–35% fewer, longer quotes on both providers. Claude's p90 under 0.3.0 was 120 and 145 words,
and its longest quote 213. That's the trade-off still open: fewer, larger pieces
of evidence for Signals and themes.

A V2 with no length range was tried and dropped: Claude's Talismanic median went to 104, p90
to 242, max to 351.

## Why it happened

- **30 Jan / 19 Feb 2026.** Rules 6 and 7 were written: "typically 1-5 sentences", "split long
  monologues", "bundle short navigational sequences". Unchanged until this lab.
- **June to October.** IKEA was already short on gpt-4o (median 12–13) and on Claude (18–27).
- **11–12 Oct.** Stage 6's 60-word sentence-end rule. IKEA session 2 went from 43 paragraphs
  to 9, so a line-anchored extraction now had fewer, longer lines to cut.
- **3–5 Nov.** Quote cards learned to break long quotes into paragraphs. The prompt still asked
  for 1–5 sentences.
- **11 Nov.** project-ikea was reprocessed on ChatGPT (gpt-5.6-terra) for the first time: 42
  quotes, median 16, none long enough to break.

The cause is the model and the content together. ChatGPT reads "1-5 sentences" literally and
anchors quotes to transcript lines, and think-aloud is many short lines on one point. Claude
mostly ignored the cap.

## The 0.3.0 change (landed 21 Nov 2026)

Rule 6 replaces "Bundle short navigational sequences into a single quote" with: keep narration
together with the reactions around it while the participant stays on one task or screen, and
never make a quote per action, per item read out or per passing remark.

Rule 7 becomes: a quote is one passage on one point, for as long as the participant stays on
it. It may run to several paragraphs, because the report lays it out. Start a new quote at a
new point, task or screen, or at a researcher's question. Most quotes are 20–120 words; past
that, split where the reasoning turns.

Full text: `bristlenose/llm/prompts/quote-extraction.md`. The previous version is
`bristlenose/llm/prompts-archive/prompts_2026-11-21_quote-extraction-v0.2.0-one-to-five-sentences.md`.

## Tests

- `tests/test_quote_cohesion_scorer.py` (free) pins the scorer on hand-made quotes and on the
  eight saved runs: 0.2.0 fails all four, 0.3.0 passes all four. Each of its checks was mutated
  out once to make sure a test fails.
- `tests/test_quote_cohesion_live.py` (paid, `-m slow`) runs stage 9 on the fixture for Claude
  and for ChatGPT, about a cent each, and asserts the PASS verdict and coverage of at least 0.9.
  It skips, saying it never ran, for a provider with no key, no credit or no service. On 21 Nov
  it passed on 0.3.0 (Claude and ChatGPT), and failed on the archived 0.2.0 (17 quotes, per task
  3·4·5·5; 23 quotes, 6·5·6·6). No free test can check the prompt's wording.

## Known limits

- A prompt change reaches only new sessions and studies. The quote cache key
  (`_quote_session_fps`, `pipeline.py`) holds the transcript and topic map, not the prompt or
  model, so an existing project keeps its old quotes until it is re-analysed.
- On long paragraphs ChatGPT stamps several quotes with the paragraph's start time, which moves
  where jump-to-time lands. Seen, not fixed.
