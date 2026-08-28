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
| **12** | **0.27.0 #7 — perf red for four runs, nobody knew** | Non-blocking by design, so nothing surfaced it | ✗ **Not caught.** No row watches non-blocking workflow conclusions. The fix is a `gh run list --workflow=perf.yml` row; it is not built |
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

**16 caught mechanically · 4 surfaced but not stopped · 1 still invisible.**

_Updated 23 Aug 2026: incidents 3 and 12 were the two invisible ones. Both are
now closed — 12 by the advisory-streak row, 3 by `release.sh recover`. What
remains at ✗ is nothing; the four ⚠️ are genuine partials, not deferrals._

The two that are genuinely invisible are worth naming rather than rounding up:

### ✗ 12 — a non-blocking workflow that has been red for weeks

`perf.yml` is deliberately non-blocking (post-merge only, so runner noise cannot
stall a release). That is the right call and it means **nothing surfaces a
sustained red**. It went unnoticed for four consecutive runs, including on the
abandoned 0.26.0 tag.

The gap is one preflight row: `gh run list --workflow=perf.yml --limit 5` and
warn on a run of failures. It is not built, and it should be — the shape
generalises to any advisory check the project adds later.

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

---

## What this exercise changed

Nothing in the code — every mitigation above was already built. What it produced
is the honest denominator: **two of twenty-one incidents would still happen
tonight, and one of them (12) is a row someone could add in an hour.**

The pre-mortem's own risk is that it becomes a scorecard. It is dated, and the
next release log entry should either move 12 to ✅ or say why it stayed.

## See also

- `docs/release-log.md` — the 0.27.0 entry, the primary source
- `docs/design-release-system-audit.md` — the 14 Aug audit, §3's fail-open cluster
- `docs/design-release-machine.md` — the architecture these mitigations live in
