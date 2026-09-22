# Generated-language spike — do themes and sections follow an instruction?

**Status: spec, 22 Sep 2026. Nothing built, nothing run.**

## The question

`docs/design-i18n.md` § "PARKED: what language should sections and themes be
generated in" records that nothing steers the language of generated text. The
V1 product decision, taken 22 Sep 2026, is narrower than the parked question and
does not wait on it:

> **V1: one language, the UI language.** Switch the UI to Spanish, run an
> analysis, get Spanish themes and sections. A mixed Catalan / Spanish / English
> study is forced into Spanish, and a section the participant saw as
> *Configuració* on a Catalan site may come back as *Ajustes*. Accepted for V1.

The doc's own leaning (the language of the conversation, per session) stays on
record as the V2 candidate. **This spike is agnostic between them** — the model
is handed a target language and asked to comply; where the string "Spanish"
comes from is wiring, not behaviour, and wiring is not what is unknown.

What is unknown, and what this measures:

1. What the model does **unsteered** on non-English quotes, and whether it is
   the same twice.
2. Whether a **one-sentence instruction** makes every generated field come back
   in the target language, on every pass, on every provider.
3. Whether steering changes **what** it groups, not only what it calls the
   groups — the partition of quotes into themes should be the same analysis
   in a different language.
4. What it does with a **mixed-language** corpus under a single-language
   instruction: which words it translates, which it keeps (product names,
   `Checkout`), and whether it wobbles.

## What is already known

One unsteered data point exists and it is the one the Welcome illustration is
drawn to. `trial-runs/demo-escuela-gastronomica` — two es-MX sessions, 18
quotes — was run on `gpt-4o` on 16 Jun 2026 and every generated field came back
in English over Spanish quotes:

- themes: *Financial and Resource Challenges*, *Curriculum and Educational
  Concerns*, *Career Aspirations and Personal Goals*, … (six, all English)
- descriptions: *"Participants face significant financial burdens…"* (English)
- section labels (s08): *Introduction and personal background*, *Experience
  during culinary internship* (English)

One run, one model that is no longer a default, no repeat. It is enough to say
"English is the likely unsteered outcome" and not enough to say anything else.

## Boundary

Throwaway research code, `experiments/` rules apply. It **does not modify**
`bristlenose/`. It imports the real stage functions and the real `LLMClient`
and reads existing intermediates read-only; it writes only under `out/`.

The prompt is changed **without editing the shipped `.md`**: the harness builds
a `PromptTemplate` from the shipped one with the steer appended to `system`, and
monkeypatches `get_prompt_template` **in the stage module** for the duration of
the call (`bristlenose.stages.s11_thematic_grouping.get_prompt_template`, not
the loader's own name — the stage imported the name at module load). The
shipped file's `sha` therefore never moves, which is also the seam the doc
flags as cheapest for the product: *"a call-site instruction may be cheaper"*
than churning `cohort-baselines.json`.

No telemetry context is bound, so `record_call` drops these rows by design and
nothing lands in any project's `llm-calls.jsonl`. Cost is estimated up front
from `bristlenose.llm.pricing.PRICING` as `quote-stability/run.py::plan` does,
and the run refuses to start without `--yes` once the plan is printed.

## Corpora

| id | what | sessions | quotes | how obtained | exercises |
|---|---|---|---|---|---|
| `escuela` | native es-MX synthetic interviews | 2 | 18 (all general_context) | already on disk | s11, and **s08** (Spanish transcripts exist) |
| `ikea-es` | `project-ikea` quotes translated to Spanish | 3 | 33 (27 screen, 6 general) | one LLM call, cached to `corpora/ikea-es.json`, hand-read once | s10 **and** s11 — the only corpus with screens |
| `ikea-mixed` | s1 → Spanish, s2 → Catalan, s3 left English | 3 | 33 | two LLM calls, cached | the mixed case under a single-language steer |

Translation is by the same provider the corpus is later analysed with is
**not** required; use Claude once and cache. The translation is data
preparation, not a condition. `verbatim_excerpt` is set equal to `text`;
`topic_label` is translated too, since s10/s11 hand it to the model as a hint
and an English hint would leak the answer.

FOSSDA (284 quotes, 181k chars) is deliberately out: translating it costs more
than every other call in this spike combined, and the questions above are not
about scale. A 40-quote sample is the first thing to add if the ikea results
disagree with each other.

## Conditions

Two, per corpus, per provider:

- **`unsteered`** — the shipped prompt, byte for byte. Baseline.
- **`steered`** — the shipped `system` prompt plus one appended sentence:

  > Write every generated label, name, title, subtitle and description in
  > **Spanish** (es). Do not translate or alter the quotes themselves. Keep
  > product names, brand names and on-screen UI labels as the participants
  > said them.

  The last clause is the V1 decision's known cost made explicit: it tells the
  model *Checkout* may stay *Checkout*. Whether it obeys is a measurement, and
  the mixed corpus is where it is tested. One alternative wording is allowed
  per stage if the first fails a provider — recorded as `steered-b`, never
  silently swapped in.

Providers: the three cloud defaults as `PROVIDERS[...].default_model` resolves
them on the day (Claude, ChatGPT, Gemini). Local/Ollama is out of scope.

Passes: **3** per cell. Stability is a question here, and two passes cannot
distinguish a wobble from a coin.

Stages: s10 `cluster_by_screen` and s11 `group_by_theme` on every corpus;
s08 `segment_topics` on `escuela` only (its transcripts are Spanish; the ikea
transcripts are English and translating 4.4k chars of transcript adds nothing
the quotes do not already test).

**Measured by `--plan`, 22 Sep 2026: 108 cells = 126 LLM calls, $1.04** across
the three providers at their current defaults — $0.53 Claude, $0.38 ChatGPT,
$0.13 Gemini. A cell is not a call: `segment_topics` fans out one call per
session inside a single cell, which is why the two numbers differ and why
pricing by cells under-counted every s08 row by half. The estimate reads
`bristlenose.llm.pricing.PRICING`, so it moves when the price table does —
re-run `--plan` rather than quoting this line.

## Known limitations, measured during the run

**`ikea-es` and `ikea-mixed` cannot answer the s11 question.** Ikea has only
6 `general_context` quotes, so thematic grouping produces 2–3 themes and the
hardcoded `Uncategorised` bucket holds two to four of them — the majority, in
some passes. The partition metric over 6 items in 2 groups is noise, and the
language table for those cells is polluted by our own English fallback label
rather than by anything the model did. **Read ikea for s10 only** (27
screen-specific quotes → 9–11 clusters, which is healthy). `escuela` is the
corpus that answers s11, with 18 quotes and 5–8 themes.

This is the degenerate-fixture trap the root `CLAUDE.md` documents, arriving
from the direction nobody watches: the corpus was chosen because it is the only
one with *screens*, and its thinness on the *other* axis was not checked. It
was visible only by reading a cell's output rather than its counts.

It also sharpens the `Uncategorised` finding. On a small contextual corpus that
label is not an edge case — it is where most of the quotes end up, in English,
under every locale.

## Measurements

Written to `out/<corpus>/<provider>/<condition>/pass_<n>.json` (the stage's
own model dumps) and summarised by `analyse.py` into `out/compare.md`.

1. **Language per field.** `theme_label`, `description`, `screen_label`,
   `topic_label`, tagged `en` / `es` / `ca` / `mixed` / `?` by a stop-word
   ratio classifier (spike-grade: `el la de que y en los … ` vs `the and of to
   is … ` vs `el la de que i és amb … `). Ties and short labels go to `?` and
   are read by a human — a two-word screen label like *Bolsa de compra* is the
   normal case, not the edge. The table is the finding; the classifier only
   sorts it.
2. **Stability across passes**, per cell: theme count; label-set overlap
   after normalising case and accents; **adjusted Rand index** between the
   quote→group partitions of pass *n* and pass *m*. `scikit-learn` is **not**
   in this venv — `thematic-spike`'s README says it installs it, the venv has
   been rebuilt since, and it is gone. ARI is a closed form over a contingency
   table, so `analyse.py` computes it and self-checks at import against four
   published values, rather than pulling numpy and scipy in for a throwaway.
3. **Partition drift, steered vs unsteered**: ARI between each steered pass
   and each unsteered pass on the same corpus and provider. This is the
   "same analysis, different language" check. Report it next to the
   within-condition ARI from (2), because a steered-vs-unsteered gap smaller
   than the pass-to-pass wobble is not a gap.
4. **Retention on the mixed corpus**: for each screen label, whether an
   on-screen term the participants used (`Checkout`, `Shopping Bag`, the
   Catalan session's own words) survived, was translated, or was replaced.
   Hand-read; there are nine screens.
5. **Schema and failure**: any `StageOutcome.failed`, any fallback grouping,
   any label that came back empty or in the wrong script. A structured-output
   schema with a `description="…"` in English is itself a steer in the wrong
   direction, and this is where it would show.
6. **Descriptions vs labels**: tag them separately. A model that translates
   the two-word label and leaves the fifteen-word description in English is a
   plausible failure mode and the table must be able to show it.

## What the results decide

- Steered cells ≥ 95 % `es` on every field, every pass, every provider, and
  steered-vs-unsteered ARI within the pass-to-pass band → **V1 is a one-line
  call-site steer**, fed from the UI locale, and the Welcome illustration's
  GENERATED entries can be keyed the same day.
- Any provider that ignores the instruction on any pass → that provider
  needs its own wording or a schema-level steer, and V1 ships behind a
  per-provider check rather than a blanket assumption.
- Partition drift outside the band → steering costs analysis quality and the
  V1 design needs to say so, or generate unsteered and translate labels in a
  second cheap call.
- The unsteered baseline is itself unstable (English on one pass, Spanish on
  the next) → the "undefined" in the design doc is measured, not argued, and
  the case for steering does not depend on which language wins.

## Findings the spike surfaces without running

- `s11_thematic_grouping.py:130` hardcodes `theme_label="Uncategorised"` and
  an English description for the thin-theme bucket. That is **our** string,
  not generated text, and it renders in the report under every locale. It
  belongs in `bristlenose/locales/*/` through `t_in(locale, …)` whatever the
  spike concludes.
- The response schemas in `bristlenose/llm/structured.py` carry English
  `Field(description=…)` text that reaches the model as part of the JSON
  schema. If steering fails on a provider that weights schema descriptions
  heavily, that is the first place to look.

## Layout and run

```
experiments/generated-language/
├── README.md        — this file
├── corpora.py       — load escuela / ikea from trial-runs; translate + cache ikea-es, ikea-mixed
├── run.py           — --corpus --provider --condition --passes --plan --yes ; monkeypatches the stage's template
├── analyse.py       — language tags, ARI, out/compare.md
├── corpora/         — cached translations (gitignored: trial-run derived)
└── out/             — one JSON per pass (gitignored)
```

```bash
cd /Users/cassio/Code/bristlenose
.venv/bin/python experiments/generated-language/corpora.py --build            # translations, once
.venv/bin/python experiments/generated-language/run.py --plan                 # cost, no calls
.venv/bin/python experiments/generated-language/run.py --yes                  # everything
.venv/bin/python experiments/generated-language/analyse.py
```

A pass already on disk is never re-run (the 3 Jul 2026 double-spend rule).
