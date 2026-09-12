---
status: partial
last-trued: 2026-09-12
previous-trued: 2026-06-04 (v1.9 → v2, against an uncommitted working tree)
trued-against: HEAD@main on 2026-09-12
---

> **Truing status:** Partial — trued 2026-09-12 against `main`. Two rungs of v3
> remain genuinely unshipped, not one: the **`recommended` marker** (data + JSON
> + tests ship it; no CLI or React badge) and the **orphaned positive notes**
> (`_why_text` returns `""` for `✓●`/`✓○`, so both Local structural notes and
> both transcription notes render nowhere). The banner said "one rung" until
> 2026-09-12 while §"The rung map" below listed two — the doc disagreed with
> itself, in the summary rather than the body, which is the half a cold reader
> reads.
>
> **Superseded front-matter, kept as the record:** this doc was previously
> anchored to `HEAD@pipeline-view-models (working tree — v2 uncommitted)`. That
> branch is long merged and the anchor named a working tree that was never a
> commit, so it could not be checked against anything.

## Changelog

- _2026-09-05_ — **the catalogue's model ids caught up with what ships, and a
  test now stops them drifting again.** Every cloud id here was a May 2026
  snapshot: Sonnet 4 and Opus 4 (dated `20250514`), `gpt-4o`, and
  `gemini-2.5-pro` — which had been **404 for new accounts** since at least
  4 Sep, when all three *other* model tables moved and this one did not. The
  view therefore offered a model a researcher could not call, marked
  `default` and rated `good`, directly above a synthesised row for the model
  that actually ran, marked untested. The `(current)` badge was the only true
  thing in the group. Now: Claude → Sonnet 4.6 / Opus 5 / Haiku 4.5, ChatGPT →
  GPT-5.6 Terra / Luna, Gemini → 3.8 Flash / 3.5 Flash-Lite.
  **Gemini ships unrated**, and so do Haiku and Luna: the retired `good` was a
  judgement about a *Pro*-class model, and carrying it onto Flash would assert
  something nobody measured. Where a rating did move (Sonnet 4 → 4.6, Opus 4 →
  5, gpt-4o → Terra) it is a judgement about the class, and each of those ran
  the six real stage templates live on 4–5 Sep. The gate is
  `test_models.py::test_catalogue_ids_match_the_shipping_model_lists` +
  `…_default_model_is_the_registry_default`, which read `providers.py` and
  parse `LLMProvider.swift`; both were mutation-checked (retired id → red,
  wrong default flag → red) rather than assumed. Note for whoever adds the
  next model: **the per-stage `default` badge comes from the *rating*, not
  from `ModelOption.default`** — it is singular per stage and belongs to the
  provider BN dispatches, so an unselected provider correctly shows no badge;
  which model *it* would use is answered by `(current)` on selection.
- _2026-06-04_ — trued up v1.9 → v2: schema 3→4 + per-(provider, model) grain
  (`ModelOption` on `BackendOption.models`); `BackendAvailability` → `ModelAvailability`,
  `reason` → `reason_key` + new `action_key`; `llm_summary` deleted (per-stage
  rendering); CLI/React glyph + 6-locale rendering shipped (21 full locales as of Sep 2026); dead sort-weight
  section replaced with the declaration-order + collapse-when-uniform invariant;
  untested glyph `⚠` → `?`; provenance now editorial + community; `_migrate_schema`
  hook added (Rule-of-Three fired at schema v3→v4). `recommended`-marker rendering remains
  the sole outstanding rung. Anchors: `render.py:55,58,138,148,318`,
  `catalogue.py:68,117`, `cli.py:170,188`, `test_models.py:45`, four-scenario
  `pipeline-view-contract.json`.
- _2026-05-25_ — initial v1.9 truing (`git log` `8dfda74`).

# Design: Pipeline view — read-only catalogue surface

**Status (12 Sep 2026, was 4 Jun):** v1.5, v1.9, and v2 shipped. The Pipeline view is the **read-only catalogue surface** that tells a researcher, at a glance, which backends Bristlenose could use for each stage on the current host, which it actually picks by default, which it editorially endorses, and how good each one is for the job. It is **not** the resolver — choosing per-stage backends is still owned by the user via global `llm_provider` (LLM stages) + the host-aware resolver in `s05_transcribe._resolve_backend` (transcription). The CLI rendering, the React Settings surface, the quality glyphs, and the locale fill all shipped in **v2**, now at per-(provider, model) grain. The next rung is **v3** — render the `recommended` marker (see §"Why `recommended` is foundational, not dead weight"); the `optimise_for` axis (cost / speed / privacy / determinism) is deferred to v6 (see the rung map below).

**Related:** [design-stage-backends.md](design-stage-backends.md) (architectural principle — capability declaration + resolver), [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) (full routing roadmap, mostly still aspirational), [design-research-methodology.md](design-research-methodology.md) §Backend quality scale (canonical home for the 4-level scale + axes), [design-decisions.md](design-decisions.md) (the "why" for the scale + orthogonal axes), [design-i18n.md](design-i18n.md) (locale convention for `pipeline.<category>.<leaf>`).

## Why this doc exists

The Pipeline view is the user-visible mirror of [design-stage-backends.md](design-stage-backends.md)'s "capability declaration" principle. It started life inside `design-cli-improvements.md` as a one-section idea for the CLI; v1 shipped it in the React Settings → Pipeline tab; v1.5 extended it with per-stage **alternatives** and eligibility predicates; v1.9 adds **editorial quality ratings**. The shipped surface now warrants its own design doc — both because it's grown enough to deserve a self-contained explanation, and because [design-stage-backends.md](design-stage-backends.md) and [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) point at it as a downstream artefact.

## What the Pipeline view is

A **read-only JSON payload** (`PipelineView` in `bristlenose/pipeline_view/render.py`) consumed by the React Settings → Pipeline tab and the CLI `bristlenose pipeline` command. For each user-visible stage it answers four questions:

1. **What does this stage currently use?** — the `StageSelection.chosen` string, derived from `BristlenoseSettings` + host-aware resolvers. Single source of truth: matches what `bristlenose run` would dispatch.
2. **What else could it use on this host?** — `StageSelection.alternatives`, a flat per-(provider, model) list of `ModelAvailability` rows. (v2 deleted the v1.5 `llm_summary` dedup card — the five LLM stages no longer share one card; see §"v2: per-(provider, model) grain".) Each `ModelAvailability` has `available: bool` + a translation-key `reason_key` when not, plus an `action_key` (the "what to do about it" hint — e.g. "add an API key").
3. **How good is each option for this stage?** — `quality` (4-level rating) + `quality_note` (translation key) + `quality_source` (provenance). Editorial layer over the mechanical eligibility layer.
4. **Which does Bristlenose itself pick or endorse?** — `default: bool` (the cell BN runs if you change nothing) + `recommended: bool` (cells BN actively endorses; potentially plural).

The view is **never the source of truth for dispatch**. `bristlenose run` reads settings + resolvers directly. The Pipeline view is a *projection* of dispatch, evaluated against the catalogue and the host. If they ever disagree, the view is wrong by definition.

## The two layers

### v1.5: mechanical eligibility (✓/✗)

`bristlenose/pipeline_view/eligibility.py` evaluates each `BackendOption.requires` (list of `Requirement` predicates) against `HostFacts` (API keys present, hardware tier, OS version, RAM, Ollama reachability, Python packages installed, Apple FM status) and `BristlenoseSettings`. Output is binary: the backend either runs on this host or it doesn't, with a translation-key reason when not.

This layer answers **"can it?"** and is the floor everything else builds on.

### v1.9: editorial quality (●/○/⚠/✗)

Layered on top of v1.5. For each (stage, backend) cell, `quality_for()` returns a `QualityRating` from a hand-curated catalogue. The rating is **editorial, not derived** — there is no benchmark runner. Researchers see signal that's been thought about, not computed.

This layer answers **"is it any good for THIS stage?"** and is what closes the v1.5 "viable-but-poor confidence trap" risk: shipping ✓ alongside a backend that technically runs but produces unusable output set researchers up for disappointment. The editorial layer makes the disappointment legible *before* they pipe an interview through it.

### v2: per-(provider, model) grain

v1.5 and v1.9 evaluated eligibility + quality per *backend* (provider family), and the five LLM stages shared one deduped summary card. v2 pushes the grain down to the individual **model**: `BackendOption` now holds `models: list[ModelOption]` (`catalogue.py:117`), eligibility + quality resolve per (stage, provider, model), and each stage carries a flat `alternatives` list of `ModelAvailability` rows (`render.py:58`) instead of the deleted `llm_summary` card. This is what lets the catalogue say "Claude offers Sonnet 4.6 (the default) *and* Opus 5 (also endorsed) *and* Haiku 4.5 (offered, unrated)" rather than collapsing the provider to one line.

Per-model grain is the axis the editorial layer needed — a provider isn't uniformly good: Local (Ollama) is `good` for the structural stages (speaker id, topic segmentation) but `marginal` for the three synthesis stages (`catalogue.py:491-494`), a distinction the old per-backend card couldn't express. New per-row fields: `model_id`; `provider_display` (the provider label carried on every row so consumers don't re-derive it); `publisher`; `action_key` (the fix hint); and `synthesised` (True for rows composed from settings rather than the catalogue — the Azure deployment, user-pulled Ollama models, dispatched-but-uncatalogued models; rendered distinctly).

## The orthogonal axes

Four axes on every `QualityRating`. Independent on purpose — collapsing them sacrifices honest signal.

| Axis | Type | Plurality | Meaning |
|---|---|---|---|
| `rating` | `excellent` / `good` / `marginal` / `avoid` | one per cell | Fitness for purpose at this stage |
| `default` | bool | **singular** per provider (≤1 default model) | What BN runs if user changes nothing — `ModelOption.default`, enforced by `test_at_most_one_default_model_per_provider` |
| `recommended` | bool | **plural by design** | Cells BN actively endorses as production choices |
| `source` | `internal_bench` / `published_bench` / `community` / `editorial` | one per cell | Where the rating came from |

**Invariant:** `default ⇒ recommended`. BN cannot default to a cell it does not actively endorse. Recommended is strictly wider than default; both are subsets of `rating ∈ {excellent, good}` (BN never defaults to or recommends `marginal` / `avoid`).

See [design-research-methodology.md](design-research-methodology.md) §Backend quality scale for the canonical definitions of the four rating levels (including the verbatim metaphor for `marginal`), and [design-decisions.md](design-decisions.md) §Pipeline and analysis for the "why" behind each axis choice.

### Worked example — default vs recommended

A researcher opens the Pipeline view for *quote_extraction* with all four cloud keys + Ollama configured.

**v1.9 baseline (provider grain — preserved to show the v1.9 → v2 delta):**

| Backend | `available` | `quality` | `default` | `recommended` | What renders |
|---|---|---|---|---|---|
| Claude | ✓ | excellent | **true** | **true** | `✓●★ Claude — BN's pick` |
| ChatGPT | ✓ | excellent | false | false | `✓● ChatGPT` |
| Azure OpenAI | ✓ | good | false | false | `✓○ Azure OpenAI` |
| Gemini | ✓ | good | false | false | `✓○ Gemini` |
| Local (Ollama) | ✓ | marginal | false | false | `✓⚠ Local (Ollama) — small models miss multi-clause quotes` |
| Apple FM | ✗ | — | false | false | `✗ Apple FM — check in the desktop app` |

v1.9 flagged only Claude `recommended=true` — the one cell with evidence.

**v2 (per-model grain):** each provider expands into its catalogued models, and v2 is the **first build where `recommended ≠ default` fires** — Claude is endorsed at *two* models (Sonnet 4.6 the default, Opus 5 recommended-but-not-default), and GPT-5.6 Terra is recommended without being the default (`_LLM_QUALITY` in `catalogue.py`):

| Provider | Model | `available` | `quality` | `default` | `recommended` |
|---|---|---|---|---|---|
| Claude | Sonnet 4.6 | ✓ | excellent | **true** | **true** |
| Claude | Opus 5 | ✓ | excellent | false | **true** |
| Claude | Haiku 4.5 | ✓ | — untested | false | false |
| ChatGPT | GPT-5.6 Terra | ✓ | excellent | false | **true** |
| ChatGPT | GPT-5.6 Luna | ✓ | — untested | false | false |
| Gemini | 3.8 Flash | ✓ | — untested | false | false |
| Gemini | 3.5 Flash-Lite | ✓ | — untested | false | false |
| Local | llama3.2:3b | ✓ | marginal | false | false |
| Local | Gemma 4 E4B / 26B / 31B | ✓ (RAM permitting) | — untested | false | false |

As more cohort data arrives — "Local on a 30B+ model now handles structural stages well" — we flip the relevant `recommended` flag without touching `default`. The view becomes more permissive over time; the singular default stays singular. **Caveat:** as of v2 `recommended` is carried in data + JSON + tests but renders no badge in any surface — see §"Why `recommended` is foundational, not dead weight".

### Why this matters

Without separating the axes:

- **Researchers see a monolithic choice.** "Claude is the default; everything else is just 'available with quality X'." The default's authority outshines every other option even when BN would happily endorse two or three of them.
- **Cohort signal accumulates nowhere.** Saying "ChatGPT is also fine for this stage" requires either changing the default (singular — wrong tool) or adding a new axis (which we'd then have to invent under pressure).
- **The autonomy framing breaks.** [methodology/consent-gradient.md](methodology/consent-gradient.md) §"Default to professional norms" commits to "researchers are adults". A plural `recommended` is the architectural form of that commitment — "these are all in-bounds production choices; pick what fits your constraints."

### Why `recommended` is foundational, not dead weight

As of v2 the `recommended` flag is carried in data, test-enforced (`default ⇒ recommended`), and shipped in the `/api/pipeline` JSON payload — but rendered in **no** user-facing chrome (no CLI badge, no React badge, no locale string; only `default` and `current` render today). This is a **deliberate capture-only stub, not an oversight**. The exposure work is intentionally deferred; the axis is foundational for three reasons:

1. **`default` makes it just work out of the box.** A researcher who changes nothing gets BN's single wired pick per stage. That's the singular axis, and it ships rendered today.
2. **The model space only grows.** Apple keeps adding on-device options; we bake in more choices as hardware widens; and because Bristlenose is open source, contributors may wire up all sorts of models. The catalogue has to hold *many* cells without letting "many" decay into "unguided".
3. **Knowing about a model ≠ being able to recommend it.** As the cell count climbs, BN needs a first-class way to say "of the many models that *run* on this host, here are the ones we *endorse* for this stage" — without collapsing that judgement into the singular `default`. `recommended` is that mechanism: the architectural answer to managing crazy choice. (The know-vs-recommend distinction is the one Alex Jones's llmfit makes sharp — see the `reference_alex_jones_llmfit.md` memory.)

The progression — v1 → v1.5 → v1.9 → v2 — has built this catalogue surface incrementally and is probably not finished. But the four-axis data model (`default` · `recommended` · `quality` · `source`) is **more than enough for TestFlight**: it ships a legible, honest, out-of-the-box-correct view today and leaves the recommendation-rendering rung (**v3**, see the rung map) ready to land when the evidence and the expanding model space justify it. **Finding 16 is resolved as working-as-intended**, not a gap.

## Honesty about provenance: `source`

Most cells ship `source="editorial"`; the Local (Ollama) rows ship `source="community"` (small-model failure modes are well-known from aggregated researcher reports — `catalogue.py:512+`). The four valid values:

- `editorial` — Bristlenose's subjective opinion. No measurement, no published benchmark, no aggregated community signal. Shipped as a starting point. **The default for any cell with no other evidence** — most cells today.
- `community` — aggregated researcher feedback (e.g. forum reports, cohort discussions). Used for the Local-LLM rows where small-model failure modes are well-known.
- `published_bench` — third-party benchmark (cite in note).
- `internal_bench` — measured on a Bristlenose trial run (FOSSDA corpus or equivalent). The trajectory: as the eval harness in [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §3 ships, ratings flip from `editorial` to `internal_bench` cell by cell.

> **Measurements now exist, and every cell is still `editorial` — deliberately (12 Sep 2026).**
> `experiments/quote-stability/FINDINGS.md` records 4–12 re-extraction passes per shipped
> cloud model through the real stage on FOSSDA. It did **not** flip a single `source`, and
> the reasoning is the durable part of this section:
>
> - **What was measured is one dimension of the judgement.** The harness measures *recovery
>   stability* — whether a quote survives re-analysis on its position key. A rating answers
>   "is this model any good for this stage", which also covers text stability, and text
>   stability is poor on all three cloud models with the *corpus*, not the models, as the
>   leading explanation. Flipping `source` would claim the whole rating is evidenced when a
>   slice of it is.
> - **Unsettled evidence is not evidence.** `gemini-3.8-flash` reads 80.4% union on the
>   padded passes, which looks like a miss, and the findings say in terms not to act on it:
>   scored against a common reference the model is unmoved, and it returns the fewest quotes
>   so each is worth ~1.5% of the figure. ~8 more passes (about $0.63) would settle it.
>   Gemini therefore stays unrated because the evidence is *unsettled*, which is a different
>   reason from the class-judgement call recorded in the 5 Sep changelog entry above.
> - **Read the padded table, never §1's unpadded one.** The unpadded rows are kept for
>   provenance and, for `gpt-5.6-terra`, are measuring garbage — overlap is scored on a
>   timeline and 63% of its timecodes were then 60× wrong. Reading them as current says terra
>   misses the target and Gemini leads. Both are false; a review on 12 Sep proposed acting on
>   exactly that and had to be withdrawn.
>
> So the gap this section names is narrower than it was, not closed: what is missing is not
> *a* measurement but a measurement of the thing the rating claims.

The `source` field is internal context — it ships in the JSON payload for debug / tooling but is **not rendered to users**. The honesty is for us: an audit later can tell which ratings have evidence behind them.

## Apple FM — the third state

Apple FM is intentionally unrated in the catalogue. Its `QualityRating` returns `None`, and the render layer treats this as `?` "untested" — distinct from `⚠` `marginal` (`cli.py:170`; React `bn-pipeline-quality-untested`). When the Swift-side probe ships ([design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §2), apple_fm cells will become `available=True, quality=None` for the first time: a state the React layer must distinguish from any rated cell. Pinned at the data layer in `tests/pipeline_view/test_quality.py::test_unrated_available_backend_is_a_distinct_state`.

**Ordering (v2):** there is **no global quality sort**. Rows stay in catalogue declaration order — providers in declaration order, models in declaration order, synthesised rows appended after their provider's catalogued models (`render.py:318-324`). v1.9's quality-weight sort (which ranked `quality=None` alongside `marginal`) was removed: a read-only catalogue is more legible when its order is stable and predictable than when it silently re-ranks by an editorial axis. Collapsing a provider's rows to one line when they're uniform (single model, or all-unavailable with one shared reason) is a **render-layer** concern (`cli.py:215 _collapse`, React `collapseProvider`); the payload always carries the full per-model list so consumers can filter or collapse themselves.

## Locale convention

New keys land under `pipeline.quality.*` (snake_case nested under `pipeline.<category>.<snake_case_leaf>`). Matches v1.5's precedent at `pipeline.reasons.*` and `pipeline.backends.*` (currently colocated under `settings.json`; the older small `pipeline.json` uses camelCase flat keys and is the outlier — separate housekeeping). **v2 shipped the locale-file fill** across all 6 locales (en/es/fr/de/ko/ja): `pipeline.quality.*` (the glyph + note keys, including `pipeline.quality.glyph.avoid`), the new `pipeline.actions.*` namespace (the `action_key` "what to do about it" hints), and `pipeline.column.*` (the sr-only matrix column headers). Unrated cells fall back to `pipeline.quality.untested`.

See [design-i18n.md](design-i18n.md) §Per-namespace key convention for the full rule.

## Schema versioning

> **`schema_version` is a different number line from the feature rungs — keep them apart deliberately.** The rungs (v1 / v1.5 / v1.9 / v2 / v3 …, see the rung map) track *features*; `schema_version` (an integer: 1 / 2 / 3 / 4) tracks the *JSON payload contract*. They are decoupled in **both** directions, which is the whole reason for two counters: we often change the **schema** with no visible / UX change (an internal payload restructure), and we improve **UX in a feature rung** with no schema change at all (the render-only rungs v3 and v4 ship new chrome over data the schema already carries). So feature **v2** happens to carry **schema 4**, and that coincidence will drift further over time — don't tie one number to the other. Below, "schema N" always means `schema_version`.

`PipelineView.schema_version` is currently `4` (`render.py:55`). The bump policy:

- **Default on fresh build** = `SCHEMA_VERSION` (the current shipping value).
- **Preserve on parse** — Pydantic does not coerce. A parsed schema-2 payload reports `schema_version=2` and round-trips faithfully.
- **A `_migrate_schema` model_validator now exists** (`render.py:148`), but it is a **no-op placeholder**. The Rule-of-Three trigger fired at schema v3 → v4 (third schema transition since v1), so the hook was added as the clean landing site for the *next* non-additive migration. Today nothing actually migrates: schema-3-and-earlier payloads still parse via Pydantic's `extra="ignore"` (the removed `llm_summary` is silently dropped; schema 4's new `model_id` fields default).

Schema bumps are **additive**. Schema 1 → 2 added `llm_summary` + per-stage `alternatives`. 2 → 3 added quality fields + `default` + `recommended` on every row. 3 → 4 split each backend into per-(provider, model) rows (`ModelAvailability` with `model_id` / `provider_display` / `publisher` / `synthesised` / `action_key`) and **removed** `llm_summary` — the one subtractive change, absorbed by `extra="ignore"` on old consumers. Older consumers (schema 1–3) ignore the new fields and keep working. The shape contract is pinned by `tests/fixtures/pipeline-view-contract.json` (four scenarios) and the round-trip tests in `tests/pipeline_view/test_schema_compat.py`.

## What binds the catalogue to reality — and the one thing deliberately unbound

Three mechanisms, and they are not the same kind of thing. The third is the one
that will be "fixed" by mistake.

1. **Cloud model ids are bound to what ships.** `tests/pipeline_view/test_models.py`
   asserts every catalogued cloud id is one `bristlenose/providers.py` defaults to or
   `LLMProvider.swift`'s picker offers, and that the flagged default is the registry's.
   Added 5 Sep 2026 because this catalogue was a **fourth** place model ids are written
   down, and on 4 Sep the other three moved while this one did not — leaving the view
   offering `gemini-2.5-pro`, by then a 404 for new accounts, as Gemini's default.
2. **The Ollama set mirrors the desktop picker's `OllamaCatalog`.** By convention, not
   by test. See [design-gemma4-local-models.md](design-gemma4-local-models.md) for the
   model set and the RAM floors that gate the three Gemma rows.
3. **`tests/fixtures/pipeline-view-contract.json` is bound to nothing, on purpose.** It
   holds ~115 `model_id` values of which ~95 name no catalogued model — retired ids,
   plus deliberate fictions like `claude-opus-5-future` and `qwen2.5:14b`. That is
   correct. The fixture pins the **JSON schema** across the Python/TypeScript boundary:
   `test_schema_compat.py` re-serialises the fixture's own `catalogue` and compares it to
   itself, never to `build_pipeline_view()`. Its ids are scenario data, and freezing them
   is what makes it a contract rather than a snapshot.

   **The hazard is the asymmetry.** Now that (1) exists, a reader who finds stale ids in
   the fixture will reasonably infer the same sweep is owed there. It is not: truing the
   fixture would couple a schema pin to the live catalogue, so every future model bump
   would redden a test that has nothing to say about model bumps, and the pin would be
   quietly retuned until it pinned nothing. **If the fixture's ids ever go stale in a way
   that matters, the schema changed — bump `schema_version` and add a scenario.**

## Why catalogue before resolver

The original Apr 2026 [design-stage-backends.md](design-stage-backends.md) §"Recommendation: don't build the resolver, build the evidence" advised against building the resolver before the evidence existed. v1.5 + v1.9 took a slightly different path: build the **read-only catalogue surface** that shows the user what a resolver would pick, with editorial signal about how good each cell is. Two benefits:

1. **Researchers stay in control.** v1.9 makes signal legible. It does not automate the choice. Per [methodology/consent-gradient.md](methodology/consent-gradient.md) §Level 1+, researchers are adults; we surface signal, they decide.
2. **The catalogue IS the resolver's eventual input.** Whatever auto-pick logic the optimise_for rung (v6) introduces will read `quality_for()` + `recommended` + host facts. Building the surface first means the resolver, when it lands, doesn't have to invent its own knowledge base.

The recommendation to "build the evidence" still stands — `internal_bench` provenance is the gap. v1.9 is the editorial scaffolding that catches the evidence as it arrives. **Narrowed, not closed, on 12 Sep 2026:** evidence now exists for recovery stability and still did not move a single cell. See §"Honesty about provenance: `source`" for why, before promoting anything.

## What shipped in v2

The items v1.9 carried "to the next rung" mostly landed in v2:

- **CLI / React rendering** of the quality glyphs (`✓●` / `✓○` / `✓⚠` / `✗` / `?`) and the inline quality notes — **shipped** (`cli.py:86-97,176`; React `QUALITY_GLYPH` + `whyText`).
- **Locale-file fill** — **shipped** across all **21 full locales** (6 at v2; `zh-Hant-HK` carries only genuine HK overrides and inherits the rest by design). See §Locale convention.
- **The summary-card-vs-per-stage decision for LLM-stage quality** — **resolved: per-stage rendering won**, reversing v1.5's LLM-stage dedup. `_build_llm_summary` was deleted (deletion pinned by `tests/pipeline_view/test_models.py::test_build_llm_summary_function_does_not_exist`), so the "Local looks `good` because the card templated off `speaker_identification`" trap is gone — each stage now shows its own per-model quality (Local `good` for structural stages, `marginal` for synthesis).
- **The "available + untested" (`?`) rendering** for the apple_fm probe path — **shipped** at the render layer (`cli.py:170`). The Swift-side probe that will flip apple_fm to `available=True` is still pending (see [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §2).

## The rung map (v3 → v6)

The pipeline view grows in deliberate increments. The discipline: stay
read-only and let the surface + the data earn trust first; user control and
the `optimise_for` axis come last. Each rung below is a feature rung, *not* a
`schema_version` (see §Schema versioning — the render-only rungs v3 and v4
don't bump the schema).

- **v3 — render all the data.** Surface the catalogued-but-currently-unrendered signal: the `recommended` marker (carried since v2 but shown by no badge — see §"Why `recommended` is foundational, not dead weight") and the orphaned positive / transcription quality notes. No new data; just expose what v2 already captures.
- **v4 — desktop (Swift) surface.** Render the same read-only view natively in the macOS app, under "Advanced Settings" (or similar). **No functionality change** — a Swift read-only mirror of the React / CLI view.
- **v5 — manual model choice.** Let users pick, per stage, between the models the catalogue shows as available. This is the first rung where the view stops being purely read-only.
- **v6 — `optimise_for`, simplest form.** A single **speed ↔ quality** slider that moves multiple stages up and down that axis at once, as a master controller — like a macro on a digital synthesiser (a Yamaha DX): one knob, many parameters moving together. This is the simplest possible expression of the `optimise_for` axis (cost / speed / privacy / determinism); the full multi-axis form, per-stage TOML overrides (`[llm_stages]` in [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md)), and any auto-pick resolver remain further out.

### Provider naming — keep product names (deferred: account-vs-product + logos)

**Decision (4 Jun 2026):** provider headings stay **product names** (Claude,
ChatGPT, Gemini, Azure OpenAI, Ollama), matching the desktop provider picker,
the CLAUDE.md convention, and the vendors' own branding (Anthropic brands its
platform "Claude", not "Anthropic"). Press register says "Anthropic"; day-to-day
people say "Claude". The **account/billing identity** ("who you pay") is carried
by the **vendor domain link** already shown in the desktop provider detail
(`anthropic.com` / `openai.com` · Pricing · Keys), not by renaming the heading.

**Parked (post-TestFlight):** a possible account-vs-product rename (company
headings + product on the model rows) and **vendor logos** in the pipeline view
(the desktop picker already uses logo + product name). Both are deliberately
deferred — the desktop settings view is ~95% of users; the pipeline deep view
is a freshly-working edge case we don't want to destabilise before the macOS
TestFlight. Rough scope if revisited: `bristlenose/providers.py` (`display_name`
×5), `bristlenose/llm/billing_hints.py`, the Settings → API Keys labels
(`frontend/src/components/SettingsModal.tsx`), `doctor.py`, CLI help in
`bristlenose/cli.py`, the `pipeline.reasons.*` / `pipeline.backends.*` keys ×6
locales, and the CLAUDE.md provider-naming convention itself.

## File map

| Concern | Path |
|---|---|
| Catalogue (per-stage backends + ratings) | `bristlenose/pipeline_view/catalogue.py` |
| Host probe (eligibility inputs) | `bristlenose/pipeline_view/host.py` |
| Eligibility predicates | `bristlenose/pipeline_view/eligibility.py` |
| Render (`PipelineView` payload, per-model rows) | `bristlenose/pipeline_view/render.py` |
| CLI command | `bristlenose/pipeline_view/cli.py` |
| Tests | `tests/pipeline_view/` |
| Contract fixture | `tests/fixtures/pipeline-view-contract.json` |

## See also

- [design-stage-backends.md](design-stage-backends.md) — the architectural principle (capability × profile, resolver, A/B spike plan)
- [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) — the full routing roadmap (TOML, eval harness, Apple FM Swift bridge)
- [design-research-methodology.md](design-research-methodology.md) §Backend quality scale — canonical 4-level scale + marginal metaphor + axes
- [design-decisions.md](design-decisions.md) — the "why" entries for the scale + axes
- [design-i18n.md](design-i18n.md) §Per-namespace key convention — locale rule for `pipeline.<category>.<leaf>`
- [methodology/consent-gradient.md](methodology/consent-gradient.md) — autonomy framing the plural `recommended` axis instantiates
