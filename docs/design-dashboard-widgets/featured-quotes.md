# Featured quotes — the job, the algorithm, and the trim

**Status:** Parked with the rest of this effort (post-TF). The **trim prompt is explicitly a
post-TF optimisation** (Martin, 15 Jul 2026). The clamp is the pre-TF stopgap.
Companions: [data-density.md](data-density.md) · [brief.md](brief.md).

---

## The job

> Three quotes to represent the possibly **100,000 words** in the study. Show a **spread of
> meaning**, from **more than one participant**, of the **strongest findings** — hopefully
> **memorable** quotes the researcher should remember them saying, and go *"oh — yes, that was
> a great moment of insight."*  — Martin

That's roughly a **33,000:1 compression**, and the acceptance test is *recognition*, not
coverage. Note the primary case is **3 quotes** — not 5. Most people see 3 (13"/13.6"/14"
laptops); 4 and 5 are bonuses on a 16" and an HD external. **Design for 3.**

## What exists today

`pick_featured_quotes()` — [bristlenose/server/export_core.py:361](../../bristlenose/server/export_core.py).
Called with `n=9`; the dashboard renders `slice(0, 5)`.

1. **Word filter** — prefer quotes of **12–33 words**.
2. **Score** — `+min(intensity,3)` · `+2` negative (frustration/confusion/doubt) · `+2` surprise
   · `+2` delight · `+1` other positive · `+1` researcher_context · `−min((words−33)/10, 2.0)`.
3. **Diversify, three passes** — ① one per participant × distinct polarity → ② relax polarity,
   keep participants distinct → ③ relax everything.

**This already implements the stated MVP** (signal strength + polarity spread + multiple
participants + up to 5). The problem isn't the design — it's that it doesn't bind.

## The measurements (761 real quotes, 9 studies)

**Quote length.** Median **64 words** overall; **IKEA usability median 79**; p90 174; max 927.
A human pull-quote is 10–20. So BN's quotes are **4–8× longer than a human would select** —
because the extraction prompt is deliberately high-recall (*"extract every substantive quote…
typically 1–5 sentences"*). The LLM harvests (~80% of a session); a human observer notes 5–15%.

**The word filter doesn't bind.** Only **69 of 761 (9%)** of real quotes fall in the 12–33 band:

| Study | quotes | in band | |
|---|---|---|---|
| IKEA with uxfriends | 28 | 6 | falls back |
| Ikea dick | 13 | 4 | falls back |
| **Ikea tom** | 11 | **0** | falls back |
| demo-escuela | 18 | 2 | falls back |
| fossda-opensource | 284 | 11 | scrapes by |
| foo/foobar *(synthetic)* | 90 | 22/24 | ✅ |

So the fallback ("any quote ≥12 words") is the **normal** path, and the length penalty **caps at
−2.0** — too weak to matter, since a 200-word quote still scores 3.0 with negative sentiment +
intensity 3. **Real dashboards therefore serve long quotes**, which puts "on first processing you
see something good" at risk.

**Short quotes are measurably blander** — this kills the obvious fix:

| | n | mean intensity | carry any sentiment |
|---|---|---|---|
| Short (12–33w) | 23 | **1.43** | **52%** |
| Long (>33w) | 335 | **1.81** | **70%** |

Emotion needs runway. 48% of short quotes carry no sentiment at all.

## Decisions

- **"Prefer shorter" is OFF the table.** Measured: it costs intensity (1.43 vs 1.81) *and* the
  candidate pool doesn't exist (23 eligible quotes across all real studies; Ikea tom has zero).
- **Clamp (`-webkit-line-clamp`) = the pre-TF stopgap.** Free, presentation-only, no pipeline
  change; the lens keeps the full quote. **Known flaw:** it cuts the *tail*, and in think-aloud
  the payload is usually at the end ("…so I gave up"). A knowing stopgap, not the fix.
- **LLM trim = the real fix, post-TF.** The only option that keeps emotion *and* brevity, because
  it can select the punchy *span* rather than the first N lines.
- **They compose.** Trim → 15–30 words → **2–4 lines** at the primary 3-up face (8.6 w/line).
  Clamp 4 is then a **backstop that only fires when the trim overshoots** — not a crutch.
- **Key quote / "keyframe"** (a human designating the featured quote) — good future idea. The
  **star is the natural mechanism**, and it's the observation act made explicit.

## The trim prompt (proposed — post-TF)

Emit a **new `pull` field. Never overwrite `text`** — the lens keeps the evidence, the dashboard
shows the pull.

> You are shortening an already-extracted verbatim quote for a dashboard card. The full quote
> stays available elsewhere — your output is a **pull**, not a replacement.
>
> **The shape.** Featured quotes earn their place by showing **impact** — what the experience did
> to the person. The strongest pull carries up to three beats, **in the order spoken**:
> 1. **Cause** — what triggered it ("the stock wasn't listed")
> 2. **Feeling** — the strongest affective beat
> 3. **Consequence** — what they did or decided ("so I gave up and went to Google")
>
> *Prefer the triple; never invent it.* Many quotes have only a feeling — keep the strongest
> feeling clause. Delight often has no consequence; that must not be penalised.
>
> **Rules**
> 1. **Elide, don't edit.** You may only DELETE whole clauses or phrases. No substituting,
>    paraphrasing, reordering, re-inflecting, grammar-fixing, or adding words. Every word in the
>    pull must appear in the source, in the same order.
> 2. **Never remove individual words or stopwords.** The unit of deletion is the clause.
> 3. **Mark every deletion with `...`**, per the existing editorial policy. A pull joining two
>    distant clauses must show `...` between them.
> 4. **No trailing `...`** if the pull ends on the quote's final clause.
> 5. **Preserve [square brackets]** exactly — they mark words not spoken.
> 6. **Budget: 15–30 words; never exceed 35.** If the quote is already ≤30 words, return unchanged.
> 7. **Returning it unchanged is a valid answer.** If nothing can go without losing the cause, the
>    feeling, or the consequence — don't cut.
>
> **Ranking clauses.** Use the seven sentiments (frustration, confusion, doubt, surprise,
> satisfaction, delight, confidence) at intensity 1–3. Drop lowest-signal first: scene-setting,
> repetition, self-correction, navigational narration ("so I'm clicking the thing at the top").

### Why the prompt says what it says
- **Stopword removal was proposed and rejected** — it contradicts "no edits". Stopwords aren't
  filler; they carry hesitation, register, emphasis. The shipped policy only permits removing
  *filler* (um, uh) with `...`. **Clause is the unit; word-level surgery is where verbatim
  integrity dies.**
- **"Signal strength" is bound to the taxonomy** (7 sentiments × intensity 1–3) rather than left
  to the model's own scale — otherwise it disagrees with the tags already on the quote.
- **The triple is preferred, not required** — see the bias warning below.

### Two things that make it shippable
1. **"No edits" can be ENFORCED, not requested.** Strip the `...` markers and the pull must be a
   token-level **subsequence** of the source. ~10 lines of Python. If it fails, the model edited
   the verbatim → **reject, fall back to the original.** Turns a polite instruction into a hard
   guarantee — the precondition for letting an LLM near verbatims.
2. **Run on 9, not 761.** It only runs *after* `pick_featured_quotes`, on the featured candidates
   — ~9 calls (or one batched), not a corpus pass. Cost/latency stop being an objection, and
   `pull` exists only where it's used.

### ⚠️ Bias warning — the negativity trap
The scorer already gives **+2 to negative sentiment**, and cause→feeling→consequence is most
natural for *task failure*. Stack both and "the first thing you see on first processing" becomes a
wall of doom — the opposite of the goal. Delight rarely has a consequence ("Oh, that's lovely" is
the whole quote). **Watch the positive/negative mix of the featured set**, and keep the triple a
preferred shape rather than a filter.

## Pro & contra — real-data stress test (15 Jul 2026): the columns don't fill

Brick 4 (Pro & contra, ex kudos/kvetch) was to draw from `pick_featured_quotes` too, **de-duped
against the featured row** (Martin's requirement — don't repeat a quote already shown in the
selected-quotes area). Ported the selection and simulated: featured takes its top 5, Pro/Contra
draw from the ranked remainder by polarity.

| Study | quotes | featured | Pro left | Contra left | verdict |
|---|---|---|---|---|---|
| IKEA uxfriends | 28 | 5 | 4 | 4 | Pro all-long |
| Ikea dick | 13 | 5 | 5 | **1** | Contra thin |
| Ikea tom | 11 | 5 | 5 | **1** | Contra thin, Pro all-long |
| demo-escuela | 18 | 5 | **1** | 9 | Pro thin |
| fossda-test1 | 9 | 5 | 3 | **0** | Contra **empty** |
| fossda-opensource | 284 | 5 | 2 | 2 | thin even at 284 |

**Verdict — the naive design fails.** Three reasons: (1) the de-dup makes it worse (featured takes
the 5 best first, Pro/Contra scrape the remainder); (2) **real studies are lopsided, not balanced**
— a study has a mood (demo-escuela Pro 1/Contra 9; the Ikeas Contra 1), so an empty/one-item column
is the *normal* case, not an edge; (3) even where counts survive, the remaining quotes are "all-long"
(the punchy ones already went to featured). Martin flagged this as the area he was most suspicious
of — confirmed.

**The real decision isn't de-dup logic, it's which widget exists:**
- **(A) Pro/Contra REPLACES the featured row** (the 10-ideas framing). No de-dup; full pool. Still
  needs a real "no pros in this study" empty state for lopsided studies.
- **(B) Keep featured, drop Pro/Contra.** Featured's pass-1 already diversifies by polarity — it
  *already* shows a pro/contra spread in one widget; separate columns promise a balance the data
  doesn't have. **Leaning (B).**

If Pro/Contra survives at all, the de-dup requirement stands: exclude anything already in the
featured/selected-quotes area.

## Open, if this is picked up
- Widen the band (12–45?) and/or **uncap the length penalty** — cheap fixes that make the
  *existing* filter bind, independent of the trim.
- Clamp depth: 3 or 4 lines? Choose it at the **worst case** (HD/5-up, median-length quotes).
