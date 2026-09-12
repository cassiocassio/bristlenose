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

**Read the PADDED column.** The unpadded runs were taken before §3's prompt-format
fix, and on a metric measured along the **timeline** — so for `gpt-5.6-terra`,
whose timecodes were 60× wrong in 63% of quotes, the unpadded figures are
measuring garbage and mean nothing. They are kept only because §3 and §3b are
built on that same data.

| | single ≥70% | union ≥70% | fragile tail | quote counts |
|---|---:|---:|---:|---|
| Jul 2026 baseline (`claude-sonnet-4` @ 0.1) | 80.9–83.5% | 94.6% | ~9% | — |
| **`claude-sonnet-4-6`** (shipped default, no temp pin) | **88.5%** | **96.1%** | **1.6%** | 115–128 |
| `gpt-5.6-terra` | 84.4% | **95.6%** | 0.0% | 85–97 |
| `gemini-3.8-flash` | 76.0% | **80.4%** ✗ | 5.9% | 60–68 |
| _unpadded, for §3's provenance only_ | | | | |
| `claude-sonnet-4-6` (unpadded) | 84.2% | 94.5% | 2.5% | 119–129 |
| `gemini-3.8-flash` (unpadded) | 90.7% | 92.3% | 0% | 61–72 |
| `gpt-5.6-terra` (unpadded) | 77.3% | 86.6% | 3.1% | 81–112 |

**Answer: yes, on Claude, and comfortably.** `claude-sonnet-4-6` returns **96.1%**
union recovery against the Jul figure of **94.6%**, single-match **88.5%** against
80.9–83.5%, and a fragile tail of **1.6%** against ~9% — every number at or better
than a baseline measured *with* a temperature pin, on a model that **cannot accept
one at all**.

**So losing the temperature pin cost nothing the pin was credited with**, which
is the argument already recorded in `docs/design-decisions.md` § "Temperature is
not a control we ship" — the stability comes from the position-overlap matcher
and the union rule, not the sampler — now measured rather than reasoned.

**`gpt-5.6-terra` clears the target too**, at 95.6%.

### A claim withdrawn, and one opened

**WITHDRAWN: "`gpt-5.6-terra` misses the ≥90% union target."** That was §2 of this
file, from the unpadded run: 86.6% mean, 82.5% worst. It was an artefact. The
metric is timeline-based and 63% of that model's timecodes were 60× wrong, so the
overlap it measured was not the overlap of the quotes. With the format mismatch
fixed, terra clears the target at **95.6%** with a **zero** fragile tail. Recorded
rather than deleted, because the original claim reached a session summary and a
commit body before it was re-measured.

**OPEN: `gemini-3.8-flash` now appears to MISS the target** — 80.4% union,
77.9% worst, down from 92.3% unpadded. A 11.9-point drop in the direction the
fix was not supposed to push anything. Three readings, none settled:

- **noise** — four passes, one corpus; the per-pass spread is 77.9–83.8%, so the
  mean is not resting on an outlier, but n is small;
- **a real interaction** with zero-padded `HH:MM:SS`, which would mean the fix
  traded one model's correctness for another's stability;
- **a measurement boundary** — Gemini returns the fewest quotes (60–68 against
  Claude's 115–128), so each quote is worth 1.5% and the denominator is thin.

**§3's common-reference measurement points at the first reading.** Scored against
a *shared* baseline — unpadded pass 1, so only the prompt differs — Gemini is
**unmoved**: 89.8% single / 92.2% union, against 90.7% / 92.3% for the baseline's
own passes. So Gemini's output did not change when the prompt did; what changed is
how well its four padded passes agree with **each other**. Those are different
quantities, and the second is the noisier one at this n.

**Do not act on 80.4% without more passes.** ~8 more is about $0.60:
`run.py --provider google --model gemini-3.8-flash --passes 12`. Until then the
right statement is that Gemini's *self*-consistency reads lower on the padded
passes while its *agreement with the pre-fix baseline* is intact — which is what
sampling noise on a thin denominator looks like, and not yet what a regression
looks like.

## 1b. Text stability is far below the Jul figure — on ALL THREE models

Padded runs:

| | text also ≥0.90 | median text similarity |
|---|---:|---:|
| Jul 2026 baseline | — | **1.00** |
| `claude-sonnet-4-6` | 51.8% | 0.92–0.94 |
| `gemini-3.8-flash` | 18.6% | 0.55–0.60 |
| `gpt-5.6-terra` | 14.4% | 0.43–0.54 |

Median timecode drift is **+0.0s at both ends for every model**, so the quotes
land on the same spans and carry different words. The padding fix barely moved
these numbers — Claude 51.1% → 51.8%, Gemini 30.6% → 18.6%, terra 16.2% → 14.4% —
so text instability is **not** a symptom of the timecode defect. It is its own
thing.

**There is a model gradient — Claude 51.8%, Gemini 18.6%, ChatGPT 14.4% — but
the CORPUS is the leading explanation for the level, and it is not settled.**
Claude is the control and the closest thing here to the Jul configuration, and
even it sits near half against a baseline whose median similarity was 1.00. So
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

## 2. _(withdrawn — see §1 "A claim withdrawn, and one opened")_

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

**Guarded 7 Sep 2026** (`a7d455d2`). `s09_quote_extraction.py` range-checks each
parsed timecode against the session's own duration: out of range, a whole number
of minutes, and back in range once divided by 60 is repaired and logged
`quote_timecode_repair`; out of range without that signature is clamped, not
divided, and logged `quote_timecode_out_of_range`. Never silent.

**Fixed at source 11 Sep 2026, and re-measured.** The guard treats the symptom;
the cause was that the prompt showed `MM:SS` while the schema asked for
`HH:MM:SS`. `full_text()` and the `boundaries_text` beside it now render
`format_timecode_prompt` — zero-padded `HH:MM:SS`, one format per prompt — so
there is no mismatch left for a model to resolve. 12 fresh passes, same corpus,
same four sessions (`--tag padded`):

| model | out of range, before | after | median span, before | after |
|---|---:|---:|---:|---:|
| `gpt-5.6-terra` | **239/380 (62.9%)** | **0/361 (0.0%)** | 270–2100s | **48–55s** |
| `claude-sonnet-4-6` | 0/494 | 0/499 | 42–45s | 40–45s |
| `gemini-3.8-flash` | 0/259 | 0/260 | 46–59s | 50–51s |

**The guard fired zero times across all 12 passes** — no `quote_timecode_repair`,
no `quote_timecode_out_of_range`. That distinction is the whole measurement: the
guard was active throughout, so a still-broken model would have been silently
repaired and the saved quotes would have looked identical to a real fix. Only the
absence of the log lines separates "fixed" from "repaired". Check them, not the
JSON, if this is ever re-run.

The median span is the stronger evidence than the out-of-range count. Avoiding
the end of the recording could be luck; a span distribution collapsing from
1380s to 54s, into the same band as the two models that were never affected, is
the `HH:MM:SS` slot being filled correctly rather than merely plausibly.

**Terra's stability numbers in section 1 were never valid** and are now replaced.
Overlap is computed on the timeline, so a 60x timecode makes every overlap
meaningless. The first trustworthy reading is 84.4% single / 95.6% union / 0.0%
fragile — union clears the >=90% target the merge rule needs, where the old
(meaningless) figure was 86.6%.

**Claude's output shifted; Gemini's did not.** Scored against a *common*
reference — baseline pass 1, so only the prompt differs — Claude's padded passes
recover it at 77.7% single / 91.0% union, against 84.2% / 94.5% for the
baseline's own passes. Gemini is unmoved (89.8% / 92.2% vs 90.7% / 92.3%).
Padded Claude is no less self-consistent (88.5% / 96.1% internally, versus
84.2% / 94.5% before), so this is a shift in *which* quotes it picks, not a loss
of stability. Operationally that is a one-time migration cost: a project analysed
before this change and re-analysed after it sees ~9% of pinned stars at risk
rather than the usual ~5.5%.

**Do not compare two runs via `analyse.py` alone.** It scores each run against
its OWN pass 1, so two independent runs are measured against two different
references. That artefact read as a 14.7-point Gemini regression on the first
look; holding the reference fixed showed 0.9 points. A cross-run comparison has
to pin the reference.

## 3b. The same defect is in stage 8, and it is NOT model-specific

Measured 11 Sep 2026, after § 3's fix. s08 feeds the same `full_text()` into the
same kind of prompt and parses the answer back with the same `parse_timecode`,
and **unlike s09 it has no range guard** — so a mangled boundary is corrected
nowhere and reported nowhere.

**It was in the cached corpus this harness fed to every pass as
`boundaries_text`** (repaired in place 11 Sep 2026 — see the end of this
section; the table below is the pre-repair state, preserved because it is the
evidence):

| | boundaries | exact-minute | out of range | resolve under /60 |
|---|---:|---:|---:|---:|
| cached `topic_boundaries.json` | 133 | 41 | **38 (28.6%)** | **38 — all** |

Bimodal by session: s1 9/10, s3 13/21, s6 7/8, s10 9/10 affected; s2, s4, s5, s8,
s9 completely clean.

**And the telemetry says which model wrote it: `claude-sonnet-4-20250514`**, all
ten s08 calls, outcome `ok`, 30 Apr 2026
(`.bristlenose/llm-calls.jsonl`, key `gen_ai.request.model` — note the file's
keys are OpenTelemetry-style, so a grep for `model` finds nothing).

**This retires § 3's "model-specific, not prompt-specific".** That inference came
from one stage and three models. Three different model *families* have now been
observed doing it: `claude-sonnet-4` (s08, 38/133), `gpt-5.6-terra` (s09,
239/380), and `gemini-3.8-flash` (s08 unpadded, below). It is a **prompt-format
hazard**, and the padding is a fix rather than a vendor workaround.

**The controlled arm, and it is the cleanest evidence in this document.** One
variable — the timecode rendering — 10 sessions, one pass per arm:

| model / arm | boundaries | out of range |
|---|---:|---:|
| `gemini-3.8-flash` **unpadded** | 95 | **5 (5.3%)**, all in s8, all resolving under /60 |
| `gemini-3.8-flash` **padded** | 100 | **0** |
| `claude-sonnet-4-6` unpadded | 121 | 0 |
| `claude-sonnet-4-6` padded | 131 | 0 |

Same model, same sessions, same code but for the rendering: the defect appears
and disappears with it.

**terra on s08: 0, 0, 0, 11 across four unpadded passes** (12 Sep 2026) — 11 of
683 boundaries, **1.6%**. The first pass read clean and was reported as such; it
was sampling, not immunity. The eleven arrived together, in one session, in the
fourth pass.

The grid, with every cell's pass count stated because that is what the first
reading got wrong:

| unpadded | s08 | s09 |
|---|---|---|
| `gpt-5.6-terra` | **1.6%** (11/683, 4 passes) | **62.9%** (239/380, 4 passes) |
| `gemini-3.8-flash` | **5.3%** (5/95, 1 pass) | 0% (0/259, 4 passes) |
| `claude-sonnet-4` | **28.6%** (38/133, 1 run) | 0% (0/284, same run) |
| `claude-sonnet-4-6` | 0% (0/121, 1 pass) | 0% (0/494, 4 passes) |

So the earlier reading — "every model that fails, fails on exactly one stage" —
is **retired**. terra fails on both, at rates differing by a factor of forty. What
survives is weaker and more useful: the hazard is the prompt/schema mismatch, the
rate varies enormously by (model, stage) for reasons nothing here explains, and
**a single clean pass is worth almost nothing**. Every zero in that table with a
pass count of 1 should be read as "did not fire once".

**Both models' failures landed in s8. That is not evidence about s8.** Nothing
distinguishes it — 33.7 min, 300 segments, first timecode 1.2s, median gap 6.8s,
all unremarkable against s1/s4/s7. Two independent one-in-ten picks coinciding is
a 10% event. Recorded so the next reader does not spend a cycle on it, the way
the boundary-echo hypothesis in § 3b's history already cost one.

**This was the guard's first live firing, and it worked.** Pass 4's eleven
boundaries were repaired in flight — `03:38:00` -> 218s, `31:54:00` -> 1914s in a
33.7-minute session — and `boundary_timecodes_repaired | session=s8 |
boundaries=12 | scaled=11` records it. It also demonstrates the masking effect
concretely: **pass 4's file on disk audits CLEAN**, because the guard corrected
it before it was written. Only the log knows. Any future audit of a
post-11-Sep-2026 run must read the logs, not the JSON, or it will measure the
guard instead of the model.

The stray single exact-minute boundary in several clean arms is the ~1-in-60 base
rate the § 3 tell predicts, in range and correct — a sanity check that the audit
is not over-flagging.

**s08 is now guarded** (11 Sep 2026). The guard is shared —
`bristlenose/stages/timecode_guard.py`, one implementation behind both stages —
with per-stage log keys (`quote_*` / `boundary_*`) so a stage's lines stay
greppable on their own.

The stages diverge on ONE rule, deliberately. s09 **clamps** a value that is out
of range without the 60x signature, because a quote timecode is *shown* and a
bounded deep link beats one past the end of the media. s08 **drops** it: clamping
a boundary would invent a topic transition at the session end and then push it
back inside `_boundaries_in_range`, turning a boundary the downstream filter
would have caught into one it cannot. s08's old behaviour was to lose these
silently anyway; the guard makes the loss visible.

Replayed against the real cached corpus, the guard recovers **38 of 38** affected
boundaries, drops none, and leaves the 95 good ones untouched. s1's repaired
values land at 1.0, 4.4, 7.7 and 10.9 min in a 39.6-min session — monotonic,
sensibly spaced, and in the topical order the labels imply.

**The corpus was then repaired in place** (`repair_cached_boundaries.py`, 11 Sep
2026). Verified after: 133 boundaries before and after, **labels byte-identical**,
38 timecodes changed, **zero non-timecode fields changed**, zero still out of
range. The pre-repair file is pinned at
`out/_pinned-inputs/fossda-opensource-topic_boundaries-preRepair.json`, so the 12
committed quote-stability passes — measured with the *old* boundaries as prompt
input — stay reproducible.

**Repair, not re-run, and the distinction is the point.** A fresh s08 call returns
NEW boundaries with NEW labels, and every cached quote's `topic_label` is an exact
boundary label string — **106 of 106** — so re-running s08 alone would leave all
284 quotes pointing at boundaries that no longer exist. "Re-run s08" and "fix the
cached boundaries" are different operations.

**The cached quotes did NOT need repairing.** Same model, same run, s09: 3 of 284
out of range (1.1%) and none carrying the signature — s4 overshoots its last
segment by 6s, s7 by 29s, s9 by 15s, which is ordinary imprecision. So
`claude-sonnet-4` hit 28.6% on s08 and 0% on s09 in the same run. Whatever makes
a model fall into this, it is not uniform across stages, and a stage measured
clean says nothing about its neighbour.

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
