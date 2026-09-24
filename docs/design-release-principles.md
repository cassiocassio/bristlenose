---
status: current
last-trued: 2026-09-23
trued-against: the 25 failed step attempts recorded in .release/*/events.jsonl for 0.28.0–0.31.2, and release-premortem incidents 1–34
---

# Release principles — what this machine has learned to believe

*Every line below was paid for. Where a principle has an incident behind it, the
incident is named: `docs/release-premortem.md` holds the numbered ones and
`docs/release-log.md` the per-release accounts. A principle with no anchor is
borrowed from the literature and has not yet cost us anything — treat those as
weaker, and delete any that never earns its keep.*

**What this is not.** Not a checklist, not a gate, and nothing mechanical reads
it. `scripts/README.md` says what to type, `desktop/scripts/REPORT-STYLE.md`
Part 2 says how a script in this chain must behave, and
`docs/design-release-machine.md` is the architecture. This file is the *why*
underneath all three, written down because it kept being re-derived at 2am.

## The shape of the problem

The release train is a **saga**: a sequence of local transactions across systems
that share no coordinator, where atomicity is impossible and you get
compensation rather than rollback. The canonical saga structure is compensatable
steps → a **pivot** → retriable steps, and that is exactly the step table's
order. The tag is the pivot.

Three consequences follow from that one fact, and most of this document is
those consequences.

- **Before the pivot everything is disposable.** Measured 23 Sep 2026: 24 of 25
  recorded step failures across 0.28.0–0.31.2 happened before the tag. That is
  the region where patience is free.
- **After the pivot nothing is.** A published PyPI version and a spent
  TestFlight build number are *absorbing states*. No ingenuity un-publishes
  them.
- **Success is a conjunction and failure is a disjunction.** Roughly a dozen
  steps and forty-odd checks must all hold; any one stops the train. The escape
  is not more reliability per check — it is fewer checks in the critical window,
  and failures that do not terminate.

## Ordering — where a step goes

1. **Irreversible last.** Sort by reversibility, never by convenience.
   _0.25.2: three channels shipped on a version the suite then rejected, because
   uploads preceded the verdict (premortem 5)._
2. **One pivot, not several.** Each absorbing state multiplies the partial-failure
   states you must reason about. We have three — the PyPI version, the
   TestFlight build number, the `.dmg` permalink — and only the first is
   unavoidable.
3. **Cheap-and-decisive first.** Order the reversible prefix by failure
   probability ÷ cost to run, descending. Failing at second 3 costs nothing;
   failing at minute 11 costs the night.
4. **No irreversible act without a complete verdict about the exact artefact** —
   not a recent verdict, not one about the branch. _Incidents 29, 30: a verdict
   about a commit applied after the commit moved._
5. **An irreversible step's precondition must be strictly stronger than the act.**
   `verdict_tag_provenance` refuses a dirty tree *and* a moved HEAD, because the
   tag can be neither un-pushed nor re-pointed once PyPI has the version.

## Preconditions — acquire before you need

6. **Resolve every capability up front** — credentials, signing identities,
   profiles, tokens, reachability. The unattended run makes this
   non-negotiable: the human is asleep, so a missing keychain item at minute 40
   is a dead night. _Three of the 25 failures were a signing identity discovered
   eleven minutes into an expensive step; fixed after 0.29.1 by resolving and
   probing credentials above the confirmation prompt._
7. **Fail fast on preconditions, fail slow on transients.** Opposite treatments.
   Conflating them is the most common error in this class.
8. **A check that cannot run must say it could not run** — never pass by
   default, never fail by default. _REPORT-STYLE.md, the fail-open cluster._
9. **Discovery belongs before the window, not inside it.** A release run should
   contain acts, not questions. Every question it asks at 11pm that a person
   could have answered at 6pm costs a night, and the measurement is blunt:
   across 0.28.0–0.31.2, three releases died on an uncommitted working tree and
   one on genuinely red tests. None of those is a machine failure and none of
   them needed to happen in the dark. `release.sh ready` is this principle
   wearing a verb — the same checks, moved to where they are cheap.
10. **Some preconditions can only be printed, never probed.** The probe for
    Finder automation is an Apple event to Finder, and firing a permission
    dialog from automation trains a person to click Confirm without reading.
    Print the check and let them run it. _0.29.0: build-dmg died ~30 minutes in
    on "Not authorised to send Apple events to Finder (-1743)" — a permission,
    not a flake, which no retry could ever have fixed._

## Oracles — reading a world that lies by omission

11. **Three outcomes minimum: yes / no / could-not-ask.** A two-valued check has
    to spend one value on both "no" and "I could not tell".
    _0.31.1 and 0.31.2, incidents 33–34: a 503 mid-watch and a silent empty
    lookup, both read as a negative verdict._
12. **A successful probe beats an unsuccessful one; an unsuccessful probe beats
    nothing.** `unreachable` never rolls up as pass.
13. **Provenance beats recency when two reads disagree.** A confirmed delivery
    cannot be un-happened by a later empty read. _0.29.0: an ASC read inside the
    propagation window offered to re-spend a build number; only Apple's own
    DUPLICATE refusal stopped it._
14. **Break ties by asymmetric cost** — believe the reading that is cheaper to be
    wrong about. On an irreversible step that always means stopping.
15. **Never infer a negative from an empty result without checking that the call
    succeeded.** `$(…)` discards the exit status, which is precisely what made
    "the API failed" and "the API found nothing" indistinguishable.
16. **Eventual consistency has a propagation window; give a read that window
    before concluding absence.** `BN_PROBE_WINDOW_S`.

## The check–use gap (TOCTOU)

*Most incidents in the log are one bug family wearing different clothes: the
world changed between the check and the use.*

17. **Every check has a shelf life. Name it.**
18. **Prefer content-addressing to re-checking.** Make the artefact carry the
    property — a lock file, a digest, a pinned closure. This deletes a failure
    mode instead of detecting it faster, and it is the outstanding structural
    answer to dependency drift.
19. **Bind a verdict to an identity, not to a time.** "CI passed for sha X",
    never "CI passed". _`ci-sha`, and the `sha/<step>` artefact provenance._
20. **Where the window cannot be closed, re-verify at the point of use.**

## Effects and idempotence

21. **Every step is idempotent, or guarded by a probe.**
22. **Exactly-once does not exist.** At-least-once plus idempotence is the
    achievable thing.
23. **A non-idempotent effect needs an external idempotency key.** Build numbers
    and version strings *are* those keys — which is why spending one is
    permanent and why `probe_done` exists.
24. **Write the marker after the act and read it before** — and distinguish "no
    marker" from "marker unreadable". _`probe_done`'s exit 1 vs 2 vs 3._

## Retry

25. **Retry transients; never retry a verdict.** Retrying a red CI is asking it
    to change its mind.
26. **Bounded, backed off, and jittered** wherever anything runs concurrently.
27. **Retry cost is the budget.** Make retries cheap before making them
    numerous — an eleven-minute retry is why a script gives up rather than
    persisting.
28. **Three distinct moves; do not blur them:** retry-same, remediate-then-retry,
    alternate-route.
29. **A remedy must not mutate state an already-passed gate certified** — or it
    must re-run that gate. This is what makes a tree-mutating remedy stop the run
    rather than continue it.

## Safety versus liveness

30. **Name which property each mechanism buys.** Gates buy safety ("nothing bad
    ships"); retries buy liveness ("the release eventually completes").
31. **Never trade safety for liveness on an irreversible step. Trade freely in
    the other direction.**
32. **Failing closed is not the same as giving up.** Refusing to proceed past a
    gate and abandoning the run are different acts that `exit 1` currently
    conflates. _Incident 33: a 38-minute wait discarded over one dropped API
    call, buying no safety at all._

## Observability

33. **An append-only ledger, one line per state transition.** History, not state.
34. **Record what a step was configured with, not only that it ran.**
    _0.27.0: an inherited signing identity cost a notarisation round-trip and the
    ledger could not say why._
35. **Liveness belongs outside the ledger; staleness is the signal.** A status
    the fold does not recognise takes the stranded path, so a heartbeat in the
    ledger would make every long step unresumable.
36. **A zero-byte log is a bug, not a state.** Every failure says something.
37. **Total functions over parsed state.** An unrecognised status folds to
    `corrupt`, never through to "run it again".
38. **Redirect, never pipe, when you need an exit code.** _0.27.0 #1: five runs
    reported exit 0 and three had failed._

## Gates as a population

*A gate is a component. It is born, it ages, and it can die without anyone
noticing.*

39. **Every gate records the incident that caused it.**
40. **Every gate declares a disposition** — hard, soft, ratcheted, or expiring.
    No open-ended softness. _`docs/testing/soft-gates.json`._
41. **A gate that has never fired is unproven, not proven.** Track fire counts.
42. **A gate with no caller is not a gate.** _`check-deployment-floors.sh` had
    five documents claiming it and no invocation for nine days._
43. **A gate whose verdict nobody reads is not a gate either.** _`ratchet` and
    `inventory` were red for all 178 commits of the 0.31.0 window._
44. **Prove a gate red before trusting it green.** Mutation-test it; a test a
    comment can satisfy is not a test.
45. **Retire a gate when its origin bug is fixed at the cause.** _Measured
    23 Sep 2026: the stale-`.xctest` signing race fired in 0.30.0 and 0.31.0 and
    not since `8ae1ecd3` fixed it. A remedy wired to it that day would have been
    born dead._
46. **A mitigation is a new component that can fail.** _Incident 32: a
    four-hour-old push-main guard became the next incident, because it was
    verified only in the environment where it could not misbehave._

## What to measure

*The ledgers already carry most of this; almost none of it is currently read.*

- **Attempts per step per release** — the primary indicator, already tabulated
  per release in `docs/release-log.md`.
- **Clean-run rate.** Measured 23 Sep 2026: zero of seven.
- **Failure class, and recurrence count per class.** This is what converts "this
  again" from a feeling into evidence. Dependency drift: four of 25, in four
  consecutive releases.
- **Share of failures needing a human.** Measured 23 Sep 2026: 11 of 25 needed
  someone to write or decide something; 14 needed only tenacity.
- **Time to first failure**, and **wall-clock burned per failure**.
- **Gate fire counts** — ever fired, last fired.
- **Detection–origin gap**: the layer a defect came from versus the layer that
  caught it.
- **Self-harm ratio**: incidents per release originating in the release machine
  itself. When this rises, stop adding gates and start deleting them.
- **Irreversible acts spent per release** — build numbers, versions.

## Formalisms worth the effort, and the ones that are not

**Worth it.** Model-checking the step state machine (TLA+ or Alloy): the state
space is small — pending/running/ok/fail/skipped crossed with resume — and it
has already produced at least four real bugs of exactly the kind a model checker
finds. STPA or FMEA for the rest, because the framing fits: nearly every
incident here is an unsafe *interaction* between components that each did what
they were specified to do. Deterministic fault injection in a simulator rather
than chaos in production — `experiments/dep-resolve-spike/` is the seed.
Hermetic, reproducible builds as the structural answer to drift.

**Not worth it.** Formal specification of the whole pipeline. Most of the chain
is glue to third-party systems whose contracts are undocumented and change
without notice; a proof about our half says nothing about theirs.

## Philosophy

**Authorisation, not execution** — automate the mechanical, let the human gate
the rest.

**The agent may diagnose, retry and fix; it must never be what authorises an
irreversible act.** This is the invariant that makes an adaptive supervisor over
a deterministic kernel safe. It held on 23 Sep 2026, when the tag gate refused a
dirty tree and the agent stashed rather than forced.

**Fix at the cause, or record an accepted risk. There is no third option.**
Every incident leaves behind code, a register entry, or an explicit acceptance —
otherwise the learning evaporates with the session that had it.

**Prefer deleting a failure mode to detecting it faster.**

**The pre-pivot region is free. Spend your patience there.**
