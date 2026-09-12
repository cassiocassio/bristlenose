# Testing gaps — what is not covered, ranked by what reaches a user

_Judgement, not facts. The facts are generated into [inventory.md](inventory.md);
this file is the reading of them. Measured 3 Sep 2026 — every number below has the
command that produced it, so it can be re-measured rather than believed._

Ranked by **what class of defect reaches a user**, not by effort. A cheap fix for
a shipping-channel hole outranks an expensive fix for an internal annoyance.

---

## The shape they share

Every gap below, and every wrong claim found in the 2 Sep audit, is the same
artefact: **an intention with no owner and no expiry.**

- `design-ci.md` — *"informational initially — promote to blocking once stable"*.
  The promotion never came. The Swift tests went unrun for three months and
  v0.29.0 shipped on nine channels with the suite red.
- `mypy` — soft since it was added. Now 238 errors.
- `test_no_fake_success_acceptance.py` — written, cited as built, never run.
- `design-release-system-audit.md` — five findings marked unverified, untriaged.
- `README.md` — "16 ingest formats" against its own named source's 27.

None was careless. Each was true, or nearly true, when written, and **nothing was
ever obliged to revisit it.** That is the thing to fix, not the individual items:
a gate needs a colour *and* either an expiry or a ratchet.

---

## Tier 1 — a defect can reach a user

### G1. ✅ `build-dmg.sh` has no Swift gate — CLOSED 3 Sep 2026

Closed by commit "G1 and G5: gate the last ungated channel, and take the free
promotion". `desktop/scripts/build-dmg.sh:273` calls `test-swift.sh --quiet || die`,
honouring `SKIP_SWIFT_TESTS`.

**Re-measured 12 Sep 2026:** the evidence line below now returns the opposite of
what it says — `3`, not `0`. Kept because a register entry whose own command
contradicts it is the clearest possible statement of why these are re-measurable.

_Original entry:_ The `.dmg` is a real shipping channel — Developer ID, notarised,
direct download — and it was the one path neither `mac-build.yml` nor
`build-all.sh` covered. A red Swift suite could reach a notarised download.
**Evidence:** `grep -cE 'xcodebuild (test|build-for-testing)|test-swift' desktop/scripts/build-dmg.sh` → `0`.

### G2. The fake-success auditor produces a fake success

`tests/test_no_fake_success_acceptance.py` is the executable audit that asserts
every success signal has a real artifact behind it. Root `CLAUDE.md` lists it
under "Built already".

It has never run. **6 tests, 6 skipped, exit 0** — and a skip is indistinguishable
from a pass in a summary line, a badge, or a close-out report. The auditor built
to catch success-without-substance is itself reporting success without substance.

**Evidence:** `pytest tests/test_no_fake_success_acceptance.py -q -m slow` → `6 skipped in 0.88s`.
Note the `-m slow`: since 4 Sep 2026 `addopts = -m "not slow"` deselects the marker by
default, so the bare form reports `6 deselected` and measures nothing. Re-measured
4 Sep 2026 — it was 8 until `8094490e` parked the Zoom leg as a path no user can reach.

**Blocker, measured 3 Sep 2026 — and it is not a fixture-generation problem.** The
six legs are 2 providers × 3 inputs, and they skip on three conditions: no
provider API key, absent input, no Whisper backend. the gitignored local fixture slot
contains **a README and nothing else**, so the test has never run *anywhere* —
not in CI and not locally — `@pytest.mark.slow` is deselected by default in both
since 4 Sep 2026, and there is nothing to run it against anyway.

That README specifies the work exactly: **one ~5-minute call exported natively from
each of Zoom (`.vtt`), Microsoft Teams (`.docx`) and Google Meet (`.docx`)**. It is
~30 minutes of human time on three accounts, and it cannot be synthesised —
[coverage-inventory.md](coverage-inventory.md) §1 already argues a synthetic docx
parses by construction against the Teams-shaped parser and proves nothing. Running
it then fires paid LLM calls against real interview data, which is why it is a
local, keyed, human-initiated tier by design.

So *"6 skipped in CI"* is correct behaviour. The defect is the claim: root
`CLAUDE.md` lists it under "Built already" without any of the above.

**Cheap interim:** make the skip *loud*. A suite that reports "6 skipped" where
someone expects "6 passed" is only safe if somebody reads the word. **Precedent set
4 Sep 2026** in `tests/test_autocode_discrimination.py`, whose live-LLM skip message
now leads `SKIPPED, NOT PASSED` and names the provider failure kind — copy that shape
here when the fixtures land. That harness used to *error* on an unfunded account, so
every local close-out reported 3 non-regressions; the wording is the other half of the
same fix.

---

## Tier 2 — the gap hides its own growth

### G3. `mypy` is soft, and has accumulated 238 errors — ⚙️ **ceiling set 3 Sep 2026**

**Evidence:** `mypy bristlenose/ --ignore-missing-imports` → `Found 238 errors in 43 files (checked 156 source files)`.

This is the ratchet case in its purest form. It cannot be promoted to blocking
cheaply — 238 errors is a project, not a commit. But nothing stops it growing,
and the number is the proof that it grew. Soft-with-no-ceiling is not a policy;
it is the absence of one.

**Closed as a growth risk, not as debt.** `scripts/check-ratchet.py` holds it in
CI — **149 as of 4 Sep 2026**, down from 239 after `7aaa7f37` cleared the two
mechanical classes. The listing step stays soft so a human still sees the errors;
the ratchet gates the count. Nothing here schedules the work of reaching zero,
and the script says so — a ceiling is not a plan.

**The ceiling did not follow that fall on its own, and for a day it held 239
against a tree measuring 148** — 91 errors of headroom, which is a gate that
passes whatever happens. Why nothing noticed, and the three changes that close
it, are in G4.

### G4. Nothing in the tree says "this number must not increase" — ⚙️ **shipped 3 Sep 2026**

Measured candidates, all currently ungated in this direction:

| number | today | why it matters |
|---|---|---|
| mypy errors | 238 | G3 |
| skip sites in `tests/` | 25 (3 skip, 3 skipif, 19 runtime) | a skip reads as a pass |
| `@pytest.mark.slow` | 7 | excluded from CI by `-m "not slow"` |
| e2e allowlist entries | 4 | governed, but uncapped |

The colour vocabulary was hard / soft / informational. **The missing fourth is the
ratchet** — a number allowed to be non-zero but not allowed to rise. It is the
only colour that fits G3, and the only one that would have made the others
visible while they grew.

**A ratcheted number must be a property of the code, not of the toolchain.** `mypy_errors`
was not, and its first real CI run failed because of it: identical source measured 238 on
the dev Mac and 239 in CI, because `pyproject` pins `mypy>=1.13` — a floor — so a fresh
install resolves whatever is newest. Such metrics now carry `authority: ci`: enforced
there, advisory locally, and `--tighten` refuses to lower one from a local run. Pinning
mypy exactly would be the better fix, but that is a dependency-policy decision.

`scripts/check-ratchet.py` now holds all four in CI, ceilings in
`docs/testing/ratchet.json`. `--tighten` only ever lowers them; raising one is a
deliberate human edit in a commit that has to say why, because a ratchet the
tooling can loosen is not a ratchet. Its own red was proven against a **real**
added `@pytest.mark.slow`, per G8, not against an edited ceiling.

**A ceiling that stops following its number down is a gate that stops gating, and
that took one day.** `7aaa7f37` cleared two mechanical classes on 4 Sep 2026 —
238 → 148 — and the ceiling stayed at 239, so the ratchet would have accepted 91
new errors without a word. Nothing was obliged to notice: `authority: ci` means
`--tighten` refuses from a dev machine, and the local report printed the
measurement alone for such a metric, so a ceiling 91 above it read exactly like a
ceiling at it. Three changes close it, none of which is "remember to look":

* the report always names **both numbers**, whoever owns the metric — off CI it
  stops there and does not call the gap slack, because on this side it cannot
  tell slack from toolchain, and a permanent "1 of slack, go tighten it" is how
  a line stops being read;
* a CI run with headroom emits a `::notice` annotation on the run page, naming
  the command that fixes it — there the measurement *is* the authority, so
  headroom there really is slack;
* `.github/workflows/ratchet-tighten.yml` measures on a fresh CI install, using
  the gates job's exact recipe, and uploads the result; `--adopt` installs it
  here, taking only the ceiling and its provenance stamp so prose edited since
  the run survives, and refusing a CI-owned number the stamp does not say CI
  measured. Dispatched, not automatic: tightening on every green push would lock
  in a dip a laxer mypy release caused and fail the next run on unchanged
  source — the 238/239 incident with the human taken out.

That last step uploads rather than commits because **CI cannot commit to `main`**
— see G9, found while building it.

Tightening also **preserves** `note`, which it used to delete: the entry was
rebuilt from `METRICS`, so every key living only in the JSON went with it — the
prose arguing why a number is what it is, which is the whole reason a ratchet is
better than a suppression. `scripts/test-check-ratchet.py` pins that and the
reporting, and was watched red against the pre-fix script.

**Closed 4 Sep 2026 — and the round trip immediately justified `authority: ci`.**
Run `33881394121` measured **149**, not the 148 this Mac reports, because it
resolved mypy **2.3.1** against the local **2.3.0**. A ceiling hand-edited to 148
would have failed its first CI run, which is the 3 Sep incident repeating one
minor version later. The stamp now records which run produced the number, so the
first question after a failure has an answer in the file.

Two things the first real run taught, both worth more than the fix. The
self-test's one environment-dependent case — `run()` inherited the process
environment, so *"a CI-authority metric is skipped outside CI"* ran with
`CI=true` — failed on a runner having passed on a laptop, which is the trap
`CLAUDE.md` already names and which no amount of local green would have found.
And it failed *usefully*: the self-test runs before anything is measured, so it
blocked the tighten, the artifact and the summary. Nothing published a number
whose write path nobody had checked.

---

## Tier 3 — decisions already teed up, unmade

### G5. ✅ `check-locales.py` is clean, and `--strict` is free — CLOSED 3 Sep 2026

Taken, by the same commit as G1. `.github/workflows/i18n-check.yml:39` runs
`python scripts/check-locales.py --strict`, with an inline comment dating it.

_Original entry:_ **Evidence:** `scripts/check-locales.py` → `✓ All locale checks
passed`, exit 0. A soft gate that is currently green is a free promotion — the
exact inverse of G3. It had been decidable since 21 Aug 2026 and undecided since.

### G6. Unverified findings in the release-system audit — ✅ **triaged 3 Sep 2026**

`design-release-system-audit.md` carried findings marked unverified, untriaged
since the morning after the 0.25.2 incident. Release machinery rather than
testing, but the same shape: findings with no owner and no expiry.

**First correction: there were three, not five.** The earlier count counted
occurrences of the word, including the legend that defines it. The doc's own
tier-2 line says *six*, disagreeing with its table. Three numbers, all written by
people reading the same file.

**Outcome of checking all three against the tree:**

- **3.6** (`upload-testflight` printing "confirmed present in ASC" unconfirmed) —
  real, and **already fixed**. It now `die`s on an unparsed delivery UUID, sets
  `CONFIRMED=1` only inside the successful `--build-status` branch, and exits 1 on
  "Delivered, but UNCONFIRMED".
- **3.8** (snap publish jobs green-no-op without store credentials) — real, and
  **already fixed**. Both publish jobs now `exit 1`, carrying the finding's own
  reasoning in the error text.
- **`--ref main` drift** (§4) — **confirmed and still open**, but narrowed. Edge
  only: `snap-stable` is correctly pinned to the tag. And the defect is the
  *version claim*, not the ref — `--ref main` is arguably right for a channel whose
  meaning is *latest main*; what misleads is an edge snap built from `main + drift`
  announcing a released `X.Y.Z`, because `craftctl set version` stamps from source.
  Left as a product decision rather than silently patched.

**Both fixes landed in `c6bbf7d9` on 14 Aug 2026 — the same day the doc was last
touched.** The work was done and the status column was not moved, so two closed
findings read as open for three weeks. Same shape as `design-ci.md`'s banner, which
recorded a gap accurately and inertly for three months: **the cost here is not
undone work, it is a register that stopped describing the tree.**

---

## Tier 4 — blind spots in the mechanism built to close the others

Added 3 Sep 2026, the day the mechanism shipped. Both were found by using it, not
by reasoning about it.

### G7. The inventory gate catches drift in what it models, never gaps in the model

`gen-test-inventory.py --check` compares the committed structure against one it
*extracts*. It is therefore exactly as complete as its extractor, and nothing in
the system knows about a fact the extractor does not look at.

**Demonstrated on itself, minutes after it shipped.** A real edit to
`build-dmg.sh` — retitling step 1b's banner — left `--check` **green**, because
the parser derives `phase` from `banner.split("—")[0]` and the descriptive tail
is stripped before comparison. The gate was right; the change was not structural
*in its model*. A second, equally real edit to the stage name did drift, and did
go red in CI. Nothing distinguishes those two edits from the outside.

**A live instance, in the map right now:** `can_skip` for `build-dmg.sh` stages
is inferred by searching a **400-character window** after the stage line for
`SKIP_SWIFT_TESTS`. That is a heuristic; it will be wrong the moment someone
moves the check; and it is currently rendered as a fact in a table. Same shape as
`bn_step_skip`'s two call forms, where a positional-only pattern reported every
skippable gate as unskippable until the rendered table was read by eye.

**State the claim precisely and do not let it inflate:** this replaces *"docs
drift silently"* with *"docs drift only where the extractor is not looking."* A
real improvement; not a solved problem.

Mitigations: keep the modelled set **small and reviewable** — the generated
output is committed, so a change to the extractor lands as a diff someone can
read — and prefer deriving a fact from the thing that *enforces* it over parsing
prose about it.

**A concrete instance, found while proving the sidecar gates (4 Sep 2026):**
`check-bundle-integrity.py` scans `__TEXT,__text` for a zero-run of at least one
page, because the incident it was built for left 16 KB of zeros in a 128 MB dylib.
**42 of the bundle's 224 Mach-Os have a `__text` smaller than one page**, so at the
default threshold they are unscannable by construction — a hole there cannot be a
page long. The first probe picked one of those and stayed green, which looked like
a mute gate and was in fact a gate looking somewhere else. Page granularity is
still the right default for the failure mode that happened; the limit is recorded
here rather than "fixed" with a lower threshold that would fire on legitimate
padding.

The residual is unmechanisable by construction. It needs someone reading the tree
and asking *what is not in here?* — which is how every finding of 2–3 Sep 2026
was made, this one included.

### G8. `--check`'s failure path has been observed once, by hand — ⚙️ **generalised 3 Sep 2026**

Until 3 Sep the gate's red had only been produced against **hand-edited JSON**,
which tests the comparison and not the wiring. Its first CI appearance returned
`skipped`, because `ruff` failed above it — so it proved nothing while looking
like it had.

It has since been watched going red in CI on a real un-regenerated drift
(`4dd87b9c`), with `ruff` passing above it, and green again after regeneration
(`ff488734`). One deliberate exercise, prompted by a human asking for it.

**A gate whose red has never been seen is the exact shape `mac-build.yml` had for
three months** — nominally blocking, structurally incapable of failing, green on
every run including those carrying 16 compile errors. Nothing schedules a repeat
of this exercise, for this gate or any other.

The general form is worth more than the instance: **for every gate, when was its
failure path last observed?** Nothing in the tree recorded that, and it is a
different question from *is it passing*.

**Now recorded.** `scripts/check-gate-proofs.py` sorts every gate into *automated*
(a paired `test-<name>` re-proves the red on every run), *declared* (proven some
other way, with a date that ages), or *unproven*. First run: **3 automated, 4
declared, 16 unproven of 21**.

It does not demand zero, and that is deliberate — 16 is unmeetable today and an
unmeetable gate is one somebody switches off. The count is held by the ratchet
metric `gates_without_proof` instead, so existing debt is frozen while a **new**
gate must arrive with a proof or push the number up and fail. Proven by adding a
dummy `check-*` script: `17 > ceiling 16`, exit 1. The ageing half runs as
`--stale 180`, matching the gate policy's `expires` disposition.

**Its own limits, per G7:** the automated bucket is a naming convention, so a gate
proven another way reads as unproven until declared; and nothing verifies that a
paired `test-*` actually exercises the failure path rather than merely existing.

---

### G9. `main` requires a status check that no job can emit — ⚠️ **found 4 Sep 2026**

**Evidence:** `gh api repos/cassiocassio/bristlenose/branches/main/protection`
requires `ci / test (3.10–3.13, ubuntu-latest)`, `ci / frontend-lint-type-test`
and **`ci / lint`**. `ci.yml`'s jobs are `e2e, frontend-lint-type-test, gates,
package, release-suites, supply-chain, test`. There has been no `lint` job since
`5058bec0` split it into the fail-fast matrix on 3 Sep 2026, so that check can
never report again.

Two consequences, opposite in sign, and the second is the one that bites:

* **Nobody could tell.** `enforce_admins` is false and this is a solo trunk repo,
  so the maintainer pushes straight through a rule that has been unsatisfiable
  for a day. A protection that only ever applies to actors who do not exist reads
  as protection. GitHub says so out loud on every push and it scrolls past —
  `remote: - 6 of 6 required status checks are expected.` immediately above a
  successful `1c9482c9..f842cc4b  main -> main`.
* **It is impassable for anything that is not the maintainer.** The first thing
  to try was `ratchet-tighten.yml` committing its own measurement; that job would
  have been red every time it worked correctly. It uploads an artifact instead,
  which wants no write token and is the better split anyway — but the next
  automation to want a commit will hit the same wall, and will not necessarily
  read it as a wall.

**And the gates matrix is not required at all.** `ci / gates (ruff)`,
`(ratchet)`, `(inventory)`, `(gate-policy)`, `(gate-proofs)`, `(manpage)` are
absent from the list, so every mechanism in this document is outside the rule
that is supposed to hold the branch. That is not urgent while one admin bypasses
everything, and it is exactly the shape of G3 and G8: a rule nobody is obliged to
check.

**Not fixed here.** It is a repository setting, not a file, and picking the
contexts is a decision about how much ceremony a solo trunk repo wants — see
`CLAUDE.md` § Branch workflow, which argues for very little. The honest options
are to name the six `gates` cells and drop `ci / lint`, or to drop required
status checks and let the local gates and `/end-session` carry it. Either is
defensible; the present state is the one that is not, because it claims a
guarantee it cannot deliver.

### G10. Two records of the same run, and every gate reads only one — ✅ **closed 12 Sep 2026**

`mark_session_complete` writes the next run's work list; the terminus event
writes the run's own account of itself. Nothing anywhere compares them. s09
wrote a FAILED session as complete, and both records stayed individually
well-formed: `quote_extraction -> s3: complete` in the manifest, `10 == 9 + 1`
in the terminus. The one driving resume was the wrong one.

**Evidence.** The cached FOSSDA run of 30 Apr 2026 — s3, a 94-minute interview,
hit three consecutive 600 s API timeouts, recorded a `StageFailure`, and was
marked complete in the same breath. `get_completed_session_ids` dropped it from
the work list permanently; `_cached_q_count` then counted it into **both**
`attempted` and `succeeded` (`pipeline.py:1722-1724`), so the next run's
terminus read a clean 10/10 with `failed: []`. The interview contributed nothing
to the report and no re-run would have retried it.

**Four gates pass on it, and three structurally cannot fail.**

- `assert_sessions_accounted` — the arithmetic is *honest* on both runs
  (10 == 9 + 1, then 10 == 10 + 0). Not the "session in no bucket" shape it was
  built for.
- Cross-bucket continuity (`topics.attempted == transcripts.succeeded`) agrees
  too: s08 held the rule, so only s09 lost the session, and the cached count
  restores it to the bucket on the next run.
- The whole-stage guards from `1e1ec118` — abandon on `succeeded == 0`, and
  `mark_stage_complete` refusing empty content — both pass: one failed session
  of a batch leaves the intermediate JSON non-empty and `succeeded != 0`.
- `check-gate-proofs.py` never saw it. It discovers `check-*` scripts; this
  invariant lives inside `pipeline.py`. Per G7: the model, not the gate.

**The general form, and it is not G7's.** G7 is *the extractor is not looking at
this fact*. This is *the fact is consistent inside every artefact anyone checks,
and false only across two of them*. Every assertion we own is single-run and
within-bucket. The manifest is cross-run state, and nothing compares it to the
run record written beside it. The cheap check that would have caught it is one
line of set arithmetic: **a session id in the manifest's completed set must not
appear in any `failed` list in `pipeline-events.jsonl`.**

**Closed in two commits.** `6277eabe` made the per-session record honest — one
`_record_session_outcomes` (`pipeline.py:399`) that both stages
call, rather than a second inline copy, because an uncommented inline copy is
exactly how the s09 one went missing. That was **necessary and inert**: a
partially-failed stage was still marked `COMPLETE`, so `_is_stage_verified` took
the full-cache read and never consulted those records. The follow-up (12 Sep)
records failures as `StageStatus.FAILED` rather than omitting them — absence
derives to `COMPLETE` — and stops `mark_stage_complete` forcing `COMPLETE` over
its own session map. Two-run probe: run 2 now re-extracts only the failed
session.

**The lesson worth keeping is the day in between.** The first fix was correct,
tested, proved red against the pre-fix tree, and reported as "the failed session
is retried on the next run" — which was false, because nothing had ever run the
loop twice. A guard test that stops at "the manifest says the right thing"
cannot see a coarser record overriding it.

**What the researcher saw in between.** `bristlenose status` puts a green tick
on the stage — `✓ Quotes  8 quotes (2 sessions)` with `✓ Transcribe  3 sessions`
two rows above it, the discrepancy in plain sight and unmarked — and a re-run
returns `(cached)` instantly without retrying anything.

**The gate is `test_a_failed_session_is_retried_on_the_next_run`**, which runs
the project twice and asserts run 2 attempts exactly the failed session. Watched
red against **each half of the fix reverted independently**. Its fixture had to
be widened from `[]` quotes to real ones first: the degenerate value made
`mark_stage_complete` refuse on its own empty-content guard, so the stage never
reached `COMPLETE` and the short-circuit was unreachable from the test meant to
catch it — **a fixture's zero values can disable the path under test.**

**Two sibling sites carry the un-fixed half**: `pipeline.py:969-972` (s05 —
`s05_transcribe.py:198` writes `results[sid] = []` on failure, so the failed
session is a key and gets marked; the helper applies directly) and `:1271-1276`
(s05b — no `StageOutcome` to filter on without changing the stage's signature).

### G11. A gate that ran, reported green, and exercised nothing — ✅ **closed 12 Sep 2026**

The acceptance matrix's cloud cells reported PASS from **7 July to 4 September**
while making zero LLM calls. Not a skip, not a crash, not a stubbed assertion: the
cells ran, the invariants were applied, and every one of them genuinely held. They
held against the *previous run's report*.

**The distinguishing property, and why it is not G7 or G10.** G7 is *the extractor
is not looking at this fact*. G10 is *the fact is consistent inside every artefact
and false only across two*. This one is: **the artefact was real, well-formed, and
satisfied every invariant — only its provenance was wrong.** No assertion could
have caught it, because no assertion was false. Four gates and 45 tests were
looking straight at a valid report and reading it correctly.

**Mechanism.** `run_matrix.py` wrote each cell to a fixed directory and never
cleaned it. `bristlenose run` *resumes*: handed a manifest whose stages are all
COMPLETE it reloads the cached results, re-renders, exits 0 and calls no LLM. The
cell prints `Resuming: all stages complete` — the thing under test behaving
correctly. Compounding it, `is_green` counted `FAIL_EXPECTED` as green, so a
provider that could not start a run *at all* still yielded
`GREEN: all 4 cells green` and exit 0.

**Evidence.** `.bristlenose/llm-calls.jsonl` in each cell directory, empty on runs
that reported PASS. The tell was the absence of a file's contents, not the presence
of a wrong value — which is why reading the summary could never surface it.

**Closed** by commits "acceptance matrix: a cell that reuses its directory tests
nothing, and a failed provider is not green" and "acceptance matrix: prove the
runner goes RED, synthetically and for nothing". `prepare_cell_dir()` wipes at the
start of every cell; only a pass or declared skip is green; and
`tests/test_acceptance_matrix_synthetic.py` drives the real runner against a fake
`bristlenose` for 7 scenarios, offline and free, mutation-verified (restore the old
green rule → 3 red; delete the wipe → 2 red; restore both → 45 green). Verified
live: a cloud pass now makes 5/4/5 real calls with no resume.

**Residual, and it is the reason this stayed open two months.** *Nothing schedules
`run_matrix.py`.* No cron, no launchd job, no CI workflow; it is absent from
`inventory.md`, and `check-gate-proofs.py` cannot discover it (that script finds
`check-*` scripts only — G8's stated limit). It is a gate by function that is
invisible to every register in this document, so the window was detectable only by
a human choosing to run it. Enrolling it would change G8's discovery convention;
that call is open.

**The generalisable tell:** a gate whose cost is "needs keys and spend" is a gate
nobody exercises, and therefore a gate whose failure path has never been seen. Ask
what it would cost to make it provable *without* the expensive dependency — here, a
fake executable, two seconds, zero pence.

## Explicitly NOT gaps

Recorded so they are not re-derived as problems by the next reader.

- **The 26 container/subtitle ingest formats are covered**, by a cheap pytest
  that generates fixtures at test time via ffmpeg. Only `.docx` needs real
  exports, and for a stated reason: a synthetic docx parses by construction
  against the Teams-shaped parser, proving nothing. "27 formats untested" would
  be wrong.
- **The e2e allowlist is small** — 4 entries against the 10 its own register set
  as the threshold for building tooling.
- **`ci.yml` and `snap.yml` carry unpipefailed piped steps**, and they were
  triaged on 3 Sep 2026 as benign: a help-text display, a diagnostic inside a
  failure branch, an `if ! zipfile … | grep -q` that fails safe, and an
  `ls | head` for a path. Named in [inventory.md](inventory.md) so a future
  reader can re-judge rather than re-discover.

---

## What Phase 3 has to decide

1. **G1 now?** It is small and it is a shipping channel.
2. **Adopt the ratchet as a fourth gate colour**, and give G3 a ceiling.
3. **Take G5**, since it costs nothing today and gets more expensive the longer
   the tree is allowed to drift.
4. **Record when each gate's failure path was last observed** (G8), and treat a gate
   whose red nobody has seen as unproven rather than passing.
5. **Give every soft gate an expiry or a ratchet.** Not a new rule so much as the
   one that was already written in `design-ci.md` and never enforced.
