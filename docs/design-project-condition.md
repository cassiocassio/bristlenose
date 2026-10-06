---
status: in progress — phases A and B shipped in 0.31.5 (the POC code was production code); D, C, E, F designed, not built
last-trued: 2026-10-06
owner: project status across Python, the report server, the SPA and the Mac app
---

# Project condition — one answer to "what state is this project in?"

**Why this doc exists.** On 28 Sep 2026 re-analysing a project whose last run had
failed put *"Last run failed."* in the detail pane under a sidebar row reading
*"Queued · position 1"*. Fixing that one combination (`738a69f8`) led to an audit
of every surface that describes a project's state. It found the same defect
twenty-odd times: **three readers derive the project's condition from the events
log, each in its own way, and every bug is one surface reading a source that is
stale relative to its neighbour's.** This doc is the plan and design for giving
the question a single owner, the record of the proof of concept (POC) that tested
the design against data, and the design of the Mac half that follows.

How to read it: §1 is the problem in one screen, §2 the plan, §3 the design,
§4 what the POC taught (it revised §3 — the changes are marked), §5 the Mac
implementation design, §6 open questions, and the appendix the verified register
every claim here rests on.

---

## 1. The problem

The pipeline appends lifecycle events (`run_started`, `run_progress`,
`run_completed`, `run_failed`, `run_cancelled`) to
`<output>/.bristlenose/pipeline-events.jsonl`. That file is the complete record.
Three readers turn it into "what state is this project in":

| Reader | How it reads the log | What it gets wrong |
|---|---|---|
| **Mac** — `EventLogReader.deriveState` → `PipelineState` | latest lifecycle event in a 64 KB tail, plus a PID-liveness check | no memory of the last *report*; cancel and dequeue write `.idle`; states written once and never re-derived |
| **Report server** — `event_watcher` → `app.state.last_run` → `status_page.detect_status` | a startup seed of the last terminus, then a watcher that dispatches **only `run_completed`**, baselined by **line count** | blind to failures and cancels while up; misses a replaced log (`--clean`); ignores `kind`; roots at the interview folder when `bristlenose-output/` doesn't exist yet; title and cause from different runs |
| **SPA** — `LastRunStore` polls `/api/projects/1/last-run` | the server's `last_run` | inherits every server blind spot; can't know a run is in progress |

Five root causes, in order of reach:

1. **State written by one path and never re-derived** (Mac: sticky "Stopping…",
   "Timed out", orphan runs, `.failedWithDiagnostic` only after relaunch).
2. **Absence written as a state** (`.idle` on cancel/dequeue; "no run" when the
   terminus line is lost).
3. **Readers that ignore identity** (line counts not `run_id`; wrong folder;
   `kind` ignored; outcome and cause from different runs).
4. **Refresh on a clock, not a signal** (the Mac's 1.5 s one-shot reload).
5. **Contracts that pin names, not behaviour** (parity tests check vocabulary;
   nothing checks that two readers agree about *when*).

The full register — 57 verified findings with evidence — is in the appendix.

---

## 2. Plan

### 2.1 Shape: four layers, one owner each

```
Record        events log (append-only; run_id, kind, cause)
   │
Condition     one pure reducer, Python + Swift, pinned by one shared fixture
   │
Overlays      facts only one host knows — Mac: queue, stop requested, spawn failed
   │                                     server: importing, import failed
Presentation  one cause table (category/reason → kind, locale key, action)
```

Rule the whole design serves: **every surface reads the same condition, and every
new state enters through a fixture case.**

### 2.2 Phases

| Phase | Scope | Status |
|---|---|---|
| **A — reducer** | `bristlenose/run_condition.py`, the shared fixture, property tests, differential run over real logs | **shipped 0.31.5** (`d367bcca`; §4) |
| **B — report server** | output-location resolution, identity-keyed watcher, condition state, `last_run` as data version only, import overlay, intercept policy, in-progress status page, condition endpoint | **shipped 0.31.5** (`d367bcca`, test fix `e6c39a05`; §4) |
| **D — Swift reducer parity** | `RunCondition.reduce` in Swift, reading the same fixture; `EventLogReader` gains the report slot | designed (§5.1) — **before C** (revised by §4: the sidebar needs the condition for projects with no server running) |
| **C — Mac** | `ProjectStatus` aggregate + resolvers, overlays instead of `.idle` writes, run-id freshness, libproc liveness, reload on a signal | **designed** (§5), not built |
| E — cause table + status page copy | shared JSON; category headline; `t_in` + `lang` | designed (§3.7) |
| F — contract hardening | category parity vs real Swift; `ArtifactPrior` vs server rule; `default:` gate; bridge parity; export partial-run note | listed (§6) |

### 2.3 Why a POC before implementation

The core is a pure function over data, the cheapest thing to prove before
building in three languages. The real corpus is thin (18 logs, 160 events,
all kind `run`, zero cancels — measured §4.1), so the POC proves the reducer
against **generated** event sequences and uses the real logs as the check that the
model matches reality. Phase A code lives in `bristlenose/` from day one with no
callers outside the POC wiring, so it *is* the production code; the fixture and
harness are permanent.

---

## 3. Detailed design

### 3.1 The record

The events log is unchanged by this design. Two properties the readers must now
respect:

- **Identity is `run_id`.** Every lifecycle event carries one. Line position and
  line count are not identity: `--clean` moves the whole output folder aside
  (`output_backup.stash`) and the new run starts a fresh, shorter log; a failed
  `--clean` run restores the old tree and appends the new run's history to it.
- **`kind` is part of the fact.** `run` and `analyze` produce a report;
  `transcribe-only` does not. A `transcribe-only` completion is not a report.

### 3.2 The condition

A pure function: `reduce(lines, liveness) → Condition`. `lines` are raw JSONL
lines; `liveness(run_id) → bool | None` answers "is the process that owns this
run alive?" (`None` = unknown, treated as dead after the fact).

```json
{
  "schema": 1,
  "decodable": true,
  "latest": {
    "run_id": "01M1C6…", "kind": "run",
    "state": "in_progress | completed | failed | cancelled | stranded",
    "started_at": "…", "ended_at": "… | null",
    "degraded": false,
    "cause": { "category": "out_of_credit", "reason": null, "stage": "topic_segmentation" }
  },
  "report": { "run_id": "01K…", "kind": "run", "ended_at": "…", "degraded": false },
  "history": { "runs": 4, "stranded": 1 }
}
```

- **`latest`** — the run whose lifecycle event appears last in the file. Its
  state comes from its terminus; with no terminus it is `in_progress` if
  `liveness(run_id)` is true, else `stranded`.
- **`report`** — the last `run_completed` whose kind is `run` or `analyze`: the
  run whose report is on disk. `null` if none.
- **`degraded`** — a completion whose `summary` carries any failed session. Same
  rule as Swift's `totalFailureCount > 0`.
- **`cause`** — category, reason, stage. **No `message`**: it is English forensic
  text; wording comes from the cause table (§3.7). The raw message stays in the
  log for "Show details".
- **Legacy evidence** — *revised by the POC (§4.2).* `reduce(lines, liveness,
  legacy_report)`: when the log records **no runs at all** and the manifest
  records a finished render, `report` is that render, marked
  `source: "manifest"`. It never overrides anything the log says.
- **`decodable`** — `false` when a *well-formed JSON line* of a **known** event
  type does not fit the event model (an unknown event type is skipped, as the
  Swift reader already does). Swift already fails closed on this (a `duration_ms: null` once turned a
  successful run into "stopped unexpectedly"); Python's `read_events` silently
  skipped it. A torn final line (not valid JSON) is crash residue and is skipped.
- **`history`** — counts only, for diagnostics and the POC visualisation.

**Why two slots, not "latest per kind"** (the draft said per kind): every verified
defect is one of two questions — *what happened last?* and *is there a report
behind it?* A per-kind map answered neither directly and pushed the
interpretation back into each reader, which is the disease.

**Liveness is matched to `run_id`.** The Python PID file already records
`{pid, start_time, run_id}`; Swift decodes `runId` and ignores it. A stranded
older run and a live newer one can coexist in one log; unkeyed liveness would
call the old one alive.

### 3.3 Invariants (property-tested)

1. Appending a `run_progress` line never changes the condition.
2. `report` never points at a failed, cancelled or `transcribe-only` run.
3. A terminus for a run never *removes* `report` unless it is a newer completion
   replacing it.
4. `latest.run_id` is the run of the last lifecycle event in file order.
5. The reducer is total: any sequence of valid events yields a condition;
   no exception escapes.
6. Deterministic: the same lines and liveness give the same condition.

### 3.4 The shared fixture

`tests/fixtures/run-condition-contract.json` — each case is a compact event list,
a liveness map and the expected condition. Python reads it now; the Swift
`@Test` reads it in phase D. Cases are named for the bug each would have caught.

### 3.5 Report server

**Output location, resolved lazily.** One resolver answers "where does this
project's output live?" — `<project>/bristlenose-output` unless the caller passed
an output dir itself. The events path is derived from it *even when it doesn't
exist yet*, and re-evaluated on every poll. The server does **not** create the
directory (a pre-existing `bristlenose-output/` would make `bristlenose run`
refuse with `output_exists`).

**Watcher keyed on identity.** Each poll compares the file's
`(device, inode, size, mtime)`. Re-import is keyed on `run_id` (a first-seen
`run_completed`), never on line position — unchanged contract,
`test_ignores_run_failed` stays. A second callback, `on_change`, fires once at
start and on **every** change to the file, and recomputes the condition. *Revised
after review:* the draft recomputed only when a new `(run_id, event)` pair
appeared, which missed `output_backup.restore` rewriting the log without a new
run, and events landing between app construction and the watcher's baseline.

**Liveness re-checked at request time.** *Added after review.* A run that dies
without a terminus (SIGKILL, OOM, a crash) changes nothing on disk, so a cached
`in_progress` would never become `stranded`; a run seen in the gap between
`run_started` and its PID file would read `stranded` for its whole life.
`current_condition()` serves the cache for settled states and re-reads whenever
the latest run has no terminus.

**Two pieces of state, not one.**
- `app.state.condition` — the reducer's answer, recomputed on every lifecycle
  event and at startup. The status page and the condition endpoint read it.
- `app.state.last_run` — **the data version only**: set when an import
  *succeeds*. `/last-run` keeps its pinned shape and meaning for the SPA's
  refetch key.

**Server overlay.** `importing` between a completion and a finished import;
`import_failed` when the import raises (today it is swallowed and the run is
published anyway).

**Intercept policy — one function, one open decision.** Whether the SPA renders
is `should_intercept(condition, overlay, policy)`:

| Condition | `latest-attempt` (today's startup rule, default) | `last-good-report` (D4-B, proposed) |
|---|---|---|
| no runs, no legacy report | intercept: no-run | intercept: no-run |
| no runs, legacy report (manifest) | SPA | SPA |
| latest in progress, no report | intercept: in-progress | intercept: in-progress |
| latest in progress, report exists | SPA (+ banner) — *revised by the POC: a re-run never hides the report it will replace, in either policy* | SPA (+ banner) |
| latest stranded, report exists | SPA — *revised after review: a stranded run did not touch the report, and liveness can be wrong in the "can't tell" direction* | SPA |
| latest completed, import in flight, no data version yet | intercept: in-progress — *added after review* | intercept: in-progress |
| latest failed / cancelled / stranded, report exists | intercept: failed / cancelled | **SPA** (+ banner) |
| latest completed (`run`/`analyze`) | SPA | SPA |
| latest `transcribe-only` completed, no report | SPA — *revised after review: a "transcribed" page hid the Sessions and transcript routes that were reachable before* | SPA |
| import failed | SPA of the previous data version; the failure is in the condition endpoint's overlay (a status page for it needs new copy — phase E) | same |

Today the server implements *neither* consistently: the startup seed gives
`latest-attempt`, the running watcher gives `last-good-report` by accident. The
POC makes the policy explicit and defaults to `latest-attempt`.

**Status page outcomes.** `no-run`, `failed`, `cancelled` as today, plus
`in-progress` and `stranded`. Each is added to
Swift's `StatusPageOutcome` in the same commit (the parity test demands it; no
Swift code switches on the value, so the mirror is inert). The in-progress page
refreshes itself.

**Condition endpoint.** `GET /api/projects/{id}/condition` — the reducer's
answer plus the server overlay. Classified `SERVER_ONLY` in `routes/export.py`
(an export is a snapshot; it carries a stamp instead, phase F).

### 3.6 SPA (phase F — not in the POC)

Polls the condition endpoint (instead of inferring from `/last-run`) only to
drive the freshness banner already mocked in
`docs/mockups/report-freshness-banner.html`. `/last-run` stays the data-version
refetch key.

### 3.7 Presentation — the cause table (phase E — not in the POC)

`bristlenose/data/cause-presentation.json`, keyed `(category, reason?)` →
`{kind, key, action}`. Replaces three mappings: Swift
`FailureMessage.failure(for:)`, TypeScript `utils/autocodeFailure.ts`, and the
status page (which has none). Completeness test: every `CauseCategoryEnum` value
has a row, every row's key exists in all 21 full locales.

---

## 4. What the POC taught

Built 28 Sep 2026: `bristlenose/run_condition.py`, the shared fixture (22
cases), property tests over 300 generated logs, the server wiring, the condition
endpoint, a self-refreshing status page, and end-to-end tests with the live
watcher. Every new test was proved to bite by reverting the fix it guards (10
mutants, all killed). Full suite 5475 passed; mypy unchanged at 162 locally
(the ratchet's zero margin held); `check-locales.py --strict` clean.

### 4.1 Reproduced before fixing

| Defect | Reproduced by | Now |
|---|---|---|
| F4 — failure while serving invisible; title and cause from different runs | `test_failure_while_serve_is_up_reaches_the_page`, `test_title_and_cause_come_from_the_same_run` | fixed |
| N19 — Re-analyse (`--clean`) never reaches the report | `test_clean_rerun_replacing_the_log_is_seen` | fixed |
| N46 — serve started before the first run watches the interview folder | `test_serve_started_before_first_run_follows_the_output` | fixed for the watcher and status page (see §4.4) |
| F6 — a failed import published as the new data version | `test_failed_import_is_not_published` | fixed |
| F5 — stranded run shows the previous result on the web | fixture `first-run-stranded`, `test_owner_dying_without_a_terminus_is_noticed` | fixed |
| N20 / N49 — kind ignored | fixture `transcribe-only-*`, `test_failed_transcribe_never_hides_a_report` | fixed |

### 4.2 The real data changed the design

A differential over every events log on the maintainer's Mac (18 logs, 23 runs,
30 output folders; `experiments/run-condition/differential.py`) found:

- **13 of 30 output folders have no events log.** Two are real projects analysed
  before the log existed; the manifest says render complete and the report is on
  disk, yet today's server shows *"Nothing to see here, yet."* over them. The
  reducer gained a `legacy_report` input (§3.2) — and then the policy function
  had the same bug one layer up (it checked "no runs" before "is there a
  report"), caught by running the same data through it again.
- **One project disagreed with today's server**: a stranded run the server
  called "no run" and the Mac called "stopped unexpectedly". The reducer agrees
  with the Mac.
- **The corpus is thin**: every run is kind `run`, zero cancels, logs ≤ 23 KB.
  The generated fixture and property tests carry the states the real data
  doesn't, which is why they exist.

### 4.3 The reviews changed it again

Three independent reviews (correctness, silent failures, cross-surface
regression) ran against the first build. Two findings were reported by all
three, which is the strongest signal a review gives:

1. **The cached condition went stale in both directions** — a crashed run stayed
   "in progress" for the server's life; a run seen before its PID file stayed
   "stranded". Fixed by request-time liveness (§3.5).
2. **The page flipped to the report before the import finished.** The log says
   completed before the database holds the run. Fixed by passing the import
   state into `page_for`.

And, from one review each: the watcher recomputed only on new run ids (missed
`restore`); `read_condition` loaded the manifest unconditionally, so a junk
manifest could stop the server starting; one malformed `run_progress` line made
the whole log undecodable; the report slot aliased a mutable record; the
"transcribed" page hid transcripts that were reachable before (withdrawn — its
locale key and Swift case with it); `/last-run` could 500 on a legacy report
with no timestamp; the MCP overview's "newest run" silently became the data
version (it now reads the condition). All fixed, each with a test.

### 4.4 Deliberately not fixed in the POC

- **N23 — a zero-quote run is recorded `run_completed` before `restore()`**
  puts the old tree back, so the condition names a report that is not on disk.
  A writer bug in `cli.py`: the terminus must be decided inside the lifecycle
  block. Phase B, pipeline side.
- **The other eight output-location call sites** (`db.py`, `importer.py`, …)
  still use the old two-line rule, so a serve started before the first run puts
  its database in the interview folder. Moving them changes where an existing
  project's database lives — a migration, not a refactor.
- **An undecodable log with no known report fails open** (serves the SPA). The
  honest page needs copy ("this project's history can't be read") — phase E.
- **The self-refresh script cannot say it lost contact** with a stopped server;
  it keeps its last state. Needs copy — phase E.
- **Liveness under the Mac sandbox is unmeasured.** The serve now judges whether
  the pipeline process is alive from `run.pid` (`proc_pidinfo`). If the sandbox
  denies that for a sibling process, every live first run reads as stranded on
  the Mac. The Mac covers a running project natively, which would mask it —
  needs one measurement on a sandboxed build before phase C relies on it.

### 4.5 What generalises

- **A cache of a derived answer is only as fresh as its slowest input.** The
  log is the fast input; process death is the slow one and writes nothing.
  Anything that caches the condition must re-derive when an unsettled state is
  asked about.
- **"Did anything new happen?" is the wrong trigger; "did the input change?" is
  the right one.** Keying recompute on new events missed a rewrite that added
  none.
- **Two readers, two orders of truth.** The log said "completed" before the
  database held it. The condition is about the run; the data version is about
  the database; a page decision needs both.
- **Run the real data through each layer, not just the first.** The legacy bug
  was fixed in the reducer and survived in the policy function above it.

## 5. Mac implementation design (phase C) — designed, not built

This is `docs/design-desktop-project-status.md` §7's deferred **`ProjectStatus`
aggregate**, made concrete now that the condition exists. It is not a sibling
design: that doc's point 1 (one aggregate) and point 2 (one pure resolver,
already done for the subtitle as `ProjectSubtitle.resolve`) are what this
section builds, and the subtitle resolver becomes one consumer of it.

### 5.1 Where the Mac gets the condition

**Locally, from a Swift reducer — not from the server.** The sidebar shows
every project, and serves start lazily (`ServeFleet`), so most rows have no
server to ask. `EventLogReader` becomes `RunCondition.reduce(lines:liveness:legacyReport:)`,
the Swift twin of `run_condition.reduce_lines`, and reads the same fixture
(`tests/fixtures/run-condition-contract.json`) from a Swift `@Test`. So **phase D
(Swift reducer parity) is a prerequisite of phase C**, not a follow-up — the plan
table's order is corrected in §2.2.

Three things the Swift reader changes, each forced by a fixture case:

| Today (`EventLogReader.deriveState`) | Designed | Case that forces it |
|---|---|---|
| Latest lifecycle event only | two slots: `latest` + `report` | `rerun-fails-after-report`, `rerun-cancelled-after-report` |
| 64 KB tail | reads until it has both slots (whole file when needed; logs measured ≤ 23 KB) | `report-beyond-64kb-tail` |
| liveness = PID file alive | PID file alive **and** `run_id` matches | `old-stranded-new-completed` |
| manifest consulted first; a damaged manifest masks a healthy log | log first; manifest only as legacy evidence | `legacy-project-without-log`, `legacy-evidence-never-overrides-the-log` |

Liveness moves to libproc (`proc_pidinfo`), which `EventLogReader` already
uses. The orphan probe's two `/bin/ps` execs (`PipelineRunner.swift:637`,
`:648`) go too — under the sandbox they fail and delete the PID file.

### 5.2 One aggregate, one resolver

```swift
struct ProjectStatus: Equatable {
    let condition: RunCondition          // from disk — the Swift reducer
    let overlay: RunOverlay?             // facts only the Mac knows
    let availability: ProjectAvailability
    let serve: ServeState                // whether a document can be shown at all
}

enum RunOverlay: Equatable {
    case queued(position: Int)
    case spawned(runID: String?)         // our own subprocess, before its run_started lands
    case stopping
    case spawnFailed(PipelineFailureCategory)
}
```

`PipelineState` stops being the source of truth. It survives, during migration,
as a **derived** value (`ProjectStatus.legacyPipelineState`) so the eleven
surfaces that read it can move one at a time. The resolvers, each pure and
each unit-tested, are:

- `ProjectStatus.rowVariant` — replaces `ProjectSubtitle.resolve`'s inputs;
- `ProjectStatus.paneKind` — replaces `DetailPaneKind.resolve` **and**
  `DetailPaneKind.runCover` (the cover becomes "an overlay the server cannot
  know about", keyed on the overlay, not on `documentState`);
- `ProjectStatus.lensPrior` — replaces `ArtifactPrior`, and is tested **against
  `page_for` through the shared fixture**: the prior predicts SPA exactly when
  `page_for` returns `None`. This is the test the audit found missing (C3).

### 5.3 The writes that go

| Today | Designed |
|---|---|
| `cancel()` on a queued project → `state = .idle` (F1) | remove the overlay; the condition underneath shows through |
| owned-run cancel → `state = .idle` (F2) | remove the overlay; Python has already written `run_cancelled`, so the condition says cancelled |
| orphan exit → `.idle`, then rescan after 500 ms (N36) | remove the overlay; rescan |
| `applyScanResult` refuses to overwrite runner-owned states (N63, N61, sticky "Run failed" after a CLI run) | replaces whenever the scanned condition's `latest.run_id` differs — the run id, not the state, decides freshness |
| `isStopping` set once, never cleared (N60) | lives in the overlay; gone when the overlay goes |
| one global `generation` guards every project's termination write (N66) | per-project run generation |
| spawn path resolves `.failedWithDiagnostic` only after relaunch (N68) | the termination handler re-reads the condition — the same reducer as launch |

The rule underneath all seven: **the Mac never writes a state it can re-derive.**
It writes overlays (what only it knows) and re-reads the condition (what the log
knows). Absence of an overlay means "nothing Mac-only is happening" — which is a
fact, not a guess — and never means "never analysed".

### 5.4 Reload: from a clock to a signal

With the server change (§4) the Mac's one-shot 1.5 s reload
(`ContentView.scheduleReportReloadOnCompletion`) is redundant for status pages —
**the page now refreshes itself** when its condition changes, including into the
SPA. For the SPA, the data version (`/last-run`) already drives a refetch where
`LastRunStore` polls; the Signals and Transcript lenses don't poll (N30), which
is phase F. So the design is: delete the clock loop once `LastRunStore` polling is
app-wide (phase F); until then keep it, but gate it on the server reporting the
finished `run_id` as its data version rather than on a sleep.

**One interaction to handle:** a status page
reloading itself sets `documentState` to `.loading` for a moment, which lifts the
native cover (`runCover` needs `.statusPage`). Keying the cover on the overlay
(§5.2) removes the dependency on `documentState` altogether.

### 5.5 Tests

- `RunConditionTests` — the shared fixture, byte-for-byte the Python cases.
- `ProjectStatusTests` — a scenario matrix: (condition case × overlay ×
  availability × serve state) → row variant, pane kind, lens prior, menu gates
  (Analyse / Re-analyse / Stop / Locate). One table asserts every surface
  together — the agreement test that did not exist.
- `LensPriorParityTests` — prior vs `page_for` over every fixture case.
- A `default:`-arm gate (`check-*.sh`, the appearance-seam precedent) over
  switches on `RunCondition.State`, `RunOverlay` and `ProjectStatus`.
- One live pass on a sandboxed build: Stop, dequeue, relaunch mid-run, eject.
  Timing and sandbox behaviour are the two things tests here cannot see.

### 5.6 Order of work (each step shippable)

1. Swift reducer + fixture parity (phase D).
2. `ProjectStatus` + resolvers, with `legacyPipelineState` so nothing else moves.
3. Replace the `.idle` writes and the `applyScanResult` rule (F1, F2, N36, N61, N63).
4. Overlay-keyed cover; per-project generation; clear stopping (N60, N66).
5. libproc orphan probe (N34); `.failedWithDiagnostic` on the spawn path (N68).
6. Move surfaces off `PipelineState` one at a time; delete it when none read it.
7. Delete the clock reload once phase F lands.

---

## 6. Open questions

1. **D4 — after a failed re-run, show the last good report or the failure?**
   Proposed as D4-B in `design-pipeline-diagnostic-popover.md` §"Proposed — the
   three-part body", not decided. The POC makes it one environment switch
   (`_BRISTLENOSE_REPORT_POLICY=last-good-report`) and the mockup shows both.
   Default today: latest-attempt, which is what the server did at startup.
2. **Where should the database of a never-run project live?** Today: the
   interview folder's `.bristlenose/`. The resolver says `bristlenose-output/`,
   which `bristlenose run` refuses to start into if it already exists. Options:
   create the DB lazily on first import, or teach `run` to accept an output
   folder holding only `.bristlenose/bristlenose.db`.
3. **Sandbox liveness** (§4.4) — measure before phase C.
4. **Copy for three pages that don't exist yet** — import failed with no earlier
   data, history unreadable, lost contact — phase E, with the cause table.

---

## Appendix — verified register

The audit behind this doc (28 Sep 2026): 31 claims verified by trace, refute and
impact lenses; 26 further findings verified or reproduced (13 by running code);
57 candidates in all, 0 refuted. IDs are the ones used above.

| ID | Surface | Finding | Status |
|---|---|---|---|
| F1 | Mac | dequeue writes `.idle` → "Drag Interviews Here" over a report | phase C |
| F2 | Mac | owned-run cancel writes `.idle`, not `.stopped` | phase C |
| F3 | Mac | `.scanning` counted as analysing (shoal + spurious reload) | phase C |
| F4 | server | failure while serving invisible; title/cause from different runs | **fixed (POC)** |
| F5 | server/web | stranded run invisible until next run | **fixed (POC)** |
| F6 | server | failed import published | **fixed (POC)** |
| F7 | status page | English `cause.message`, category only in details | phase E |
| F9 | Mac | window subtitle keeps the lens count over a status page | phase C |
| F10 | export | partial run looks complete in an export | phase F |
| F12 | Mac | exit-0 paths to `.partial`/`.idle`/`.unreachable` skip the reload | phase C (reload deleted) |
| F18 | Mac | Re-analyse enablement stale after a run | phase C |
| N19 | server | `--clean` log replacement missed by line-count watcher | **fixed (POC)** |
| N20/N49 | server | run kind ignored | **fixed (POC)** |
| N23 | pipeline | zero-quote completion recorded before restore | phase B (writer) |
| N34 | Mac | orphan probe `/bin/ps` fails under sandbox, deletes PID file | phase C |
| N35/N59 | Mac | one-shot reload on a clock | phase C / F |
| N36, N60, N61, N63, N66, N68 | Mac | states written once and never re-derived | phase C |
| N46/N54 | server | never-run serve watches the interview folder | **watcher fixed (POC)**; DB location open (§6.2) |
| N57 | server | `/report/*` served dotfiles and paths outside the output folder, no token | **fixed separately** — `ba4429c7`; re-verified 28 Sep: all three probes now 404 |
| N58 | server | lost terminus demotes an imported report to "no run" | partly (legacy manifest fallback) |
| N69 | contracts | category parity test compares Python to a hand-typed list | phase F |
| C3 | contracts | `ArtifactPrior` vs server rule untested | phase C (`LensPriorParityTests`) |
| C4 | contracts | TS↔Swift bridge message parity untested | phase F |
| C6 | Swift | `default:` arms over `PipelineState` | phase C (gate) |

**Docs to true when phase C lands** (from the cross-surface review):
`desktop/CLAUDE.md` report-auto-reload gotcha; `bristlenose/server/CLAUDE.md`
(`last_run` is the data version; `app.state.condition` is the run state);
`LensAvailability.swift` `ArtifactPrior` comment; `DetailPaneKind.swift`
("describes the last terminus"); `docs/design-detail-panes-catalogue.md`
outcome list; `docs/design-pipeline-resilience.md` liveness rules (the serve
judges liveness now too); `docs/design-analysis-lifecycle.md` stranded row.
