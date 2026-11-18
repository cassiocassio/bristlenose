---
status: v1-built
last-trued: 2026-11-18
---

# Analysis usage: a sense of scale, not a budget

## The ask

Owner, 17–18 Nov 2026: show what an analysis spends, small, tasteful and
meaningful. **The objective is a sense of the scale of a typical run.** Not
limits, not a running total, not cost control: researchers manage, cap and
reconcile spend in their provider's own console, which knows their discounts,
credits and real bill. Bristlenose cannot (the API returns token counts, never
a price), so it does not try.

## v1: one line, for five seconds, at the end of a successful run

Settings ▸ Appearance ▸ **Show analysis usage**: Tokens (default) /
Estimated cost / Off.

When a run succeeds, the project's row in the sidebar says, for five seconds:

- **Tokens**: "Used 412K tokens" (input plus output, compact).
- **Estimated cost**: "Estimated cost $1.24", in US dollars, because every
  provider bills API use in dollars; the Mac's formatter writes "US$" where a
  bare "$" would read as another dollar. "Estimated cost under $0.01" for a tiny
  run.

then the silence a successful run has always ended in.

Silence, whatever the setting, for: Off; a local (Ollama) run, which costs
nothing and whose usage some builds do not report; a run served entirely from
cache (no LLM call); and any failure, stop, partial run, warning, info or error,
which keep their own lines (a failure usually ends early, so little was spent).
Estimated cost with no price on record (an Azure deployment, an any-llm route)
falls back to the token line, which is still true.

### How it works

- **Data: none new.** The run's `run_completed` line already carries its token
  totals and its list-price estimate (`input_tokens`, `output_tokens`,
  `cost_usd_estimate`, from `bristlenose/cost.py`), and is written only for a
  run that returned: exactly the success this line is for. Swift decodes
  `cost_usd_estimate` beside the token counts it already read
  (`EventLogReader.Event`). Pinned across the two languages by
  `tests/test_swift_python_contract.py::TestRunUsageTerminusContract`.
- **Decision: `RunUsageLine.resolve`** (`RunUsageLine.swift`), pure: terminus,
  prior run id, provider, preference → a line or nil.
- **Timing: `PipelineRunner.showRunUsage`**, called beside the credit check on
  every witnessed success (spawned, attached, and a slow end re-read), publishes
  `runUsage[projectID]` and clears it after `RunUsageLine.shownFor` (5 s), with
  a token so an earlier run's timer cannot clear a later one's line. The same
  shape as the "Adding N interviews…" acknowledgement.
- **Placement: `ProjectSubtitle.resolveIdle`.** `.runUsage` takes only a moment
  with no news of its own: any delta (missing files, unanalysed files, a forked
  database) keeps its line. It sits above "Picking up Signals…" and screen
  reading, which start as a run ends and can last minutes to hours, so it is
  not lost behind them; they come back when it clears. No glyph, no door, no
  ring, no shimmer.
- **Strings:** `desktop.chrome.runUsageTokens` / `runUsageCost` /
  `runUsageCostUnderCent` and `settings.appearance.usage*`, in all 21 locales;
  plain strings, not plurals (the count is always large and compact), with a
  label form ("Tokens used: 412K") where a language would inflect the noun.
  Non-English values drafted by Claude: owed a native review.

### Counting fixes that came with it

Both make the figure the line shows, and the CLI's end-of-run line, true:

- **Gemini thinking is counted.** Direct Gemini calls do not switch thinking
  off, Gemini 2.5 and 3.x Flash think by default, thinking is billed as output,
  and the client read only `candidates_token_count`, which leaves it out.
  Output is now candidates plus `thoughts_token_count` (`client.py`,
  `_analyze_google`), as OpenAI's `completion_tokens` already included
  reasoning. Gemini figures go up; they were short. Switching Gemini thinking
  off is a separate, behavioural decision, not made.
- **Three serve-time callers recorded nothing.** The chat lens, the codebook
  builder and AutoCode's re-apply (after every run, and each catch-up) bound
  only `telemetry.stage(...)`, so none of their calls reached
  `llm-calls.jsonl`. Each is now bound as a run
  (`docs/design-llm-call-telemetry.md` §"As built").

### Known limits

- The cost is the run's tokens at the provider's **list price** from the
  bundled table (`bristlenose/llm/pricing.py`), as stale as the release. It
  prices cached input at the full input rate. It is an estimate of scale, not
  the bill.
- Five seconds, whether or not anyone is looking. After a long run the
  researcher may have walked away; holding the line until the window is in
  front was discussed and left for later (owner, 18 Nov 2026).
- No VoiceOver announcement: the line is voiced only if the row is read while
  it shows.

## Built and removed (17 Nov 2026), on record if wanted

A first pass built more, before the objective was stated: a per-study token
ledger (`.bristlenose/usage.jsonl`) carried across Re-analyse, a dated price
table with exchange rates (ECB, bundled), `GET /api/projects/{id}/usage` with
live in-flight counts, and `usage_*` fields on progress lines. It was reviewed
(Fable, code review, silent-failure hunt) and fixed, then removed as complexity
v1 does not need. It is in the history of branch `claude/eager-dijkstra-jl95bx`:
commits `274da70`, `8e7a47c`, `c832861`. What it taught, kept here:

- Providers disagree on what their counts mean: Anthropic reports cache reads
  and writes beside `input_tokens`; OpenAI, Azure and Gemini count cached input
  inside their prompt count (`prompt_tokens_details.cached_tokens`,
  `cached_content_token_count`). A precise price needs them normalised.
- A per-study total kept in the output folder resets on Re-analyse (the folder
  is set aside), and a naive append on restore doubles it.
- Prices change and promotions end (Gemini 3.x rates are promotional through
  31 Dec 2026); a price table without dates prices January at December's rate.
- Bundled exchange rates are as stale as the release; a fetched price table is
  an egress decision (`docs/design-llm-pricing-fetch.md`).
