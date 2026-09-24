# Release pre-mortem — every incident of the last six months, replayed

**23 Aug 2026, extended 28 Aug.** Twenty-two release incidents mined from `docs/release-log.md`,
`docs/design-release-system-audit.md`, `CLAUDE.md`'s gotchas and six months of
git history. For each: what happened, and **what `scripts/release.sh` would do
if it happened tonight.**

The point of the last column is the ones marked ✗. A pre-mortem that finds
everything already handled has been written to flatter the system.

**Verdicts:** ✅ caught mechanically · ⚠️ surfaced but not stopped · ✗ still
invisible.

---

## The hit list

| | Incident | What happened | Tonight |
|---|---|---|---|
| **1** | **v0.15.5–0.15.9 published nothing, for six days** | Five tags pushed, five workflow runs never delivered to PyPI. Nobody checked, because the tag reaching GitHub *looked* like a release | ✅ `verify-channels.sh` probes the version-specific PyPI endpoint. `run` exits **75** (verification pending), never 0 — so `release.sh run && …` cannot chain off an unpublished release |
| **2** | **v0.15.0 debounce — `--tags` bundled the pushes** | One `git push origin main --tags` bundled branch and tag events; the tag-driven workflow never fired | ⚠️ The step table has `git push origin main` and `git push origin v<V>` as **two separate steps**, so the shape cannot recur from the driver. Not asserted for a hand-run — the rule lives in prose |
| **3** | **v0.15.13 — `gh run rerun --failed` replayed the stale commit** | The e2e Playwright CDN stalled. A `--failed` rerun re-ran the *tagged* commit, not `main`'s fix, and failed identically | ✅ `release.sh recover` probes PyPI, the tag sha and the run state, then names which of **three** cases applies. Tag == HEAD → rerun (no fix can exist). Main moved → **retag**, with the warning that a rerun replays the stale commit. No run at all → redeliver |
| **4** | **v0.6.7–0.6.13 — seven versions, CI parity** | Local ran `ruff check bristlenose/`, CI runs `ruff check .`. Test-file lint errors were invisible locally | ✅ `run`'s first step is the preflight, whose `CI status` row asks whether **HEAD has a green run** rather than whether local checks pass |
| **5** | **0.25.2 — three channels shipped on a version the suite then rejected** | First CI run green → uploads out → second CI run red. The uploads preceded the verdict | ✅ This is the whole reason for step `strict-ci`. `ci-green` blocks before `testflight`, and is pinned to `--event workflow_dispatch` **and** to HEAD's sha, so it cannot certify the push-triggered non-strict run or a different commit |
| **6** | **0.26.0 — tagged with 34 commits of real code past it** | "Docs-only, wheel byte-identical" was asserted without running the diff. Tag abandoned | ✅ `shippable diff` runs the diff and classifies release / rebuild / nothing. ✅ `abandon` now **probes PyPI** and refuses if the version published |
| **7** | **0.27.0 build 1 — a gate became unsatisfiable, latent two days** | `check-window-surfaces` asserted an exact source line; a rename made it unmatchable. Cost 11 min of build | ✅ The preflight now **runs** the five source-only gates in ~2s. It would fail before the bump |
| **8** | **0.27.0 build 2 — stale supply-chain inventory** | `THIRD-PARTY-BINARIES.md` drifted; caught mid-build | ✅ Two preflight rows: `dependency majors` (named, a major is a hard stop) and `dependency drift` |
| **9** | **0.27.0 build 3 — `skip-worktree` entitlements invisible** | Both entitlements files marked `S`; `git status` and the preflight both reported a clean tree | ✅ The `skip-worktree` row compares content hashes rather than asking `git diff`, which goes through the same index-trusting mechanism |
| **10** | **0.27.0 #1 — three failed builds read as successes** | Five background runs reported exit 0; three had printed `✗ Build failed` | ✅ `run` redirects, never pipes, and reads `$?` directly. Pinned by an assertion that the eval line carries no pipe |
| **11** | **0.27.0 #6 — "I approved it" vs `pending_deployments`** | Ticking the environment is not pressing **Approve and deploy** | ✅ Moot: the approval is gone. The gate is `publish → build → ci(strict)`, asserted by parsing both workflows |
| **12** | **0.27.0 #7 — perf red for four runs, nobody knew** | Non-blocking by design, so nothing surfaced it | ✅ The `advisory workflows` block reads `WF_ADVISORY` (`perf.yml codeql.yml`) and goes **bad** at `ADVISORY_STREAK_MAX=3` consecutive reds on `main` — one failure is noise, three is a signal. `check-release-ready.sh:839-874`, constants in `project.conf:91-92` |
| **13** | **0.27.0 #9 — a self-imposed `timeout` killed a working upload** | Interrupted at ~1%; `upload-dmg.sh`'s staging design absorbed it | ✅ Now better than survivable: a signal kills the step **and its descendants**, the step is left `running`, and the next `run` reports it stranded rather than re-running it |
| **14** | **0.27.0 #2 — `rsync --progress` read as frozen** | Carriage returns made `tail` show the start of one enormous line | ✅ Fixed at source (`--progress` is TTY-gated) **and** in the driver (the failure tail goes through `tr '\r' '\n'`) |
| **15** | **0.23.0 — ~2 hours across three attempts** | Test-suite changes, repeated failures | ⚠️ Resume makes attempt N+1 cheap — completed steps skip. The underlying flakiness is untouched |
| **16** | **Homebrew 6.0 tap trust — bare `brew upgrade` silently skips** | Non-official taps must be named in ARGV; `opoo`, not an error | ✅ Out of the driver's scope, but `bristlenose doctor`'s `check_brew_tap_trust` catches it on the user's side |
| **17** | **PyPI index JSON is CDN-cached and reads stale** | A poll returned 0.23.0 then 0.22.0 seconds later, from a different edge | ✅ `verify-channels.sh` uses the **version-specific** endpoint (`/pypi/<pkg>/<ver>/json`), which is authoritative, not the cached index |
| **18** | **`.dmg` gates that could not fail** | `stapler validate … && ok "passed"` — `set -e` exempts the left operand of `&&`, so the gate printed nothing on failure and fell through | ✅ Fixed in `build-dmg.sh` (`fc1d6ca7`), and the same shape was found and removed from `verify-channels.sh` in this pass |
| **19** | **0.17.0 blocked by a stale locale test + size budget** | Discovered mid-release | ✅ The preflight's `CI status` row asks for a green run on HEAD before anything |
| **20** | **Already-bumped / publish-pending** | A re-run had to distinguish "bump not done" from "bump done, push pending" | ✅ This is exactly what the fold is: `run` re-entered is the resume path, and every step's status is derived from the log |
| **21** | **App Store — 3 nested-binary MAS signing rejections** | Found at upload, after a full build | ⚠️ `check-pkg-shippable.sh` is an unskippable precondition **inside** `upload-testflight.sh`, so it fails before the upload — but still after the build. Only an archive can be inspected |
| **22** | **0.28.0 reported "every act is done" over an unpublished release** | The step loop reads its table from a heredoc on **stdin**, and each step runs backgrounded, inheriting it. `ssh` inside `upload-dmg.sh` consumed the remaining rows, so `tag` and `snap` were never read, never ran, and left **no events** — the loop hit EOF and exited normally. TestFlight and the `.dmg` had already published; PyPI had nothing | ✅ Two fixes, instance and class. Steps now run `< /dev/null` (no release step may read stdin). And `run completed` became a **checklist** claim: `verdict_complete` re-derives the table and names any Tier-1 step without a terminal event — exit 1, no completed event. e2e test 19 reproduces the eaten table with `cat` standing in for ssh, and fails on the old code |

---

## Score

**17 caught mechanically · 4 surfaced but not stopped · 0 still invisible.**

_Updated 23 Aug 2026: incidents 3 and 12 were the two invisible ones. Both are
now closed — 12 by the advisory-streak row, 3 by `release.sh recover`. What
remains at ✗ is nothing; the four ⚠️ are genuine partials, not deferrals._

> **Trued 20 Sep 2026.** The tally above read *"16 · 4 · 1 still invisible"* —
> contradicting, in the adjacent paragraph, its own note that nothing remains
> at ✗. That patch was made on 23 Aug and reached the Score block alone; the
> hit-list row, this section's heading, and §What-this-exercise-changed each
> kept the pre-23-Aug verdict for four weeks. **The stale claim lived in four
> places and the correction reached one.** Both are now named below as closed.

The two that *were* invisible are worth naming rather than rounding up, because
what closed them is the reusable part:

### ✅ 12 — a non-blocking workflow that has been red for weeks

`perf.yml` is deliberately non-blocking (post-merge only, so runner noise cannot
stall a release). That is the right call and it means **nothing surfaces a
sustained red**. It went unnoticed for four consecutive runs, including on the
abandoned 0.26.0 tag.

The gap was one preflight row: `gh run list --workflow=perf.yml --limit 5` and
warn on a run of failures. **It is built** — `check-release-ready.sh:839-874`,
iterating `WF_ADVISORY` from `project.conf:91` so the shape generalises to any
advisory check the project adds later, exactly as this paragraph predicted.
`codeql.yml` is already the second member.

The threshold is the design, and the script says so: *"One failure is noise.
Three in a row is a signal — a row that fires on every flake gets ignored,
which is how the advisory workflow became invisible in the first place."*

### ✅ 3 — closed, and the third case is the one that gets forgotten

`release.sh recover <X.Y.Z>` probes PyPI, the tag sha, HEAD and the run state,
and names the case:

- **published** → nothing to recover, only supersede. Reached first, so no
  branch can suggest tag surgery on an immutable version.
- **no run fired** → the *debounce* case (v0.15.0). A bundled `push --tags`
  sends both events together and the tag workflow never runs. Redelivering the
  same sha is a semantic no-op that re-triggers it.
- **failed, tag == HEAD** → rerun. Nothing on main is missing from the tagged
  commit, so the failure can only be transient.
- **failed, main has moved** → **retag**, with the reason: a `--failed` rerun
  replays the tagged commit, which is exactly how v0.15.13 failed twice.
- **green but not on PyPI** → neither. That is the v0.15.5–0.15.9 shape, where
  five runs looked fine and delivered nothing.

It diagnoses and prints the command; it does not perform tag surgery. The
diagnosis is mechanical, the act is not.

---

## The two shapes that recur

Read as a set rather than a list, the twenty-one collapse into two failure
modes, and one of them is over-represented:

**A check that reports success while seeing nothing** — 1, 3, 7, 9, 10, 11, 12,
18. Eight of twenty-one. Every gate written this month was written against this
shape, and four *new* instances of it were still found during review the same
day. It is the house defect.

**A verdict arriving after the act it should have gated** — 5, 6, 8, 19, 21.
The reorder (strict verdict before the uploads, tag last) closes four of five;
21 is closed only as far as physics allows, since an archive must exist before
it can be inspected.

> **28 Aug 2026 — incident 22, and the counts above deliberately exclude it.**
> The analysis in this section is dated and reasons over the twenty-one mined on
> 23 Aug; re-pointing "eight of twenty-one" at a later set would falsify the
> argument rather than update it. Recording the delta instead: **22 is the house
> defect, in the machine written to catch it.** A step command ate the driver's
> own step table and the run declared itself complete over an unpublished
> release — "a check that reports success while seeing nothing", five days after
> this section named that shape as the thing to watch for. Two differences from
> its eight predecessors are worth keeping. It was the first such defect the
> *release machine itself* caused rather than caught. And the fix that
> generalises was not the one-line stdin redirect but the realisation that
> `run completed` had been derived from an input stream ending rather than from
> a checklist closing — the same tautology `CLAUDE.md` records for the
> pipeline's `attempted == succeeded + failed`. On the 23 Aug denominator
> nothing moved: 22 arrived and was closed the same day.

> **21 Sep 2026 — incidents 23–27, from the 0.30.0 run. The 23 Aug counts
> above are left as written; this records the delta.**
>
> Five new instances in one night, and they sort into the two shapes without
> remainder. Four are the house defect; one is the reorder's residual.
>
> **A check that reports success while seeing nothing — 23, 24, 25, 26.**
>
> - **23 — the drift gate reads the venv the release then discards.** Both
>   release lanes run `ensure-sidecar.sh --force`, which re-resolves every
>   `>=` floor; preflight's `check-dep-drift.py` reads `.venv-sidecar` *before*
>   either force. It cannot see the drift the release causes, only drift that
>   was already there. 24 packages moved, including a major — the recurrence of
>   #5 that the 23 Aug fix was meant to prevent, and would have, had the
>   discovery been of the right venv. Same night, the live-provider probe ran
>   under `.venv` and passed 7/7 on an SDK eleven minors older than the one
>   shipping. Fix: resolve once, in preflight; lanes reuse.
> - **24 — eleven green tests over an archive that could not run.**
>   `test_entitlements_split.py` asserted the `CODE_SIGN_ENTITLEMENTS` override
>   *appeared in the archive invocation*. It did. The path was relative, and a
>   command-line build setting reaches every target — the Settings package
>   resolved it against its own `SRCROOT` and the archive died on a target the
>   override was never about. First `.dmg` since the override landed. Two tests
>   added, mutation-proved.
> - **25 — `bash -n` blessed a truncated command.** A comment placed inside a
>   backslash continuation ended the `xcodebuild` invocation: no override, no
>   `archive` verb, BUILD SUCCEEDED, next line "command not found". Valid shell,
>   wrong command. The quiet variant ships MAS entitlements on the Developer-ID
>   channel with no error at all. Fix is the general one: run the block with a
>   stub and assert on the arguments that *arrive*, not the text of the file.
> - **26 — PyInstaller logs a missing hidden import as ERROR and builds
>   anyway.** Five entries named a package renamed a day earlier; the step
>   exited on an unrelated cause and the errors scrolled past. Nothing in the
>   repo read them. A module is a hidden import *because* analysis cannot see
>   it, so its absence is silent until a researcher hits the `ImportError`.
>   Gate added: every `bristlenose.*` hidden import must resolve.
>
> **A verdict arriving after the act it should have gated — 27.**
>
> - **27 — the tag checks provenance; the uploads before it do not.**
>   `verdict_tag_provenance` runs only in `TAG_CMD`. `ci-green` finds its run by
>   `ci-sha` and never compares HEAD. Land a fix mid-run, resume with
>   `strict-ci` still marked ok, and the TestFlight build and the `.dmg`
>   permalink both ship from a HEAD the strict verdict does not name — then the
>   tag refuses. #5's shape exactly, one step later. Avoided twice tonight by
>   the documented hand-update of `ci-sha`, at ~38 minutes of CI each. Fix: the
>   resume path refuses, or resets `strict-ci`, when HEAD ≠ `ci-sha`.
>
> What generalises past the five: **every one was caught by running the
> release, not by a gate**, and three of the five were latent — green under
> tests that could not fail, waiting for the first real archive. The 23 Aug
> observation stands and hardens: a gate written against a *string* in a file
> is the house defect wearing a test's clothes. Assert on the thing that
> arrives.

> **23 Sep 2026 — incidents 28–31, from the 0.31.0 run.** Four more, and the
> shape has shifted: only one is the house defect. Three are a *third* shape
> this log should now name.
>
> **A check that reports success while seeing nothing — 28.**
>
> - **28 — the doc-surfaces gate could not see a flag in the first half of the
>   README.** Two defects in one script. `is_new()` ran `grep -qxF "$1"` with a
>   flag as its argument, so every `--flag` was parsed as a grep *option*:
>   `--version` printed grep's own version and was "new since the tag" on every
>   run, and every other flag errored and was never new. And the three surface
>   checks piped a 101 KB README into `grep -q` under `pipefail` — `grep -q`
>   exits on first match, `printf` takes SIGPIPE, and the pipeline reports
>   failure. A flag documented at line 277 was reported *missing from the
>   README that documents it*, while flags mentioned only in the changelog at
>   the end of the file matched. That asymmetry is why it looked healthy.
>
> **A verdict that is about a commit, applied after the commit moved — 29, 30.**
> This is the new shape, and it is the sibling of "a verdict arriving after the
> act it should have gated": here the verdict is *correct* and the tree is what
> moved underneath it.
>
> - **29 — a fix committed between attempts was never pushed.** `push-main` is
>   a plain step, so a recorded success is skipped on resume. `strict-ci` knows
>   about moved HEADs and re-dispatches — but records `git rev-parse HEAD` while
>   `gh workflow run --ref main` dispatches the *remote* ref, so `ci-sha` named
>   a commit the dispatched run was not about (measured: `a3475297` against a
>   `ci-sha` of `3346e692`). `ci-green` selects by `headSha == ci-sha`; it would
>   have failed closed 40 minutes later naming neither cause. Fixed: push-main
>   asks whether HEAD is an ancestor of `origin/main`. Fired correctly twice on
>   its first night.
> - **30 — and the same class one step lower, where it is worse.** `build-all`
>   is plain too, so the final resume printed `skipped (done)` over a `.pkg`
>   built at the previous commit. The App Store build and the `.dmg` would have
>   carried **different commits out of one release**. Invalidated by hand. The
>   rule the driver needs is one line: *a step whose output is a function of
>   the tree is invalidated when the tree moves* — it already implements
>   exactly that for `strict-ci`, with a comment explaining why, and it was
>   applied to one step instead of to the class.
>
> **A correct gate whose signal reached nobody — 31.**
>
> - **31 — two hard CI gates had been red for the whole release.** `ratchet`
>   (skip sites, slow marks) and `inventory` (stale generated test map) failed
>   on every CI run of the 178 commits and nothing surfaced it until a release
>   read the verdict. Both ratcheted counts sat *exactly at* their ceilings when
>   0.30.0 shipped, so the first addition pushed them over. This is the same
>   shape as the Swift suite going unrun for three months (`gaps.md`): the gate
>   is right, it fires, and no one is downstream of it. **The standing question
>   it raises is whether anything watches CI on `main` between releases.**
>
> **32 — and the fix for 29 failed the release run.** Four hours old. The new
> push-main guard asked `git merge-base --is-ancestor HEAD origin/main` and
> negated it; a fixture repo has no `origin/main`, so merge-base *errors* and
> `!` reads the error as "not published". It re-pushed inside
> `test-release-sh`'s stranded-resume case, which asserts that no step runs at
> all — 206 passed, 1 failed, and `release-suites` sits inside the publish
> gate, so PyPI never received the tag. **Green locally, red in CI**: this repo
> has the ref, so the guard never fired once while it was being proved. The
> missing distinction is *cannot answer ≠ answered no*. Filed here rather than
> in the log alone because it is a fourth shape, and a mean one: **a mitigation
> written for one incident becoming the next incident**, verified only in the
> environment where it cannot misbehave.
>
> **What earned its keep this release.** mypy — soft, ratcheted, the gate most
> tempting to wave through — was two over its ceiling, and one of the two was a
> `ValueError` that kills any run reaching it. 5,247 tests were green. The move
> that found it was diffing the error *sets* against a worktree at the previous
> tag rather than comparing the counts. **A soft gate is not a weak gate; it is
> a gate whose verdict someone has to read.**

> **23 Sep 2026 — incidents 33–34, from the 0.31.1 and 0.31.2 runs.** Both are
> the distinction incident 32 had named hours earlier — *cannot answer ≠
> answered no* — sitting unfixed in a different gate. One gate, two releases,
> two shapes.
>
> - **33 — a transient HTTP 503 killed `gh run watch` mid-poll (0.31.1).** The
>   run it was watching was still queued, and went green on its own minutes
>   later. `gh run watch --exit-status` spends ONE exit code on two unrelated
>   facts — "CI says no" and "the wire broke" — so a 38-minute wait was
>   discarded over one dropped API call.
> - **34 — and the same gate failed SILENTLY the next release (0.31.2).**
>   `CI_CMD`'s `[ -n "$_id" ] && … && gh run watch …` short-circuited on its
>   *middle* test when the lookup came back empty: exit 1, no error text, a
>   **zero-byte log** for a CI run that was genuinely still in progress. The
>   `cmd && ok` shape this repo already documents, in its quiet direction —
>   and worse than 33, because a gate that fails without saying anything reads
>   as a defect in the gate.
>
> **What the fix is, and what it deliberately is not.** `ci_await_verdict`
> retries both reads with backoff, which is the obvious half and the smaller
> one. The half that matters is two pure verdicts above the sourcing seam:
> `verdict_run_lookup` classifies an empty lookup by `gh run list`'s **exit
> status** rather than by its emptiness, because `$(…)` discards the status
> and that is precisely what made the two causes indistinguishable; and
> `verdict_watch_drop` refuses to read a non-zero watch as CI's answer until
> the run itself reads `completed`. **Retries alone would have been the wrong
> fix and a dangerous one** — they decide how many times to ask, not whether
> what came back was an answer, so a genuinely red CI would have been retried
> as though it were weather. `test-release-e2e.sh` 30–34 pins that a concluded
> failure is watched exactly *once*; run against the pre-fix chain, 11 of
> those 17 assertions go red, one of them by reproducing 34's zero-byte log.
>
> The generalisation is already in this file twice (incident 32; the tri-state
> probe rule) and was still absent here: **every gate that reads a remote
> system needs three outcomes, not two.** A gate with two has to spend one of
> them on both "no" and "I could not ask".

---

## What this exercise changed

Nothing in the code — every mitigation above was already built. What it produced
is the honest denominator: **two of twenty-one incidents would still happen
tonight, and one of them (12) is a row someone could add in an hour.**

> **20 Sep 2026 — 12 is closed, and the denominator moves to one of
> twenty-one.** The row took about an hour, as predicted. Recording the delta
> rather than re-pointing the sentence above, per this doc's own convention for
> incident 22: the "two of twenty-one" reasoning is dated to 23 Aug and stays
> legible as of that date.
>
> The more useful finding is about *this file*. The sentence below asked the
> next release log entry to "either move 12 to ✅ or say why it stayed". The
> Score block was duly updated on 23 Aug — and the hit-list row, the section
> heading and this paragraph were not, so for four weeks the document answered
> its own question in one place and contradicted the answer in three others. A
> scorecard with more than one scoreboard keeps the stale one.

The pre-mortem's own risk is that it becomes a scorecard. It is dated, and the
next release log entry should either move 12 to ✅ or say why it stayed.

## See also

- `docs/release-log.md` — the 0.27.0 entry, the primary source
- `docs/design-release-system-audit.md` — the 14 Aug audit, §3's fail-open cluster
- `docs/design-release-machine.md` — the architecture these mitigations live in
