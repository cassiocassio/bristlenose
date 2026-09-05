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

### 1.1 `desktop/scripts/sink.sh` — one helper, five consumers

```bash
# sink_line <kind> k=v …  — append "@bn <kind> ts=<UTC> run=<id> k=v…" to
# $BN_EVENT_SINK. No-op unless the sink is set and absolute. Never fails the
# caller. bash 3.2 safe.
```

- **Normalise before quoting** (the measured defect): each value has control
  bytes stripped (`tr -d '\000-\037'` after CR/LF/TAB → space) and is cut to
  200 bytes, then `printf '%q'`. That keeps `shlex` able to read every line,
  keeps every line under `PIPE_BUF` so concurrent appenders cannot interleave,
  and keeps a value from forging a second `@bn` line.
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
board was written, `1` when the run dir or `steps.tbl` is missing, `2` usage.

Output: `board.json` and `board.html` (the template with the JSON inlined,
`ensure_ascii` then `< > &` escaped) into `.release/<v>/`, mode 0600.

### 2.1 Proof — `scripts/test-release-board.py` (unittest, `.venv/bin/python`)

Synthetic run dirs under a temp `.release/`: fold (stranded vs running via a
dead pid; `corrupt` from a fragment; `skipped`; `later`; `unknown`;
`not-in-this-run`); no data is not green (an empty run dir with `steps.tbl`
renders every tile no-data, exit 0; without `steps.tbl` exit 1); build
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
- The header says *snapshot, generated HH:MM*; there is no live mode.
  Watching: `while sleep 5; do .venv/bin/python scripts/release-board.py; done`
  and ⌘R.

## 4 · Sequence and proof

| # | step | proof |
|---|---|---|
| 0 | key-id slip in `upload-testflight.sh` — landed alone | `git log -S'printed the live ASC key id'` |
| 1 | the feed: `sink.sh`, `report.sh` ownership + tee, `bn_events.py` extracted, `release.sh` boundaries + `steps.tbl` + `resolve_run` + `status` CI lines, preflight/verify rows, the two clocks, `test-sink.sh`, `ci.yml` entry | `test-sink.sh` green; `test-release-sh.sh` / `test-release-e2e.sh` / `test-verify-channels.sh` / `test-preflight-*.sh` still green; a `check-*.sh` run with a sink set writes lines |
| 2 | generator + `test-release-board.py` + the 0.28.0 fixture | suite green; `release-board.py 0.29.1` renders the real run with build panes honestly no-data |
| 3 | template | the fixture run renders every pane; DOM-sink grep and round-trip tests green; screenshot compared with the sketch |
| 4 | docs: `scripts/README.md`, `REPORT-STYLE.md` sink paragraph, `release-channels.md` "watching it", mockup register → IMPLEMENTED, this doc trued | `check-mockup-register.py` green |

## 5 · Out of scope, by decision

History overlay and Welford estimates (review-log Finding 22); probing from
the board; any server (`--serve`, SSE, FastAPI, SwiftUI); the T-7 expiry
warning (a future preflight row, not the board); the bn-accurate design
system; any change to what a step does. The orphaned Python suites
(`test-dep-drift.py`, `test-tap-provenance.py` run in no workflow) are a
separate item.

## 6 · Risks the review named, and where each is answered

bash 3.2 safety → grep assertion in `test-sink.sh`. The `release.yml` reader →
deleted. Poll cost → no live mode. Untrusted tail → never inlined by default.
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

Owed, and written down rather than done: the round-trip test that drives the
real `release.sh` under a sink and asserts the board's fold equals the
driver's (guard 3 of the drift review); a redacted `bn-events.log` fixture
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

**The server** is stdlib `ThreadingHTTPServer` on `127.0.0.1` (port 0 unless
`--port`). A watcher thread stats the watched files every `--poll` seconds
(`(name, mtime_ns, size)` — size too, since two writes can share an mtime tick)
and rebuilds the with-logs model when anything moved; a generator failure keeps
the last good model and puts the error on the page. `GET /` is the page with the
model inlined, `/board.json` the model, `/events` an SSE tick per generation
(`: ping` every 15 s), `/health` the generation. A `Host` header that is not
loopback is a 400 — the DNS-rebinding case. `Cache-Control: no-store`, a CSP
that allows only inline script and style and `connect-src 'self'`. It carries
log tails because it is the view on your own screen; it never leaves the
machine, and `board.html` on disk stays the clean one.

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

**The one seam into the driver.** The server writes
`.release/<v>/board-server.json` — `{schema, url, port, pid, version, started}`,
0600, removed on exit if the pid is its own. `release.sh`'s `board_link`
prints one line, `board  http://127.0.0.1:<port>/`, when that file exists,
its pid is alive and its url is loopback; on every other outcome it is silent.
It never starts, waits on, or fails because of the server, and
`test-release-sh.sh` pins that the driver never invokes the generator and no
build script names the server or the handshake.

**Replay** — `--replay` writes `board-replay.html`: frame *i* is the real
generator on the first *i* ledger lines and the sink lines stamped no later, in
a throwaway copy of the run dir; a fixed scrubber (buttons, arrow keys) steps
through them. Liveness is the one thing a prefix cannot read, so a step a
prefix leaves running is shown running and the frame says "liveness assumed".
A design tool for the info design; the real board never renders the scrubber.

**Links.** Every public page is an anchor built in the generator from
`project.conf` constants (`read_conf` expands its own `${VAR}`s) and validated
ids: PyPI at the version, the release tag, the tap formula, snapcraft, Copr,
the dmg permalink, the changelog, App Store Connect; the ci-sha as a commit,
each CI run id as an Actions run, `ratchet.json` pinned to the ci-sha. The
template sets `href` in one place, every url is https, and a sha that is not
hex or a run id that is not digits gets plain text.

**Writes are atomic**: `write_private` writes a sibling temp file
(`O_EXCL|O_NOFOLLOW`, 0600, fsync) and renames it over the destination, so a
reloading browser or a poller never reads a half file and a symlink at the
destination is replaced, never followed.

Proof: `Server` in `test-release-board.py` (loopback bind, page and model,
generation bump and SSE tick on a ledger write, foreign Host refused, handshake
0600 and removed, lost ledger keeps the last model); `board_link` cases in
`test-release-sh.sh`; the served page rendered in jsdom with every pane, the
live pill and no renderer error. Not mechanised: the in-place patch and the
tick run only in a browser — the jsdom check is a scratch script, not a suite.
