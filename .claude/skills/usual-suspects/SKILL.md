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
| `.ts`/`.tsx`/`.css`, `package.json`, server, pipeline, or perf-sensitive | `perf-review` |

**`code-review` always runs.** The others run only if their area is touched.

Announce which agents you're launching and why:
```
Calling the usual suspects:
- code-review (always)
- ux-critique (frontend components changed)
- i18n-review (locale files touched)
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

## Step 4: Consolidate

Once all agents return, produce a **single consolidated report**. This is the
hard part — don't just concatenate. Do this:

1. **Deduplicate** — if two agents flag the same issue (e.g. code-review and
   ux-critique both notice a missing keyboard handler), merge into one finding
   and note which agents flagged it.

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

## Step 4.6: William's parsimony pass

Before showing the report to the user, run the consolidated finding list
through the **what-would-william-of-ockham-say** agent in adjudicator mode
(Mode A). Spawn it via `Agent` with `subagent_type:
"what-would-william-of-ockham-say"` and pass the consolidated report as
input.

William's job at this stage is to:

1. **Filter every finding** as `real` / `edge` / `speculative` —
   shrinking the user's triage list from "everything every agent
   raised" to "the things actually worth deciding on."
2. **Pick the parsimonious fix** when multiple fixes have been
   proposed for the same problem, citing the heuristic (Rule of Three,
   simple-vs-easy, Hoare's test, Metz's wrong abstraction, etc.).
3. **Cluster duplicates** — agreement across agents is signal worth
   surfacing.
4. **Flag bikeshed crowding** — if the report devotes disproportionate
   weight to trivial findings while a hard one is under-discussed,
   William names *Parkinson's Law of Triviality* and points at what's
   been crowded out.

William returns an **annotated version** of the consolidated list
(per-finding annotation + a short summary). Show the annotated version
to the user in Step 5, not the raw consolidated list — one report, not
two.

**Skip William** when: only one agent ran (nothing to adjudicate), the
consolidated list has fewer than 3 findings (no signal worth filtering),
or the user explicitly invoked `--no-william`. Note the skip in the
report header so future passes know whether William's absence was
deliberate.

William is a signal, not a gate. The user still decides what to act on,
park, or ignore — William's annotations are pre-triage advice, not
verdicts.

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
**Agents called:** code-review, ux-critique, i18n-review (3 of 6)
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
