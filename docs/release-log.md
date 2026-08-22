# Release log

One entry per release, written at the end of `/bn-release`. **Started 22 Aug 2026
at the maintainer's request, to run for the next few releases and then be judged
on whether it earned its keep.**

**What it is for.** Three questions that no single release can answer and a short
run of them can:

1. **How long does a release actually take?** Every estimate in `bn-release`'s
   plan table is a guess someone made once. Measured numbers replace them.
2. **What goes wrong, and does the same thing go wrong twice?** A trap that
   recurs is a gate that should exist. A trap that never recurs was a one-off and
   should not grow ceremony around it.
3. **Is the skill getting better?** Every change to `bn-release` is recorded
   against the release that provoked it, so its edit history reads as a response
   to evidence rather than a pile of good intentions.

**What it is not.** Not a changelog — `CHANGELOG.md` owns what users are told.
Not a post-mortem template. Not a place for anything a user would read. Entries
are terse and factual; if something wants a paragraph of reasoning it belongs in
the design doc it concerns, linked from here.

**Honesty rule for timings.** Mark a number as measured or estimated. Wall-clock
that includes a human deciding something is *not* pipeline time — split it out,
or the averages will slowly describe how fast the maintainer answers questions.

---

## 0.27.0 — 22 Aug 2026 · Tier 1

**Channels:** TestFlight · `.dmg` · PyPI · GitHub Release · Homebrew · Snap edge.
Website deploy owed at close.

**What shipped.** The full fortnight: N windows per study, cloud import from
Teams and Meet, MCP Agents projects register, ingest refusals (27 formats, up
from 16), working Re-analyse, the two `.docx` transcript fixes, Catalan as the
22nd locale. Plus five things that landed after the abandoned tag — the export
read-only leak, a failed analysis surviving relaunch, `transcribe` naming silent
recordings, session duration and timecode agreeing across surfaces, and the
diagnostic popover's reason in all 21 languages.

**The version is not 0.26.0, and that is the headline of this entry.** `v0.26.0`
was tagged at `31932bc2` and left waiting on the publish hold. Thirty-four
commits of real shipped code sat past it — `Cause.reason` on the wire, the
transcribe-only silent-session accounting, the timecode unification, eight
refusal reasons across 21 locales. The claim that they were "docs-only, wheel
byte-identical" was asserted without running the diff and was false. The tag was
deleted, 0.27.0 cut from HEAD, and the 0.26.0 changelog entry **renamed rather
than superseded** — it reached no channel, so it is not a version anyone can
have. Build number 2501 was likewise never spent; 2856 shipped.

### Timing (measured unless noted)

| Phase | Duration | Note |
|---|---|---|
| Preflight (both runs) | ~1 min | second run is the gate |
| `Release to PyPI` run | 131 min total | **~100 of it waiting on the approval hold** — not pipeline time |
| `CI` on main | 37.6 min | 8-cell matrix + e2e |
| `build-all.sh` (successful attempt) | ~11 min | pre-flight 26s · sidecar 8m37s · archive 1m07s · export 1m19s |
| `build-dmg.sh` | ~30 min | includes one Apple notary wait, Accepted first try |
| `upload-testflight.sh` | ~6 min | 15 gate checks, then transfer + ASC confirm |
| `upload-dmg.sh` | ~13 min | rsync measured 12m22s for 651 MB at ~0.7 MB/s |
| Approval → PyPI 200 | ~2 min | far faster than the 25-min budget `release.md` warns of |
| Snap edge workflow | 10.3 min | store showed the new revision a few min after |
| **First preflight → last channel verified** | **~4h35** | includes 3 failed builds and two human decision points |

**Against the skill's estimate of ~1h55.** The overrun is entirely the three
failed builds and the human waits, not slow steps. Each individual step came in
at or under its estimate. Do not raise the estimates; raise the odds of a clean
first build.

### Builds

**Four attempts, three failures — all three real, all three caught by gates.**

| # | Failed at | Cause | Fix |
|---|---|---|---|
| 1 | Pre-flight · window surfaces | Gate asserts an exact source line naming `handshakeProjectPath`; `037b371e` (20 Aug) renamed it plural, so the assertion became unsatisfiable and failed on correct code | `5b1902bf` — repointed, both literals marked load-bearing |
| 2 | Build · supply-chain inventory | `THIRD-PARTY-BINARIES.md` stale; 16 packages had drifted under open version floors | `f6a4c3e4` — regenerated |
| 3 | Xcode archive | `com.apple.developer.associated-domains` in the **Release** entitlements; the MAS profile lacks the capability | Restored Release entitlements to HEAD; local copy backed up |

Failure 1 had been latent for two days and nothing caught it, because the 22 Aug
TestFlight session deliberately cut no build. **A gate is only as fresh as the
last time something ran it.**

### Tricky things

1. **A background task's "exit code 0" is the shell's, not the build's.** All
   five build/upload runs reported exit 0; three had failed outright, printing
   `✗ Build failed`. Reading the notification instead of the log would have
   carried three failed builds forward as successes. **Never report a result
   from a background task's exit code — read the log and quote its verdict.**
2. **`rsync --progress` writes carriage returns, not newlines.** `tail` on the
   raw log shows the *start* of one enormous line, so a healthy upload at 81%
   looks frozen at 0% across repeated polls. Pipe through `tr '\r' '\n'`.
   Nearly caused a second interruption of a working transfer.
3. **`skip-worktree` files are invisible to `git status` AND to the preflight.**
   Both entitlements files are marked `S`, so the preflight reported "working
   tree clean" while carrying the one modification guaranteed to fail the
   archive. Audit with `git ls-files -v | grep '^S'`. **This is a real hole in
   `check-release-ready.sh`** — see Owed below.
4. **A gate asserting an exact source line dies on a rename.** It does not adapt
   and it does not degrade; it becomes unsatisfiable and then accuses correct
   code. Failing loud beats the export-CSS class, which fails silent — but a
   gate that cries wolf is one somebody eventually switches off.
5. **Open version floors let a major arrive during a release.** `openai>=1.50`
   resolved to 3.0.0. Probed rather than reasoned about: every constructor and
   parameter we pass survives, so it was a non-event — but the discovery moment
   was "10pm, mid-release", which is the wrong moment for it.
6. **Ticking the environment in GitHub's approval UI is not approving it.** The
   maintainer reported having approved; `pending_deployments` still showed the
   gate pending and PyPI still 404. The confirm button is **Approve and deploy**.
   Check the API rather than trusting either party's belief.
7. **Perf had been red for four consecutive runs and nobody knew** — including
   on the abandoned 0.26.0 tag. It is deliberately non-blocking (post-merge only,
   by design, to stop runner noise stalling releases), so nothing surfaced it.
   Cause: the export is a single-file build with `inlineDynamicImports: true`
   while locales load via a dynamic-import glob, so **all 22 locales inline into
   every exported report**. `CLAUDE.md`'s note that a new language is
   "size-neutral on the web bundle" is true of `size-limit` and false here.
   Deliberately not re-baselined under time pressure.
8. **"I can't probe this" was itself an unchecked claim.** The close-out table
   asserted that with no `snap` CLI on macOS the workflow conclusion was the only
   available probe. False — `api.snapcraft.io/v2/snaps/info` is public and
   answers from anywhere. Caught by the maintainer. A missing CLI is not a
   missing channel.
9. **A self-imposed `timeout` killed a working upload at ~1%.** No harm, and the
   reason is worth keeping: `upload-dmg.sh` stages to `.upload-*.part` with
   `rsync --partial --inplace` and only swaps atomically at the end, so an
   interrupted transfer resumes and the live permalink never sees a partial
   file. **The script's design absorbed a mistake the caller made.**

### Skill changes provoked by this release

| Change | Why |
|---|---|
| Snap probe → `api.snapcraft.io/v2/snaps/info` | The row told the reader to give up; the data was one request away |
| Added: the two Snap probes answer different questions | Run conclusion = upload succeeded; store API = what a user gets. They diverged by minutes tonight, and Tier 2 (promote to stable) can only use the second |
| Added: "I can't probe this" is itself a claim | Generalises #8 past Snap — the skill already knew this for the website row and hadn't applied it |
| Added this log + Phase 7 | This file |

### Owed out of this release

- **Website deploy.** At close the live changelog named **0.26.0** — a version
  never published and no longer in `CHANGELOG.md` — while the download button
  served 0.27.0. Actively wrong, not merely stale.
- **Preflight cannot see `skip-worktree` files.** Add `git ls-files -v | grep '^S'`
  to `check-release-ready.sh` as a warning row. It would have caught failure 3
  before 11 minutes of build.
- **Perf red.** Decide: re-baseline with the reason recorded, or make the export
  carry one locale instead of 22. The second is probably right.
- **`openai` upper bound.** An open floor means the next major also arrives in a
  build, mid-release.
