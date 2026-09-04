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

**Closed as a growth risk, not as debt.** `scripts/check-ratchet.py` holds it at
238 in CI. The listing step stays soft so a human still sees the errors; the
ratchet gates the count. Nothing here schedules the work of reaching zero, and
the script says so — a ceiling is not a plan.

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

* the report always names the ceiling and the slack, whoever owns the metric;
* a CI run with headroom emits a `::notice` annotation on the run page, naming
  the command that fixes it;
* `.github/workflows/ratchet-tighten.yml` measures on a fresh CI install and
  commits the lowered ceiling — dispatched, not automatic, because tightening on
  every green push would lock in a dip that a laxer mypy release caused and fail
  the next run on unchanged source. That is the 238/239 incident with the human
  taken out.

Tightening also **preserves** `note`, which it used to delete: the entry was
rebuilt from `METRICS`, so every key living only in the JSON went with it — the
prose arguing why a number is what it is, which is the whole reason a ratchet is
better than a suppression. `scripts/test-check-ratchet.py` pins that and the
reporting, and was watched red against the pre-fix script.

---

## Tier 3 — decisions already teed up, unmade

### G5. `check-locales.py` is clean, and `--strict` is free

**Evidence:** `scripts/check-locales.py` → `✓ All locale checks passed`, exit 0.

A soft gate that is currently green is a free promotion — the exact inverse of
G3. Root `CLAUDE.md` already says so and points at `docs/i18n-defects.md`
Decision 2. It has been decidable since 21 Aug 2026 and undecided since.

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
