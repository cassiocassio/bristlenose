# Design: Per-stage pluggable LLM/ASR backends

**Status (20 Apr 2026):** Evidence-gathering stage. Per-stage wall-time and LLM-time breakdowns captured via [`scripts/perf-breakdown.py`](../scripts/perf-breakdown.py) on FOSSDA and project-ikea. This doc frames the architectural principle, records what the numbers actually say, surveys the Mac-side on-device trajectory (Apple FM, MLX, M5), and proposes a narrow A/B spike on the dominant stage (s10 `quote_extraction`) before any resolver or provider-registry work begins. The spike is explicitly designed as a **re-runnable benchmark** we re-measure at each Apple release and each Claude generation — not a one-shot comparison.

## Problem

The pipeline is pluggable at the **provider level** today — one `LLMClient` backend for the whole run, chosen once via `BristlenoseSettings.llm_provider` — and the LLM provider abstraction covers five backends (Anthropic, OpenAI, Azure, Google, local Ollama). It is **not** pluggable at the **stage level**.

That matters because:

- Hosts vary: Mac + Apple Silicon, Linux + NVIDIA, cloud-only laptop, locked-down enterprise. No single backend is right for every stage on every host.
- Stages vary: some want short-context structured output (fast local models do well), some want long-context synthesis (only capable cloud models do well).
- Costs concentrate: in real runs, one stage dominates both wall time and LLM spend — the right lever is at the stage level, not the run level.

The user has also signalled a preference: **free + bring-your-own-key CLI forever; the Mac app is the commercial product**. Mac-specific on-device acceleration (Apple Foundation Models, SpeechAnalyzer) is exactly the right kind of platform differentiation for the commercial product, without undermining the open CLI. That's only coherent if backend selection is per-stage and platform-aware.

## Evidence: per-stage breakdown

Numbers from [`scripts/perf-breakdown.py`](../scripts/perf-breakdown.py), reading `.bristlenose/pipeline-manifest.json` (started_at / completed_at per stage) and `.bristlenose/bristlenose.log` (`llm_request | ... | elapsed_ms=N` lines). LLM seconds are bucketed into the stage whose interval contains each log line's timestamp.

### FOSSDA (10 sessions, ~7 hours audio, MLX Whisper on M2 Max, Claude Sonnet)

```
total wall:  2208.4s     total llm:  3133.5s   (141.9% of wall — async concurrency within stages)

stage                    wall s  wall %     llm s   llm %  calls
----------------------------------------------------------------
ingest                      0.4    0.0%       0.0    0.0%      0
extract_audio               9.4    0.4%       0.0    0.0%      0
transcribe               1041.1   47.1%       0.0    0.0%      0
identify_speakers          39.5    1.8%     100.8    3.2%     20
merge_transcript            0.0    0.0%       0.0    0.0%      0
topic_segmentation         35.9    1.6%     101.3    3.2%     10
quote_extraction         1050.5   47.6%    2897.6   92.5%     10
cluster_and_group          27.1    1.2%      33.7    1.1%      2
render                      4.5    0.2%       0.0    0.0%      0
```

### project-ikea (short, cached — only 2 LLM calls ran)

```
stage                    wall s  wall %
--------------------------------------
transcribe                 58.7   48.3%
quote_extraction           37.7   31.1%
cluster_and_group           9.1    7.5%
identify_speakers           7.7    6.3%
topic_segmentation          7.4    6.1%
everything else            <1%
```

### What the numbers say

- **Transcribe and quote-extraction together are 95% of wall time.** Everything else is a rounding error.
- **Quote-extraction is 92.5% of total LLM time on FOSSDA.** One stage is effectively the whole LLM workload.
- **The LLM time > wall time ratio is ~1.4×** — real async concurrency inside stages. Useful to remember when reasoning about cost (linear in tokens, not wall time) vs latency (gated by concurrency).
- **Clustering and thematic grouping are cheap.** I had guessed ~25–35% of LLM time between them; reality is ~1%. They're few calls with moderate context.

### Known caveats

- Bucketing is by timestamp-falls-in-stage-interval. Good enough for coarse attribution; can mis-bucket during overlapping async work.
- **LLM seconds is a cost proxy, not a cost.** Real $ depends on input vs output token ratios, which vary wildly by stage. To get truth, `LLMClient` needs to emit token counts — cheap to add, deferred.
- One-run-per-project sample. Re-run to see variance.

## Teams / Zoom implication

Teams and Zoom exports ship users with a transcript (VTT/SRT or platform-specific text) — **s05 `transcribe` is skipped entirely**. This is expected to be the common path, not an edge case, because the kinds of researchers Bristlenose targets are running remote interviews on those platforms and already have the transcript file before Bristlenose is even opened.

Strip the 1041s transcribe slice out of FOSSDA:

| stage | wall % (no s05) |
|---|---|
| **quote_extraction** | **~90%** |
| identify_speakers | ~3% |
| topic_segmentation | ~3% |
| cluster_and_group | ~2% |
| everything else | ~2% |

So on a Teams/Zoom run, **s10 is essentially the entire runtime and essentially the entire LLM cost**. The "drop the Teams folder in, get a report in a minute" demo moment depends entirely on making s10 fast on that path.

## The Mac-side on-device landscape

Treating "on-device on Mac" as a single option is wrong. There are three tiers, with very different quality ceilings and setup costs. The spike needs all three in the slate.

### Tier 1 — Apple Foundation Models

Apple shipped Foundation Models at WWDC 2025. For Bristlenose-on-Mac it offers:

- **~3B parameter on-device LLM** via `LanguageModelSession` (Swift-only)
- **`@Generable` guided generation** producing typed structs (equivalent to our Pydantic schemas)
- **Tool calling, streaming**
- **~4k token context** — the defining constraint
- **Free, private, offline, fast on the Neural Engine**
- **macOS 26+, Apple Silicon only**
- **Zero user setup** — ships with the OS

This is the "it just works" path for Mac users. Whether it is *good enough* for s10 is an open question today; whether it's good enough after WWDC 2026 is a stronger open question.

### Tier 2 — MLX + open-weights models

Apple Machine Learning Research published a benchmark in November 2025 showing M5 LLM inference performance via MLX ([exploring-llms-mlx-m5](https://machinelearning.apple.com/research/exploring-llms-mlx-m5)). Headline numbers:

- **M5 vs M4**: 3.33× to 4.06× time-to-first-token (TTFT) speedup on Qwen 1.7B/8B BF16, 8B/14B 4-bit, Qwen 30B MoE, and GPT-OSS 20B MoE
- **14B dense model**: TTFT under 10 seconds at 4k context on a 24GB M5 MacBook Pro
- **30B MoE**: TTFT under 3 seconds at 4k context
- **Memory bandwidth**: 120 GB/s (M4) → 153 GB/s (M5), +28%, driving 19–27% generation-speed gains
- **Dedicated Neural Accelerators** for matmul — architectural investment, not a one-off
- **24GB M5** comfortably runs 14B BF16 or 30B MoE-4bit under 18GB

Why this matters for s10 specifically: the stage calls the LLM once per session to produce a bounded JSON struct. Output is modest, not thousands of streamed tokens. So **TTFT is the axis we care about, not sustained generation speed** — which happens to be the compute-bound axis Apple is investing in most heavily. The 4× TTFT gain lands squarely on Bristlenose's workload shape.

Note also that Apple's own benchmark uses 4k context. That is not a coincidence — 4k is the regime Apple is optimising for today, and the most likely direction of WWDC 2026 announcements.

MLX is already in the repo as the Whisper backend (`mlx-community/whisper-large-v3-turbo` in s05). Adding `mlx-lm` for LLM inference is a pip dep plus a thin provider wrapper in [bristlenose/llm/client.py](../bristlenose/llm/client.py) — no Swift shim required. This is the cheapest on-device arm to add to the spike.

### Tier 3 — Ollama + open-weights models

Same open-weight models as Tier 2, but via Ollama's generic HTTP interface. Already wired up as the `local` provider. Relevant as the **generic on-device story** a Linux or Windows user gets — not platform-specific to Mac, but the floor beneath which MLX must outperform for a Mac claim to be meaningful.

### Adjacent on-device APIs (not s10)

Worth remembering when the resolver conversation returns:

- **SpeechAnalyzer** (macOS 26) — on-device ASR, plausible Whisper alternative for s05 on Mac
- **NLTagger** — on-device NER, useful as PII pre-pass before FM judgement
- **Vision** — OCR and face detection, relevant to later video-frame work

### Strategic trajectory (not a reason to delay the spike; a reason to build it as a benchmark)

Two curves are rising simultaneously:

| | Cloud (Claude et al.) | On-device (Apple FM, MLX) |
|---|---|---|
| Quality | Steady rise; already high | Steep rise from a lower base |
| Cost | Tends to fall (Haiku class gets better) | Zero marginal, always |
| Latency | Network-bound, roughly stable | Improves with hardware (M5, M6, NE gens) |
| Context | Expanding fast (1M+) | Expanding slowly (4k → maybe 16k → ?) |
| Privacy | Trust-based | Architectural |

Anchor dates on our horizon:

- **WWDC 2026 (8 June)** — FM improvements highly likely; context-window bump is the obvious headline
- **M5 products already in market (Nov 2025)** — the MLX numbers above are achievable today
- **macOS 27 / iOS 27 developer beta (July 2026), public release (September 2026)**
- **Our Jan 2027 out-of-beta launch** — four months after Apple's v2 lands

This means the spike is most valuable as a **re-runnable benchmark we re-measure each quarter**, not a one-shot reading. First run: April 2026 baseline. Then at WWDC 2026, at macOS 27 GA, at the next Claude generation, at M5 availability on the dev machine. The curve we publish to users / App Store reviewers / investors is the interesting artefact — the first reading is just the "before".

### Stage-by-stage fit (on-device tiers)

"FM" = Apple Foundation Models (~3B, 4k). "MLX-14B" = MLX-hosted Qwen-class 14B BF16. "MLX-MoE" = 30B MoE 4-bit.

| Stage | FM fit | MLX-14B fit | MLX-MoE fit | Notes |
|---|---|---|---|---|
| s01 ingest | — | — | — | I/O |
| s02 extract audio | — | — | — | AVFoundation post-100d |
| s03 parse subtitles | — | — | — | parsing |
| s04 parse docx | — | — | — | parsing |
| **s05 transcribe** | — | — | — | SpeechAnalyzer or faster-whisper, not an LLM stage |
| s06 identify speakers | ◐ | ◉ | ◉ | Short text classification |
| s07 merge transcript | — | — | — | deterministic |
| **s08 PII removal** | ◉ | ◉ | ◉ | Per-segment, short context, structured output |
| s09 topic segmentation | ✗ | ◐ | ◉ | Whole-transcript context; FM 4k too small, MLX-14B borderline, MoE plausible |
| **s10 quote extraction** | ◐ | ◉ | ◉ | 90%+ of cost; primary spike target. FM plausible on short sessions, MLX likely the sweet spot |
| s11 quote clustering | ✗ | ✗ | ◐ | Corpus-wide reasoning; cloud for now, MoE an open question |
| s12 thematic grouping | ✗ | ✗ | ✗ | Synthesis quality matters; keep cloud |
| Autocode / tag suggest | ◉ | ◉ | ◉ | Short-context classification |
| Sentiment per quote | ◉ | ◉ | ◉ | Enum classification with `@Generable` / JSON schema |

Key: ◉ strong fit, ◐ plausible, ✗ poor fit, — not an LLM stage.

### Constraints that matter

- **FM 4k context** will bite on long quotes with surrounding windows. Needs chunking or session-length filtering. May loosen at WWDC 2026; still a real constraint today.
- **Quality ceiling** on synthesis — do not let FM touch s11/s12. MLX-MoE is an open question we should measure, not assume.
- **FM is Swift-only** — access must live in the desktop sidecar, with a local HTTP/XPC endpoint the Python pipeline calls. Respects [`design-modularity.md`](design-modularity.md) ("single Python artefact, no CLI fork") — Python code stays identical, only the sidecar exposes an extra provider on Mac.
- **MLX is Python-native** — `mlx-lm` ships as a pip package. No sidecar needed. Weights are a one-time download (several GB for 14B, more for 30B). First-run user experience matters.
- **OS/hardware gating** — must fall back gracefully on macOS <26 (no FM), Intel Macs (no MLX), and non-Apple platforms (neither).

## Generalised principle: per-stage backends

The mental model is not provider-of-the-run. It is:

- **Each stage declares a capability and a profile.** E.g. s10 is `extract-quotes @ short-context-structured`. s11 is `synthesise @ long-context-reasoning`. s05 is `transcribe @ asr`.
- **Each backend declares which capability × profile pairs it satisfies on which host.** faster-whisper+CUDA satisfies `asr` on Linux+NVIDIA. SpeechAnalyzer satisfies `asr` on macOS 26+. Apple FM satisfies `short-context-structured` on macOS 26+. Claude Opus satisfies `long-context-reasoning` anywhere with network.
- **A resolver picks per stage** given host capabilities (doctor already knows these), a user preference axis (speed / quality / cost / privacy), and a fallback chain ending at Claude.

What makes this tractable rather than a combinatorial mess:

1. **Not every stage is pluggable.** s09 / s11 / s12 lock to `long-context-reasoning`. Only cloud satisfies that profile today, so there is nothing to resolve.
2. **Capability declaration beats per-backend if/else.** The resolver does not care whether the host has Apple or NVIDIA, only whether something claims `asr @ fast` on this host.
3. **Doctor already does host detection.** CUDA, Apple Silicon, macOS version, Ollama reachability — checks exist.
4. **Preference is one slider, not a matrix.** "Prefer local when good enough, fall back to Claude" is a sensible default.

### Not a transition, a stable end state

The temptation is to frame this as "on-device will eventually catch up to cloud and we'll switch." That's wrong, and matters for how we design the architecture.

Both curves are rising. Claude gets better. Apple FM gets better. Neither of those changes the shape of the answer, because the two profiles serve different jobs:

- **Long-context reasoning** (s09, s11, s12) — cloud wins indefinitely. No realistic on-device horizon reaches Opus-class synthesis quality at Opus-class context. We should stop entertaining it.
- **Short-context structured** (s08, s10, autocode, sentiment) — on-device crosses the "good enough" threshold at some point between now and 2028. After that, there is no reason to pay Claude for it. Quality difference on a bounded task isn't visible in the output; latency and cost differences are enormous.

So the pipeline permanently has two profiles, not a transitional mix that eventually consolidates. The resolver's job is to route each stage to its profile, forever.

One corollary worth noting: Claude improving helps CLI users directly (they pay Anthropic, they get the upgrade free of us). Apple FM improving helps only Mac app users. The commercial product wants both — cloud quality for the expensive stages where researchers *feel* quality, on-device speed/privacy for the stages where they'd feel the cost or the wait. Durable product positioning, not transitional.

### Honest limits of the principle

- **Quality drift within a single run is a real risk.** If s08 is local and s10 is Claude, the report now depends on which Mac it ran on. Must be visible in the manifest (`"s10: claude-opus-4-7; s08: apple-foundation-models-3b"`) and probably in the report footer.
- **Testing surface explodes.** Today ~5 providers; this is ~5 providers × ~12 stages × host matrix. CI can't cover it. The honest answer is contract tests per capability profile, not per combination.
- **Not worth building yet.** Without evidence about which backends are actually competitive on which stages, the resolver is an abstraction without a justification.

## Recommendation: don't build the resolver, build the evidence

The cheap, high-signal next step is an **isolated s10 A/B spike**. No app wiring, no sandbox plumbing, no pipeline CLI changes, no config schema evolution. A script that replays the dominant stage against N backends using cached intermediate JSON from existing trial runs.

If the spike shows local models are competitive on s10, we have the strongest possible case for the per-stage architecture — because s10 is 90%+ of the cost on Teams/Zoom inputs, and localising s10 alone is a category-changing product story. If the spike shows local models are not yet competitive on s10, we have saved months of resolver-building for a payoff that would not land.

## Appendix — stage A/B spike plan

### Goal

For a fixed input (one or two real trial-run projects), run **only** one named stage (starting with s10, but the harness is generic) against N backend configs and report:

- wall time per session and total
- LLM-reported token counts where available (for cost estimation)
- estimated $ cost from a per-provider rate table (cloud only; local is $0 marginal)
- quote count per session
- sentiment / intensity / quote-type distribution
- **context-fit fraction** — what fraction of real sessions fit the backend's context window without truncation (critical for FM's 4k)
- fuzzy overlap with a designated baseline run (time-window IoU + text Jaccard)
- optional: pairwise LLM-as-judge score on a sampled subset

All of this goes into a single JSON output + a Markdown summary table.

### Re-runnable benchmark, not a one-shot

The spike's durable value is being re-runnable cheaply. Store results as dated snapshots under `trial-runs/fossda-opensource/stage-ab/<YYYY-MM-DD>/`, same shape as the existing `perf-baselines/` directory. Re-run at:

- WWDC 2026 announcements (8 June)
- Each Claude model generation
- macOS 27 developer beta (July 2026) and GA (September 2026)
- M5 machine availability on the dev bench
- Any new Apple FM API change

The curve we publish over time is the interesting artefact — the first reading is just the baseline.

**Always include the best-available Claude model of the day as the cloud reference**, not a frozen Sonnet-4 forever. Otherwise the curve misrepresents the gap — we'd be measuring on-device progress against a fossil, not against what Bristlenose users would actually be paying for.

### Why this is small

The stage is already cleanly isolated:

- **Input** is `PiiCleanTranscript` + `SessionTopicMap`. Both are serialised in `.bristlenose/intermediate/session_segments.json` and `.bristlenose/intermediate/topic_boundaries.json` for any completed run. No need to rerun s01–s08.
- **Call site** is [`bristlenose/stages/s09_quote_extraction.py:74`](../bristlenose/stages/s09_quote_extraction.py) — `extract_quotes(transcripts, topic_maps, llm_client, concurrency)`. A public async function.
- **Provider swap** is a one-liner on `BristlenoseSettings` (`llm_provider`, `llm_model`) then re-init `LLMClient`. No pipeline config, no DB, no serve mode.

So the spike is a Python script that:

1. Loads cached intermediate JSON for a chosen trial-run.
2. Reconstructs `PiiCleanTranscript` / `SessionTopicMap` Pydantic models.
3. For each backend config: builds `LLMClient`, awaits `extract_quotes(...)`, times it, records tokens where the SDK returns them.
4. Writes per-run JSON + an aggregate comparison Markdown table.

### Proposed script

**Path**: `scripts/stage-ab.py` (generic over stages; starts with s10 only)

**CLI**:

- `--stage <name>` — pipeline stage key (e.g. `quote_extraction`). Starts with only `quote_extraction` wired, but script is structured to add others
- `--input <output-dir>` — completed `bristlenose-output/`, default `trial-runs/fossda-opensource/bristlenose-output`
- `--baseline <label>` — which config labels the reference for overlap computation
- `--configs <path>` — JSON of `[{provider, model, label, max_tokens?}, ...]`
- `--out <dir>` — where to write per-run JSON + `summary.md`, default `trial-runs/<project>/stage-ab/<YYYY-MM-DD>/`
- `--sample <int>` — optional, limit to first N sessions for fast iteration
- `--judge <provider>:<model>` — optional, enable pairwise LLM-as-judge

**Output**:

- `<out>/<label>/quotes.json` — raw `ExtractedQuote` list
- `<out>/<label>/metrics.json` — wall time per session, tokens, errors, context-fit flags
- `<out>/summary.md` — comparison table, headline numbers, context-fit histogram

### Backends in the first pass

Six entries across the tiers:

**On-device (Mac)**:
1. `apple:foundation-models-3b` — zero-setup path (needs Swift shim; see sequencing below)
2. `mlx:mlx-community/Qwen2.5-14B-Instruct-bf16` — likely quality sweet spot on M-class hardware (~10s TTFT on M5)
3. `mlx:mlx-community/Qwen2.5-MoE-30B-4bit` — stretch option if RAM permits (~3s TTFT on M5)

**On-device (generic, cross-platform)**:
4. `local:ollama/qwen2.5:7b` — baseline Linux/Windows users get; MLX must outperform for a Mac-specific claim to be meaningful

**Cloud (reference)**:
5. `anthropic:claude-sonnet-4` — current production (or best-available Claude at time-of-run)
6. `anthropic:claude-haiku-4-5` — cheap cloud reference; tests "is cheaper Claude good enough"

### Sequencing

MLX is Python-native — adding it is a pip dep + a thin provider wrapper in `bristlenose/llm/client.py`. Apple FM needs a small Swift shim exposing a local HTTP endpoint. So the work goes:

1. **Phase A (this session or next)** — harness, cloud + Ollama arms. Proves replay against the cached baseline `extracted_quotes.json`.
2. **Phase B** — MLX arm. `mlx-lm` provider in `LLMClient`, add entries 2 and 3 to slate. No Swift work.
3. **Phase C (separate plan)** — Apple FM Swift shim + `apple` provider. Standalone dev executable; later folded into the Track C sidecar.

Each phase is independently useful and produces a dated benchmark snapshot.

### Quality metric strategy

There is no ground truth for quote extraction. Options, in order of signal-to-effort:

1. **Structural metrics (free, deterministic)** — quote count, density per minute, sentiment/intensity distribution, `quote_type` split, timecode coverage histogram.
2. **Fuzzy overlap vs baseline** — for each quote in the test run, find the baseline quote with closest `start_timecode` (within ±5s) in the same session. Match score: IoU on timecode window + character-level Jaccard on `text`. Report recovery fraction and novel-quote fraction per provider.
3. **LLM-as-judge (moderate effort, adds noise)** — sample N segments, show both runs side-by-side to Claude Opus, ask for preference + rationale. Report win-rate. Known limitations: judge bias toward its own family, non-determinism.
4. **Human spot-check (highest signal, expensive)** — out of scope for the spike. Flag as follow-up if (1) and (3) disagree.

Start with (1) and (2). Add (3) only if cost permits. Skip (4).

### Alternative routes considered

- **Add `--provider` override to `bristlenose run --only-stage s10`** — requires pipeline CLI changes, manifest handling, error paths. More wiring than warranted.
- **Parametrise pytest with a provider fixture** — good for regression, bad for one-off quality comparison. CI cost would balloon.
- **Extend [`scripts/compare-runs.py`](../scripts/compare-runs.py)** — it compares two *full* runs. Would need re-running the whole pipeline per provider (slow, wasteful) or rewriting around stage-isolation, at which point it's `scripts/stage-ab.py`.
- **Build the resolver first, A/B as its first user** — builds the abstraction without evidence. Wrong order.

Isolated script wins on every axis.

### Risks / known unknowns

- **Prompt compatibility across providers** — the prompt assumes a capable model. A 7B local model may not handle structured output reliably; already known to require the 3-retry fallback in [`bristlenose/llm/client.py`](../bristlenose/llm/client.py).
- **Token counting asymmetry** — Anthropic and OpenAI return usage; Gemini's shape differs; Ollama returns nothing; MLX must be counted manually. Cost table must handle "unknown tokens" gracefully.
- **Context window variance** — FM 4k is a hard limit; MLX models vary (Qwen 2.5 has 32k+ natively, though practical limits depend on RAM); cloud is effectively unlimited. The context-fit metric is how we surface this honestly rather than silently degrading.
- **MLX cold-start cost** — first model load is several seconds; not representative of steady-state use. Warm the model with a throwaway call before the timed run.
- **Provider caching** — some cloud providers cache by prompt hash. If cold latency is the goal, add a cache-bust nonce per run.
- **M-chip variance** — MLX numbers on an M2 Max will not match M5. Record the host chip in metrics.json so re-runs on newer hardware are comparable.

### Verification

- Run the script with a single backend (Claude Sonnet) against FOSSDA.
- Compare output `quotes.json` to the existing `extracted_quotes.json` in that project's intermediate cache.
- Expect: same quote count ±5%, substantial timecode overlap, same structure where prompt and model are unchanged.
- If numbers diverge by more than expected jitter, the replay harness is wrong — not the providers.

## Open questions

- **Quality judgement** — are structural + fuzzy overlap enough signal on their own, or is LLM-as-judge mandatory for the spike? A narrow judge pass on 2–3 sessions is probably affordable.
- **MLX model selection** — Qwen 2.5 14B BF16 is the obvious choice but not the only one. Gemma, Llama-variant, or an Apple-published model may be better aligned to `@Generable`-style JSON output. Worth trying 2–3 in Phase B before locking in.
- **Token counting in `LLMClient`** — add now (so the spike reports real $, not proxy seconds) or add later (so the spike stays narrow)? Adding now is ~20 lines per provider.
- **Apple FM sequencing** — Phase C Swift shim before or after Phase B MLX? MLX likely produces stronger numbers (larger models), so FM may look worse than it deserves in a Phase C reading. Document both side by side so readers see the tier structure, not a single "on-device" column.
- **Hardware disclosure** — record chip generation in every metrics.json. Without it, re-runs across an M2 Max / M3 / M5 are meaningless to compare.
- **When to promote this from spike to pipeline feature** — once any on-device arm beats Haiku-class Claude on s10 quality at lower cost and latency, the case to wire it into the real pipeline (behind a flag) is strong. Define that threshold now so we recognise it when it hits.

## See also

- [`docs/design-performance.md`](design-performance.md) — principle-level performance notes, complementary
- [`docs/design-perf-fossda-baseline.md`](design-perf-fossda-baseline.md) — precedent for this kind of evidence doc
- [`docs/design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md) — provider abstraction (replaces archived `design-llm-providers.md`)
- [`docs/design-modularity.md`](design-modularity.md) — single-Python-artefact principle; Apple FM must respect it
- [`scripts/perf-breakdown.py`](../scripts/perf-breakdown.py) — evidence producer
- [`bristlenose/llm/client.py`](../bristlenose/llm/client.py) — `LLMClient.analyze`
- [`bristlenose/stages/s09_quote_extraction.py`](../bristlenose/stages/s09_quote_extraction.py) — s10 call site
- [`bristlenose/llm/prompts/quote-extraction.md`](../bristlenose/llm/prompts/quote-extraction.md) — the prompt under test
