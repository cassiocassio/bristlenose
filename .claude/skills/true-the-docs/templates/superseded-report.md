# Superseded report template (Archetype D)

Prepended to Archetype D docs when they move to `docs/archive/`.
Replaces the need for readers to infer "is this doc still useful?"
by reading the whole body. The body below remains unedited as a
historical record.

Structure:

1. One-paragraph summary of what changed since the doc was written.
2. Pointer list to the current authoritative doc(s).
3. Explicit retention note.

## Template

```markdown
---
status: archived-historical  # or archived-reference
last-trued: 2026-04-21
trued-against: HEAD@main on 2026-04-21
superseded-by:
  - docs/design-current-doc-1.md
  - docs/design-current-doc-2.md
---

> **Archived — do not treat body as current.**

## What changed since this doc was written

<One paragraph summarising the delta. What decisions were made
differently? What shipped instead of what's described here? If a
pivot happened, when and why in one sentence.>

## Current authoritative docs

- [design-current-doc-1.md](../design-current-doc-1.md) — <what it covers>
- [design-current-doc-2.md](../design-current-doc-2.md) — <what it covers>

## Retention note

<One or two sentences explaining why this doc is kept at all.>

- If `archived-historical`: "Retained for the record — this is how we
  thought about <subject> in <date range>. Factually obsolete; do not
  treat body as truth."
- If `archived-reference`: "Retained as design-rationale reference —
  the specific approach described here is superseded, but the
  reasoning in §X informed subsequent decisions and may be useful to
  future contributors revisiting this problem space."

---

<original body preserved verbatim below this line>
```

## Writing rules

### Summary paragraph — two beats

1. What this doc used to describe.
2. What replaced it and roughly when.

Don't try to summarise the whole body. Don't editorialise about who
was right. State the change.

### Current-docs list — explicit coverage

For each current doc pointed to, say in one phrase what portion of
the old doc's scope it now covers. Readers arriving via search often
don't know which current doc is authoritative for their specific
question.

### Retention note — be specific

"Retained for historical record" is lazy. Name the reason:

- Historical: "This is how we thought about entitlements before the C0
  audit contradicted the guess list."
- Reference: "The credential-flow rationale in §3 predates the
  Keychain decision but the threat-model analysis there informed
  subsequent design."

### Never edit the body

The body is the historical artefact. Prepending is allowed; editing
inline is not. If a body claim is actively dangerous (e.g., points
readers at a vulnerable pattern), flag it in the summary paragraph
and leave the body alone. The banner makes it unambiguous that the
body isn't current.

## When NOT to use this template

- Archetype B or C docs — those get the stale-banner + changelog
  instead, and edits to the body.
- Marked-historical docs that already have a "rejected path" or
  equivalent banner — those already explain their own status. Add a
  dated post-script at most.
- Docs that should be deleted outright. Archiving implies "retained
  for reasons"; if there are no reasons, delete instead. This skill
  never deletes — it flags for human deletion.
