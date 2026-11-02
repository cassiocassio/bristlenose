# The shared progress layer: one set of events and rules, many pictures

Status: proposal, 30 Oct 2026, revised the same day after a stress test against ten families of job (section 4). Not built. Owner direction, from the progress audit: there is nothing special about "the run" as far as the researcher is concerned, the ring we built for the analysis is an accident of history, and any wait of more than a handful of seconds that stands between them and a result should show determinate progress wherever the computer can estimate anything, with an indeterminate indicator as the fallback and never a blank wait. And: do not re-invent what we already thought through, and when a progress display is wrong, improve the common rules, not the one process.

This document designs little that is new. It lifts what is specified and what is built for the run and for the Miro board into one shape that any job can call on. The first draft did that and then met the jobs: three of its rules (pad, hold-and-only-down, four observations) turned out to be wrong for most of them, and the vocabulary was missing events several jobs need. Section 4 is the evidence; section 3 is the design as revised by it. The audit that motivated this is in the private forward plan ("Progress is not special to the run").

## 1. Prior art in this repo (read these, do not re-derive them)

- `docs/design-llm-call-telemetry.md`, § Prior art, § Time display, § Post-run reconciliation, § The watchable countdown: the literature (Maister, Myers, Nielsen's 10-second rule, Harrison et al., Apple HIG, Fluent, the cone of uncertainty, tqdm and Databricks) and the display rules that follow. In short: pad time, show a point not a range, hold the number, coarse when history is thin, precision tightens as the remainder shrinks in fixed bands, the last minute rewards attention without a countdown gimmick. Its reconciliation section (compare each finished run's prediction with its actual, and calibrate) is the right home for the padding rule, as section 3.2 uses it.
- `docs/design-sidebar-activity-indicators.md`, § Determinate progress: the best-available ladder (1 history estimate with a ring and "~N min left", 2 a count with a ring, 3 a coarse stage ring, 4 a spinner), the two honesty rules (monotonic, asymptote), and "single source, two render sites".
- `docs/design-progress-ring-estimate.md`: stage-weighted slices and the overrun creep, built as R27 (`RunProgressMath`).
- `docs/design-shared-formats.md` and `tests/fixtures/shared-format-contract.json`: how one rendered value is kept identical in Python, TypeScript and Swift.
- `docs/design-pipeline-diagnostic-popover.md`: where each kind of progress may appear.
- The owner's standing rules: absence is information, not needy, expected outcomes get plain words, never a fake determinate bar (`OllamaDownloadPill.swift:102`), and the MAAS lesson that "we cannot predict, so we will not try" is a retreat.

## 2. What exists today

One idea, written four times. Every long job reports some subset of the same facts: a plan, advance, a wait that is not work, a phase change, an end.

| Job | Events | Estimator | Wire shape | Pictures |
|---|---|---|---|---|
| Analysis run | `run_progress` lines (`run_lifecycle.py`, `events.py:199`) | `TimingEstimator` (`timing.py`), Welford by stage, keyed by hardware, with a stage budget | the event; carries inputs, not a finished fraction | ring and subtitle, maths in Swift (`RunProgressMath`) |
| Miro board | `BoardProgress.plan / enter / counted / call_done / waiting_for / unplan` (`board_progress.py`) | per-kind Welford rates, history in `board-timing.json` | `BoardBuild` (`routes/miro.py:92-108`) | one linear bar, a count line, a time line |
| Screens reading | the job's counters (`screen_text_job.py`) | one live rate, recording seconds per wall second | `/screens/status` | "Screens · N of M" and a tooltip ETA; text in the SPA |
| Whisper and Ollama download | bytes | `DownloadRate` (`WhisperDownloadModel.swift:66`), sliding window with hysteresis | Swift model properties | linear bar in a pill and Settings |
| Copy into a project | bytes after each whole file | none | `InFlight.progress` in Swift | ring and "Copying · N%" |
| Cloud import | bytes per file; settled files per batch | none | `FetchProgress`, `BatchProgress` in Swift | per-row bar; "3 of 4" and a ring |
| AutoCode, catch-up, clip and screens export | counts, polled every 2 s | none | each route's own model | the SPA chip: shimmer text, an `n/total` string, no bar |

Shared today: `WelfordStat`, the four-observation threshold and the ten-second floor (imported by `board_progress.py` from `timing.py`); `RunProgressSubtitle.etaText`, the minute wording; and the prose rules.

### 2.1 Specified but not built

Checked by reading `timing.py` and `board_progress.py`:

- **Padding.** The telemetry doc says time forecasts pad to P75. The run's estimate is the Welford mean with a standard deviation printed as a band (`timing.py:322-328`); Miro's is the mean of the rates times the calls left. Neither pads.
- **Hold.** Both recompute from scratch on every read. Nothing remembers what was last shown.
- **Banded precision.** `etaText` gives whole minutes or "under a minute"; the telemetry doc's bands are implemented nowhere.
- **Hysteresis** exists only in Swift, only for downloads.

One consequence the first draft missed: Miro is the first job on the shared rules, but it proves only half of them. Its events, counted plan, earned rates, ten-second floor and waits-excluded rule work in production; its original "under a minute left" failure was an uncounted plan (groups not planned), not a rate problem. Pad, hold, band and hysteresis have no production evidence anywhere, which is why section 4 matters.

## 3. The design: four layers

```
job            estimator (Python)         display state              renderers
-----------    -----------------------    -----------------------    ----------------------
events    -->  weighted units, rates, -->  ProgressState         -->  ring, bar, pill,
(plan,         history, floor,             (fraction?, count,         subtitle, chip, CLI
advance,       asymmetric hysteresis,      weight, eta, rung,         line, indeterminate
wait, phase,   calibration, bands,         phase, waiting,            with elapsed, ...
restart, end)  waits kept out              cancellable, ...)
```

A new job implements layer 1 only. A job with nothing countable and no recurrence (section 3.5) does not use layers 2 and 3 at all.

### 3.1 Layer 1: events

The vocabulary `BoardProgress` already speaks, generalised by what the ten families needed:

- `plan(kind, total, weight_total=None)`: every unit of work, counted by kind before the first, so a total is counted and never guessed. `total=None` declares an **open** total (a paged listing): the display then has no count total and no fraction. A job may call `plan` again after a counted preparation phase (the screens board prepares stills, then plans its calls). `unplan(kind, n)` removes units that will not happen (a cache hit, a skipped file, a Stop); `replan(kind, delta)` adds units that arrive mid-job (AutoCode quotes that begin to count while it runs).
- `enter(phase, count_total=0, timed=True)`: what the phase's line counts. `timed=False` marks a phase whose time is not a rate (Miro's opening, a verify step); it is counted but contributes nothing to any rate.
- `unit_done(kind, n=1, weight=None, seconds=None, outcome="ok")`: `n` units finished (a Signals call finishes `n` cards), of total `weight` (media seconds, quotes in a batch, bytes). **`outcome` is `ok`, `failed`, `cancelled` or `skipped`, and only `ok` units are rate evidence.** A failed or cancelled unit still advances the count; it never enters a rate or a history.
- `waiting_for(reason, owner)`: time that is not work. `owner` is `rate_limit` (ours, bounded, may carry a back-off), `person` (sign-in, consent, a save panel; unbounded), `third_party` (a provider's clock, may never end: a transcript that does not arrive) or `deferred` (queued behind work we cannot see end: strips behind a run, OCR behind strips). Waits are kept out of every rate and none of the last three ever carries an estimate.
- `restart(done)`: the work began again from `done` (a download that cannot resume, a pass that was interrupted). It flushes the rate window and the shown figure; it is the one event after which the fraction may go backwards.
- `finish(partial=False, failed=0, parked=0)`, `fail`, `cancel_requested` (cancel pressed, a call still in hand: the display says stopping), `cancel`.
- `indeterminate(phase)` once, for a job with nothing to count (the HTML export's build), and `await_user(reason)` for a human step inside a job (the save panel); both are rung 4 and show no number.

Bytes are a second weight family on the same events (`weight` in bytes) for transfers and copies. A job with only a count (AutoCode, clip export) calls `plan("batch", n)` and `unit_done("batch")` and is done.

The run is not asked to change; its `run_progress` lines stay its wire format (section 5).

### 3.2 Layer 2: the estimator

One Python implementation, extracted from `BoardProgress`. It owns, in one place:

- **The ladder as its contract.** It returns the best rung the job has earned: rung 1 (history estimate: a fraction and minutes), rung 2 (a count: a fraction and no minutes), rung 4 (nothing measurable). Rung 3, the coarse stage ring, stays the run's. A job never claims a higher rung than it has earned. A job may declare **`estimable=False`** (heterogeneous unit cost with no predictor in its metadata: scene strips differ about 25 times between a call recording and a 4K screen capture); the layer then offers rung 2 at best and never `eta_seconds`.
- **Units and weights.** Cost follows weight, not the call. Signals cost 5.9 to 7.1 s a card but 20.9 to 42.5 s a call; clip burn-in follows clip length; OCR follows media seconds; the run's quotes stage follows transcript tokens (correlation 0.84 with input tokens) and not session count. So the unit is the thing the cost is proportional to, and where one call does several, `unit_done(n, weight)` credits them and the rate is per weight.
- **Concurrency.** The rate is completions per wall second (throughput), never summed per-unit elapsed. AutoCode's eight batches summed to 289 s of elapsed against 67 s of wall; the run's eight quote calls summed to 247 s against about 123 s. The layer measures wall time between completions, or takes the width and divides.
- **Earned rates.** A rate for a kind exists once at least four units have been measured, **or** the measured units cover at least a tenth of the planned weight (one OCR recording of a three-recording project is a rate; four of five Signals cards are not four calls). This threshold is a starting value to be tuned by replaying the recorded logs. The estimate is withheld until every kind still to come has a rate, except a kind that is under a tenth of the remaining weight borrows the job's own average (Miro's screens-board frames have no history and about eight calls). Under `ETA_FLOOR_SECONDS` (ten) it says nothing, which is also the rule that keeps a small export from showing any chrome.
- **Evidence.** Only `ok` units are measured, and history readers filter on `outcome == "ok"` as well. This is not hypothetical: in the recorded call logs 11 of the 19 Signals calls are `cancelled` (0.5 to 3.8 s each, from a page stream being dropped), and 8 of 56 AutoCode calls are `error` returns at 0.2 to 0.7 s; counted as work they would drag the AutoCode mean from 32 s to about 27 s and the Signals mean toward 2 s.
- **History.** Per kind, per cohort, merged with `_merge`, saved after the job (`BoardProgress.remember`), kept apart from `timing.json` for the reason `board_progress.py` records. `board-timing.json` already stores a `profiles` envelope with the Miro profile under one key, so another job type is another key with no format change. **The cohort key holds only the dimensions that change the rate**, and differs by job: transcription on hardware and backend alone, not on the language model (the run's key today includes it, which splits one transcription rate over several profiles: `timing.py` `build_hardware_key`); model calls on provider and model, and for Signals pooled across prompt versions per card, since a prompt edit invalidates a cache but not the per-card rate; OCR on engine and resolution class; Miro on none; transfers keep **no cross-job history** (bandwidth is the network, not the machine, and a transfer recurs once per machine). A job that recurs too rarely to ever earn history (boot, project open) is not in the estimator at all (3.5).
- **Calibration, and the pad.** After each job the estimator records the first estimate it showed against the actual time (the telemetry doc's post-run reconciliation). The padding is then the observed spread of that job-level ratio, per cohort, and not a per-unit statistic. The first draft padded as mean plus 0.67 standard deviations of unit time, and the data rule that out: the run's quotes stage has a coefficient of variation of 3.2 (a 150 s per-session pad over a 31 s median), Signals has eight ok observations, and the spread of a sum of N units is √N times a unit's, not a unit's. Until a cohort has enough finished jobs to calibrate, the central figure is a median (or trimmed mean) of per-weight rates, the pad is the largest figure seen, and with fewer than about ten observations the job stays on rung 2. Two measured facts set the expectation: the run's opening estimates over fourteen logged runs ran from 0.28 to 3.3 times the actual (median about 1.8), and only two landed within a quarter; and an estimate built from a per-call mean was about 30 s optimistic on the one real Miro build.
- **One revision rule, asymmetric hysteresis, and not hold-and-only-down.** The telemetry doc's rule (hold the number, revise only down and only a little) is right for a forecast made before work starts. In flight it is false whenever the truth rises, and the jobs show it does: bandwidth halves mid-download; a 54 s AutoCode call lands last; a screen capture follows call recordings; the run's own logs rise as often as they fall; Miro refuses frames for a late half-minute. Holding a figure the world has overtaken is a lie, and the worst misleading outcome the transfer and OCR reports named. So the rule is the one `DownloadRate` already ships: a figure moves **down** as soon as the estimate has left its band by one step, and moves **up** only when the estimate has left its band by two steps, held until then; the minute figure is rounded to the nearest minute, as `etaText` does today in Swift and TypeScript (the choice is pinned once in `shared-format-contract.json`, since Python's `round()` and the two disagree at 150 s); a figure that would flicker between adjacent bands keeps the shown one. A rise that passes is not announced with words (not needy) but is also never silent about being stale: a window with no progress for the window length (a **stall**) withholds the figure instead of showing the last one. `window_seconds` is the one parameter, short for volatile rates (bandwidth: the current eight) and long for model calls. The bands are the telemetry doc's, coarse far out and fine in the last half minute.
- **Waits and overrun.** Waits come out of the rates (`waiting_for`). When elapsed passes the shown figure and no estimate can be earned, the figure stops being offered, as the run does ("under a minute"); the wording is an open question (section 8).
- **Fraction.** Units or weight done over planned, clamped, never 1.0 before `finish`, and never 1.0 while `failed` or `parked` is above zero. It moves backwards only across `restart`. The count is the fraction unless the measured per-kind cost differs by more than about three times, when it is weighted by estimated time: Miro's measured kinds differ by 1.3 (bulk 0.22 s, group 0.29 s), so its plain count is right (the first draft's claim that 13 batches against 212 groups needed time-weighting was wrong; that board's failure was an uncounted plan); the run's stages differ by far more, which is why it keeps its slices.

It never holds a quote, a name or a title: counts, kinds, weights and seconds only, so history can be kept and logged. Per-recording or per-batch rows carry none of a participant's content.

### 3.3 Layer 3: the display state

One value, the thing every picture is drawn from: `BoardBuild` with the Miro-specific parts taken out and what the families asked for added.

| Field | Meaning |
|---|---|
| `phase` | what the line counts; a closed vocabulary per job type |
| `count_done`, `count_total` | the phase's line; `count_total` absent for an open total |
| `weight_done`, `weight_total`, `weight_unit` | media seconds, bytes or quotes, when the job has them |
| `fraction` | 0 to 1, or absent (indeterminate) |
| `eta_seconds` | already calibrated, hysteresis-held and banded, or absent until earned |
| `rung` | 1, 2 or 4, so a renderer never infers it |
| `waiting`, `waiting_owner` | a wait that is not work, and whose it is: `rate_limit`, `person`, `third_party`, `deferred` |
| `blocked_by` | a closed vocabulary (`scene_strips`, `analysis_run`, `cloud_fetch`, `person`) while deferred; no ETA while set |
| `stalled`, `restarted` | no progress for the window; the work began again |
| `stopping`, `partial`, `failed`, `parked` | cancel pressed with a call in hand; an end short of the plan; units that failed; units waiting on a third party and neither done nor failed |
| `stale` | a rate carried across a restart, or a figure from earlier history, not this job's |
| `estimable` | false for a job that can never earn minutes |
| `elapsed_seconds`, `ceiling_seconds` | rung 4 only: for the indeterminate-with-elapsed renderer, and to word a hang; never a fraction |
| `cancellable` | whether the job can be stopped, which decides whether a ring may offer a hover cancel |

`BoardBuild` keeps its current wire shape for the Mac sheet and the web panel; the new fields are additive. The run's `run_progress` event is untouched. No job fills `confidence` or a range, so neither is in the state. Several fields (`stopping`, `blocked_by`, `stale`, `restarted`, `parked`) are state, not pictures: a renderer that turns one into words or a mark is new UX and needs the owner's approval (and a string in 21 locales) before it is built.

The state is the one place the layer is tested across languages: `tests/fixtures/progress-state-contract.json`, in the pattern of `shared-format-contract.json`, holding cases of estimator input and expected state, asserted from pytest, vitest and Swift Testing.

### 3.4 Layer 4: renderers

The pictures stay different on purpose; none of them computes anything.

| Picture | Reads | Placement rule (existing) |
|---|---|---|
| Ring on a project row | `fraction`, `cancellable` | only for work the app can stop (`ProjectSubtitle.swift` on `readingScreens`) |
| Linear bar in a sheet or panel | `fraction`, absent means indeterminate, turning determinate in place | the Miro pattern |
| Title-bar pill | the same, plus `eta_seconds` | app-global operations only |
| Row subtitle | `count_done`, `count_total`, `eta_seconds`, `phase`, `waiting_owner` | a count where a count is the question ("3 of 4") |
| SPA chip | `count_done`, `count_total`, `fraction` | gains a `<progress>` |
| CLI line | `count_done`, `count_total`, `fraction` | `console.status` with the count; never a bar off a TTY |
| Indeterminate with an elapsed cue | `phase`, `elapsed_seconds`, `ceiling_seconds` | **proposed, not promised:** it is a new picture with no defined look, so it needs a mockup before any slice builds it; until then rung 4 uses the existing boot bar, scan spinner and shimmer |

Renderers choose by `rung`: rung 1 draws the fraction and the time; rung 2 the fraction and the count and no time; rung 4 the indeterminate form and no number. Where `waiting_owner` is `person` or `third_party` the renderer says what is being waited for and draws no bar and no figure. A job that sets `deferred` is never drawn as finished.

The estimate's rounding is one pure function (seconds to under-a-minute or whole minutes), pinned in `shared-format-contract.json` and used by Swift and TypeScript, which word it through their own i18n keys. The CLI keeps its English chrome and `count_noun` (`docs/design-i18n.md`); there is no Python `etaText`.

When nothing is shown: a wait under the ten-second floor, or under the renderer's appearance delay, gets no chrome. The delay is one renderer constant (precedents: 250 ms for the row-scan spinner, `ProjectRow.swift:197`; a 2 s acknowledgement floor, `PipelineRunner.swift:440-447`); the value is an open question.

### 3.5 What the layer does not take

A job with no countable unit and no recurrence does not enter the estimator, and the layer adds nothing there beyond the existing indeterminate pictures (the boot bar, the scan spinner, the shimmer): sidecar boot, project open, the startup-refusal probe, folder and manifest scans, fingerprinting, the session registry, and each CLI preflight row. Each is a single call bounded by a timeout that exists already (90 s, 30 s, 5 s), the first-ever launch (the slow one, over 15 s on a new Mac) is exactly the case history can never cover, and a plain indeterminate bar with an elapsed cue is already the honest picture. Such a job calls `indeterminate(phase)`, may pass a `ceiling_seconds`, and is rung 4 permanently. It must not call `plan` (no counted total). Two countable exceptions: ingest (N files) and the CLI preflight (eight rows) are counted, but both are mostly under the floor, so the CLI prints each row as it finishes and adds no bar.

## 4. Stress test: ten families against the first draft

Ten read-only audits, one per job family, each answering the same questionnaire (work shape, what drives the rate and how stable, initial-estimate quality, how the estimate should move, time that is not work, lifecycle, history, display, then a stress test of the draft). What they agreed on is the revision above; the per-family verdicts are here.

| Family | Rate behaviour | Total | Verdict on the first draft | What it forced |
|---|---|---|---|---|
| Analysis run | LLM stages volatile within a job; transcription stable per machine and backend (mlx 3.5 s per audio minute, n=33, M2 Max only) | session count known, stages cached or optional | pad wrong (cv 3.2); hold wrong (estimates rise as often as fall); history key fragmented by LLM choice | median-based central figure, asymmetric hysteresis, per-unit cohort keys; run exempt from the pad until calibrated |
| Miro board | provider latency across builds; kinds cost about the same (1.3 times) | counted, can only shrink | events, counted plan, earned rates, floor, waits all proven; pad and hold unproven | second `plan` after a prep phase, `enter(timed=False)`, `cancel_requested`; plain count over time-weighting |
| Signals build | per card 5.9 to 7.1 s, per call 20.9 to 42.5 s; chunks serial | cards known up front, cache hits shrink it | four observations counted in calls is wrong; cancelled rows poison history | unit = card, `n` and `weight` on `unit_done`, `outcome`, pooled across prompt versions |
| AutoCode and codebook jobs | provider latency and output length (r=0.87); concurrency 3 | batches known, quotes can grow mid-run | hold wrong (54 s calls land last); error rows poison the mean | throughput not summed elapsed, `replan`, `finish(partial, failed)`; the catch-up and re-apply tick no live count |
| OCR screens reading | per media second: 1.9 to 2.0 min an hour for 1080p calls, about 2.9 times that for 4K capture | recordings counted, seconds partly unknown | four observations wrong (3 to 10 recordings), per-unit equality wrong, restart discards the rate | weights, one-observation rule by weight, `stale`, `blocked_by` |
| Scene strips and frames | 25 times between recording classes (14 to 16 s an hour of call, 5 to 8 min an hour of screen capture) | counted, shrinks on cache hits | any estimate misleads; "deferred" read as "done" | `estimable=False`, `deferred`, done/total only |
| Transfers and copy | bandwidth: volatile within a job; no cross-job history | bytes known, sometimes late or absent | hold wrong; fraction monotone wrong on restart; P75 meaningless | asymmetric hysteresis (`DownloadRate`'s rule), `restart`, `stalled`, bytes windows not four observations |
| File exports | HTML build: nothing to count; clips: per clip length, burn-in follows duration | clips counted; HTML none | no unit in HTML; pad and hold wrong for burn-in | `indeterminate`, `await_user`, weights, a "too short to show" rule, re-raise pending for the second build |
| Startup, scan, CLI | one opaque call; first launch cannot have history | none | four observations never reached; nothing for pad or hold to act on | 3.5: not in the estimator; `elapsed_seconds` and `ceiling_seconds` |
| Importers and human waits | provider and human controlled; downloads aggregate three streams | listing open; batch counted | a transcript wait must never carry a figure; ring reaches 100% over failed rows | `waiting_for(owner)`, open `plan`, `parked`, `finish(partial)`, aggregate rate |

Measured facts the revision rests on, from the per-project `.bristlenose/llm-calls.jsonl` logs, `timing.json` and the experiment write-ups:

- Signals: eight ok calls, 19.2 to 42.5 s, median 25.4 s, and eleven cancelled calls; builds of about 54, 53 and 73 s matched their summed calls to within two seconds (the build overhead is negligible); per card 5.9 to 7.1 s across six calls. Stage `serve_signal_elaboration`. The short Signals rows are cancelled calls (a dropped page stream, a cancelled startup task), not fast builds, and must not be read as rates.
- AutoCode: 47 ok (median 31.4 s, p90 51.6 s, max 54.3 s), 8 error rows at 0.19 to 0.73 s that are failed batches and not cache hits, 1 cancelled. Elapsed correlates 0.87 with output tokens and 0.41 with input characters.
- The run: opening estimates 0.28 to 3.3 times the actual over fourteen runs; at speakers entry the prediction was 14 s against 40 s true, 16 against 37, 171 against 357 (too optimistic), while later runs overshoot; quotes stage cv 3.2 in the n=40 profile; one session cost 27 to 30 s on one project and 126 to 131 s on another.
- OCR: 1.9 min (p3), 2.0 min (Teams) and 5.5 min (4K at 120 fps, decode-bound) per hour of video; 0.122 to 0.268 s a frame (`experiments/screen-text/README.md:166-170`).
- Scene strips: FOSSDA calls 14 to 16 s an hour (the README says 8); IKEA screen captures 5 to 8 min an hour; the same recording differs about twice between passes.
- Transfers: hf_xet does not resume, and an outage of about 15 s restarts the download from zero (`whisper.py:22`, `810-815`).
- Miro: bulk 0.222 s (n=58), group 0.292 s (n=200); the first-build estimate from history was about 30 s optimistic.

## 5. The run

The run keeps its estimator and its events; moving it would touch `test_swift_python_contract.py`, the events format and the most sensitive progress code we have, for a gain it does not need. Two things happen instead, in this order:

1. **A precondition.** The live `timing.json` profile for `claude-sonnet-4-6` on the M2 Max holds 16,262 observations for render and 12,053 for speakers, with coefficients of variation up to 54. No one machine's runs can have produced that. Until the cause is found and the profile cleaned, any figure derived from it is not evidence. (Filed as a separate task.)
2. **Read-through.** A thin adapter turns the latest `run_progress` event into a `ProgressState` (rung from whether a stage budget is present, fraction from `RunProgressMath`, `cancellable` from `canStop`), so a new surface can draw the run with the same renderers. When the layer's calibration and hysteresis land, the run's text figure moves onto them behind the contract test; its ring keeps its slice maths. The run's transcription history key is also split out so it stops fragmenting by LLM choice.

The run moves last, or not at all.

## 6. Build order

Reliability phase: this is consistency work, mostly a bar and a count, invents no UX, and each step ships alone. The stress test added a step zero, because some surfaces report state that is not true and a shared layer would inherit the lie.

0. **Make the sources honest** (defects the audits found, each small and independent; none is the layer): the catch-up and post-run re-apply write their `processed` counts only at the end, so the chip has nothing to draw while running (`autocode.py:1235`, `routes/data.py:1801`); `strips_pending` is false while the strip job is deferred behind a run, so the grid stops polling and reads a deferral as done (`scene_strips.py:90`, `tapestry.py:253`); the OCR pass resets its rate on every restart and counts a cloud fetch as read time (`screen_text_job.py:165,196-198`); `DownloadRate` keeps a stale "About 2 minutes" at a zero rate (`WhisperDownloadModel.swift:96-99`); the anonymised HTML refetch shows no "Exporting…" (`WebView.swift:752,836-846`); `cancelLoad()` has no caller (`CloudImportStore.swift:706`); and the startup-refusal Retry has no feedback (`RunCoverPane.swift:121`).
1. **The contract.** `ProgressState` as a Pydantic model; `BoardBuild` becomes a view of it; the fixture and its three assertions. No behaviour change.
2. **The chip bar.** One `<progress>` in `ActivityChip` fed by the counts already served for the first-run AutoCode apply, clip export and screens export; the catch-up chip follows step 0's server tick. Rung 2 only.
3. **The estimator extraction.** `BoardProgress` generalised behind the 3.1 vocabulary, Miro as its first caller with no change a researcher can see; then outcome filtering, throughput, weights, the earned-evidence rule and asymmetric hysteresis, each proven by a fixture case; then calibration. This changes Miro's time line and needs its own review.
4. **Signals.** A per-chunk tracker that records each build's per-card seconds; rung 2 from the first build, rung 1 once calibrated. The Mac row reads it as it reads `readingScreens`.
5. **Screens lens** bar and time from `seconds_done`, `seconds_total` and `rate` (already served), with `blocked_by`; **codebook re-apply** as a job row so it has a chip.
6. **Transfers.** `DownloadRate` stays in Swift (the estimator is Python, and an Ollama pull goes Swift to Ollama with no sidecar); the shared fixture's hysteresis and stall cases hold the two versions together. Cloud import's ring weighs bytes after the size sweep, once the owner has seen a mockup of it beside the "3 of 4" words.
7. **The CLI renderer**, and the silent waits before the first stage line (rows printed as they finish; no bar).
8. **The run's read-through and text-figure adoption**, after the precondition in section 5. Last.

## 7. Tests and gates

- The contract fixture, asserted from pytest, vitest and Swift Testing, with a case per rule: no time before every remaining kind has a rate; the floor; waits kept out of the rate; only `ok` outcomes measured; throughput under concurrency (eight units, summed 289 s, wall 67 s); weights (a short last batch is not a fast unit); a fall passing at one band and a rise only at two; a stall withholding the figure; a restart flushing the window and letting the fraction fall; fraction never 1.0 with `failed` or `parked`; a `third_party` wait never carrying a figure; `estimable=False` never carrying one; a deferred job never drawn as finished.
- Prove each rule can fail: mutate it alone and see its case go red.
- A registry of job types and a structural test that every listed job resolves to a tracker and a renderer. The repo has been bitten by a dispatch table that skips names it lacks (`run_preflight`, `fd6286ee`); a `.get()` with a None-skip is a gate that cannot fail.
- Per job: an "estimate is absent until earned" case, as `MiroBoardBuildText.eta` is tested today.
- A replay harness over the recorded `llm-calls.jsonl` and `pipeline-events.jsonl` (no paid call) that predicts each job's wall time from the first half and scores the layer's earned figure against the actual; it also tunes the earned-evidence threshold in 3.2.
- The run's adapter tested against recorded `run_progress` lines, so it cannot drift from the real events.

## 8. Open questions (owner)

Settled by the stress test, so no longer questions: the padding form (job-level calibration, median until then); whether non-cancellable jobs get a ring (no, `cancellable` decides); cloud import's ring (weigh by bytes after the size sweep, keep the "N of M" words; a file of unknown size takes the median known size, and with none known the ring is indeterminate and the words stay).

1. **Overrun wording.** When elapsed passes the shown figure and nothing better can be earned, what does the time line say? Today the run says "under a minute left" and Miro says nothing. Plain words, not needy.
2. **When chrome appears.** The delay before any progress shows: 250 ms (row-scan precedent), 2 s (acknowledgement floor), or "more than a handful of seconds".
3. **Earned-evidence threshold.** "Four units, or a tenth of the planned weight" is a starting value; tune from the replay harness before it ships.
4. **Whether to record predicted against actual per job** for calibration (a small row per job beside the history), which the pad depends on, and where it lives.
5. **History file.** Extend `board-timing.json` (no format change) or rename it for what it now holds.
6. **Background enhancements that gate nothing** (scene strips, tapestry): done/total only, no ring, no time? Recommended yes, with the poll cap (about 3.3 hours) replaced by a `pending` that stays true while the job is deferred.
7. **The run's key.** Splitting transcription out of the LLM-keyed profile discards the existing profile's history; accept that, or migrate.

## 9. What this is not

- Not a service process, a daemon or a new store: a Python module, a Pydantic model and a fixture.
- Not new estimator maths beyond what the evidence demanded: Welford, the threshold, the floor and the merge are existing code; the rules that changed (calibrated pad, asymmetric hysteresis) are changes to existing specification, made because the specification was wrong for most jobs.
- Not a new look: no picture is added or restyled; the chip gains the `<progress>` the Miro panel already draws, and a shared indeterminate renderer is proposed only once a mockup exists.
- Not a reason to show an estimate before one is earned. A count first, minutes after history and calibration, a spinner when there is nothing to count, and no estimate at all for a wait a person or a provider controls.
- Not a fix per process. A wrong display is repaired in the estimator, the ladder or the state, with a fixture case, and every job inherits it.

## 10. References

`bristlenose/board_progress.py`, `bristlenose/timing.py`, `bristlenose/run_lifecycle.py`, `bristlenose/server/routes/miro.py`, `bristlenose/server/screen_text_job.py`, `bristlenose/server/scene_strips.py`, `bristlenose/server/routes/signals.py`, `bristlenose/server/autocode.py`, `desktop/Bristlenose/Bristlenose/RunProgressMath.swift`, `RunProgressSubtitle.swift`, `MiroBoardBuild.swift`, `ScreenReading.swift`, `WhisperDownloadModel.swift`, `CopyMachinery.swift`, `CloudImportStore.swift`, `frontend/src/components/ActivityChip.tsx`, `ActivityChipStack.tsx`, `MiroExportPanel.tsx`, and the docs named in section 1.
