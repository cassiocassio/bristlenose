# Codebook corpora — real participant speech, openly licensed (E2)

Real think-aloud transcripts for testing codebook wording against speech
nobody wrote to fit it. These are **evidence class E2** in the decision
registers (`docs/design-codebook-norman.md` § Evidence policy): public,
cited by URL, committed here because the licence allows it. Two other
corpora used in the same work are **not** here: Steve Krug's *Rocket Surgery
Made Easy* demo test (publicly posted, no stated licence — local only) and
our own project databases (E3 — never committed; a synthetic twin goes in
the golden fixture instead).

None of this is a golden set. No file here carries an `accept` list. They
are for measuring what a wording change *moves* on real speech (run the
same quotes through two versions and diff), and for the noise floor: two
runs of the identical codebook over the Wikipedia quotes agreed on most
tags but not all, so a change that moves one or two quotes is unproven.

## Files

| File | What | Licence | Attribution |
|---|---|---|---|
| `wikipedia-editing-usability-2009-highlights.txt` | Four highlight reels from the Wikimedia Foundation's March 2009 *Usability and Experience Study*: new editors thinking aloud while trying to edit in the MonoBook editor. **Transcribed locally with Whisper** from the CC-licensed `.ogv` clips on Commons; no published transcript exists, so expect ASR errors and no speaker labels. | **CC BY-SA 3.0** — the transcript is a derivative of CC BY-SA video and is licensed the same | Wikimedia Foundation; clip URLs inline |
| `wikipedia-editing-2009.quotes.txt` | The above, sentence-grouped into 52 quote-sized chunks (~45 words) for the harness | CC BY-SA 3.0 | as above |
| `instagram-feed-think-aloud-2022.txt` | Concurrent and retrospective think-aloud, ~18 pseudonymised participants browsing their own Instagram feed for five minutes. `Image description:` lines are researcher annotations, not speech. | **CC BY 4.0** | Davies, Turner & Udell, University of Portsmouth, 2022. Figshare 21195811 |
| `instagram-fitspiration-think-aloud-2022.txt` | Same study, twenty fixed "fitspiration" posts, per-image think-aloud | CC BY 4.0 | as above |
| `instagram-feed-2022.sample40.quotes.txt` | Forty participant lines of at least twelve words, drawn with `random.seed(7)` from the feed transcript, `Image description:` lines excluded — the sample the Norman register's Instagram numbers come from | CC BY 4.0 | as above |

Each transcript opens with a three-line header (source URL, licence, one-line
description) that travels with the file.

## Why Instagram, which is browsing and not a task

Because it is the control. A designed product, real speech, and almost
nothing a Norman tag should fire on: the right result is a median
confidence near 0.10 with nothing above the accept line, and the Norman
register records exactly that for five versions. A codebook that surfaces
"findings" here is over-reaching. It also exposes the placeholder tag the
shared autocode prompt forces onto out-of-scope quotes (register N-18),
which moves with wording that has nothing to do with these quotes.

## Running them

```bash
.venv/bin/python scripts/codebook-harness.py norman tests/fixtures/codebook-corpora/wikipedia-editing-2009.quotes.txt /tmp/wiki-a.json
```

then the same with a draft YAML as the first argument, and
`scripts/codebook-harness.py --compare /tmp/wiki-a.json /tmp/wiki-b.json`.
Paid: one LLM call per 25 quotes.

## What is still wanted

Task-driven sessions on more products, physical ones especially, and our
own moderated sessions run through the real pipeline so the quotes arrive
the way AutoCode receives them rather than chunked by word count. The
register's closing section lists what to collect first.
