# Scale, tokens, and LLM limits

What we know about how dataset size translates into LLM tokens, where the ceilings are, and what's observed across trial studies. Written 17 Apr 2026 after FOSSDA hit `max_tokens=32768` during quote extraction.

## The issue

`BRISTLENOSE_LLM_MAX_TOKENS` defaults to 32,768 ([bristlenose/config.py:56](bristlenose/config.py)). The error message already suggests raising it to 65,536 ([bristlenose/llm/client.py:276](bristlenose/llm/client.py)) — so we know 32K is tight, we just haven't changed the default. The truncation detector is wired for all four cloud providers and Ollama ([client.py:273, 342, 415, 486, 570](bristlenose/llm/client.py)).

It's a recurring issue. Long oral-history sessions and any dataset that produces many quotes per session push output past 32K.

## Data from trial studies

Measured from `extracted_quotes.json` + `session_segments.json` in each `trial-runs/*/bristlenose-output/.bristlenose/intermediate/` tree. Chars→tokens estimate uses the standard **~4 chars/token** rule of thumb.

| Study | Sessions | Total audio | Total transcript (chars) | Quotes | Median quote len | p95 quote len | Largest transcript (tokens) | Truncation? |
|-------|----------|-------------|--------------------------|--------|------------------|---------------|-----------------------------|-------------|
| fossda-opensource | 10 | 490 min | 350,736 | 238 (9/10 sessions) | 559 ch (~140 tok) | 1,512 ch (~378 tok) | s3: ~18,500 | **yes — s5 dropped entirely** |
| Fishkeeping | 20 | — | 394,390 | 0 (stage not run / empty) | — | — | s13: ~6,345 | n/a |
| Rockclimbing | 7 | — | 30,487 | 71 | 352 ch (~88 tok) | 442 ch (~111 tok) | s7: ~1,368 | no |
| project-ikea | 4 | — | 9,099 | 67 | 86 ch (~22 tok) | 203 ch (~51 tok) | s1: ~845 | no |

**Dataset shapes differ enormously:**

- **FOSSDA** is oral-history-length monologues with ~140-token median quotes. One hour of interview = thousands of lines of transcript and many long quotes.
- **Rockclimbing** is moderated-interview-length (~350-char quotes) with short sessions.
- **project-ikea** is short task-based sessions with ~86-char quotes — the most "atomic".
- **Fishkeeping** has 20 substantial sessions but no quotes in the saved output — likely a stale or empty run, not a truncation.

## Why FOSSDA's s5 hit the ceiling

s5 had the most transcript *segments* (1,712) — fast-talking, many sentence breaks — but only 61K chars in. Input fit easily inside the 200K context. The problem was output:

- Every extracted quote carries ~10 metadata fields (`session_id`, `participant_id`, `start_timecode`, `end_timecode`, `text`, `verbatim_excerpt`, `topic_label`, `quote_type`, `researcher_context`, `sentiment`, `intensity`, `segment_index`). Call that ~100 output tokens of metadata per quote.
- Plus quote text: FOSSDA's median is ~140 tokens, p95 ~378.
- So each quote costs ~240–500 output tokens.
- At 100 quotes × 300 tokens ≈ 30K — right at the default ceiling.

s5 would have extracted ~50 quotes (extrapolating from its density); the truncation happened before the JSON closed, so nothing was saved for that session.

## Provider limits (Apr 2026)

Shipped models are defined in [bristlenose/llm/pricing.py](bristlenose/llm/pricing.py). Each provider's max output ceiling:

| Provider | Model (as shipped) | Context | Max output | Bristlenose default |
|----------|--------------------|---------|------------|---------------------|
| Anthropic (Claude) | `claude-sonnet-4-20250514` | 200K | 64K | 32K |
| Anthropic (Claude) | `claude-haiku-3-5-20241022` | 200K | 8K | 32K (too high — will fail) |
| OpenAI (ChatGPT) | `gpt-4o` | 128K | 16K | 32K (too high — will fail) |
| OpenAI (ChatGPT) | `gpt-4o-mini` | 128K | 16K | 32K (too high — will fail) |
| Google (Gemini) | `gemini-2.5-pro` | ~1M | 64K | 32K |
| Google (Gemini) | `gemini-2.5-flash` | ~1M | 64K | 32K |
| Azure OpenAI | follows OpenAI model caps | 128K | 16K | 32K (too high — will fail) |
| Ollama (local) | model-dependent (typ. 4K–128K) | varies | varies | 32K (often too high) |

Treat these as "at the time of writing" — the provider pricing URLs in [pricing.py:26](bristlenose/llm/pricing.py) are the source of truth. Models drift.

**Sonnet 4 is the only shipped model where raising `BRISTLENOSE_LLM_MAX_TOKENS` to 65,536 (the suggested fix) is actually supported.** For Haiku 3.5, GPT-4o, and GPT-4o-mini, the current 32K default is already *above* the provider's max-output ceiling — requests at those settings would fail at the API layer, not in our truncation detector. We don't currently clamp `llm_max_tokens` per-model.

## Assumptions we're making

1. **4 chars/token** — good enough for English. Worse for code/JSON (closer to 3 chars/token), so our output estimates undershoot slightly.
2. **Input tokens = transcript chars / 4 + system prompt overhead.** Quote extraction prompt is ~2K tokens ([quote-extraction.md](bristlenose/llm/prompts/quote-extraction.md)).
3. **Output tokens scale super-linearly with session length**, because longer sessions tend to produce both more quotes *and* longer quotes (oral history vs task-based).
4. **Each quote structurally costs ~100 output tokens of metadata** on top of quote text, because every field is serialised in the JSON response.
5. **Per-participant chaining (S2)** will keep per-call input size roughly constant (one participant's transcript + one quote pass) but doesn't change the per-call output size much — so it doesn't solve the truncation risk on its own.

## What drives output tokens

Ordered roughly by observed effect:

1. **Session length** — more material means more extractable quotes. Linear.
2. **Speaking style** — monologue/oral-history produces longer quotes than task/think-aloud. See FOSSDA (~140 tok median) vs project-ikea (~22 tok median) — **6× difference**.
3. **Quote atomicity of the prompt** — the current prompt says "typically 1-5 sentences" ([quote-extraction.md:36](bristlenose/llm/prompts/quote-extraction.md)), but oral-history monologues routinely produce 3,000-char quotes that are "one long paragraph" not "1-5 sentences". See [docs/design-quote-length.md](docs/design-quote-length.md) — this is already on the backlog.
4. **Metadata fields** — every additional field per quote is ~N output tokens × quote count.
5. **Response format** — JSON with indentation bloats; provider streams strip whitespace but the token count is per-token-ID, not per-char.

## What doesn't break (yet)

- **Input context.** Even FOSSDA's biggest session is 18K tokens — nowhere near 200K. We're a long way from the input ceiling on any shipped model.
- **Audio/video duration per se.** What matters is how many words got transcribed, not how many minutes of audio. Heavy silence or noise → fewer tokens.
- **Topic segmentation stage.** Emits boundaries only, not quote-like bodies. Output is small.

## Recommended actions (not in this doc's scope)

- Raise default `llm_max_tokens` from 32K → 64K. Safe for Sonnet 4 and Gemini 2.5; needs a per-model clamp for Haiku 3.5 / GPT-4o / GPT-4o-mini.
- Treat quote atomicity as the real fix — if quotes stay "1-5 sentences" as the prompt says, the 32K ceiling is rarely hit even on oral-history data. See [docs/design-quote-length.md](docs/design-quote-length.md).
- Per-model clamp: when `settings.llm_max_tokens > provider_cap(model)`, clamp silently or warn at startup. Today the failure mode is a mid-run API error.
- Drop a few metadata fields (or flatten them) if we need to shave output size fast.

## Reference: files

- [bristlenose/config.py:56](bristlenose/config.py) — default `llm_max_tokens = 32768`
- [bristlenose/llm/client.py](bristlenose/llm/client.py) — truncation detection (all five providers)
- [bristlenose/llm/pricing.py](bristlenose/llm/pricing.py) — shipped model IDs + pricing URLs
- [bristlenose/llm/prompts/quote-extraction.md](bristlenose/llm/prompts/quote-extraction.md) — the prompt that controls quote length
- [bristlenose/llm/CLAUDE.md](bristlenose/llm/CLAUDE.md) — provider gotchas, incl. SDK streaming heuristic above ~21K
- [docs/design-quote-length.md](docs/design-quote-length.md) — separate investigation of quote atomicity
- [trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md](trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md) — the baseline that surfaced this
