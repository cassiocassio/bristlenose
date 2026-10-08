# Paragraph case — rule C on real transcripts

Before building option C of `docs/mockups/transcript-paragraph-capitalisation.html`
(a paragraph's first letter drawn as a capital where a sentence begins), run it
over every trial run and look at what it does.

    .venv/bin/python experiments/paragraph-case/measure.py <scratch-dir> [project ...]

It copies each project (no media) into the scratch dir, imports it with serve
in-process, and reads `GET /transcripts/{sid}` — so the first word measured is
the one the page draws (word timings when present, else the text). The report
(`<scratch>/report/report.html`, `rows.json`) holds participant text: keep it
out of git.

## Result, 7 Oct 2026 — 3,237 paragraphs, 13 projects

| | paragraphs |
|---|---|
| already a capital at a sentence start | 2,921 |
| kept lower-case: carries on mid-sentence | 207 |
| **capitalised by the rule** | **55** |
| capital where the rule sees no start (left alone; the rule never lower-cases) | 51 |
| no case (digit, punctuation, caseless script) | 3 |

1,141 paragraphs are drawn from word timings; the rule's 55 come almost all from those
(IKEA, foo/foobar, fossda).

- **The capitals are right.** Sampled: "…the bedroom. ⏎ Ideas what's new…", "…did work
  there. ⏎ Okay let's…", a new speaker's "Basically, I came to…".
- **Kept lower-case is mostly right too:** "…there was this idea that ⏎ by enabling
  people…", "…which, you know…". A minority are real starts the rule cannot see, because
  the previous paragraph's text has no punctuation ("okay and then beds ⏎ has this gone
  slow"): 31 flagged. They stay as transcribed, which is today's behaviour.
- **No false sentence ends.** Every paragraph ending in a number or "No." that the rule
  treated as an end really was one (22 checked).
- **No brand words at a sentence start** ("iPhone", "eBay") in this corpus, but the guard
  is cheap: skip a first word with an internal capital.
- **The session language is unknown for every paragraph here** (outputs predate the
  `# Language:` header), so a `lang` for Turkish casing would rarely be set.
- **Scale:** the rule changes 1.7% of paragraphs. It fixes turn starts and starts after a
  split; it does nothing for lower-case sentence starts and "i" *inside* a paragraph,
  which is the larger part of what makes Whisper's words read badly.
