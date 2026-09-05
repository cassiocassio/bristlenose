# Quote-stability corpus

Re-extract the same interviews N times, measure what survives.

## Why it was rebuilt

The Jul 2026 validation (`docs/design-incremental-analysis.md` § Validation) is
the grounding for the incremental-analysis merge rule — ~81% recovery by single
best-overlap match, ~95% by union/split-crediting, a ~9% genuinely-fragile tail.
It ran on a **private** corpus with `claude-sonnet-4` at temperature 0.1, and its
harness was deliberately kept out of the public tree because the data was
participants'.

Two things have since changed underneath those numbers:

- the ChatGPT and Gemini defaults moved model **family** (`gpt-5.6-terra`,
  `gemini-3.8-flash`), and
- the temperature pin is gone from the Claude path entirely — sampling
  parameters are refused on every Claude model after 4.6, and
  `docs/design-decisions.md` § "Temperature is not a control we ship" records
  that the slider's removal was justified partly *by* these numbers.

So the rates the merge rule rests on describe a configuration we no longer ship.

## The corpus

FOSSDA — open-source interviews, already transcribed, so this can live in the
public tree. It reads the cached `session_segments.json` and
`topic_boundaries.json` from an existing run and calls the real `extract_quotes`
stage, so a pass costs one LLM call per session and nothing else. No
transcription, no PII pass, no clustering.

Default session set is `s1 s4 s9 s10` — four mid-sized interviews, ~91k
transcript chars, 72 quotes in the reference run.

## Running it

```bash
cd experiments/quote-stability
../../.venv/bin/python run.py --model claude-sonnet-4-6 --passes 4 --plan   # cost, no calls
../../.venv/bin/python run.py --provider google --model gemini-3.8-flash --passes 4
../../.venv/bin/python analyse.py
```

`--plan` prices the run from `bristlenose/llm/pricing.py`, so the estimate moves
when the price table does. A pass already on disk is never re-run: passes are
paid for, and the 3 Jul 2026 double-spend came from re-running a step whose
guard had quietly failed.

## Reading the output

Two recovery rules, because a star pinned to a quote has to survive re-analysis:

- **single best-overlap** — the one re-run quote overlapping the reference most
  covers ≥70% of it. The naive reading, and the Jul run is its refutation.
- **union / split-crediting** — all overlapping re-run quotes together cover
  ≥70%. This credits a quote the model split in two, and it is what cleared the
  ≥90% target.

The gap between those two lines is the value of the union rule. Quotes no rule
recovers are the fragile tail — the model did not return them that pass, so no
boundary logic reaches them.

## Validating the metrics without spending anything

`analyse.compare` is pure. Known perturbations move it predictably, and these
were checked before the first paid pass:

| input | single | union |
|---|---:|---:|
| a pass against itself | 100% | 100% |
| every quote dropped | 0% | 0% |
| boundaries shifted 10% | 98.6% | 98.6% |
| boundaries shifted 40% | 13.9% | 65.3% |
| **every quote split in two** | **2.8%** | **100%** |

The last row is the union rule's whole purpose, demonstrated on real quotes.

Findings live in `FINDINGS.md`.
