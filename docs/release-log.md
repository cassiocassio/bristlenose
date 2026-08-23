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

**Channels:** TestFlight · `.dmg` · PyPI · GitHub Release · Homebrew · Snap edge
· website. **All seven verified on 0.27.0 the same night** — the website was owed
at close and deployed shortly after, so this release closed complete rather than
partial.

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

- ~~**Website deploy.**~~ ✅ **done 22 Aug 2026, same night.** At close the live
  changelog named **0.26.0** — a version never published and no longer in
  `CHANGELOG.md` — while the download button served 0.27.0. Actively wrong rather
  than merely stale, and the reason it was: that page renders from
  `CHANGELOG.md` at build time, so renaming the entry made every *previously*
  deployed copy of the site wrong the moment the rename landed. **A version
  abandoned before publication leaves a footprint on any surface already
  rendered from the changelog** — a `/bn-release` that abandons a tag should
  treat the website deploy as part of that decision, not as a later step.
  Verified: `0.27.0` present, `0.26.0` absent, sequence clean, and the four pages
  the deploy was also carrying now resolve (`recording-permissions.html` had been
  a live 404).
- ~~**Preflight cannot see `skip-worktree` files.**~~ ✅ **done 22 Aug 2026.** Added
  as a `bad` row, not a warning — an untracked file cannot change a build and
  this one did. It compares content hashes rather than asking `git diff`, since
  `diff` goes through the same index-trusting mechanism being bypassed. Verified
  against both states before committing. **It found a second divergence in the
  first run:** `BristlenoseDebug.entitlements` had been diverged from HEAD the
  whole time and nobody knew — only the Release file was ever restored. One row,
  one previously invisible defect, on the first execution.
- ~~**Perf red.**~~ ✅ **done 23 Aug 2026**, `30f9305d` — the export now carries
  one language rather than 22 (`localeLoader.export.ts`), which was the option
  this entry called "probably right". Not a re-baseline: the number came down
  rather than the line moving up.
- ~~**`openai` upper bound.**~~ ✅ **addressed 23 Aug 2026, but not as written.**
  Re-reading the complaint: #5 does not say the bump was bad — every constructor
  survived and it was a non-event. It says *"the discovery moment was 10pm,
  mid-release, which is the wrong moment for it."* That is a **timing** problem,
  and a cap is the wrong instrument for it: `pyproject.toml`'s written policy is
  floor-only, and pinning without a renovation bot ships known-vulnerable
  transitives for months. So the discovery moved instead of the floor —
  `scripts/check-dep-drift.py` names every package whose resolved version has
  drifted from the committed inventory and makes a **major** a hard stop, in the
  preflight, ~40 minutes before `build-all.sh` would have found it. Whether to
  cap `openai` remains open and is the maintainer's call; it is no longer a
  10pm one.

### What this entry produced, beyond the release

The three questions the log's header exists to answer, answered once by this
entry rather than waiting for a run of them — because six of its nine tricky
things turned out to be gates that did not exist rather than incidents.

Shipped 23 Aug 2026 (`docs/design-release-machine.md`): all 11 Tier A items —
`.release/` ignored, `--progress` TTY-gated, per-attempt altool logs, publish
state, dependency drift, `verify-channels.sh`, the never-read-a-background-exit-code
rule, `shippable diff`, `SIGN_IDENTITY` required, doc-surface parity, and gate
freshness. Plus the read-only half of Tier B (`release.sh plan|verify|status|abandon`).

**Two things this entry got wrong, found by building against it:**

1. **#1, #6 and #7 are not one failure.** The entry groups them as "a fact
   existed and was never recorded". Two of the three were *recorded* — the log
   said `✗ Build failed`, the API said `pending` — and misread. That distinction
   changed the design: a fourth artefact to read is not the cure for a reading
   problem, and Tier B shrank accordingly.
2. **Failure 1's gate cost 23 seconds and nobody had measured it.** Its
   `SelectionSync` assertion walked 2.4 GB of build output to find zero matches.
   Scoped to source: 23s → 0.07s. That measurement is what made gate freshness
   affordable to solve by *running* the gates rather than by building the stamp
   ledger the design specified — the feature hardest to design turned out to be
   the one that should not exist.
