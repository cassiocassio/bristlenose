---
status: partial
last-trued: 2026-06-04
trued-against: HEAD@pipeline-view-models (working tree — v2 uncommitted) on 2026-06-04
---

> **Truing status:** Partial — trued v1.9 → v2 on 2026-06-04 against the
> (uncommitted) v2 working tree. The catalogue, two-layer, schema, provenance,
> Apple-FM, locale, and "did not ship" sections are now current. The
> §"Why `recommended` is foundational, not dead weight" subsection is current. One rung remains
> genuinely unshipped: the **`recommended`-marker rendering** (data + JSON +
> tests ship it; no CLI/React badge yet). See changelog + inline notes.

## Changelog

- _2026-06-04_ — trued up v1.9 → v2: schema 3→4 + per-(provider, model) grain
  (`ModelOption` on `BackendOption.models`); `BackendAvailability` → `ModelAvailability`,
  `reason` → `reason_key` + new `action_key`; `llm_summary` deleted (per-stage
  rendering); CLI/React glyph + 6-locale rendering shipped; dead sort-weight
  section replaced with the declaration-order + collapse-when-uniform invariant;
  untested glyph `⚠` → `?`; provenance now editorial + community; `_migrate_schema`
  hook added (Rule-of-Three fired at schema v3→v4). `recommended`-marker rendering remains
  the sole outstanding rung. Anchors: `render.py:55,58,138,148,318`,
  `catalogue.py:68,117`, `cli.py:170,188`, `test_models.py:45`, four-scenario
  `pipeline-view-contract.json`.
- _2026-05-25_ — initial v1.9 truing (`git log` `8dfda74`).

# Design: Pipeline view — read-only catalogue surface

**Status (4 Jun 2026):** v1.5, v1.9, and v2 shipped. The Pipeline view is the **read-only catalogue surface** that tells a researcher, at a glance, which backends Bristlenose could use for each stage on the current host, which it actually picks by default, which it editorially endorses, and how good each one is for the job. It is **not** the resolver — choosing per-stage backends is still owned by the user via global `llm_provider` (LLM stages) + the host-aware resolver in `s05_transcribe._resolve_backend` (transcription). The CLI rendering, the React Settings surface, the quality glyphs, and the 6-locale fill all shipped in **v2**, now at per-(provider, model) grain. The next rung is **v3** — render the `recommended` marker (see §"Why `recommended` is foundational, not dead weight"); the `optimise_for` axis (cost / speed / privacy / determinism) is deferred to v6 (see the rung map below).

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

v1.5 and v1.9 evaluated eligibility + quality per *backend* (provider family), and the five LLM stages shared one deduped summary card. v2 pushes the grain down to the individual **model**: `BackendOption` now holds `models: list[ModelOption]` (`catalogue.py:117`), eligibility + quality resolve per (stage, provider, model), and each stage carries a flat `alternatives` list of `ModelAvailability` rows (`render.py:58`) instead of the deleted `llm_summary` card. This is what lets the catalogue say "Claude offers Sonnet 4 (the default) *and* Opus 4 (also endorsed)" rather than collapsing the provider to one line.

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

**v2 (per-model grain):** each provider expands into its catalogued models, and v2 is the **first build where `recommended ≠ default` fires** — Claude is endorsed at *two* models (Sonnet 4 the default, Opus 4 recommended-but-not-default), and gpt-4o is recommended without being the default (`catalogue.py:500-505`):

| Provider | Model | `available` | `quality` | `default` | `recommended` |
|---|---|---|---|---|---|
| Claude | Sonnet 4 | ✓ | excellent | **true** | **true** |
| Claude | Opus 4 | ✓ | excellent | false | **true** |
| ChatGPT | gpt-4o | ✓ | excellent | false | **true** |
| Gemini | 2.5 Pro | ✓ | good | false | false |
| Local | llama3.2:3b | ✓ | marginal | false | false |

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

The `source` field is internal context — it ships in the JSON payload for debug / tooling but is **not rendered to users**. The honesty is for us: an audit later can tell which ratings have evidence behind them.

## Apple FM — the third state

Apple FM is intentionally unrated in the catalogue. Its `QualityRating` returns `None`, and the render layer treats this as `?` "untested" — distinct from `⚠` `marginal` (`cli.py:170`; React `bn-pipeline-quality-untested`). When the Swift-side probe ships ([design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §2), apple_fm cells will become `available=True, quality=None` for the first time: a state the React layer must distinguish from any rated cell. Pinned at the data layer in `tests/pipeline_view/test_quality.py::test_unrated_available_backend_is_a_distinct_state`.

**Ordering (v2):** there is **no global quality sort**. Rows stay in catalogue declaration order — providers in declaration order, models in declaration order, synthesised rows appended after their provider's catalogued models (`render.py:318-324`). v1.9's quality-weight sort (which ranked `quality=None` alongside `marginal`) was removed: a read-only catalogue is more legible when its order is stable and predictable than when it silently re-ranks by an editorial axis. Collapsing a provider's rows to one line when they're uniform (single model, or all-unavailable with one shared reason) is a **render-layer** concern (`cli.py:215 _collapse`, React `collapseProvider`); the payload always carries the full per-model list so consumers can filter or collapse themselves.

## Locale convention

New keys land under `pipeline.quality.*` (snake_case nested under `pipeline.<category>.<snake_case_leaf>`). Matches v1.5's precedent at `pipeline.reasons.*` and `pipeline.backends.*` (currently colocated under `settings.json`; the older small `pipeline.json` uses camelCase flat keys and is the outlier — separate housekeeping). **v2 shipped the locale-file fill** across all 6 locales (en/es/fr/de/ko/ja): `pipeline.quality.*` (the glyph + note keys, including `pipeline.quality.glyph.avoid`), the new `pipeline.actions.*` namespace (the `action_key` "what to do about it" hints), and `pipeline.column.*` (the sr-only matrix column headers). Unrated cells fall back to `pipeline.quality.untested`.

See [design-i18n.md](design-i18n.md) §Per-namespace key convention for the full rule.

## Schema versioning

> **`schema_version` is a different number line from the feature rungs.** The rungs (v1 / v1.5 / v1.9 / v2 / v3 …, see the rung map) track *features*; `schema_version` (an integer: 1 / 2 / 3 / 4) tracks the *JSON payload contract*. They move independently — feature **v2** happens to carry **schema 4**, and the render-only rungs v3 and v4 won't bump the schema at all. Below, "schema N" always means `schema_version`.

`PipelineView.schema_version` is currently `4` (`render.py:55`). The bump policy:

- **Default on fresh build** = `SCHEMA_VERSION` (the current shipping value).
- **Preserve on parse** — Pydantic does not coerce. A parsed schema-2 payload reports `schema_version=2` and round-trips faithfully.
- **A `_migrate_schema` model_validator now exists** (`render.py:148`), but it is a **no-op placeholder**. The Rule-of-Three trigger fired at schema v3 → v4 (third schema transition since v1), so the hook was added as the clean landing site for the *next* non-additive migration. Today nothing actually migrates: schema-3-and-earlier payloads still parse via Pydantic's `extra="ignore"` (the removed `llm_summary` is silently dropped; schema 4's new `model_id` fields default).

Schema bumps are **additive**. Schema 1 → 2 added `llm_summary` + per-stage `alternatives`. 2 → 3 added quality fields + `default` + `recommended` on every row. 3 → 4 split each backend into per-(provider, model) rows (`ModelAvailability` with `model_id` / `provider_display` / `publisher` / `synthesised` / `action_key`) and **removed** `llm_summary` — the one subtractive change, absorbed by `extra="ignore"` on old consumers. Older consumers (schema 1–3) ignore the new fields and keep working. The shape contract is pinned by `tests/fixtures/pipeline-view-contract.json` (four scenarios) and the round-trip tests in `tests/pipeline_view/test_schema_compat.py`.

## Why catalogue before resolver

The original Apr 2026 [design-stage-backends.md](design-stage-backends.md) §"Recommendation: don't build the resolver, build the evidence" advised against building the resolver before the evidence existed. v1.5 + v1.9 took a slightly different path: build the **read-only catalogue surface** that shows the user what a resolver would pick, with editorial signal about how good each cell is. Two benefits:

1. **Researchers stay in control.** v1.9 makes signal legible. It does not automate the choice. Per [methodology/consent-gradient.md](methodology/consent-gradient.md) §Level 1+, researchers are adults; we surface signal, they decide.
2. **The catalogue IS the resolver's eventual input.** Whatever auto-pick logic the optimise_for rung (v6) introduces will read `quality_for()` + `recommended` + host facts. Building the surface first means the resolver, when it lands, doesn't have to invent its own knowledge base.

The recommendation to "build the evidence" still stands — internal_bench provenance is the gap. v1.9 is the editorial scaffolding that catches the evidence as it arrives.

## What shipped in v2

The items v1.9 carried "to the next rung" mostly landed in v2:

- **CLI / React rendering** of the quality glyphs (`✓●` / `✓○` / `✓⚠` / `✗` / `?`) and the inline quality notes — **shipped** (`cli.py:86-97,176`; React `QUALITY_GLYPH` + `whyText`).
- **Locale-file fill** — **shipped** across all 6 locales (see §Locale convention).
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
