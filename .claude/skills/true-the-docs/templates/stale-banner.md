# Truing-status banner template

Prepended below the front-matter (and above the changelog) for any
doc that is NOT Archetype A. Uses blockquote syntax so it renders
visibly in any Markdown viewer.

Purpose: tell a cold reader at a glance whether they can trust the
body. Front-matter status is machine-readable; this banner is human-
readable.

## By archetype

### Archetype B — mostly-good

```markdown
> **Truing status:** Current with targeted edits (trued 2026-04-21).
> §"<drifted section name>" was rewritten to match shipped reality;
> rest of the body is verbatim-accurate. See changelog below.
```

### Archetype C — partial

```markdown
> **Truing status:** Partial — sections on <topics current> are
> current (trued 2026-04-21); section on <superseded topic> is
> retained for context but superseded by <link>. See changelog and
> inline banners for specifics.
```

### Archetype D — archived

```markdown
> **Archived — do not treat body as current.** This doc describes
> <subject> as it was planned/understood in <rough date range>.
> Shipped reality diverged; current authoritative design lives in
> <link-1>, <link-2>. Body retained for historical record and
> design-rationale insight.
```

### Archetype E — escalated (temporary banner during review)

```markdown
> **Truing status:** Under review — agent classified as
> insufficient-evidence on 2026-04-21. Human disambiguation needed
> before updating; see `docs/private/truing-<scope>-2026-04-21.md`
> for open questions.
```

### Archetype P — pending

```markdown
> **Pending / aspirational.** This doc describes forward-looking
> design not yet shipped. Last confirmed aspirational 2026-04-21.
> Do not expect code to match; check `TODO.md` /
> `docs/ROADMAP.md` for status.
```

### Archetype A

No banner. Fresh docs don't need a status disclaimer.

## Section-level supersedence banner

For Archetype C docs where only specific sections are superseded, use
inline banners at the top of each affected section (not a global
banner at doc top — that would understate the current sections):

```markdown
## <Section heading>

> **Superseded by <link-to-current-doc> as of 2026-04-21.** Retained
> for context — <one line on why the pivot happened, if non-obvious>.

<original section body preserved, unedited>
```

## Writing rules

### Date every banner

Every banner includes the truing date. Readers returning months later
need to know when this assessment was made.

### Name the current doc when superseding

A superseded-section banner without a pointer to the current authority
leaves the reader stranded. Always link.

### Explain the pivot only when non-obvious

If a section was superseded because a feature was rescoped, say so
briefly. If it was superseded as routine implementation cleanup,
don't editorialise — just point to the current doc.

### Keep banners short

One to three sentences. Body is for detail; banner is for triage.

### Don't apologise

Wrong: "Sorry, this section is out of date…"
Right: "Superseded by X as of <date>."

State the fact. Readers don't need emotional cushioning.
