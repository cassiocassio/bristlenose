---
status: layer-1-built
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

Layer 1 is built (below). Layers 2 and 3 are open and wait on owner decisions.

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
  `read_rows` keeps the first row per (run id, provider, model, ts). The
  timestamp is in the key because AutoCode and elaboration mint run ids to the
  second: two such jobs flush at different milliseconds and both count.
- **Keyed on the requested model**, the one the researcher chose. A response's
  snapshot name varies within a run, and a failed call has none.

Row fields: `schema_version, ts, run_id, kind, provider, model, calls,
input_tokens, output_tokens, cache_read_input_tokens,
cache_creation_input_tokens, calls_without_usage`.

### Known limits

- A process killed outright (SIGKILL, power cut, the hosted backstop's hard
  exit) never reaches its flush. Its tokens are uncounted; nothing is ever
  counted twice.
- A call whose provider reported no usage (some Ollama builds) is counted in
  `calls` and `calls_without_usage`, with no tokens. A surface should say so
  rather than show a falsely low total.
- The dev-only codebook lab (`routes/dev.py`) is not counted: it is not a
  project.
- Studies used before 17 Nov 2026 start from zero. Nothing reconstructs their
  past from `llm-calls.jsonl`, which is capped and missed two surfaces.

### Verification

`tests/test_usage_ledger.py` (contract, counting, pipeline and serve-context
callers), plus a pin beside each surface's own fixtures: `test_chat_lens.py`,
`test_codebook_builder.py`, `test_autocode_engine.py`, and
`test_cli_output_backup_wiring.py` for a successful and a failed Re-analyse.
Each of the ten fixes was mutated alone and a test went red for each (17 Nov
2026).

## Layer 2 — tokens to money (open)

Owner's notes, 17 Nov 2026: currency and price are always tricky; a researcher
on a plan with an allowance expects a percentage; tokens in and out may be the
simpler thing to show.

What is known:

- Bristlenose uses an **API key**, and providers tell us nothing about that
  key's limit or remaining credit, so a percentage cannot be computed. The
  provider's own usage page can show it; a surface can link there.
- API use is billed separately from a consumer subscription (ChatGPT Plus,
  Claude Pro). Researchers can confuse the two.
- The price table (`llm/pricing.py`) is USD, per model, versioned
  (`PRICE_TABLE_VERSION`), and goes stale between releases
  (`design-llm-pricing-fetch.md`). Azure deployment names are not priceable.
- The ledger keeps the model and the date of every row, so layer 2 can price a
  row at the price in force when it was used, if it chooses to.

Left behind for layer 2 to settle: the dead `manifest.total_cost_usd` and the
`bristlenose status` "Cost so far" line that reads it, and the CLI's end-of-run
`~$` line (`cli.py`, `_print_pipeline_summary`), which prices only a run that
returned.

## Layer 3 — where to show it (open)

Candidates the owner named, both reading the same ledger:

| | Get Info (per study, ⌘I) | Settings ▸ Usage (app-wide) |
|---|---|---|
| Answers | "What did this study use?" | "How much have I used this month?" |
| Groups by | the study, all jobs | month and provider, across sidebar studies |
| Cost to build | a Get Info panel (none exists; ⌘I is free) | a seventh Settings pane |

Per `desktop/CLAUDE.md`, a `what-would-gruber-say` pass comes before any
mockup, and the R114 UX gate wants a mockup and owner approval before any UX is
built. Not decided.
