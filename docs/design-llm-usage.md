---
status: layers-1-2-and-api-built
last-trued: 2026-11-17
---

# LLM usage: counting, money and where to show it

## The ask

Owner, 17 Nov 2026: show what an analysis is spending, small, tasteful and
meaningful. The CLI already prints a line at the end of a run; the Mac app shows
nothing. The owner then split it into **three separate problems**, to be solved
in order and never mixed:

1. **Plumbing and counting.** Tokens a study has used, every job, for the life
   of the study. Facts the provider returned, no money.
2. **Tokens to money, in the researcher's currency.** Price tables, how stale a
   price may be, exchange rates, and what "estimate" means.
3. **The UX of where to show it.** Candidates so far: a per-study **Get Info**
   (project context menu, ⌘I) and a **Settings ▸ Usage** pane (by month and
   provider, across studies).

Layers 1 and 2, the API and the live updates are built (below). Layer 3, where
any of it is shown, is the owner's and is not started. Decisions still owed are
listed at the end.

## Layer 1 — counting (built 17 Nov 2026)

### What was wrong before

There was no lifetime figure for a study anywhere, and each candidate was wrong
differently:

| Source | Failed or stopped runs | Serve-side calls (AutoCode, chat, …) | Survives Re-analyse |
|---|---|---|---|
| The run's terminus event (`cost_usd_estimate`, tokens) | ✗ set by `handle.set_cost` only for a run that returned (`cli.py`) | ✗ | ✗ |
| `manifest.total_cost_usd` | ✗ **written by nothing**; `bristlenose status`'s "Cost so far" has never printed | ✗ | ✗ |
| `llm-calls.jsonl` (per call) | ✓ | partly (below) | ✗, and capped at 1000 rows |

And two serve-time surfaces, **the chat lens and the codebook builder**, bound
only `telemetry.stage(...)` and never a run context, so every call they made
was missing from `llm-calls.jsonl`. This is the failure §"As built" of
`design-llm-call-telemetry.md` describes for elaboration, recurring twice more.

### What was built

**`<output>/.bristlenose/usage.jsonl`**, one row per job, provider and model,
appended when the job ends (`bristlenose/llm/usage.py`). Format pinned by
`tests/fixtures/usage-ledger-contract.json`, which a Swift reader must also
pass when layer 3 reads the file.

- **Counted where every call already arrives.** `telemetry.record_call` (all six
  providers reach it through `LLMClient._record_call`) adds the call to an
  in-memory tally keyed by run id. The per-call log is never read back, so its
  cap cannot shrink a total.
- **Counted with telemetry off.** The tally is fed before the
  `BRISTLENOSE_LLM_TELEMETRY` kill switch and before the `stage(...)` check. The
  per-call log can re-identify participants; a usage row carries no session id,
  prompt or timing, and a forgotten `stage(...)` wrapper must not make a
  researcher's tokens vanish.
- **Each job writes its row on the way out, however it ends:**

  | Job | Where its row is written | `kind` |
  |---|---|---|
  | Pipeline run | `run_lifecycle`'s `finally`, once for every exit path | `run` / `analyze` / `transcribe-only` |
  | AutoCode pass | `run_autocode_job`'s `finally` | `autocode` |
  | Signals elaboration | `telemetry.serve_run_context` on exit | `elaboration` |
  | Chat-lens question (answer + support check) | the route, via `serve_run_context` | `chat_lens` |
  | Codebook builder call | the route, via `serve_run_context` | `codebook_builder` |

  `serve_run_context` now takes the job's `kind` and is the one way a serve-time
  LLM caller binds itself; a new one uses it.
- **Crosses a Re-analyse.** `run --clean` sets the output aside; the ledger is
  read before the stash and written into the new output, beside the study id
  and start times (`cli.py`). A Re-analyse that fails puts the old report back,
  and `usage.jsonl` is in `output_backup._APPEND_ONLY`, so the failed run's rows
  come back with it.
- **The reader removes repeats.** That append repeats the carried rows, so
  `read_rows` drops a row whose `row_id` it has already seen. Every row is
  written with a fresh random id, so only a byte-for-byte repeat matches: a
  timestamp key was tried first and dropped a late call flushed in the same
  millisecond as its job (caught by its test, 17 Nov 2026).
- **Keyed on the requested model**, the one the researcher chose. A response's
  snapshot name varies within a run, and a failed call has none.

Row fields: `schema_version, row_id, ts, run_id, kind, provider, model, calls,
input_tokens, output_tokens, cache_read_input_tokens,
cache_creation_input_tokens, calls_without_usage`.

### One meaning across providers (built 17 Nov 2026)

The providers do not agree on what their token counts mean, and a price is
only right if the counts mean one thing. The contract's `field_meanings` is
that one thing:

| | Anthropic | OpenAI, Azure | Gemini |
|---|---|---|---|
| Cached input | reported beside `input_tokens` | **inside** `prompt_tokens` (`prompt_tokens_details.cached_tokens`) | **inside** `prompt_token_count` (`cached_content_token_count`) |
| Thinking / reasoning | n/a | inside `completion_tokens` | **apart**, in `thoughts_token_count` |

- **Gemini thinking was not counted at all, anywhere.** Direct Gemini calls do
  not switch thinking off, Gemini 2.5 and 3.x Flash think by default, thinking
  is billed as output, and the client read only `candidates_token_count`. Fixed
  at the source (`client.py`, `_analyze_google`): output is candidates plus
  thoughts, so the CLI's end-of-run line, the terminus tokens, the per-call log
  and the ledger all now agree with the bill. Gemini figures go up; they were
  short. Switching Gemini thinking off is a different, behavioural decision
  and was not made.
- **The cached share moves only in the ledger.** The client passes it to
  `record_call` as `cached_input_tokens_included`, and `usage.note_call` moves
  it from `input_tokens` to `cache_read_input_tokens`. The per-call log keeps
  each provider's own meaning, because the forecast's cohort medians are built
  on it.
- any-llm's counts stay as reported: their meaning depends on the inner
  provider, and any-llm is never priced.

### Known limits

- A process killed outright (SIGKILL, power cut, the hosted backstop's hard
  exit) never reaches its flush. Its tokens are uncounted; nothing is ever
  counted twice.
- A call whose provider reported no usage (some Ollama builds, a call cut off
  before its reply) is counted in `calls` and `calls_without_usage`, with no
  tokens. A surface should say so rather than show a falsely low total.
- Tiered prices (Gemini Pro above 200k prompt tokens, long-context premiums)
  cannot be recovered from a per-job row. None of the models priced today is
  billed above the tier in Bristlenose's use; a tiered model needs per-call
  pricing, from `llm-calls.jsonl`.
- The dev-only codebook lab (`routes/dev.py`) is not counted: it is not a
  project.
- Studies used before 17 Nov 2026 start from zero. Nothing reconstructs their
  past from `llm-calls.jsonl`, which is capped and missed two surfaces.

### Verification

`tests/test_usage_ledger.py` (contract, counting, provider meanings through the
real client paths, in-flight and late calls, progress lines), plus a pin beside
each surface's own fixtures: `test_chat_lens.py`, `test_codebook_builder.py`,
`test_autocode_engine.py`, and `test_cli_output_backup_wiring.py` for a
successful and a failed Re-analyse. Each fix was mutated alone and a test went
red for each.

## Layer 2 — tokens to money (built 17 Nov 2026)

`bristlenose/llm/money.py`. Nothing in it reads a price from the network or a
time from the clock.

- **Prices: `bristlenose/llm/pricing.json`**, bundled, USD per million tokens,
  a dated list per model (`from`), each with optional `cache_read` and
  `cache_write` rates. The file name is the one
  `design-llm-pricing-fetch.md` planned for its alpha step; that step is done,
  and its fetch is not.
- **A row is priced at the price in force on its own day** (`ts`, UTC). Rows
  hold tokens, never money, so a release with a newer table re-prices every
  study, and a price change never rewrites spend at the old price. The
  earliest entry also covers earlier days. An add-only rule: a price change is
  a new dated entry, never an edit.
- **No wall clock.** `pricing.PRICING`, `estimate_cost`, the forecast and the
  telemetry stamps read each model's price on the table's own version date, so
  a serve running across a price change and a test agree until a release
  changes the file. `PRICING` was checked identical to the old literal dict.
- **Exact lookup.** A model is priced only by its exact id under its own
  provider. No cohort-family fallback: Gemini 3.5 Flash, 3.8 Flash and 3.5
  Flash Lite share a family and not a price. Azure deployment names and any-llm
  routes are `unpriced`; `local` is `free`.
- **Cache rates where known.** Anthropic's are its published multipliers
  (reads 0.1×, 5-minute writes 1.25×), gpt-4o's and gpt-4o-mini's are on
  record; the rest are null. Cached tokens with no rate are priced at the full
  input rate and the price says `cache_priced_at_input_rate`: an upper bound,
  never a guess.
- **The 2027 Gemini rates are not entered.** The 3.x rows are promotional
  through 31 Dec 2026 and "roughly double" after, with only one model's new
  price published. A guessed dated entry would be a made-up figure; the
  table needs a real one before 1 Jan 2027.
- **Currency: `bristlenose/llm/fx-rates.json`**, ECB euro reference rates
  rebased to USD by `scripts/update-fx-rates.py` (30 currencies, first run
  17 Nov 2026). Bundled, so no installed copy makes a request for it; every
  converted figure carries `as_of`. The caller names the currency; nothing
  guesses one from a locale. An unknown currency answers in USD and says
  which was asked for.
- **Shipped everywhere the code ships.** Both files are tracked package data
  (the wheel), in the sidecar spec's `datas`, and in the sidecar source
  fingerprint (each proved to move it).

## The API (built 17 Nov 2026)

`GET /api/projects/{project_id}/usage?currency=GBP` (`server/routes/usage.py`),
bearer-only, `SERVER_ONLY` in the export (the operator's information, never in a
deliverable). Shape pinned by the contract's `api_fields`:

- `rows`: every ledger row, priced at its day, with `price.status`,
  `cost_usd`, `cost` (in `currency`) and `cache_priced_at_input_rate`.
- `totals`: per provider and model, with `jobs`.
- `in_flight`: jobs not yet in the ledger (next section).
- `currency`, `conversion` (rate, `as_of`, source), `currency_unavailable`,
  `price_table_version`.

No rounding server-side: display is layer 3's.

## Live updates across the seams (built 17 Nov 2026)

Use is recorded at three speeds in three places, and the API reads all three on
every request:

| Where the job runs | How its use is seen before it ends | When it lands in the ledger |
|---|---|---|
| This serve (AutoCode, elaboration, chat, codebook builder) | `usage.peek(run_dir)`: the in-memory tally of jobs that called `usage.begin` | its `flush` at the end |
| A pipeline run, in its own process (CLI or the Mac's sidecar) | its newest `run_progress` line, which now carries `usage_calls`, `usage_input_tokens`, `usage_output_tokens`, `usage_cache_*`, summed over its models (so no price) | `run_lifecycle`'s `finally` |
| Any process, finished | the ledger file | — |

- **Distinct names on purpose.** A terminus's `input_tokens`/`output_tokens`
  are the provider's own counts; the progress line's `usage_*` use the
  ledger's meanings. The same key with two meanings on one Swift struct would
  have made the last progress line and the terminus disagree.
- **Swift sees them without a change.** `JSONDecoder` ignores unknown keys, so
  today's app is unaffected; a Swift consumer decodes the `usage_*` keys named
  in the contract's `progress_fields`. No Swift code was written: it cannot be
  compiled in the Linux container this was built in, and uncompiled code is not
  a gate.
- **A poller is cheap.** The ETag is a hash of the body; `If-None-Match`
  answers 304. A new row, a running job's next call, or a progress line each
  change it (tested).
- **A late call is not lost.** A call that finishes after its job flushed (a
  cancelled task) is written as a row of its own; a new job reusing a finished
  one's id (AutoCode and elaboration mint ids to the second) is not mistaken
  for one.
- **Prices update live by construction**: costs are computed at read time, so
  a new table needs no migration.
- A pipeline run's progress lines arrive per stage and per session, so "live"
  is that coarse.

## Layer 3 — where to show it (owner's, not started)

Candidates the owner named, both reading the same API:

| | Get Info (per study, ⌘I) | Settings ▸ Usage (app-wide) |
|---|---|---|
| Answers | "What did this study use?" | "How much have I used this month?" |
| Groups by | the study, all jobs (`totals`) | month and provider, across sidebar studies (bucket `rows` by `ts`, UTC) |
| Cost to build | a Get Info panel (none exists; ⌘I is free) | a seventh Settings pane |

Per `desktop/CLAUDE.md`, a `what-would-gruber-say` pass comes before any
mockup, and the R114 UX gate wants a mockup and owner approval before any UX is
built. A percentage of a plan's allowance cannot be computed: providers do not
tell an API key its limit or balance. Their own usage pages can, and a surface
can link there (`pricing.PRICING_URLS` holds the price pages, not usage pages).

## Decisions owed to the owner

1. **Price freshness.** Bundled prices go stale between releases. The fetch in
   `design-llm-pricing-fetch.md` would add a request to `bristlenose.app`, a
   change to what leaves the machine (SECURITY.md, the website's privacy pages,
   App Review notes).
2. **Exchange-rate freshness.** `scripts/update-fx-rates.py` is run by hand. Wire
   it into the release (`release.sh`, after reading the four release docs), or
   keep it manual and let `as_of` show its age.
3. **Gemini 3.x prices from 1 Jan 2027**, once published.
4. **Gemini thinking.** Now counted; whether to switch it off (cost and time
   against quality) is a separate call.
5. **The dead `manifest.total_cost_usd`** and `bristlenose status`'s "Cost so
   far" line, which reads it and has never printed. Both are CLI text; the
   ledger now has the true figure.
6. **The CLI's end-of-run `~$` line** still prices only a run that returned, at
   the provider-native counts. It is CLI text, left as it is.
