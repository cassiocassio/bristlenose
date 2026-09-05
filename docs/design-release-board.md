---
status: plan — reviewed by /usual-suspects before build (5 Sep 2026)
date: 2026-09-05
decides: docs/design-release-train-dashboard.md § 3 → sketch B, the board
sketch: docs/mockups/release-train-board.html
---

# The release board — build plan

**Decision (5 Sep 2026): build the board, not the timeline.** The maintainer's
framing: this is the London Underground map, not the Ordnance Survey — what
matters is the *connections and the logic of the journey*, sequence,
dependencies, pass and fail, the qualitative state, not the distance between
stations. A time axis makes the picture less useful, not more. The board has
a flow (top-left to bottom-right), room for scrolling detail inside panes,
and panes that can size to content or be resized.

This plan has two halves that ship in order: **the feed** (make the train
write down what it already knows) and **the board** (draw it). The feed is
worth having with no board at all; the board is worthless without the feed.

## 0 · Principles, stated once

1. **Read, never derive.** Every state on the board comes from a file a script
   wrote or a probe answered. The board never infers "PyPI is live" from "the
   tag was pushed". Where nothing was written, the tile says *no data*, which
   is a third state, not green and not red — the tri-state rule from
   `verify-channels.sh` applied to a picture.
2. **The report is a view; so is the board.** No step's control flow changes.
   The feed is a tee on lines the scripts already emit
   (`REPORT-STYLE.md`: "a view, not the control flow").
3. **One run id joins everything.** `release.sh` mints it; every child carries
   it; a standalone build mints its own. Without it there is no join, only a
   guess.
4. **Topology from the sources of topology.** The sequence of steps comes from
   `release.sh`'s own step table; the CI chain comes from `release.yml`'s
   `needs:`; the channels come from `project.conf`'s `CHANNELS`. The board
   holds no second copy of any of these — a number in two places is a number
   wrong in one.
5. **stdlib only, file-first.** The generator is a single Python script with
   no dependencies; the board is a single HTML file that works from `file://`
   with its data inlined. A `--serve` mode adds polling for the live case and
   nothing else.
6. **Escaped, not trusted.** Log tails, evidence strings and channel bodies are
   third-party text. The inlined JSON is escaped for `<`, `>` and `&` after
   `ensure_ascii` (the export-JSON gotcha in CLAUDE.md applies here verbatim).

## 1 · The feed

### 1.1 One helper, three consumers — `scripts/sink.sh`

```bash
# sink_line <kind> k=v …  — append one "@bn <kind> ts=… run=… k=v…" line to
# $BN_EVENT_SINK when it is set. No-op otherwise. Never fails the caller.
```

Ten lines. Values are `printf '%q'`-quoted exactly as `report.sh::_bn_emit`
does, so the sink file is **the `@bn` protocol itself with two fields added**
(`ts`, `run`), parseable by the existing `build_report.py::parse_event` —
no JSON escaping in bash, no second parser. Append with `>>`; a write failure
is swallowed (`2>/dev/null || true`), because a dashboard must never be the
reason a release step fails. Sourced by:

- `desktop/scripts/report.sh` — `_bn_emit` calls `sink_line` after its
  nested-child suppression check (the owner's events are the record; a silent
  child stays silent in the sink too). Every `@bn step/check/gate/art/done`
  from `build-all.sh`, `build-dmg.sh` and any `check-*.sh` that narrates then
  lands in the file with the run id.
- `scripts/check-release-ready.sh` — `ok/warn/bad` gain one line each:
  `sink_line row src=preflight label=… result=… evidence=…`. The 34 preflight
  rows become data.
- `scripts/verify-channels.sh` — `row()` gains
  `sink_line channel name=… verdict=… evidence=…`. Every probe run is recorded
  with its timestamp; "PyPI went green at T+34m" becomes answerable.

Two more emitters, one line each, for the clocks (§1.3):
`desktop/scripts/upload-testflight.sh` after `EXPIRES` is parsed
(`sink_line clock name=testflight build=… expires=…`), and
`desktop/scripts/build-dmg.sh` at manifest time
(`sink_line clock name=dmg built=… expires=…` — 30 days from the build, the
one clock we *do* compute, because Apple gives no date for a `.dmg`).

### 1.2 The run id and the sink path — `scripts/release.sh`

In `cmd_run`, once `RUNDIR` exists:

```bash
export BN_RUN_ID="$V" BN_EVENT_SINK="$RUNDIR/bn-events.log"
```

Children inherit both through `eval "$cmd"`. `ev_append` is untouched —
`events.jsonl` stays the conductor's ledger; the sink is the orchestra's.
A standalone `build-all.sh` (no `BN_RUN_ID`) writes nothing unless the caller
sets a sink, in which case `sink_line` mints `run=standalone-<epoch>`.

`release.sh` also gains a **`steps` verb** — `steps) run_steps ;;` — that prints
the step table (`id|label|kind|est|tier|consequence|cmd`) so the generator can
read the sequence from its source rather than carry a copy. Two lines.

### 1.3 What the feed captures that nothing did before

| Fact | Before | After |
|---|---|---|
| per-step build durations | measured, rendered, discarded | `@bn step … elapsed=` in the sink, per run |
| which gate `d2` last ran, and when | log archaeology | `@bn gate id=d2 … ts=` |
| preflight rows | terminal only | `@bn row src=preflight …` |
| channel verdicts over time | one rollup, exited | `@bn channel … ts=` per probe run |
| TestFlight expiry | printed once by altool | `@bn clock name=testflight expires=` |
| `.dmg` expiry | a banner string | `@bn clock name=dmg expires=` |
| a build joined to its release | impossible | `run=` on every line |

### 1.4 Proof — `scripts/test-sink.sh`

A fake script sources `report.sh` with `BN_EVENT_SINK` set to a temp file,
emits a step/check/gate/done sequence, and the suite asserts: four lines
landed; each parses with `parse_event`; `ts` and `run` are present; a value
containing spaces, quotes, a backslash and a `<` round-trips intact; **no sink
set → no file, exit 0**; an unwritable sink path → the script still exits 0.
Uses `test-lib.sh`. Wired into `ci.yml::release-suites` beside the other
`scripts/test-*.sh`.

## 2 · The generator — `scripts/release-board.py`

One file, argparse, stdlib. Reads; never probes, with one opt-in exception.

```
release-board.py [VERSION] [--out DIR] [--ci] [--serve PORT] [--json]
```

- **VERSION** defaults to the sole run under `.release/` (the same rule
  `release.sh` uses for `retry`/`abandon`); ambiguous → exit 2 naming them.
- **Inputs, in reading order:**
  1. `scripts/release.sh steps` → the sequence and each step's kind
     (`gate | plain | soft | hard`) and static estimate.
  2. `.release/<v>/events.jsonl` → fold per step to `ok | fail | running |
     pending`, using the same rule as `fold_status` (a `running` with no
     terminus is **stranded**, shown as such, never as running-green).
  3. `.release/<v>/heartbeat` → liveness: step, elapsed, last log line, and
     its age; older than `BN_HEARTBEAT_SECS` × 3 with a `running` step →
     stranded.
  4. `.release/<v>/bn-events.log` → the build steps with elapsed, the checks
     under step 1, the a–f gate battery, the artefacts, the preflight rows,
     the channel verdicts, the clocks. Parsed with `build_report.parse_event`
     (imported by path; the two scripts already live in the same tree).
  5. `.release/<v>/context.json`, `ci-sha` → the header (host, Xcode, sha).
  6. `.release/<v>/logs/<step>.<n>.log` → last 12 non-blank lines of the
     newest attempt of the running or failed step (CR → LF, as `release.sh`
     does). Never the whole log.
  7. `docs/testing/ratchet.json`, `soft-gates.json`, `gate-proofs.json` →
     the ratchet meters and the gate dispositions.
  8. `scripts/project.conf` → `CHANNELS`, `CHANNELS_UNPROBEABLE`, the
     endpoint templates (parsed as `KEY="value"` lines; `${VAR}` expansion
     for the derived URLs done in Python against the same file).
  9. `.github/workflows/release.yml` → job names and `needs:` (a 15-line
     YAML-shaped regex read, no PyYAML; asserted by a test against the real
     file so a workflow edit that breaks the read is red).
  10. **History**, for estimates: every `.release/*/bn-events.log` and
      `events.jsonl` on disk → per-step Welford mean/stddev over past runs,
      using `bristlenose/timing.py::WelfordStat` — the estimator the pipeline
      already has, applied to the build for the first time. Fewer than two
      samples → the static estimate from the step table, labelled *table*.
- **`--ci`** (opt-in, the one network call): `gh run list` for `ci.yml` on
  the `ci-sha` and for `release.yml` on the tag, `gh run view --json jobs` →
  the matrix and gate cells. `gh` missing or non-zero → the CI panel reads
  *unreachable*, dated; never empty-green.
- **Output:** `board.json` (the model, every panel a keyed object with a
  `source` and `as_of` on it) and `board.html` = the template with the JSON
  inlined in a `<script type="application/json">`, escaped. Written to
  `.release/<v>/` by default so the board travels with the run.
- **`--serve PORT`:** `http.server` on localhost, `GET /` regenerates and
  returns the page, `GET /board.json` regenerates and returns the model;
  the page polls `/board.json` every 5 s when served, never from `file://`.
  Localhost only, no auth, read-only, one process; the same shape as
  `serve --dev` mounting `docs/mockups/`.

**Exit codes**, the house vocabulary: `0` written · `1` run dir exists but
holds nothing renderable (says what is missing) · `2` usage / ambiguous
version.

### 2.1 Proof — `scripts/test-release-board.py`

stdlib `unittest`, run by `.venv/bin/python`. Fixtures are synthesised into
a temp `.release/x.y.z/`:

- **fold**: a run with `running` and no terminus renders `stranded`, not
  `running`; a failed step keeps its attempt count; a completed run is
  `completed`.
- **no data is not green**: an empty run dir yields a board whose every tile
  is `no data`, and the generator exits 1 naming the missing files.
- **channels**: every name in `CHANNELS` has a card; a channel in
  `CHANNELS_UNPROBEABLE` renders `skipped` with the reason; a probe line
  `unreachable` renders amber, never green.
- **topology**: the step order equals `release.sh steps` order; the
  `release.yml` reader returns the real file's jobs and `needs:` (asserted
  against the tree, so a workflow refactor that breaks the regex is red).
- **estimates**: two past runs → Welford mean shown with `n=2`; one → the
  table estimate labelled *table*.
- **escaping**: a log tail containing `</script><script>` lands in the HTML
  as `</script>`; the regression test from `export.py` copied in
  shape.
- **ci**: with `gh` stubbed to exit 1, the CI panel is `unreachable`; with
  a canned JSON, the matrix cells are placed by `(os, python)`.
- **`--serve`**: starts on port 0, `GET /board.json` returns the model with
  `Content-Type: application/json`, stops.

## 3 · The board — `scripts/release-board/board.html`

One file: CSS, a `<template>`, and ~300 lines of JS that render `board.json`.
No framework, no CDN — it must open from `file://` on a machine with no
network in the middle of a release. Hand-rolled tokens; this is maintainer
tooling, not a product surface, so the bn-accurate recipe is deliberately not
used (recorded so nobody "fixes" it later).

### 3.1 Layout — the Tube map

```
┌ header: version · run id · started · phase pill row · liveness ─────────────┐
├ the line: 12 stations from `release.sh steps`, left→right, interchange     ┤
│   glyphs for gate/soft/hard, coloured by fold state, ▶ at the running one   │
├──────────────────────────┬─ ┆ irreversible ┆ ─┬───────────────────────────┤
│ BUILD (left column)      │                     │ RELEASE (right column)     │
│  preflight chips 34      │                     │  tag preconditions         │
│  build steps + elapsed   │                     │  channel cards ×8, two     │
│    ↳ checks · gates a–f  │                     │   columns, CHANNELS order  │
│  CI chain (release.yml   │                     │   each: trigger · live ·   │
│   needs) + matrix cells  │                     │   probe history · clock    │
│  ratchets ×5             │                     │  verify rollup             │
├──────────────────────────┴─────────────────────┴───────────────────────────┤
│ events tail (both ledgers merged by ts) │ heartbeat + activity per minute  │
└───────────────────────────────────────────────────────────────────────────┘
```

The **line** is the sequence-and-dependency spine the sketch lacked: the
twelve steps as stations, a thicker ring at `gate` steps, a black bar at the
`hard` (tag) step, a half-ring at `soft` ones; below it a second, thinner
line for the `release.yml` chain drawn from `needs:` (ci → build → publish →
{github-release, verify-pypi → trigger-copr, notify-homebrew}), which is the
only fan-out in the system and the reason a Tube map is the right metaphor.
Clicking a station scrolls its pane into view.

### 3.2 Panes

- `resize: vertical; overflow: auto` on every pane — native, no JS; default
  height is content-sized with a max, so a healthy board needs no scrollbars
  and a busy one gets them inside the pane, not on the page. Pane heights
  persist in `localStorage` (wrapped in try/catch; the page renders without
  it).
- **State vocabulary, one set:** `ok · warn · fail · running · pending ·
  skipped · unreachable · stranded · no-data`. Colour carries only the first
  five; the last four are outlined or hatched, never filled — the same
  discipline as `REPORT-STYLE.md`'s probes.
- **Effort without a time axis:** each build step shows its elapsed as a
  proportion of the run's longest step, and its estimate as a hatched
  extension; the activity strip is events-per-minute across both ledgers. That
  is the "activity and effort" of the ask, delivered without geography.
- **Scrolling areas:** the events tail, the failed step's log tail, a channel
  card's probe history, the preflight evidence column. Each is a pane.
- **No data** is rendered as a labelled empty tile ("no bn-events.log — the
  build has not run under this release"), never as a blank.

### 3.3 Live mode

Under `--serve`, the page fetches `/board.json` every 5 s, diffs by `as_of`
per panel, and re-renders only panels whose `as_of` moved. A pane the user
has resized keeps its size. The heartbeat's age drives the header's
liveness pill (green under 2× `BN_HEARTBEAT_SECS`, amber to 3×, red beyond
with "stranded?"). From `file://` the page is a snapshot and says so in the
header.

## 4 · Sequence, and what proves each step

| # | step | proof |
|---|---|---|
| 1 | `scripts/sink.sh` + `report.sh` tee + `release.sh` exports and `steps` verb | `test-sink.sh` green; `release.sh steps` prints 12 rows; a `check-*.sh` run with a sink set writes lines |
| 2 | preflight rows, channel rows and the two clocks emit to the sink | `check-release-ready.sh` with a sink set writes ≥30 `row` lines; `verify-channels.sh` writes 8 `channel` lines (network needed for real verdicts; `unreachable` is fine) |
| 3 | generator reads the real `.release/0.29.1` (events, context, logs) and renders a board with the build panes at *no data* | `release-board.py 0.29.1` writes `board.html`; opened, the twelve stations show 0.29.1's real fold; build panes say *no data* honestly |
| 4 | generator unit suite | `test-release-board.py` green |
| 5 | board template — layout, line, panes, states, escaping | a synthetic full run (fixture from the suite) renders every pane populated; the sketch's screenshot compared by eye |
| 6 | `--serve` + polling | `curl localhost:PORT/board.json` returns the model; the page re-renders a changed panel |
| 7 | a real feed: `build-all.sh` run under a sink (ad-hoc signing path stops at step 2d — enough to prove step/check/gate lines and elapsed) | `bn-events.log` holds real `@bn` lines; the board's build pane fills |
| 8 | docs: `scripts/README.md` rows, `docs/release-channels.md` "watching it" paragraph, `REPORT-STYLE.md` sink paragraph, mockup register → IMPLEMENTED, this doc trued to as-built | `check-mockup-register.py` green; `check-doc-surfaces` untouched (no CLI flag changes) |

Steps 1–2 ship as one commit (the feed), 3–6 as one or two (the board),
7–8 close it out. Nothing here is release-gating, so no ratchet or gate-proof
entry is needed; the two suites join `release-suites` so they run where the
rest of the release machine's proofs run.

## 5 · Out of scope, by decision

- **History overlay** (past runs on the board): the feed makes it possible;
  the board shows only the estimate it derives from history. The Marey
  sketch stays a sketch.
- **Probing from the board**: the board never calls PyPI, ASC or the store.
  `release.sh verify` does, and writes the sink. One place asks the network.
- **A SwiftUI window, a FastAPI mount, SSE**: rejected in the options doc;
  `--serve` is `http.server` and stays that.
- **The bn-accurate design system**: not for maintainer tooling.
- **Any change to what a step does.** If a step's behaviour has to change to
  be visible, the plan is wrong, not the step.

## 6 · Risks the review should look at

1. `report.sh` is "3.2-safe bash"; the sink helper must stay so (no
   associative arrays, no `${var,,}`), and must not break `bn_autowrap`'s
   re-exec (the sink is written by the *inner* run, which is the owner).
2. The `release.yml` regex reader is the one place topology is read from a
   file not designed to be read; the test against the real file is what keeps
   it honest, and it must fail loud on a shape it does not understand rather
   than return a partial chain.
3. `--serve` regenerates on every poll: reading every `.release/*/bn-events.log`
   for history each time is wasteful; cache by mtime.
4. The log tail is untrusted text from tools (rsync, altool, notarytool); the
   escaping test is the guard, and the tail is capped at 12 lines × 200 chars.
5. Two ledgers (`events.jsonl`, `bn-events.log`) merged by timestamp: both are
   UTC ISO-8601 already; the sink must write the same format or the merge
   silently misorders.
