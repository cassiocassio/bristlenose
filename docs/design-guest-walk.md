---
status: slices 0–1 built 20 Oct 2026; slices 2–5 proposed; the QA journey (slices 6–14) proposed 24 Oct 2026
last-trued: 2026-10-20
trued-against: experiments/guest-walk @ 892baba1, desktop/scripts/guest-matrix.sh and build-dmg.sh @ 714e5348
---

# Guest walk — the nightly click-through, productionised

*A plan, written 20 Oct 2026. Every measurement is dated; anything undated is a
proposal. Slices 0 and 1 were built the same day (see § Review); 2–6 are not.*

## What exists

`experiments/guest-walk/` (committed 20 Oct 2026, `892baba1`) walks the shipped Mac
app inside a clean macOS 27 tart guest and diffs every screen against another walk.
`walker.swift` drives the app by accessibility element name, dumps the menu tree as
JSON lines, screenshots every window and pixel-diffs PNGs under reasoned masks (pink
for a change, hatched for a mask). `walk.sh` asserts the state each step should produce
and halts loudly with `verdict.txt`. `night.sh` clones the base `walk27-base`
(Cirrus `macos-golden-gate-vanilla:27.0`, SIP on, only the tart guest agent added, with
Accessibility, Screen Recording and Full Disk Access granted once by hand), walks, and
deletes the clone. The analysis run uses the host's Ollama through an ssh reverse
tunnel (`tunnel.sh`). `report.py` builds the morning page after
`docs/mockups/guest-walk-diff.html`. Measured: 22 steps, 26 captures, about 4 min a
night including clone, boot and teardown; two unattended nights with no prompt;
between two unchanged nights 5 of 26 screens differed, four of them model output and
one the Welcome animation. Vision OCR fails inside a 27 guest and works in 26.6 and on
the host, so the Screens lens cannot be OCR'd in the guest. `README.md` and
`COVERAGE.md` there are the spike's record and stay where they are.

## Decisions (settled 20 Oct 2026)

1. The walk is a second job in `desktop/scripts/guest-matrix.sh`, after the Swift
   suite, under the same gates plus "Iona attached" and "Ollama answers". A release
   running or pending skips the night; Iona absent is a normal skip. QA, subordinate
   to the dev/release cycle.
2. Each night stages that night's build: a signed Developer-ID build of committed HEAD
   if it can run with no human present; otherwise an explicit fallback, named in the
   morning line.
3. Baselines live on Iona; tonight is diffed against the last completed walk with no
   click; history kept; no Accept button in v1.
4. A frozen, already-analysed project makes lens screens deterministic, made once on
   the host (where Vision works, so it carries screen text), refreshed deliberately.
5. Halt on any foreign window at every step; the Welcome cards respect Reduce Motion
   and the guest has it on, so the animation masks go.
6. Then `COVERAGE.md` stages, one at a time over a week or more. Sign-in integrations
   are out of v1.

## Architecture

### Where the code goes

`desktop/scripts/guest-walk/`, beside `guest-matrix.sh`, which calls it. Three reasons.
`experiments/` is excluded from `ruff check` (`pyproject.toml:239`) and reads as
throwaway; a nightly job's code is not. The gate-policy rule in the root `CLAUDE.md` —
a script with no caller is not a gate — argues for the caller and the callee sharing a
directory, as `test-swift.sh` and `guest-matrix.sh` do. And `report.py` becomes a
tested Python module under `tests/`, which `experiments/` cannot host. What moves:
`walker.swift`, `walk.sh`, `tunnel.sh`, `g.sh`, `pull.sh`, `run_summary.py`,
`report.py`, `fixture/`. `night.sh` becomes `guest-walk.sh` (below); `prep-base.sh`
moves too, since the base image is part of the job. `vision-probe.swift` stays in the
spike as evidence. `experiments/guest-walk/README.md` gets one line pointing here.

### How guest-matrix.sh calls it

`guest-matrix.sh` keeps what it owns: the tick, the window, the gates, the lock, the
night's one line, the notification. After the `for vm in $GUESTS` loop
(`guest-matrix.sh:429-437`) it runs `run_walk`, which calls
`desktop/scripts/guest-walk/guest-walk.sh run <night-dir>` under `with_timeout`
(`:259-266`) and appends the walk's one-line verdict to the night's line. The walk
script owns clone, boot, stage, walk, pull, report and teardown, and prints its verdict
as `GW-*` protocol lines the way the guest script prints `GM-*` (`:198-224`), so
`summarise_walk` is pure and testable like `summarise_guest` (`:232-255`).

New subcommands: `guest-matrix.sh walk --now` runs only the walk job under the gates
(a trial, filed as `trial-…` like `run --now`, `:365`), and `guest-matrix.sh walk open`
opens the latest page. `guest-walk.sh` has `check | build | stage | run | summarise |
prune`, each a seam the suite can drive alone.

### The walk job's own gates and timeouts

Asked after the suite, in this order, each a named reason in the line:

- **release** — `release_engaged` (`scripts/lib-release-state.sh:65`) is asked again
  here, and again before the clone. The suite takes 10–15 min and a release can start
  inside that; a verdict about the world at 23:00 is not one about 23:20
  (`docs/design-release-principles.md` §17, §20).
- **Iona** — `$GM_IONA/guest-matrix.conf` names `WALK_BASE` (machine specifics stay
  on the drive, `:39-40`), and `tart list` shows it.
- **no guest running** — the suite's loop stops each guest (`stop_guest`, `:272-283`);
  assert it anyway. Any leftover `walk-*` clone from a killed night is deleted first.
- **Ollama** — `curl -s -m 3 http://127.0.0.1:11434/api/tags` on the host, the same
  probe `tunnel.sh:16` makes. Not answering is a named reason, not retried: the
  night's report exists once the suite ran, and a later tick does not repeat a
  finished night (`:369-373`). One line a night.
- **time** — the walk does not start after `GM_WALK_LATEST_START` (05:00): a build
  and a walk started at 05:25 would be running when the owner sits down.

Timeouts, all env-overridable in the `GM_*` style: build 30 min (the `.dmg` lane's
archive+export+sidecar portion is well under that; `docs/release-log.md` has
build-dmg at 560–908 s *including* notarisation), boot 300 s (reuse
`GM_BOOT_TIMEOUT_S`), walk 20 min (measured 4; the run inside is already bounded at
10 min, `walk.sh:158-163`), stop 90 s. A timeout is "no verdict", never a result.

### The two-guest limit

Virtualization.framework and the EULA allow two macOS guests
(`docs/design-test-environments.md` §3.1). The suite runs its guests one after another
and stops each; the walk clones its own guest after the loop and deletes it on every
exit path (the `trap cleanup EXIT` in `night.sh:22-23`, moved into `guest-walk.sh`, plus
`guest-matrix.sh`'s own `stop_guest` trap knowing the clone's name). Never alongside
the suite: at most one guest is up at any moment of the night.

### Baselines on Iona

```
/Volumes/Iona/tart/walks/                 host data; NOT under share/, which guests mount
  2026-10-20/                             one walk: NN-*.png, NN-*.menus.jsonl, owners/,
                                          walk.log, verdict.txt, run-end.json,
                                          build.txt (sha, version, build number, origin),
                                          index.html + img/ (the page)
  2026-10-21/
  latest   -> 2026-10-21                  the last walk, whatever its verdict
  baseline -> 2026-10-20                  the last COMPLETED walk; advanced only by a
                                          walk whose verdict.txt starts COMPLETED
```

Tonight is diffed against `baseline`; after a completed walk, `baseline` moves to
tonight (decision 3). A halted walk is kept, diffed against the baseline as far as it
got (missing screens are a state `report.py` already has, `:118-120`), and does not
become the baseline. The first night has no baseline: the page says so and every
screen is "new". Retention: `guest-walk.sh prune` deletes night directories older than
60 days except the two link targets. Measured 20 Oct 2026: a night's page with its
image copies is 12 MB (`experiments/guest-walk/out/27`), so 60 nights is under 1 GB on
a drive with 1.1 TB free. The staged app tarball is 1.2 GB
(`share/bn-walk/Bristlenose.app.tar`); only the newest is kept.

### The morning line

The suite's line is unchanged and the walk is appended after ` · walk: `:

```
2026-10-21 · tested 714e5348 (3 desktop commits since 71844637) · ✓ 15.7.3 1811 passed · ✓ 26.6.2 1811 passed · walk: 2 of 26 screens changed, 0 menu changes, vs 20 Oct · built tonight 714e5348
2026-10-22 · … · walk: halted at step 9 (Open panel up) · built tonight 9a1c2f30
2026-10-23 · … · walk: not run (Ollama not answering)
2026-10-24 · … · walk: no verdict (the guest never reported) · walked release 0.42.0 (built 20 Oct, expires 19 Nov)
```

Four shapes: `N of M screens changed` · `halted at step K (<description>)` ·
`not run (<reason>)` · `no verdict (<reason>)`, always followed by which build was
walked. The segment never contains `✓`, `✗`, `skipped:` or `error:`: `cmd_report`
classifies the whole line by those tokens (`guest-matrix.sh:347-353`) and `cmd_run`
decides whether a night is finished by `skipped:` (`:371`), and the walk must not
change either verdict — a halted walk is a reason to look, not a red suite, and the
release preflight row (`scripts/check-release-ready.sh:534`) stays about the suite. A
test pins the vocabulary.

### The page, and the morning

`report.py` writes `index.html` into the night's directory; `latest/index.html` is the
page to open. `guest-matrix.sh walk open` runs `open` on it. The notification
(`:330-335`) carries the walk segment; `display notification` cannot act on a click, so
the path to the page is in the line and in `~/Library/Logs/bristlenose-guest-matrix/latest.txt`.
If Iona is detached in the morning there is no page, and there was no walk.

## The build question (decision 2)

Read, not run, 20 Oct 2026: `desktop/scripts/build-dmg.sh` @ `714e5348`.

**A full `build-dmg.sh` cannot be the nightly build.** It is `set -euo pipefail` (`:44`)
and its preflight dies without the notarytool keychain profile (`:250-253`), then
spends 1–15 min in Apple's notarisation queue (`:177-178`) and creates the image with
`create-dmg` (`:478`), which drives Finder by Apple events. That last one is the
decisive problem: Automation permission is granted per responsible app, so under the
*Bristlenose Guest Matrix* applet it would raise a dialog at 02:00 and wait for a click
(`docs/design-release-principles.md` §10 records the 0.29.0 `-1743` stop). None of
steps 7–10 is needed to walk the app.

**What the walk needs is steps 2–5**, and those can run with no human:

- step 2, `_BRISTLENOSE_RELEASE=1 ensure-sidecar.sh` under the Developer ID identity
  (`:306-307`; the release flag is what authorises a real identity,
  `ensure-sidecar.sh:97`). Signing ~220 inner Mach-Os with the Developer ID key is
  silent once *Always Allow* was granted to that key, which
  `docs/design-dmg-build.md` § Prerequisites records as done;
- step 3, `xcodebuild archive` with development signing and the `DEVELOPER_ID_BETA`
  condition (`:379-395`);
- step 4, `-exportArchive -allowProvisioningUpdates`, where Xcode mints the Developer
  ID profile itself (`:402-409`); this needs network and Xcode's stored Apple ID
  session, and fails with a log, not a dialog;
- step 5, `codesign --verify --deep --strict` and `check-release-binary.sh`
  (`:422-432`).

The result is a Developer-ID-signed, sandboxed `.app` with the alpha channel's 30-day
clock starting tonight — the same binary a `.dmg` would carry, minus the ticket. It is
not notarised, and that is fine where it runs: the tarball is untarred inside the guest
by `tart exec`, so no quarantine attribute is ever set and Gatekeeper never assesses it
(the spike launched the 0.42.0 export this way). **Checks to run before trusting this,
in a daytime trial, not at night:** `spctl --status` in `walk27-base` (`prep-base.sh:57`
prints it; the value is not in the repo); one launch of an un-notarised export in a
clone; one `-exportArchive -allowProvisioningUpdates` from a shell with no Xcode window
open; and one `ensure-sidecar.sh` under the Developer ID identity from a `launchctl`
context, because the keychain *Always Allow* was granted to a terminal session.

**Build in a separate local clone, not the main checkout.** `guest-matrix.sh:34-36` is
explicit that the night tests the committed HEAD, never a working tree a session may
be half-way through; `xcodebuild` archives whatever is on disk. And `ensure-sidecar.sh`
treats an identity transition as a reason to rebuild PyInstaller from scratch
(`:149-152`): a nightly Developer-ID build in the dev tree would leave the sidecar
Developer-ID-signed for the owner's next ad-hoc Cmd+R, which rebuilds it again
(~10 min), and the next night flips it back. A clone at
`~/Library/Caches/bristlenose-guest-walk/src` (`git clone --local`, the pattern the
root `CLAUDE.md` gives for a release freeze) holds its own `.venv-sidecar`,
`frontend/node_modules`, fetched ffmpeg and DerivedData — about 5 GB, rebuildable — and
`guest-walk.sh build` fetches the main checkout's HEAD sha into it and builds there. The
gitignored inputs that break worktrees (`desktop/CLAUDE.md`, the first-build
`GeneratedBuildInfo` trap) are set up once by `guest-walk.sh prepare` and then persist.

**Reuse, not a copy.** The archive/export invocation encodes four verified dead ends
(`docs/design-dmg-build.md` § The signing flow). Proposed: `build-dmg.sh --export-only`,
which skips the `create-dmg` and notary preflight lines (`:247-253`), runs steps 2–5
with `SKIP_SWIFT_TESTS=1` (the walk is not a shipping gate; the suite just ran in two
guests), and stops after `check-release-binary.sh`, printing the exported `.app` path.
`scripts/test-dmg-lane.sh` gains a case. The alternative — a second script carrying the
same `xcodebuild` lines — is the copied scaffolding `REPORT-STYLE.md` § The harness
warns about.

**The fallback, named in the line.** If the identity is not configured
(`.ship-local.conf`, `build-dmg.sh:58-61`), the tree cannot be fetched, or the build
fails or times out, the walk uses, in order: the newest tarball it staged itself
(`share/guest-walk/app-<sha>.tar`, content-named per `guest-matrix.sh:419-422`); else
the `.app` inside the last release's `.dmg` (`desktop/build/Bristlenose-0.42.0.dmg`
today). The line says `built tonight <sha8>`, `last built <date> <sha8>` or
`release 0.42.0 (built 20 Oct, expires 19 Nov)`. The expiry matters: a `DEVELOPER_ID_BETA`
build stops working 30 days after it is cut (`AlphaBuild.swift:32`), shows an `Alpha · Nd`
pill in its last 7 days (`AlphaExpiryPill.swift:18-23`), and an expired one presents an
alert and quits — a foreign window the walk will halt on, correctly. The walk also
checks the build it got: the About window's tree carries the commit (`BuildInfo.swift:43-45`),
and `walk.sh` asserts it equals the staged sha, so a stale tar can never be reported as
tonight's build.

## The frozen project (decision 4)

**Made on the host** by `desktop/scripts/guest-walk/fixtures/make-frozen.sh`: a folder
holding the smoke transcript (`fixture/Session 1.vtt`) and the screens fixture
(`fixture/make.sh`: a 36 s three-page video with its transcript, 75 KB), analysed once
with `bristlenose run` under a named provider and model, with the Screens lens's OCR
done here where Vision works. The output folder, `bristlenose-study.txt` marker and
`.bristlenose/` database travel with it. `FROZEN.txt` in the folder records provider,
model, Bristlenose version, commit and date, and the page prints it.

**Where it lives:** `/Volumes/Iona/tart/share/guest-walk/fixtures/frozen-project/`,
generated, never committed (the recipe is). The walk copies it into the guest's
`~/Documents` (`night.sh:30` already does this for the screens fixture) and opens it the
way a researcher opens an existing study — the exact menu item is read from the menu
dump, not assumed — then asserts no run starts (no new `run_started` in the project's
`pipeline-events.jsonl` within 20 s) and that the sessions count is on screen.

**Two kinds of screen from then on.** Lens screens are captured on the frozen project
and diffed: pink means the UI changed. The real run on the smoke fixture still
happens, via the host's Ollama, and is checked on its terminus event and counts
(`walk.sh:156-165`); its outcome and lens screens are captured but marked
*informational* in `report.py` — shown, never counted as changed.

**Refreshed deliberately, never on a schedule.** When a lens's data model or the
report's import changes so that every lens is pink and the pink is content, not chrome,
the owner re-runs `make-frozen.sh`; `FROZEN.txt` carries the reason. The database is
migrated on open by the serve as any old study is, so a schema migration alone is not
a reason.

## Slices

Each slice: what changes, files, how it is tested without a VM, and its done-check.
`scripts/test-guest-matrix.sh` is the pattern for the shell: the real script against
fake `tart`/`pmset`/`ps`/`sysctl` on PATH in a throwaway repo, mutants proven red.

### Slice 0 — the gate that has stopped every night since 8 Oct (precondition for tonight)

Measured 20 Oct 2026: 11 of 12 nights since the first run skipped with
`busy: playwright running` (`~/Library/Logs/bristlenose-guest-matrix/reports/`), and
`ps -axo command=` today shows four `npm exec @playwright/mcp@latest` processes — the
Playwright MCP server that Claude Desktop sessions keep alive, matched by the
`play[w]right` pattern at `guest-matrix.sh:151`. It is not a test run. Narrow the
pattern so `@playwright/mcp` and `playwright-mcp` do not count while
`node_modules/@playwright/test` still does; add the two cases to
`test-guest-matrix.sh` beside the `pytest.ini` one (`:126`). Without this, no slice
runs tonight. Done-check: `guest-matrix.sh check` says `go:` with the MCP servers
running and Iona attached.

### Slice 1 — tonight: walk the 0.42.0 export, last-night baseline, morning line

- **Changes:** move the spike's code to `desktop/scripts/guest-walk/`; `night.sh` becomes
  `guest-walk.sh` with the subcommands above; `guest-matrix.sh` gains `run_walk`,
  `summarise_walk`, the walk gates, `walk --now` and `walk open`; `report.py` takes the
  baseline from the `baseline` link and writes `build.txt` into the night; the walker is
  built on the host into `share/guest-walk/walker-<sha8 of walker.swift>` and a host
  copy for `diff`. The staged app is the existing 0.42.0 export tarball
  (`share/bn-walk/Bristlenose.app.tar`, 20 Oct 10:33) renamed by its sha. Masks move
  from the dict at `report.py:27-40` to `masks.json` with reasons, so the page and the
  tests read one file. `guest-matrix.conf` on Iona gains `WALK_BASE=walk27-base`.
- **Tests:** `scripts/test-guest-walk.sh` — fake `tart`, `ssh`, `rsync`, `curl`, `swiftc`
  and a fake `walker` that prints canned frames; cases for every `not run` reason, a
  completed walk advancing `baseline`, a halted walk not advancing it, the first night
  with no baseline, a hang timing out as `no verdict`, the clone deleted on SIGTERM, and
  the vocabulary rule (no `✓ ✗ skipped: error:` in any walk segment). `test-guest-matrix.sh`
  gains: the line carries the walk segment; `report`'s exit code is unchanged by a halted
  or not-run walk; a running guest after the suite is a named reason. `tests/test_guest_walk_report.py`
  — `menu_diff`, `phase_of`, `stem`, verdict parsing and the morning-segment composer
  as pure functions; the diff path with a fake walker binary (`WALKER` env seam) over
  three tiny PNGs the test writes itself.
- **Done-check:** a daytime `guest-matrix.sh walk --now` (idle gate overridden) leaves a
  `trial-…` line with a `walk:` segment and a page under `walks/`; the first scheduled
  night produces `walk: … new … no baseline` and the second `walk: N of 26 screens changed`.

### Slice 2 — the nightly build

- **Changes:** `build-dmg.sh --export-only`; `guest-walk.sh prepare` (the clone and its
  inputs) and `guest-walk.sh build` (fetch HEAD, build, verify, tar, stage, drop the
  previous tar); the fallback ladder and its wording; the About-sha assertion in
  `walk.sh`; the About window's commit line masked with the reason "the commit, by
  design". Widen the night's change gate: the walk's paths are `desktop/ bristlenose/
  frontend/`, so a frontend-only commit night runs the walk and not the suite, each job
  keeping its own `last-*-sha` (today `gate_changed` on `desktop/ bristlenose/locales/`
  ends the night for both, `:101-113`).
- **Tests:** `test-dmg-lane.sh` — `--export-only` stops after step 5 and never calls
  `create-dmg` or `notarytool` (stubs that fail loudly if called). `test-guest-walk.sh`
  — identity absent → fallback named; build fails → fallback named; tar named by sha,
  previous removed; the staged sha and the About sha disagree → halt. `test-guest-matrix.sh`
  — a frontend-only commit runs the walk only.
- **Done-check:** the morning line reads `built tonight <sha8>` and the About screen is
  pink exactly once (the night the mask lands, never again).

### Slice 3 — halt on any foreign window

- **Changes:** `walk.sh`'s `shot()` runs `walker owners` (`walker.swift:301-313`) and
  halts on any on-screen window whose owner is not on the allowlist; the dump is saved
  per step. The allowlist comes from a measured clean walk, not from memory: the
  sandboxed Open panel is its own process (`walker.swift:204-205`), and the PoC's one
  prompt came from Notification Center. `halt-screen.png` and the owner line go in
  `verdict.txt`.
- **Tests:** the classifier as a function with canned `owners` output in
  `test-guest-walk.sh`: allowlisted owners pass, a `UserNotificationCenter` banner halts,
  a `CrashReporter` window halts.
- **Done-check:** in a `KEEP=1` clone, `tart exec … osascript -e 'display dialog "x"'`
  mid-walk produces `HALTED step N: foreign window 'osascript: x'` and the screenshot.

### Slice 4 — Reduce Motion

- **Measure first.** The app already reads `accessibilityReduceMotion`: `WelcomeHomeView.swift:240`
  and `:259-260` feed it to `WelcomeBaton.setReduceMotion` (`WelcomeBaton.swift:86-89`),
  which stops the choreography; the webview illustrations take `reduce`
  (`WelcomeIllustrations.swift:53, :211, :468`). So the product change may be nil.
  Turn Reduce Motion on in `walk27-base` by hand (System Settings ▸ Accessibility ▸
  Display; SIP is on, so a written preference is not trusted until a reboot shows it
  held), walk the same build twice with the two `first-launch`/`consent-accepted`
  animation masks removed from `masks.json`, and read the count.
- **Changes:** whatever still moves is the product change, fixed at its site in the
  Swift app, with a `BristlenoseTests` case if it is a decision and not a view. The
  focus-ring mask is timing, not motion, and stays with its reason.
- **Done-check:** 0 of 26 screens changed between two walks of one build, with the
  animation masks gone.

### Slice 5 — the frozen project

- **Changes:** `fixtures/make-frozen.sh`; the walk's open-existing-study steps; the
  *informational* state in `report.py`; the page prints `FROZEN.txt`.
- **Tests:** `test_guest_walk_report.py` — informational screens are shown and never
  counted; `test-guest-walk.sh` — a run that starts on open is a halt.
- **Done-check:** every lens screen 0 changed across two nights of one build, pink only
  when a frontend commit landed.

### Slice 6 onwards — coverage, a stage at a time

_Superseded 24 Oct 2026 by [§ The QA journey](#the-qa-journey-proposed-24-oct-2026):
the coverage stages become rows in its inventory, walked in rail order, and the slices
are renumbered there._ As first written: `experiments/guest-walk/COVERAGE.md` stages 2,
3, 5 and 6, in that order, one stage every few nights; a stage is kept only after two
nights at 0 changed on an unchanged build. Stage 4 (video, Screens) runs on the frozen
project's host-read screen text, since Vision fails in the 27 guest. The page gains the
mockup's timing section (per-step durations, tonight vs baseline) when the step count
passes 50.

## The QA journey (proposed 24 Oct 2026)

_A proposal, agreed in outline with the owner on 24 Oct 2026; nothing below is built.
Slices 2–5 above come first._

### Why

By-hand QA had become debt. On 24 Oct 2026 a sweep of one week's sessions found about
180 owed checks. Most had been written as "check by hand: …" at the end of a session,
some copied into one of six trackers and some not, so a set of five report-chip checks
from 20 Oct was found only by accident. Sorted by what they need, 86 of the 106 the
first walk-through had missed are **mechanical** (a state, a count, a menu item, a log
line, a file), 16 are **judgement** (it looks or reads right) and 4 are **physical** (a
lid, a battery, VoiceOver listened to, a Keychain dialog). By driver: 51 can be read
from the Mac app's accessibility tree, 25 driven by Playwright against a serve, 3 by
calling the pipeline or the server directly, 5 belong to the walk as it is, and 22 need
a person. 96 make no real model call.

The machine already exists for the mechanical part: the walker drives the app by
accessibility name, dumps the menus and shoots every window, and the page diffs it in
pink. What is missing is the list it should walk, the order, and a walk that keeps
going.

### What it is, and what it is not

**Parallel and non-blocking.** The journey assumes working software. It is a more
human set of tests, run beside the dev and release cycle, never inside it: no verdict
feeds `check-release-ready.sh`, the release board or a CI job, and no changelog line
waits on it. The gate policy does not apply because nothing blocks. Its output is
triage, not a pass: an urgent patch (lost work, a crash, a fake success), a tweak or an
idea for the forward plan, or a screen that changed on purpose and becomes the new
baseline. Most findings are expected to be the second kind.

**One journey, atomic checks.** A check is atomic: it names what it needs, does one
thing, and gets one result. The run is one journey through one guest boot, in the
order a researcher works: open the app, drop the recordings, analyse, go down the
lenses, export, Settings, quit and relaunch, then the destructive checks. The setup is
paid once; a failure points at one thing.

### The inventory

One file per stop of the journey, under `desktop/scripts/guest-walk/checks/`, tracked.
Each row:

| field | meaning |
|---|---|
| `id` | a stable slug; tests, Playwright specs and the page key on it |
| `stop` | where in the journey it is performed: `launch`, `drop`, `sidebar`, a lens, `export`, `dialogs`, `settings`, `lifecycle`, `destructive`, or a host track (`cli`, `providers`) |
| `checkpoint` | the checkpoint it hangs under (below) |
| `kind` | `mechanical`, `judgement` or `physical` |
| `driver` | `walker`, `playwright`, `python`, `providers-live` or `human` |
| `areas` | the code it covers, as folders, not files (see Selection) |
| `steps`, `expect` | what to do and what should be seen, in plain words |
| `also_look` | a later stop where its effect must be checked (hide a quote on Quotes → Signals) |
| `budget_s` | its time budget, calibrated in the guest |
| `tier` | `baseline` or `feature` |
| `status` | `new`, `passing`, `retired`, `promoted` |
| `source` | the commit, issue or design-doc section it came from |

The coverage states in `experiments/guest-walk/COVERAGE.md` become rows of kind
`judgement` (a capture), so there is one list, not two. Rows are tracked, so each is
screened before it lands: no participant data, no study content, nothing commercial —
functional checks only. The 24 Oct sweep is the seed; its private working copy is
migrated row by row.

**A session adds a row instead of writing prose.** `/end-session`'s "human QA" step
writes inventory rows for the checks a session leaves, so a check can no longer live
only in a closing message.

**Two structural tests keep it honest**, because a gate that matches on a name drifts
when the name moves: every `areas` path exists, and every lens `stop` is a lens on the
rail. The rail order is read from `LensItem.lenses` in
`desktop/Bristlenose/Bristlenose/LensItem.swift`, never restated, so a lens that joins
the rail joins the journey the way it gets its ⌘ number.

### The journey and its checkpoints

The order is the rail's: Project ⌘1, Sessions ⌘2 (transcripts are reached from here),
Quotes ⌘3, Codebook ⌘4, Signals ⌘5, Discussion ⌘6, Screens ⌘7. Inside each lens:
**capture first, then act** — the lens's judgement screens are shot untouched, on the
frozen project, before anything is starred, hidden or edited, so they diff cleanly
night to night; then every action owed in that lens. An effect that shows further
down the rail is checked there; the one that points back up (the Dashboard's quote
count after a hide) is a short return to ⌘1 after the lens pass. Exports follow the
lenses, so they carry the edits just made.

Most checks are leaves. Four are checkpoints, which later checks need:

| checkpoint | its leaves | if it fails |
|---|---|---|
| The app launches and its serve starts | boot, Welcome, the menus on an empty window | no fallback: the journey stops |
| A study is in the sidebar | drops, Add Files, row states | open a ready-made study folder; the drop checks still fail on their own |
| Analysis finishes | every lens, editing, Undo, exports, dialogs | the next provider, then local, then the frozen project |
| Quit and relaunch | state kept (zoom, widths), the queue, a stopped run, a key kept on ⌘Q | a cold launch, marked as such |

So the runner needs no dependency graph: a short list of checkpoints, each with a
fallback, and every check naming its checkpoint.

**Analysis is a set of checks as well as a checkpoint.** Each provider is its own
check — Claude, ChatGPT, Gemini, local — on a small public fixture, so a run costs
pennies. Local runs every walk: it is free, a supported provider, and the walk already
reaches the host's Ollama through `tunnel.sh`. The cloud legs run on the host through
`scripts/check-providers-live.py`, one provider a night in rotation, so no paid key
ever enters a guest. A live run's lens screens stay *informational*, as § The frozen
project already says: models differ, so the live run is checked on the report's shape
(quotes exist, sections are named, every timecode falls inside its session), and the
diffed screens come from the frozen project.

### Results

Five, and the page and the morning line keep them apart:

- **passed**
- **failed**, with its evidence (the screenshot, the tree dump, the log line)
- **passed on a fallback**, naming the fallback ("export: passed, on the frozen
  project, because tonight's analysis failed"). It proves the step works on tonight's
  build, not on tonight's analysis, so it never reads as plain green
- **not reached**, because its checkpoint failed with no fallback
- **timed out** or **not reached (out of time)**, when a budget ran out

A failed assertion no longer halts the walk: `walk.sh`'s `halt()` (`walk.sh:23-29`)
stays for the cases where the screen can no longer be trusted — a foreign window
(slice 3), a dead app, a stale build — and every other step records its result and the
journey carries on. The morning line's vocabulary rule holds: none of these words is
`✓`, `✗`, `skipped:` or `error:`, and a test pins it.

### Selection: baseline, focus, exhaustive

A walk has a time budget (the window `guest-matrix.sh` already owns, with a release
always winning), and fills it in this order:

1. **Baseline** — the standard journey, every walk, never skipped. Kept deliberately
   small: launch, a drop, analysis on local, each lens's core actions, one export,
   Settings, quit and relaunch.
2. **Focus** — every check whose `areas` changed in `git diff` since the last walk on
   this OS, plus every `feature` row not yet passing. A change to a wide area (the
   theme, the locales, a shared store) marks every check that reads it; a dependency
   or Python bump marks everything.
3. **Exhaustive** — everything else, stalest first, until the budget runs out.

**A maximum age is the backstop.** Every check runs at least once every 14 days
whatever changed, because selecting tests by changed code misses what the map cannot
see. The page says why each check ran ("focus: `MiroExportPanel` changed", "stalest:
13 days") so a skipped check is a visible decision, never a gap.

**A feature check has a lifecycle.** New, it runs every walk until it passes (a
judgement one goes on the page once, for the owner's mark). Passed, it either
**retires** — a one-off confirmation such as "Print is gone" — or is **promoted** into
the baseline, when it is worth guarding against regression; a marked judgement screen
becomes a baseline screen. Failing, it stays on the page until fixed or waived.

**Budgets are calibrated, not copied.** A threshold measured on the host ("ready within
15 s", "Stopped within 30 s") flakes in a slower guest. Each time-bound check's
threshold is set from its first walks' measured durations, with headroom, and the page
gains its timing section.

The slow legs do not run every night: a 23-minute dense interview, the paid providers
beyond tonight's one, anything over its own budget — weekly, or on demand.

### Three operating systems, in rotation

The walk runs **27, 26, 27, 15, 27, 26, 27, 15…** (owner, 24 Oct 2026): the latest
every other walk, and the two older systems taking turns between. The rotation counts
walks, not calendar nights, so a skipped night does not skip an OS.

- **macOS 27** (`walk27-base`), half the walks: what most researchers will run.
- **macOS 26** (a `walk26-base`), a quarter: Vision reads shared screens in a 26.6
  guest but not in a 27 one, so this is where the Screens lens gets a live read.
- **macOS 15** (a `walk15-base`), a quarter: the floor, where a 27-only API or layout
  assumption breaks unnoticed. `docs/design-test-environments.md` records three
  sidebar geometries across 15, 26 and 27.

The two new bases are siblings of the 15.7.3 and 26.6.2 images the suite already
runs, made by hand once with the same three grants as `walk27-base`; nothing scripted
may delete them. Each OS has its own baseline, diffed against its own last walk, and
the page names the OS. At about 100 walks a year — release nights and nights without
Iona excepted — that is about 50 on 27 and 25 each on 26 and 15.

**Iona.** The morning line already reports "Iona absent" as an ordinary skip. After two
nights in a row without it, the line says so once, so 100 walks do not quietly become
40.

### Release nights

A release produces exactly the artefact people will install, so on a release night the
walk starts as soon as the `.dmg` exists and walks the `.app` inside it. Today
`guest-matrix.sh` skips a night with a release running; this changes that, on two
conditions: the release always wins (the walk yields CPU, holds no lock, and stops if
the release needs the machine), and it takes a guest only if the release is not using
one, under § The two-guest limit.

### The host tracks

Two tracks run beside the guest, because nothing in the journey depends on them, and
their results land on the same page under the same ids:

- **Playwright**, against a serve on a scratch copy and a spare port: the report's
  web-side checks (chips that fail when the server goes away, Undo offline, hide
  counts, lenses after a run). Specs carry the inventory `id` in their title.
- **Python**, against the pipeline and the server directly, with the model mocked the
  way the 23 Oct measurement of joining files did it: the CLI's `--clean` prompt, a
  fresh start interrupted, `analyze` then `run`, a home-folder refusal, the serve's
  token line. Most of what was filed as "paid, by hand" is free this way.

### Slices

Each slice ships alone and is kept only after two walks at no unexplained change on an
unchanged build.

- **Spike first, daytime, measuring only.** Can the walker drag and drop (it has no
  drag command today: `walker.swift` offers `press`, `action`, `select`, `menu`, `type`,
  `key`, `shot` and the rest)? Can tart checkpoint a guest mid-journey? Does cutting
  the guest's network leave the host alone (if so, the network-change checks become
  walk leaves)? How long does a full journey with analysis take?
- **Slice 6 — the inventory.** The format, the two structural tests, the seed migrated
  and screened, `COVERAGE.md` folded in.
- **Slice 7 — keep going.** Results per check, the five states, `halt()` kept for
  untrustworthy screens only, `report.py` and the morning line.
- **Slice 8 — checkpoints and fallbacks.** The ready-made study, the provider chain, the
  frozen project as the analysis fallback, the cold relaunch.
- **Slice 9 — the journey in rail order.** Capture-then-act per lens, the return to ⌘1,
  exports after the lenses.
- **Slice 10 — selection.** Tiers, budgets, the maximum age, the reasons on the page.
- **Slice 11 — the host tracks.** Playwright and Python results under inventory ids;
  the provider rotation through `check-providers-live.py`.
- **Slice 12 — the other systems.** `walk26-base` and `walk15-base`, the 27/26/27/15 rotation, per-OS baselines, the
  Iona line.
- **Slice 13 — release nights.** Start from the `.dmg`, yield to the release.
- **Slice 14 — the page as triage.** Each finding goes to a patch, to a forward-plan
  row in one step, or to the baseline; `/end-session` writes inventory rows.

**Still for a person,** whatever is built: closing a lid, running on battery, listening
to VoiceOver, answering a Keychain dialog, signing in to real accounts, and the owner's
mark on every judgement screen.

## Risks and failure modes

| Risk | Mitigation |
|---|---|
| A stale build walked as if new | The tar is content-named; the line names origin and sha; `walk.sh` asserts About's commit equals the staged sha and halts otherwise |
| The walk hangs | `with_timeout` round the whole job; the run bounded at 10 min inside `walk.sh`; every walker wait has a deadline; a timeout is `no verdict`, the clone is stopped and deleted by the trap |
| Ollama absent | A named `not run` reason; one line, no retry that night |
| Iona disconnected mid-run | The clone dies with the volume; `tart exec` fails → `no verdict`; the next night deletes any `walk-*` leftover before cloning; nothing on the host depends on Iona except the page |
| Disk growth | 60-night prune excluding the link targets; one app tar; the clone deleted every night; measured 12 MB a night and 1.2 GB per tar against 1.1 TB free (20 Oct 2026) |
| A prompt appears | Grants live in the base image, not the clone (`README.md` § traps); the foreign-window halt names it; the base never updates macOS; `softwareupdate --schedule off` in `prep-base.sh` |
| A release starts mid-walk | `release_engaged` re-asked before the build and before the clone; a release starting during the 4-min walk shares CPU for that long and nothing else — the walk commits nothing |
| The Removable Volumes prompt under launchd | §3.7 lists it as unmeasured and no scheduled night with Iona attached has yet run (reports 8–19 Oct); the first one is watched; the grant goes to the applet |
| Clipboard | tart shares the host clipboard (`report.py:38-40` masks Edit ▸ Paste); set it to a fixed string in the guest before the walk and drop the mask |
| Timezone, locale, relative times | `prep-base.sh` sets Europe/London and en_GB in the base; "3 days ago" strings on the frozen project are masked with the reason until a fixed-clock route exists |
| The fallback build expires | `AlphaBuild.validityDays` is 30; the line prints the expiry; an expired build's alert is a foreign window and halts, which is the right morning |
| The night of 25 Oct 2026 | Clocks go back; the 01:00 tick happens twice and `night()` names the night by `date -v-12H` — the report-file check (`:371`) makes the second tick a no-op |
| Capture size changes with the base | A base rebuild changes the display; `report.py` reports a size mismatch as changed; the first night after a base change is a new baseline, by hand |

## Review, 20 Oct 2026 — what changed before slice 1

Three reviews (correctness, scope, test placement) ran on this plan before any of it
was built. The raw findings are in the maintainer's private notes; what they changed:

- **Slice 1 is smaller than written above.** No `GW-*` protocol: `guest-matrix.sh`
  reads the walk's own `verdict.txt` and the one-line summary `report.py` writes.
  `guest-walk.sh` takes one argument, the night's directory, and has no subcommands;
  no `walk --now`/`walk open`, no `masks.json` (the masks stay a dict in `report.py`,
  which the tests import), no prune (60 nights is under 1 GB on 1.1 TB), no
  `GM_WALK_LATEST_START` (the window is re-asked against the walk's budget).
- **Slice 2 becomes a daytime spike** until its four preconditions are measured; slice
  1 walks the app baked into the base image and names its version and build.
- **Clones are named `gw-<night>`**, a prefix that cannot match the base, and the
  script refuses to delete `WALK_BASE` by name: the base carries three grants a
  person gave by hand.
- **The parent owns the walk's processes.** `tart run` is a tracked child, not
  `nohup`-detached; `guest-matrix.sh` waits in its own loop, polls `release_engaged`
  and the deadline, and stops the walk (`TERM`, whose trap stops and deletes the
  clone) if either fires. A release that starts mid-walk wins.
- **`tart run --no-clipboard`** for the walk clone: tart's clipboard sync is
  bidirectional, so the host's clipboard is neither read into the walk nor written.
- **The segment is scrubbed at runtime**, not only by a test: any `✓ ✗ skipped:
  error:` in it turns it into `no verdict (segment malformed)`.
- **Corrections:** 10 of 11 reports (8–19 Oct) were `busy: playwright`, not 11 of 12;
  Iona was read under launchd on 8 and 18 Oct, so the Removable Volumes prompt is
  measured passable; `AlphaBuild.validityDays` is at `:24`.
- **Tests at the walk seam:** a stub `GM_WALK_SCRIPT` writes `verdict.txt`; cases for a
  completed walk, a halted one, one that died writing nothing, Ollama down, a release
  lock appearing after the gates, the carried-forward line still exiting 3, and the
  vocabulary. `CHANGE=1` stays the instrument's own mutation test, run by hand.

## Not in this plan

An Accept button or accepted-baseline UI (v1 diffs against the last completed walk).
Sign-in integrations: Zoom, Teams, Meet, Miro, the MCP installs. A release-preflight
row for the walk — and, since 24 Oct 2026, any verdict that blocks anything: the QA
journey is non-blocking by design. Peekaboo, Appium or an XCUITest target. An
accessibility audit from the tree dump. Anything on CI runners.

_Moved into the plan on 24 Oct 2026, by § The QA journey:_ the cloud provider calls
(one provider a walk, on the host, through `scripts/check-providers-live.py`), and the
26.6 walk guest (now one of two further bases, 26 and 15).

## Open

Decided here by default, overridable by the owner: `--export-only` on `build-dmg.sh`
rather than a second build script · the build clone under `~/Library/Caches` rather
than the main checkout · the walk guest keeps the window (`tart run` without
`--no-graphics`, the two measured nights) until a daytime trial shows `--no-graphics`
captures · an un-notarised export is expected to launch in the guest (no quarantine via
`tar`), confirmed in the first trial · the change gate widens in slice 2, not slice 1 ·
Ollama down means no walk that night, no retry · the walk never moves `report`'s exit
code · masks live in `masks.json`.
