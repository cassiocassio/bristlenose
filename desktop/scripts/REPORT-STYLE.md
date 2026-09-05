# Script house style — how a script renders, and how it is shaped

Two directories, one set of conventions: `desktop/scripts/` (build the app) and
`scripts/` (release it, and gate it). **Part 1** is the shared look-and-protocol
for CLI output, so every script renders as **one system** and adding a new one
raises no design questions. **Part 2** is the structure the release chain
settled on — where constants live, how a script decides, what its exit code
means, and how a test proves any of it.

**Status (Jul 2026): shipped.** `report.sh` (emitter helpers) + `build_report.py`
(Rich renderer) are wired into `build-all.sh` (validated on a real signed build that
delivered a TestFlight `.pkg`) and the standalone gates `check-release-binary` /
`check-bundle-manifest` / `check-logging-hygiene`. Remaining siblings
(`sign-sidecar.sh` — the bar showcase — `build-sidecar.sh`, `ensure-sidecar.sh`,
`fetch-ffmpeg.sh`, `sign-ffmpeg.sh`) adopt the recipe below without redesign.

# Part 1 — how a script renders

## Split of responsibilities

- **Scripts stay dumb about presentation.** A script emits *events* (structured
  sentinel lines) and redirects its noisy tool output (`xcodebuild`, PyInstaller,
  `codesign`) to a per-step log file under `desktop/build/`, exactly as today.
- **One renderer owns the look** — `build_report.py` (Rich). It reads the event
  stream on stdout, draws the report, and passes non-event lines through only in
  `--verbose`. Nothing else formats glyphs, bars, or panels.
- **Degrades to plain.** Non-TTY / `NO_COLOR` / `TERM=dumb` → no colour, no
  animation (the resting frame, still readable). Renderer never writes ANSI into
  the redirected log files. (clig.dev: don't animate a non-terminal.)

## The event protocol (the contract siblings adopt)

Scripts source `report.sh` and call its helpers, which echo sentinel lines. The
renderer parses lines beginning `@bn ` and maps them 1:1 onto the schema below.

```
@bn step   id=<tag> phase=<Phase> name="…" status=start|ok|skip|fail \
           elapsed=<sec> detail="…" narrative="…"
@bn check  parent=<tag> label="…" result=ok|warn|fail evidence="…"
@bn bar    parent=<tag> done=<n> total=<n> label="…"
@bn gate   id=<a> desc="…" result=ok|skip|fail evidence="…"
@bn art    key="…" value="…"
@bn done   status=ok|fail
```

- `tag` is the **script index** (`5`, `2a`) — kept for log grepping; the renderer
  assigns the human `1…N` display number itself.
- A step with no known count omits `@bn bar` and shows a spinner + elapsed. A step
  with a real count (per-file signing) emits `@bn bar` for a determinate bar.
  **Never fake a fraction we don't have.**
- On non-zero exit a script emits `status=fail` with the failing step; the renderer
  shows the step's log tail inside its block and a red footer. Scripts still
  `set -euo pipefail`; the report is a view, not the control flow.

## The sink — the file form of the same protocol (5 Sep 2026)

`_bn_emit` also appends every line it renders to `$BN_EVENT_SINK` when that
is set — the `@bn` line itself with `ts=` (UTC, stamped by the sink) and
`run=` added — via `sink.sh` next to this file. `release.sh run` exports the
sink as `.release/<v>/bn-events.log` (absolute; a child's cwd is not ours),
writes its own boundary lines (`@bn run`, `@bn step … attempt=N
status=start|end rc=…`) with the write **asserted**, and snapshots the step
table to `steps.tbl`. The preflight's rows, `verify`'s rows and rollup,
`status`'s CI facts and the two expiry clocks ride the same file. The board
(`scripts/release-board.py`) reads it and nothing else; `bn_events.py` is the
one parser, shared with the renderer.

Three rules the file taught, all measured:

- **Normalise before `%q`.** `printf %q` renders control bytes — and, under a
  C locale, every non-ASCII byte — in ANSI-C quoting (`$'…'`), which `shlex`
  does not decode: a newline plus an apostrophe made the parser drop the whole
  line. `sink_line` strips `\000-\037` (CR/LF/TAB → space), caps at 200
  bytes, drops an incomplete trailing UTF-8 sequence, and runs the pipeline
  under `LC_ALL=C` (a UTF-8 BSD `tr`/`cut` aborts on the first invalid byte,
  and a `set -e` caller dies inside the sink). The cap stops a value forging
  a second `@bn` line; it does **not** make a line atomic — bash's `printf` to
  a file is stdio-buffered at 1 KB and `%q` can expand a non-ASCII value
  fourfold, so two writers can splice a long line, which the parser then
  counts as unparsed rather than reading half of it. The parser decodes
  `$'…'` byte-wise (bash 3.2 writes a raw lead byte plus octal continuations)
  and **counts** what it cannot read.
- **Ownership is one token.** The sink follows rendering ownership: a nested
  child that is silent on stdout is silent in the file. `bn_autowrap` claims
  `_bn_owner` on *every* standalone path — plain mode and no-renderer used to
  skip it, so a parent and its children would all have recorded.
- **The driver's write fails loud; the children's swallow.** A dashboard must
  never fail a build step, but "the sink received nothing" has to be
  readable as such — so the driver's own lines are the assertion.

`scripts/test-sink.sh` is the proof.

## The three section schemas

| Section | Fields |
|---|---|
| **Step** | `tag, phase, name, status, elapsed, detail, narrative, checks[], bar?` |
| **Check** (leaf under a step) | `label, result, evidence` |
| **Gate** (final readiness battery) | `id, desc, result, evidence` |

Plus a **header panel** (build identity: target, identity, bundle, team, logs) and a
**footer panel** (artifact + size + signed + next action, green on success / red on
fail).

## Rendering rules

1. **Glyph vocabulary is fixed and shared** — `✓ ℹ ⚠ ✗ —` from
   `bristlenose/ui_kinds.py`. Never invent a new glyph; map new states onto these.
   Colour only for state (green ok · yellow warn · red fail · dim skip/detail),
   used sparingly.
2. **Phases group the steps** — `PRE-FLIGHT · BUILD · PACKAGE · VERIFY` headers
   with a per-phase step count; live mode also shows an `[n/N]` counter. A new
   script slots its steps into an existing phase before inventing one.
3. **Human numbering, script tag retained** — display `1…N`; show the script index
   as a dim right-aligned `[5]` / `[2a]` so both first-timers and log-greppers win.
4. **Narrative for the heavy/opaque steps** — one dim italic line saying *what it
   does and why it's slow*. Skip it for the trivially self-evident steps.
5. **Detail on the indented line**, not crammed inline — evidence (`220 binaries
   signed`, `flags=0x10000(runtime)`) sits under the step at the 8-col indent.
   **Exception — list-shaped callers** (amended 23 Aug 2026): a caller whose whole
   output *is* the step list, rather than a build with steps in it, may put short
   detail inline and right-align the composite `detail  [tag]  elapsed` as one
   blob — ragged left edge on the detail, clean right edge on the tags. The
   trade is explicit: a 14-row release overview reads as 14 lines instead of 28,
   and rule 8's single right edge is preserved *because* the whole cluster is
   aligned as a unit. Applies only when every detail is short enough not to wrap;
   the moment one does, that row falls back to the indent line. `release.sh` is
   the first such caller (`docs/design-release-machine.md` §10); `build-all.sh`
   and the `check-*` family are **not** — they are builds, and stay on the rule.
6. **Append-only, not a redrawing tree** — each step prints its final line when it
   completes (cargo/uv style). Spinners/bars are transient *during* a step, then
   resolve to a static line. This keeps `tail -f` on the log files sane and CI
   capture clean.
7. **Airy leaders** — spaced `· · ·` between name and the right cluster, not a
   solid dotted run.
8. **Width** — target 92 cols; wrap narrative to width−indent; right cluster
   (`[tag]  elapsed`) is right-aligned. Under rule 5's list-shaped exception the
   right cluster is `detail  [tag]  elapsed` and is right-aligned as one unit —
   **never** align the tags while letting detail float, which is what produces a
   `[n]` column that wanders and is the failure this amendment exists to forbid.

## Adopting the style in a sibling script (the recipe)

`report.sh` centralises the wrapper, so adoption is a fixed preamble — no per-script
boilerplate to get wrong:

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # many scripts already set this
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"      # re-execs self piped through build_report.py if standalone
trap '_ec=$?; [ "$_ec" -ne 0 ] && bn_trap_fail' EXIT   # any abort → red footer
bn_meta title="…" done_title="✓ … clean"
bn_step_start 1 <Phase> "<Step name>" narrative="…" log="$SOME_LOG"
#   … the script's real work, UNCHANGED …
bn_step_ok 1 detail="…"    # or the trap fires on a nonzero exit
bn_done ok
```

- **Light-touch is fine for gates.** Wrap the whole check as one step; leave the
  script's internal `echo`s alone — the renderer suppresses them when pretty, and
  they reappear under `BN_REPORT=0`. Don't convert every line.
- **`bn_autowrap` handles every mode**: standalone → wraps + renders; nested under a
  rendering parent → silent (parent narrates); `BN_REPORT=0` or no python → plain
  `==>` output — and since 5 Sep 2026 a plain-mode parent claims ownership too,
  so its nested children are silent under `BN_REPORT=0` as well (they used to
  each print, and each write to the sink).
- **Redirect a noisy/opaque subprocess** to `desktop/build/<name>.log` and pass
  `log=<path>` on `bn_step_start`; the renderer shows "tail `<basename>`" while it
  runs and points there on failure.
- **Numbering**: reuse the script's own step index as the `tag`; the renderer
  assigns the human `1…N`.

## Portability & nesting (the two traps)

1. **bash 3.2 — `report.sh` MUST stay 3.2-safe.** `ensure-sidecar.sh` and the Xcode
   "Ensure Sidecar Fresh" build phase run under `/bin/bash` 3.2. So `report.sh` uses
   NO associative arrays (`local -A`), NO `mapfile`, NO `${var,,}` — only string ops,
   `case` globs, `printf %q`, `PIPESTATUS`. `_bn_field` replaces the assoc-array
   lookup. (A script that needs bash 4+ for its OWN logic — `sign-sidecar.sh`'s
   `wait -n`, `check-bundle-manifest.sh`'s `mapfile` — may require it; it's
   `report.sh` that must run anywhere. Verified against real `/bin/bash 3.2.57`.)
2. **Nesting — a child never starts a second renderer.** `bn_autowrap` exports
   `_BN_ACTIVE=1`; a child seeing it does not wrap, and its `bn_*` calls emit nothing
   (only the non-exported `_bn_owner=1`, set in the render owner, enables emission).
   So `build-all.sh` calling `check-*` produces ONE report — the gate's own narration
   is suppressed and build-all narrates the step.

## Level 2 — determinate bars (next enhancement)

The showcase is a real per-file progress bar. `sign-sidecar.sh` signs ~220 Mach-Os in
a `wait -n` job pool; emitting `@bn bar parent=<tag> done=<n> total=220` from the
completion loop renders a determinate bar under that step. Deferred for now
(instrumenting a parallel-signing loop in the critical signing path is intricate); the
renderer's `@bn bar` path is ready and its parser is hardened (`_int` clamps untrusted
counts — a bad `done=`/`total=` must not crash the report). **Never emit a bar for
work without a real count** — opaque steps spin (rule 6).

# Part 2 — how a script is shaped

Part 1 is what a script *looks* like. This is what it *is*: where its constants
live, how it decides, what its exit code means, and how a test proves any of it.
It was settled while building the release chain (`scripts/release.sh`,
`verify-channels.sh`, `check-release-ready.sh`, `check-doc-surfaces.sh`,
`check-dep-drift.py`) and is written down because every rule below cost a real
incident — `docs/release-premortem.md` replays them.

## Identity lives in `scripts/project.conf`, never in a script

Project-specific literals — package name, repo, tap, site, version file, derived
URLs, workflow filenames — are constants in one sourced file. Not a plugin
system: there is one project. It exists because ~14 literals across six scripts
had already drifted into three spellings of the same URL, and because a second
project should be a copy of that file rather than a fork of the scripts.

**`CHANNELS` is the abstraction that earns its keep.** Which channels a project
ships on is the whole difference between a CLI (`pypi homebrew snap`), a Mac app
(`testflight dmg`) and a hybrid that is both. `verify-channels.sh` iterates it
and calls `probe_<name>` per entry, so removing a channel removes its probe, its
verdict and its row. A channel listed with **no** probe is a hard error, not a
skip — otherwise it is a channel silently unchecked, which is the defect this
whole body of work exists to prevent. A channel that genuinely cannot be probed
from a dev machine is *named* in `CHANNELS_UNPROBEABLE` and reports `skipped`
with a reason, never omitted.

## Probes are tri-state, and "I can't probe this" is itself a claim

> A successful probe wins. An unsuccessful probe wins over nothing.

`curl` writes `000` on a connection failure, and `[ "$code" = 200 ]` reads that
as *not published* — manufacturing a false conclusion from a network fault.
Every probe returns **ok / bad / unreachable**, and `unreachable` never rolls up
as pass (`rollup()` accepts `ok` and `skipped` only). `verdict_http` is the
shared shape; don't re-derive it per channel.

`release.sh`'s `probe_done` carries the same distinction one level further, as
exit status: `0` done · `1` probed and absent · **`2` no probe exists from
here**. Collapsing 1 and 2 meant a resume could re-perform an irreversible act
because "I didn't look" read as "it isn't there".

Two corollaries the log paid for:

- **Match on boundaries, not substrings.** `0.28.10` satisfies a naive test for
  `0.28.1`, and `location:.*0\.28\.0` treats the dots as wildcards. Probe the
  versioned filename with `grep -F`, and bound the token so a trailing digit or
  `.<digit>` disqualifies it (`_token_present` in `verify-channels.sh`).
- **"There's no endpoint for this" is usually false.** There is no row that
  says *read the workflow conclusion instead*; every channel has an HTTP
  endpoint behind whatever CLI normally reads it.

## Exit codes are a vocabulary, not a boolean

A caller chains on these, so each number has to mean one thing:

| | |
|---|---|
| `0` | ready / verified / complete |
| `1` | not ready, a step failed, or a channel is not on this version |
| `2` | usage error, or another run holds the lock |
| `3` | stranded — started, outcome unrecorded, never auto-advanced |
| `75` | `EX_TEMPFAIL` — every act is done, verification is pending |

`75` is the one worth copying. `release.sh run` is a launcher, not a foreground
poll: after the tag lands, PyPI, the GitHub Release, Homebrew and Snap are
legitimately absent for ~40 minutes. Kept distinct from `0` so
`release.sh run … && deploy-website` cannot fire on a release that has not
published yet. A script that returns `0` for "probably fine" has no way to say
"done, but don't act on it".

## The pure/impure split, and the sourcing seam

Every decision a script makes lives in a `verdict_*` function above a guard:

```bash
[ "${RELEASE_LIB:-0}" = "1" ] && return 0 2>/dev/null
```

Above it: pure functions, no I/O, the whole risk surface. Below it: the driver.
A suite sources the file with the flag set and drives every worst case with
synthetic input — no network, no git, no release. The four in use are
`RELEASE_LIB`, `VERIFY_CHANNELS_LIB`, `CHECK_RELEASE_READY_LIB` and
`DOC_SURFACES_LIB`; a new decision-bearing script gets its own.

**Testability seams are overrides that make a claim checkable, not features.**
They must be inert when unset and documented as seams where they're read:
`BN_BIN` (point the doc gate at a fake CLI so its own failure path fires),
`RELEASE_STEPS_FILE` (substitute a synthetic step table so `run` is driven end
to end without performing a release). Both are how a suite proves the *driver*,
not just the helpers — `test-release-e2e.sh` found two real bugs that way that
no pure-function test could reach.

## Data tables: put the command last

`release.sh`'s step table is `id|label|kind|est|tier|consequence|COMMAND`, and
the command is last **because `IFS='|' read` gives the final variable the line's
remainder**. A pipe inside a command would otherwise spill into the next field
and silently drop the step. Any `|`-delimited table with a free-text column has
this shape; put the free-text column last.

## The harness: `scripts/test-lib.sh`

`ok` / `bad` / `head_` / `eq` / `finish`, plus two things worth knowing:

- **`meta_check`** — proves `eq()` can actually fail. A suite whose assertions
  cannot fail is decoration, and that is not hypothetical: an earlier harness
  decremented the counter for a deliberate failure, so a suite with exactly one
  *real* failure reported zero and exited green.
- **`guard_tracked <paths>`** — restore tracked files on **any** exit path,
  including a signal. Use it in any suite that mutates the tree to prove a gate
  fires. `test-doc-surfaces.sh` corrupted the man page exactly once, when a
  batch timeout killed it mid-injection, and the next gate run reported a gap
  that did not exist. A test that damages the tree when interrupted is worse
  than no test, because the damage then reads as a finding.

  Two details in it are load-bearing and were both wrong in the first draft.
  **The `git checkout` is `-C`-anchored**, because from a cwd outside the work
  tree it fails and the `|| true` that keeps the trap quiet swallows that — a
  restore that silently does nothing, wearing the costume of the fix. **And the
  signal arms `exit`**: a trap that only restores lets bash *resume* after the
  handler returns, so the suite carries on, re-injects, and is then SIGKILLed
  with a dirty tree — which is the original incident, reproduced by its own
  remedy. It also defines `restore_guarded`, so a suite that restores mid-run
  (to assert the gate goes green again) has one spelling of the restore.

The harness exists because five suites carried a byte-identical copy of the same
four functions, and the SIGTERM-safe restore added to one of them was never
propagated to its structural twin. **Scaffolding that is copied is scaffolding
whose fixes do not travel.**

## Shell traps this codebase has already paid for

Each of these produced a wrong answer that looked right. The tell matters more
than the rule.

- **Redirect, never pipe, when you need the exit code.** A pipeline's status is
  its *last* stage without `pipefail`, so `pytest … | tail` reports `tail`'s
  success. In a step runner: `eval "$cmd" > "$LOG" 2>&1`, then read `$?`.
- **…and `pipefail` + `grep -q` SIGPIPEs the producer.** `grep -q` exits on its
  first match, the upstream `curl`/`printf` dies with `141`, and `pipefail`
  hands you the 141. Use a herestring: `grep -qE -- "$pat" <<<"$body"`.
- **`cmd && ok "passed"` is a gate that cannot fail.** POSIX exempts the left
  operand of `&&` from `errexit`. An assertion is `cmd || die "…"`, never
  `cmd && ok`.
- **Background the step so traps fire.** Bash defers a trap until the current
  *foreground* command returns, so SIGTERM during a 30-minute build does
  nothing. Run it with `&`, `wait "$pid"`, and have the handler `pkill -TERM -P`
  the child.
- **Python's `finally` does not run on SIGTERM; bash's `trap EXIT` does.** A
  Python suite that mutates the tree needs an explicit `signal` handler — the
  `try/finally` you'd reach for by reflex is not equivalent.
- **`grep -c . || echo 0`** prints the count *and* the fallback when the count
  is zero, because `grep` exits non-zero on no match. An anti-trivial-pass guard
  written this way is itself broken.
- **zsh does not word-split unquoted variables.** `for f in $LIST` iterates
  once, over the whole string, and reports success having done nothing.

## Proving portability, rather than reasoning about it

Parts of this chain are meant to run anywhere, and BSD-vs-GNU divergence is not
something to settle by argument. One container settles it in about ninety
seconds:

```bash
docker run --rm -v "$PWD":/src:ro ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  apt-get install -y -qq git curl python3 procps ca-certificates >/dev/null 2>&1
  git config --global --add safe.directory "*"
  git clone -q /src /work && cd /work
  for t in scripts/test-*.sh; do bash "$t"; done'
```

**Mount read-only and `git clone` inside the container.** Several suites mutate
tracked files to prove a gate fires; a read-write bind mount lets a
container-side abort damage the host tree, and the clone also gives you a
committed-state run, which is what CI would actually see.

**Two traps in doing it, both hit 24 Aug 2026.**

1. **A clean container has no `user.email`, so `git commit` fails.** Any sandbox
   built with `git init && git commit --allow-empty` then has no HEAD, and
   assertions comparing against `git rev-parse HEAD` compare against the literal
   string `HEAD`. Four failed this way and cleared the instant an identity
   existed. The danger is *which* four: they were regression pins for an
   unrelated fix, so a clean runner reports a false regression rather than a
   missing config.
2. **An interactive shell's `grep` may not be the script's `grep`.** Here the
   Bash tool resolves `grep` to `ugrep` while a script gets `/usr/bin/grep`, so
   a one-liner typed to debug a script need not behave like the script.
   `command -v grep` printing a bare name rather than a path is the tell.

Measured portable and worth not re-deriving: `pkill -P` / `pgrep -f`,
`sed 's/\x1b\[…//'` (both seds take `\x` escapes), `date -u +%Y-%m-%dT%H:%M:%SZ`,
and POSIX test stubs under dash (Ubuntu's `/bin/sh`). The only BSD-only calls in
the chain are `date -j -f` (GNU has no `-j`) and `stat -f%Lp` (GNU is `-c%a`),
both inside the macOS-channel block. `docs/design-release-machine.md` §20 has
the full account.

## The defect class all of this exists to prevent

**A check that reports success while seeing nothing.** It appeared nine times
during this work, four of them in code written that same hour to prevent it: a
doc gate that enumerated 2 of 25 flags and passed; a probe matching `0.28.1`
against a page advertising `0.28.10`; a probe reading a 404 page as content; a
suite whose own deliberate-failure guard could not fail. (`.bn-export-mode`'s
CSS gate is the same shape a directory away — `tests/test_export_css_selectors.py`
and the root `CLAUDE.md` carry that one.) The rule that catches it is not "test
the gate" but **"prove the gate fails on the thing it exists to catch"** —
inject the defect, assert the red, restore. Every `scripts/test-*` suite that
guards a gate does this, and it is why they are worth their weight.

## See also

- Implementation: `build_report.py` (renderer — `--demo` / `--demo-fail` self-tests)
  + `report.sh` (emitter helpers + `bn_autowrap`). `build_report_mock.py` is the
  original static design mock (`--frame`, `--fail`, `--svg <path>`).
- Glyph/colour source of truth: [`bristlenose/ui_kinds.py`](../../bristlenose/ui_kinds.py).
- CLI output canon: [clig.dev](https://clig.dev) — human-first, honest progress,
  colour off when not a TTY.
- [`README.md`](README.md) — the per-script index this style applies to
  (`desktop/scripts/`), and [`scripts/README.md`](../../scripts/README.md) for
  the release-and-gate half.

Part 2's sources, in the order you'd read them:

- [`scripts/project.conf`](../../scripts/project.conf) — the constants, with the
  reasoning for each inline.
- [`scripts/release.sh`](../../scripts/release.sh) — exit-code vocabulary, the
  pure/impure split, the step table, `probe_done`'s third state.
- [`scripts/verify-channels.sh`](../../scripts/verify-channels.sh) — the
  tri-state probe rule and `_token_present`'s boundary matching.
- [`scripts/test-lib.sh`](../../scripts/test-lib.sh) — the harness, `meta_check`,
  `guard_tracked`.
- [`docs/design-release-machine.md`](../../docs/design-release-machine.md) — the
  architecture these conventions serve, and
  [`docs/release-premortem.md`](../../docs/release-premortem.md) — the incidents
  that produced each rule, replayed against the current scripts.
