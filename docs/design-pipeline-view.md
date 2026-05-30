---
status: partial
last-trued: 2026-05-25
trued-against: HEAD@pipeline-view-v1-9 on 2026-05-25
---

# Design: Pipeline view — read-only catalogue surface

**Status (25 May 2026):** v1.5 and v1.9 shipped. The Pipeline view is the **read-only catalogue surface** that tells a researcher, at a glance, which backends Bristlenose could use for each stage on the current host, which it actually picks by default, which it editorially endorses, and how good each one is for the job. It is **not** the resolver — choosing per-stage backends is still owned by the user via global `llm_provider` (LLM stages) + the host-aware resolver in `s05_transcribe._resolve_backend` (transcription). Future rungs add the React surface for the new badges, the CLI rendering, and the locale-file fill. v2's `optimise_for` axis (cost / speed / privacy / determinism) is explicitly deferred.

**Related:** [design-stage-backends.md](design-stage-backends.md) (architectural principle — capability declaration + resolver), [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) (full routing roadmap, mostly still aspirational), [design-research-methodology.md](design-research-methodology.md) §Backend quality scale (canonical home for the 4-level scale + axes), [design-decisions.md](design-decisions.md) (the "why" for the scale + orthogonal axes), [design-i18n.md](design-i18n.md) (locale convention for `pipeline.<category>.<leaf>`).

## Why this doc exists

The Pipeline view is the user-visible mirror of [design-stage-backends.md](design-stage-backends.md)'s "capability declaration" principle. It started life inside `design-cli-improvements.md` as a one-section idea for the CLI; v1 shipped it in the React Settings → Pipeline tab; v1.5 extended it with per-stage **alternatives** and eligibility predicates; v1.9 adds **editorial quality ratings**. The shipped surface now warrants its own design doc — both because it's grown enough to deserve a self-contained explanation, and because [design-stage-backends.md](design-stage-backends.md) and [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) point at it as a downstream artefact.

## What the Pipeline view is

A **read-only JSON payload** (`PipelineView` in `bristlenose/pipeline_view/render.py`) consumed by the React Settings → Pipeline tab and the CLI `bristlenose pipeline` command. For each user-visible stage it answers four questions:

1. **What does this stage currently use?** — the `StageSelection.chosen` string, derived from `BristlenoseSettings` + host-aware resolvers. Single source of truth: matches what `bristlenose run` would dispatch.
2. **What else could it use on this host?** — `StageSelection.alternatives` (or `llm_summary` for the 5 LLM stages, deduped). Each `BackendAvailability` has `available: bool` + a translation-key `reason` when not.
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

## The orthogonal axes

Four axes on every `QualityRating`. Independent on purpose — collapsing them sacrifices honest signal.

| Axis | Type | Plurality | Meaning |
|---|---|---|---|
| `rating` | `excellent` / `good` / `marginal` / `avoid` | one per cell | Fitness for purpose at this stage |
| `default` | bool | **singular** per (stage, provider-family) | What BN runs if user changes nothing |
| `recommended` | bool | **plural by design** | Cells BN actively endorses as production choices |
| `source` | `internal_bench` / `published_bench` / `community` / `editorial` | one per cell | Where the rating came from |

**Invariant:** `default ⇒ recommended`. BN cannot default to a cell it does not actively endorse. Recommended is strictly wider than default; both are subsets of `rating ∈ {excellent, good}` (BN never defaults to or recommends `marginal` / `avoid`).

See [design-research-methodology.md](design-research-methodology.md) §Backend quality scale for the canonical definitions of the four rating levels (including the verbatim metaphor for `marginal`), and [design-decisions.md](design-decisions.md) §Pipeline and analysis for the "why" behind each axis choice.

### Worked example — default vs recommended

A researcher opens the Pipeline view for *quote_extraction* with all four cloud keys + Ollama configured. v1.9 emits:

| Backend | `available` | `quality` | `default` | `recommended` | What renders |
|---|---|---|---|---|---|
| Claude | ✓ | excellent | **true** | **true** | `✓●★ Claude — BN's pick` |
| ChatGPT | ✓ | excellent | false | false | `✓● ChatGPT` |
| Azure OpenAI | ✓ | good | false | false | `✓○ Azure OpenAI` |
| Gemini | ✓ | good | false | false | `✓○ Gemini` |
| Local (Ollama) | ✓ | marginal | false | false | `✓⚠ Local (Ollama) — small models miss multi-clause quotes` |
| Apple FM | ✗ | — | false | false | `✗ Apple FM — check in the desktop app` |

Today, only Claude is flagged `recommended=true` because that's the only cell we have evidence for. As cohort data arrives — "ChatGPT is genuinely production-grade for quote extraction", or "Local on a 30B+ model now handles structural stages well" — we flip the relevant `recommended` flag without touching `default`. The view becomes more permissive over time; the singular default stays singular.

### Why this matters

Without separating the axes:

- **Researchers see a monolithic choice.** "Claude is the default; everything else is just 'available with quality X'." The default's authority outshines every other option even when BN would happily endorse two or three of them.
- **Cohort signal accumulates nowhere.** Saying "ChatGPT is also fine for this stage" requires either changing the default (singular — wrong tool) or adding a new axis (which we'd then have to invent under pressure).
- **The autonomy framing breaks.** [methodology/consent-gradient.md](methodology/consent-gradient.md) §"Default to professional norms" commits to "researchers are adults". A plural `recommended` is the architectural form of that commitment — "these are all in-bounds production choices; pick what fits your constraints."

## Honesty about provenance: `source`

All v1.9 cells ship `source="editorial"`. The four valid values:

- `editorial` — Bristlenose's subjective opinion. No measurement, no published benchmark, no aggregated community signal. Shipped as a starting point. **This is what we have today.**
- `community` — aggregated researcher feedback (e.g. forum reports, cohort discussions). Used for the Local-LLM rows where small-model failure modes are well-known.
- `published_bench` — third-party benchmark (cite in note).
- `internal_bench` — measured on a Bristlenose trial run (FOSSDA corpus or equivalent). The trajectory: as the eval harness in [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §3 ships, ratings flip from `editorial` to `internal_bench` cell by cell.

The `source` field is internal context — it ships in the JSON payload for debug / tooling but is **not rendered to users**. The honesty is for us: an audit later can tell which ratings have evidence behind them.

## Apple FM — the third state

Apple FM is intentionally unrated in the v1.9 catalogue. Its `QualityRating` returns `None`, and the render layer treats this as ⚠ "untested" — distinct from `marginal`. When the Swift-side probe ships ([design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §2), apple_fm cells will become `available=True, quality=None` for the first time: a state the React layer must distinguish from any rated cell. Pinned at the data layer in `tests/pipeline_view/test_quality.py::test_unrated_available_backend_is_a_distinct_state`.

The sort weight for `quality=None` sits with `marginal` (both weight 2) — so unrated cells sort below rated `good` and rated `excellent` but above rated `avoid`. This is the conservative choice: never silently promote an unmeasured cell to excellent-equivalent rank.

## Locale convention

New keys land under `pipeline.quality.*` (snake_case nested under `pipeline.<category>.<snake_case_leaf>`). Matches v1.5's precedent at `pipeline.reasons.*` and `pipeline.backends.*` (currently colocated under `settings.json`; the older small `pipeline.json` uses camelCase flat keys and is the outlier — separate housekeeping). Locale-file fill is deferred to a later rung; v1.9 ships the catalogue keys only, with a render-layer fallback to `pipeline.quality.untested` for unrated cells.

See [design-i18n.md](design-i18n.md) §Per-namespace key convention for the full rule.

## Schema versioning

`PipelineView.schema_version` is currently `3`. The bump policy:

- **Default on fresh build** = `SCHEMA_VERSION` (the current shipping version).
- **Preserve on parse** — Pydantic does not coerce. A parsed v2 payload reports `schema_version=2` and round-trips faithfully.
- **No model_validator that bumps on parse.** Speculative generality for a versioning story that has had two transitions (1 → 2, 2 → 3) so far. Rule of Three: write the migration policy when there's a third transition.

Schema bumps are **additive**. v1 → v2 added `llm_summary` + per-stage `alternatives`. v2 → v3 added quality fields + `default` + `recommended` on every `BackendAvailability`. Older consumers (v1, v2) ignore the new fields and keep working. The shape contract is pinned by `tests/fixtures/pipeline-view-contract.json` (three scenarios) and the round-trip tests in `tests/pipeline_view/test_schema_compat.py`.

## Why catalogue before resolver

The original Apr 2026 [design-stage-backends.md](design-stage-backends.md) §"Recommendation: don't build the resolver, build the evidence" advised against building the resolver before the evidence existed. v1.5 + v1.9 took a slightly different path: build the **read-only catalogue surface** that shows the user what a resolver would pick, with editorial signal about how good each cell is. Two benefits:

1. **Researchers stay in control.** v1.9 makes signal legible. It does not automate the choice. Per [methodology/consent-gradient.md](methodology/consent-gradient.md) §Level 1+, researchers are adults; we surface signal, they decide.
2. **The catalogue IS the resolver's eventual input.** Whatever auto-pick logic v2 introduces will read `quality_for()` + `recommended` + host facts. Building the surface first means the resolver, when it lands, doesn't have to invent its own knowledge base.

The recommendation to "build the evidence" still stands — internal_bench provenance is the gap. v1.9 is the editorial scaffolding that catches the evidence as it arrives.

## What v1.9 deliberately did not ship

Carried to the next rung:

- **CLI / React rendering** of the new glyphs (`✓●` / `✓○` / `✓⚠`), the BN-recommended marker, and the inline quality notes. Data shipped; rendering is the next rung.
- **Locale-file fill** of the 8 `pipeline.quality.*` keys × 6 locales = 48 strings. Catalogue references the keys; locales catch up next.
- **The summary-card-vs-per-stage decision for LLM-stage quality** — `_build_llm_summary` currently uses `speaker_identification` as template, which paints `local` as `good` even though it's `marginal` for the three synthesis stages. Three options open: optimistic single-card signal, min-fold across stages, or per-stage rendering that reverses v1.5's dedup. Decided in the next rung's plan.
- **The "available + untested" rendering** for the apple_fm probe path. Pinned at the data layer; React layer renders next.

Carried to v2 (`optimise_for` axis):

- **Cost / speed / privacy / determinism** as orthogonal axes. v1.9 quality is "is it any good for the job?"; v2 is "given that it's good enough, what trade-off matters?"
- **Per-stage user overrides** via TOML (`[llm_stages]` block in [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md)) and a UI for off-piste configurations.
- **The auto-pick resolver itself** — once `optimise_for` exists, BN can pick a default cell per (stage, preference) pair.

## File map

| Concern | Path |
|---|---|
| Catalogue (per-stage backends + ratings) | `bristlenose/pipeline_view/catalogue.py` |
| Host probe (eligibility inputs) | `bristlenose/pipeline_view/host.py` |
| Eligibility predicates | `bristlenose/pipeline_view/eligibility.py` |
| Render (`PipelineView` payload + sort) | `bristlenose/pipeline_view/render.py` |
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
