---
name: cassandra
description: Pre-mortem a dependency-bump set before merging — predict what breaks, prove how, and record the prophecy for later calibration
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, Agent, WebSearch, WebFetch, Write, Edit
---

Run a **dependency-bump pre-mortem**: before applying a batch of
Dependabot PRs or a quarterly dependency wave, predict the blast radius
of each bump, write the prophecy to the calibration ledger, and present
a ranked report the user triages. Later, after the bumps are applied,
re-run in `--score` mode to record what actually happened and tune the
oracle.

This skill is the **calling mechanism** for the `cassandra` agent. The
agent holds the method and the coupling map; the skill gathers the
candidate set, runs the agent, and owns the ledger.

## When to invoke

- A batch of Dependabot PRs has landed and you're deciding what to merge.
- The quarterly tooling-sprint review (`docs/design-platform-policy.md`)
  is firing.
- Before any coordinated dependency wave ("move as a wave, not a phone
  call").
- Ad hoc: "is it safe to bump X?"
- `--score`: a previously-prophesied bump set has been applied; record
  outcomes and score the prediction.
- `--watch`: re-examine the Held register — re-evaluate each held bump's
  release-predicate against fresh ecosystem metadata, and surface any
  coupling cluster that has become safe to take "as a wave."

This is a **local, on-demand** skill, not a CI bot. The trigger is a
human (or Claude) at review time — deliberately, to keep this a
bandwidth-reducing one-shot, not an ambient signal stream on every PR.
See `docs/design-dependency-premortem.md` § Why a skill, not a CI bot.

## Mode A: prophesy (default)

### Step 1 — gather the candidate set

If the user named a specific set ("bump anthropic and openai"), use that.
Otherwise discover it:

```bash
# Python — outdated + the open Dependabot PRs
.venv/bin/pip list --outdated 2>/dev/null
gh pr list --label dependencies --state open --json number,title 2>/dev/null

# Frontend + e2e
( cd frontend && npm outdated ) 2>/dev/null
( cd e2e && npm outdated ) 2>/dev/null
```

`outdated` is **reconnaissance, not the candidate set** — it over-reports
(headline gaps ignore pins). Note that the agent will re-ground against
installed metadata; don't pre-filter here, just collect.

> **Guard: an empty result is a tool failure, not an all-clear.** Every
> command above ends in `2>/dev/null`, so a wrong venv path (`.venv/bin/pip`
> doesn't exist in this worktree — common; some worktrees and cloud envs
> have no `.venv`), an unauthenticated `gh`, or an `npm` error each yields
> *silent emptiness* that looks identical to "nothing to bump." **Before
> running Cassandra, confirm the tools actually ran:** check `.venv/bin/pip`
> exists (else find the right interpreter), `gh auth status` is clean, and
> at least one source returned rows. If discovery comes back wholly empty,
> **stop and report "couldn't enumerate candidates" — do not hand Cassandra
> an empty set and present her clean report as an all-clear.** A pre-mortem
> over nothing is the silent failure this whole subsystem exists to prevent.

### Step 2 — read the register, the ignore list, and the ledger

Read before prophesying so the agent is calibrated:
- `docs/design-platform-policy.md` — the pinning register (what's held,
  why, re-check dates).
- `.github/dependabot.yml` — the ignore rules.
- `docs/dependency-premortem-log.md` — the prophecy ledger (past
  predictions + outcomes). If absent, this is the first prophecy; note
  it.

### Step 3 — run Cassandra

Spawn the `cassandra` agent via `Agent` with `subagent_type: "cassandra"`.
Pass it: the candidate set, the venv path, and the three files from
Step 2 (or their salient contents).

**For a large batch (≥ ~6 risky bumps),** have Cassandra fan the gossip
research out across **parallel sub-agents by cluster** (spaCy ecosystem,
numpy ABI, LLM SDKs, web stack, HF stack, Node-gated tooling) — one
`general-purpose` agent per cluster, launched in a single message — then
synthesise. This is the pattern that produced the inaugural ledger
entry; it keeps each research thread focused and the main context clean.

### Step 4 — record the prophecy

**Before** showing the report, append a new entry to
`docs/dependency-premortem-log.md` (create it from the schema below if
absent). The entry captures every verdict with its receipt and an
**OUTCOME: open** block to be filled in `--score` mode. Number entries
sequentially; never renumber.

### Step 5 — present the ranked pre-mortem

Show Cassandra's report: the blast-radius ranking table, the guaranteed
breakages first, the non-events, the safe wave, and the recommendations.
End with the triage prompt — the user decides what to merge, group,
ignore, or hold. Apply any dependabot.yml / register changes the user
approves in the same turn.

## Mode B: score (`/cassandra --score [entry N]`)

A previously-prophesied bump set has been applied (merged, or applied
locally and tested). Close the loop:

1. **Read the open ledger entry** (the latest, or entry N if named).
2. **Establish what actually happened** for each prophesied bump:
   - Was it applied? (check `git log`, the lockfile diff, the merged PR.)
   - Did CI go red? (`gh run list`, the PR checks.)
   - Did it break at runtime? (test failures, the user's report.)
3. **Score each verdict**: **hit** / **miss** (predicted safe → broke,
   the costly error) / **false-alarm** (predicted break → held, the
   curse-inducing error) / **untested** (bump not yet applied).
   **Evidence barrier — a hit costs proof.** `untested` is the *default*;
   a verdict only earns `hit`/`miss`/`false-alarm` once you can point to
   what actually happened (a CI run, a lockfile diff showing the bump
   landed, a passing/failing test, the user's report). A SAFE prophecy
   that was never applied is **untested, never a free hit** — letting
   untested decay into hit silently inflates the tally and corrupts the
   one number the whole ledger exists to keep honest. ❔ UNKNOWN verdicts
   are unscoreable by construction (there was no prediction to test) —
   record them `untested` until the bump is actually attempted.
4. **Write the OUTCOME + SCORE** into the ledger entry, with evidence
   (the CI run, the error, the commit). No evidence → the score stays
   `untested`.
5. **Extract the lesson.** If a cluster was mis-called, state the tuning
   the agent should apply next time, and — if the heuristic itself was
   wrong — propose the edit to `.claude/agents/cassandra.md` or the
   coupling catalog in `docs/design-dependency-premortem.md`.
6. **Update the running tally** in the ledger header (N prophecies, M
   hits, K misses, J false-alarms).

The score pass is where the curse lifts: accuracy accrues in public, and
the agent's own past errors become its next prophecy's calibration.

## Mode C: watch (`/cassandra --watch`)

Re-examine the **Held register** — the standing list of bumps held with a
reason and a release-predicate (see schema below). This is what turns an
ignore from a tombstone into a deferred obligation: instead of pinning to
an old version forever, each hold is re-evaluated against the *evolving*
ecosystem until the day a coupling cluster becomes safe to take as a wave.

1. **Read the Held register** in `docs/dependency-premortem-log.md`.
2. **For each held row, re-evaluate its release-predicate against fresh
   metadata** — *not* the installed venv (still on the old pins by
   definition). Cassandra grounds the watch against:
   - **deps.dev v3** (`https://api.deps.dev/v3/...`) — `GetVersion` for
     `publishedAt` / deprecation / OpenSSF scorecard, `GetRequirements`
     for the *unresolved* upstream caps (has the `spaCy pins thinc<8.4`
     edge floated yet?). Plain JSON, `WebFetch`-able.
   - **OSV** (`https://api.osv.dev/v1/query`) — advisories that force or
     forbid a move.
   - the target's own changelog for the predicate's specific condition.
3. **Classify each row**: **still held** (predicate unmet — restate the
   reason, stamp the date checked), **wave forming** (partly met — name
   what's still missing, e.g. "spaCy 4 GA'd but `en_core_web_lg` hasn't
   re-published"), or **ready — move as a wave** (met for every cluster
   member).
4. **For any "ready" cluster, run a fresh Mode-A pre-mortem of that
   atomic move** (it's a new bump set now) and record it as a new ledger
   entry. The hold graduates: drop the dependabot.yml ignore, take the
   wave.
5. **Update the Held register** with the new status + date checked. A row
   never silently rots — every watch pass leaves a dated breadcrumb.

On-demand only. The watch pass is run when the human sits down to clear
deps, never on a cron — an ambient drift-checker would add to the signal
stream the maintainer must process, which is exactly the bandwidth cost
this subsystem is shaped to avoid (`docs/design-dependency-premortem.md`
§ Why a skill, not a CI bot).

## The ledger schema

`docs/dependency-premortem-log.md`:

```markdown
# Dependency pre-mortem ledger

Cassandra's prophecies and their outcomes. One entry per pre-mortem pass.
Append-only; never renumber. The running tally lets us see, over time,
how well the oracle calls it.

**Tally:** <N> prophecies scored — <M> hits, <K> misses, <J> false-alarms.

## Held register

<!-- The standing watch list. Each held bump is a (reason, release-predicate)
     obligation, re-examined by /cassandra --watch — never a bare pin. -->

| Held bump | Cluster | Reason (blocks now) | Release-predicate (lifts it) | Last watched | Status |
|-----------|---------|---------------------|------------------------------|--------------|--------|
| …         | …       | …                   | …                            | <date>       | held / wave-forming / ready |

---

## Entry <N> — <date> — <candidate set / version line>

- **Grounded against:** <venv> installed metadata + register + ignore list
- **Prior calibration applied:** <which past lessons fed this prophecy>

### Prophecy

| Bump (from→to) | Verdict | Surface | Receipt |
|----------------|---------|---------|---------|
| …              | 🔴/🟡/🟢/❔/⚠️ | resolver/runtime/— | <pin / issue / changelog> |

<!-- Verdict legend: 🔴 WILL-BREAK · 🟡 RESOLVER-NON-EVENT · 🟢 SAFE ·
     ❔ UNKNOWN (couldn't look — not a soft SAFE) · ⚠️ LATENT (orthogonal). -->

### OUTCOME — open
<!-- filled in by /cassandra --score after the bumps are applied -->

### SCORE — pending
<!-- hit / miss / false-alarm / untested per verdict, with evidence and the
     lesson. untested is the default; a hit costs proof (CI run, lockfile
     diff, test result). A SAFE never applied is untested, never a hit. -->
```

## Rules

- **Ground truth beats headline.** The skill collects `outdated`; the
  agent re-grounds against installed metadata. Never present the
  `outdated` table as the prophecy.
- **Every prophecy is logged before it's shown.** A pre-mortem nobody
  can later score is a pre-mortem that can't improve. Step 4 is not
  optional.
- **A confident SAFE is a deliverable.** Don't let the report become an
  amber smear. The contrast — reds in a field of greens — is the value.
- **Never apply a bump.** This skill predicts and records. Merging /
  applying is a separate human decision; `--score` observes the result.
  `Write`/`Edit` are in `allowed-tools` for **one purpose only — writing
  the ledger** (`docs/dependency-premortem-log.md`). Never edit
  `dependabot.yml`, `pyproject.toml`, a lockfile, or any dependency file;
  proposing those edits is the report's job, applying them is the human's.
- **Couldn't look ≠ safe.** An empty candidate set, an unreadable pin
  (`PackageNotFoundError`), or failed gossip is ❔ UNKNOWN — never folded
  into the greens. The skill's Step 1 guard enforces this at the input
  boundary; the agent enforces it per-verdict.
- **A hold carries its release-predicate.** When the report recommends
  ignoring a 🔴/🟡, it records a `(reason, release-predicate, cluster)`
  row in the Held register, not a bare pin. `--watch` is what later
  collects on that obligation.
- **The ledger is engineering history, not strategy.** It lives in
  public `docs/` so contributors can see the calibration. Nothing
  sensitive goes in it.
