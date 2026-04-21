# Triage report template

Produced by `/true-the-docs --corpus` (whole-tree sweep, no edits) and
written to `docs/private/truing-corpus-<date>.md`. Also produced by
`--topic` runs as a pre-edit plan, written to
`docs/private/truing-<topic>-<date>.md`.

Purpose: one-page inventory of doc health, readable in a single pass,
drillable by `/true-the-docs --topic X` or `--doc Y`.

## Structure

```markdown
# True-the-docs triage — <scope>

**Date:** 2026-04-21
**Scope:** <corpus / topic: desktop python runtime / doc: path>
**Mode:** <shallow / deep>
**Agents invoked:** N parallel `design-doc-review` calls
**Short-circuited:** M docs (last-trued within 5 commits of HEAD)

## Summary

<One paragraph: doc count, archetype distribution, top-level invariant
status ("5 top-level docs classify as mixed — flagged for split"),
cross-doc parity issues found.>

## Classification

| Path | Archetype | Confidence | Last-trued | One-line evidence |
|---|---|---|---|---|
| `docs/design-X.md` | A | high | 2026-04-14 | all claims verified |
| `docs/design-Y.md` | B | high | 2026-04-07 | §Z drifted, rest current |
| `docs/design-Z.md` | C | medium | never | §A current, §B superseded, §C drifted |
| `docs/design-W.md` | D | high | never | body pre-Sprint-2; content now in X+Y |
| `docs/design-V.md` | E | — | never | external systems not inspectable |
| `docs/design-U.md` | P | — | 2026-04-14 | aspirational, no shipped code |

## Recommended actions

### Immediate (cold-reader-misleading)

- `docs/design-Y.md` — `/true-the-docs --doc docs/design-Y.md` (B,
  one section drifted)
- `docs/design-Z.md` — `/true-the-docs --doc docs/design-Z.md` (C,
  multiple sections)
- `docs/design-W.md` — archive move (D); run `--doc` to apply
  superseded report and move

### Follow-up (non-misleading drift)

- <docs flagged but where the drift isn't load-bearing; defer until
  next pass>

### Human action needed

- `docs/design-V.md` — E. Open question: <what the agent couldn't
  resolve>. Decide whether to classify as P or provide the missing
  evidence.

### Cross-doc parity issues

- Checkpoint C2 status: `road-to-alpha.md` says ⬜, `sprint2-tracks.md`
  says ✅. Resolve by sweep — run `/true-the-docs --topic "track C"`.

## Structural additions suggested

<Only when evidence warrants: multiple shipped things with shared
framing that don't yet have a design-doc home. Each suggestion names
the new section/table and the evidence for why it earns structural
prominence.>

- **"Validation gates" section** in
  `docs/design-desktop-python-runtime.md` — four shipped gates
  (logging-hygiene, bundle-manifest, release-binary, doctor
  self-test) currently have zero design-doc coverage. Shared framing:
  fail-loud guard-rails extending from signing pipeline.

## Docs not reviewed

<With reasons. Session notes / walkthroughs as edit targets (always
append-only). Marked-historical docs (already self-disclaim). CLAUDE.md
files (out of scope v1).>

- `docs/private/*-session-notes.md` (N files) — append-only, evidence
  only
- `docs/walkthroughs/*.md` (N files) — append-only, evidence only
- `docs/design-desktop-distribution.md` — marked-historical banner;
  may warrant a dated post-script, flagged for separate pass
- `CLAUDE.md` at N locations — out of scope v1
```

## Writing rules

### The summary paragraph earns its keep

A reader who reads only the summary paragraph should know: how healthy
is the corpus, what's urgent, is there a cross-cutting issue.

### Classification table ordered by urgency

Not alphabetical, not by directory. Most-load-bearing-drift docs at
top; fresh/pending docs at bottom. Reader should be able to stop
reading after the first block if they're short on time.

### Recommended-actions section is the drill-in menu

Every line in this section is a concrete next command the user can
run. No vague "consider updating X" — name the invocation.

### Cross-doc parity issues get their own subsection

These require a `--topic` sweep, not per-doc edits. Calling them out
separately prevents the skill user from running three `--doc`
invocations that each say ⬜/✅/🟡 inconsistently.

### Structural-addition suggestions earn their keep

Only include when you can cite multiple shipped things with a shared
framing. Don't suggest structural additions for one-offs.

### Explicit "not reviewed" section

Readers shouldn't wonder why session notes don't appear in the
classification table. Enumerate the out-of-scope set and why.

## Frequency

- `--corpus` triage: quarterly, or after a major release.
- `--topic` triage (produced as pre-edit plan): every time the skill
  runs in `--topic` mode.
- `--doc` mode: no triage report; findings roll into the doc's own
  changelog.
