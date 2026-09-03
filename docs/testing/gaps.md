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

### G1. `build-dmg.sh` has no Swift gate

The `.dmg` is a real shipping channel — Developer ID, notarised, direct
download — and it is the one path neither `mac-build.yml` nor `build-all.sh`
covers. A red Swift suite can reach a notarised download today.

**Evidence:** `grep -cE 'xcodebuild (test|build-for-testing)|test-swift' desktop/scripts/build-dmg.sh` → `0`.

**Fix:** the same block as `build-all.sh` step 1c — call `test-swift.sh`, skip on
ad-hoc, honour `SKIP_SWIFT_TESTS`. **Small.** It didn't land with the rest only
because it wasn't in the ask.

### G2. The fake-success auditor produces a fake success

`tests/test_no_fake_success_acceptance.py` is the executable audit that asserts
every success signal has a real artifact behind it. Root `CLAUDE.md` lists it
under "Built already".

It has never run. **8 tests, 8 skipped, exit 0** — and a skip is indistinguishable
from a pass in a summary line, a badge, or a close-out report. The auditor built
to catch success-without-substance is itself reporting success without substance.

**Evidence:** `pytest tests/test_no_fake_success_acceptance.py -q` → `8 skipped in 0.97s`.

**Blocker:** the format-parity fixtures each leg skips on. Recipe already exists in
[test-data-generation.md](test-data-generation.md); the gap is tracked in
[coverage-inventory.md](coverage-inventory.md) §1.

**Cheap interim:** make the skip *loud*. A suite that reports "8 skipped" where
someone expects "8 passed" is only safe if somebody reads the word.

---

## Tier 2 — the gap hides its own growth

### G3. `mypy` is soft, and has accumulated 238 errors

**Evidence:** `mypy bristlenose/ --ignore-missing-imports` → `Found 238 errors in 43 files (checked 156 source files)`.

This is the ratchet case in its purest form. It cannot be promoted to blocking
cheaply — 238 errors is a project, not a commit. But nothing stops it growing,
and the number is the proof that it grew. Soft-with-no-ceiling is not a policy;
it is the absence of one.

### G4. Nothing in the tree says "this number must not increase"

Measured candidates, all currently ungated in this direction:

| number | today | why it matters |
|---|---|---|
| mypy errors | 238 | G3 |
| skip sites in `tests/` | 25 (3 skip, 3 skipif, 19 runtime) | a skip reads as a pass |
| `@pytest.mark.slow` | 7 | excluded from CI by `-m "not slow"` |
| e2e allowlist entries | 4 | governed, but uncapped |

The colour vocabulary today is hard / soft / informational. **The missing fourth
is the ratchet** — a number allowed to be non-zero but not allowed to rise. It is
the only colour that fits G3, and the only one that would have made the others
visible while they grew.

---

## Tier 3 — decisions already teed up, unmade

### G5. `check-locales.py` is clean, and `--strict` is free

**Evidence:** `scripts/check-locales.py` → `✓ All locale checks passed`, exit 0.

A soft gate that is currently green is a free promotion — the exact inverse of
G3. Root `CLAUDE.md` already says so and points at `docs/i18n-defects.md`
Decision 2. It has been decidable since 21 Aug 2026 and undecided since.

### G6. Five unverified findings in the release-system audit

`design-release-system-audit.md` carries **14 confirmed and 5 unverified**
findings, untriaged since the morning after the 0.25.2 incident. Release
machinery rather than testing, but the same shape: findings with no owner and no
expiry.

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

The residual is unmechanisable by construction. It needs someone reading the tree
and asking *what is not in here?* — which is how every finding of 2–3 Sep 2026
was made, this one included.

### G8. `--check`'s failure path has been observed once, by hand

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
failure path last observed?** Nothing in the tree records that, and it is a
different question from *is it passing*.

---

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
