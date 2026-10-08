---
status: built 5 Sep 2026 — feed, generator, template and suites on main; as-built notes at the end
date: 2026-09-05
decides: docs/design-release-train-dashboard.md § 3 → sketch B, the board
sketch: docs/mockups/release-train-board.html
review log: the maintainer's private review notes, kept outside the public tree (33 findings with dispositions)
---

# The release board — build plan (v2)

**Decision (5 Sep 2026): build the board, not the timeline.** The maintainer's
framing: this is the London Underground map, not the Ordnance Survey — the
connections and the logic of the journey, sequence, dependencies, pass and
fail, the qualitative state. A time axis makes the picture less useful. The
board has a flow (top-left to bottom-right), room for scrolling detail inside
panes, and panes that size to content or resize.

**v2 differs from v1 in what it deletes.** The plan review found v1 breaking
its own principle 4 ("no second copy") four times — a regex reader of
`release.yml`, a `--ci` flag calling GitHub from the viewer, a `steps` verb the
generator would depend on, a channel count written into prose — each a
re-reading of a source that already has a correct reader. All four are gone.
It also found the feed could be silently empty in four measured ways; all four
are closed in the feed commit. And it deleted live mode: the one person who
will ever watch this can type `while sleep 5; do …; done` and press ⌘R.

> _Reversed later the same day — see §8._ `--serve` shipped in `bce36c78`: a
> loopback server behind a per-run token, patching pane by pane. The reasoning
> above is preserved because it is why the **snapshot is still the default** and
> why the server is opt-in (`release.sh run --board`), self-exiting and
> loopback-only rather than a dashboard anyone maintains.

Two halves, in order: **the feed** (make the train write down what it already
knows) and **the board** (draw it). The feed is worth having with no board.

## 0 · Principles

1. **Read, never derive.** Every state comes from a file a script wrote. Where
   nothing was written the tile says *no data* — a third state. And "no data"
   itself is read, not inferred: the driver writes its own boundary lines into
   the sink, so an empty sink under a completed step is *"ran; sink received
   nothing"*, never *"did not run"*.
2. **The report is a view; so is the board.** No step's control flow changes.
3. **One run id joins everything**; attempts ride on the driver's boundary
   lines, not on a forked id.
4. **Topology from the run.** The step table is snapshotted into the run dir
   at start; the channels come from `project.conf`; the CI chain's *verdict*
   comes from the preflight row that already parses the YAML properly. The
   board holds no number that lives in a tracked file.
5. **One parser.** The sink is the `@bn` protocol with `ts` and `run` added;
   `parse_event` moves to a stdlib module both readers import.
6. **Nothing here ships in the `.app`.** Maintainer tooling; the sandbox rules
   do not apply, and the bn-accurate design recipe is deliberately not used.
7. **What leaves the machine.** `board.html` carries no credentials, no host
   identity and no raw tool output, by construction and by test; it is safe to
   attach to an issue. `board-with-logs.html` is not, and says so in its header.

## 1 · The feed

### 1.1 `desktop/scripts/sink.sh` — one helper, six production consumers

```bash
# sink_line <kind> k=v …  — append "@bn <kind> ts=<UTC> run=<id> k=v…" to
# $BN_EVENT_SINK. No-op unless the sink is set and absolute. Never fails the
# caller. bash 3.2 safe.
```

- **Normalise before quoting** (the measured defect): each value has control
  bytes stripped (`tr -d '\000-\037'` after CR/LF/TAB → space) and is cut to
  200 bytes, then `printf '%q'`. That keeps `shlex` able to read every line, and
  keeps a value from forging a second `@bn` line.

- **It does NOT make a line atomic, and the sink says so at its own contract
  block.** `sink.sh:26-31`: *"bash's printf to a file is stdio-buffered at 1 KB,
  and `%q` can expand a non-ASCII value fourfold, so two writers (a `status`
  during a `run`) can splice a long line — the parser then counts it as unparsed
  rather than reading half of it."* The 200-byte cap is about forgery, not
  interleaving. _(This bullet claimed the cap "keeps every line under `PIPE_BUF`
  so concurrent appenders cannot interleave". Corrected 20 Sep 2026 — a reader
  would have designed against a guarantee the implementation disclaims, and the
  mitigation that does exist is the parser counting what it cannot read.)_

- **`LC_ALL=C` is load-bearing, not noise.** `sink.sh:32-36`: under a UTF-8
  locale BSD `tr`/`cut` abort on the first invalid byte, the assignment fails,
  and a `set -e` caller — every build script — would **die inside the sink**.
  Recorded at the point of the choice so nobody drops it while tidying.
- `ts` is `date -u +%Y-%m-%dT%H:%M:%SZ`, written by `sink_line` itself, so a
  child cannot write local time into the merge.
- `run` is `$BN_RUN_ID`, or `standalone-<epoch>` when a sink is set by hand.
- Writes happen under `umask 077`. A write failure is swallowed
  (`2>/dev/null || true`): a dashboard must never fail a release step.
- Lives next to `report.sh` (the desktop half is the publisher of the
  protocol); the `scripts/*.sh` consumers source it with an existence guard.

Consumers:

- **`report.sh::_bn_emit`** — the tee sits after the nested-child guard and
  before the `BN_REPORT=0` branch, so plain mode records too. **Ownership is
  claimed once:** every early-return branch of `bn_autowrap` taken by a
  *standalone* run (no `_BN_ACTIVE` at entry) sets `_bn_owner=1` and exports
  `_BN_ACTIVE=1`, so rendering and recording share one token in every mode.
  This changes what nested children print under `BN_REPORT=0` (they go
  silent, as they already do under the renderer); the test pins it.
- **`scripts/check-release-ready.sh`** — `ok/warn/bad` gain
  `sink_line row src=preflight label=… result=… evidence=…`.
- **`scripts/verify-channels.sh`** — `row()` gains
  `sink_line row src=verify label=… result=… evidence=…` for every row, plus
  `sink_line verify status=start` at entry and `status=done rollup=<rc>
  channels=<n>` at the end, so a partial verify is never rolled up as complete.
- **`desktop/scripts/upload-testflight.sh`** — after `EXPIRES` is parsed:
  `sink_line clock name=testflight build=… expires=…` (empty when altool gave
  none — the board renders that as no-data, never a computed date).
- **`desktop/scripts/build-dmg.sh`** — at manifest time:
  `sink_line clock name=dmg built=<UTC>`; the 30-day rule stays in one place
  (`AlphaBuild.swift`), mirrored in the generator with a parity test.

### 1.2 `scripts/release.sh` — the conductor writes its own boundaries

- `cmd_run`, once `RUNDIR` exists: `export BN_RUN_ID="$V"
  BN_EVENT_SINK="$ROOT/$RUNDIR/bn-events.log"` (absolute), and
  `run_steps > "$RUNDIR/steps.tbl"` — the topology snapshot the board reads.
- `sink_line run status=start attempt=<n>` at entry (n = count of prior
  `run started` lines + 1), and `sink_line step id=<step> attempt=<n>
  status=start|end rc=<rc>` around every step — **these writes are asserted**
  (`|| die`), like `ev_append`. Children swallow; the driver does not.
- A shared `resolve_run` helper (the rule `retry`/`abandon` already use, plus
  "newest by mtime when several, narrated") is used by `verify` and `status`
  to export the same two variables when a run dir exists — so post-release
  `release.sh verify 0.29.1` and `release.sh status` write channel and CI
  lines into the run's sink.
- `cmd_status` writes `sink_line ci …` lines from the same `gh` selector
  `CI_CMD` uses (`--event workflow_dispatch --branch main`, `headSha ==
  ci-sha`) — the one place that asks GitHub — with `queued`, `no run for sha`
  and `unreachable` as distinct results.

### 1.3 Proof — `scripts/test-sink.sh` (bash, `test-lib.sh`)

A fake script sources `report.sh` with a temp sink and emits step/check/gate/
done. Asserts: four lines; each parses via `bn_events.parse_event`; `ts` ends
in `Z`; `run` present; values with spaces, quotes, backslash, `<` round-trip;
**a value with a newline and an apostrophe, a tab, and a non-ASCII string under
`LC_ALL=C`** round-trip post-normalisation and parse; a 500-byte value is
capped; no sink → no file, exit 0; unwritable sink → exit 0; **relative sink
→ no write**; `BN_REPORT=0` + sink → lines land once (parent) and a nested
child writes nothing; a `cd /tmp` before emitting still lands in the absolute
path; `sink.sh` and `report.sh` contain none of `declare -A`, `${var,,}`,
`mapfile`. Wired into `ci.yml::release-suites` by name.

## 2 · The generator — `scripts/release-board.py`

`.venv/bin/python scripts/release-board.py [VERSION] [--out DIR] [--with-logs]`.
Stdlib plus one import by path (`desktop/scripts/bn_events.py`). Reads; never
probes; makes no network call.

Inputs, and each pane's **no-data condition**:

| Pane | Source | No data when |
|---|---|---|
| header | `context.json` allowlist (`os arch xcode python disk_free_gb git`), `ci-sha` | file absent (0.28.0 has none) — header shows version and started only |
| the line | `steps.tbl` + `events.jsonl` folded | `steps.tbl` absent → ledger order, confounded log not computable; unparseable lines counted and shown; a partial trailing line **naming a step** folds that step to `corrupt`, as `release.sh` does |
| liveness | `.lock/pid` + `os.kill(pid,0)`; heartbeat as a fact | no lock and no `running` → "not running"; lock + dead pid → stranded; empty heartbeat → "mid-write" |
| preflight | sink `row src=preflight` | no rows → no-data; rows present → N of them, never a rollup the file did not make |
| build steps / checks / gates / art | sink `@bn step/check/gate/art` inside the driver's window for each lane whose command is a `desktop/scripts/build-*.sh` (read from `steps.tbl`) | no boundary → not-run / skipped / failed-no-window by the ledger; boundary present, zero child lines → "ran, no @bn lines" — counted as *missing* only when that script emitted on this or the previous run (`build-dmg.sh` never has; a permanent entry would be the gate that cries wolf) |
| CI | sink `ci` lines from `status` | none → "not queried (run `release.sh status`)" |
| ratchets | `ratchet.json` | ceilings only: "ceiling N · current not measured" |
| tag | `ci-sha` + the tag step's fold | as the line |
| channels | `CHANNELS` from `project.conf` × newest complete verify's rows | no verify → no-data; verify without `done` → "partial, N of M"; a verify whose `version=` is not this run's → rows withheld and said (a bare `release.sh verify` probes the tree's version); `unreachable` amber never green; `as_of` is the batch's newest stamp |
| clocks | sink `clock` | none → no-data; empty `expires` → no-data |
| events | both ledgers merged `(ts, source_rank, line_index)`, conductor wins | — |
| failed step | log **path** and exit code only; `--with-logs` adds a 12×200 tail with CSI/control bytes stripped, in `board-with-logs.html` **and** `board-with-logs.json` — `board.json` is never overwritten with tails | — |

Every sink string is scrubbed at the door (`scrub()`): signing-identity common
names collapse to their kind, ten-character team ids after "Team" to `<team>`,
and the home directory to `~`. `context.json` is allowlisted; the sink is the
other door, and `bn_meta identity=` / `bn_art signed=` walk through it. Output
files are 0600 and written `O_NOFOLLOW`.

**The confounded-expectations log** (added 5 Sep 2026 after the drift
review). The board's drift guard is one pane, always present, with its count in
the header — including *0 confounded* as a positive statement, and *cannot be
computed* when `steps.tbl` is missing. Four sections: **unknown** (seen in the
feed, not in the board's vocabulary — a kind, a field, a status word; rendered
raw, counted, never dropped); **new shape** (a known thing carrying a value the
board has no rule for); **missing** (declared by the run, never seen — a
channel in `CHANNELS` with no row after a `done` verify, a step in `steps.tbl`
with no event on a completed run, a driver window with zero child lines, the
preflight label the CI tile keys on absent from a complete preflight); and
**changed since last run** (this run's `steps.tbl` and channel set diffed
against the previous run dir's — an added phase, a deleted platform, a rename).
A fixture with one of each proves the log can fail. What it cannot see is a
semantic disagreement between the ledger's fold and the board's; the
round-trip test below is that guard. Version stamps: `steps.tbl` starts with
`# steps.tbl v1`, and the driver's `run` line carries `proto=1`.

Fold vocabulary: `ok · fail · running · pending · skipped · corrupt · stranded
· later (tier 2) · unknown (id not in steps.tbl) · not-in-this-run (completed
run, no event)`. Only `\n`-terminated lines are complete; a fragment naming a
step folds it to `corrupt`, as `release.sh`'s awk does, so the two never
disagree on one file.

`as_of` per pane = the newest source mtime; the header prints generated time
and newest source. Estimates are the step table's `est` column, labelled
*table* (Welford deferred — review-log Finding 22). VERSION is validated
(`\d+\.\d+\.\d+[\w.+-]*`) and resolved under `ROOT/.release`. Exit `0` when a
board was written, `1` when the run dir or **`events.jsonl`** is missing, `2`
usage. **A missing `steps.tbl` is not an error** — the board falls back to
ledger order, says so, and exits `0` (`release-board.py:1592-1600`; pinned by
`test-release-board.py::test_no_steps_tbl_falls_back_to_ledger_order_and_says_so`).
That matters because every run on disk today — 0.28.0, 0.29.0, 0.29.1 — predates
`steps.tbl` and would otherwise be undrawable. _(§7 corrected this in prose and
left §2 and §2.1 standing; trued here 20 Sep 2026.)_

Output: `board.json` and `board.html` (the template with the JSON inlined,
`ensure_ascii` then `< > &` escaped) into `.release/<v>/`, mode 0600.

### 2.1 Proof — `scripts/test-release-board.py` (unittest, `.venv/bin/python`)

Synthetic run dirs under a temp `.release/`: fold (stranded vs running via a
dead pid; `corrupt` from a fragment; `skipped`; `later`; `unknown`;
`not-in-this-run`); no data is not green (an empty run dir with `steps.tbl`
renders every tile no-data, exit 0; without `steps.tbl`, ledger-order fallback
and still exit 0); build
"ran, sink received nothing" vs "not run"; channels from `CHANNELS`
(`unreachable` never green; partial verify never rolled up); clocks (empty
expires → no-data; dmg expiry parity with `AlphaBuild.swift`); merge order on
same-second ties; **escaping** (`</script><script>` in evidence → `<`
present and literal `</script>` exactly once); **round-trip** (extract the
inlined block with `html.parser`, `json.loads` it, equal to `board.json`);
**CANARY** (`context.json` with `"host":"CANARY"` and a canary env value →
absent from `board.html`); **DOM sinks** (the template contains none of
`innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write`, matched on
whole tokens); a fixture copied from the real `0.28.0` run (fail, retry, skip,
resume, no `context.json`) asserting every tile by name. Wired into
`ci.yml::release-suites` on its own Python line.

## 3 · The board — `scripts/release-board.template.html`

One file, no framework, no CDN, opens from `file://`. Hand-rolled tokens (§0.6).

```
┌ header: version · run · started (first run started, n attempts) · generated · newest source · liveness ┐
├ the line: stations from steps.tbl, interchange glyphs for gate/soft/hard, ▶ at running, · at later   ┤
├──────────────────────────┬─ ┆ irreversible ┆ ─┬────────────────────────────────────────────────────────┤
│ BUILD                    │                     │ RELEASE                                                │
│  preflight rows          │                     │  tag: ci-sha · tag step                                │
│  build steps + elapsed   │                     │  channel cards × CHANNELS, newest verify, as_of age    │
│   ↳ checks · gates       │                     │  clocks                                                │
│  CI (from status)        │                     │  verify rollup (complete only)                         │
│  ratchets (ceilings)     │                     │                                                        │
├──────────────────────────┴─────────────────────┴────────────────────────────────────────────────────────┤
│ events tail (merged) · unparsed count           │ failed step: log path · exit code                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- Panes: `resize: vertical; overflow: auto`, content-sized with a max; sizes
  persist in `localStorage` (try/catch).
- The renderer builds nodes with `createElement` and writes text with
  `textContent`. No `innerHTML` anywhere (tested).
- State colour carries `ok · warn · fail · running`; `pending · skipped ·
  unreachable · stranded · corrupt · later · unknown · no-data` are outlined
  or hatched, never filled.
- Effort without a time axis: elapsed as a proportion of the run's longest
  step; the table estimate as a hatched extension; the events-per-minute strip.
- The header says *snapshot, generated HH:MM*. **Superseded the same day by
  §8's `--serve`:** the served page patches itself pane by pane as the run dir
  changes, running stations pulse only while the heartbeat is fresh, and the
  header carries a live pill. The snapshot remains the default — `release.sh
  run --board` starts a server, plain generation does not — so both are true,
  but "there is no live mode" is not.

## 4 · Sequence and proof

| # | step | proof |
|---|---|---|
| 0 | key-id slip in `upload-testflight.sh` — landed alone | `git log -S'printed the live ASC key id'` |
| 1 | the feed: `sink.sh`, `report.sh` ownership + tee, `bn_events.py` extracted, `release.sh` boundaries + `steps.tbl` + `resolve_run` + `status` CI lines, preflight/verify rows, the two clocks, `test-sink.sh`, `ci.yml` entry | `test-sink.sh` green; `test-release-sh.sh` / `test-release-e2e.sh` / `test-verify-channels.sh` / `test-preflight-*.sh` still green; a `check-*.sh` run with a sink set writes lines |
| 2 | generator + `test-release-board.py` + the 0.28.0 fixture | suite green; `release-board.py 0.29.1` renders the real run with build panes honestly no-data |
| 3 | template | the fixture run renders every pane; DOM-sink grep and round-trip tests green; screenshot compared with the sketch |
| 4 | docs: `scripts/README.md`, `REPORT-STYLE.md` sink paragraph, `release-channels.md` "watching it", mockup register → IMPLEMENTED, this doc trued | `check-mockup-register.py` green |

## 5 · Out of scope, by decision

History overlay (the cross-release view shipped 7 Oct 2026 as a tab, §9) and Welford estimates (review-log Finding 22); probing from
the board; ~~any server (`--serve`, SSE, FastAPI, SwiftUI)~~ — **the server
shipped the same day this list was written; see §8** (`--serve`, loopback
`127.0.0.1:8151`, per-run token in the 0600 handshake, self-exiting after four
idle hours, `release-board.py:1503,1580`). The rest of the clause still holds:
no SSE, no FastAPI, no SwiftUI — it is `http.server` and a `: ping` comment
stream. The T-7 expiry warning (a future preflight row, not the board); the
bn-accurate design
system; any change to what a step does. The orphaned Python suites
(`test-dep-drift.py`, `test-tap-provenance.py` run in no workflow) are a
separate item.

## 6 · Risks the review named, and where each is answered

bash 3.2 safety → grep assertion in `test-sink.sh`. The `release.yml` reader →
deleted. Poll cost → snapshot by default, `--serve` opt-in (§8). Untrusted tail → never inlined by default.
Two-ledger merge → `sink_line` owns the clock; sort key; conductor wins.
**Can the tee hurt the train?** A full disk mid-`build-dmg`: the child's write
is swallowed and the driver's boundary write dies loud, which is the right
asymmetry — the driver already dies on `events.jsonl`. File growth: a run is a
few hundred lines. The EXIT trap's `rmdir` only succeeds on an empty dir, and
the sink makes it non-empty exactly as `events.jsonl` already does.

## 7 · As built (5 Sep 2026)

Landed as three commits — the feed, the board, the docs — plus the key-id
slip on its own. What differs from §1–§3 as written:

- **A run that predates `steps.tbl` still draws.** The line falls back to the
  ledger's own step ids in first-seen order, labelled *ledger order (no
  steps.tbl)*, and the confounded log reports *cannot be computed* rather than
  zero. Every run on disk today is that shape; the next `release.sh run` is not.
- **The channel count is read, not written.** `CHANNELS` from `project.conf`
  drives the cards; no document holds the number (review Finding 21).
- **A build lane has three states, not two.** *not run* (no ledger event), *ran
  — the sink has no record* (the ledger says ok, the sink has no window: every
  historical run), *data*. A driver window that closed with zero child lines is
  a *missing* entry in the confounded log.
- **The parser decodes ANSI-C quoting itself**, so a line a pre-normalisation
  writer produced still parses; a line `shlex` genuinely cannot read is
  counted. Both are in `test-sink.sh`.
- **`resolve_run`** is the shared "which run" rule for `verify`, `status` and
  the board: the sole run, or the newest by ledger mtime, narrated. The
  generator repeats the rule in Python because it does not source bash;
  both are tested.
- **Exit codes:** `0` written · `1` no run dir or no ledger · `2` usage — and a
  stranded run is `0` (it drew).
- **`docs/testing/inventory.md` moved** by the two suites, regenerated.

Owed, and written down rather than done: ~~the round-trip test that drives the
real `release.sh` under a sink and asserts the board's fold equals the
driver's (guard 3 of the drift review)~~ — closed by the rehearsal (§8, 5 Sep
2026); a redacted `bn-events.log` fixture
after the first real feed (guard 5); the orphaned Python suites in no
workflow — `test-release-board.py` and `test-sink.sh` joined `ci.yml`'s
release-suites job on 5 Sep 2026, which leaves the two that were there before.
And one observation from the build: `test-release-sh.sh`
still reaches the real `.release/` on some path with a version that resolves
to 0.28.0 and declines at the prompt — harmless now that the driver's lines
land after the prompt, and worth a look.

## 8 · Live, replay, and what the driver knows (5 Sep 2026, second day)

The snapshot was the layout to critique; the connection between the board and
reality is the thing. Five layers, each knowing only the one below, and the
writers knowing nothing above the files:

| Layer | Knows | Never knows |
|---|---|---|
| writers — `release.sh`, `build-*.sh`, the gates | a sink path that may be set; the run dir | generator, server, page |
| files — `.release/<v>/` | — | — |
| generator — `release-board.py` | the files, `steps.tbl`, `project.conf` | server, page |
| server — `release-board.py <v> --serve` | the generator, the run dir's mtimes | the writers |
| page | `board.json` over loopback HTTP | everything else |

**The server** is stdlib `ThreadingHTTPServer` on `127.0.0.1`, port 8151 by
default (deterministic, because the browser keys the saved layout by origin).
**When 8151 is taken** (incident 43, 0.35.0: the previous release's board,
hours from its idle exit, held it), the server reads the other boards'
handshakes. A board for another version whose run has **finished** is retired
(TERM, then wait on the port, not the pid) so the new run keeps the origin; a
board whose run is live, or anything that is not a board, is never touched, and
the server takes the next free port of nine and says so. An explicit `--port`
is honoured or fails. `bind_with_fallback` in `scripts/release-board.py`;
`PortFallback` in `scripts/test-release-board.py`.
**Loopback is not a boundary between users or processes on one Mac**, so every
request carries a per-run token minted at start and written only into the
0600 handshake — the house pattern of serve mode's auth token and the scoped
`/mcp` bearer (security review, 5 Sep 2026); no token or the wrong one is a
404, as if nothing were there. A watcher thread stats the watched files every
`--poll` seconds (`(name, mtime_ns, size)` — size too, since two writes can
share an mtime tick) and rebuilds the model when anything moved, skipping a
tick whose ledger does not end in a newline (a torn read would flash the run
stranded). Log tails are an **opt-in** here as everywhere (`--with-logs`), and
a tail is read by seeking the last 64 KB, never the file — a `gh run watch`
transcript reaches megabytes over a 38-minute gate. The previous run is read
once, at start; it cannot change while this one is live. A generator failure
keeps the last good model and puts the scrubbed error on the page; a watcher
failure does the same rather than serving a stale 200. `GET /` is the page
with the model inlined, `/board.json` the model with `served_at` stamped at
serve time (so staleness on the page means "no successful pull", not "nothing
changed"), `/events` an SSE tick per generation (`: ping` every 15 s, at most
16 streams), `/health` the generation. A `Host` header that is not loopback is
a 400 — the DNS-rebinding case. `Cache-Control: no-store`, a CSP that allows
only inline script and style, `connect-src 'self'`, `frame-ancestors 'none'`;
a 30 s handler timeout. **The server owns its own life**: it exits after
`--idle` seconds without a request (4 h) or a minute after the run dir loses
its ledger, and removes its handshake on the way out.

**The page** renders from one model, `render(data, root)`, and in live mode
patches: SSE says changed, the page fetches `board.json`, renders into a
detached tree, and swaps only the panes whose data slice moved
(`JSON.stringify` of a per-pane slice; a pane set that changed shape falls back
to a full render). A one-second tick counts every age from its stamp
(`data-ts`), counts a running station's elapsed from its ledger stamp
(`data-since`), and decides freshness: **motion carries liveness, and every
motion is driven by a stamp that expires.** The running station pulses only
while the heartbeat is under 60 s old (or a pid exists and no heartbeat file
does; or the frame is a replay, which says so); stale turns it amber. A pane
whose newest stamp is under 10 s old is outlined; a swapped pane glistens once.
`prefers-reduced-motion` replaces the pulse with an outline and drops the
glisten. Widths of the three columns are fractions of the row, set by dragging
the two gutters (the red IRREVERSIBLE band is the first) and kept in
`localStorage`; dim means a pane's inputs have not been written yet.

**The seam into the driver, in two internal functions.** The server writes
`.release/<v>/board-server.json` — `{schema: 2, url, port, pid, token,
version, started}`, 0600, removed on exit if the pid is its own. `board_link`
prints one line, `board  http://127.0.0.1:<port>/?k=…`, when that file
exists, its pid is alive, the url's port is the file's, and that port accepts a
connection (a recycled pid is not the board); on every other outcome it is
silent. `run --board` calls `board_ensure` instead: the same link if one is
serving, else a **detached** server (`nohup … &`, its log in the run dir) and a
wait of at most three seconds for its handshake — then it prints and forgets.
The driver never waits on the server past that, never stops it, and never fails
because of it: a missing generator or python is one line of note and the
release proceeds.

**What a person actually types — six shipped surfaces, recorded 20 Sep 2026.**
`board_link` and `board_ensure` are internal; none of the below appeared
anywhere in this document, and §2's usage line still showed
`[VERSION] [--out DIR] [--with-logs]`.

| Surface | What it does |
|---|---|
| `release.sh run --board` | starts a detached server if none is serving, prints the link. Without the flag, `run` prints a link only if it finds one — the release never needs the board |
| `release.sh board [<X.Y.Z>]` | the standalone verb (`cmd_board`, `release.sh:499`) — the eighth verb, absent from §19's list of seven in the sibling doc |
| `release.sh board --stop` / `--restart` | TERM not INT, deliberately (`release.sh:509`); pinned by `test-release-sh.sh:81-84` |
| `release-board.py --json` | the board's model without the page (`:1576`) |
| `release-board.py --backfill-preflight` | **changes §2's preflight-pane contract.** §2 says "no rows → no-data"; this *writes* rows a pre-sink run never recorded, from the driver's captured logs (`:1578`). `--dry-run` (`:1579`) reports what it would write |
| `release-board.py --replay` | a scrubber over the real generator at every ledger line | `test-release-sh.sh` pins the six `board_link` outcomes, the
four `board_ensure` ones, that `release.sh` names the generator exactly once
(that default), and that no build script names the server or the handshake —
`build-all.sh` and `build-dmg.sh` are also run standalone, from Xcode and by
hand, and their whole contract with observability stays the sink env var.

**Rehearsal** — `scripts/rehearse-board.sh` runs a whole release at fake speed
on the live board, with nothing synthetic about the writers: a throwaway root
with its own `.release/`, a previous run to diff against, the real step table
(`run_steps`, now exposed to `RELEASE_LIB=1` sourcers), the real `ev_append`
writing the ledger, the real `sink.sh` writing the driver's windows, the real
`report.sh` helpers writing a build lane's steps, checks, gates and art in
plain mode with stdout captured to the step's log exactly as the driver does.
The run has one warn and one duplicate preflight label, a result and an event
kind the board has no rule for, a build-dmg failure whose log fills the Log
pane and then a retry, a heartbeat stall long enough to turn the running
station amber (the board reads `BN_HEARTBEAT_SECS` as the driver does; the
rehearsal sets it to 5), CI rows, a verify with one channel missing and one
unreachable, both clocks, and a completed run whose confounded log is
computable and non-zero. `--check` asserts that final model from
`/board.json` and is a case in `test-release-sh.sh` — the fold in two
languages proven equal on a run that never happened, which was guard 3 of the
drift review and had been owed since the first day.

**Replay** — `--replay` writes `board-replay.html`: frame *i* is the real
generator on the first *i* ledger lines and the sink lines stamped no later, in
a throwaway copy of the run dir (made inside `.release/`, so a crash leaves it
somewhere private); a fixed scrubber (buttons, arrow keys) steps through them.
The **last frame is the board**: the whole sink, late verifies included. Every
other frame's caption counts the sink lines beyond its horizon, and an
unparseable ledger line keeps the previous horizon rather than emptying the
sink. Each frame carries its own clock (`now` = its last ledger stamp), so a
running station's elapsed counts from the frame, not from today. Liveness is
the one thing a prefix cannot read, so a step a prefix leaves running is shown
running and the frame says "liveness assumed". A design tool for the info
design; the real board never renders the scrubber.

**The board's replay** (8 Oct 2026). A replay icon at the top
right of THE LINE (served boards only: a snapshot has no server to ask, and the
`--replay` page is already a replay) replays the run in place, with
back / play-pause / forward, ←/→, space and Esc, and a count (`17 of 55 · attempt 1 of 6`). A scrubber with attempt and fail ticks shipped first and was dropped the same day at the owner's word: too much; the buttons are enough. The owner's
decisions, asked before it was built:

- **The whole board moves** (revised the same day). It first shipped with
  only THE LINE moving and every other pane live underneath; the owner then
  asked for the rest of the board to follow. Each step now renders the frame's
  full model; the controls stay on THE LINE as one persistent node, so focus
  survives. While replaying, a live pull only updates the page's newest model
  and draws nothing; **back to live** draws that model, so nothing that
  happened during the replay is lost.
- **The whole release, every attempt.** 0.34.0's failures are all in attempts
  1–5, and its last attempt is clean. The control bar names the attempt
  (`attempt 5 of 6`).
- **Evenly spaced.** About 10 s from start to end: `10 s / (frames − 1)`,
  clamped to 120 ms–1 s per frame. Proportional time was offered, with a
  minimum dwell and an automatic pause on fail, and was declined. So a 13-minute
  build-dmg gets the same beat as a 2-second inventory, and play does not stop
  on a failure. The red caption is how a failure is found.
  Step to it, don't wait for it.
- **The last frame holds**, captioned "the line as it stands", until
  back-to-live or Esc. Play from the last frame starts again at frame 0.

Frames are **`replay_frames` minus the cross-release history**
(`board_frames`: `model`, `now`, caption). There is no second frame model. The
History pane keeps the live model's history, whose mark for this run follows
the frame's line. The page fetches the frames from `/replay.json`
(token-gated like everything else) on each open, and never inlines them.
0.34.0 is 55 frames, about 1.6 MB, about 1.7 s to build. `BoardState` caches them by the ledger's and the sink's
(mtime, size), so a heartbeat does not rebuild them. **The last frame is the
current model**, when the model was built from the same ledger and sink.
Liveness moves without the ledger (a lock taken, a pid gone), and a cached last
frame said *stranded* for a run in progress. `replay_frames` had the same
defect for any prefix that is the whole ledger: it assumed "not alive" from the
copy, which has no `.lock`. It now reads the real run dir's liveness for that
frame. A replayed running station pulses (liveness assumed) and counts elapsed
from its frame's clock, through the same tick as the rest of the board.

Rendering keeps the no-DOM-sinks rule (icons by `createElementNS`). **Reduced motion:** the replay opens paused on frame 0 and
plays only when asked. Pinned by section 5 of `test-release-board-dom.js` (all
red on their mutants: the live-pull hold, a line-only render, the reduced-motion
guard, the frame clock) and by
`Server.test_replay_route_serves_the_lines_frames_behind_the_token`.

**The run picker** (8 Oct 2026, owner's ask). On a served board the version in
the header is a pull-down of every run under `.release/` that has a ledger,
newest first by its first stamp (`list_runs`). Abandoned dirs such as
`0.31.3-stopped-24sep` are included, because they are runs. The board's own
run is the bare URL. Any other run is `?run=<id>`, which the server draws with
the same generator (`BoardState.past`) and serves **read-only**: the page reads
it once, never patches it from the live run's stream, says "past run ·
read-only", and offers a way back. Its replay fetches
`/replay.json?run=<id>`, and the replay's last button reads "done", not "back
to live". Only a listed id is ever opened: anything else, a path included, is
a 404, behind the same token. A snapshot has no picker, because there is no
server to ask. The cross-release question still belongs to History; this is for
looking at one run as its own board.

**Links.** Every public page is an anchor built in the generator from
`project.conf` constants (`read_conf` expands its own `${VAR}`s) and validated
ids: PyPI at the version, the release tag, the tap formula, snapcraft, Copr,
the dmg permalink, the changelog, App Store Connect; the ci-sha as a commit,
each CI run id as an Actions run, `ratchet.json` pinned to the ci-sha. The
template sets `href` in one place, every url is https, and a sha that is not
hex or a run id that is not digits gets plain text.

**One live board per run** (7 Oct 2026). The handshake is one file per
version and everything in `release.sh` reads it, so a second `--serve` for a
version that already has a live board (a board process, not us, whose port
answers) prints that board's url and exits 0 instead of taking the file over.
Before this, a preview board for 0.35.0 overwrote the release's handshake;
`release.sh board --stop` then killed the preview, and the preview's exit
deleted the file the release's board still needed. `live_board()` in
`release-board.py`; `OneBoardPerRun` in the suite, proved red with the guard
removed.

**Writes are atomic**: `write_private` writes a sibling temp file
(`O_EXCL|O_NOFOLLOW`, 0600, fsync) and renames it over the destination, so a
reloading browser or a poller never reads a half file and a symlink at the
destination is replaced, never followed.

Proof, three layers. `Server` in `test-release-board.py`: loopback bind, page
and model, no token or a wrong one is a 404, a foreign Host a 400, log tails
opt-in, `served_at` per pull, a torn ledger write not published, generation
bump and SSE tick on a ledger write, handshake 0600 with the token and removed
on SIGINT by the real `--serve` process, a lost ledger keeps the last model
with a scrubbed error. `Heartbeat` pins the cadence against `release.sh`'s
default (as the dmg clock is pinned against `AlphaBuild.swift`) and that the
last log line is scrubbed. `board_link` and `board_ensure` cases in
`test-release-sh.sh`. And **`scripts/test-release-board-dom.js`**, run in the
frontend CI job where jsdom lives: the page's live half executed, not grepped
— every pane renders, the running station pulses on a fresh heartbeat and goes
stale past three cadences, a patch swaps only the pane whose slice moved and
keeps the others' nodes, an older generation does not regress the page, a
failed pull is an "unreachable" state on the pill with the server's reason, a
renderer fault on live data reaches the band, and a replay frame keeps its own
clock and assumed liveness. fetch and EventSource are stubbed (jsdom has
neither), so the wire is proven by the Python suite and the page's reaction
to a model by the node one; the two together cover what a single-language
harness could not.

## 9 · History: every release attempt, on one step axis (7 Oct 2026)

**What it answers.** The maintainer's three questions, after 0.35.0 became the
first release since 0.31.5 to run start to finish unattended: (i) where do most
attempts stop, and what are the edge cases; (ii) is the machine getting
better; (iii) every release attempt we have made, over time. The run board
answers none of them, because it is one run.

**It is a tab, not a page.** A segmented control in the header, **This run ·
History**, stored in `localStorage` (`rb-view`), the theme toggle's pattern.
The run's panes stay in the DOM under History, so a live patch still lands;
`pane-history` is one more slice in the patch map.

**Layout, after the owner's first reading (8 Oct 2026).** The key sits top
right in a titled, keylined box beside the controls, and wraps its own text
rather than dropping onto a line of its own. The focused release's detail is
an **inspector** to the right of the scrolling strip, not under it. It is
exactly as tall as the step rows (`H_ALL`, the depth of the funnel's step
list) and scrolls inside, so choosing another release never moves the
"Where attempts stopped" tables below it. They used to jump with every
choice. Below 900 px it drops under the strip at a capped height.

**No `--history` flag, by decision.** The tab reads every `.release/*/events.jsonl`
and `bn-events.log` on every model build — 16 ledgers, ~60 KB of model — and
needs nothing the run dir does not already hold. A flag would hide the one
view that answers "are we getting better" behind a thing nobody remembers to
type. The cost is bounded by caching: `history()` is keyed on the ledgers'
and sinks' mtimes and sizes, and each failed log's class on its own, so the
live server re-derives nothing between changes. §5's "History overlay … out of
scope" is superseded by this section for the cross-release view; the
per-run overlay (Welford estimates) stays out.

**The model is `release-stats.py`'s, not the board's.** `release_stats.history(root)`
returns one record per `run started` line, grouped by the ledger's own `run`
field (so the renamed `0.31.3-stopped-*` dirs are invocations of 0.31.3). Each
has an **entry** — the first step it executed, because resume skips completed
steps silently and a resumed run enters mid-line — and an **exit**:

| exit | when | drawn as |
|---|---|---|
| `fail` | a step wrote `fail`; class from the ledger stamp (`class=`, since 0.32.0), else `verdict_failure_class` on the step log | ✕ |
| `stopped` | the ledger just ends: killed, or stopped by hand. `mid_step` says whether a step was running. Also `run completed` over a table that never reached `snap` (incident 22's first form, 0.28.0) | ▢ |
| `skipped` | `run completed` over a skipped irreversible step with no tag pushed (incident 22 reopened, 0.31.3) | ◇ |
| `completed` | every step it ran was ok, through `snap` | ● |

Channels come from `release.sh verify` in the sink: a channel is **reached** if
any complete pass saw it ok, because a later pass reads `bad` only once the
next release has moved the channel on. No sink is no record (0.28.0, 0.29.0),
never zero. `CAUSES` and `UNLEDGERED` are the two hand-kept tables — the cause
of a stop where the release log or the premortem names it, keyed
`version#n`, and stops that happened before `run started` was written (0.33.0's
notary 403). Absent a cause, the chart shows the class alone; it never invents
one. `MACHINE_MILESTONES` names the release-machine commits worth labelling;
every other commit to `MACHINE_PATHS` still appears, unnamed, in its gap.

**The picture.** Rows are steps in plan order, then the eight channels.

- **Left, a funnel** (fixed): of 100 attempts that start, how many get past each step.
  The width at a step is the share of that step's attempts that passed it,
  multiplied down the line — rolled throughput yield, from process
  engineering. A plain head-count was tried first and rejected: resumed
  attempts join mid-line, so the count bulges instead of narrowing, and the
  owner's "100 starts, fewer finish, where did they abandon" stops being
  readable. One outline per release, newest on top and bold; every older
  layer carries a 5 % fill, so where many releases got through reads darker
  (the onion). The grey behind is every release pooled; the number at each
  row's edge is how many attempts stopped there. An attempt stopped *between*
  steps is counted as abandoned at the next one.
- **To its right, every invocation** as its own vertical line, grouped by
  release (dated). Time runs right to left so the newest attempt sits against
  the funnel: the strip is laid out oldest-first and mirrored (`DIR = -1`), so
  it opens on the newest runs with no scroll measuring, and you scroll right to
  go back in time. The row labels and the funnel stay fixed on the left. It starts at the step it entered (▸ when mid-line), runs
  down, and ends in its exit mark; a dashed curve carries a release from one
  invocation's end to the next one's start (leftward, since later is left), so
  a resume reads as a U-turn.
  Dashed vertical rules are commits to the release machine landing between
  two attempts; the numbered ones are the milestones, listed under the chart.
- **Above the funnel, All releases · By machine version** and a slider. A
  machine version is the release machine as it stood between two *named*
  changes (`MACHINE_MILESTONES`), not every commit: fifty commits would be
  fifty stops, most with no attempt under them, and several changes often land
  in one gap between releases. So the slider has one stop per version at least
  one attempt ran under (11 at 0.35.0). An attempt belongs to the version in
  force when it started; a release's channel row to the version that shipped
  it. In version mode the funnel draws one outline per version, built from the
  attempts that ran under it (the selected one blue), the timeline dims every
  attempt outside it and scrolls to it, and a line names the version, its
  attempts, its yield and the changes that began it. All releases is the
  per-release onion. Read at 0.35.0: every version through 10 sits between 0
  and 13 % because one bad night (0.32.0's eight attempts) outweighs three
  clean releases in the same version; version 11 is the first at 100 %, on one
  attempt — a trend to watch, not yet a measurement.
- **The run in progress** is drawn with the run board's own semantics and
  tokens, never a second verdict: whether the newest attempt is running or
  stranded comes from the generator's station fold (lock, pid, heartbeat),
  plus a held lock with a live pid between two steps. Running: a `--now` line
  and a pulsing dot (`.hist-live.running`, toggled `fresh`/`stale` by the same
  tick and heartbeat rule as `.station.running`, amber when stale, still under
  reduced motion), and "· running" on its release label. Stranded: a broken
  `--bad` ring, never pulsing. Its funnel layer stops at the live step, dashed
  ("so far"), and the undecided step counts as neither a pass nor a stop. The
  live slice for the patch map includes the station states and the lock, so a
  run going stranded re-draws the pane even when the ledger has not moved.
- Under it: the selected release's stops in words (click a release label),
  a table of where attempts stopped by step and class (the chart's text
  equivalent; every heading sorts, "step" by plan order, numbers
  largest-first, and the stop count carries an in-cell data bar), and the
  milestone list.

**Prior art.** The right half is a Marey chart (E. J. Marey's 1885 Paris–Lyon
train schedule: stations on one axis, one line per train, a reversing train
turns back) crossed with the clinical swimmer plot (one bar per patient, an
event mark where something happened, an arrow for "still going"); the
demographers' Lexis diagram draws the same lifelines with a mark at death. The
left half is a funnel read as rolled throughput yield. The closest software
analogue is a CI stage view (build × stage grid), which loses both the resume
shape and the cross-release trend this view exists for.

**Proof.** `scripts/test-release-history.py` (unittest, in the `release-suites`
CI job): a clean run, a resume that enters mid-line with its stamped class,
`completed` over an unfinished table, a skipped tag versus a skipped act
already done, stopped mid-step versus between steps, renamed dirs grouped by
`run`, a channel reached on an earlier pass, no sink is no record, torn lines
counted, a root git cannot answer for is `None`, and the board surviving a
failed history read. Two of those were proven red on mutants (the
claimed-complete rule; reached-on-any-pass). `test-release-board-dom.js`
section 4: the toggle, the pane, one release label per release, the stopped
mark, the table view, text-only SVG titles, and a bad read as a nodata line,
not the fault band.
