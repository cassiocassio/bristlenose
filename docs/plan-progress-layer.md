# Plan: the shared progress layer (v2)

Status: plan v2, 30 Oct 2026. Turns `docs/design-progress-layer.md` (the design, with its ten-family stress test) into slices that ship one at a time. v1 of this plan went through an eight-reviewer plan review the same day (37 findings, about 22 distinct, kept in the maintainer's private notes); every change below answers one of them, and the closing section says which findings were taken, which were left as owner calls, and which were declined. Nothing here is built. The design owns the why and the rules; this plan owns the order, the files, the tests and the stop conditions. Where they disagree, the design wins and this plan is wrong.

## Two phases

- **Phase A: make the displays honest.** Slice 0 (eight small independent fixes) and slice 2 (the chip bar). These remove most of what is untrue on screen today, need no new picture, and invent no setting. About 9 working days.
- **Phase B: the shared layer.** Slices 1 and 3 to 8, about 22 more days, with a review at every step of slice 3. **Held until the owner decides scope (D8):** the project is in a reliability phase where "beta means almost no new features", and the first App Store submission is 24 Nov. Phase B is consistency work the owner asked for, not a feature, but it is the long pole. The plan does not start it by default.

## Constraints that shape the plan

- **Trunk on `main`, one slice per commit series, each green on its own.** No branches or worktrees unless two environments must be live at once. A slice that cannot ship alone is cut again.
- **Any task is a claim about HEAD.** Before each slice's first edit: `git log -S` and grep for the fix or feature, and re-read the cited lines. File and line references below come from audits and a review made on 30 Oct against a working tree other sessions had dirtied; treat each as a lead, not a fact.
- **A running release freezes `main` locally.** If `release.sh run` is live, a slice waits, or lands with `BN_RELEASE_FREEZE_OK=1` only if the release itself needs it.
- **Tests are free by default** (`pytest tests/`); nothing here needs a paid LLM call.
- **Locale rule.** A new user-facing string goes into all 21 full locales (`check-locales.py --strict`) and rewording an `en` value is a 21-file change. **Every slice carries a "strings" line** that lists the keys it adds (with the count) or says "reuse only" and lists the keys it reuses.
- **Stop and ask the owner if:** a slice would add a picture, a setting, a control or a string beyond what is named; **any state a renderer could turn into words** (`stopping`, `blocked_by`, `stale`, `restarted`, `parked`, an overrun line) is about to be drawn (those fields exist as state and stay undrawn until approved); a change touches the startup-refusal pane or any flow the R114 UX gate covers; a rule's test cannot be made to fail; the Miro time line changes in a way the owner did not expect; or the run's profile is still polluted when slice 8b would start.
- **One poll per surface.** A new job does not add a poller: anything a Mac row needs rides the existing carriers (`/condition` and the status routes already polled), and the SPA reads state it already fetches. Counts never go on `/tapestry`, which rebuilds its whole payload per call.
- **A new route is classified.** `tests/test_serve_export_coverage.py` fails any project GET not listed in `EMBED_PATH_TEMPLATES` or `SERVER_ONLY_PATH_TEMPLATES` (`routes/export.py`); a status route says which in its own commit.
- **No push, tag or release is part of any slice.**

## Owner decisions

| # | Question | Blocks | Status |
|---|---|---|---|
| D1 | Overrun wording when a job passes its shown figure | slice 3d text | open; until answered, keep today's behaviour (run says "under a minute", Miro nothing), no new string |
| D2 | When chrome appears (250 ms, 2 s, "a handful of seconds") | slices 7, 8a | open; slice 2 does not need it (the chip already appears when the job starts) |
| D3 | The earned-evidence threshold | nothing | **a tuning constant, not an owner call.** Ship "four units, or a tenth of the planned weight" as a starting value and revisit when the cohort shows it misbehaving; the replay harness is deferred until then |
| D4 | Record predicted against actual per job, and where; also the Welford-versus-median history question (3f) | 3f | open; blocks 3f only |
| D5 | History file: extend `board-timing.json` or rename | 3f | open; extend unless told otherwise, since no format changes |
| D6 | Background jobs that gate nothing: done/total only, and only if a renderer is named | slice 6 | open |
| D7 | Splitting the run's transcription key discards its history | slice 8b | open |
| **D8** | **Scope: do Phase B slices 1 and 3 to 8 start before the 24 Nov submission, or wait?** | all of Phase B | **open. The plan recommends Phase A first and Phase B after submission** (the reviewer's and the parsimony pass's recommendation; the owner's call) |
| D9 | Should the Signals count or minutes reach the Mac at all? (a new poll or bridge field, in the tooltip only) | slice 4's Mac half | open; default none, see slice 4 |
| D10 | Does the owner approve 0.6 (a Cancel on the cloud-import listing) and 0.7 (Retry feedback)? Both are new UX; 0.7 is inside the R114-gated startup-refusal flow and needs a mockup | 0.6, 0.7 | open; both held |

A slice that depends on an open decision is **blocked** until it is answered; a stated default is a starting proposal for the owner to overrule, never a reason to ship.

## Phase A

### Slice 0: make the sources honest (eight independent fixes)

Each is its own commit and its own test, and none depends on the layer. They matter because the layer would otherwise inherit a source that reports something untrue. Order: 0.1, 0.2, 0.4, 0.3, 0.8, 0.5; 0.6 and 0.7 are held (D10).

**0.1 Catch-up and post-run re-apply tick no live count.** Where: `bristlenose/server/autocode.py` (the `catch_up_*` writes, final UPDATE near `:1221-1241`), `routes/data.py` near `:1801`. Three conditions: the per-batch counter write is write-only (no SELECT first) and non-fatal, so a locked database cannot eat the batch's proposals (the "0 of 0 proposals" bug in `server/CLAUDE.md`); it carries the `status != "cancelled"` filter the final UPDATE has, so a batch landing after Stop cannot flip the chip back to running; and the catch-up counts reset at start. Tests: a mid-run poll over a stubbed model client **that blocks on an event between batches** (an instant stub passes vacuously) and sees `processed` rise before release; a test where the counter write raises and the proposals still land; Stop, then a batch lands, still cancelled. Strings: none.

**0.2 `strips_pending` is false while the strip job is deferred.** Two parts. 0.2a: a small status read for the strip job that reads only its counters (not the whole `/tapestry` payload), classified in the export-coverage lists. 0.2b: `strips_pending` stays true while the job is *deferred and owed* (a run is in flight and strips remain to make), and the grid polls the small status read instead of `/tapestry` while pending. The "owed" predicate matters: with the job disabled, or no video sessions, it must be false, or the grid polls for ever (`STRIP_POLL_LIMIT` is 400). Where: `server/scene_strips.py` (`start()` returns before setting `running`, `:89-90`), `routes/tapestry.py` near `:253`, `SessionsTable.tsx`. Tests: with a run in flight, pending stays true; with the job disabled, it is false; the grid keeps polling the small read and stops when it clears (the consumer, not only the flag). Strings: none.

**0.3 The OCR pass resets its rate on restart and counts a cloud fetch as read time.** Where: `server/screen_text_job.py` near `:165`, `:196-198`. Carry the rate across a restart within the same serve; start the clock after `ensure_materialised`. The "estimate from the previous pass" flag is the design's `stale`, which does not exist until the layer does, so this slice carries the rate and leaves marking it to slice 5. Tests: a restarted pass keeps its rate; fetch time is excluded from it. Strings: none.

**0.4 `DownloadRate` keeps a stale figure.** Where: `WhisperDownloadModel.swift` (`minutesLeft` returns `shownMinutes` on a nil or zero rate, `:100-103`). A real stall sends no transfer lines at all, so nothing ever asks `DownloadRate`; a test that feeds a zero-byte window feeds an input production never sends. Fix: take `now` at read time and withhold minutes once the newest sample is older than the window; do not add a heartbeat line (the larger fix). Also stop reporting a zero throughput. Tests (Swift Testing): a clock-injected read after the window with no new sample returns no minutes; the nil path (window unfilled, bytes fell) returns no minutes; a restart still resets. Mutation check: remove the age test and see the first case go red. Strings: none.

**0.5 The anonymised HTML refetch shows no "Exporting…".** Where: `WebView.swift` near `:752`, `:836-846` (the refetch closure never re-raises the pending state), `BridgeHandler.swift` (`reportExportDownloadBegan`). The fix is one call in the closure. Factor the "should the row show Exporting" decision out of the `WebView` extension first, so the test reaches it (`desktop/CLAUDE.md`); a test of a flag alone does not prove the row renders. Human QA: export with Anonymise toggled in the save panel and watch the row. Strings: none.

**0.8 A corrupt history file is overwritten silently.** Live for Miro today. Where: `bristlenose/board_progress.py` (`load_history` returns empty "never an error", `:94-100`; `remember()` then rewrites the whole `profiles` envelope with only this job's data, `:261-274`). Fix: log a WARNING and keep a `.corrupt` copy instead of overwriting; write through a temp file and rename; a non-dict `profiles` is not dropped silently. The lock and a cap on rows belong to 3f, behind the writers that make them necessary. Tests: a corrupt file is kept and warned about, not replaced; a half-written file is never read as empty. Strings: none.

**0.6 Cancel on the cloud-import listing (held, D10; a new control).** `cancelLoad()` has no caller (`CloudImportStore.swift:706`). If approved: label it "Cancel" (the sign-in state in the same window has one), bind `.cancelAction` so Esc and ⌘. work, cancel on window close, and on cancel return to the previous listing, or the signed-in state when there is none. Wiring `cancelLoad` as it stands sets `.loaded` with a nil `listing`, which draws "No recordings in the last 30 days": a false absence. Test: cancel on a first open does not draw the empty state. Strings: reuse only.

**0.7 Retry feedback on the startup-refusal pane (held, D10; inside the R114-gated flow).** Needs a mockup and explicit owner approval before any implementation (the approved scope was "Main panes Retry only"). When approved: publish the probe state (`startupProbeIsRunning` is a computed property over a non-`@Published` `startupProbe`, `ServeManager.swift:93,98`, so no view can observe it), pass a Bool into `RunCoverPane` (which takes only a closure today), and use the `FeedbackSheet` layout (`:386-391`) with the existing `llmSettings.status.checking` text, keeping `.defaultAction`. Test: the view, given the flag, disables Retry and shows the spinner. Strings: reuse only.

Exit for slice 0: each fix has a test that fails without it (mutate the fix away and see it go red, asserting the mutation landed); the full Python and Swift suites are green. About 5 days without the two held items.

### Slice 2: the chip bar

The first visible win, and bigger than v1 said: it is a motion-rule fix, a live-region fix, a string and a size check.

- **The bar replaces the shimmer; they never share the element** (`docs/design-motion.md` 4.7.1: shimmer means "thinking, no ETA", a determinate bar only where a real fraction exists). When `count_total > 1` the label drops `bn-thinking-shimmer` and the bar shows; with a total of 0, 1 or unknown the shimmer stays and no bar is drawn.
- **The bar reads a capped fraction, not `done / total`.** A failed batch still advances the count and a Stop removes the rest, so done would equal total and fill the bar. Until slice 3 gives a real `fraction`, the chip caps its own at just under 1 until the job's status is completed, and shows the chip's existing partial state when batches failed. It never moves backwards (first-run AutoCode's total can grow; the design's rule is monotone except across a `restart`).
- **Numeric fields on the job.** `ActivityChipJob` carries only `progressLabel: string` (`ActivityChip.tsx:12-23`); add numeric `done` and `total` to the type, `normaliseAutoCode`, the poll sources (`AppLayout.tsx:782,857`, `ActivityChipStack.tsx:137`) and the `ActivityStore` rehydrate path. The clip and screens chips pass `progress: 0` hard-coded (`AppLayout.tsx:748`, `:803`); fix those in the same series or they read "0 of N" all through.
- **Styling.** A chip-sized bar class in the chip's own stylesheet with `accent-color: var(--bn-colour-accent)`; not `.bn-export-progress` (`atoms/modal.css:294`, a dialog-width bar with a dialog margin). The "reused `<progress>`" is the Miro panel's element, not the toast's.
- **Accessibility.** `ActivityChipStack` wraps every chip in `role="status"` (`:347`), a polite live region re-read at each poll. Take the role off the stack and call `announce()` only on start, finish, fail, partial, cancel and stall; a count-only change makes no announcement (a test). The bar is named by `aria-labelledby` on the chip label, with a localised `aria-valuetext` ("12 of 40"). Check 3:1 contrast of fill on track in light and dark in WebKit at 1x.
- **Strings.** A new AutoCode count string, "of", in 21 locales (the first-run chip label, `autocode.chip.coding`, has no count today); the clip and screens "of" strings exist (`export.clips.progress`, `export.screens.progress`), reuse only. One key, no new vocabulary.
- **Bundle.** The report download is 208,357 B against a 222 kB budget (13.6 kB spare). The chip code in `AppLayout` is eager and imports types only; run the existing size gate and report the delta in the commit.
- **Jobs wired.** First-run AutoCode, clip export, screens export. The catch-up chip follows 0.1.
- **Tests.** Component tests: bar present and determinate for the three job shapes; absent for total 0, 1 and unknown (shimmer kept); a failed batch leaves the bar short of full and the chip partial; a stopped job does not fill it; the bar never moves backwards; no announcement on a count-only change; name and value text. Human QA, three checks: bar and shimmer never coexist; a failed batch leaves a partial bar; Stop does not fill it.

Size about 4 days. Depends on 0.1 for the catch-up chip only.

## Phase B (held pending D8)

### Slice 1 and 3a together: the contract, with its first consumer

The contract lands with its first real consumer, the extraction in 3a, not before: a schema no client reads has nothing checking it.

- `ProgressState` as a Pydantic model (`bristlenose/progress_state.py`); `BoardBuild` becomes a view of it with the same wire names. Absence is explicit: `failed`, `parked` and `partial` required with default 0; `count_total`, `fraction` and `eta_seconds` nullable and explicit; **`rung` defaults to 4** (a default of 1 claims an unearned rung; a required `rung` breaks decoding of the old payload).
- **Extend `tests/test_board_progress_contract.py`, do not add a second contract beside it.** It asserts the snapshot keys, the model fields, the Swift struct and the TS interface are the same set, so adding any field reds it; update it for the new fields and fix its Swift extraction (`split("}", 1)` truncates at the first `}`, so a nested type silently shortens the set). The fixture holds only cases that cross a language boundary (the rung choice, the fraction clamp, the failed/parked rule) with absent fields as explicit nulls, and Swift and TS assert nil, not 0. The estimator rules are Python-only.
- **ETA wording belongs in the existing `shared-format-contract.json`**, not a new file: a pure function from seconds to `{under_minute | minutes: n}` with the rounding decided once. The shipped Swift and TS both round to the nearest minute (Swift `.rounded()`, JS `Math.round`; Python's `round()` would give 2 where they give 3 at 150 s), so nearest is the rule, and the design sentence that said "rounded up" is corrected. **No Python `etaText`**: CLI chrome is English by design (`docs/design-i18n.md`), counts go through `count_noun`, and an English function cannot match 20 locales. Merging the two key copies (`common.miro.eta*` and `desktop.chrome.pipeline.eta*`, identical today) is parked: a 21-locale change twice that earns nothing until a third surface needs the words; name the namespace owner when it does.
- The job-type registry and its structural test wait for a third caller (slice 4) and are built from the producers (a `JobType` enum or the call sites, asserting the registry keys equal that set), not by iterating the registry, which cannot catch a job that never registers.

### Slice 3: the estimator (the risky one), split

Each sub-slice ships and is reviewed alone. Ordering constraints from the compose-check: 3a's goldens are recorded from the current code before extracting; the history hardening (0.8) precedes anything that adds writers; the `outcome` literal is pinned before 3b; `snapshot()` is a pure read before 3d.

- **3a. Extraction.** `BoardProgress` behind the design's event vocabulary, Miro and the screens board as callers (two callers: `miro_export.py` and `screens_export.py`). `timed` is per call, not per phase (`screens_export.py:390` times nothing for a refused image inside the `screens` phase), so `unit_done` carries it; keep a shim for `call_done` and the old `waiting_for` signature so the 18 references in `tests/test_board_progress.py` still pass. Golden snapshots of `snapshot()` over replayed call sequences recorded from the current code first, for both boards, including failed, waiting and cancelled sequences and an injected clock (the `clock=` seam). **The golden is a one-commit refactor harness: delete it at 3b.** Strings: none.
- **3b. Outcome, throughput, the fraction cap.** Pin the `outcome` literal at its producer: the call log writes `ok`, `cancelled` and `error` while the design's vocabulary says `failed`; the filter is `== "ok"`, never `!= "cancelled"` (which admits `error` rows). Rate as completions per wall second under concurrency. **The fraction cap: never 1.0 while `failed` or `parked` is above zero**, which the design promises and v1 scheduled nowhere. A zero-ok-units case: rung 2, no mean, no ETA, with the ten-second floor not what hides it. Fixture cases: eight units summing 289 s over 67 s of wall; failed rows excluded from the mean.
- **3c. Weights and the earned-evidence rule.** Per-weight rates; "four units, or a tenth of the planned weight" as a starting constant (D3).
- **3d. Hysteresis, bands and the stall rule.** The held figure and stall state are updated by events, not by reads: `snapshot()` is a pure read (a fixture: N reads, same figure; otherwise each poller ratchets it and a stall is judged against a poll gap). The stall is judged against a clock at read time. Fixture cases: a fall passing at one band, a rise only at two (and a bound on how far one visible rise may jump, covered by D1's wording when it exists), a stall withholding the figure, a restart flushing the window. Strings: none until D1 is answered.
- **3e. (folded into 0.8.)** History hardening is slice 0's.
- **3f. Calibration and the pad (blocked on D4 and D5).** Not a build slice until answered. Record each job's first estimate against its actual (a small row, capped). Note the migration it needs: `board-timing.json` holds Welford statistics, which cannot yield a median or "the largest seen", so a median-plus-max pad either keeps a row store beside the statistics (a second file, which breaks "one envelope") or demotes Miro to rung 2 under ten observations, which visibly regresses Miro's time line; an older `remember()` also rewrites the Miro profile and drops new fields, so "additive and revert-safe" is false. Decide before building. Add the lock around the read-modify-write here, with the writers (Signals, OCR, AutoCode) that make it matter.

Mutation checks apply to the Python rules: mutate each alone under `PYTHONDONTWRITEBYTECODE=1` and assert the mutation landed. For Swift, ask only that the shared contract case goes red when a decoder field is renamed.

### Slice 4: Signals (serve side only, until D9)

- A per-chunk tracker in the snapshot build (`routes/signals.py`, the chunk loop) using `unit_done(n=cards, weight=cards, seconds, outcome)`, cache hits `unplan`ned, history pooled across prompt versions per card (provider and model key only, the key defined in the new layer, not in `build_hardware_key`). The `outcome == "ok"` filter is non-negotiable: the recorded log holds more cancelled Signals rows than ok ones.
- **The Mac and the page stay as they are.** The readiness design chose "no bridge message" on purpose and rules out a progress bar or percentage on the greyed page (`design-signals-lens-readiness.md:43-45,68,106`); the Mac row reads the `lens-availability` message, not `/condition` or `/signals/snapshot`; and `preparingSignals` is text with no ring because it cannot be stopped (`ProjectSubtitle.swift:80-87`). A count would need a new bridge field or a poll like the Screens one. Whether "3 of 9" cards is worth it for a job of about a minute ("of what?") is D9; if approved, it goes in the row's tooltip as `screensTooltip` does, never as a ring or a new line.
- The job-type registry and its structural test land here (third caller).
- Tests: a tracker test over a recorded chunk sequence (cached and uncached chunks, cancelled rows, a zero-ok build); a Swift test only if D9 is approved. Strings: none unless D9.

### Slice 5: Screens lens, codebook re-apply

- The Screens lens draws a bar and a time line from `seconds_done`, `seconds_total` and `rate` already served, depends on 0.3. `blocked_by` is served nowhere today (`git grep` finds nothing); adding it to `/screens/status` is part of this slice, and showing a reason is **new copy in 21 locales that needs the owner's sign-off** (a stop-and-ask item). The Mac row keeps "Screens · N of M" with no ring by decision, so there is no frozen ring to worry about; the lens gives the reason in plain words and no time while blocked.
- The post-run codebook re-apply becomes a job row with a chip (depends on 0.1), showing the owed-quote count; no Stop, by existing design.
- Strings: the `blocked_by` reasons (up to four keys across 21 locales; reuse `screens.waiting_*` for the analysis case) and the chip's reuse of slice 2's count string.

### Slice 6: background enhancements that gate nothing

Counts for strips, colours and frames come from 0.2a's small status read, never `/tapestry`. Built only if a renderer is named to draw them (D6): a field nothing renders is a contract with no witness. If none is named, slice 6 stops at 0.2 and nothing is added. No ring, no time.

### Slice 7: transfers (mockup first)

- **A mockup of exactly the disagreeing case comes first** and the owner confirms it: a ring weighted by bytes beside the "3 of 4" words (three small files done, one large left: words say 3 of 4, ring near 20%). It changes a shipped surface.
- **`DownloadRate` stays in Swift.** The layer's estimator is Python and Ollama pulls go Swift to Ollama and can run from Settings with no sidecar, so "moves into the layer" does not work. The shared fixture's hysteresis and stall cases hold the two versions together. The Ollama pill keeps showing a percentage and no minutes; reading shared state must not quietly add minutes there.
- Unknown sizes take the median known size; with none known the ring is indeterminate and the words stay; **the ring never steps backwards** when a real size replaces a median (clamped to the highest value shown; a fixture case).
- Tests, which v1 left out and which are pure arithmetic: the byte-weighted fraction, median fill, none-known indeterminate, the clamp. Strings: reuse only.

### Slice 8: CLI, and the run

- **8a (any time after slice 3a).** Print each preflight row as its check finishes (no bar); print the `serve` URL only after it answers (the `--port 0` path already does); a `console.status` for the silent key checks. These are English-only lines (the `preflight` namespace refuses translated copies); count-bearing lines use `count_noun`. About 2 days.
- **8b, last.** The run's read-through adapter (`run_progress` to `ProgressState`) and the text figure onto the layer's rules, behind the contract test. **Precondition as a gate, not prose:** a check that fails while `timing.json` carries more than N observations for a stage (the pollution is being investigated in its own task). Not started until D7 is answered.

### Not in the plan

The shared indeterminate-with-elapsed renderer: the design promises it, no slice builds it, and "an elapsed cue" has no defined look anywhere, so it is a new picture. It needs a mockup before any slice takes it, and the design promise is withdrawn until then. Also: the replay harness (deferred until the cohort shows the default threshold misbehaving; when it is built it scores failed and cancelled jobs separately, asserts a minimum row count per job, and streams the log); a heartbeat line from the transfer sidecar; a Python `etaText`; merging the two ETA key copies; any new progress picture; time estimates for jobs the design marks `estimable=False` or rung 4 forever; the cloud-evicted-file wait, closed by the 22 Oct ruling; pushing, tagging or releasing.

## Order and dependencies

```
Phase A
  0.1, 0.2 (a then b), 0.4, 0.3, 0.8, 0.5   (independent; 0.6 and 0.7 held, D10)
  2 chip bar          (catch-up chip waits for 0.1)

Phase B (held, D8)
  0.8 --> 3a+1 --> 3b --> 3c --> 3d
                   3b..3d --> 4 (serve side) --> registry test
                   3d --> 3f (D4, D5) --> lock, calibration
  0.2a, 0.3 --> 5, 6
  mockup + owner --> 7
  3a --> 8a
  gate on timing.json + D7 --> 8b (last)
```

No cycle. Slice 1 does not wait for slice 3: they land together.

## Verification and stop conditions

- Per slice: the new tests plus the full Python suite and whole-repo Ruff (`.venv/bin/python -m pytest tests/`, `.venv/bin/ruff check .`); Swift slices run the native suite locally (`desktop/scripts/test-swift.sh`; CI runs it post-push on a stub sidecar); frontend slices run vitest, the type check and the bundle-size gate; a slice that adds a route runs `tests/test_serve_export_coverage.py`; a slice that adds a string runs `check-locales.py --strict`.
- Rollback is `git revert` of the slice's commits. Slice 0 and 2 change no stored format. Phase B changes history keys additively except 3f, whose migration is called out above before it is built.

## What the plan review changed

Taken, in the plan above: the existing contract test and nested-type truncation (1, 21); the bar filling over failed units (2, 18); the stall fix needing a read-time clock (3); the Cancel false empty state (4); the R114 gate on 0.7 (5); the three conditions on 0.1 (6); deferred-versus-disabled and the consumers (7, 23); the motion-rule conflict, live region, numeric job fields, strings and bundle for slice 2 (10, 11, 12, 25); slice 4's contradiction of the readiness design (13); history corruption (14, as 0.8) and its pure-read and migration notes (15, 16); the extraction details (17); the `outcome` literal (19); explicit absence in the contract (21); the registry at its third caller (22); one poll per surface (24); the ETA rounding and the English-CLI rule (26); a strings line per slice and the undrawn-state rule (27); the byte ring, `DownloadRate` and the Ollama pill (28); the rise bound (29); `blocked_by` (30); the indeterminate renderer withdrawn (31); the test strategy gaps and the 3d/3e split (32); the gates table (33); the small items (37).

Left as owner calls: 34 (scope, D8), 4 and 5 (D10), 28's mockup, 13's Mac count (D9), 31's mockup. Declined, with reasons: the replay harness now (20: the default stands; revisit on evidence), a heartbeat line (3: the larger of two fixes), a Python `etaText` and merging the key copies (26: three times too big for what it buys), the history lock and row cap before the writers exist (14).
