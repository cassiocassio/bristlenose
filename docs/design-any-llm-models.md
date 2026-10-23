# any-llm: models and routes, as measured

_Status: record. Measured 23 Oct 2026 on Bristlenose 0.42.0 plus the
unreleased any-llm work (`b1c16d374` → `8b16e797f`), any-llm-sdk 1.27.0,
macOS arm64. One run per model unless noted, so treat close gaps as
indicative. The plan this measures is [`design-any-llm.md`](design-any-llm.md)._

This is what three paid real-account walks (OpenRouter, Mistral, DeepSeek)
and a free local run found. It covers how each route to a model behaves, how
good each model is at Bristlenose's job, and what the walks changed in
Bristlenose. The raw walk logs are private, and their conclusions are here.

## 1. Method

- **Data.** Three interviews from the public FOSSDA oral-history fixture (s1,
  s6, s10: 25, 18 and 17 KB of transcript). None of them has a product
  screen, so **the right number of screens is 0**. A second set was a short,
  real UX session (18 minutes, test data, 8 screens in the shipped report),
  which shows whether a model can follow a flow from screen to screen.
- **Command.** `BRISTLENOSE_ANYLLM_MODEL=<provider:model> bristlenose analyze <tx> --llm any-llm`.
  Tokens, retries and finish reasons came from `llm-calls.jsonl`.
- **Reference.** Claude Sonnet 4.6, run twice. Its A-vs-B agreement is the
  **noise floor**: 90% on FOSSDA and 85% on the UX session. No model can
  score above it.
- **Scores** (each against Sonnet 4.6 run A):
  - **faith**: the share of quotes whose verbatim 5-grams are at least 90%
    present in the transcript. Below 100% means paraphrase or invention.
  - **Jaccard**: the overlap of transcript-seconds that the quotes cover.
  - **tc ok**: the share of quotes whose timecode lands in the turn that
    holds the quote's first words.
  - **sentiment**: agreement with the closest reference quote. Two Sonnet
    runs agree only 64% of the time, so this one is too noisy to rank on.
- **Cost.** List price × recorded tokens. Preflights, live checks and
  cancelled calls aren't counted (see §4.3).

A chart of these numbers is at
[`mockups/any-llm-model-tradeoffs.html`](mockups/any-llm-model-tradeoffs.html).

## 2. Models

### 2.1 FOSSDA (three interviews, no screens)

| Model | Route | Quotes | faith | Jaccard | tc ok | Screens | Themes | Wall | Tokens in / out | List $ |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Sonnet 4.6 (A, reference) | OpenRouter | 70 | 99% | — | 94% | 0 | 12 | 4m 08s | 80k / 26k | 0.62 |
| Claude Sonnet 4.6 (B) | OpenRouter | 76 | 100% | **90%** (noise floor) | 93% | 0 | 15 | 4m 07s | 81k / 27k | 0.64 |
| DeepSeek V4 Pro | native | 75 | 96% | 82% | 93% | 1 | **23** | 2m 42s | 68k / 34k | 0.11 |
| GPT-5.4 mini | OpenRouter | 33 | 100% | 82% | 97% | **7** | 3 | **43s** | 62k / 19k | 0.13 |
| Claude Sonnet 5.5 | OpenRouter | 99 | 100% | 81% | 99% | 0 | 14 | 2m 10s | 100k / 46k | 0.67 |
| Mistral Large | native | 35 | 100% | 81% | 80% | 0 | 9 | 2m 22s | 67k / 26k | — |
| Qwen 3.8 Flash, thinking off | OpenRouter | 54 | 100% | 80% | 98% | 0 | 10 | 2m 56s | 78k / 33k | — |
| DeepSeek Flash | native | **156** | 100% | 77% | 97% | **6** | 12 | 2m 20s | 99k / 57k | 0.05 |
| DeepSeek V4 Flash, thinking | OpenRouter | 37 | 100% | 63% | 92% | 0 | 5 | 7m 19s | 64k / **72k** | 0.02 |
| Grok 4.3 | OpenRouter | 24 | 100% | 62% | 88% | 0 | 5 | 1m 53s | 58k / 19k | 0.12 |
| Llama 3.3 70B | OpenRouter | 30 | 97% | 50% | 83% | **6** | 7 | 5m 01s | 54k / 12k | 0.01 |
| Mistral Small | native | 15 → 38 | 100% | 22–26% | 73–76% | 0 | 4–5 | 1m 16s | 54k / 30k | — |
| Qwen 3.8 Flash, thinking | OpenRouter | — | | | | | | killed at 38 min | | |
| Nemotron 3.5 Super (free) | OpenRouter | — | | | | | | failed at 30 min | | 0 |

**Notes**
- **Mistral cost** wasn't split by model: Large and Small together, 72 requests,
  came to €0.13.
- **Mistral Small** was measured before quote salvage (§4.1). Without it,
  the densest session lost all its quotes in 3 of 3 attempts, and 73% of its
  quoted words came from the interviewer.
- **The Qwen thinking-off row** is a re-run after `8b16e797f`, from the build
  session. All the other OpenRouter rows predate that commit.

### 2.2 The UX session (screens exist; the shipped report has 8)

| Model (OpenRouter) | Quotes | faith | Jaccard | Screens | Wall | Tokens in / out |
|---|---|---|---|---|---|---|
| Claude Sonnet 4.6 (A, reference) | 23 | 100% | — | 10 | 2m 18s | 22k / 7k |
| Claude Sonnet 4.6 (B) | 23 | 100% | **85%** (noise floor) | 9 | 2m 27s | 22k / 8k |
| Claude Sonnet 5.5 | 30 | 100% | 82% | 9 | 1m 20s | 28k / 14k |
| Qwen 3.8 Flash, thinking | 34 | 100% | 79% | 9 | **16m 36s** | 21k / **67k** |
| DeepSeek V4 Flash, thinking | 21 | 100% | 75% | 6 | 5m 18s | 19k / 36k |
| Llama 3.3 70B | 22 | 100% | 68% | 7 | **13m 21s** | 20k / 9k |
| GPT-5.4 mini | 15 | 93% | 55% | 5 | 23s | 15k / 5k |
| Grok 4.3 | 9 | 100% | 54% | 3 | 1m 16s | 18k / 8k |
| Mistral Large 2512 | — | | | | failed at 48s | shared-pool 429 |

Sonnet 4.6, Sonnet 5.5 and Qwen follow the flow from homepage to checkout at
the shipped report's level of detail. GPT-5.4 mini and Grok collapse it to 3–5
screens. Sonnet 5.5 named one "screen" after a finding ("Minimum Order
Reflection").

### 2.3 What the numbers say

- **Sonnet is still the model to recommend.** Nothing cheaper reaches its own
  run-to-run agreement.
- **Four models sit just under the floor on FOSSDA: DeepSeek V4 Pro (82%), GPT-5.4
  mini (82%), Mistral Large (81%) and Sonnet 5.5 (81%).** They differ in how they
  get there:
  - **Mistral Large and GPT-5.4 mini** cover the same ground in half as many
    quotes, each about twice as long.
  - **DeepSeek V4 Pro** over-splits themes: 23, nine of them with two quotes.
  - **GPT-5.4 mini** gives 3 themes and invents 7 screens.
- **No model invented quote text.** Faith was 96% or more everywhere, and the
  lowest scores were paraphrase at the 5-gram bar.
- **Invented screens are the quickest quality tell on interview-only data.**
  Llama 3.3 70B, GPT-5.4 mini, DeepSeek Flash and an older Sonnet 4 run all
  turned topics into screens.
- **Coverage hides calibration.** On AutoCode with Nielsen's heuristics (a
  framework that doesn't fit oral history):
  - Sonnet 4.6 gave all 70 quotes a confidence of 0.10–0.20, so all were
    excluded. That's the right answer.
  - DeepSeek Flash did the same, at 0.10–0.15.
  - Mistral Large proposed a tag at 0.3–0.7 for every quote, some of them
    loose.
  
  A model that applies the wrong framework with confidence costs the
  researcher review time, and the coverage scores can't show it.
- **Speed belongs to the host, not just the model.** Through OpenRouter, Llama
  3.3 70B took 13 minutes on an 18-minute session. GPT-5.4 mini took 23 seconds.

## 3. Routes

### 3.1 OpenRouter (`openrouter:<vendor>/<model>`)

- **Setup.** Sign-up needs no card. One key reaches every vendor: the walk
  ran nine models from seven vendors on it. Model ids come from the public
  `GET https://openrouter.ai/api/v1/models`, and its `supported_parameters`
  says whether a model takes `structured_outputs`. any-llm rides the `openai`
  SDK against `https://openrouter.ai/api/v1`, so no extra SDK is needed.
- **Billing.** Prepaid credit in USD, at the model's own list price. The card
  fee is 5.5% with a $0.80 minimum, so $5 of credit costs about $5.80. A per-key
  credit limit is available, and auto top-up is opt-in.
- **Free models.**
  - Limits: 50 requests a day until $10 has ever been bought, then 1000.
  - Free hosts were unreliable on the day. One returned a 404 from the host,
    one an upstream 429, and one validated but couldn't finish a run.
  - Free hosts may log or train on inputs, so use public data only.
- **Errors arrive in two shapes.**
  - **OpenRouter's own errors** are plain, for example a 401 `User not found.`
    for a deleted key.
  - **A failure at the model's host** is wrapped as `Provider returned error`,
    with `metadata.provider_name`, `metadata.raw`, and for a shared-pool limit
    `limit_source: upstream_provider_shared_pool`. The status code alone (404,
    429) blames the user's key, but the host is what failed. `anyllm.upstream()`
    reads the host (`a2b733457`). The wording is being fixed (§5).
- **Thinking.** Hybrid models think by default through OpenRouter, and it's
  billed as output. Bristlenose now turns it off (§4.2).
- **Not captured:** the out-of-credit 402.

### 3.2 Mistral, native (`mistral:<model>`)

- **The free plan has no API quota.** A new Experiment account gets 429
  `Rate limit exceeded`, and only the header `x-ratelimit-limit-req-minute: 0`
  shows that it's permanent. A one-off €10 prepaid top-up turned it on.
  Experiment requests may also be used for training, so use public data only.
- **Limits are per model** in tokens per minute (API ▸ Limits), from 20K to 5M.
- **Error shapes:**
  - 401 `{"detail":"Invalid API Key"}`
  - 429 code `1300`
  - 403 `tier_not_allowed`, code `1910`
- **Billing.** The console reports by the requested alias
  (`mistral-large-latest`), not the snapshot it resolved to. The whole walk,
  72 requests, cost €0.13.
- **Structured output.** Large was clean. Small drops required fields
  (`start_timecode`, `topic_label`) on long outputs, and in the live check it
  dropped `screen_label` in quote clustering one time in four.
- **Thinking.** any-llm maps every `reasoning_effort` except `auto`/`none` to
  `"high"`. **Never send `"low"`, because it switches thinking on.**

### 3.3 DeepSeek, native (`deepseek:<model>`)

- **Model ids.** `deepseek-chat` and `deepseek-reasoner` were retired on
  24 Jul 2026. The current ids are `deepseek-flash` (V4.1 Flash) and
  `deepseek-v4-pro`, and `deepseek-v4-flash` still works as an alias. The
  docs carried `deepseek-chat` until `3ad7a5435`.
- **Billing.**
  - The minimum top-up was $2, one-off, with no granted balance. Unspent
    top-up doesn't expire and can be refunded.
  - Off-peak prices are half of peak. Peak is 01:00–04:00 and 06:00–10:00
    UTC on weekdays.
  - Out of balance is a 402 `Insufficient Balance`.
- **JSON.** DeepSeek refuses `json_schema` with a 400 (`This response_format
  type is unavailable now`), so Bristlenose falls back to `json_object` as
  planned. The fallback is logged 3 to 4 times per run, not once: concurrent
  first calls (sessions, AutoCode batches) all reach the 400 before the
  per-client flag is set. That costs three free 400s and needs no fix.
- **Output cap.** With no `max_tokens` sent, DeepSeek stops at **8192**.
  That's not the 4096 of the old `deepseek-chat`, and not the 384K maximum
  in its docs. DeepSeek Flash over-extracts enough to reach it on a 25 KB
  transcript, so s09's split-and-retry recovered at depth 2. **This was the
  first real-provider proof of that path.**
  - A user with long interviews could set `BRISTLENOSE_LLM_MAX_TOKENS=32000`
    to skip the round-trips (not measured).
  - With a forced 2000 cap, the split ran to depth 3, a leaf still
    truncated, and the run was abandoned as `output_truncated`, as designed.
- **Thinking.** Natively, any-llm sends `thinking: disabled` for every
  non-legacy id. Through OpenRouter the same model thinks, which is why its
  OpenRouter row scores lower and runs longer.
- **Data.** DeepSeek is a Chinese provider with no UK/EU adequacy decision.
  The walk used public data only.

### 3.4 Local, through llama.cpp's OpenAI endpoint (free)

`llamacpp:<model>` with `LLAMACPP_API_BASE=http://localhost:11434/v1`,
pointed at Ollama, proved the real library end to end for nothing. A full
`analyze` of the three FOSSDA interviews gave 31 quotes, and serve's
Settings ▸ Pipeline and AutoCode both worked. For local models the native
`local` provider remains the supported path. This route was the free
real-library test.

## 4. Quirks that shape a run

### 4.1 One bad quote used to cost the whole session

Before `5939d6c89`, one quote missing one field failed the whole
`QuoteExtractionResult`. The session ended with no quotes, and the run still
said "Done with warnings · N quotes". The schema retry (`edbf1b469`)
recovered 0 of 1 sessions on Mistral Small, because a model that drops a
field on long output drops it again.

Salvage now keeps the quotes that validate and drops the bad one, with a
WARNING that names fields, not values. It needs at least one survivor, and it
covers quote extraction only: dropping a screen cluster would orphan its
quotes. Mistral Small hasn't been re-walked since.

### 4.2 Thinking models stall quote extraction

Hybrid models reached through OpenRouter (Qwen 3.8 Flash, DeepSeek V4 Flash,
Nemotron) think by default:
- **Qwen 3.8 Flash** wrote 20–37k output tokens per ~5k-token pass.
- **Every s09 pass** hit the 570 s deadline and split, and the halves were
  nearly as slow.
- **Result:** Qwen 16–40 minutes, Nemotron failing at 30.

`8b16e797f` sends `reasoning_effort="none"` on every call. A model that
can't turn thinking off (GPT-5 mini, Gemini 2.5 Pro: `Reasoning is mandatory
for this endpoint`) gets a resend without it, and the run remembers.

Qwen on FOSSDA then went from >38 minutes to **2m 56s** at 80% Jaccard. The
per-model measurements are in `design-any-llm.md` §5.3d.

### 4.3 What a run can't see

- **A call cancelled at the deadline** records no usage, but the host has
  probably billed what it generated.
- **The model catalogue rates a route, not a model.** Settings ▸ Pipeline
  shows `openrouter:anthropic/claude-sonnet-4.6` as "? untested", while
  native Sonnet 4.6 reads "● excellent".

### 4.4 A `.env` could silently outrank `use` and `configure`

The repo's own `.env` sets a provider, and it loads for an editable install
whatever the working directory. So after "any-llm is now your provider", one
walk's run went to Claude. Since `ac926c395`, `use` and `configure` name the
file that overrides them. A user with a provider line in a `.env` above
their working directory had the same problem. Walks in a dev checkout pass
`--llm any-llm`.

## 5. What the walks changed in Bristlenose

**Fixed**

| Commit | What |
|---|---|
| `b1c16d374` | A 401 no longer gets "credit balance" advice, and an HTML error page is no longer printed as the message |
| `3ad7a5435` | DeepSeek's documented model is `deepseek-flash` |
| `ac926c395` | `use`/`configure` name a `.env` that overrides them; `check-providers-live --stages` runs again |
| `edbf1b469`, `5a44506eb` | A reply that misses the schema is asked once more, with its own telemetry row |
| `a2b733457` | The host behind a gateway is read from its error; one key in two places isn't a shadow; the pipeline badge stays indented |
| `8b16e797f` | Thinking is turned off; a deadline pass isn't called a network failure; an unexplained give-up names the model and `bristlenose use` |
| `5939d6c89` | One incomplete quote no longer discards a session's quotes |
| `25b24d90d` | AutoCode progress writes land (every batch's write was being skipped) |
| `d8f30b46b` | The live-check fixture is tested against the real prompts and schemas |
| `0e3d4122f` | A failed call's log line is one line of field paths and never quotes the reply |

**In progress:** naming the host, not the key, for a failure behind
OpenRouter, and retrying a shared-pool 429 for longer than 44 seconds.

**Open**

- **Failure category.** No category says "this model can't do this job". The
  run is abandoned as `unknown`. A new category means changes in Swift and in
  21 locales, so it waits for any-llm on the Mac.
- **Hidden remedy.** Every per-session message is overwritten with "All quote
  extraction calls failed.", so the truncation remedy never reaches the CLI.
- **Terminal noise.** Stage WARNINGs (`quote_extraction_pass_deadline`,
  `split_fallback_halves`) print as raw log lines between the checkmarks.
- **AutoCode.** It must propose one tag per quote, so a well-calibrated model
  files placeholders. A "no tag applies" answer would be more honest and
  cheaper to review.
- **Mistral's zero quota.** It's worded as a transient rate limit, and
  `configure` says "Not valid" for a 429.
- **Not yet measured:**
  - OpenRouter's 402
  - Mistral Small after salvage
  - Nemotron and DeepSeek V4 Flash (OpenRouter) after thinking-off
  - Mistral Large through OpenRouter on FOSSDA

## 6. For the docs

- **The examples to give:**
  - `mistral:mistral-large-latest` (not Small)
  - `deepseek:deepseek-flash` or `deepseek:deepseek-v4-pro`
  - an `openrouter:` model with `structured_outputs` in its
    `supported_parameters`
- **Free tiers on Mistral and OpenRouter are not a way in.** Mistral's has no
  API quota, and OpenRouter's free hosts fail in ways that look like the
  user's fault.
- **Public data only** on any free tier, and on DeepSeek.
- **For long interviews on DeepSeek,** set `BRISTLENOSE_LLM_MAX_TOKENS`.
