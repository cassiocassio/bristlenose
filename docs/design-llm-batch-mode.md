# LLM Batch Mode — considered, parked

_7 Jul 2026_

**Decision: don't adopt the async LLM Batch API for alpha, and not for the default interactive path at all. Revisit post-Beta as an explicit opt-in "overnight" mode, gated on cohort signal (someone running large corpora *and* flagging cost).** This doc records the fit analysis so the question isn't re-litigated from scratch next time it comes up.

## What "batch mode" means here

The provider batch APIs — Anthropic [Message Batches](https://platform.claude.com/docs/en/build-with-claude/batch-processing), OpenAI Batch, Gemini Batch — are the same shape: submit a job file, poll, retrieve. **~50% off, asynchronous, up-to-24h turnaround, no streaming.** The discount is the draw; the async-ness is the whole cost.

This is a different thing from ROADMAP #27 "Batch processing — queue multiple projects", which is queueing multiple *Bristlenose projects* back-to-back (still synchronous, still streaming per project). If async LLM batching is ever built it needs a distinct name to avoid that collision.

## Why it's a poor fit for the default path

1. **The live-progress UX is the product, not a nice-to-have.** The CLI has per-stage Welford timing; the desktop app has the whole sidebar/analysis progress story. The batch API is submit-and-wait with no per-item progress and no streaming. Adopting it for the default run trades the core interactive experience for a cost saving on runs that are already cheap.

2. **The pipeline is staged with hard data dependencies, so batch only helps *within* a stage.** topic-segmentation → quote-extraction → clustering → theming: each stage consumes the prior stage's output. You can't batch across the dependency chain. The only place batch buys anything is the fan-out *inside* a single stage.

3. **That fan-out is already concurrent and synchronous.** [s09_quote_extraction.py:125](../bristlenose/stages/s09_quote_extraction.py#L125) already runs an `asyncio.Semaphore(concurrency)` + `asyncio.gather` over transcripts, and the SDK retry/backoff layer ([llm/client.py:120](../bristlenose/llm/client.py#L120)) already honours `Retry-After`. So the latency win batch would offer over serial calls we mostly already have — concurrently, synchronously, with progress. Batch would be a *cost* win, not a *speed* win, and cost isn't the bottleneck.

4. **Fail-stop consent-integrity gets harder.** The model is "provider failure stops and asks, no silent failover." A batch that partially fails 40 minutes after submission is much harder to surface into that contract than a synchronous exception caught in the gather loop.

5. **Small-N reality + user's own key.** Alpha runs are a handful of interviews on the user's own API key. 50% of a small number is a smaller number. **Ollama has no batch concept** — the free local path is unaffected either way.

6. **4× provider surface.** Each batch API is a different submit/poll/retrieve shape with different formats and limits. That's a whole second dispatch path to build and maintain alongside the sync one — against the "exercise the existing 5 providers" alpha posture, for no alpha-relevant gain.

## Prior mentions in the tree (all point the same way)

Batch has only ever been touched as a **cost-estimation accuracy** footnote, never as a processing mode:

- [design-llm-pricing-fetch.md:191](design-llm-pricing-fetch.md#L191) — lists "Tiered / batch / cache-token pricing" under *Out of scope (v2 candidates)*: "Anthropic's batch API is half price… The forecast under-counts these savings today." The concern there is that our cost *forecast* under-counts what a batch user would save — not using batch ourselves.
- [design-llm-call-telemetry.md:665](design-llm-call-telemetry.md#L665) — "batch tiers" listed among the invisible billing adjustments that keep `cost_usd_actual_estimate` an estimate. Pure accounting caveat.

## Where it could earn its place — later

One legitimate future shape: an **explicit opt-in "overnight / batch" mode** for large corpora — someone drops 40 interviews, doesn't need to watch it stream, wants the cost cut and will come back tomorrow. A distinct mode with its own UX (submit → "we'll notify you when it's done"), **not** a swap-in for the default runner.

Revisit trigger (both, not either): a cohort tester is actually running large corpora, **and** flags cost as a pain. Until both hold it's neither the hard differentiating problem nor a validated ask.
