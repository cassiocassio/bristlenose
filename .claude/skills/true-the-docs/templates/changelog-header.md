# Changelog header template

Prepended to the body of docs with Archetype A, B, C, D, or P after a
truing pass. Lives directly under the front-matter (and below any
truing-status banner, if present).

Purpose: machine-readable-ish trail of what each truing pass changed.
Replaces a missing git log for people who don't reach for it.

## Format

```markdown
## Changelog

- _<YYYY-MM-DD>_ — trued up: <one-line summary of what changed>.
  Anchors: <file:line or commit subject list>.
- _<earlier date>_ — trued up: <earlier summary>.
- _<doc creation date>_ — initial draft.
```

Newest entry at top. Older entries retained — this is a trail, not
just a status.

## Writing rules

### One line per pass

A truing pass produces one line. If the pass touched many sections,
summarise: "trued up C2 signing section, promoted bash invariant from
session notes, added validation-gates section." Don't break into
multiple bullets — that's what the body edits are for.

### Name the anchors

Every changelog line names its evidence anchors: file:line refs or
commit subjects. Readers checking "what changed on 21 Apr?" can
follow the anchors back to the evidence.

### Use past tense

"trued up", "rewrote", "marked superseded", "promoted". Not "will
trueup" or "is updating."

### No marketing voice

Wrong: "The system now robustly handles signing failures."
Right: "Rewrote signing section to describe `wait -n` job pool; added
fail-loud behaviour on codesign failure."

State the fact. Don't characterise.

## Per-archetype examples

### Archetype A (fresh)

```markdown
## Changelog

- _2026-04-21_ — trued up, no material changes. Verified against
  `desktop/scripts/build-all.sh`, `bristlenose-sidecar.spec`.
```

### Archetype B (one drifted section)

```markdown
## Changelog

- _2026-04-21_ — trued up: rewrote §"Entitlement table" to match
  empirical result from C0 spike (one key only:
  `cs.disable-library-validation`). Pre-spike guess preserved as
  baseline subsection. Anchors: `desktop/bristlenose-sidecar.entitlements`,
  commits "sidecar entitlement spike", "mark track C c0 done".
```

### Archetype C (multiple sections triaged)

```markdown
## Changelog

- _2026-04-21_ — trued up: promoted `wait -n` invariant from
  c2-session-notes to signing section (war story stays in notes);
  replaced "Bundling gotchas" with "Bundle data requirements" table
  covering BUG-3/4/5 class; added "Validation gates" section for four
  shipped guard-rails; marked §"Hypothetical launchd approach" as
  superseded. Anchors: `desktop/scripts/sign-sidecar.sh`,
  `desktop/scripts/check-bundle-manifest.sh`, C3 walkthrough.
```

### Archetype D (moved to archive)

```markdown
## Changelog

- _2026-04-21_ — moved to `docs/archive/` as `archived-reference`:
  body describes pre-Sprint-2 approach; current design lives in
  `docs/design-desktop-python-runtime.md` and `docs/design-modularity.md`.
  Body retained for pre-contact design rationale.
```

### Archetype P (aspirational)

```markdown
## Changelog

- _2026-04-21_ — confirmed still aspirational; no related work shipped
  since last pass. Cross-referenced with `TODO.md` and
  `docs/ROADMAP.md` — work remains post-100-days.
```

## Placement

Between front-matter and first H1 (or after the truing-status banner
if one is present):

```markdown
---
status: partial
last-trued: 2026-04-21
---

> **Truing status:** Partial — …

## Changelog

- _2026-04-21_ — trued up: …

# <Original H1 of the doc>

<body starts here>
```
