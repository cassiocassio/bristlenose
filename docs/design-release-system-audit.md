---
status: §1, §2, §3 closed (§3.5 folded into §1's fix); §5 open and awaiting a decision
last-trued: 2026-08-14
trued-against: the §1+§3.5 change — pypi environment hold live, strict-macos wired, flow rewritten; §5 as first written against 824655d6
---

# Release-system audit — findings

Eight parallel reviewers over `scripts/`, `desktop/scripts/`, both release skills and
the three workflows; high-severity findings then handed to adversarial skeptics
instructed to **refute**, several of whom re-derived the behaviour by running the
scripts. 64 findings, **9 confirmed**, 1 refuted (and replaced by a better one), 6
high-severity uncapped. Grounded in the live 0.25.2 incident, and seeded with the
twelve findings already known from that session so the lenses hunted past them.

**Verdict.** The gates are strong and mostly earned — a lens tasked with dismantling
them failed, tracing each to a taken rejection. What makes the system feel
*"complex and slightly unpredictable"* is not the gates. It is that **the seams
between components are unowned, several authority signals do not mean what they
appear to mean, and release knowledge lives as prose in four places that drift.**
The unpredictability is a specification problem wearing a complexity costume.

> **Triaged 3 Sep 2026 (gaps.md G6).** The three findings still marked unverified were
> checked against the tree. **3.6 and 3.8 were real and had already been fixed** on
> 14 Aug by `c6bbf7d9` — the same day this doc was last touched, so the fixes landed
> and the status column never moved. The `--ref main` note in §4 is **confirmed and
> still open**, now narrowed to a version-claim decision rather than a bug.
>
> Note the tier-2 line at the foot says *"six unverified findings"* while the table
> marks three. Both numbers were written by people reading this file.

Every finding below carries its verification status. `CONFIRMED` means a skeptic
established the behaviour independently; `unverified` means plausible but untested —
treat accordingly.

---

## 1. The reframe — the irreversibility line is movable

`CONFIRMED` · [.claude/skills/bn-release/SKILL.md:133](../.claude/skills/bn-release/SKILL.md)

Phase 5's whole topology rests on *"push the tag and you have burned an immutable
PyPI version."* That is false as `release.yml` stands. The version burns only when
the `publish` job succeeds, and publish already runs in a GitHub `environment: pypi`
(`release.yml:115`) whose `protection_rules` are currently empty. A required
reviewer there is a settings toggle, no code.

With the hold in place:

```
today:   bump → [75 min serial Mac lane] → tag push = point of no return → tag-CI → publish
option:  bump → push main+tag → (tag-CI ~25min ∥ Mac lane ~75min) → both green
         → TF + dmg uploads → approve publish → PyPI → website → snap
```

- The tag push becomes reversible; the constraint forcing the Mac lane to precede
  the tag evaporates.
- Tag-CI overlaps the Mac build. Wall clock ~100 → ~75 min.
- **The 0.25.2 incident becomes a zero-channels-published non-event.**
- The single authorisation (D3) moves from chat to the GitHub approval UI — arguably
  stronger, since the approver sees the run.

Costs: the release depends on out-of-repo settings, which must be written down or
the hold silently doesn't exist on a fresh setup; an abandoned release leaves a
deleted-tag stub on origin.

Retires K2 and K5, and repairs the claim in §3 below.

## 2. The bump seam — three lenses found it independently

`CONFIRMED` ×3 · [SKILL.md:120–126](../.claude/skills/bn-release/SKILL.md) ·
[new-release/SKILL.md:43](../.claude/skills/new-release/SKILL.md) ·
[bump-version.py:243](../scripts/bump-version.py)

Phase 5 step 1 runs `bump-version.py` + commit, then step 3 hands off to *"new-release
Steps 4–6"* — but **Step 4 is the bump**. A literal execution either re-runs it (guard
exits non-zero; release halts with the tag still at the pre-bump commit) or matches
new-release's *publish-pending* definition, whose instruction is *"Skip Step 4 — push
main + the existing tag"* — **pushing a tag at the pre-bump SHA**.

Sharper still, applied to the live state (tag `6ddae7ce` = partial fix, main
`824655d6` = corrected, PyPI 404): new-release's publish-pending tree offers only
*flaky → rerun* or *fixed-later → move the tag*, and **the flake it names as its
canonical example is this exact lifecycle test — which was in fact a genuinely
incomplete fix**. A rerun of `6ddae7ce` plausibly goes green and publishes the partial
fix immutably. A skeptic ran the proposed discriminator —
`git log v0.25.2..origin/main -- bristlenose/ frontend/` returns non-empty — confirming
a mechanical gate would forbid the rerun branch in precisely this state.

Options, most-dissolving first:

- **(a)** Fix at source: `bump-version.py` tags *after* the commit, or gains `--no-tag`.
  Kills this seam, K6, and the delete/retag dance in every runbook at once.
- **(b)** Cheap: hand off *"Steps 5–6 only"*; Phase 5 step 1 spells the full
  bump→commit→retag unit. Duplicates knowledge the skill forbids itself to duplicate.
- **(c)** Add the missing third branch — **supersede** (bump X.Y.Z+1) — gated on that
  `git log` probe.

Recommendation: (a) + (c).

## 3. The fail-open cluster — gates that answer green when they never checked

The house's documented nemesis (`&& ok`) in new clothes. The unifying defect:
**these scripts fail correctly when a check runs and fails, and answer green when a
check could not run.**

> **Closed 14 Aug 2026.** 3.3 in `e9158717`; 3.1, 3.2, 3.4, 3.6, 3.7, 3.8 in
> `c6bbf7d9`. Each fixed gate was driven through its full decision table,
> including the states that previously read green. **3.5 closed the same day as
> part of the §1 change**: the policy question resolved to "blocking on release
> runs, informational on daily pushes" — `ci.yml` gained a `strict-macos`
> workflow_call/dispatch input and `release.yml` passes it true.

| # | Finding | Status |
|---|---|---|
| 3.1 | **Preflight never compares tag→HEAD.** [check-release-ready.sh:166](../scripts/check-release-ready.sh) passes on tag *existence*. Run today it prints `✓ v0.25.2 exists` and reaches READY — the exact mid-flight hazard the maintainer paused on is invisible to the tool whose job is release-state hazards, and re-running the skill is the documented resume mechanism | `CONFIRMED`, reproduced live |
| 3.2 | **CI check cannot fail pre-push.** [check-release-ready.sh:266](../scripts/check-release-ready.sh) collapses never-pushed, wip-only (K7), in-progress and gh-failure into one non-blocking warn labelled `no CI run found`. Warnings never touch the exit code; the skill's authority rule is exit-code-shaped | `CONFIRMED`, empirically |
| 3.3 | **The bundle self-test is dead code on every build.** [build-all.sh:183](../desktop/scripts/build-all.sh) skips on app-sandbox entitlements, which `sign-sidecar.sh` applies *unconditionally* since 14 Jul (`4c549c36`). The "covered by 1b + ASC" message is a false equivalence: 1b covers source→spec only, ASC has no idea whether PyInstaller dropped a `datas` entry. **The BUG-3/4/5 class is now mechanically unguarded** | `CONFIRMED` — worse than reported |
| 3.4 | **Identity check fails open on parse failure.** [check-pkg-shippable.sh:143](../desktop/scripts/check-pkg-shippable.sh): empty `sed` extraction → `ok "version … agrees with tree"` for a comparison that never ran — in the only defence against the cross-channel stale-artefact class its own header warns about | `CONFIRMED`, empirically |
| 3.5 | **`continue-on-error` on macOS test cells.** [ci.yml:87](../.github/workflows/ci.yml) — deliberate and commented, but it means **"CI green" certifies Linux for a Mac-first product** whose Mac artefacts additionally never pass through CI. The flake that saved 0.25.2 happened to be on Linux; had the race only manifested on macOS, the release would have published | self-verified true |
| 3.6 | **`upload-testflight`'s fallback prints "confirmed present in ASC" unconfirmed.** [upload-testflight.sh:251](../desktop/scripts/upload-testflight.sh) — the script's whole reason to exist is not trusting altool's exit 0, and its else-branch soft-warns then prints the confirmed banner anyway | **CONFIRMED and FIXED** — `c6bbf7d9`, 14 Aug 2026 |
| 3.7 | **`bump-version.py` prints `Updated <file>` whether or not `re.sub` matched.** A pbxproj format change silently no-ops while claiming success | found by 2 lenses |
| 3.8 | **Snap publish jobs green-no-op on missing store credentials** — on the *deliberate-publish* paths only, where a silent skip is worst | **CONFIRMED and FIXED** — `c6bbf7d9`, 14 Aug 2026 |

One house rule covers the cluster: **a check that could not run reports that it could
not run.**

3.5 deserves its own decision rather than a reflex: blocking on macOS *only for
tag-triggered runs* (strict for releases, informational for daily pushes) is probably
the right shape.

## 4. Snap — the refuted finding, and the real one underneath

A lens claimed edge can never ship the tag's bits. **`REFUTED`** — and the disproof is
more interesting than the claim. [snap.yml:65](../.github/workflows/snap.yml) gates
`publish-edge` on `github.event_name == 'workflow_dispatch'` with **no ref condition**,
so `gh workflow run snap.yml --ref vX.Y.Z` fires **both** `publish-edge` and
`publish-stable`.

So the design doc's *"the ref is the channel selector"* is not quite true: it selects
*stable additionally*, not *instead*. A Tier 2 promotion double-publishes. Benign today
(same bits to both channels), but it means the mental model in the skill and the design
doc does not match the workflow, and any future `channel` input must gate **both** job
conditions.

Separately — **CONFIRMED 3 Sep 2026, and still open.** `--ref main` builds whatever
main is at dispatch time, and snap runs last in Phase 5, giving the longest window for
a post-release commit to land. `adopt-info: bristlenose` +
`craftctl set version="$VERSION"` stamps from source at build time, so a drifted edge
snap still reports X.Y.Z to every probe.

Now characterised precisely, which narrows it:

- **Edge only.** `snap-stable` dispatches `--ref v__V__` and is correctly pinned
  ([release.sh:475](../scripts/release.sh)). Only the `snap edge` row at `:474` uses
  `--ref main`.
- **The guard pattern already exists one row up.** The `tag` step refuses unless
  `verdict_tag_provenance` matches `$CI_SHA_FILE` — *"the tag must land on the exact
  commit strict CI validated"*. Nothing extends that to the snap dispatch.
- **But `--ref main` is arguably right for edge**, whose whole meaning is *latest main*.
  The defect is not the ref; it is the **version claim**. An edge snap built from
  `main + drift` announcing a released `X.Y.Z` is what misleads a probe.

**So this is a product decision, not a mechanical fix, and is deliberately left open
rather than silently patched:** either stamp edge builds with a dev suffix so the
version tells the truth, or pin the edge dispatch to the tag and accept that edge means
*last release* rather than *latest main*. Whoever takes it should read
`docs/design-doctor-and-snap.md` first.

## 5. Relaxations — the mirror review

**Endorsed:**

- **Double notarisation (~20 min/release).** Apple requires notarising the outermost
  distributable; one `.dmg` submission notarises every nested signature. The inner-app
  staple buys exactly one scenario: first launch of the dragged-out app on a **fully
  offline** Mac — near-vacuous for a 30-day expiring BYOK sampler whose user pulled
  644 MB seconds earlier. **Must land with the matching `check-dmg-shippable` change in
  the same commit**, or the relax fails its own publish gate.
- **`validate-app` inside the upload path (~8 min/release).** The precondition ships
  675 MB to Apple, then `--upload-package` ships it again and the server revalidates.
  Expected loss ≈ zero. Keep check 12 for standalone gate runs.
- **The 9pm rule binds the wrong act.** Its purpose is delivered entirely by holding
  the *tag*; as written it also holds the main push — the one that costs nothing and
  buys CI signal — and is restated on five surfaces. *"Main any time; the tag waits
  for 9pm"* retires the wip-branch workaround as a side effect.
- **The acceptance doc's re-score-every-run protocol is shelf-ware.** The log is empty
  and the first live run went unlogged — the predictable steady state. Event-driven
  scoring (first dry run · any SKILL.md edit · first live run · then failures and
  surprises only) fits one maintainer.
- **`S9`'s byte-identical decline is unsatisfiable by construction** (`CONFIRMED`).
  The preflight hard-fails until prose exists on disk, so a declined fresh release
  *always* leaves drafts. Re-scope to *"no commits, no tags, no uploads; drafts offered
  for restore."*
- **Four copies each of the PyPI poll loop and the tag-surgery tree**, while
  `verify-pypi` and `check-release-ready.sh` now encode both. Collapse the prose to
  pointers; the silent-stall class it guarded now fails loudly red.

**Refuted — leave alone.** This is the part that answers *"is the complexity
warranted?"*: `check-pkg-shippable`'s 16 checks each trace to a taken post-upload
rejection, costing seconds against a 644 MB upload and a forever-spent build number;
`check-dmg-shippable`'s mount-and-interrogate is the 4 Aug create-dmg lesson;
stage 2c's `itms-services` scan is the only coverage in the ad-hoc/IDE loop.

> _Correction, 14 Aug:_ this list originally also defended the inner-app staple
> check ("the staple check is the distinct offline guarantee") — which the
> **Endorsed** list above simultaneously authorised removing. The endorsed side
> won when the relaxation shipped: the staple check was replaced by a
> `codesign --deep --strict` assertion, and offline-first-launch was the
> guarantee knowingly traded. One doc should not argue both sides; the losing
> argument is preserved here as the record of the trade.

> **The artefact gates are earned complexity. The prose sprawl is not.**

## 6. Diagnosis — why it feels unpredictable

1. **Authority signals that do not mean what they say.** READY excludes CI evidence.
   "CI green" excludes macOS. "Tag exists" ≠ tag is right. "Confirmed present in ASC"
   has a path that prints without confirming. Each one trains the operator to distrust
   the instrument, and a distrusted instrument *is* unpredictability.
2. **Unowned seams.** Within a script the discipline is excellent; between components
   (skill↔skill, script↔sibling, skill↔workflow) nothing owns the contract. The bump
   seam, sibling drift (K8), the snap ref/channel model — all seam defects.
3. **Process-memory state.** Phase 6 preaches probe-don't-remember, then needs a
   remembered delivery UUID; the dmg resume path exists as header prose, not mechanism;
   the mid-flight channel-state matrix has no representation anywhere.
4. **Knowledge quadruplication.** Drift between copies is unpredictability on a delay.

## 7. Shortlist

1. ~~`pypi` environment hold + Phase 5 reorder~~ — **done 14 Aug 2026, with §3.5
   folded in**: required reviewer live on the environment (probed by the
   preflight's `publish hold` line, since it lives in Settings, not the tree);
   `release.yml` passes `strict-macos: true` so the release run's macOS cells
   block; Phase 5 pushes main+tag first, builds while both CI runs execute, and
   puts uploads + approval after every verdict. The 9pm guideline now binds the
   approval — which also settles §5's re-scoping item. (§1, §3.5, §5c)
2. ~~`bump-version.py` tags post-commit~~ — **done**, `d6bf3a49`: it no longer
   tags at all; the tag is created after the prose commit (§2)
3. ~~Fail-open sweep as one themed commit~~ — **done**, `e9158717` + `c6bbf7d9` (§3)
4. ~~The two ~10-minute relaxations~~ — **done 14 Aug 2026**: app-level
   notarisation retired from `build-dmg.sh` (the `.dmg` submission covers the
   nested app; trade accepted — one online Gatekeeper lookup on first launch of
   a dragged-out app), with `check-dmg-shippable.sh`'s inner-app staple check
   becoming a `codesign --deep --strict` check in the same commit; and
   `upload-testflight.sh` now sets `BN_SKIP_ASC_VALIDATE=1` so its gate skips
   the pre-upload `validate-app` transfer (announced, upload revalidates
   server-side; standalone gate runs keep it). ~28 min returned per release. (§5)
5. Acceptance-doc rescope: S9's byte-identical decline, criteria for the
   K9/K10 classes (S5 already rewritten for the new order) (§5)

Note on ordering as it actually went: item 3 was done first, because it needed no
decision from anyone. Items 1, 2, 4 and 5 all turn on a judgement — how much the
tag push should cost, whether to depend on out-of-repo settings, what to trade
away — and those are the maintainer's to make.

Everything else is drift-cleanup that can ride along with normal work.

## 8. Live warning

**The current 0.25.2 state sits exactly on the confirmed trap in §2.** The documented
resume path's *flaky → rerun* branch is the dangerous one: a green rerun of `6ddae7ce`
publishes the partial fix to PyPI immutably. The safe branches are **supersede**
(0.25.3) or **move-the-tag-and-rebuild**. Worth deciding before muscle memory meets
the decision tree at 11pm.

## 9. Reviews worth running next

- **Tier-2 fault injections**, now with a fixture list: empty `sed` into
  `check-pkg-shippable`; missing snap credential on a publish path; `DELIVERY=""` into
  `upload-testflight`'s confirm; an out-of-order publish into `upload-dmg`'s retention.
  An afternoon, reversible, converts six unverified findings into knowledge.
- **A game-day tabletop for the resume paths** — *notarisation takes six hours*,
  *ASC down mid-upload*, *laptop dies between dmg-publish and tag-push*. The weakest-
  documented area, and the one Phase 6's probe table cannot express.
- **`what-would-james-bach-say` on the acceptance doc** — its S-tier partly restates
  what shell now enforces, while the observed incident classes (one-green-as-authority,
  mid-run HEAD movement, sibling drift) have no criteria at all.
- **A bus-factor drill.** There is no written inventory of what can only run on this
  one Mac (certs, notary profile, `.ship-local.conf`, SSH agent, gitignored ffmpeg
  binaries). *"Pretend this Mac died"* produces the inventory as a side effect.
- **A supply-chain pass on the release path itself.** `create-dmg` is unpinned via brew
  and unrecorded in the manifest; the snap publish action is SHA-pinned — the pattern
  exists, apply it wider. `/cassandra` before bumping anything release-critical.
- **A channel-state model** in `release-channels.md`: reachable states per channel
  (published / stale / never × tag ahead / behind) with the legal repair for each.
  Phase 6 currently verifies the happy column only. Cheap formality, outsized payoff
  against the "unpredictable" feeling specifically.

## See also

- [design-bn-release-skill.md](design-bn-release-skill.md) — D1–D5, the decisions this audits
- [testing/bn-release-acceptance.md](testing/bn-release-acceptance.md) — the skill's exam; §5 proposes rescoping it
- [release-channels.md](release-channels.md) — the five channels on one page
