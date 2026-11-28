# Local models for each memory size, November 2026: fix the context window and the Mac build first (27 Nov 2026)

_Research note, 27 Nov 2026. A proposal only: the app's `OllamaCatalog` (`desktop/Bristlenose/Bristlenose/LLMProvider.swift`), the CLI default (`local_model` in `bristlenose/config.py`) and the website's set-up page are unchanged until the maintainer decides. Scope: on-device analysis under Ollama for the Bristlenose Mac app and the CLI on macOS and Linux. Ollama v0.40.18 (24 Nov 2026) is the latest stable release; the registry and memory measurements were taken on v0.20.7, and the Bristlenose analysis runs in § "Measured on the Bristlenose task" on v0.40.18. Revised the same day when those runs came in, and again on 28 Nov 2026 with nine models measured._

**Update, 28 Nov 2026.** Nine models have now been run on the Bristlenose task with the fixed client (§ "Nine models measured, and one model per tier"), and they settle one model per tier:
- **8 GB:** use a cloud provider.
- **16 GB:** `gemma4:e4b`, with other large apps closed.
- **32 GB and 64 GB:** `gemma4:26b`.

Qwen 3.8 27B gave the best quotes of any local model, but it runs into quote extraction's 570-second limit on each call, which costs slower models whole interviews. The proposals below that say otherwise are the 27 Nov reasoning, kept as it was.

Bristlenose should not change its local-model catalogue until the local client sets the context length, and until it can run on the build a current Mac downloads. On Ollama 0.40.18, `gemma4:e4b` on Apple silicon arrives as an MLX build. On the test Mac's Homebrew install that build's runner refused structured output with HTTP 501, so today's recommended model failed at the first call (measured, below). The cause is a library missing from Homebrew's package, not MLX itself (§ "Structured output on MLX: a packaging gap"). Until 27 Nov 2026 the client sent no `num_ctx` (it now sets 32k: § "Ways to set the context"), so Ollama picked a default from the GPU memory it detects: 4,096 tokens on every Mac with 16 GB or less, almost certainly on 24 GB Macs, and on most Linux GPUs. A 60-minute transcript is 9–14k tokens. What happens next depends on which build of the model runs:

- **On the GGUF path** (Linux, any Mac on Ollama before 0.40, and Llama 3.2 3B everywhere), Ollama keeps the first 5 tokens and the last ~2,050 of the prompt and returns HTTP 200. The system prompt and schema instruction, which come first, are lost with most of the transcript. Measured on 0.40.18 with a 4k server: every topic-segmentation call arrived as exactly 2,051 tokens, "succeeded", and nothing told the user; every quote-extraction reply then ran out of room (`finish_reason: length`) and the analysis failed after 10 minutes. This was a Gemma 4 E4B GGUF build, so the HTTP 400 that the source suggested for models with a projector did not happen.
- **On a Mac with Ollama 0.40 or later**, the Gemma 4 and Qwen 3.5 tags resolve to an MLX build. For `gemma4:e4b` that build was pulled and tried: the MLX runner answers every structured-output request with **501 "structured output is unavailable"**, through `/v1` with `json_object` or `json_schema` and through native `/api/chat` with `format: "json"`. A request with no format works. Bristlenose always asks for structured output, so the run ends in 8 seconds. Other MLX builds were not tried. The server log gives the cause: `xgrammar library not found at …/mlx_metal_v3/libollama_xgrammar.dylib`. Homebrew's Ollama package leaves that library out, and Ollama's own builds ship it (§ "Structured output on MLX: a packaging gap"). So this failure is certain for Homebrew installs; the official app was not tried.

Once the context is set to 32k, the evidence supports a range that starts at 16 GB, not 8 GB:

- **smallest:** Qwen 3.5 4B (about 5 GB in use);
- **balanced:** Qwen 3.5 9B (about 8–9 GB);
- **good:** Gemma 4 12B (about 10 GB, from 24 GB);
- **better:** Qwen 3.8 27B (about 21 GB, from 32 GB, confirmed only at 36 GB).

All of these tags pull an MLX build on a current Mac, so on the Mac the range holds only once one of three things is true: the client stops asking Ollama for structured output and validates the JSON itself (done 27 Nov 2026, on the 501 only); it pulls and runs the GGUF build (Ollama has a hidden `--runner llamacpp` flag on `pull` and `run`, and a `runner` field on native API requests, but none on `/v1`); or Ollama's MLX runner gains structured output. On Linux the range holds as written.

The two Qwen picks also need the local client to switch thinking off, which it has done since 27 Nov 2026 (`think: false`; not yet measured on Qwen). Without that change, the fallback is Gemma 4 E2B, E4B, 12B and 26B. The 26B has an open bug: Gemma 4 falls into repetition loops under JSON schemas with long free-text fields, which is the shape of a verbatim quote. No model examined fits an 8 GB Mac with a browser and Mail open (Qwen 3.5 2B and 0.8B exist and were not assessed). Those machines, about three in ten Macs, should be pointed at a cloud provider.

Today's catalogue understates memory:

- Llama 3.2 3B needs about 6.2 GB at 32k, not 4 GB (`ollama ps` showed 4.3 GB on 0.40.18 with q8_0 KV). More to the point, its output is not usable: measured below, it repeats quotes, stamps them all at 0:00, and on current Ollama did not finish three real interviews.
- Gemma 4 E4B downloads 6.6 GB (GGUF) or 9.5 GB (the MLX build a current Mac pulls), not 3 GB.
- Gemma 4 31B needs about 27 GB, more than the 26.8 GB GPU working set measured on a 32 GB Mac.

Of the proposed models, only Gemma 4 E4B (GGUF) has been run on the Bristlenose task, on three public test sessions: at 32k it finished, with nearly all quotes verbatim and weaker themes than Claude. That measurement for the rest decides whether any of this ships. The memory figures below are arithmetic for the GGUF builds, and for the Gemma E-models they overstate resident memory (see "Measured on the Bristlenose task"); they describe Linux and older Macs, not the MLX builds a current Mac runs.

A wider search of the other families Ollama carries (§ "Beyond Gemma and Qwen: the wider field") found none that beats this shortlist. One, Bonsai 2 27B, a 2-bit Qwen 3.8 derivative at about 10.4 GB, earns a run for 16 GB Macs. The same search traced the MLX 501 to Homebrew's package: it leaves out the XGrammar library.

## How the figures were obtained and labelled

Every figure carries a label:

- **(M) measured here, 27 Nov 2026.** This covers:
  - Ollama registry manifests (`https://registry.ollama.ai/v2/library/<name>/manifests/<tag>`, layer sizes summed);
  - GGUF headers read from the model blobs;
  - Metal's `recommendedMaxWorkingSetSize` and the Ollama server log, both on one M2 Max with 32 GB running macOS 27 and Ollama 0.20.7;
  - the idle memory footprint of the Bristlenose app and its sidecar;
  - the Bristlenose client code.
- **(C) computed here from measured inputs.** Chiefly the KV-cache sizes, worked out from GGUF headers.
- **(V) vendor-reported.** The model's maker, or Ollama about Ollama.
- **(I) independent.** A third party's measurement or evaluation.
- **(Inf) inference.** Arithmetic or judgement on the above; not measured.

Units:

- Download sizes are in GB of 10⁹ bytes, as Ollama and Finder show them.
- KV-cache sizes are computed in GiB (2³⁰ bytes) and converted at 1 GiB = 1.074 GB before being added.

**Memory in use** is the sum of three parts:

1. **Weights as loaded.** The model, plus the vision projector and the draft layer, both of which Ollama passes to llama-server on every load ([llm/llama_server.go](https://github.com/ollama/ollama/blob/v0.40.18/llm/llama_server.go)) (V).
2. **The KV cache.** The cache per slot multiplied by the number of slots.
3. **Compute buffers.** These take 0.4–1.5 GB. The low end is measured: for Llama 3.2 3B at 32k they took 281 MiB on the GPU and 112 MiB on the CPU (M).

All figures assume Ollama's default f16 KV cache. Setting `OLLAMA_KV_CACHE_TYPE=q8_0` halves the KV term, but that setting is global, needs flash attention and applies only to the GGUF path ([Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)) (V).

**The workload:**

| Input | Tokens |
|---|---|
| One 60-minute interview, current transcript format | 9,371 (M) |
| The same interview, earlier transcript format | 13,621 (M) |
| A 99-minute interview | 17,587 (M) |
| JSON schema the client appends to the system prompt (quote extraction) | 867 (M) |
| Quote-extraction prompt | 1,407 (M) |
| Topic-segmentation prompt | 782 (M) |

The counts use OpenAI's o200k tokeniser on the transcript files on disk, so each model's own count, and the text the stage actually sends, will differ somewhat. Only one 60-minute interview was counted, in two transcript formats. Both stages send the whole transcript in one request, with the prompt and the JSON schema, and the answer shares the same window. The server log on the test Mac shows 5,852 and 8,285 input tokens for two calls on one roughly 19-minute session, which implies up to about 4k tokens of overhead beyond the transcript (M). So a 60-minute interview needs roughly 13–18k tokens in, plus the answer, and 32k is the working figure throughout.

## Most Macs and Linux GPUs get a 4k window, which a transcript overflows

**Ollama picks a default context at server start from the GPU memory it detects** ([server/routes.go, v0.40.18](https://github.com/ollama/ollama/blob/v0.40.18/server/routes.go); [v0.15.5 release notes](https://github.com/ollama/ollama/releases/tag/v0.15.5)) (V):

| GPU memory detected | Default context |
|---|---|
| Under 23 GiB | 4,096 tokens |
| 23 GiB or more | 32,768 tokens |
| 47 GiB or more | 262,144 tokens, clamped to the model's trained length |

On a Mac, "GPU memory" is Metal's `recommendedMaxWorkingSetSize` (V, same source).

**The two-thirds rule for a 32 GB Mac does not hold on the one machine measured.** Published guidance assumes the working set is two-thirds of RAM, which on a 32 GB Mac means 21.3 GiB and the 4k tier. That assumption comes from a 2023 reverse-engineering of the GPU driver ([llama.cpp discussion #2182](https://github.com/ggml-org/llama.cpp/discussions/2182)) (I) and from Apple's 2021 figure of 21 GB for a 32 GB M1 Pro or Max ([Apple Tech Talk 10580](https://developer.apple.com/videos/play/tech-talks/10580/)) (V). The measurement disagrees:

- On the M2 Max with 32 GB under macOS 27, the working set is **26,800,603,136 bytes (24.96 GiB, 78% of RAM)** (M).
- The Ollama server log reads `msg="vram-based default context" total_vram="25.0 GiB" default_num_ctx=32768`, on both 13 and 27 Nov (M).

So this 32 GB Mac gets 32k because its working set is 25.0 GiB. Two caveats follow. This is one machine. And the 8, 16 and 24 GB figures below are inferences from both fractions.

| Mac RAM | GPU working set | Default context | Share of Macs, Steam survey, Oct 2026 (I) |
|---|---|---|---|
| 8 GB | ~5.3–6.2 GiB (Inf, ⅔ to 78%) | 4k | 28.8% |
| 16 GB | ~10.7–12.5 GiB (Inf; secondary reports conflict) | 4k | 43.2% |
| 24 GB | ~16–18.7 GiB (Inf) | 4k, probably | 11.3% |
| 32 GB | 24.96 GiB (M) | 32k (M) | 5.6% |
| 36 GB | ~24–28 GiB (Inf) | 32k (Inf) | 2.0% |
| 48 GB | 40,200 MB on an M5 Pro ([Curunir evals, Apr 2026](https://jalemieux.github.io/curunir-evals/reviews/article-draft-26b-perf-20260409)) (I) | 32k (Inf) | 2.7% |
| 64 GB | ~42.7 GiB at ⅔ (Inf) to ~48–50 GiB (V, Apple's 2021 "48 GB"; Inf) | 32k at ⅔, 256k at ¾ (Inf) | 2.7% |
| 128 GB | 96 GiB ([llama.cpp #2182](https://github.com/ggml-org/llama.cpp/discussions/2182)) (I) | 256k (Inf) | under 1% (">64 GB" row) |

Shares are from [Steam's Mac hardware survey](https://store.steampowered.com/hwsurvey/?platform=mac). Steam also has a 20 GB row at 2.3%. Together the 8, 16, 20 and 24 GB rows are **about 86% of the Macs in the sample**, including the 28.8% at 8 GB, which get no model anyway. Steam's users are gamers, so treat this as indicative only. The 24 GB row is twice the size of the 32 GB row.

### What happens when the prompt does not fit

On the GGUF path (every tag on Linux, every tag on a Mac running Ollama before 0.40, and tags with no MLX build, such as `llama3.2:3b`, everywhere), a single oversized user message cannot be dropped as a whole message. Ollama's llama-server wrapper therefore cuts it at token level ([llm/llama_server.go](https://github.com/ollama/ollama/blob/v0.40.18/llm/llama_server.go)) (V):

- It keeps the first `num_keep` tokens (4, plus BOS).
- It keeps roughly the last half of the window, about 2,050 tokens of a 4k context.
- It logs a warning and returns HTTP 200.

Because the JSON grammar still applies, the answer comes back valid, schema-shaped and plausible. Ollama 0.20.7 does the same but keeps the last ~4,090 tokens ([runner.go, v0.20.7](https://github.com/ollama/ollama/blob/v0.20.7/runner/ollamarunner/runner.go)) (V).

There are two exceptions:

- **Models with a vision projector.** The source suggests llama-server disables context shifting for them and returns an HTTP 400 saying the prompt is longer than the context ([server/sched.go](https://github.com/ollama/ollama/blob/v0.40.18/server/sched.go)) (V). **Not what was measured:** a Gemma 4 E4B GGUF build on 0.40.18 at 4k was truncated silently with HTTP 200, the server logging `truncating input prompt limit=2051 prompt=6419 keep=5 new=2051` (M). Treat silent truncation as the GGUF behaviour for every model until a 400 is observed.
- **The MLX path.** Ollama does not truncate at all and treats `num_ctx` only as a sizing hint. On a Homebrew install this is moot: the MLX runner refuses structured output (501) before any of this matters (M) ([mlxrunner/parallel.go](https://github.com/ollama/ollama/blob/v0.40.18/mlxrunner/parallel.go)) (V).

What this means for the catalogue (Inf):

- **Llama 3.2 3B is a text-only GGUF** (M: one layer, no projector, and no MLX build in the registry). On a 16 or 24 GB Mac, today's CLI default would therefore analyse only the end of a 60-minute interview and report success (Inf; the same truncation was reproduced with Gemma 4 E4B, not with Llama). On current Ollama that is at most the last 9–13 minutes (2,050 tokens at 156–227 tokens a minute). The cut applies to the whole rendered prompt, so the system prompt and the schema instruction go too; in quote extraction about 16 template lines follow the transcript, leaving roughly 1,700 transcript tokens. On 0.20.7 it is up to the last 18–26 minutes.
- **The Gemma 4 tags and the Qwen 3.5 tags up to 35B carry projectors** (M; `qwen3.5:122b` has none). The source suggested a hard error for them on the GGUF path; the measured Gemma 4 E4B build was truncated silently instead, and its analysis failed at quote extraction with a message blaming `max_tokens` 64,000 rather than the context (M). So the failure is visible only at the second stage, and it names the wrong limit.
- **A Mac on Ollama 0.40 or later runs those tags on MLX** (next section). On the test Mac's Homebrew install, `gemma4:e4b` refused structured output with a 501, so no transcript reached it (M).
- **This is not just a problem with long interviews.** One call on an 18-minute interview already sent 8,283 tokens (M, a separate measurement on the same Mac).

### Large Macs need the context set too

From 47 GiB of GPU memory (64 and 128 GB Macs, and 48 GB GPUs), the default context is 256k, clamped to the model's trained length:

- **Qwen 3.8 27B at 256k** would hold about 16 GiB of f16 KV instead of 2 GiB. That puts it at roughly 36 GB in use instead of 21 GB (C).
- **Gemma 4 31B at 256k** with a q8_0 cache measured 31.0 GiB on an M5 Max ([PR #19327](https://github.com/ollama/ollama/pull/19327)) (I).

If a load runs out of memory while the context is automatic, Ollama lowers the context and retries once, and the client is not told ([server/sched.go](https://github.com/ollama/ollama/blob/v0.40.18/server/sched.go)) (V).

### Ways to set the context

Three mechanisms exist. Since 27 Nov 2026 Bristlenose uses the first ("What the client does now", below).

The OpenAI-compatible endpoint that the app uses has no context field. Its request type maps `max_tokens`, `temperature`, `response_format` and `reasoning_effort`, and nothing for the window ([openai/openai.go](https://github.com/ollama/ollama/blob/v0.40.18/openai/openai.go); [OpenAI compatibility docs](https://github.com/ollama/ollama/blob/v0.40.18/docs/api/openai-compatibility.mdx)) (V).

1. **Ollama's native `/api/chat` with `options.num_ctx` on each request.** This is the highest-precedence setting. Native requests also accept `truncate: false`, which turns silent truncation into an error ([api/types.go](https://github.com/ollama/ollama/blob/v0.40.18/api/types.go)) (V).
2. **A tag derived from a Modelfile with `PARAMETER num_ctx`.** This is the route Ollama's OpenAI-compatibility page itself recommends. It shares the base tag's blobs, so there is no second download (Inf from the content-addressed blob store, [server/download.go](https://github.com/ollama/ollama/blob/v0.40.18/server/download.go)).
3. **`OLLAMA_CONTEXT_LENGTH` on the server.** The Ollama Mac app's context slider sets this ([app/server/server.go](https://github.com/ollama/ollama/blob/v0.40.18/app/server/server.go)) (V). It is global and belongs to the user, not to Bristlenose.

**What the client does now (27 Nov 2026, card `ollama-mlx-json`).** The local client asks Ollama on its native `/api/chat` with `options.num_ctx` 32768, `truncate: false`, `shift: false` and `think: false`, through the openai SDK's generic `post`, so errors keep the classes they had (`ollama_chat_body` in `bristlenose/llm/client.py`; the key preflight sends the same body with a one-token cap, so the model loads at the run's window during setup). A derived tag would leave artefacts in the user's Ollama, and `OLLAMA_CONTEXT_LENGTH` is the user's. Which API to use is asked once per client at `GET /api/version` (a 404 or 405 means not Ollama). A server that is not Ollama (llama.cpp's server, LM Studio, vLLM: no `/api/chat`) keeps the `/v1` request, where the window cannot be set. The consequences:

- On the GGUF runner, a prompt over the window becomes a 400 instead of a silent cut to its tail, and an answer that fills the window ends `done_reason: "length"` instead of shifting the prompt out (V, `llm/llama_server.go`). The client treats both as a truncation, which quote extraction splits the session on; topic segmentation does not split, so there an over-long transcript fails visibly.
- The MLX runner ignores `truncate` and does not truncate; the over-window case there was not measured.
- 32k is fixed, not sized per call, because a different `num_ctx` reloads the model. It replaces Ollama's own default in both directions: up from 4k on small machines, which is the point; down from 256k at 47 GiB or more, which still fits the workload (§ "Large Macs need the context set too"); and down from a larger `OLLAMA_CONTEXT_LENGTH` a user set. There is no setting to change it yet.
- On the MLX runner's 501 the client asks again with no format, for the rest of the run. The schema stays in the system prompt, and the reply is parsed and validated as any reply is.

Tested with mocked HTTP (`tests/test_local_ollama_native.py`) and checked once each against Ollama 0.40.18 (Homebrew) on the test Mac, with a two-turn transcript (M): `gemma4:e4b` on MLX refused the format, the client asked again in plain text and validated 2 quotes, loaded at 32,768; the `gemma4` GGUF build answered the schema with `think: false` (valid JSON, `n_ctx = 32768` in the log); `llama3.2:3b` given a prompt over the window answered 400 in 1.9 s, raised as a truncation, with no "truncating input prompt" line; the preflight loaded `gemma4` at 32,768. No full analysis has run with the change: item 3 under "What must be verified".

Whichever is chosen has to size for input plus output:

- A 13.6k-token transcript plus the 1.4k-token prompt plus a few thousand output tokens fits in 32k.
- A 99-minute interview at 17.6k tokens leaves about 13k tokens for the prompt and the answer.

Since v0.32.6, truncated answers report `finish_reason: "length"` ([v0.32.6 release](https://github.com/ollama/ollama/releases/tag/v0.32.6)) (V).

## Thinking, Gemma's loops, two download sizes and a serial queue

### Qwen, gpt-oss and Nemotron would think on every call

**Until 27 Nov 2026 the local client sent no thinking switch.** It now sends `think: false` on Ollama's native API, the value Ollama maps `reasoning_effort: "none"` to; a model that cannot think accepts it, since Ollama refuses only `think: true` there (V, `server/routes.go`). As measured before the change: the local path, `_analyze_local` in `bristlenose/llm/client.py` (around lines 1645–1661), sends the model, the messages, `max_tokens`, `temperature` and a `json_schema` response format. It sends no `reasoning_effort` and no `num_ctx` (M). The gateway route in the same file already sends `reasoning_effort: "none"` (lines 417–426) (M).

**Several candidate families think by default:**

- **Qwen 3.5, 3.6 and 3.8** ([Qwen3.5-4B card](https://huggingface.co/Qwen/Qwen3.5-4B); [Qwen3.8-27B card](https://huggingface.co/Qwen/Qwen3.8-27B)) (V).
- **NVIDIA Nemotron 3.5 Lightning** ([model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16)) (V).
- **gpt-oss**, which cannot disable thinking at all; Ollama maps `"none"` to its lowest level ([OpenAI compatibility docs](https://github.com/ollama/ollama/blob/v0.40.18/docs/api/openai-compatibility.mdx)) (V).

**Why this matters.** Thinking tokens come out of the same context window as the answer, and they take time. The seam between thinking and the grammar has also had bugs:

- With thinking on, an MLX build returned invalid JSON in 8 of 10 calls, against 0 of 10 with `reasoning_effort: "none"` ([#18441](https://github.com/ollama/ollama/issues/18441), closed 20 Sep 2026) (I).
- An earlier bug ignored the schema for Qwen 3.5 when thinking was off. It was fixed in 0.31.2, July 2026 ([#14645](https://github.com/ollama/ollama/issues/14645)) (I).

**Consequence for the catalogue.**

- The Qwen picks below depend on two things. The local client must switch thinking off, which it does since 27 Nov 2026 with `think: false`, the value `reasoning_effort: "none"` maps to ([openai.go](https://github.com/ollama/ollama/blob/v0.40.18/openai/openai.go)) (V). And Ollama must be 0.31.2 or later.
- gpt-oss and Nemotron are left out.
- Gemma 4 thinks only when the system prompt opens with its think token ([Gemma 4 model card](https://gemma.ai/models/gemma-4/model-card/)) (V), so it works with the client as it is. With thinking off, Gemma 12B, 26B and 31B still emit an empty thought block (V, same card). This note did not check whether Ollama strips that block on every path.

### Gemma 4 loops under JSON schemas, worst at 26B and 31B

**The evidence.** In google-deepmind/gemma issue #622, opened 11 Apr 2026 and still open, testers ran ten seeds per test on Ollama 0.20.5, with later reports on 0.30.8 and 0.31.1. Whenever a schema was set, the models fell into repetition loops and mostly returned invalid JSON ([gemma #622](https://github.com/google-deepmind/gemma/issues/622)) (I):

- gemma4:26b returned valid JSON in 0 or 1 of 10 runs on most of the schema tests.
- gemma4:31b looped in 10 of 10 runs on a 1,000-word answer bound to a schema.
- With no schema, neither model looped.
- gemma3:27b was clean on the same tests.
- llama.cpp, running the same files, gave 10 of 10 valid answers, though a later comment (19 May) reports loops under llama.cpp too.
- Changing the sampling settings did not help (I, same thread).

Ollama's own issue for 31B, with 60–100% failure in long free-text fields, is also open ([#15502](https://github.com/ollama/ollama/issues/15502)) (I). A verbatim quote is exactly that shape: a long free-text field inside a schema.

**What is not known.**

- Smaller sizes are not clean either (§ "Gemma 4's loops: a grammar makes them worse"): E2B and E4B loop on long unconstrained enumerations, E2B under an MLX grammar failed to stop on 3 of 12 runs, and 12B loops while thinking. One report says the GGUF 12B enforced schemas where the MLX 26B did not ([#16776](https://github.com/ollama/ollama/issues/16776)) (I).
- Ollama moved its GGUF path to upstream llama-server in v0.30.0. Loops were still reported on 0.30.8 and 0.31.1, so the move alone did not fix them.
- One report (6 Jul, 0.31.1, QAT build) found non-streaming calls did not loop. Bristlenose does not stream, so this matters, but it is one report.
- August comments reproduce the loops on Google's own hosted API, which points at the model rather than Ollama (I, same thread).

**A separate regression.** Ollama 0.40.18 currently returns HTTP 200 with an empty body for `json_schema` requests on Windows with ROCm ([#19918](https://github.com/ollama/ollama/issues/19918), open since 26 Nov 2026) (I).

**Consequence for the catalogue.**

- Gemma 4 26B and 31B stay out of the recommended range until Bristlenose has measured their loop rate on its own schemas on a current Ollama.
- Every local response needs schema validation, loop detection and a retry, whichever model is picked.

### Each tag has two builds, and a current Mac pulls the MLX one

The Ollama library page lists a size range for each tag, consistent with one GGUF manifest and one MLX manifest per tag ([gemma4 tags](https://ollama.com/library/gemma4/tags); [qwen3.5 tags](https://ollama.com/library/qwen3.5/tags)) (V).

| Tag | GGUF manifest (M) | `-mlx` tag (M) | Library-page range (V) | Size to quote to users |
|---|---|---|---|---|
| llama3.2:3b | 2.02 GB | none listed | 2.0 GB | 2.0 GB |
| qwen3.5:4b | 3.32 GB | 3.97 GB | 3.3–4.0 GB | 4.0 GB |
| gemma4:e2b | 4.59 GB | 7.48 GB | 4.6–7.5 GB | 7.5 GB |
| gemma4:e4b | 6.58 GB (pulls from before the republish: 9.61 GB) | 9.46 GB | 6.6–9.5 GB | 9.5 GB on a Mac |
| qwen3.5:9b | 6.55 GB | 8.90 GB | 6.6–7.6 GB | 8.9 GB on a Mac |
| gemma4:12b | 8.02 GB | 7.71 GB | 7.7–8.0 GB | 8.0 GB |
| qwen3.8:27b | 17.74 GB | 18.17 GB | 18 GB | 18.2 GB |
| gemma4:26b | 18.73 GB | 18.33 GB | 16–19 GB | 19 GB |
| gemma4:31b | 20.39 GB | 19.42 GB | 19–20 GB | 20.4 GB |
| qwen3.6:35b | 22.62 GB | 23.11 GB | 23 GB | 23.1 GB |

**A Mac on current Ollama receives the MLX build.** Asked with the manifest-list media type the Ollama client sends (`application/vnd.ollama.manifest.list.v2+json`), the registry returns, for `gemma4:e4b`, `gemma4:12b` and `qwen3.5:4b`, a list with two children: `runner: llamacpp, format: gguf` and `runner: mlx, format: safetensors` (M). `llama3.2:3b` returns a single GGUF manifest (M). The client prefers MLX first on macOS on Apple silicon and llama.cpp first everywhere else ([manifest/manifest.go:854–860, v0.40.18](https://github.com/ollama/ollama/blob/v0.40.18/manifest/manifest.go)) (V), and v0.40.0 made MLX the default runner there ([v0.40.0 release](https://github.com/ollama/ollama/releases/tag/v0.40.0)) (V). The list does not show the children's sizes; the explicit `-mlx` tags in the table above are used as their sizes, which is an assumption (Inf). A pull on this Mac under 0.40.18 confirmed it for `gemma4:e4b`: it fetched an `nvfp4` MLX build, 9.46 GB, which needs Ollama 0.31.0 or later (M). On 0.20.7 the same pull fails with HTTP 412 "requires a newer version of Ollama" (M). Linux gets GGUF. A Mac can ask for the GGUF child with the hidden `--runner llamacpp` flag on `ollama pull` and `ollama run` ([cmd/cmd.go, v0.40.18](https://github.com/ollama/ollama/blob/v0.40.18/cmd/cmd.go)) and with a `runner` field on native `/api/chat` requests ([api/types.go](https://github.com/ollama/ollama/blob/v0.40.18/api/types.go)) (V). The OpenAI-compatible endpoint has no such field (V), and whether a model pulled that way is then served on llama.cpp to a `/v1` request was not tested.

**The current E4B was republished.** On the test Mac, an E4B pulled about five months ago is a single 9.61 GB layer (M). The current GGUF is 6.58 GB: a 5.49 GB model, a 0.99 GB projector and a 0.10 GB draft layer, built around 29 Sep 2026 (M). Third-party guides still quote 9.6 GB ([dev.to guide](https://dev.to/purpledoubled/how-to-run-googles-gemma-4-locally-with-ollama-all-4-model-sizes-compared-2pbh)) (I).

**Consequences.**

- On a Mac, user-facing copy should quote the MLX size; on Linux and in the docs' Linux column, the GGUF size.
- An MLX manifest changes behaviour as well as size. It does not truncate and it picks its own parallelism. **On the test Mac's Homebrew install of 0.40.18, the `gemma4:e4b` MLX build refused structured output outright: HTTP 501 "structured output is unavailable", for `json_object`, `json_schema` and native `format: "json"` alike (M).** MLX structured output uses XGrammar, and the Homebrew package lacks the XGrammar library (§ "Structured output on MLX: a packaging gap"). XGrammar has its own bug history: MLX ignored schemas up to v0.33.0; structured output arrived in v0.33.1 (26 Aug 2026). [#17933](https://github.com/ollama/ollama/issues/17933), often cited for the fix, was closed as a duplicate with no change (V). The `OLLAMA_KV_CACHE_TYPE` setting is not wired into the MLX path (V, per source search of v0.40.18).

### Three concurrent requests run one at a time

Bristlenose's default `llm_concurrency` is 3 (M).

**On the GGUF path, Ollama serves one request at a time.** With `OLLAMA_NUM_PARALLEL` unset, Ollama uses one slot ([server/sched.go](https://github.com/ollama/ollama/blob/v0.40.18/server/sched.go); [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)) (V). The server log on the test Mac confirms `n_slots = 1` (M). So:

- Requests two and three wait in the queue.
- Wall time is roughly three times one request.
- The client's timeouts have to allow for the wait (Inf).

**Raising parallelism multiplies the KV cache.** Setting the variable to 3 starts llama-server with three times `num_ctx`, which triples the KV cache (V, same sources). Gemma's sliding-window layers scale with it ([PR #19327](https://github.com/ollama/ollama/pull/19327)) (V).

**On MLX, parallelism depends on free memory.** Since v0.40.17, with the variable unset, Ollama picks 8, 4, 2 or 1 slots from the memory free after reserving 4 GiB ([mlxrunner/parallel.go](https://github.com/ollama/ollama/blob/v0.40.18/mlxrunner/parallel.go)) (V). So memory in use on MLX varies with the machine and with whatever else is open (Inf).

The tables below assume one slot and show three slots where that changes the tier.

## The KV cache, not the weights, separates the candidates at 32k

### Checking the arithmetic against the test Mac

**Llama 3.2 3B.** The method was checked against the one model loaded at 32k on the test Mac. The server there runs with two non-default settings, `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`. Its log shows (M):

| Buffer | Size |
|---|---|
| Model, on the GPU | 1,918 MiB |
| Model, on the CPU | 308 MiB |
| KV cache (q8_0) | 1,904 MiB |
| Compute | 393 MiB |
| **Total** | **about 4.7 GB** |

The f16 KV computed from the GGUF header is 3.5 GiB (C). On Ollama's default f16 cache that gives about 6.2 GB from download sizes, or about 6.7 GB from the measured buffers (C). `ollama ps` reported 5.6 GB for the same model at 32k (M). That was on the q8_0 server, where the logged buffers sum to about 4.7 GB, so `ollama ps` reads about 0.9 GB above the buffers, and the gap is unexplained. What the log does validate is the KV term: 1,904 MiB measured at q8_0 against about 1,792 MiB predicted. Read `ollama ps` on real machines before quoting totals.

**Gemma correction.** A first pass sized Gemma's sliding-window layers at the window length, which gave 0.82 GiB for 26B and 3.28 GiB for 31B. Ollama in fact allocates the window plus a 2,048-token batch, padded, for each sliding layer. This method reproduces the measured figures in [PR #19327](https://github.com/ollama/ollama/pull/19327) (I):

- E2B: 111.56 MiB allocated at 32k with q8_0.
- 31B: 31.0 GiB measured, against 30.4 predicted, at 256k.

The corrected f16 figures per slot at 32k are (C):

| Gemma 4 size | KV per slot at 32k, f16 |
|---|---|
| E2B | 0.2 GiB |
| E4B | 0.6 GiB |
| 12B | 1.4 GiB |
| 26B | 1.2 GiB |
| 31B | 4.8 GiB |

**Qwen caveat: the arithmetic may run low.** An independent benchmark on a 16 GB Linux card ran Ollama 0.17.7 at 19k context ([glukhov.org](https://glukhov.org/llm-performance/benchmarks/choosing-best-llm-for-ollama-on-16gb-vram-gpu/)) (I). For two other models the same arithmetic matches within 0.4 GB; for Qwen 3.5 it does not:

| Model | Reported at 19k (I) | Same arithmetic (C) |
|---|---|---|
| qwen3.5:9b | 9.3 GB | about 7.7 GB |
| qwen3.5:27b | 24 GB | about 19.8 GB |
| qwen3.5:35b | 27 GB | about 23.5 GB |
| mistral-small3.2:24b | 19 GB | about 19.4 GB |
| ministral-3:14b | 13 GB | about 13.0 GB |

So the Qwen-family figures here may be 1.5–4 GB low. That benchmark predates Ollama's move to llama-server, so the gap needs re-measuring (Inf).

### Memory per model

Memory in use at 32k context, f16 KV, one slot unless stated. These are GGUF figures: they hold on Linux and for Macs on Ollama before 0.40. A current Mac runs the Gemma 4 and Qwen 3.5 tags as MLX builds, whose weights are up to 2.9 GB larger at the small end (E2B 7.5 against 4.6 GB, E4B 9.5 against 6.6, Qwen 3.5 9B 8.9 against 6.6) and whose KV and parallelism policy was not measured, so Mac fits below carry that uncertainty:

| Model (tag) | Weights, GGUF download (M) | KV per slot at 32k (C) | Compute (Inf) | **In use at 32k (C)** | Three slots (C) | Licence |
|---|---|---|---|---|---|---|
| llama3.2:3b | 2.02 GB | 3.50 GiB = 3.76 GB | 0.4 GB | **6.2 GB** (6.7 from measured buffers) | 13.7 GB | Llama 3.2 Community Licence ([card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)) (V) |
| qwen3.5:4b | 3.32 GB | 1.00 GiB = 1.07 GB | 0.4–0.8 | **4.8–5.2 GB** (perhaps ~1.5 more) | 6.9–7.3 GB | Apache 2.0 (M, GGUF header) |
| gemma4:e2b | 4.59 GB | 0.2 GiB = 0.21 GB | 0.4–0.8 | **5.2–5.6 GB** | 5.6–6.0 GB | Apache 2.0 (M) |
| gemma4:e4b | 6.58 GB | 0.6 GiB = 0.64 GB | 0.4–0.8 | **7.6–8.0 GB** | 8.9–9.3 GB | Apache 2.0 (M) |
| qwen3.5:9b | 6.55 GB | 1.00 GiB = 1.07 GB | 0.5–1.0 | **8.1–8.6 GB** (9.3 reported at 19k, I) | 10.3–10.8 GB | Apache 2.0 (M) |
| gemma4:12b-it-qat | 7.15 GB | 1.4 GiB = 1.50 GB | 0.5–1.0 | **9.2–9.7 GB** | 12.3–12.8 GB | Apache 2.0 (M) |
| gemma4:12b | 8.02 GB | 1.4 GiB = 1.50 GB | 0.5–1.0 | **10.0–10.5 GB** | 13.1–13.6 GB | Apache 2.0 (M) |
| gpt-oss:20b | 13.79 GB | ~0.8 GiB = 0.86 GB | 0.5–1.0 | **15.2–15.7 GB** (14 reported at 19k, I) | 16.9–17.4 GB | Apache 2.0 ([card](https://huggingface.co/openai/gpt-oss-20b)) (V) |
| gemma4:26b-a4b-it-qat | 15.63 GB | 1.2 GiB = 1.29 GB | 0.8–1.5 | **17.7–18.4 GB** | 20.3–21.0 GB | Apache 2.0 (M) |
| gemma4:26b | 18.73 GB | 1.2 GiB = 1.29 GB | 0.8–1.5 | **20.8–21.5 GB** | 23.4–24.1 GB | Apache 2.0 (M) |
| qwen3.8:27b | 17.74 GB | 2.00 GiB = 2.15 GB | 1.0–1.5 | **20.9–21.4 GB** (perhaps up to ~25) | 25.2–25.7 GB | Apache 2.0 (M) |
| qwen3.6:35b (35B, 3B active) | 22.62 GB | 0.62 GiB = 0.67 GB | 1.0–1.5 | **24.3–24.8 GB** | 25.6–26.1 GB | Apache 2.0 ([card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)) (V) |
| nemotron-3-nano (30B, 3B active) | 24.27 GB | 0.19 GiB = 0.20 GB | 1.0 | **~25.5 GB** | ~25.9 GB | NVIDIA Open Model License (M) |
| gemma4:31b-it-qat | 18.85 GB | 4.8 GiB = 5.15 GB | 1.0–1.5 | **25.0–25.5 GB** | 35.4–35.9 GB | Apache 2.0 (M) |
| gemma4:31b | 20.39 GB | 4.8 GiB = 5.15 GB | 1.0–1.5 | **26.5–27.0 GB** | 37.0–37.5 GB | Apache 2.0 (M) |
| qwen3.8:27b-q8_0 | 30 GB (V, library page) | 2.00 GiB | 1.0–1.5 | **~33–34 GB** | ~37–38 GB | Apache 2.0 |
| qwen3.6:35b-a3b-q8_0 | 39 GB (V, library page) | 0.62 GiB | 1.0–1.5 | **~41 GB** | ~42 GB | Apache 2.0 |
| qwen3.5:122b (122B, 10B active) | 81 GB (V, library page) | not computed | ~1.5 | **~84–86 GB** (Inf) | — | Apache 2.0 (V, family) |

Two facts come out of the table:

1. **Llama 3.2 3B is not the smallest model at the needed context.** Its classic dense KV cache makes it heavier at 32k than Qwen 3.5 4B and Gemma 4 E2B. Qwen's hybrid attention puts KV on one layer in four; Gemma's sliding-window layers are small.
2. **Gemma 4 31B's large KV is what pushes it past a 32 GB Mac.**

On MLX manifests, both the weight size and the KV policy may differ, and no MLX KV measurement was found.

### Memory left for the model on each Mac

What a Mac can give the model is its RAM minus the everyday load, and never more than the GPU working set. The model's weights on the GPU are wired memory, which macOS cannot compress or swap ([Eclectic Light](https://eclecticlight.co/2022/08/13/activity-monitor-meanings-and-misleadings/)) (I). Everything else is what gets squeezed.

The everyday load is an estimate (Inf) built from these parts:

- **macOS:** about 3.5–6 GB. These are forum anecdotes ([MacRumors forums](https://forums.macrumors.com/threads/tahoe-using-too-much-memory-doing-nothing-is-it-okay.2481387/)) (I), and no controlled measurement was found.
- **A browser with 10–20 tabs:** about 3–8 GB. A browser vendor measured 8.3 GB for Safari with 20 tabs on a 16 GB Mac, and the footprint grows with free memory ([Sigma browser test](https://www.sigmabrowser.com/blog/browser-ram-benchmark-20-tabs)) (V).
- **Mail:** 0.3–0.5 GB. No measurement was found.
- **Bristlenose app and sidecar:** 0.4 GB idle (M). The peak during an analysis was not measured.

| Mac RAM | Everyday load (Inf) | Left for the model (Inf) | GPU working set | Binding limit |
|---|---|---|---|---|
| 8 GB | ~6.5 GB plus 2–3 GB swap under heavy use on an 8 GB MacBook Neo ([MacRumors review](https://www.macrumors.com/2026/03/27/macbook-neo-review/)) (I) | ~0–2 GB | ~5.7–6.7 GB (Inf) | RAM |
| 16 GB | 8–10 GB | ~6–8 GB | ~11.5–13.4 GB (Inf) | RAM |
| 24 GB | 8–10 GB | ~14–16 GB | ~17.2–20.1 GB (Inf) | RAM |
| 32 GB | 8–10 GB | ~22–24 GB | 26.8 GB (M) | RAM |
| 36 GB | 8–10 GB | ~26–28 GB | ~25.8–30.1 GB (Inf) | about equal |
| 48 GB | 9–11 GB | ~37–39 GB | 40.2 GB (I) | about equal |
| 64 GB | 9–11 GB | ~53–55 GB | ~51.5–53.7 GB (Inf) | GPU |
| 128 GB | 10–12 GB | ~116–118 GB | 103 GB (96 GiB, I) | GPU |

**On a 32 GB Mac the measurement changes the limit.** The two-thirds rule would give a 32 GB Mac 18–21 GB, with the GPU limit binding. The measured 26.8 GB working set makes RAM the binding limit, at about 22–24 GB.

## The Mac picker: four models from 16 GB, nothing at 8 GB

### The proposed range

**On a Mac, every tag below pulls an MLX build. On a Homebrew install of Ollama, MLX refuses structured output** (§ "Measured on the Bristlenose task"). The range applies on the Mac only once the client can run on what arrives, which the unconstrained fallback covers; on Linux it applies as written.

The proposal states minimum and recommended RAM as values, not buckets. That way 24 and 36 GB Macs fall where their memory puts them instead of being rounded down to 16 and 32 GB. The often-quoted ladder of 8, 16, 32, 48, 64 and 128 GB skips both, yet 24 GB alone is twice the 32 GB share.

| Slot | Model (tag) | Download to quote | In use at 32k | Minimum Mac | Recommended from | Condition |
|---|---|---|---|---|---|---|
| Smallest | qwen3.5:4b | 4.0 GB | ~5 GB (4.8–5.2; perhaps ~6.5) | 16 GB | 16 GB | client sends the thinking switch |
| Balanced | qwen3.5:9b | 8.9 GB | ~8–9.5 GB (GGUF; MLX weights ~2.3 GB larger) | 16 GB, light browser only | 24 GB | client sends the thinking switch |
| Good | gemma4:12b | 8.0 GB | ~10–10.5 GB | 24 GB (16 GB tight) | 24 GB | none beyond the context fix |
| Better | qwen3.8:27b | 18.2 GB | ~21 GB (perhaps ~25) | 32 GB, only if `ollama ps` confirms ≤ 23 GB | 36 GB | client sends the thinking switch |

**If the thinking switch is not added,** the range falls back to Gemma 4:

| Slot | Fallback | Download | In use at 32k |
|---|---|---|---|
| Smallest | gemma4:e2b | 7.5 GB | ~5.4 GB (GGUF; MLX weights ~2.9 GB larger) |
| Balanced | gemma4:e4b | 9.5 GB | ~7.8 GB (GGUF; MLX weights ~2.9 GB larger) |
| Good | gemma4:12b | 8.0 GB | ~10.3 GB |
| Better | gemma4:26b | 19 GB | ~21 GB |

The 26B fallback is conditional on Bristlenose's own measurement of its loop rate, and the smallest fallback is weak at long context (see the quality notes below). The smaller QAT tags cut 0.9–3.1 GB from 12B, 26B and 31B: `gemma4:12b-it-qat` saves 0.9 GB and `gemma4:26b-a4b-it-qat` saves 3.1 GB. One independent test found no loss on JSON or 12k-token recall at 12B ([3h4x](https://3h4x.github.io/tech/2026/06/08/gemma4-qat-vs-non-qat)) (I).

### What to offer on each Mac

| Mac RAM | Offer | Why |
|---|---|---|
| 8 GB | Nothing; point to a cloud provider (Claude, ChatGPT, Azure OpenAI or Gemini) | The lightest model that holds a transcript needs ~5 GB of wired memory. With a browser and Mail open, that leaves under 3 GB for everything else on a machine that already swaps (Inf). |
| 16 GB | Smallest. Balanced or Good only with a light browser. | Smallest fits the ~6–8 GB budget. The 8–10.5 GB models exceed it, and macOS would compress the other apps to make room (Inf). |
| 24 GB | Good. Balanced is also comfortable. | ~10.3 GB in use against a ~14–16 GB budget and a ~17–20 GB GPU working set. Three slots of Good (~13.4 GB) still fit (Inf). |
| 32 GB | Better, if a real load confirms ≤ 23 GB. Otherwise Good. | ~21 GB computed against a ~22–24 GB budget. If the Qwen overshoot holds, it is over (Inf). |
| 36 GB | Better | ~5–7 GB of slack (Inf) |
| 48 GB | Better, with room for three slots (~25.5 GB) | gemma4:31b (~27 GB) fits, if its loop rate measures clean. qwen3.6:35b (~24.5 GB, 3B active) is the faster alternative (Inf). |
| 64 GB | Better, or a Q8 build: qwen3.8:27b-q8_0 (~33–34 GB) or qwen3.6:35b-a3b-q8_0 (~41 GB) | `num_ctx` must be set, or the 256k default applies (Inf) |
| 128 GB | As 64 GB. qwen3.5:122b (81 GB download, ~84–86 GB in use, Inf) is the only larger candidate. | Under 1% of Macs. gpt-oss:120b is left out for thinking. |

### Against today's catalogue

| Today's entry | What the app says | Measured or computed | Verdict |
|---|---|---|---|
| Llama 3.2 3B (also the CLI default) | 2 GB download, min 4 GB | 2.02 GB (M); 6.2–6.7 GB at 32k (C), 4.3 GB in `ollama ps` on 0.40.18 with q8_0 KV (M); text-only, so silently truncated at the 4k default | The download is right. Measured on the task even at 32k, the output is not usable (below). Retire it, as the default and from the picker. |
| Gemma 4 E4B | 3 GB, min 8 GB, recommended ≥ 15 GB | 6.58 GB GGUF, 9.46 GB MLX, 9.61 GB for older pulls (M); 7.6–8.0 GB in use (C), but 4.7 GB resident measured for the older GGUF at 32k with q8_0 KV (M) | No manifest is 3 GB. **On a current Mac it pulls the MLX build, which refused structured output on the test Mac's Homebrew install: the app's recommended model for 15–35 GB failed at the first call (M).** On GGUF at 32k it ran the task (below). It becomes the balanced fallback once the Mac can run it. |
| Gemma 4 26B | 16 GB, min 24 GB, recommended ≥ 35 GB | 18.73 GB GGUF; 16 GB is the lower end of the tag page's range (V); 20.8–21.5 GB in use (C) | Min 24 GB is too low; the floor is 32 GB. Open loop bug. |
| Gemma 4 31B | 20 GB, min 32 GB, recommended ≥ 47 GB | 20.39 GB GGUF, 19.42 GB MLX (M); 26.5–27.0 GB in use, ~37 GB with three slots (C) | On a 32 GB Mac it exceeds both the RAM budget and the measured 26.8 GB working set. The realistic minimum is 48 GB. Open loop bug, worst of the family. |

**The documentation table has the same problems.** It reads "Under 16 GB → Llama 3.2 3B ~2 GB; 16–32 GB → Gemma 4 E4B ~3 GB; 36–47 GB → Gemma 4 26B ~16 GB; 48 GB+ → Gemma 4 31B ~20 GB":

- Its smallest row recommends a model that truncates.
- It gives E4B a size no manifest has.
- It puts 32 GB Macs on E4B, although they could run a model of about 21 GB.

### Quality notes

No proposed model has a published result on this task: verbatim quotes, topic boundaries and themes over a 10–15k-token transcript, returned under a JSON schema. The order within the range rests on size and vendor numbers, which are not directly comparable across families. Gemma publishes MRCR and Tau2 but no IFEval; Qwen publishes IFEval, IFBench and AA-LCR but no MRCR.

**Qwen 3.5 4B (smallest).** Vendor scores ([card](https://huggingface.co/Qwen/Qwen3.5-4B)) (V):

| Benchmark | Qwen 3.5 4B |
|---|---|
| IFEval | 89.8 |
| IFBench | 59.2 |
| LongBench v2 | 50.0 |
| AA-LCR | 57.0 |

Llama 3.2 3B's IFEval is 77.4 ([card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)) (V). No independent figure exists at this size. Two cautions apply to this slot:

- **The cost of forcing a format is largest at the small end.** Asking for a format degrades open models ([Format Tax, Apr 2026](https://arxiv.org/abs/2604.03616)) (I). Below 3B, hard schema decoding took validity from 61.5% to 100% but cut accuracy from 19.7% to 11.0% ([Constraint Tax, May 2026](https://arxiv.org/abs/2605.26128)) (I).
- **Long inputs are hard for small models.** Older small models lost most of their non-literal retrieval accuracy by 16k tokens. Llama 3.1 8B scored 22.6% at 16K against a base of 76.7 ([NoLiMa](https://arxiv.org/html/2502.05167v3)) (I).

Expect missed quotes from the middle of a transcript rather than outright failure (Inf).

**Qwen 3.5 9B (balanced).** Vendor scores ([card](https://huggingface.co/Qwen/Qwen3.5-9B)) (V):

| Benchmark | Qwen 3.5 9B |
|---|---|
| IFEval | 91.5 |
| IFBench | 64.5 |
| LongBench v2 | 55.2 |
| AA-LCR | 63.0 |

Qwen's own table puts gpt-oss-20B at an AA-LCR of 30.7 (V, a vendor reporting a competitor). Prompt reading dominates the time:

- A 16 GB M2 manages about 110 tokens a second of prompt processing under MLX ([oMLX community benchmark, via search summary](https://omlx.ai/benchmarks/g0iz2zz0)) (I).
- At that rate, reading one transcript takes about two minutes (Inf).

**Gemma 4 12B (good).** Vendor scores ([model card](https://gemma.ai/models/gemma-4/model-card/)) (V):

| Benchmark | 12B | 26B | E4B |
|---|---|---|---|
| MRCR v2 8-needle at 128k | 43.4% | 44.1% | 25.4% |
| Tau2 | 69.0 | 68.2 | — |

The independent evidence is one practitioner test on Apple silicon at 32k ([3h4x](https://3h4x.github.io/tech/2026/06/08/gemma4-qat-vs-non-qat)) (I):

- QAT and Q4_K_M both passed strict JSON and recall from a ~12k-token log.
- Each scored 4.5 out of 6.
- The QAT build decoded 27% faster.

No loop reports exist at this size, but nobody has tested it either. It needs no client change beyond the context fix.

**Qwen 3.8 27B (better).** It is the newest dense Qwen (August 2026), with a vendor IFBench of 79.5 ([card](https://huggingface.co/Qwen/Qwen3.8-27B)) (V). On Artificial Analysis's index, its predecessor Qwen 3.5 27B scores 37 non-reasoning against Gemma 4 31B's 32. That is the best independent result without thinking in the sub-32B group ([Artificial Analysis, Apr 2026](https://artificialanalysis.ai/articles/sub-32b-open-weights)) (I).

It is a dense model, which limits speed on base chips:

- A base M5 or M6 with 153–170 GB/s of bandwidth would decode ~17 GB of weights at under ~10 tokens a second (Inf: bandwidth divided by the bytes read per token; [MacBook Pro specs](https://www.apple.com/macbook-pro/specs/)).
- That means a few minutes per call.

From 36 GB, qwen3.6:35b, with 3B active parameters, is the speed option. It runs at about 60–110 tokens a second on an M4 Max under MLX ([oMLX community benchmark](https://omlx.ai/benchmarks/fqabp6rx)) (I, secondary).

**Gemma 4 26B and 31B.** The 31B is the strongest long-context model in either family, at 66.4% on MRCR (V). Both carry the loop bug, and the 31B also has the largest KV cache.

**Models left out.**

- **gpt-oss:20b.** It cannot stop thinking. An independent write-up documents its schema failures under Ollama ([glukhov.org](https://www.glukhov.org/llm-performance/ollama/ollama-gpt-oss-structured-output-issues/)) (I).
- **Nemotron.** It thinks by default, and its NVIDIA licences need reading first.

**Applies to every pick.**

- **4-bit is acceptable at this input length.** It is usually fine at short context; large losses were measured only above 64k tokens ([Mekala et al., 2025](https://arxiv.org/abs/2505.20276)) (I).
- **Low-bit models invent quotes.** A 2026 study of interview transcripts found low-bit models hallucinated more ([Adeseye et al., 2026](https://arxiv.org/abs/2605.20193)) (I). So a verbatim match of each quote against the transcript matters most at Q4 and below.

## One documentation table for macOS and Linux

**On Linux with a discrete NVIDIA or AMD GPU, the tier is the card's VRAM.** The model is not sharing that memory with the desktop and the browser, so a 16 GB card goes further than a 16 GB Mac. System RAM only decides how far a model can spill out of the card, and spilling is slow. In the same independent test, both models ran at a 43/57 CPU/GPU split ([glukhov.org](https://glukhov.org/llm-performance/benchmarks/choosing-best-llm-for-ollama-on-16gb-vram-gpu/)) (I):

| Model | Type | Generation speed |
|---|---|---|
| qwen3.5:27b | dense | 6.5 tokens a second |
| qwen3.5:35b | mixture-of-experts | 20.7 tokens a second |

Ollama cannot move a mixture-of-experts model's experts to the CPU. The feature request has been open since August 2025 ([#11772](https://github.com/ollama/ollama/issues/11772)) (I). Linux always pulls GGUF, so the GGUF size is the download.

**Cards under 23 GiB get the 4k default**, so the context must be set on most Linux machines too. That covers the 8, 12 and 16 GB cards, about 80% of the GPUs in Steam's October 2026 survey ([Steam](https://store.steampowered.com/hwsurvey/Steam-Hardware-Software-Survey-Welcome-to-Steam)) (I). A 24 GB card probably reports enough for 32k (Inf).

| Range | Model | Download (Linux GGUF; Mac MLX) | Linux with NVIDIA or AMD GPU (VRAM) | macOS (unified memory) | Unified-memory x86 (memory given to the GPU) or CPU-only (RAM) |
|---|---|---|---|---|---|
| Smallest | qwen3.5:4b | 3.3 GB (Mac 4.0) | 8 GB card | 16 GB | Strix Halo: 8 GB share. CPU-only: 16 GB RAM, slow. |
| Balanced | qwen3.5:9b | 6.6 GB (Mac 8.9) | 12 GB card | 24 GB (16 GB tight) | 12–16 GB share |
| Good | gemma4:12b | 8.0 GB | 16 GB card (12 GB tight) | 24 GB | 16 GB share |
| Better | qwen3.8:27b | 17.7 GB (Mac 18.2) | 24 GB card (tight); 32 GB card comfortable | 32 GB (tight), 36 GB | 32 GB share |
| Better, faster alternative (3B active) | qwen3.6:35b | 22.6 GB (Mac 23.1) | 24 GB card with some spill | 36–48 GB | 32–64 GB share |
| Not usable | — | — | under 8 GB | 8 GB | 8 GB RAM, CPU-only |

**If the thinking switch is not added,** the Gemma column applies on every platform: gemma4:e2b, e4b, 12b and 26b, with their GGUF sizes (4.6, 6.6, 8.0 and 18.7 GB) and memory in use (~5.4, ~7.8, ~10.3 and ~21 GB). The same platform minimums hold, except that the 26B needs a 24 GB card.

**CPU-only machines are slow.** On recent laptop and mini-PC chips, Ollama generated 9–24 tokens a second with Llama 3.2 3B on the CPU ([geerlingguy/ai-benchmarks](https://github.com/geerlingguy/ai-benchmarks)) (I). No measured CPU prompt-processing figure was found, so the time to read a 14k-token transcript is unknown. It is plausibly several minutes (Inf). Three concurrent requests would compete for the same memory bandwidth.

**Strix Halo (Ryzen AI Max+) behaves like a Mac with a dial.** It is on Ollama's ROCm list ([Ollama GPU docs](https://docs.ollama.com/gpu)) (V). Its tier is the memory given to the GPU in the BIOS, not the installed total. AMD ran 64 GB of a 128 GB machine as GPU memory ([AMD ROCm blog, May 2026](https://rocm.blogs.amd.com/artificial-intelligence/ryzen-uma-llm/README.html)) (V):

- Qwen 3.5 35B-A3B ran 100% on the GPU, at 154.5 tokens a second of prompt processing and 42 a second of generation.
- The 122B spilled 39% to the CPU and fell to 8.6 tokens a second.

At 154.5 tokens a second, a 14k-token transcript takes about 90 seconds to read before the first output token (Inf).

**A Linux desktop leaves more memory free than macOS.** It idles at about 0.9 GB with GNOME and 1.2 GB with KDE Plasma ([computingforgeeks, Oct 2026](https://computingforgeeks.com/desktop-environment-ram-usage/)) (I), plus the browser. That matters for CPU-only and unified-memory machines, where system RAM is the whole budget.

**Drivers set the floor** ([Ollama GPU docs](https://docs.ollama.com/gpu)) (V):

- NVIDIA needs driver 550 or newer, or 570 for compute capability 5.0–6.2.
- AMD needs ROCm 7 on a listed card.
- Other GPUs go through Vulkan, which estimates VRAM unless Ollama has `cap_perfmon`.

## Conclusion

**The catalogue has been quoting download sizes at a context that cannot hold the work.** The unit that decides fit is memory in use at the needed context, and it reorders the models: the KV-cache design matters more than the parameter count. That is why a 3B dense model is heavier at 32k than a 4B hybrid. It is also why Gemma's 31B, not its 26B, is the one that misses a 32 GB Mac. Setting the context explicitly does two jobs. It lets the work fit, and it turns a silent wrong answer into either a correct answer or a visible error. It is needed at the top of the range too, where the 256k default inflates memory instead of starving it.

**The practical floor for local analysis is a 16 GB Mac or an 8 GB card.** Below that sit roughly three in ten Macs in the one available sample, and those users are cloud users.

**The order of work follows from these dependencies:**

1. The context setting, the thinking switch and response validation, all in the client.
2. A Bristlenose-specific measurement of each candidate.
3. Only then, the picker.

Without step 2, choosing between the Gemma and Qwen lines would be choosing between one family's documented failure (the loop bug) and another family's undocumented one.

## Measured on the Bristlenose task (27 Nov 2026)

A sibling measurement ran Bristlenose 0.49.0's `analyze` on three public test sessions (18, 36 and 38 minutes), on the same M2 Max with 32 GB, Ollama 0.40.18, flash attention on and q8_0 KV, against Claude Sonnet 4.6. Full method, the verbatim check and the raw figures: [`experiments/ollama-quality/README.md`](../../experiments/ollama-quality/README.md) (M).

| | Claude Sonnet 4.6 | Gemma 4 E4B, GGUF, 32k | Gemma 4 E4B, GGUF, 4k | Llama 3.2 3B, 32k |
|---|---|---|---|---|
| Finished | yes, 5 min 10 s | yes, 37 min 19 s | no: failed after 10 min | three sessions: abandoned after 89 min; one 18-minute session: 1 min 30 s |
| Quotes | 85 | 95 (92 distinct) | none | 15 (13 distinct), on the one session |
| Verbatim (exact / joined / altered / invented) | 75 / 8 / 2 / 0 | 71 / 18 / 6 / 0 | — | 8 / 4 / 0 / 3 |
| Sections / themes | 13 / 8 | 6 / 6, one a catch-all | — | 1 / 1 ("Uncategorised") |

What this settles for the catalogue:

- **Gemma 4 E4B can do the job on GGUF at 32k**, as a starting point: quotes nearly all verbatim and covering the same minutes as Claude's, themes loosely fitted, sections merged, about seven times slower than Claude on this Mac.
- **At 4k the same model fails**, after topic segmentation "succeeds" on prompts cut to 2,051 tokens. The error the user sees blames `max_tokens`, not the context.
- **Llama 3.2 3B is not fit to offer.** On 0.40.18 one call ran to about 21,000 tokens until the 30-minute timeout. Where it finished, quotes repeated (29 of 34 the same sentence on one session under 0.20.7), every timecode was 0:00, and a moderator's words were given to a participant.
- **Memory of the E-models is lower than the arithmetic.** The older E4B GGUF had 4.7 GB resident at 32k with q8_0 KV. Its 5.4 GB per-layer embedding table is memory-mapped and read sparsely; `ollama ps` showed 1.2 GB, an undercount. The MLX build showed 9.4 GB in `ollama ps`. The figures in "Memory per model" count the whole table, so they overstate E2B and E4B.
- **Three sessions at once overran a one-slot server.** Ollama served one request at a time, the 570-second pass deadline counted time spent queued, and the abandoned run told the user to check their network connection. This is the queue described in "Three concurrent requests run one at a time": on GGUF, Bristlenose's concurrency of 3 queues rather than runs in parallel.

These are product findings for the client (context, structured output on MLX, the `max_tokens` cap, the deadline, the error text). Three were fixed on 27 Nov 2026: the context, the MLX refusal, and thinking (§ "Ways to set the context"). The deadline that counts queued time, and its "check your network" wording, remain.

### With the fixed client (27 Nov 2026, evening)

The same three sessions, re-run with the client fixes in place (CLI from main at `331d7e984`, which includes the context, fallback and thinking fixes), on Homebrew Ollama 0.40.18 with q8_0 KV and flash attention, at Bristlenose's default concurrency of 3 (M):

| | Claude Sonnet 4.6 (earlier run) | Gemma 4 E4B, MLX (Mac default; 501, then unconstrained with client validation) | Gemma 4 E4B, GGUF (schema enforced) |
|---|---|---|---|
| Finished | yes, 5 min 10 s | with a warning, 13 min 10 s | yes, 15 min 47 s |
| Quotes | 85 | 105 | 82 |
| Verbatim (exact / joined / altered / invented) | 75 / 8 / 2 / 0 | 43 / 47 / 15 / 0 | 64 / 17 / 1 / 0 |
| Sections / themes | 13 / 8 | 7 / 7, one catch-all | 5 / 8, 17 quotes uncategorised |
| Failed calls | 0 | 3: the discussion lens, one per session | 0 |
| `ollama ps` | — | 9.6–10 GB, runner mlx, context 32768 | 1.2 GB (undercounts), llamacpp, 32768 |

- **The Mac's default build now runs.** Earlier the analysis failed in 8 seconds; now it finishes in 13 minutes.
- **Without a grammar, enum fields drift.** The discussion lens's labels failed validation in all three sessions (`literal_error` on `kind`, after 3 attempts), and 23 quotes came back with an unrecognised sentiment such as "neutral" or null.
- **The transcript's speaker label leaks into quotes.** 58 of the 105 MLX quotes begin with "(Speaker A)", against none on GGUF. That accounts for much of the gap in exact matches (Inf).
- **The GGUF run went from 37 minutes to 16** on the same model with the fixed client. The earlier run had lost time to pass deadlines and split retries.

What the run folder shows on a closer read, and what was done about it (27 Nov 2026, late):

- **The speaker label is in `verbatim_excerpt`, not in the quote.** No quote's text carries it; 58 excerpts do (M). The model copied the transcript exactly: `analyze` read each line's label, `(Speaker A)`, as part of the words, so every provider's prompt carried it, and GGUF and Claude chose not to copy it. Serve finds a quote in its transcript by the excerpt, and its transcript has the label stripped, so those 58 excerpts would not match (Inf). Fixed at the source: `analyze` now moves a label the project recorded for the session out of the words, the serve importer's own rule. A run folder that holds only `transcripts-raw/` has no record, and keeps the label; copy `.bristlenose/intermediate/speaker-info/` with it. Checked once on gemma4:e4b MLX, on the first four minutes of one session: 7 quotes, no excerpt opening with a bracket (M).
- **The discussion lens's labels: the model put another field's value in `kind`.** Rerun once on one session (57 turns): it wrote `role`'s `"core"` into `kind` on 31–33 turns, on each of three attempts (M). Validation caught every one; "core" names no kind, so it is not mapped. Listing each enum field's allowed values in plain words made it slightly worse (45 outside the set on the last attempt, against 26 without), and naming them in the retry turn changed nothing (M, one run each). Both were dropped. The last attempt now keeps the labels that validate, the turns it leaves out read "unclassified", and the lens is marked partial (the house salvage, opted in for this reply); a reply mostly outside the set still fails. On that rerun the session kept 31 of 57 labels. In the measured run, the two sessions that failed on one bad label (1 in 29, 1 in 64) would have kept the rest (Inf).
- **A reframed classify prompt cures the swap, at a price (28 Nov 2026).** A proposed 1.1.0 of the lens's turn-labelling prompt (same definitions; `kind` and `role` numbered apart, each field's allowed words on one line, one worked example) was run against 1.0.0 on 22 sessions (Talismanic with and without its guide, six FOSSDA oral histories, two synthetic studies), with Claude as the reference and Claude 1.0.0 run twice as the noise floor (`experiments/discussion-prompt-eval/`). On Gemma 4 E4B MLX, `kind = "core"` fell from 157 to 0 over every attempt and sessions lost from 4 to 1 (M); the 57-turn session failed in all three 1.0.0 runs and in one of two 1.1.0 runs, that one on JSON nulls a `None → ""` reading would have kept (54 of 57, replayed) (M). `closing` in `kind` stayed, and with no guide Gemma still labels most turns `planned` or `adlib` against items that do not exist, under either prompt (M). Qwen 3.5 4B MLX, also without a grammar, never drifted under either (M, one run). On Claude the new framing moved labels beyond its own noise on the guided study (kind 78% against a 95% floor), so it is the owner's call; as written its JSON example also breaks `str.format`, and the brace-free form moves Claude less (88%) (M).
- **Sentiment is not an enum anywhere.** `sentiment` is `str | None` on every path, so a grammar holds it no more than the fallback does. The 23 were reported as "neutral" and the string "null" (the log keeps the first two values only), and quote extraction stores an unrecognised value as no sentiment, which is what the field asks for when a quote is descriptive. No change.

## Beyond Gemma and Qwen: the wider field (27 Nov 2026)

A second pass looked at every other family Ollama carries: Phi, Granite, SmolLM, OLMo, Mistral (Ministral, NeMo, Small, Magistral, Medium), Llama 3.x and 4, the DeepSeek-R1 distills, and everything the library added or updated from July to November 2026. It also covered the prior art on local models for interview analysis, and the Gemma 4 loop and MLX structured-output problems in more depth. No model was pulled or run. Registry sizes, GGUF headers, Ollama's source at v0.40.18, and the test Mac's files and log are (M). Labels otherwise follow this note's scheme. A bug reporter's measurements in an issue are (I). Ollama's source, commits and release notes are (V).

**The short answer.** No family beyond Gemma 4 and Qwen 3.5/3.8 beats the shortlist on the evidence available. One entrant could change a tier: **Bonsai 2 27B**, a 2-bit derivative of Qwen 3.8 27B that needs about 10.4 GB at 32k (C), which would put 27B-class analysis on a 16 GB Mac if its quotes stay verbatim. Most July–November additions are coding-agent tunes or cloud-only.

### Structured output on MLX: a packaging gap

The 501 "structured output is unavailable" in § "Measured on the Bristlenose task" comes from **Homebrew's Ollama package, not from MLX**.
- On the test Mac, Homebrew's 0.40.18 has only `libmlxc.dylib` in `libexec/lib/ollama/mlx_metal_v3/`. The server log reads `source=grammar.go:74 msg="Structured output is unavailable" error="xgrammar library not found at …/mlx_metal_v3/libollama_xgrammar.dylib"` (M).
- In the source, the MLX runner's grammar engine is nil when the XGrammar library fails to load, and every structured request then gets the 501 ([grammar.go L52–81, L133–142](https://github.com/ollama/ollama/blob/v0.40.18/mlxrunner/grammar.go#L52-L81)) (V).
- Ollama's own build ships that library in every MLX payload, and its CI refuses a payload without it ([build_darwin.sh](https://github.com/ollama/ollama/blob/v0.40.18/scripts/build_darwin.sh#L118)) (V).
- The Homebrew formula never builds it (M). The gap is reported as [Homebrew core issue #302645](https://github.com/Homebrew/homebrew-core/issues/302645) (opened 6 Sep, still open), where a user names the `ollama-binary` cask as a workaround (I). Ollama commit `9a4b136ef` (16 Nov, in 0.40.18) lets packagers supply XGrammar; the formula doesn't use it yet (V/M).

A Mac on an MLX tag therefore gets one of three behaviours. Up to 0.33.0, the schema is dropped and the reply is HTTP 200. From 0.33.1 with the library, as in the official app, the schema is enforced. From 0.33.1 without it, as on Homebrew, the reply is 501 (Inf, from the release notes and commits). That the official app enforces Bristlenose's schemas on MLX is likely, but it **was not measured**.

Where MLX enforces a schema, it has a failure of its own. In [ollama#18567](https://github.com/ollama/ollama/issues/18567), `gemma4:e2b-mlx` under a schema emitted whitespace until the output cap on 3 of 12 runs, and on 0 of 12 on GGUF (official 0.34.2, temperature 0.3) (I). It was closed as standard behaviour. The v0.40.18 MLX runner has no whitespace bound (M, source search), while llama.cpp's JSON grammar caps it at 20 characters ([json-schema-to-grammar.cpp](https://github.com/ggml-org/llama.cpp/blob/b12651/common/json-schema-to-grammar.cpp#L229)) (V).

A Mac can ask for the GGUF build only through the native API: `runner: "llamacpp"` on `/api/chat` and `/api/pull`, or the hidden `--runner` flag on `ollama pull` and `run` ([types.go](https://github.com/ollama/ollama/blob/v0.40.18/api/types.go#L138-L146)) (V). `/v1` has no such field (M). Whether `/api/chat` with that field fetches the GGUF child when only the MLX one is on disk is untested.

### Gemma 4's loops: a grammar makes them worse

The loop is open in [gemma#622](https://github.com/google-deepmind/gemma/issues/622), [ollama#15502](https://github.com/ollama/ollama/issues/15502) and [gemma#610](https://github.com/google-deepmind/gemma/issues/610) (unconstrained lists on 26B, reports to 22 Oct). Neither Google nor Ollama has shipped a fix.
- **A grammar amplifies it** (I, the #622 reporter's ten seeds per test on Ollama 0.20.5). 31B looped 7–10/10 under a schema, 26B 4–5/10, and both 0/10 with no schema. Gemma 3 27B was clean. #15502 needed all three of a `format` schema, free-text string fields and Gemma 4.
- **Unconstrained output isn't immune.** Words double with no grammar ("the the"). Google's hosted API looped 2 of 5 runs of 26B under structured output, and AI Studio failed 10/10 on a string-array schema (I). So the model starts the loop and a grammar traps it (Inf).
- **Runner.** The same GGUF on standalone llama.cpp-server gave 0/10 loops and 10/10 valid JSON for 26B and 31B, but 31B on Ollama 0.30.8, by then on llama-server, still collapsed under `format` (I).
- **What doesn't help.** Repeat penalties of 1.0–1.5 under a grammar; greedy decoding; the schema in the prompt for 1,000+ word outputs (10/10 looped). `think=False` removed the loop in one test but made the JSON invalid in all three runs (I). That result came from [ollama#15260](https://github.com/ollama/ollama/issues/15260), where `think=false` dropped the format constraint. It was fixed on 21 Apr 2026 in 0.20.x (V), and on 0.40.18 a GGUF Gemma 4 E4B returned valid schema JSON with `format` and `think:false` (M, one call). Google's card gives temperature 1.0, top_p 0.95, top_k 64 and nothing on structured output ([model card](https://gemma.ai/models/gemma-4/model-card/)) (V). No source tests Bristlenose's 0.1–0.2.
- **Smaller sizes.** E2B, E4B, 26B and 31B loop on long factual enumeration with no JSON, at about 12% of runs ([arXiv:2606.13705](https://arxiv.org/abs/2606.13705)) (I). The 12B loops while thinking on llama-server (I, forum). Bristlenose's E4B GGUF run under its schema finished without a recorded loop (M).

For Bristlenose this means that for Gemma 4, unconstrained output with the schema in the prompt and client-side validation has the lowest reported loop rate on any runner (Inf). It is the better path, not a degraded fallback. A verbatim quote is copied rather than invented, which the reports suggest is less loop-prone, but that is unmeasured (Inf).

### Other families: nothing beats the shortlist

No Mistral, Llama, DeepSeek, Phi, Granite, OLMo, SmolLM, Bonsai or LFM2.5 tag has an MLX build (M). On a Mac today that is an advantage: they never meet the Homebrew 501 or MLX's whitespace runaway, and they always get llama.cpp's bounded grammar. The cost is MLX's speed. The older families also carry dense attention: 4–6 GiB of KV at 32k for the 8–24B models, against 1.0 GiB for Qwen 3.5 9B (C). So Ministral 3 8B at ~10.6 GB is worse on a 16 GB Mac than Qwen 3.5 9B (Inf).

| Model (tag) | MLX on a Mac (M) | Download (M) | In use at 32k (C) | Licence | Thinking | Verdict |
|---|---|---|---|---|---|---|
| Bonsai 2 27B `bonsai-2:27b` (Q2_0, Qwen 3.8 27B derivative) | no | 8.26 GB | ~10.4 GB | Apache 2.0 (V) | on by default; off works through the qwen3.5 renderer (M) | **Measure, 16 GB.** IFEval 91.3 and IFBench 74.0 against 91.5/71.0 at full precision, but MuSR −9 points (V, thinking on); needs Ollama ≥ 0.40.6 (M) |
| Granite 4.2 8B `granite4.2:8b` (25 Aug) | no | 5.35 GB | ~10.0 GiB | Apache 2.0 | on by default; off through the GGUF's Jinja `enable_thinking`, unmeasured | **Measure, 16–24 GB.** RULER 81.0 at 64K, IFBench 79.3 (V); library sets temperature 1.0, so pin it |
| Muse Glimmer 30B `muse-glimmer:30b-q4_K_M` (Aug) | `latest` GGUF; a `30b-mlx` tag exists | 18.16 GB | ~18.7 GB | Apache 2.0 per card (V); no licence layer in the manifest (M) | on; `false` sends a "none" level the card doesn't document | **Measure, 32 GB.** IFBench 77.0, AA-LCR 80.0 at high reasoning (V); 82% hallucination on a knowledge test (I) |
| Mistral Small 3.2 `mistral-small3.2:24b` | no | 15.18 GB | ~20.6 GB | Apache 2.0 | none | Second opinion, 32 GB. Vendor "infinite generations" 1.29%, IF 84.8 (V) |
| Ministral 3 14B `ministral-3:14b` | no | 9.08 GB | ~14.5 GB | Apache 2.0 | none | Second opinion, 24 GB. Trained at 16k, stretched to 256k (V) |
| Inkling 2 Mini `inkling-2-mini:26b-a5b-iq4_NL` (20 Nov) | `latest` is MLX; pin this GGUF tag | 18.27 GB | ~19–19.5 GB | Apache 2.0 | off = effort 0, which the vendor says doesn't fully disable reasoning | Second opinion, 32 GB. Strong long-context (V), days-old runtime support |
| LFM2.5 24B `lfm2.5:24b` | no | 14.53 GB | ~15.2 GB | LFM Open License: no commercial use at $10M+ revenue (V) | always reasons (V) | Only after a licence decision |
| Granite 4.0 H-Tiny `granite4:tiny-h` | no | 4.23 GB | ~4.2 GiB (4 of 40 layers attend) | Apache 2.0 | none | Memory outlier; no long-context evidence |
| Llama 3.1 8B; Llama 3.3 70B; Llama 4 Scout | no | 4.92; 42.52; 67.44 GB | ~9.2; ~53; ~70–74 GB | Llama licences; Llama 4 withholds the multimodal licence from EU entities (V) | none | No. 3.3 70B (IFEval 92.1) only for 96–128 GB |
| Mistral NeMo 12B | no | 7.07 GB | ~12.4 GB | Apache 2.0 | none | No: RULER 69.0 at 32K (I) |
| Magistral 24B; DeepSeek-R1 distills | no | 14.33; 1.1–42.5 GB | — | Apache 2.0; MIT | reasoning only; `false` pre-fills an empty think block (M) | No |
| Phi-4 (16K), SmolLM2 (8K), OLMo 2 (4K) | no | — | can't hold 32k (M) | MIT / Apache 2.0 | — | No |
| Phi-4-mini; Olmo 3 / 3.1 Instruct | no | 2.49; 4.47 / 19.48 GB | ~6.3; ~9.7–20 GiB | MIT; Apache 2.0 | none (`olmo-3:latest` is the Think model) | No. Olmo 3 has a llama.cpp YaRN bug ([#33191](https://github.com/ggml-org/llama.cpp/issues/33191), I) |

**July–November releases.** Thirteen local families arrived or changed (M, [library](https://ollama.com/search?o=newest)). Flint, Laguna, Ripple, North Mini Code and MiMo-V2.6 are coding-agent tunes. Every frontier release is cloud-only on Ollama: GLM-5.3, Kimi K3, MiniMax M3.1, DeepSeek V4, Mistral Large 4 and others. Cohere's in-window models are non-commercial. Bonsai 2, MiMo-V2.6 and Ornith-1.5 share the `qwen35` architecture, so they add no independent lineage (M/Inf). On a Mac, `latest` resolves to MLX for inkling-2-mini, flint, ripple-preview, mimo-v2.6 and lfm3 (M).

**The indices don't line up.** Artificial Analysis's scale appears to have changed between August and November, and Granite 4.2 8B appears there as 5, 11 and 20 (I). No candidate publishes JSON-schema adherence, verbatim-extraction or loop-rate figures.

### Prior art

Published evidence on local models for interview analysis is thin and a generation old. No study tests Qwen 3.x, Gemma 3 or 4, gpt-oss, Mistral Small 3.x or Llama 4 on interview thematic analysis, so Bristlenose's own runs are among the first.
- **Coding.** Open Qwen, Llama and Mistral 7–8B models were not reliable enough for unsupervised coding of 13,000 conversations; Claude 3.5 Haiku had under 3% malformed JSON ([arXiv 2507.17985](https://arxiv.org/html/2507.17985v3)) (I). The best local result found is a 70B model on psychiatric interviews, Jaccard 0.44–0.69 against human themes (I).
- **The cloud bar.** On a focus group, ChatGPT-5 and Claude 4 Sonnet matched human deductive coding (93.5% against 92.7%). Cohen's κ was 0.34, while Gwet's AC1 was 0.93: κ collapses on imbalanced codes, so report AC1 too ([PLOS Digital Health](https://journals.plos.org/digitalhealth/article?id=10.1371%2Fjournal.pdig.0001189)) (I).
- **Quote fidelity.** GPT-5.2 over 20–30k-word batches of heart-failure transcripts gave 68% verbatim, 20% paraphrased, 3% truncated and 9% partly or wholly hallucinated quotes, checked by hand ([JAMIA](https://pmc.ncbi.nlm.nih.gov/articles/PMC13687763)) (I). Recall is a separate failure: 44% of the excerpts humans chose were missed (I). Bristlenose's E4B GGUF run had 0 invented quotes of 95 (M), though the taxonomies differ.
- **Long context.** On NoLiMa, which removes literal-match shortcuts, Gemma 3 12B falls from 87.4 to 27.4 at 8k and 7.3 at 32k, and Llama 3.3 70B holds 85% of its base only to 2k ([NoLiMa](https://huggingface.co/datasets/amodaresi/NoLiMa/raw/main/README.md)) (I). It has no Qwen or Gemma 4 rows. Sending one topic segment of 2–4k tokens rather than a whole session is worth testing (Inf).
- **Format.** JSONSchemaBench finds a two-fold spread in schema coverage between frameworks ([arXiv 2501.10868](https://arxiv.org/abs/2501.10868v2)) (I). The Format Tax paper puts most of the cost of asking for JSON in the instruction, not the decoder ([arXiv 2604.03616](https://arxiv.org/abs/2604.03616)) (I). For Gemma 4 the issue-tracker evidence is stronger than either.
- **Tools.** QDA Miner/WordStat 2026.1 runs local models through Ollama or LM Studio, with no model recommendation (V). No other mainstream QDA tool with a local option was confirmed. A measured recommendation would be unusual in the field (Inf).

### Client findings that bear on the fix

1. **Cap the output.** Ollama's default `num_predict` is -1. On llama-server, generation is then bounded only at 10 × `num_ctx` ([types.go](https://github.com/ollama/ollama/blob/v0.40.18/api/types.go#L1340-L1356); [llama_server.go](https://github.com/ollama/ollama/blob/v0.40.18/llm/llama_server.go#L118-L136)) (V), which fits the ~21,000-token Llama runaway. Size the cap from the expected reply, and treat `length` as a failure.
2. **An HTTP 200 can be empty.** On 0.40.18, `json_schema` requests on the llama.cpp path have returned 200 with an empty body mid-load: 92 of 535 requests, against none on 0.40.16/17 ([ollama#19918](https://github.com/ollama/ollama/issues/19918), open) (I). Validation must reject it.
3. **The default repeat penalty is gone.** PR #17679 (merged 12 Aug, in v0.32.10) changed the default from 1.1 to 1.0 for models that set none, and warns that small older models will repeat more ([commit](https://github.com/ollama/ollama/commit/6a261db7d)) (V). `repeat_penalty` isn't an OpenAI field, so on `/v1` it probably needs the native API or a Modelfile (Inf).
4. **MLX's whitespace runaway** will meet users of the official app once XGrammar loads, as described above. The output cap and the unconstrained fallback cover it.
5. **Prompt-cache reuse is off** for hybrid and sliding-window models on llama-server ([llama.cpp#22940](https://github.com/ggml-org/llama.cpp/issues/22940), closed as stale) (I). That covers Qwen 3.5/3.8, Gemma 4 and most candidates, so each call pays a full 10–15k-token prefill (Inf).
6. **Thinking off is per model, and silence means on.** Since v0.40.17, "off" maps to the model's lowest level, and `/api/show` advertises each model's controls (V). A request that omits `think` for a thinking-capable model is sent with thinking on ([routes.go](https://github.com/ollama/ollama/blob/v0.40.18/server/routes.go#L3241-L3245)) (V), so the client should send `think:false` explicitly, Gemma 4 included. The #15502 report that `think=False` broke Gemma's JSON predates the 21 Apr fix for [#15260](https://github.com/ollama/ollama/issues/15260) (V), and one call on 0.40.18 returned valid JSON with both set (M).

### What to measure next

Measure on the protocol of § "Measured on the Bristlenose task", plus an explicit output cap, a constrained and an unconstrained arm, reasoning tokens counted separately, and quotes scored in both Bristlenose's four classes and JAMIA's five.
- **First runs:** `bonsai-2:27b` (16 GB, against `qwen3.5:9b`), `granite4.2:8b` (16–24 GB), `muse-glimmer:30b-q4_K_M` (32 GB, against `qwen3.8:27b` and `gemma4:26b`).
- **Second opinions:** `mistral-small3.2:24b`, `ministral-3:14b`, `inkling-2-mini:26b-a5b-iq4_NL`.
- **Gemma 26B in three arms:** GGUF constrained, GGUF unconstrained, and MLX on the official app. This decides whether the shortlist keeps its 26B.

The deciding test is Bonsai 2. The vendor reports 98% benchmark retention at 2.25 bits per weight, while this note's § "Quality notes" cites a finding that low-bit models invent more quotes. Only a verbatim check on real transcripts can say which holds.

## The 64 GB pick, and whether an overnight run works (27 Nov 2026)

Nothing here was run on a 64 GB Mac, and no cloud model was used. The pick rests on registry facts measured today, published benchmarks, and this note's own runs.

### 64 GB: Qwen 3.8 27B at 8 bits

_Superseded on 28 Nov 2026: the measured runs put `gemma4:26b` at 64 GB, and an 8-bit 27B would overrun quote extraction's 570-second limit (§ "Why the large dense models lose interviews"). The reasoning is kept as it was._

**Pick: `qwen3.8:27b-q8_0`.** Same model as the 32 GB candidate, at twice the precision.
- **Download:** 29.98 GB (M).
- **Build:** GGUF only, a single manifest with no MLX child (M). So a Mac runs it on llama.cpp with the schema enforced: no 501, and none of the unconstrained path's drift (§ "With the fixed client").
- **Memory at 32k:** about 33 GB, perhaps 37 if the Qwen overshoot in § "Memory per model" holds, and about 4 GB more for three slots (C/Inf). A 64 GB Mac gives a model about 48 GiB of GPU memory (Inf, from the working-set fractions in § "Most Macs and Linux GPUs get a 4k window").
- **Licence and thinking:** Apache 2.0. Thinks by default; the client now sends `think:false`.

Why this one:
- **Higher precision protects quotes.** The 2026 study in § "Quality notes" found low-bit models invent more interview quotes (I). Eight bits is close to the unquantised model, which is the cheapest gain 64 GB buys (Inf).
- **It avoids the known traps.** It doesn't suffer from Gemma 4's grammar-amplified loops at 31B (§ "Gemma 4's loops"), and it isn't exposed to MLX's whitespace runaway.
- **Nothing larger fits.** `llama3.3:70b` needs about 53 GB at 32k, over the budget (C). `qwen3.5:122b` is 81 GB (M).

| Alternative | Download (M) | Why not the pick |
|---|---|---|
| `gemma4:31b-it-q8_0` | 33.84 GB | the loop bug is worst at 31B; Gemma 4 31B's plain `gemma4:31b` pulls MLX on a Mac |
| `qwen3.6:35b-a3b-q8_0` | 38.70 GB, GGUF only | 3B active parameters: about four times faster, but less capacity per token (Inf). The pick if speed matters more than depth |
| `muse-glimmer:30b-q8_0` | 31.01 GB | unmeasured; 82% hallucination on a knowledge test (I) |

**Confidence: moderate.** It rests on one condition that this note's own runs will test: the same model at 4 bits (`qwen3.8:27b`) doing the job on the 32 GB tier.
- **It rises to high** if the 4-bit run gives verbatim quotes, sections and themes near Claude's. The same weights at higher precision should do at least as well (Inf).
- **It falls** if the 4-bit run fails for reasons precision won't fix: invented quotes, themes that don't fit, thinking that leaks despite `think:false`. Then the fallback is `gemma4:31b-it-q8_0`, run unconstrained. If that also fails, the honest answer for 64 GB is "use a cloud provider".
- **It also falls** if a measured load on a 64 GB Mac exceeds about 45 GB, or if `ollama ps` on any Mac shows the Qwen overshoot growing at 8 bits.

### What more memory buys

Up to 32 GB, more memory buys a larger model: E4B-class at 16 GB, 12–27B at 24–32 GB. From 32 to 64 GB it mostly buys **precision and headroom**: the same 27B at 8 bits instead of 4, three slots at once, and room for a browser alongside. Only at 128 GB does a new class of model fit: `qwen3.5:122b`, a 122B mixture-of-experts with 10B active parameters (Inf, from the sizes above). So the step from 32 to 64 GB should be small in quality, and the step from 64 to 128 GB larger. Neither has been measured.

**128 GB, for the docs:** "With 128 GB you can run models such as Qwen 3.5 122B; at that size you'll want to compare a few on your own interviews before trusting one."

### Overnight runs: how long one interview takes

Estimates to an order of magnitude, all (Inf). **Method:** time ≈ prompt tokens ÷ prefill rate + output tokens ÷ decode rate.
- **Decode rate** ≈ 0.65 × memory bandwidth ÷ bytes of weights read per token. Published 2026 benchmarks fit this within about ±25%; for Qwen 3.5 122B-A10B on an M5 Max, the prediction and the measurement are both 66 tokens/s (I, [llama.cpp #4167](https://github.com/ggml-org/llama.cpp/discussions/4167) and community MLX benchmarks).
- **Per interview:** about 33k prompt tokens and 12–22k output tokens over a 3-session run (M, this note's runs).
- **Decode dominates:** prefill is about 15–20% of the time.
- **Calibration:** on this M2 Max (400 GB/s), the method predicts 15–25 minutes for Gemma 4 E4B over three sessions, against 13–16 measured. So it errs on the slow side.

| Tier, typical chip (bandwidth) | Model | Per interview | A two-week study, 10–20 interviews |
|---|---|---|---|
| 16 GB, base chip (100–153 GB/s) | Gemma 4 E4B-class | 15–30 min | 3–10 h: overnight works |
| 32 GB, base to Pro (120–273 GB/s) | 27B at 4 bits | 0.5–1.5 h | 5–30 h: overnight on a Pro; a weekend on a base chip |
| 32 GB, Max (400+ GB/s) | 27B at 4 bits | ~20–30 min | 4–10 h: overnight works |
| 64 GB, Pro (273–307 GB/s) | Qwen 3.8 27B at 8 bits | ~40–60 min | 7–20 h: overnight for a small study, a weekend for a large one |
| 64 GB, Max (400–614 GB/s) | Qwen 3.8 27B at 8 bits | ~20–35 min | 4–12 h: overnight works |
| 64 GB, any | Qwen 3.6 35B-A3B at 8 bits (speed option) | ~5–15 min | 1–5 h |
| 128 GB, Max (546–614 GB/s) | Qwen 3.5 122B-A10B at 4 bits | ~5–10 min | 1–3 h |

Analysis time only: local transcription comes on top. Fanless MacBook Airs may throttle on a run of many hours, and no sustained-load measurement was found.

**The verdict for a researcher** is quality-first. Speed doesn't rule out any tier for a study left running overnight. Quality decides whether the run is worth it:
- **16 GB:** worth it, on today's measurements. Gemma 4 E4B under the schema gave 82 quotes, 64 exact and none invented, with weaker themes than Claude's.
- **32 and 64 GB:** Gemma 4 26B, at about 10 minutes per hour of interview on an M2 Max (§ "Nine models measured").
- **8 GB:** no model examined fits with a browser open, so use a cloud provider.

## Nine models measured, and one model per tier (28 Nov 2026)

**One model per tier:**

| Mac memory | Model | Download on a Mac | In memory at 32k | Evidence |
|---|---|---|---|---|
| 8 GB | none: use a cloud provider | | | Qwen 3.5 4B runs, but finds about half the quotes (M) |
| 16 GB | `gemma4:e4b`, with other large apps closed | 9.5 GB (MLX) | 10 GB | measured, clean (M) |
| 32 GB | `gemma4:26b` | 16 GB (MLX) | 16 GB | measured, clean (M) |
| 64 GB | `gemma4:26b` | 16 GB (MLX) | 16 GB | the 32 GB run, with more room to spare (Inf) |
| 128 GB | "With 128 GB you can run models such as Qwen 3.5 122B; at that size you'll want to compare a few on your own interviews before trusting one." | | | |

**What changed since 27 Nov:**
- **The 64 GB pick is no longer the 8-bit Qwen 3.8 27B.** The 4-bit Qwen 3.8 27B gave the best quotes of any local model. But its quote-extraction passes already take 450–550 s on this Mac, against a 570 s limit. An 8-bit build, or a slower chip, would pass that limit, and the analysis would lose whole interviews (below).
- **16 GB loses its 9B "balanced" step.** On the run below, Qwen 3.5 9B's discussion stage failed.

### How the runs were made

- **Hardware and software:** one M2 Max with 32 GB (400 GB/s) and Ollama 0.40.18 from Homebrew, using flash attention, a q8_0 KV cache and `num_ctx` 32768.
- **Command:** `bristlenose analyze --llm local` on three public test sessions of 18, 36 and 38 minutes (91 minutes in all), with each run in a fresh project.
- **One model at a time.** Each model was pulled, run, stopped and removed before the next started, and no other model ran during any run.
- **Commits.** The runs were spread over the commits `5fdce3f24`, `2bdb7930c`, `dea44c6f7` and `63dbc8274`. Between the first and the last, nothing changed in `bristlenose/llm`, `bristlenose/stages` or `bristlenose/discussion` except install hints, so the runs are comparable (M, `git log`).
- **One run's timing is suspect.** The Qwen 3.5 9B run overlapped a full Xcode build, so its time is probably too long. Its quality is unaffected.
- **Runner.** Every MLX run hit the 501 from Homebrew's missing XGrammar library. The client then asked without a format and validated the reply (§ "Structured output on MLX: a packaging gap"), so the MLX rows are unconstrained and the llama.cpp rows are constrained.
- **Scoring.** Quotes were scored against the source transcript with the four classes of § "Measured on the Bristlenose task".
  - The baseline is Claude on the same sessions: 85 quotes (75 exact, 8 joined, 2 altered), 8 themes, 13 sections and 2 uncategorised quotes.
  - "Invented" was zero for every model.

| Model (runner) | Time | Quotes: exact / joined / altered | Themes | Uncat. | Sections | What went wrong |
|---|---|---|---|---|---|---|
| `gemma4:e4b` (MLX) | 9 m 22 s | 103: 99 / 2 / 2 | 6 | 2 | 7 | 7 sentiments outside the list ("neutral") |
| `gemma4:26b` (MLX) | 15 m 45 s | 96: 89 / 3 / 4 | 5 | 1 | 8 | nothing |
| `qwen3.8:27b` 4-bit (MLX) | 63 m 41 s | 133: 133 / 0 / 0 | 10 | 4 | 7 | 4 passes cut at the deadline and split; nothing lost |
| `gemma4:12b` (MLX) | 43 m 42 s | 127: 120 / 5 / 2 | 6 | 6 | 6 | 3 passes cut and split; 20 sentiments outside the list |
| `qwen3.5:9b` (MLX) | 24 m 45 s | 104: 93 / 11 / 0 | 4 | 1 | 7 | the discussion stage failed (`RouteBatchOut`, 5 errors) |
| `qwen3.5:4b` (MLX) | 18 m 31 s | 49: 33 / 15 / 1 | 5 | 1 | 4 | thin: about half the quotes |
| `granite4.2:8b` (llama.cpp) | 31 m 08 s | 80: 70 / 5 / 5 | 4 | 0 | 6 | no sentiment on any quote; 11 of 46 quotes not placed on a section; one looping quote |
| `bonsai-2:27b` (llama.cpp) | 1 h 59 m | 105: 90 / 13 / 2 | 9 | 4 | 5 | **no quotes from one session**; 2 empty quotes |
| `muse-glimmer:30b-q4_K_M` (llama.cpp) | 1 h 15 m | 35: 34 / 1 / 0 | 4 | 2 | 8 | **no quotes from two of the three sessions** |

All (M), from one run each. Each row is one sample.

### Why the large dense models lose interviews

Quote extraction stops any single call after 570 seconds (`_PASS_DEADLINE_S` in `bristlenose/stages/s09_quote_extraction.py`, since 20 Oct 2026). A session cut short is split in half and retried, down to eighths. One failure ends the session.
- **Where the limit comes from.** It was set for cloud providers: a normal hour takes 230–300 s there, and the limit keeps the SDKs from re-sending a whole job.
- **Local models pay for it.** The local model is the one that runs slowest (M, the call log):
  - Qwen 3.8 27B's passes at every depth took 450–550 s;
  - Bonsai 2 27B and Muse Glimmer 30B overran even at depths 2 and 3, so their sessions ran out of depth.
- **Why that rules out the 8-bit 27B.** It reads twice the bytes per token, so it decodes at about half the speed (§ "Overnight runs"). On this Mac it would overrun at every depth, as Muse did (Inf, high confidence).
- **Slower chips have the same problem.** The 4-bit 27B on a base or Pro chip would also overrun (Inf).
- **Sessions in the field are longer.** The test sessions are 18–38 minutes, and a 60–90 minute interview gives every pass more to write.
- **The clock counts the queue.** Bristlenose sends three sessions at once. On llama.cpp, Ollama serves one at a time (§ "Three concurrent requests run one at a time"), so a pass's 570 s includes its wait behind the others (Inf, from the call log's timing). That probably explains some of the Bonsai and Muse cuts at depth 0. It doesn't explain the 27B's on MLX, where the deeper passes ran after the queue had cleared.

So under today's client the 27B is not offered on any tier. If the limit scaled with the provider, or were lifted for local models, Qwen 3.8 27B would become the quality pick on 32 GB Max chips and on 64 GB. It gave 133 quotes, all exact, and 10 themes against Claude's 8 (M). That change is for the client's owner to decide; this note only reports it.

### What each tier rests on

- **8 GB: use a cloud provider.**
  - Qwen 3.5 4B finished cleanly, with 4.5 GB in memory at 32k (M). It found 49 quotes against Claude's 85, mostly general context, and 4 sections against 13 (M).
  - It wasn't run on an 8 GB Mac, which leaves about 0–2 GB for a model once a browser and Mail are open (§ "Memory left for the model on each Mac") (Inf).
  - **Confidence:** high that a researcher on 8 GB is better served by a cloud provider.
- **16 GB: `gemma4:e4b`.** The fastest run and among the cleanest: 99 of 103 quotes exact and none invented. The discussion stage passed after 4 retries.
  - **Compared with 27 Nov:** on `4d041f0ef` the same model gave 43 exact quotes, 47 joined and 15 altered, with a "(Speaker A)" prefix. The client fixes since then account for the change (M, two runs).
  - **The risk is memory.** It held 10 GB at 32k (M). The GPU allows that, at about 11.5–13.4 GB, but RAM doesn't once a browser is open: the table in § "Memory left for the model on each Mac" leaves about 6–8 GB, so the Mac would swap (Inf). The model is for a run with the browser and other large apps closed, which suits an overnight run.
  - **The fork:** Qwen 3.5 4B (4.5 GB) fits alongside a browser, but finds about half the quotes. This is the one tier where the owner has a real choice.
  - **Confidence:** high on quality, moderate on fit.
- **32 GB: `gemma4:26b`.** A mixture-of-experts model with about 4B active parameters, so it runs at small-model speed. It made no deadline cuts: the longest pass was 460 s for a whole 38-minute session (M).
  - It gave fewer themes and sections than Claude (5 themes against 8, and 8 sections against 13), tied with Muse Glimmer for the most sections of any local model. 89 of 96 quotes were exact, and its 4 altered quotes are mostly the same cross-turn joins that Claude's altered quotes are.
  - The 501 doesn't touch it: it runs unconstrained on MLX, so the grammar-amplified loops of § "Gemma 4's loops" don't apply.
  - **Confidence:** high.
- **64 GB: `gemma4:26b`, the same model.**
  - **Why not a higher-precision Gemma.** The 8-bit tag `gemma4:26b-a4b-it-q8_0` (28.05 GB) is GGUF only (M), so a Mac would run it on llama.cpp under a grammar, which is the arm where Gemma 4's loops are worst.
  - **Why not Qwen.** The 27B waits on the deadline, above. `qwen3.6:35b-a3b-q8_0` is fast enough, but it is unmeasured.
  - **What 64 GB buys today:** headroom for other apps, not a better model.
  - **Confidence:** high that it works, since it is the 32 GB run with memory to spare. Moderate that nothing better fits, because Qwen 3.6 35B-A3B is the untested candidate (Inf).

### Time per hour of interview, measured

On this M2 Max, per hour of interview audio:
- `gemma4:e4b`: about 6 minutes;
- `gemma4:26b`: about 10;
- `gemma4:12b`: about 29;
- `qwen3.8:27b` at 4 bits: about 42.

All (M, wall-clock ÷ 1.5 h of sessions). That puts the 27B at the slow end of the estimate in § "Overnight runs" and the Gemma models below it. A base-chip Mac (100–153 GB/s) should take about three to four times as long (Inf). So a two-week study of 10–20 hour-long interviews would take 4–8 h with E4B on a base 16 GB Mac (Inf), which is an overnight run.

## What must be verified before shipping

1. **The default context on small Macs, on a current Ollama (0.40.18 or later).** On a 16 GB Mac and a 24 GB Mac, read the `vram-based default context` log line and Metal's `recommendedMaxWorkingSetSize`, and confirm whether those machines get 4k. Do the same on one 64 GB Mac to confirm the 256k default.
2. **What a Mac actually pulls, and whether it can run Bristlenose.** Done for `gemma4:e4b` on a Homebrew install (MLX, 501 on structured output). Repeat it on the official Ollama app, which ships the XGrammar library. For each other proposed tag on Apple silicon under 0.40.x, record the build that arrives and its size, and send one `json_schema` request. Then test the GGUF route: `ollama pull --runner llamacpp <tag>` and a `/v1` request. Then load it at 32k and read `ollama ps`, with f16 KV and one slot, and again with MLX's automatic parallelism.
3. **Overflow, before and after the fix.** The silent truncation is reproduced for a Gemma 4 E4B GGUF build at 4k (done, 27 Nov). With the fix, confirm a 13.6k-token transcript arrives whole, with no "truncating input prompt" warning in the server log.
4. **The thinking switch.** Confirm that `reasoning_effort: "none"` on `/v1` turns thinking off for qwen3.5:4b, qwen3.5:9b and qwen3.8:27b under `json_schema`, with valid JSON and no reasoning tokens.
5. **Bristlenose quality for each proposed model, on real transcripts.** Measure:
   - the verbatim-match rate of quotes;
   - coverage across the whole interview;
   - the quality of topic boundaries and themes;
   - schema validity;
   - the loop rate.

   Done for Llama 3.2 3B and Gemma 4 E4B (GGUF) on one M2 Max with 32 GB (§ "Measured on the Bristlenose task"). Extended on 28 Nov 2026 to nine models on MLX and llama.cpp (§ "Nine models measured"). Still to do: one run per tier on a base-chip Mac, sessions of 60–90 minutes, and more than one sample per model.
6. **Qwen memory.** Re-measure Qwen 3.5-family memory at 32k on an Ollama release from the llama-server era, to settle the 1.5–4 GB gap. That figure decides whether Better starts at 32 or 36 GB.
7. **Time and app memory.** Measure the time per session on a base-chip 16 GB Mac and a base-chip 32 GB Mac, and the memory the app and sidecar use at the peak of an analysis.
8. **Linux.** Load the Smallest, Good and Better picks on one 16 GB NVIDIA card and one 24 GB card, and read the default context and `ollama ps` for each.
