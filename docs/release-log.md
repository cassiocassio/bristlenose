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

> ## ⚠️ The log stopped after one entry — measured 20 Sep 2026
>
> The header above says *one entry per release*. There is **one entry, for
> 0.27.0**. Three releases have shipped since — **0.28.0, 0.29.0 and 0.29.1, all
> on 31 Aug 2026** — and none is logged; this file has not been touched since
> 23 Aug. Applying the header's own judgement rule ("run for the next few
> releases and then be judged on whether it earned its keep"): **the window
> passed unjudged.** One entry written, three releases unlogged, and none of the
> three questions this log exists to answer is answerable from a single run.
>
> **That silence had a cost in a sibling doc, and it is the reason this note is
> here rather than in a backlog.** `docs/release-premortem.md` closed with *"the
> next release log entry should either move 12 to ✅ or say why it stayed"* —
> making this file the only follow-up mechanism for its one open incident. The
> gate for incident 12 shipped; no entry recorded it; and the premortem carried
> "it is not built" against a built gate for four weeks, in three places, while
> its own Score block said otherwise.
>
> Nothing here is retro-written: entries are written at the time or not at all,
> and inventing three is worse than lacking them. The decision owed is whether
> the log resumes at the next release or is retired deliberately — either is
> honest; drifting is what is not.

---

## 0.31.0 — 22 Sep 2026 · Tier 1

**Channels:** tag `v0.31.0` on `8b525e42` at 00:21Z · TestFlight build **3764**
(delivery `faba5539`) · notarised `.dmg` published · Snap edge dispatched ·
PyPI, GitHub Release, Homebrew, Copr and the website follow the tag run.
Verified separately — see the verification note below.

**What shipped.** Recordings transcribed in the language they were spoken in
(the default had been pinned to English on every channel since January);
section and theme names generated in the researcher's language; the five
framework codebooks re-read against their authors, with in-place migration of
installed rows; the Mac menu bar, Welcome screen and every remaining English
surface localised; focus mode on Signals; a localised Miro board; and the
pre-run cost estimate printing again after five months silent. 178 commits
since v0.30.0.

**The headline of this entry is that a soft gate found the release's worst
bug, and two hard gates had been red for the whole release with nobody
watching.** mypy — informational, ratcheted, the one gate everyone is tempted
to wave through — was two errors over its ceiling. One of the two was a live
crash. Meanwhile `ratchet` and `inventory` had failed on every CI run of this
release and nothing surfaced it until a release actually read the verdict.

### Timing (measured, from `events.jsonl`)

Wall 22:40Z → 00:21Z = **1h41**, of which the build and CI steps that actually
ran are ~47 min; the rest is diagnosis and three builds deliberately discarded.

| step | attempts | outcome | time |
|---|---|---|---|
| preflight | 2 | fail (dirty tree — another session's WIP) → ok | 1m35 |
| bump + commit | 1 | ok | 1s |
| push main | 3 | ok each; twice re-pushed by the new guard | 8s · 2s · 2s |
| strict CI dispatch | 5 | ok each; re-dispatched on every moved HEAD | ~2s each |
| build-all | 5 | fail (unsigned xctest) → fail (inventory drift) → **ok** ×3 | 5m29 · 5m29 · **5m26** |
| build-dmg | 4 | killed ×3 (artefact provably doomed) → **ok** | **13m11** |
| ci-green | 1 | ok | 12m16 |
| testflight | 1 | ok — build 3764 | 7m36 |
| dmg | 1 | ok | 1m19 |
| tag | 1 | ok — `v0.31.0` on `8b525e42` | 2s |
| snap | 1 | ok (dispatch) | 2s |

Strict CI ran **four** times, on `3346e692`, `c15720bc` and `8b525e42`; all
green bar the mypy soft gate once its two real errors were fixed. Three of the
four cycles were the cost of landing fixes mid-run.

**Three build-dmg attempts are recorded as `fail (exit 143)` and none was a
defect.** Each was killed deliberately the moment its artefact became
provably discardable — because a fix had landed and the build would have
shipped a different commit than the tag. Recorded as failures because that is
what the driver saw; worth reading as 25 minutes each of saved wall-clock, not
as instability.

### Tricky things

1. **The test bundle was built inside the app, and two signing tasks raced.**
   Xcode derives a hosted macOS test target's `TARGET_BUILD_DIR` as the host's
   `Contents/PlugIns`, so `BristlenoseTests.xctest` is linked into the `.app`
   and the app's `CodeSign` has to seal it — with nothing ordering the
   xctest's own `CodeSign` first. Three build logs of one tree ran it both
   ways. The failing order leaves an unsigned residue *inside* the app that
   fails the next build too, and the error carries no `error:` line, so the
   Swift gate reported a compile break. **0.30.0 hit this and recorded
   "fixed by `xcodebuild clean`"** — a cache-clear against a symptom, so it
   recurred at the very next release. Fixed at the cause: the bundle now
   builds beside the app. `parallelizeBuildables = NO` was tried, measured to
   change nothing, and reverted.

2. **The sidecar rebuild re-resolved four packages after the gate had looked**
   — `anthropic` 1.7.0→1.8.0, `openai` 3.17.0→3.18.0, `google-genai`
   2.24.0→2.25.0, `mako` 1.4.1→1.4.3. **Third occurrence: 0.27.0 #5, 0.30.0 #2,
   now.** 0.30.0's own entry names the structural fix — resolve dependencies
   once, in preflight — and it remains unbuilt, so preflight is still
   structurally blind to the drift the release itself causes. Providers
   re-probed under the rebuilt `.venv-sidecar` afterwards: 7/7 live.

3. **mypy's ratchet was pointing at a crash.** Two errors over ceiling. The
   useful move was diffing the error *sets* against a detached worktree at
   v0.30.0 rather than comparing counts: 148 at the tag, 150 at HEAD, and the
   two additions named themselves. One was a Miro annotation. The other:
   `transcribe_sessions` is declared to return `(results, languages, outcome)`
   and its "nothing needs transcription" path still returned two values, so
   reaching it raises `ValueError` and kills the run. Reachable because the
   caller and the callee ask different questions — the caller selects "not
   already transcribed and has audio", the callee keeps "has audio and no
   existing transcript", and a session whose sidecar subtitle parsed to
   nothing satisfies the first and fails the second. **5,247 tests were green:
   no test had ever called the function with sessions it would filter out
   entirely**, and the docstring still described the pre-widening shape. Fixed,
   with a test proved red first.

4. **Two hard CI gates had been red all release.** `ratchet` (skip sites
   25→29, slow marks 9→12) and `inventory` (generated test map stale). Neither
   was news about the release night: both counts sat *exactly at* their
   ceilings when 0.30.0 shipped, so the first addition in 178 commits pushed
   them over. All seven ratchet additions are in the two codebook-register
   test files and all seven are house idiom — live runs of an authored
   codebook against a real provider, and the sanctioned "SKIPPED, NOT PASSED"
   degradation. Ceilings raised deliberately, with the reasoning in the file.
   **The gates were right and their signal reached nobody** until a release
   read it.

5. **A fix committed between attempts was never pushed.** `push-main` is a
   plain step, so a recorded success is skipped on resume. `strict-ci` *does*
   notice a moved HEAD and re-dispatch — but it records `git rev-parse HEAD`
   while `gh workflow run --ref main` dispatches the *remote* ref, so `ci-sha`
   named a commit the dispatched run was not about (measured: a run carrying
   `a3475297` against a `ci-sha` of `3346e692`). `ci-green` selects by
   `headSha == ci-sha` and would have found nothing, 40 minutes later, with a
   message naming neither cause. Fixed: push-main now asks whether HEAD is an
   ancestor of `origin/main`. It fired correctly on its first two outings.

6. **…and the same class bit once more, on the step below.** `build-all` is
   also plain, so on the final resume it printed `skipped (done)` while its
   `.pkg` had been built at the previous commit. Left alone, the App Store
   build and the `.dmg` would have carried **different commits out of one
   release**, with only the app's embedded build-info to show it. Invalidated
   by hand (`release.sh retry 0.31.0 build-all`) and both rebuilt from
   `8b525e42`. The general rule the driver still needs: *a step whose output
   is a function of the tree is invalidated when the tree moves.* It already
   implements exactly that for `strict-ci`, and its comment explains why — it
   was applied to one step instead of to the class.

7. **The push-main guard from #5 then failed the release run, four hours
   old.** `release-suites` is inside the publish gate, and it went red on
   `test-release-sh`: 206 passed, 1 failed, *"a step ran during a stranded
   resume"*. The guard asked `git merge-base --is-ancestor HEAD origin/main`
   and negated the result — but a fixture repo has no `origin/main`, so
   merge-base *errors*, `!` turns that error into "not published", and the
   guard re-pushed inside the one test that asserts no step runs at all.
   **Green locally and red in CI for the oldest reason in the book:** this
   repo has `origin/main` and HEAD was an ancestor of it, so the new guard
   never fired once while I was proving it worked. The distinction the
   condition was missing is *cannot answer is not the same as answered no* —
   `origin/main` must resolve before the question means anything. The tag was
   moved to the fixed commit (`8b525e42` → `8e4433bf`, a `scripts/` change
   only, so neither the `.pkg` nor the `.dmg` is affected) and re-pushed, per
   the documented remedy for a release run that fired and failed. PyPI had not
   published, so 0.31.0 was never spent.

### Changes made to the machine this release

- `desktop/Bristlenose/Bristlenose.xcodeproj`: test target builds beside the
  app (both configurations).
- `desktop/scripts/test-swift.sh`: names the unsigned-residue state and the one
  `rm -rf` that clears it, instead of printing a compile-break with no errors.
- `scripts/release.sh`: push-main re-pushes when HEAD is not published.
- `scripts/check-doc-surfaces.sh`: two defects, both of which made the gate
  report a documented flag as missing — a flag passed to `grep` as an option,
  and `grep -q` under `pipefail` losing any match in the first 64 KB of a
  101 KB README.
- `docs/testing/ratchet.json`: two ceilings raised, with reasons.

## 0.30.0 — 21 Sep 2026 · Tier 1

**Channels:** PyPI · GitHub Release · Homebrew · TestFlight (build 3578) ·
`.dmg` · website · Snap edge · Copr. **All nine verified by 07:08 BST, twenty-five minutes after the tag** — 7 of 9
at 06:58 with Snap edge published but not yet in the store map and Copr still
building `0.30.0-1` (build 11009213, succeeded 07:07); 9 of 9 on the re-run. The website deploy ran
unattended (`deploy.sh --yes`, BatchMode SSH) once PyPI answered 200 on the
version-specific endpoint — twelve minutes after the tag.

**What shipped.** The Analysis lens is Signals on every surface (21 locales,
route, package, API, CSS, symbols — and the website copy, held for deploy);
signal cards generation 4; PII redaction end to end on the CLI; a focus cursor
in Codebooks with a Codes menu; ⌘F; one keychain across app and CLI. 489
commits since v0.29.1, 182 of them product-touching. Build 3578.

**The headline of this entry is that the release machine failed four times
before it built, and three of the four were latent rather than new.** Two had
been green under tests that could not fail; one had been waiting since 11 Sep
for the first `.dmg` archive to meet it; one was mine, introduced while fixing
the third. Every one was found by the run, not by a gate — the gates that
existed reported success while seeing nothing, which is the premortem's named
house defect, and this entry adds four instances of it.

### Timing (measured unless noted)

From `events.jsonl`. Pipeline time only; the wall was 6.3 h (23:28Z → 05:43Z) of which
most was a human asleep and me debugging.

| step | attempts | outcome | time |
|---|---|---|---|
| preflight | 2 | fail (dirty tree — another session's WIP) → ok | 1m23 · 1m17 |
| bump + commit | 1 | ok | 0s |
| push main | 1 | ok | 3s |
| strict CI dispatch | 3 | ok each; verdict re-pointed by hand twice | 2s · 1s · 1s |
| build-all | 3 | fail (unsigned xctest) → fail (inventory drift) → ok | 0m16 · 3m28 · **5m28** |
| build-dmg | 3 | fail (entitlements path) → fail (my truncation) → ok | 3m22 · 4m07 · **13m35** |
| ci-green | 1 | ok — verdict already green | 2s |
| testflight | 1 | ok — build 3578 | 6m51 |
| dmg | 1 | ok | 1m57 |
| tag | 1 | ok — `v0.30.0` on `f5309362` | 2s |
| snap | 1 | ok (dispatch) | 2s |

Strict CI ran **four** times on three commits (`99b47511`, `b99e97f9` ×2,
`4aac8523`, `f5309362`); each ~38 min, all green bar the mypy soft gate. Two
of those cycles were the cost of landing fixes mid-run — see #6.

### Builds

- Sidecar rebuilt three times, each a full dependency re-resolve (see #2).
- `build-all` attempt 3 and `build-dmg` attempt 3 both from a clean tree.
- The archive was independently verified before the driver reached it: real
  `xcodebuild archive` with the fix → **ARCHIVE SUCCEEDED**, app carries
  `app-sandbox` and **no** `application-groups`, `Settings_Settings.bundle`
  signs clean.

### Tricky things

1. **DerivedData held `BristlenoseTests.xctest` built but unsigned.** The
   incremental build called it up to date; the version bump forced the app's
   signing step, which refused to wrap an unsigned nested bundle. Not keychain
   — the identity signed a scratch binary non-interactively, exit 0. Fixed by
   `xcodebuild clean` on the Debug scheme. The gate's own message ("Swift
   suite red, *or* the test bundle failed to build") covers both and names
   neither.
2. **Both release lanes `--force` the sidecar, which re-resolves every
   dependency — after the drift gate has looked.** `build-all.sh:314` and
   `build-dmg.sh:287`. `check-release-ready.sh` reads whatever `.venv-sidecar`
   exists *before* either force, so it is structurally blind to the drift the
   release itself causes. Tonight: 24 packages moved between two builds an hour
   apart — `filelock` 3.32.4 → 4.0.1 (major), `openai` 3.5.0 → 3.16.2 under the
   provider this release rewrites. Preflight's "providers live 7/7" had been
   measured under `.venv`. Re-run under `.venv-sidecar`: 21 live calls, 7/7.
   **A recurrence of 0.27.0 #5 (`openai>=1.50` → 3.0.0 at 10pm mid-release).**
   The 23 Aug fix moved the discovery into preflight; the discovery is of the
   wrong venv.
3. **`CODE_SIGN_ENTITLEMENTS` was relative, and a command-line build setting
   applies to every target.** Xcode resolved it against the Settings Swift
   package's `SRCROOT` in DerivedData, where it does not exist. Unexercised
   since `11d9cb6f`: the last `.dmg` predates it (31 Aug). Eleven tests in
   `test_entitlements_split.py` were green throughout — they assert the
   override *appears in the invocation*, never that the archive runs.
4. **My comment truncated the command it explained.** A `#` line between two
   backslash-continued lines ends the command there. `xcodebuild` ran with no
   override and no `archive` verb, printed BUILD SUCCEEDED, and the next line
   failed as a command. `bash -n` passes it. The quiet variant — truncate
   *after* `archive` — ships the MAS entitlements on the Developer-ID channel
   with no error. The thirteenth test now stubs `xcodebuild` and reads the
   arguments that arrive.
5. **The PyInstaller spec still named `bristlenose.analysis.*`.** Five hidden
   imports. PyInstaller logs `ERROR: Hidden import ... not found` and keeps
   building; the step exited on something else. The rename sweep covered
   `.py/.md/.json/.toml/.cfg` and not `.spec`. Gate added:
   `test_packaging_artifacts_coverage` resolves every `bristlenose.*` hidden
   import (`_build_info` excepted with its reason).
6. **`ci-sha` and HEAD diverge on every mid-run fix, and only the tag checks.**
   `verdict_tag_provenance` is called from `TAG_CMD` alone; `ci-green` looks up
   the run by `ci-sha` and never compares HEAD; the TestFlight and `.dmg`
   uploads precede the tag. A resume with `strict-ci` marked ok and HEAD moved
   would ship builds CI never saw and refuse only at the tag. Avoided twice by
   hand-updating `ci-sha` after a hand re-dispatch — the remedy the guard's
   own comment documents — at ~38 min of CI each.
7. **`--yes` already existed, tested at five sites in `test-release-e2e.sh`.**
   Missed because the four runtime resume hints (`plan` footer, "fix, then …
   resumes here", "Resume:", `retry`'s) print the command without it. The
   unattended run was driven by `printf '0.30.0\n' |` instead — equivalent,
   unnecessary, and one grep from a duplicate flag.
8. **A backgrounded `pytest … | tail` reported exit 0 on a real failure.**
   `test_lead_paragraph_atom.py` hardcoded `organisms/analysis.css`. The
   documented trap; caught by reading the output.
9. **mypy is 164 against a ceiling of 149.** Pre-existing — red on four
   commits before the rename — and a declared soft gate. Left alone.
10. **The Swift suite reports 1462 or 1463 on an unchanged tree.** A flake, not
    a one-test regression; two runs on the same HEAD gave both numbers.

### Skill changes provoked by this release

| Change | Why |
|---|---|
| `build-dmg.sh`: entitlements override is absolute, comment moved above the invocation | #3, #4 |
| `test_entitlements_split.py` +2: path is absolute; stub `xcodebuild` reads arriving args | #3, #4 — mutation-proved against each |
| `test_packaging_artifacts_coverage.py` +1: every `bristlenose.*` hidden import resolves | #5 — mutation-proved |
| `THIRD-PARTY-BINARIES.md` regenerated twice, second time proven live | #2 |
| `release.sh`: four resume hints carry `[--yes]`; resume re-dispatches strict CI when HEAD ≠ `ci-sha` | #7, #6 |

### Owed out of this release

- **Resolve dependencies once per release, in preflight.** Rebuild
  `.venv-sidecar` there; both lanes then reuse it (no `--force`). The drift
  verdict becomes a verdict about the venv that ships, and a regenerated
  inventory folds into the bump commit — one HEAD move, one CI dispatch, no
  cascade. Closes #2 and most of #6's cost. Also lets the live-provider probe
  run under `.venv-sidecar`, which closes the standing board card.
- **Resume refuses, or resets `strict-ci`, when HEAD ≠ `ci-sha`** — before any
  upload, not at the tag. Closes #6. Three lines in the resume path.
- **`xcodebuild clean` before `build-for-testing`** in `build-all` 1c, or a
  nested-signature check on the built products. Closes #1.
- **The unpinned stack is a decision, not a defect** — board card stands.
- ~~**Website deploy** after `verify`; commit `12981ac` is waiting on it.~~ ✅ **done
  06:57 BST, same night, unattended.** `deploy.sh --yes` over BatchMode SSH;
  its own verify all 200, sensitive paths 404/403; live changelog's first
  header is 0.30.0 and the three renamed pages say Signals.
- ~~**Re-verify Snap edge and Copr.**~~ ✅ **done 07:08 BST** — Copr build
  11009213 succeeded at 07:07 on an x86_64 wheelhouse (the arch pin held);
  Snap store map reads 0.30.0. `release.sh verify 0.30.0` → 9 of 9.
- 0.28.0, 0.29.0 and 0.29.1 remain unlogged here; this entry does not owe
  them.

### What this entry produced, beyond the release

Three gates that fail on the defects they were written for; one script fix;
two board cards written before the run and one structural finding that
upgrades both; the four `--yes` hints; and the observation that the two
premortem shapes each gained instances tonight — recorded there as 23–27.

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
