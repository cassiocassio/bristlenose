---
status: proposed — options, not a decision
date: 2026-09-05
owner: maintainer
sketches: docs/mockups/release-train-{marey,board,scroll}.html
---

# A watching GUI for the release train — options and prior art

The ask (5 Sep 2026): *see the whole end-to-end build and release train at
once — phases, stages, sub-steps, gates, test runs, platforms, publish
channels — done, doing and to-do, activity and effort, success and failure,
dense and elegant, ideally on one 16" MacBook Pro screen, time running down,
build on the left and the release platforms on the right.*

This document does three things and decides nothing: it says what the train
already emits (so the dashboard is fed by facts, not by a second model of the
train), it surveys the prior art for this kind of picture, and it puts three
sketches side by side with the trade each one makes. The two research passes
it condenses ran on 5 Sep 2026; the sketches are loose mockups, hand-rolled
tokens, real stage names, shaped fake data.

## 1 · What the train emits today — and the one seam that is missing

There are **three orchestrators and they do not share a run id.**

| Orchestrator | Steps | Structured output | Where it goes |
|---|---|---|---|
| `scripts/release.sh` (the conductor) | 12: preflight · bump · push-main · strict-ci · build-all · build-dmg · ci-green · testflight · dmg · **tag** · snap · snap-stable | `.release/<version>/events.jsonl` — `{"ts","run","step","status","detail"}`, append-only, state is folded on read | durable |
| `desktop/scripts/build-all.sh` (App Store lane) | 1 · 1c · 2 · 2a · 2b · 2c · 2d · 5 · 6 · 7 · 8 · 9, then gates a–f | the `@bn` protocol: `@bn step id= phase= name= status=start\|ok\|skip\|fail elapsed= detail=`, plus `@bn check`, `@bn gate`, `@bn art`, `@bn done` | **stdout only** |
| `desktop/scripts/build-dmg.sh` (Developer-ID lane) | 1 · 1b · 2 · 3 · 4 · 5 · 6 · 8 · 9 · 10 | same `@bn` protocol | **stdout only** |

`release.sh` runs the two build scripts as opaque commands and captures their
stdout to `.release/<v>/logs/<step>.<n>.log` — so the `@bn` structure is
**flattened to rendered text at the boundary**. Every per-step `elapsed=` is
measured, emitted, rendered by `build_report.py` and then discarded; the only
durations that survive are `release.sh`'s twelve outer numbers, as strings in
`detail` (`"27s"`). The step estimates are a static column, hand-measured from
one release, and nothing feeds actuals back — while `bristlenose/timing.py`
already implements the Welford estimator this needs, for the pipeline rather
than the build.

The rest of the signal, for completeness (the full inventory with file:line
receipts is in the 5 Sep research pass; this is the shape):

- **Gates.** ~30 `check-*.{sh,py}` scripts, each with a stated hard / soft /
  warn / ratchet / conditional disposition; `docs/testing/gate-proofs.json`
  records when each was last *seen* to fail; `ratchet.json` holds five numbers
  that may not rise; `soft-gates.json` gives every `continue-on-error` an
  expiry or a ratchet. Step 1's seven `bn_check` leaves and the a–f gate
  battery are display-only — no record of when gate `d2` last ran.
- **CI.** Eleven workflows; `release.yml` is `ci → build → publish → {github-release,
  verify-pypi → trigger-copr, notify-homebrew}`; strict macOS is conditional
  (soft on push, hard under `strict-macos: true`); the `publish gate` preflight
  row parses the YAML and fails if that chain ever breaks.
- **Channels.** Eight, in `project.conf`: pypi · github · homebrew · testflight ·
  dmg · snap · copr · website, each with a `probe_<name>` that returns
  `ok | bad | unreachable` (tri-state on purpose: `curl` returning `000` is not
  "absent"). `verify-channels.sh` prints one rollup and exits; nothing stores
  the eight verdicts, so "PyPI went green at T+34m" has no record.
- **Clocks.** TestFlight 90 days from the *upload* (read Apple's
  `EXPIRATION-DATE`, never compute it); `.dmg` 30 days from the *build*; the Copr
  token 23 Feb 2027; Apple certificates. None is written anywhere a process
  could read — the single most dashboard-shaped fact in the system lives in a
  banner string.
- **Liveness.** `.release/<v>/heartbeat` — one overwritten line, `epoch step
  elapsed last-log-line`; a heartbeat that stopped *is* the stranded case.
- **Exit codes as vocabulary.** `0` ready · `1` failed or not on this version ·
  `2` usage or lock held · `3` stranded · `75` every act done, verification
  pending.
- **Sibling series already in the house pattern.** `pipeline-events.jsonl`
  (runtime, schema v1, append-only, the SPA's source of truth),
  `.claude/workflow-log.jsonl`, `.claude/audit-log.jsonl`,
  `e2e/.perf-history.jsonl`, `docs/testing/inventory.json` (generated; already
  the closest thing to a feed: suites × where-they-run × counts).

**The highest-leverage single change is not a GUI.** It is a `BN_EVENT_SINK`
tee in `report.sh::_bn_emit` (about four lines) plus a run-id environment
variable that `release.sh` exports and every `@bn` line carries. That turns
`build-all.sh`, `build-dmg.sh` and all the `check-*` gates from "prints a pretty
report" into one durable, joinable event stream — without touching a step's
logic, because the report is already *a view, not the control flow*
(`REPORT-STYLE.md`). Whatever picture is chosen below is drawn from that file.
Without it, every option is a picture of `release.sh`'s twelve rows and a wall
of text.

## 2 · Prior art — what exists, and what does not

Nobody ships the picture as asked. Vertical time is native in exactly three
families (Marey, Treeherder's stacked pushes, and the log-anchored deploy
lists); effort is encoded in the trace/waterfall family, which is horizontal in
every implementation; structure (fan-in, fan-out, gates) lives in the DAG
family, which has no time at all. The ask is a composition: **a platform × stage
grid whose cells are vertical bars proportional to duration, stacked down the
page in phase order, with the publish channels as the right-hand column group.**

| Archetype | Exemplars | Uniquely good at | Fails at |
|---|---|---|---|
| **Marey train chart** — stations across, time down, one line per run | Ibry/Marey Paris–Lyon timetable (Tufte, *VDQI*); borgar's d3 recreation; Caltrain visual schedule | Overlaying *many releases* so habitual stalls show as geometry; effort is the slope; a flat run is a healthy train | A fan-out to eight channels breaks the linear station order; failure is a bolted-on mark; empty on a first run |
| **Treeherder letter matrix** — rows = platforms, cells = job glyphs, colour = state, pushes stacked down | Mozilla Treeherder; Debian buildd; Koji child tasks | Hundreds of cells in 150 px; instant red/orange/green scan; time-down by stacking | Effort invisible — a 4-hour job and a 40-second job are the same glyph; needs a learned vocabulary |
| **Flow DAG** — resources → jobs → channels | Concourse; GoCD Value Stream Map (the only one that treats *a commit's journey* across pipelines as the unit, upstream left, downstream right); GitHub Actions graph; Argo (vertical) | Structure: gates, fan-in, fan-out, what triggers what, one screen | No time, no history; horizontal in all but Argo |
| **Waterfall with swimlanes** — nested rows, bars by duration segmented wait/run/state | Buildkite waterfall (grey wait · yellow assigned · green/red run, matrix children nested); Jaeger span tree; Perfetto tracks; Gradle build-scan timeline (executed / cached / up-to-date); Xcode Build Timeline | Effort, waiting versus doing, critical path, sub-step nesting | Horizontal everywhere; one run per view; a 30-minute step dwarfs a 2-second gate into a sliver |
| **Status wall of small multiples** — tiles, each a pill plus a history strip | Statuspage component grid; Grafana state-timeline (merged state bands) and status-history; NASA lamp wall; Nomad's per-row proportion bar | "Is everything green?" in one second; per-tile trend | Loses ordering and dependency; equal weight for unequal things |
| **Log-anchored vertical list** — newest first, one row per event, expand to log | Heroku activity; Vercel deployments; Netlify deploy; GitHub Actions job page | Zero learning; scroll = time; the log is right there | A serial view of a parallel process; no picture of the whole |

Two borrowings worth naming regardless of layout. **Bertin's reorderable
matrix**: sort rows and columns so failures cluster — group the macOS cells so a
strict-macOS regression is one red block, not four scattered ones. **Buildkite's
tri-segment bar**: waiting for an agent, assigned, running — the release train's
equivalent is *waiting for the 21:00 window*, *waiting for ASC processing*,
*running*, and those three should not be one colour.

Substrates, in order of fit: (1) **static HTML plus the JSONL the scripts
write** — no server, survives as an artefact beside the release, reads via an
inlined `<script type="application/json">` so it opens from `file://`; polling
the file gives "doing". (2) A tiny FastAPI + SSE page — animates the live
state, but adds a running process during the one hour you want fewest moving
parts. (3) Rich/Textual `Live` in the same terminal as `release.sh` — the
split-flap archetype, natural for a 30-row wall, crude for proportional bars;
the TTY-versus-pipe gotcha applies. (4) A SwiftUI window — only if the viewer
should live inside the app, which it should not: the train is a maintainer
tool, and a Swift build in the release path is the wrong dependency direction.

Components: **Observable Plot** is the one Gantt-capable library indifferent to
which axis carries time (`barY` with `y1/y2` is the vertical Gantt in fifteen
lines); the d3 Marey gist's station/train JSON is a ready model for stations =
gates, trains = releases; **Perfetto** opens Chrome trace JSON natively, so if
the event sink writes `{"ph":"X","ts","dur","pid":phase,"tid":platform}` the
*same file* gives the horizontal deep-dive for free — but only via HTTPS or
`postMessage`, never `file://`, so it is the companion, not the host.
vis-timeline and Mermaid gantt are horizontal-only and fight a dense design.

## 3 · Three sketches

All three use the real stage names and a plausible run of `v0.30.0`. Open them
from `docs/mockups/`; `serve --dev` lists them under About ▸ Design.

### A · `release-train-marey.html` — the train chart

Stations left to right in eight groups (plan · build · upload · gate ·
**irreversible** · publish · by hand · verify), time down, one polyline per
release: two past releases in grey, the live run in blue with a dashed "now"
line, a failed-and-retried leg dashed red, waiting rendered as a vertical
segment with an amber band. The right margin is the lifespan column: `.dmg`,
TestFlight, tokens, certificates as small bars.

- **Wins.** History and the present in one picture; the slope *is* the effort;
  you can see that ASC processing and the tag window are where every train
  dwells; the irreversible line is a real vertical rule you cross once.
- **Costs.** Fifty-one stations is a lot of x; the eight channels are drawn as
  serial stations when they are really parallel, and nothing in the form says
  "these four ran at once". State is a dot on a line, so a red at station 40
  is small. Needs at least one past run to mean anything.
- **Fits the ask on:** time down, build left, channels right, dense, elegant,
  effort. Weak on: to-do (only a dotted tail), test matrices (one station).

### B · `release-train-board.html` — the fixed 16" board

One screen, 1728 × 1117, no scrolling. Left column: the 34 preflight rows as
a chip grid, the eleven build steps with elapsed bars and Welford estimates
for the unrun ones, the CI matrix (os × python) with the nine gates beneath,
the five ratchet meters. A dashed red divider labelled *irreversible*. Right
column: the tag's preconditions, then the eight channels as cards in two
columns filling top-left to bottom-right (TestFlight processing first, Website
last), each with its trigger, live version, expected latency, tri-state probe
squares and its lifespan bar. Bottom strip: the events tail and a per-minute
activity sparkline.

- **Wins.** Everything on one screen, exactly the "big board"; done / doing /
  to-do is a colour per element; test matrices and gates are first-class; the
  channel cards carry the facts a release actually waits on (CDN cache, SRPM
  arch, ASC propagation window). The activity strip is the only place *effort*
  appears in this sketch, and it is enough to tell a stalled run from a busy
  one.
- **Costs.** Time is not an axis at all — a state wall, not a timeline; history
  is a number in a corner. It is the Treeherder failure mode: a 30-minute
  notarisation and a 1-second manpage check are the same size chip. And it is
  honest about the empty space: at this density a 16" screen has room to
  spare, which argues for either richer per-cell content or a smaller window.
- **Fits the ask on:** one screen, grid of grids, build left / platforms right,
  done-doing-to-do, gates and test runs. Weak on: time down, effort.

### C · `release-train-scroll.html` — the long page

Time down and **to scale** (1 px = 6 s), lanes across by architecture chunk
(plan · python · sidecar · mac app · ci · **tag** · pypi chain · packagers ·
apple · events), every bar anchored to the event line in the right-hand lane
that emitted it. The sticky header keeps the lane names; waiting is a hatched
bar; the future is dashed outlines; the page is as long as the release took.

- **Wins.** The only sketch where a gap *means* something — an empty hour in
  every lane is an hour nobody spent, which is the effort view the ask names.
  Sub-steps nest naturally as narrower bars; parallel work is visibly parallel;
  the event lane makes it log-anchored, so any bar is one glance from its
  evidence. It is the Buildkite waterfall rotated, which nobody ships.
- **Costs.** Not one screen: a four-hour release is 2 400 px tall, so the whole
  train needs a minimap or a zoom. Long waits (the 66-minute tag window) are
  huge and empty; short gates are slivers. The right-hand channels are mostly
  to-do until the last twenty minutes, which is true and looks unbalanced.
- **Fits the ask on:** time down, activity and effort, build left / publish
  right, done-doing-to-do, the "animation" reading (scroll is time travel).
  Weak on: one screen, matrices (a cluster of cells in a lane is workable but
  small).

### The composition the sketches point at

B is what you glance at; C is what you read when something is wrong; A is
what you look at once a month to see where the train habitually stalls. They
are not rivals so much as zoom levels over one event stream, which is the
argument for §1's sink before any of them: A needs history, C needs
per-step timestamps, B needs live probes, and none of that exists as data
today. If only one is built first, **C with a B-style summary bar pinned to
the top** covers the most of the ask, because the to-scale vertical axis is
the thing no existing tool provides and the summary bar is cheap.

## 4 · Open questions — the user's, not mine

1. **Sink first?** The four-line `BN_EVENT_SINK` + run-id change is worth doing
   even if no GUI follows; it also answers "which build step got slower this
   month", which is unanswerable today. Is it in scope for the next release or
   a separate chore?
2. **Chrome trace shape or house shape?** Writing the sink in Chrome trace
   event JSON buys Perfetto as a free deep-dive; writing it in the
   `pipeline-events.jsonl` house shape buys consistency with the runtime
   events the SPA already reads. They can be the same file with two
   projections, at the cost of a converter.
3. **Where does it live?** Beside the release (`.release/<v>/index.html`, a
   file the maintainer opens), or served (`bristlenose serve --dev` already
   auto-discovers mockups; a `/release/` mount is a small step), or as a
   published artifact after each release, which is the only form a second
   person could ever see.
4. **Who is it for, on the day?** One person, at 9pm, mid-release, wants
   "what is it waiting on and how long". A month later the same person wants
   "which step got slower". Those are B and A; they may not want to share a
   screen.
5. **The clocks.** Regardless of the picture, TestFlight's expiry, the
   `.dmg`'s 30 days, the Copr token and the certificates should be written
   somewhere a script can read and warn at T-7. This is the smallest,
   highest-value tile on any of the three sketches and needs no GUI to be
   useful.

## 5 · What was not done

No code. The sketches are static, fed by hand-shaped data, and use hand-rolled
tokens rather than the design system (they are maintainer tooling, not a
product surface, so the bn-accurate recipe was deliberately skipped). No
component was evaluated by running it. The research pass looked at vendor
documentation and known layouts; it did not fetch screenshots, so "dense" and
"elegant" above are judgements about form, not measured pixels.
