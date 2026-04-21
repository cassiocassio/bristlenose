---
name: true-the-docs
description: >
  Reconcile developer-facing design docs in `docs/` and `docs/private/`
  against shipped reality (code, commits, post-mortem artefacts).
  Classifies each doc (A/B/C/D/E/P archetypes), then applies
  per-archetype edits — preserving historical value where it matters,
  archiving what's truly superseded. Three modes: `--corpus` (whole-tree
  triage report), `--topic <theme>` (slice reconciliation), `--doc
  <path>` (single-doc mode). Use after a checkpoint or release, when
  code has outrun its design docs.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion, TodoWrite
---

Reconcile design docs against shipped code. Classify per doc, act per
archetype, preserve historical value.

**Principle.** Design docs are a different genre from reference docs.
Planning narrative sometimes has value even when superseded. The skill
judges per doc — which sections to rescue, which to rewrite, which to
fossilise as history. Blanket "update all" destroys historical
evidence; blanket "archive all" loses design intent that still guides
current work.

**Output quality bar.** Fewer well-chosen edits > many cosmetic ones.
Triage by cold-reader impact — "would this mislead a contributor
picking up this doc fresh in six months?" — not by gap count.

# Invocation

Three modes, picked by args:

- `/true-the-docs --corpus` — whole-tree triage report (no edits)
- `/true-the-docs --topic <theme>` — reconcile a slice, apply edits
- `/true-the-docs --doc <path>` — reconcile one doc, apply edits
- `--dry-run` — any mode, writes edits to `/tmp/true-the-docs-preview/`
  instead of real paths

# Scope

**In scope:** `docs/design-*.md`, `docs/private/*.md` (excluding session
notes), `docs/walkthroughs/*.md` as evidence, `docs/*.md` top-level,
`docs/archive/` for moves.

**Out of scope (v1):**
- `CLAUDE.md` at any level — always-loaded-into-context truth docs,
  higher blast radius, different genre. Stretch goal.
- `docs/private/*-session-notes.md` and `docs/walkthroughs/*.md` as
  edit targets — append-only historical records. Used as evidence only.
- User-facing text — owned by `user-documentation-review` agent.
- Marked-historical docs (with "rejected path" or equivalent banner)
  — these don't need truing to match reality; they may need a dated
  post-script, handled as a separate pass.

# The four-phase workflow

Each phase earns its keep. Don't skip.

## Phase 1 — Scope orientation (5 minutes, no edits)

1. `git log --since=<window> --oneline` — one shot. What shipped?
2. List candidate docs: glob + grep by theme keywords (for `--topic`)
   or all of `docs/` (for `--corpus`).
3. Reject "audit everything" up front. For `--topic`, pick docs with
   actual topic content. For `--corpus`, do shallow classification
   (front-matter + H1 + `git log -1`), not deep reads.
4. Identify tracking docs (status tables, checklists) that need
   cross-doc parity checks.

## Phase 2 — Parallel audit (agent fan-out)

Launch up to **three parallel `design-doc-review` agents**, one per
doc cluster. Same contract for each:

> Review these docs: <paths>. Mode: deep / shallow. Return tight-bullet
> gap list with file:line refs. No prose commentary.

The prose-only constraint is load-bearing. Prose audits dissolve into
paragraphs the skill re-parses. Enforce bullets.

For `--corpus`, invoke the agent in shallow mode, batch ~25 docs per
call, ~3 calls total.

For `--topic`, invoke in deep mode, one call per cluster (e.g. "track C
runtime docs", "track C tracking docs", "track C session notes as
evidence only").

For `--doc`, one deep call.

## Phase 3 — Plan consolidation

Write a per-doc edit list into a plan note at
`docs/private/truing-<scope>-<date>.md` (gitignored via `docs/private/`
being gitignored, so it's a working scratchpad).

Scope explicitly what's *in* and what's *not*:
- In scope: inline edits, changelog headers, banner additions, archive
  moves, front-matter.
- Not in scope this pass: session-notes rewrites (never), CLAUDE.md
  updates (v1), structural reshuffles without clear framing, cosmetic
  phrasing drift.

Sequence edits: biggest / most-cross-referenced docs first, so later
docs can cite them.

For `--corpus`, the plan note IS the output. No edits. Human reviews
and drills in via `--topic` / `--doc`.

## Phase 4 — Edit + verify

Apply edits in priority order. After each doc:

1. Update front-matter (status, last-trued, trued-against).
2. Prepend changelog header (templates/changelog-header.md).
3. Apply targeted inline edits.
4. Add banners for superseded sections, preserving original content
   visibly (never silently delete).
5. Handle moves for Archetype D.

After all edits, run the **5-check verification sweep** (mechanical,
cheap; catches what re-reading won't):

1. **Tense sweep:** grep edited docs for `will`, `plan to`, `pending`,
   `unresolved`, `TBD`, `TODO`, `slated for`, `to be written`. Every
   hit that wasn't deliberate preservation is a rot candidate.
2. **Cross-ref resolution:** every `[text](path)` in edits — does
   `path` exist?
3. **Commit anchor spot-check:** for each cited commit subject, does
   `git log --grep=<subject>` find it?
4. **Status-table parity:** if tracking docs were edited, grep all
   `| N | X | ⬜/✅/🟡 |` rows and `- [ ]`/`- [x]` lines for the same
   checkpoint across docs. They must agree.
5. **Orphan-reference grep:** for any doc moved to `docs/archive/`,
   grep the rest of `docs/` + CLAUDE.md for references to the old
   path. Update or flag.

Running the checks is cheap. Skipping is where docs re-rot.

# The archetypes (summary)

Full detail in [archetypes.md](archetypes.md). Quick reference:

- **A** — fresh, changelog only
- **B** — one drifted section, targeted edits + changelog
- **C** — multiple sections triaged, rescue/rewrite/mark-superseded
- **D** — body is historical, prepend superseded report, move to
  `docs/archive/`
- **E** — insufficient evidence, escalate to human
- **P** — pending/aspirational, stays in `docs/`, changelog confirms
  still-aspirational date

# Conventions the skill enforces

## Front-matter

Schema: [front-matter-schema.md](front-matter-schema.md).

```yaml
---
status: current | partial | pending | mixed | archived-historical | archived-reference
last-trued: 2026-04-21
trued-against: HEAD@<branch> on 2026-04-21
superseded-by: [optional list of current docs that replace this]
supersedes: [optional list of archived docs this replaces]
split-candidate: true  # only for status: mixed
---
```

Added if absent, never silently overwritten.

## Changelog header

Prepended to the doc body for Archetypes B, C, D, and optionally A/P
when there was something to confirm. Template:
[templates/changelog-header.md](templates/changelog-header.md).

## Banners

Two kinds, both using blockquote syntax so they render visibly:

- **Truing-status banner** (Archetypes B, C, D):
  [templates/stale-banner.md](templates/stale-banner.md)
- **Section-superseded banner** (inline for specific sections in C
  docs): `> **Superseded by X as of YYYY-MM-DD** — see [doc-Y.md].`

## Archive

Single folder `docs/archive/`. Front-matter `status` disambiguates
historical vs reference. No subfolders — folder-name-as-editorial-
judgement blurs.

## Evidence anchors

Prefer `file:line` links + commit *subject* lines over raw SHAs. SHAs
on feature branches get rewritten by squash-merge. Only cite SHAs
when they're reachable from `origin/main` and you're confident.

## Preserve pre-contact content

**Never silently delete** content that predates shipped reality. Mark
it visibly stale (banner) and keep the body so readers debugging "why
did we pivot?" can trace the delta. Replacing pre-spike guess with
empirical result means *both* appear — old list preserved as baseline,
new section authoritative.

# Integration with existing machinery

- **`/end-session` Phase 2 step 6:** invoke `design-doc-review` on any
  design doc touched in-session. If B/C, offer `/true-the-docs --doc`.
  **Never auto-archive at session-end** — fatigue biases "yes" on
  prompts; archival requires explicit `--doc` invocation.
- **`/usual-suspects`:** add a row to the agent-selection table —
  invoke `design-doc-review` when design docs were touched AND
  implementation scope overlaps doc scope.
- **Co-trigger with `user-documentation-review`:** user-facing text changes
  (README, man page, help, locales) signal that design docs behind
  that code probably drifted too. `design-doc-review` fires in the
  same moments.
- **Short-circuit re-firing:** if `last-trued` front-matter points at
  HEAD or within 5 commits of HEAD, skip re-classification to avoid
  triple-firing and contradictory banners.

# Traps (learned from prior Track C truing pass)

- **Prose trap.** Agent audits in prose = unusable. Enforce bullets.
- **Volume-as-success.** Many cosmetic edits ≠ good truing. Few
  load-bearing edits > many nit edits.
- **Deleting pre-contact wrong things.** Preserve the delta. Visible
  staleness is a feature.
- **Rewriting session notes.** Append-only historical record. Never.
- **Inventing structure the docs don't warrant.** New section needs
  multiple shipped things with shared framing. One-off stays inline.
- **Trusting your own summary.** Re-reading your own edits smells
  right even when it isn't. The 5-check verification is mechanical
  and catches what re-reading won't.
- **"Same subject" two docs.** Not duplication — one is canonical, one
  is cross-cutting. Cross-reference, don't mirror.

# Output

After completing, print a summary:

```
True-the-docs — <scope>
Mode: <corpus | topic: X | doc: Y>
Docs classified: N (A: a, B: b, C: c, D: d, E: e, P: p)
Edits applied: <doc count> (<file count> files touched)
Moves: <archived-historical: N, archived-reference: M>
Verification: 5/5 checks clean (or list failures)
Plan note: docs/private/truing-<scope>-<date>.md
Next: review git diff; commit when satisfied
```

# Known limitations (v1)

- `CLAUDE.md` truing not supported. A trued design doc + stale sibling
  `CLAUDE.md` can be worse than two stale docs (trust-by-association).
  Users should know the skill's coverage is incomplete.
- Cross-cutting docs (`design-modularity.md`, `design-i18n.md`) may
  classify differently under different `--topic` invocations. Naive
  last-write-wins for now. Owning-theme convention is future work.
- Raw SHA anchors on feature branches are naive — trust user to not
  invoke mid-squash-merge.
