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

## Step 1: Detect mode and scope

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

**`code-review` always runs.** The others run only if their area is touched.

Announce which agents you're launching and why:
```
Calling the usual suspects:
- code-review (always)
- ux-critique (frontend components changed)
- i18n-review (locale files touched)
Skipping: security-review, a11y-review, what-would-gruber-say (not in scope)
```

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
   - **Design questions** — tradeoffs and competing approaches (from all agents'
     Questions sections, deduplicated)
   - **Improvements** — things that work but could be better

4. **Number everything** — each finding gets a number for easy reference when
   the user triages ("act on 1, 3, 7; park 4, 5; ignore 2, 6").

## Output format

```
# Review — [plan title or "recent changes"]

**Mode:** plan review / implementation review
**Scope:** <summary>
**Agents called:** code-review, ux-critique, i18n-review (3 of 6)

## Bugs / Errors
1. [HIGH] `file:line` — description (flagged by: code-review)
2. [MEDIUM] `file:line` — description (flagged by: code-review, a11y-review)

## Convention Violations
3. `file:line` — description. Ref: CLAUDE.md rule (flagged by: code-review)
4. `locale/key` — description (flagged by: i18n-review)

## Design Questions
5. Description of tradeoff. Two views: (a) ... (b) ...
   (raised by: code-review, ux-critique)
6. Description of tradeoff. (raised by: security-review)

## Improvements
7. `file:line` — suggestion (flagged by: ux-critique)

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
