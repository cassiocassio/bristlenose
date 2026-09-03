---
name: usual-suspects
description: Fan out all relevant review agents in parallel against a plan or implementation, then consolidate into a single triageable report
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, Agent, TodoWrite
---

Run all relevant review agents in parallel against the current work (plan or
implementation), then consolidate their findings into a single triageable list.

The user decides what to act on, park for later, or ignore. Your job is to
present clear findings, not to gatekeep.

## Step 1: Detect mode, scope, doc, and slice

Determine whether this is a **plan review** or an **implementation review**:

**Plan review** — if any of these are true:
- A plan file exists at the path the user provides or references
- The conversation is in plan mode or just exited plan mode
- The user says "review the plan" or similar
- A `docs/design-*.md` file was recently created/modified

**Implementation review** — if any of these are true:
- The user says "review what we did" or similar
- There are uncommitted changes or recent commits to review
- The user provides a git range

Determine scope:
- For plans: the plan file + any design docs it references
- For implementation: `git diff --stat` (staged + unstaged) or a git range

If ambiguous, ask: "Plan or implementation? And what's the scope?"

**Determine the design doc and slice** (the two dimensions of continuity):

The **doc** identifies the review log file. The **slice** is a tag inside it.

Doc slug — autodetected, in order:
1. If the user passed `--doc <slug>`, use that.
2. Nearest `docs/design-*.md` referenced in the conversation or recently
   modified — derive the slug by stripping `design-` and `.md`
   (e.g. `docs/design-cost-forecast-phase1.md` → `cost-forecast-phase1`).
3. None — proceed without a continuity log; note this in the output.

Slice tag — autodetected, in order:
1. If the user passed `--slice <name>`, use that (e.g. `--slice "Slice 2"`).
2. Conversation cue (the user said "review Slice 2 implementation"). Accept
   any user-chosen tag — number, letter, roman numeral, name. The skill does
   not parse or order it; it's free text shown in the **Pass:** line.
3. Default: ask the user `What slice + pass type? (e.g. "Slice 2 impl-review")`.

The **review log** lives at `docs/private/reviews/<doc-slug>.md` (gitignored
— strategic context stays local). Auto-create the directory if it does not
exist. **One log per design doc**; every pass across every slice appends to
the same file.

**No design doc and no `--doc` slug?** Do not silently skip the log — that's
a quiet-failure mode where findings accumulate nowhere. Prompt the user once:

> No design doc detected. Pick one:
>   1. Pass `--doc <slug>` — log goes to `docs/private/reviews/<slug>.md`.
>      Use this for sliced work without a design doc (e.g.
>      `react-migration-step-11`).
>   2. One-off review — no log. Confirm and I'll proceed.

Default to (2) on no response after one prompt. Record the choice in the
final report header so future passes know whether a missing log is by-design
or an oversight.

### Boundary with handoff docs

Handoff docs (e.g. `docs/private/<slice>-handoff.md`) describe **intent for
the next slice** — what the next session should read first, what's in scope,
working agreements. The review log captures **findings raised by review
agents and their disposition**. Boundary rule:

- "Agents found it" → review log.
- "Human decided it" (scope, sequencing, working agreements) → handoff doc.

When a handoff doc would otherwise repeat a "Decisions taken — don't
relitigate" block, replace it with a one-line link to the review log
(e.g. `See parked findings 3–7 in docs/private/reviews/<slug>.md`). One
canonical home per piece of information.

## Step 2: Select agents

Check which areas are touched (file extensions, directory prefixes, content):

| Condition | Agent |
|-----------|-------|
| Always | `code-review` |
| `.ts`/`.tsx`/`.css` files, or UI/frontend mentioned | `ux-critique` |
| `bristlenose/locales/`, `t()` calls, i18n mentioned | `i18n-review` |
| Security-sensitive (auth, tokens, PII, file access, bridge) | `security-review` |
| HTML/React components with interactive elements | `a11y-review` |
| `desktop/`, `.swift` files, macOS/HIG mentioned | `what-would-gruber-say` |
| `.ts`/`.tsx`/`.css`, `package.json`, server, pipeline, perf-sensitive, or `.swift` (concurrency/cancellation) | `perf-review` |
| Test files touched, new public API without tests, or any `.swift` change | `what-would-james-bach-say` (see three-way selector below) |
| try/except or catch blocks, fallback logic, subprocess/shellouts, JSON serialization, or E2E/Playwright specs touched | `silent-failure-hunter` |
| `.github/workflows/**` or other CI/release config touched | `security-review` + `silent-failure-hunter` (**CI workflow lens** — see below) |
| New file, core data path, or >150 changed lines — and on `--fresh-eyes` | **fresh-eyes lane** (see below) |

**`code-review` always runs.** The others run only if their area is touched.

### The fresh-eyes lane — deliberately context-free

Not a named agent. Spawn a `general-purpose` agent and **instruct it to read
nothing but the code under review** — no `CLAUDE.md`, no `MEMORY.md`, no design
docs, no `.claude/` skills. Ask for the same finding schema as everyone else.

This looks like the obvious lane to cut and it is not. The project-context
agents know the codebase's conventions, and knowing a convention is what stops
you questioning it. A reviewer with no context has nothing to defer to, so it
asks whether a call is safe at all rather than whether it matches house style —
which is how it reaches platform-level hazards the informed lanes read straight
past.

Its cost profile is the worst of the three (most tokens per unique finding), so
gate it on substantial changes rather than running it always. But when it runs,
**protect its uniques in adjudication** — a finding no other lane produced is
not a weaker finding, and 4.6c's precondition constraint exists partly for it.

**The three lanes are a partition, not a vote.** Repo-context lanes
(`code-review` and friends) own contracts, policies, conventions and
sibling-file consistency. Specialist lanes (`what-would-gruber-say`,
`perf-review`, with the vendored skills) own craft depth. The fresh-eyes lane
owns platform reality. They find different *classes* of defect; expect the
overlap between them to be well under half.

### James Bach three-way selector

The Bach reviewer (`what-would-james-bach-say`) is testing-taste-specific.
Run a finer decision than the binary table above:

**Auto-call Bach when ANY of:**
- Diff touches `*test*`, `*Tests.swift`, `tests/`, `e2e/`, or `frontend/src/**/*.test.{ts,tsx}`
- Diff adds a new module, public API, or new file under `bristlenose/`,
  `frontend/src/`, or `desktop/Bristlenose/Bristlenose/` **without**
  corresponding test changes
- Plan-review mode where the plan mentions testing
- Any `.swift` change (Swift is the under-served layer per
  `docs/design-test-philosophy.md` — Bach has the most to say there)

**Skip Bach silently when ALL of:**
- Pure doc edits (`docs/**/*.md`, `README.md`, `CHANGELOG.md`)
- Config / dependency bumps with no code changes
- Comment-only or copy-only changes
- Locale-only changes (i18n-review handles these)

**Prompt the user when:**
- Refactor with no test changes — could be "didn't need tests" or "should
  have updated tests"; user knows which
- Cross-cutting diff that touches many surfaces; Bach's value depends on
  which surface dominates
- Another agent has already raised a test-shaped concern that Bach would
  amplify (avoid double-billing)

Prompt format: one-liner — *"Bach selector is grey: <one-sentence reason>.
Call Bach? (y/n)"* — keep it tight, don't break flow.

### CI workflow lens

CI config rarely changes but is high-blast-radius, and the project's CI has a
documented fragility history (`docs/design-ci.md` § Fragility classes). When a
diff touches `.github/workflows/**` (or release/CI config), this lens ensures
the two reviewers who own those failure modes both fire, and points them at the
charter's invariants:

- **`security-review`** — the supply-chain + least-privilege invariants: every
  third-party action SHA-pinned, every workflow carries a `permissions:` block
  scoped to the minimum, no secret widened in reach. Ref: `docs/design-ci.md`
  § Least privilege and supply-chain pinning.
- **`silent-failure-hunter`** — the false-green invariants: no new
  `continue-on-error` swallowing a real failure, non-`success` conclusions
  still treated as non-green, no bounded step that fails open. Ref:
  `docs/design-ci.md` § Standing audit targets.
- **`what-would-james-bach-say`** — add only if the change alters *what gets
  tested* (matrix cells, test invocation, markers), not just infra plumbing.

This is a routing lens over existing reviewers, **not a new agent**. There is
deliberately **no standalone CI-audit mode**: the Rule of Three isn't met (one
steward use-case, not three), so the lens runs only as part of a normal
`/usual-suspects` pass on a diff that touches CI.

**Sunset.** Remove this lens row when either holds: (a) the invariants are
enforced mechanically in CI (an actionlint / pinned-SHA / permissions-check
job — at which point human review is redundant), or (b) a post-TestFlight retro
confirms two consecutive quarters with no new fragility-class incident and no
unreviewed workflow regression. Re-evaluate at the first post-TF retro; don't
let this lens ossify unexamined.

Announce which agents you're launching and why:
```
Calling the usual suspects:
- code-review (always)
- ux-critique (frontend components changed)
- i18n-review (locale files touched)
- what-would-james-bach-say (Swift change + no test updates)
Skipping: security-review, a11y-review, what-would-gruber-say (not in scope)
```

## Step 2.5: Read prior review log (if a doc slug was determined)

If `docs/private/reviews/<doc-slug>.md` exists, read it whole before launching
agents. This is the memory of every finding raised across every prior pass —
both earlier slices and earlier passes within the current slice.

Pass the file's contents to **every** agent you launch (Step 3) inside a
`## Prior findings (do not relitigate)` block, along with the current slice +
pass tag (e.g. "Current pass: Slice 2 impl-review"). Instruct each agent to
tag every finding it returns with **exactly one** of these four bracket tags
(quote them verbatim — do not paraphrase):

> - `[NEW]` — not in the prior log.
> - `[SAME-SLICE]` — already flagged in this slice's earlier pass; cite prior
>   Finding N. Do not re-raise unless evidence changed.
> - `[PARK→OPEN]` — finding parked in a prior slice, now relevant because the
>   parking condition changed; cite Finding N and explain what changed.
> - `[REGRESSION]` — finding marked `resolved` in a prior slice has reappeared;
>   cite Finding N, the resolution commit, and the regressing change.
>
> Do not re-raise `parked` findings unless the parking condition actually
> changed. Do not re-raise `resolved` findings unless you can show the
> resolution was reverted or undermined. Do not re-raise findings whose status
> is `ignored` — those were explicitly dismissed.

If the file does not exist, proceed without prior context — note this in the
final output (`First pass for this doc — no prior log.`).

## Step 3: Launch agents in parallel

Spawn all selected agents **simultaneously** in a single message with multiple
Agent tool calls. Each agent gets the same scope description:

For **plan review**, tell each agent:
```
Review this plan: <path to plan file or design doc>
Mode: plan review
Scope: <list of files/areas the plan affects>
```

For **implementation review**, tell each agent:
```
Review these changes: <git range or "staged + unstaged changes">
Mode: implementation review
Scope: <list of changed files from git diff --stat>
```

### SwiftUI knowledge source (not a peer agent)

When `.swift` files or `desktop/` are in scope, the SwiftUI-aware agents
(`what-would-gruber-say`, `code-review`, `what-would-james-bach-say`) get an
extra line telling them to consult the vendored **swiftui-pro** skill:

```
For generic SwiftUI craft (deprecated API, view composition, data flow,
navigation, performance, hygiene), read the relevant reference files under
.claude/skills/swiftui-pro/references/*.md before flagging. It is iOS-first:
project hard rules (MEMORY.md / CLAUDE.md) and macOS idiom win on any conflict.

For concurrency specifically (actors, task groups, cancellation, Sendable,
bridging, async tests), read .claude/skills/swift-concurrency-pro/references/*.md
instead — the specialist source, platform-neutral. Start at hotspots.md.
```

**Mac taste has its own source.** `mac-arsed-mac-app` (vendored, MIT, Bart
Reardon) is the judgement layer for Mac craft — menus, keyboard, windows,
selection, drag and drop. `what-would-gruber-say` reads it directly. Its
`reference/swiftui-appkit.md` is the first stop for any selection/focus/sidebar
finding. It does **not** satisfy the HIG citation rule — the corpus at
`~/.local/share/hig-corpus/` remains the citable authority for what Apple says.

**Two skills, one rule.** `swift-concurrency-pro` (also vendored, also Paul
Hudson) is the concurrency specialist and **outranks swiftui-pro on concurrency
questions**. They genuinely disagree in one place: swiftui-pro says *never* use
GCD; swift-concurrency-pro allows it in low-level, interop, and perf-critical
synchronous code and says not to flag it. There are ~16 GCD call sites in the
shipping Swift source — an agent applying swiftui-pro alone would flag them all.
Take the specialist's line.

`swiftui-pro` is a **knowledge source, not a reviewer persona** — it does not
fan out as its own agent and does not appear in the agent-selection table. It
informs the agents that already run. (Review subagents can't invoke skills, so
they `Read` the reference files directly — that's why this is a per-agent
instruction, not a Skill call.) It also auto-triggers in the main conversation
when authoring SwiftUI. See `.claude/skills/swiftui-pro/VENDORED.md`.

**Adjudication.** swiftui-pro is *evidence*, not a *vote*. If a finding cites a
swiftui-pro reference and an agent's hunch disagrees on a pure SwiftUI fact
(deprecated API, property-wrapper choice), trust swiftui-pro. If swiftui-pro's
iOS-flavoured advice collides with a Mac-platform concern or a documented
project decision, the project/Mac side wins. **William does not adjudicate
SwiftUI correctness** — his Step 4.6 pass is scope/proportion only. A
swiftui-pro-backed finding that is real but over-engineered still gets William's
"real problem, smaller fix" treatment like any other.

## Step 4: Consolidate

Once all agents return, produce a **single consolidated report**. This is the
hard part — don't just concatenate. Do this:

**Consolidation stays in the main loop, deliberately** — the accumulated
context (the diff, the greps, the coverage gaps, prior log entries) is the whole
reason it works. A subagent handed N findings has none of it and will produce a
tidy merged list with the interactions still buried in it.

1. **Deduplicate** — if two agents flag the same issue (e.g. code-review and
   ux-critique both notice a missing keyboard handler), merge into one finding
   and note which agents flagged it. **Record the agent count, and never use it
   as a filter.** Agreement is weak evidence a finding is real; disagreement is
   no evidence it isn't. Expect most findings to come from exactly one agent —
   that is the lanes working as designed, not noise. Dropping single-agent
   findings, or ranking by how many agents concurred, discards the tail, and
   the tail is where the cross-file and platform defects live.

2. **Resolve contradictions** — if agents disagree (e.g. security-review wants
   stricter validation, code-review questions whether it's needed), present
   both views honestly with the tradeoff. Don't pick a winner.

3. **Categorise** — group findings into:
   - **Bugs / Errors** — things that are broken or will break
   - **Convention violations** — deviations from documented project rules
   - **Performance** — regressions, bundle size, rendering, loading (from
     perf-review agent)
   - **Design questions** — tradeoffs and competing approaches (from all agents'
     Questions sections, deduplicated)
   - **Improvements** — things that work but could be better

4. **Tag each finding by kind** in addition to severity. Kinds:
   - `[technical]` — best-practice / correctness / perf / security. Some the
     user adjudicates; others want zoom-out (see rule below).
   - `[product]` — UX, naming, behaviour. User's call; agents propose, user
     disposes.
   - `[niggle]` — small, low-risk, mechanical. Often fixed inline on the same
     turn.
   - `[needs-zoom-out]` — answer is outside the codebase (Apple HIG, Mac indie
     norms, accessibility standards, academic methodology, etc.). Flag
     explicitly so the user can ask for prior-art research before triage,
     not after.

5. **Number everything** — each finding gets a number for easy reference when
   the user triages ("act on 1, 3, 7; park 4, 5; ignore 2, 6").

6. **Apply the merge rule for findings already in the log:**
   - Identical content, no human triage attached → silent dedup; status-update
     bullet on the existing Finding N noting "observed again in <pass>".
   - Different observations of the same issue → later wins. Quote the latest
     bullet when summarising current state, not the original detail block.
   - `parked` findings are advisory: re-surface as `[PARK→OPEN]` when code
     reality shows higher severity than the park decision had access to, OR
     when you suspect bandwidth-pressure triage. Frame as "you said X, here's
     what changed / what I now see — worth reconsidering?"
   - `ignored` is sacred — never re-raise.

## Step 4.5: Append to review log (if a doc slug was determined)

After consolidation but **before** showing the report to the user, append every
`[NEW]` finding from this pass to `docs/private/reviews/<doc-slug>.md`.
Continue numbering from the highest existing Finding N (never renumber).
New findings start at status `open`. For findings tagged `[SAME-SLICE]`,
`[REGRESSION]`, or `[PARK→OPEN]`, do not duplicate the entry — instead append
a status-update bullet under the existing Finding N capturing what this pass
observed. Do not write triage outcomes (`resolved`, `parked`, `ignored`)
yourself — those are the user's call, applied in Step 5.

If the file does not yet exist, create it with the header from the schema below.

## Step 4.6: Adjudication pipeline

Three stages, in this order, before the report reaches the user. **The order is
load-bearing.** William prunes; running him first compounds a bias that was
measured rather than theorised — see "Why this order" at the end.

### 4.6a — Reachability pass (main loop, no agent)

For every finding, establish three things and write them into the finding:

- **Live or latent?** Is the failing path reachable from a real call site
  *today*, or does it need a change nobody has made? Name the call site. A
  defect that becomes live the day someone edits a caller is real and
  non-urgent — say both.
- **Blast radius.** What does the *fix* touch? `grep` the symbols it would
  change. A one-line fix that alters a contract six files observe is not a
  one-line fix.
- **Guarded or not?** Does a test assert the behaviour the fix changes? A
  finding whose contract nothing pins is **riskier** to act on, not safer.

Re-rate severity here, and say so explicitly when you do — "raised from medium:
reachable from ContentView:1946, and no test pins the contract."

**Why this stage exists.** Reviewers systematically under-rate findings that
require cross-file knowledge: the finding that needs you to read a second file
to see the bug arrives with the lowest confidence and the smallest severity,
because from inside one file it looks conditional. Reachability is the only
stage that can push a severity **up**. Without it, every remaining stage pushes
down and the pipeline compounds in one direction.

### 4.6b — Compose-check (one agent, adversarial)

Spawn **one** agent over the *patch set*, not the finding list. Its only
question: **if all of these were applied, do they interact?**

It must return:
- **Ordering constraints** — "apply N before M, or M deletes data."
- **Pairs that must land together** — both rewrite the same construct.
- **Individually safe, jointly destructive pairs** — the whole reason for this
  stage.

This is not William's job and it is not optional. Two individually-correct
findings can combine into data loss, and that is invisible to every reviewer
that reviewed the *file*, because none of them reviewed the *diff*. If a
finding's fix relies on an invariant that another finding proves is broken,
this stage is the only place that gets caught.

Skip only when fewer than 3 findings propose code changes.

### 4.6c — William's parsimony pass

Run the annotated list through **what-would-william-of-ockham-say** in
adjudicator mode (Mode A). Spawn via `Agent` with `subagent_type:
"what-would-william-of-ockham-say"`, passing the consolidated report *plus*
the 4.6a reachability annotations.

William's job here:

1. **Pick the parsimonious fix** when several have been proposed for one
   problem, citing the heuristic (Rule of Three, simple-vs-easy, Hoare's test,
   Metz's wrong abstraction).
2. **Flag over-engineering** — real problem, fix three times bigger than it
   needs to be. This is his strongest output.
3. **Cluster duplicates** — agreement across agents is signal worth surfacing.
4. **Flag bikeshed crowding** — disproportionate weight on trivia while a hard
   finding goes under-discussed. He names *Parkinson's Law of Triviality* and
   points at what got crowded out.
5. **Filter** `real` / `edge` / `speculative` — **under one constraint below.**

**The constraint: to downgrade a finding, William must name the specific
precondition he believes will not occur.** "Speculative" as a bare verdict is
unfalsifiable and is not accepted. "This needs a non-APFS volume, which no
researcher will have" is a claim the user can check and reject. A finding
carrying a concrete failure scenario and a named call site from 4.6a cannot be
downgraded without engaging that scenario.

This constraint exists because the most valuable findings share a profile —
single-arm, cross-file, conditional — which is *also* what over-engineering
looks like from the outside. A conjunction of preconditions is exactly what a
razor cuts, and twice now the best finding in a review has had that shape.

**Scope limit.** William adjudicates *fix size and proportion*, not *finding
validity* for anything with a concrete reproduction. He does not adjudicate
SwiftUI or concurrency correctness — vendored-skill-backed findings are
evidence, not votes (see the adjudication note in Step 3).

**Skip William** when only one agent ran, the list has fewer than 3 findings,
or the user passed `--no-william`. Note the skip in the report header.

William is a signal, not a gate.

### Why this order

Consolidation and reachability stay in the **main loop** because accumulated
context is the point — the file, the ground truth, the blast-radius greps and
the coverage gaps all in one place. The two agent stages are agents precisely
because **independence** is the point: the compose-check wants fresh adversarial
eyes on the diff, and William is useful exactly because he is not invested in
the findings.

Show the user the final annotated list — one report, not four.

### Provenance — where these numbers came from

This pipeline's shape is not a hunch. It comes from a blind three-arm trial on
one 288-line Swift file, 3 Sep 2026, recorded at:

  https://claude.ai/code/artifact/cb6c0529-c4e2-4049-8b50-6d4fbcfebc5b   (maintainer's record; private)

Measured there: **20 distinct defects, 7 unanimous (35%), 11 found by exactly
one arm (55%), zero false positives across 36 findings.** Cost per unique
finding ranged 33k–69k tokens, cheapest being the arm that read the repo.

Three findings drive the design above, and a future round should build on them
rather than re-measure from scratch:

1. **Agreement is not a filter.** Ranking by concurrence would have discarded
   both of the best defects — each seen by one arm only.
2. **A razor alone compounds a measured bias.** Every arm under-rated findings
   needing cross-file knowledge, and the roster's other adjudicators also push
   down. Hence 4.6a, and hence 4.6c's precondition constraint.
3. **Nobody reviewed the diff.** Two individually-correct findings combined
   into a data-loss bug invisible to all three arms. Hence 4.6b.

**Caveat that matters: n=1.** The 35% and the zero-FP rate are the two figures
to re-check on a second run, and a diff-shaped review may distribute
differently. If a later trial contradicts them, change this pipeline and say so
here — do not quietly keep both stories.

## Step 5: Triage and update log

After showing the report, the user triages by finding number ("act on 1, 3,
7; park 4, 5; ignore 2, 6; supersede 8 by 11"). Apply the dispositions to
the log immediately, in the same turn:

- **act on N** + commit lands → status `resolved`, append bullet
  `<YYYY-MM-DD> **resolved** by <commit-sha> — <one-line note>`
- **park N because X** → status `parked`, append bullet
  `<YYYY-MM-DD> **parked** — <reason>`
- **ignore N** → status `ignored`, append bullet
  `<YYYY-MM-DD> **ignored** — <reason or "no reason given">`. Distinct from
  `parked`: ignored findings are exempt from `[PARK→OPEN]` resurrection.
- **supersede N by M** → status `superseded`, append bullet
  `<YYYY-MM-DD> **superseded** by Finding M — <why>`

If the user states dispositions clearly, apply them in the same turn; otherwise
prompt them once.

### Review-log schema

```markdown
# Review log — <doc-slug>

One log per design doc. All slices, all passes, append here.
Findings numbered sequentially across the whole doc; never renumber.
Status flags: `open`, `parked`, `ignored`, `resolved`, `superseded`.
(`ignored` is distinct from `parked` — exempt from `[PARK→OPEN]`.)

---

## Finding <N> — <one-line summary>

- **Pass:** <YYYY-MM-DD> <Slice tag> <plan-review|impl-review>
- **Agents:** code-review, security-review
- **Severity:** HIGH|MEDIUM|LOW|question
- **Where:** `path/to/file.py:123` (or "design doc §X")
- **Status:** open
- **Detail:** <2–4 sentences. The finding itself, plus enough context that
  a future pass understands what was claimed and why.>

  <!-- Status updates appended below as they happen — one bullet per event,
       chronological, including observations from later passes. -->

  - <YYYY-MM-DD> **resolved** by `<commit-sha>` — <one-line resolution note>
  - <YYYY-MM-DD> **parked** — <reason>
  - <YYYY-MM-DD> **carried to Slice N** — <why it must be enforced later>
  - <YYYY-MM-DD> **observed in <Slice tag> impl-review** — <still open / verified>
  - <YYYY-MM-DD> **superseded** by Finding <M> — <why>
```

The schema is intentionally markdown (not YAML/JSON) — humans skim this file
during slice transitions. Keep entries terse.

## Output format

```
# Review — [plan title or "recent changes"]

**Pass:** Slice 2 plan-review (or "Slice 2 impl-review", etc.)
**Doc:** <doc-slug> — `docs/private/reviews/<doc-slug>.md` (or "none — no continuity log")
**Scope:** <summary>
**Agents called:** code-review, ux-critique, i18n-review (3 of 8)
**Prior log:** N findings carried in (X open, Y parked, Z resolved) — or "first pass for this doc"

## Bugs / Errors
1. [HIGH][technical][NEW] `file:line` — description (flagged by: code-review)
   <!-- Each finding gets THREE tag groups:
        Severity:  [HIGH] | [MEDIUM] | [LOW] | [question]
        Kind:      [technical] | [product] | [niggle] | [needs-zoom-out]
        Continuity: [NEW] | [SAME-SLICE] (Finding 7) | [PARK→OPEN] (Finding 4
                    — what changed) | [REGRESSION] (Finding 12 — resolved by
                    abc123, broken by def456) -->
2. [MEDIUM] `file:line` — description (flagged by: code-review, a11y-review)

## Convention Violations
3. `file:line` — description. Ref: CLAUDE.md rule (flagged by: code-review)
4. `locale/key` — description (flagged by: i18n-review)

## Performance
5. [MEDIUM — bundle] `package.json` — description (flagged by: perf-review)

## Design Questions
6. Description of tradeoff. Two views: (a) ... (b) ...
   (raised by: code-review, ux-critique)
7. Description of tradeoff. (raised by: security-review)

## Improvements
8. `file:line` — suggestion (flagged by: ux-critique)

---
Your call — which to act on, park, or ignore?
```

## Rules

- **Don't editorialise.** Present findings, don't rank priorities or push an
  agenda. The user triages.
- **Don't inflate.** If agents found nothing interesting, say so. "Clean bill
  of health from 4 agents" is a valid outcome.
- **Preserve agent voice in design questions.** The Questions sections are the
  most valuable output — merge duplicates but keep the framing honest and
  balanced.
- **Keep it scannable.** One line per finding where possible. Details in
  sub-bullets only when needed.
- **Number everything.** The user will respond with numbers to triage.
- **Don't reorder or renumber the review log.** Findings keep their original
  numbers across passes; status updates accumulate as appended bullets under
  the existing entry. The log is append-only chronology.
- **Tagging discipline matters more than verbosity.** A finding tagged
  `[SAME-SLICE]` with a one-line "see Finding 7" reference beats a
  re-explained finding — the prior log already has the detail.
- **The log is a long-lived ledger, not a TODO that must reach zero.** Many
  findings will persist across multiple slices — that is the expected steady
  state. Don't pressure the user to close everything on every pass. Findings
  parked across slices is a feature, not a backlog smell.
- **Proactively flag `[needs-zoom-out]`.** When a finding's answer is outside
  the codebase (HIG, accessibility, Mac indie norms, academic methodology),
  say so and offer to fetch prior art *before* triage. Don't introspect
  deeper into the repo when the answer isn't there.

## Verbose mode (calibration period)

The first few times this skill runs in a new session or worktree where it
has prior log data to compare against, **narrate the merge process** in the
final report:

```
Read prior log: 7 findings (1 open, 5 parked, 1 resolved).
Carried forward to this pass:
  - Finding 1 (open) → Slice 2 impl-review must verify; mapped to current
    Finding 1 [SAME-SLICE]
  - Findings 3, 4, 5, 6 (parked) → no condition change observed; skipped
  - Finding 7 (parked → Slice 3 deferred) → not yet relevant; skipped
Genuinely new this pass: Findings 8, 9, 10
```

This is so the user can feel how the comparison and merge are working.
Drop the narration once the user says they understand the rhythm — typically
after 2–3 invocations on a doc with non-trivial prior log content.
