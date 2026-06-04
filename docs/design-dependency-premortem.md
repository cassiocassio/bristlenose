# Dependency-bump pre-mortem (Cassandra)

How Bristlenose decides what's safe to upgrade — before it upgrades.
This doc ties together three pieces: the `cassandra` **agent** (the
method and the coupling map), the `/cassandra` **skill** (the calling
mechanism and the ledger owner), and the **ledger**
(`docs/dependency-premortem-log.md`, the calibration record).

## Why this exists

Dependabot is good at *detecting* that a newer version exists. It is
useless at *predicting whether taking it will hurt.* Its PR description
is a changelog link and a diff of one line in a lockfile. The judgement
— "will this break the install? break at runtime? drag five sibling
packages? touch an API we don't even call?" — is left entirely to the
human merging the PR.

For most repos that's fine: merge, watch CI, revert if red. Bristlenose
has two properties that make blind-merge expensive:

1. **Silent runtime breaks.** The dangerous failures here don't go red
   at install. They install clean and break when exercised: a numpy
   bump past numba's ABI cap throws only when numba is imported; a spaCy
   model-format mismatch surfaces only when the PII path runs; an LLM
   SDK major silently changes a default only the analysis stage hits.
   CI catches some; the bundled-sidecar desktop path catches fewer.
2. **Coupling clusters.** A bump that looks isolated in the lockfile
   diff (one line, `thinc 8.3→9.1`) is fatal because *something else*
   (spaCy 3.8) pins against it. The PR shows one package; the blast
   radius is six.

The cost of a bad merge isn't the revert — it's the *debugging session
three days later* when the PII path produces empty output and nobody
connects it to the dependency PR that merged on Monday. A pre-mortem
moves that cost forward and shrinks it: predict the break, prove it from
the pins, and decide deliberately.

## Separation of concerns

Three actors, three jobs. Keeping them distinct is the whole design.

| Actor | Job | Output |
|-------|-----|--------|
| **Dependabot** | *Detection* — a newer version exists | A PR per bump (or grouped minor/patch) |
| **Cassandra** | *Prediction* — what breaks if we take it | A ranked pre-mortem + a logged prophecy |
| **The human** | *Decision* — merge / group / ignore / hold | The merge, and the dependabot.yml edits |

Cassandra never merges, never applies, never edits a dependency file.
She foresees and records. The human acts. A later `--score` pass
observes what actually happened and tunes the oracle. This is the same
read-only-reviewer discipline as the other review agents — Cassandra is
their supply-chain-foresight sibling.

## The Cassandra metaphor (and why it's load-bearing)

In the myth, Cassandra's prophecies are always true and never believed.
The curse is the point: a doom-crier who is right about everything is
*operationally indistinguishable* from a doom-crier who is right about
nothing — both get ignored. The myth is a parable about **calibration**,
not foresight.

So the agent is built to earn belief the only way that works: a public
ledger where every prophecy is written *before* the outcome is known,
and scored *after*. Accuracy accrues on the record. The design
consequence — encoded in the agent's voice and self-check — is that a
confident `SAFE` is worth exactly as much as a confident `WILL-BREAK`.
An agent that cries doom at every bump has cursed itself; its reds are
noise and its greens are absent. The contrast (a few reds in a field of
greens) is the deliverable, not the red count.

## The verdict taxonomy

Five labels, chosen so the *time and cost* of each failure is legible:

- 🔴 **WILL-BREAK** — produces a broken state. Sub-split by *when*:
  - *resolver-level* — pip/npm refuses to install. Loud, early, cheap.
    The PR just goes red. You lose nothing but the CI minutes.
  - *runtime* — installs clean, breaks when exercised. Silent, late,
    expensive. **These are why the agent exists.**
- 🟡 **RESOLVER-NON-EVENT** — can't be taken; an upstream pin forbids it
  (FastAPI caps starlette). Dependabot's PR dies on its own. Worth
  naming so nobody hand-forces it, with the *un-gating condition* noted.
- 🟢 **SAFE** — applies clean, exercises clean. Said with the same
  confidence as a red, and with a receipt. The green that lets the wave
  move.
- ❔ **UNKNOWN** — the oracle *could not look*. The package isn't
  installed so its pins are unreadable; the candidate set came back empty
  (a tool silently failed); the gossip research was offline or the
  release is too new to have chatter. UNKNOWN is **not a soft SAFE** — it
  is the explicit absence of a prophecy, paired with the cheap next step.
  The single most dangerous bug this system can have is letting "I
  couldn't look" decay into "looks fine," because that is exactly how a
  silent runtime break sails through. A field of greens with one honest
  ❔ beats a field of greens that swallowed a blind spot.
- ⚠️ **LATENT** — orthogonal annotation: the bump is safe but it
  neighbours a trap that fires under a *different* condition. Recorded,
  doesn't block.

The resolver/runtime split inside WILL-BREAK is the single most useful
distinction in the system. Resolver-reds are self-announcing — CI tells
you. Runtime-reds are the ones that cost a debugging session, so they
are what a pre-mortem must catch that CI won't. **UNKNOWN guards the
input boundary** the same way the runtime/resolver split guards the
output: most of this system's silent-failure surface is at the edges
(empty candidate set, unreadable metadata, failed research), and UNKNOWN
is the label that refuses to let those edges masquerade as all-clears.

## The lifecycle: a hold is a deferred obligation, not a tombstone

The taxonomy above is *point-in-time* — it judges a bump the moment it's
proposed. But the dangerous, long-lived state is what happens *after* a
🔴/🟡: the human adds it to the dependabot.yml ignore list so the red PR
stops recurring, and then it sits there forever. A bare ignore is a
**tombstone** — it makes the problem disappear and pins the repo to old
versions indefinitely, because nobody records *why* it was held or *what
would make it safe to move*. Meanwhile the ecosystem evolves underneath
the pin: spaCy ships 4.0, FastAPI floats its starlette cap, numba lifts
its numpy ceiling. The held cluster becomes safe to take **as a wave** —
but no one notices, and the repo quietly rots on stale, eventually
CVE-bearing versions.

So Cassandra models a held bump not as a tombstone but as a
**`(reason, release-predicate)`** obligation:

- **reason** — the live constraint that blocks it *now* (`spaCy 3.8 pins
  thinc<8.4`), not merely "we ignored it."
- **release-predicate** — the machine-checkable condition that would lift
  the hold (`spaCy 4 reaches GA and the cluster co-resolves`). This is
  the un-gating condition the 🟡 surface already names, promoted to a
  first-class field on *every* hold.
- **cluster** — what it must move with, so the eventual upgrade is atomic
  ("the wave," not four uncoordinated PRs that each half-break).

These live in the **Held register** at the top of the ledger, and
`/cassandra --watch` (Mode C) re-evaluates each predicate against *fresh*
ecosystem metadata — deps.dev `GetRequirements` (has the upstream cap
floated?), `GetVersion` (age, deprecation, OpenSSF scorecard), OSV
advisories — and reports **still held / wave forming / ready**. The day a
predicate is met for every cluster member, the row graduates into a fresh
Mode-A pre-mortem of *that* atomic move. Un-holding is **emergent**, not a
chore the maintainer has to remember.

### Prior art (what we stole, what we didn't)

This lifecycle idea is not novel in isolation — it's the
[Renovate `constraintsFiltering`] insight (*a good hold is derived from
live metadata each run, not stored as a dead pin*) plus the
[Renovate Dependency Dashboard] model (*one persistent artefact that
tracks every held item, why it's held, and what un-holds it*). The
"wait for the ecosystem to converge before moving" instinct is
[Renovate Merge Confidence] (age + adoption + CI-pass-rate), which we
**deliberately do not replicate**: it's cross-fleet telemetry we can't
reproduce, so the `--watch` pass reconstructs only the cheap, public
slice of it — age and deprecation from [deps.dev], advisories from
[OSV] — and leaves the adoption-velocity signal (per-version download
stats, dependent-graph growth) as a noted future extension, not a v1
dependency.

What stays bespoke is the combination no published tool offers: a
**calibrated pre-mortem** (every prophecy scored against outcome in a
public ledger) over **constraint-derived coupling clusters** moved
**atomically as a wave**. The closest community analogue, the
[thoughtbot dependabot-review-skill], does a clean per-PR
diff→changelog→grep→verdict but is stateless: no held register, no
clusters, no calibration. We borrow its instinct (read the codebase to
see whether a scary major touches a surface we actually call) and leave
the rest.

[Renovate `constraintsFiltering`]: https://docs.renovatebot.com/configuration-options/#constraintsfiltering
[Renovate Dependency Dashboard]: https://docs.renovatebot.com/key-concepts/dashboard/
[Renovate Merge Confidence]: https://docs.renovatebot.com/merge-confidence/
[deps.dev]: https://docs.deps.dev/api/v3/
[OSV]: https://osv.dev
[thoughtbot dependabot-review-skill]: https://thoughtbot.com/blog/reviewing-dependabot-prs-is-boring-let-claude-do-it-for-you

## The coupling-cluster catalog

Most breakage is *cluster* breakage. The agent starts from this map
(and confirms each against installed metadata, because versions move):

| Cluster | Members | The trap |
|---------|---------|----------|
| **spaCy ecosystem** | spacy, thinc, weasel, confection, srsly, preshed, cymem, murmurhash, blis, wasabi | spaCy 3.8 pins `thinc<8.4`, `weasel<0.5`; the 1.x/9.x generation is spaCy-4-era. Any lone thinc/weasel/confection bump is a guaranteed resolver-red. Drags the **Presidio PII path**. |
| **numpy ABI** | numpy, numba, llvmlite (+ scipy, ctranslate2, mlx) | numba pins a tight `numpy<2.X` cap and lags new numpy. numpy-first is the classic *silent* break — numba throws at import. Move atomically. |
| **LLM SDKs** | anthropic, openai, google-genai | Scary major gaps, but breaks usually live in *unused beta surfaces*. Verify against `bristlenose/llm/client.py`'s actual calls before crying doom. |
| **FastAPI / starlette** | fastapi, starlette | FastAPI's metadata caps starlette; bumping starlette alone is a resolver-non-event until FastAPI floats the cap. |
| **HF transformer stack** | torch, transformers, tokenizers, huggingface_hub | tokenizers↔transformers mismatch is the classic ImportError. Move the set together. |
| **Node-gated frontend/e2e** | vite, vitest, jsdom, eslint family, typescript / lighthouse, @playwright/test | Move with the **Node major** (`.tool-versions`). A tool whose `engines` outruns CI's Node is a red install (or a silent warning if `engine-strict` is unset). Confirm CI Node from `.tool-versions`, not a register line that may be stale. |

When the agent finds a coupling not on this list, it names it as a new
cluster and recommends adding it here — it doesn't smuggle it in.

## The calibration loop

```
   Dependabot batch lands  ┐
   quarterly review fires  ├──►  /cassandra  ──►  prophecy + receipts
   "is it safe to bump X?" ┘                          │
                                                       ▼
                                       record to ledger (OUTCOME: open)
                                                       │
                              human triages: merge / group / ignore / hold
                                                       │
                                            (bumps applied, CI runs)
                                                       │
                                                       ▼
                       /cassandra --score  ──►  read open entry, observe reality,
                                                 score each verdict (hit / miss /
                                                 false-alarm), write the lesson,
                                                 update the running tally
                                                       │
                                                       ▼
                              next prophecy reads the ledger and is calibrated
```

The loop only closes if step 4 (record) happens *before* the report is
shown, and the `--score` pass happens *after* the bumps land. The skill
enforces the first ("every prophecy is logged before it's shown"); the
human (or a follow-up session) triggers the second.

There is a **second, slower loop** running alongside the prophecy/score
cycle: the **watch loop**. A 🔴/🟡 that the human chooses to hold doesn't
leave the system — it becomes a `(reason, release-predicate)` row in the
Held register, and `/cassandra --watch` re-evaluates that predicate
against the evolving ecosystem on each pass. Where the calibration loop
asks *"was the prophecy right?"*, the watch loop asks *"is the hold still
necessary?"* — and graduates a held cluster into a fresh prophecy the day
the ecosystem makes it safe to move. Both loops are on-demand, human-
triggered at the moment of dep-review; neither is an ambient cron (see
§ Why a skill, not a CI bot).

### Scoring vocabulary

- **hit** — predicted break and it broke, or predicted safe and it held.
- **miss** — predicted safe, it broke. The *costly* error: a silent
  runtime break sailed through because the prophecy under-called it.
  Tightens the relevant cluster heuristic.
- **false-alarm** — predicted break, it held. The *curse-inducing*
  error: over-flagging that, repeated, makes the oracle ignorable.
  Loosens the heuristic.
- **untested** — the bump wasn't applied, so the prophecy stands open.
  **This is the default, and it is load-bearing.** A `hit` costs proof
  (a CI run, a lockfile diff showing the bump landed, a test result); a
  SAFE prophecy that was never applied is *untested, never a free hit*.
  Letting untested decay into hit silently inflates the tally — and the
  tally is the one number the whole ledger exists to keep honest, so the
  evidence barrier is not bureaucracy, it's the integrity of the curse-
  lifting mechanism. ❔ UNKNOWN verdicts are unscoreable by construction
  (no prediction was made) and stay `untested` until the bump is tried.

Both error kinds tune the agent; false-alarms get special weight,
because they're the mechanism by which a true prophet stops being
believed.

## Why a skill, not a CI bot

The obvious alternative is a bot that comments a risk score on every
Dependabot PR automatically. We deliberately didn't build that.

The constraint here is **bandwidth, not visibility.** A solo maintainer
with a day job doesn't lack *awareness* that dep PRs exist — Dependabot
already emails. What's scarce is the *time* to triage them well. An
ambient bot that scores every PR adds to the signal stream the
maintainer must process; it makes the problem it's solving slightly
worse on every single PR, in exchange for a number nobody asked for at
that moment.

A skill inverts this. It's a *one-shot, on-demand* pre-mortem fired at
the moment of decision — when a batch has accumulated and the human sits
down to clear it. It collapses N PRs into one ranked report with a clear
"act here first / these are non-events / this wave is safe" shape. It
reduces triage time instead of adding to the stream. The trigger is a
human (or Claude) at review time, deliberately.

This mirrors the project's standing preference: prefer mechanisms that
*reduce per-incident time-cost* over mechanisms that *increase the
ambient signal stream.* The ledger is the long-memory; the skill is the
bandwidth-shaped interface to it.

## Open questions

- **Ledger location.** *(Resolved — stays public.)* The ledger lives in
  public `docs/` so contributors can see the calibration accrue. Risk:
  a future entry accreting strategic context (pinning *strategy*, vendor
  reasoning) that shouldn't be public. This is mechanically mitigated —
  the repo's `leak-scan.sh` PreToolUse hook blocks Writes to public docs
  containing private patterns — so the guard is automatic, not vigilance.
  It stays pure engineering history (versions, pins, outcomes); if that
  ever stops being true, the hook fires before it lands.
- **Adoption-velocity signal (deferred).** The `--watch` pass
  reconstructs only the cheap half of Renovate's Merge Confidence — age +
  deprecation (deps.dev) + advisories (OSV). The richer "has the wave
  *actually* formed?" signal — per-version download velocity (PyPI
  Linehaul / npm last-week), dependent-graph growth (deps.dev BigQuery) —
  is deliberately left for v2: it needs BigQuery access (real infra) and
  the held register has too few rows to justify it yet. Revisit once
  `--watch` has graduated a couple of waves and we know whether age +
  advisories alone call the move well enough.
- **Cross-tool overlap with `/usual-suspects`.** Both are
  fan-out-then-synthesise review mechanisms that log to a record.
  `/usual-suspects` reviews *code changes* and logs to the gitignored
  private reviews area; `/cassandra` reviews *dependency changes* and
  logs to the public ledger. They don't overlap today, but if a future
  dependency change warrants a code-style review (e.g. a bump that
  forces an API migration), the two could chain. Left unbuilt until a
  real case appears.
- **Auto-`--score` trigger.** Today the score pass is human-triggered
  after bumps land. A future refinement: have `/end-session` or a merge
  hook notice that a prophesied bump was applied and prompt for the
  score pass, so the loop can't silently stay open. Not built — would
  add ambient signal, which cuts against the bandwidth principle above.
  Revisit only if open entries actually accumulate unscored.
- **Batch parallelism threshold.** The skill fans gossip research across
  parallel sub-agents by cluster for "large" batches (≥ ~6 risky bumps).
  The threshold is a guess; tune it once the ledger has a few entries
  showing where synthesis quality drops off.

## See also

- `.claude/agents/cassandra.md` — the agent (method + coupling map).
- `.claude/skills/cassandra/SKILL.md` — the skill (calling mechanism +
  ledger ownership, Mode A prophesy / Mode B score).
- `docs/dependency-premortem-log.md` — the ledger (prophecies + outcomes).
- `docs/design-platform-policy.md` — the pinning register and
  tooling-sprint cadence that triggers a pre-mortem.
- `.github/dependabot.yml` — the ignore rules Cassandra reads and the
  human edits.
