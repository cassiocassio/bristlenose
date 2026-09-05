# Quote-stability findings — 5 Sep 2026

**Corpus:** FOSSDA sessions `s1 s4 s9 s10` (91,211 transcript chars).
**Method:** four independent re-extractions per model through the real
`extract_quotes` stage; pass 1 is the reference, passes 2–4 are re-runs.
**Cost:** $2.53 across the three shipped cloud defaults.

The Jul 2026 baseline this is measured against — `claude-sonnet-4` at
temperature 0.1, on a private corpus — is 80.9–83.5% single-match recovery,
94.6% union, a ~9% fragile tail, and **median text similarity 1.00**.

---

## 1. The timecode-recovery baseline HOLDS on the recommended path

This is the question the run was asked: two defaults changed model family and
the Claude path lost its temperature pin, so do the recovery rates the merge
rule rests on still describe what we ship?

| | single ≥70% | union ≥70% | fragile tail | quote-count spread |
|---|---:|---:|---:|---:|
| Jul 2026 baseline (`claude-sonnet-4` @ 0.1) | 80.9–83.5% | 94.6% | ~9% | — |
| **`claude-sonnet-4-6`** (shipped default, no temp pin) | **84.2%** | **94.5%** | **2.5%** | 119–129 |
| `gemini-3.8-flash` | 90.7% | 92.3% | 0% | 61–72 |
| `gpt-5.6-terra` | 77.3% | **86.6%** | 3.1% | 81–112 |

**Answer: yes, on Claude, and closely.** `claude-sonnet-4-6` returns **94.5%**
union recovery against the Jul figure of **94.6%**, single-match **84.2%**
against 80.9–83.5%, and a fragile tail of **2.5%** against ~9% — every number at
or better than the baseline, on a model that *cannot accept a temperature
parameter at all*.

**So losing the temperature pin cost nothing the pin was credited with**, which
is the argument already recorded in `docs/design-decisions.md` § "Temperature is
not a control we ship" — the stability comes from the position-overlap matcher
and the union rule, not the sampler — now measured rather than reasoned.

**Gemini clears the target too** (92.3% union). **ChatGPT does not** — see §2.

The ordering is worth noting: Gemini wins on *single* match (90.7%) and Claude on
*union* (94.5%). Gemini rarely splits a quote, so its two numbers nearly
coincide; Claude splits more and the union rule recovers it. That is the union
rule doing exactly the job it was introduced for.

## 1b. But text stability is far below the Jul figure — on ALL THREE models

| | text also ≥0.90 | median text similarity |
|---|---:|---:|
| Jul 2026 baseline | — | **1.00** |
| `claude-sonnet-4-6` | 51.1% | 0.85–0.96 |
| `gemini-3.8-flash` | 30.6% | 0.78 |
| `gpt-5.6-terra` | 16.2% | 0.27–0.45 |

Median timecode drift is **+0.0s at both ends for every model**, so the quotes
land on the same spans and carry different words. On Gemini, of 166
timecode-recovered pairs: 6.6% exactly identical, 30.1% below 0.50 similarity.

**There is a model gradient — Claude 51.1%, Gemini 30.6%, ChatGPT 16.2% — but
the CORPUS is the leading explanation for the level, and it is not settled.**
Claude is the control and the closest thing here to the Jul configuration, and
even it sits at 51.1% against a baseline whose median similarity was 1.00. So
"the moved defaults regressed" cannot be the explanation: the model that did not
move shows it too. What differs is the material: the Jul run used a task-based
e-commerce usability study, where a quote is one 5–15s utterance with essentially
one defensible start and stop. FOSSDA is long-form oral history, and the median
quote here is **44–46 seconds and ~550 characters** — a multi-sentence excerpt
from a flowing answer, with many defensible places to begin and end. More room to
differ is exactly what we see.

Disentangling the two would need the Jul corpus, which is private and is why
this harness had to be rebuilt on a different one in the first place. **Until
that is done, do not read these text figures as a model regression.**

**What holds regardless.** A star pinned to a quote survives re-analysis on its
position key — that is what the union rule buys, and it is intact. Whether the
quote the researcher starred still *says the same thing* is a separate number
that the Jul validation did not have to ask, because on that corpus it was 1.00.
On long-form interviews it is not, and the merge rule has nothing to say about
it.

## 2. `gpt-5.6-terra` misses the ≥90% union target the merge rule is built on

86.6% mean, **82.5% worst pass**. The ≥90% target is the one the union rule was
introduced to clear. On the shipped ChatGPT default it does not clear it.

## 3. `gpt-5.6-terra` returns 63% of quote timecodes 60× too large — a shipped defect

Found while checking why ChatGPT's overlap numbers looked odd: its median quote
*span* is **1,380 seconds**. Gemini's is 46s and Claude's is 44s, both about 1.1×
what the quote's own text length implies. ChatGPT's is **53.8×**.

**Mechanism, confirmed at the wire.** The transcript shown to the model is
`MM:SS` (`[01:00]` is one minute). The model writes those values into an
`HH:MM:SS` slot by appending `:00`. Raw strings from a live call on `s9`, a
23-minute session:

```
'00:53:00' -> '02:07:00'
'02:10:00' -> '03:00:00'
'05:34:00' -> '07:00:00'
```

`parse_timecode` is correct and reads `00:53:00` as 53 minutes. The model is
wrong.

**The tell is exact.** In every pass, the set of quotes whose start *and* end
land on an exact minute is **byte-identical** to the set whose end exceeds the
session duration — four passes, no exceptions. A real quote boundary lands on an
exact minute about 1 time in 60.

| pass | quotes | on exact minute | out of range | same set |
|---|---:|---:|---:|---|
| 1 | 97 | 59 | 59 | yes |
| 2 | 81 | 40 | 40 | yes |
| 3 | 90 | 50 | 50 | yes |
| 4 | 112 | 90 | 90 | yes |

**239 of 380 quotes, 63%.** Gemini and Claude: **zero**, on the same
transcripts — so it is model-specific, not prompt-specific. It is also
inconsistent *within* one response (37% of quotes in the same call are correct),
so a blanket ÷60 is the wrong fix; the guard has to be per-quote.

Impact: every deep-linked timecode in a ChatGPT-analysed report, clip-export
boundaries, and the position-overlap key section 1 depends on.

## 4. `s3` extracted zero quotes, silently

The largest session in the corpus (73,747 chars) produced **no quotes at all**
in the cached reference run, while every other session produced 11–80. Nothing
errored. It is excluded from the session set above, and it is the only session
large enough to have taken `_extract_with_split`.

Ruled out: `_has_participant_speech` is not the cause (s3's segments are
untagged, which hits that function's legacy branch and returns True), and it is
not a transcription failure (805 segments of real text).

---

## Limits of this measurement, stated rather than discovered later

- **Four passes, four sessions, one corpus.** The Jul run used ten
  re-extractions. The *direction* of these findings is solid — the ChatGPT
  timecode defect is exact and reproducible — but the recovery percentages carry
  meaningful sampling noise.
- **`segment_index` is `-1` for every quote from every model**, because the
  cached `session_segments.json` carries `-1` on every segment. That is a
  property of the fixture, not of any model, and it means this harness cannot
  say anything about segment resolution.
- **Not measured: section and theme ARI.** The Jul run reported 0.96 and 0.43.
  This harness covers quote extraction only. A related observation from the
  Sonnet 5 repair work, on identical input across four passes: thematic grouping
  returned 4, 4, 3 and 1 themes. Consistent with the recorded 0.43, and not a
  substitute for measuring it.
- **The ChatGPT timecode defect has not been confirmed through a full
  `bristlenose run`.** The harness calls the real stage with the real prompt and
  a real `PiiCleanTranscript`, so the request is faithful, but an end-to-end run
  would close the last gap.

## Reproducing

```bash
cd experiments/quote-stability
../../.venv/bin/python run.py --provider google --model gemini-3.8-flash --passes 4
../../.venv/bin/python analyse.py
```
