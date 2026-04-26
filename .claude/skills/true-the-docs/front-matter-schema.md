# Front-matter schema

Every design doc that passes through `/true-the-docs` acquires (or
preserves) a YAML front-matter block. Fields are machine-readable
hints; the banner and body are the human-readable truth.

## Schema

```yaml
---
status: current | partial | pending | mixed | archived-historical | archived-reference
last-trued: 2026-04-21
trued-against: HEAD@<branch> on 2026-04-21  # or specific SHA on origin/main
superseded-by:
  - path/to/current-doc.md
supersedes:
  - path/to/old-doc.md
split-candidate: true  # only for status: mixed
---
```

## Field reference

### `status` (required)

One of:

- **`current`** — Archetype A or B. Load-bearing claims match shipped
  reality (verbatim or after targeted inline edits). Readers can act
  on the doc.
- **`partial`** — Archetype C. Mixed — some sections current, some
  marked superseded. Body banner explains which is which.
- **`pending`** — Archetype P. Forward-looking work not yet shipped.
  Body is aspirational; cross-check deferred until shipment.
- **`mixed`** — Doc is 70% current / 30% historical-only. Splitting
  deferred. Set `split-candidate: true`. Banner explains scope.
- **`archived-historical`** — Archetype D, factually obsolete.
  Retained in `docs/archive/` for the record. Do not treat body as
  truth.
- **`archived-reference`** — Archetype D, body still offers reasoning
  insight even if factually obsolete. Retained in `docs/archive/`.
  Read for design rationale, not implementation detail.

### `last-trued` (required when status != pending)

ISO date (`YYYY-MM-DD`) of the most recent truing pass. Used for
short-circuit: re-classifying a doc whose `last-trued` points at
HEAD or within 5 commits is skipped.

### `trued-against` (required when status != pending)

What reality was checked against. Two acceptable forms:

- `HEAD@<branch> on YYYY-MM-DD` — for truing passes that weren't
  anchored to `origin/main` (feature branches, beta runs)
- `<short-sha>` — only when the SHA is reachable from `origin/main`
  and won't be rewritten by squash-merge

### `superseded-by` (optional, list)

Only for archived docs. Paths to the current doc(s) that carry the
load-bearing content this one used to carry. Readers arriving here
should follow these pointers.

### `supersedes` (optional, list)

Only for current docs that replaced older ones. Paths to
`docs/archive/` entries. Useful for readers tracing "where did this
design come from?" back to pre-contact thinking.

### `split-candidate` (optional, boolean)

Only meaningful when `status: mixed`. Flags the doc for a future
split pass — contains both current and historical-only content that
would benefit from separation but wasn't split this pass.

## Worked examples

### Fresh Track C runtime doc after truing

```yaml
---
status: current
last-trued: 2026-04-21
trued-against: HEAD@main on 2026-04-21
---
```

### Partial doc with one superseded section

```yaml
---
status: partial
last-trued: 2026-04-21
trued-against: HEAD@main on 2026-04-21
---
```

Body contains `> **Superseded by X as of 2026-04-21** — see …`
banners at the relevant sections.

### Aspirational roadmap doc

```yaml
---
status: pending
last-trued: 2026-04-21
---
```

No `trued-against` because there's nothing to true against — the
work hasn't shipped.

### Archived doc (factually obsolete)

```yaml
---
status: archived-historical
last-trued: 2026-04-21
trued-against: HEAD@main on 2026-04-21
superseded-by:
  - docs/design-desktop-python-runtime.md
  - docs/design-modularity.md
---
```

Lives in `docs/archive/`.

### Current doc that replaced older thinking

```yaml
---
status: current
last-trued: 2026-04-21
trued-against: HEAD@main on 2026-04-21
supersedes:
  - docs/archive/design-desktop-pyinstaller-early-plan.md
---
```

## What the skill must not do

- **Silently overwrite existing front-matter.** If a doc already has a
  front-matter block, preserve unknown fields. Only update the
  known-schema fields.
- **Invent `trued-against` SHAs.** If the skill can't cleanly identify
  what it checked against, use the `HEAD@<branch> on <date>` form,
  never a SHA.
- **Mark `status: current` without removing drifted content from the
  body.** Front-matter is a hint; the body is truth. An inconsistent
  pair is worse than honest `partial`.
