# React Component Library — Primitive Dictionary & Build Sequence

The React migration (Milestone 2+) builds a library of reusable primitives, not page-specific islands. Every composition in the app (quote card, sessions table row, codebook group, signal card, transcript segment) is assembled from the same small set of components. This document defines the primitives, their qualities, and the build order.

## Why primitives, not pages

The original Milestone 2 plan said "quote cards as React islands." But the interactive elements on a quote card — star toggle, editable text, tag badge, tag suggest dropdown — all reappear on other surfaces. Building them as quote-card-specific code means rebuilding them for the codebook, analysis page, and transcript page.

Instead: build the smallest reusable components first, then compose them into page-specific layouts. The quote card is the first *consumer* of the library, not the deliverable itself.

## The analogy

Cocktail making. The right 3 bottles (Badge, PersonBadge, TimecodeLink) let you make 10 drinks — static skeletons of every surface. Add 2 more (EditableText, Toggle) and you can make 30 — full interactivity on the quote card. Two more (TagInput, Sparkline) unlocks the codebook and sessions sentiment. The last 5 are specialty bottles: one bottle, one drink.

---

## The dictionary — 14 primitives

### 1. Badge

A small coloured label.

- **Qualities:** text, colour (from codebook group or sentiment), type (AI-assigned / user-created / read-only)
- **States:** default, hover (delete button visible), removing (fade-out animation), appearing (fade-in animation)
- **Behaviours:** optionally deletable (× appears on hover), animation on add/remove
- **Not a behaviour of Badge:** adding a new badge — that's TagInput's job. Badge just *exists* and optionally *goes away*
- **Current surfaces:** AI sentiment badges on quotes, user tag badges on quotes, codebook panel tags, tag filter dropdown (read-only variant), transcript margin annotations, histogram labels
- **Future surfaces:** signal card sentiment label, analysis page tag reassignment

### 2. PersonBadge

A speaker code lozenge, optionally with a name.

- **Qualities:** code (`p1`, `m1`, `o1`), role (participant / moderator / observer), display name (optional), colour
- **States:** default, highlighted (e.g. signal card shows which participants are quoted)
- **Behaviours:** optionally navigable (click → session/transcript drill-down)
- **Why separate from Badge:** Badge is a tag label with codebook colour. PersonBadge is an identity marker with role semantics. Same visual shape, completely different data source and meaning
- **Current surfaces:** quote footers, sessions table speaker columns, transcript segment headers, featured quote attributions, moderator/observer headers, signal card participant row
- **Future surfaces:** people table, analysis cross-references

### 3. TimecodeLink

A clickable time reference that opens or seeks a media player.

- **Qualities:** formatted time string (`[MM:SS]` or `[HH:MM:SS]`), participant ID, seconds, optional end seconds
- **States:** default, glow-active (player is at this timecode), glow-playing (pulsating during playback)
- **Behaviours:** click opens popout player or sends seek message to existing player window
- **Why it's a primitive:** the player open/seek logic, the glow feedback loop, and the formatted display are all coupled. Every surface that shows a timecode wants all three
- **Current surfaces:** quote cards, session table, hidden quote previews, transcript segments, coverage section, analysis featured quotes

### 4. EditableText

A piece of text that can become an input.

- **Qualities:** display value, original value (for revert), committed state (has been edited)
- **States:** display mode (plain text), edit mode (contenteditable), committed (shows edited indicator)
- **Behaviours:** enter edit mode (click trigger or external), commit (Enter, blur), cancel (Escape), revert to original
- **Variations by context:** smart-quote wrapping (quotes only), ToC sync (headings), downstream name propagation (people). These are *effects of committing*, not qualities of the editable itself
- **Future extensions:** word-level brush-to-delete, drag handles for reordering fragments — these compose on top of the same editable lifecycle
- **Current surfaces:** quote text (6 call sites via `editing.js`), section headings, theme headings, theme descriptions, participant names, participant roles (via `names.js`), codebook group titles (via `codebook.js`)
- **Future surfaces:** codebook subtitles, signal card titles, journey labels, session notes

### 5. Toggle

A thing that is on or off.

- **Qualities:** on/off state, visual treatment when on, visual treatment when off
- **States:** on, off, animating (transition between states)
- **Behaviours:** click flips state, state persists, optional animation on flip
- **Variations by context:** star (reorders siblings via FLIP animation), hide (removes from view + feeds a Counter elsewhere), AI-tag-visible (global show/hide of all AI badges)
- **Not a toggle:** checkbox in a filter list — that's a filter control, different primitive
- **Current surfaces:** quote star button, quote hide button, AI-tag visibility toggle
- **Future surfaces:** signal card star (flag key findings), session row pin

### 6. TagInput

A text field that suggests from a known vocabulary.

- **Qualities:** current text, filtered suggestions list, ghost completion text, active suggestion index
- **States:** closed, open (input visible), suggesting (dropdown visible), committing
- **Behaviours:** type to filter, arrow keys to navigate suggestions, Tab to accept ghost text, Enter to commit, Escape to cancel, commit-and-reopen for rapid entry
- **Data dependency:** needs the tag vocabulary (all known tags) and the exclusion set (tags already on this target). Codebook hierarchy is a *display concern* of the suggestions, not a quality of the input
- **Variations by context:** single-target (one quote), multi-target (bulk tagging), tag-to-group reassignment (analysis page). The input doesn't care — it emits `onCommit(tagName)`, the consumer decides what that means
- **Current surfaces:** quote card add-tag button
- **Future surfaces:** codebook add-tag row, transcript page tagging, analysis page tag reassignment

### 7. Sparkline

A miniature chart showing distribution across categories.

- **Qualities:** counts per category, colour per category, orientation (horizontal stacked bars)
- **States:** purely visual (no interaction yet). Future: click a bar to filter
- **Behaviours:** none currently — render-only
- **Current surfaces:** sessions table sentiment column, dashboard session rows, codebook tag mini-bars
- **Future surfaces:** per-participant sentiment cards, journey sentiment progression

### 8. Metric

A labelled numeric value with a proportional visual indicator.

- **Qualities:** label, numeric value, formatted display (e.g. `3.5×`), visual type (bar / dots / percentage)
- **States:** render-only
- **Behaviours:** none currently — render-only
- **Current surfaces:** signal card stats (concentration, agreement, intensity with bars/dots)
- **Future surfaces:** dashboard stat cards, per-participant stats

### 9. JourneyChain

An ordered list of labels joined by arrows.

- **Qualities:** ordered label list, separator character (`→`)
- **States:** render-only
- **Behaviours:** none currently. Future: click a label to filter by screen
- **Current surfaces:** sessions table journey column, dashboard session rows
- **Future surfaces:** journey detail view

### 10. Annotation

A positioned label that links a transcript segment to its analytical context.

- **Qualities:** label text (section/theme name), optional badge below, position alongside transcript text
- **States:** default, highlighted (when navigated to from report)
- **Behaviours:** click navigates to the corresponding section in the report
- **Current surfaces:** transcript page margins (section/theme labels + sentiment badges)
- **Future surfaces:** analysis drill-down, export previews

### 11. Counter

A count of suppressed/hidden/filtered items with a dropdown to see and restore them.

- **Qualities:** count, expanded/collapsed state
- **States:** collapsed (shows count), expanded (shows preview list)
- **Behaviours:** click to expand/collapse, item actions within the list (restore, navigate)
- **Variations by context:** hidden quotes (restore action), filtered items (clear filter action). The counter pattern is the same — the *item actions* vary
- **Current surfaces:** hidden quotes badge per quote-group
- **Future surfaces:** hidden sessions, filtered-out analysis items, collapsed sections

### 12. Thumbnail

A media preview image with a play action.

- **Qualities:** image source (or placeholder), has-media flag
- **States:** default (placeholder), loaded (image), hover (play icon prominent)
- **Behaviours:** click opens player at session start
- **Current surfaces:** sessions table media column, dashboard featured quotes (video fallback)

### 13. Modal

A dialog that takes focus.

- **Qualities:** visible/hidden, title, body content, action buttons
- **States:** hidden, visible (with backdrop)
- **Behaviours:** Escape to close, click-outside to close, focus trap
- **Variations:** confirmation (two buttons, destructive action), informational (single dismiss), form (inputs + submit)
- **Current surfaces:** histogram tag delete, codebook group delete, help overlay
- **Note:** infrastructure primitive — build when first needed (likely round 2)

### 14. Toast

A transient notification.

- **Qualities:** message text, duration, optional action
- **States:** appearing, visible, dismissing
- **Behaviours:** appears, auto-dismisses after timeout, optional manual dismiss
- **Current surfaces:** hide feedback, clipboard copy, API error feedback
- **Note:** infrastructure primitive — build when first needed (likely round 2)

---

## Build sequence

### Round 1 — Badge, PersonBadge, TimecodeLink

The three primitives that appear on 3–4 surfaces each. Largely stateless, render-only with one optional behaviour each (delete, navigate, seek). Building them first means you can immediately compose partial versions of *every* major surface.

**After round 1 you can render:** the static skeleton of a quote card, a sessions row's speaker column, transcript segments with margin labels, signal card footer and featured quote.

**Coverage:** partial skeletons of all 5 major compositions.

### Round 2 — EditableText, Toggle (+Modal, Toast as infrastructure)

EditableText appears on 3 surfaces and is the most *reused within* a single surface (6+ instances on one page). Toggle is in 1 surface (quote card) but star and hide are the two most common researcher actions. Together these unlock all interactivity on the quote card except tagging.

**After round 2 you can build:** a fully interactive quote card (minus tags), editable codebook titles, editable signal card titles. The quote card is *shippable* at this point as a first deliverable.

**Coverage:** complete quote card (minus tags), partial codebook, partial signal card.

### Round 3 — TagInput, Sparkline

TagInput is the most complex primitive (ghost text, keyboard nav, bulk mode) but unlocks tagging on quotes *and* codebook add-tag — the two surfaces researchers spend the most time on. Sparkline is simple and unlocks sessions table sentiment and codebook tag mini-bars.

**After round 3 you can build:** complete quote card (all interactions), complete codebook group, sessions table sentiment column.

**Coverage:** complete quote card, complete codebook group, near-complete sessions row.

### Round 4 — Metric, Annotation, Counter, Thumbnail, JourneyChain

Each unlocks one surface. Order within round 4 driven by what you're building next:

| Primitive | Unlocks | Build when |
|-----------|---------|------------|
| Metric | Signal cards (analysis page) | Before analysis migration |
| Annotation | Transcript page margins | Before transcript migration |
| Counter | Hidden quotes badge + dropdown | Before/with quote card ship |
| Thumbnail | Sessions table media column | Before sessions table parity |
| JourneyChain | Sessions table journey column | Before sessions table parity |

**Coverage after round 4:** all 14 primitives, all surfaces composable.

---

## Coverage matrix

Which primitives are needed by which compositions:

| Primitive | QuoteCard | SessionsRow | Transcript | Codebook | SignalCard |
|-----------|:---------:|:-----------:|:----------:|:--------:|:----------:|
| Badge | x | | x | x | x |
| PersonBadge | x | x | x | | x |
| TimecodeLink | x | | x | | x |
| EditableText | x | | | x | x |
| Toggle | x | | | | |
| TagInput | x | | | x | |
| Sparkline | | x | | x | |
| Metric | | | | | x |
| JourneyChain | | x | | | |
| Annotation | | | x | | |
| Counter | x | | | | |
| Thumbnail | | x | | | |
| Modal | (infra) | | | (infra) | |
| Toast | (infra) | | | | |

**7 primitives** cover 80% of the app. The remaining 5 are one-surface-each.

---

## Compositions

How the primitives assemble into page-level components:

- **Quote card** = Toggle(star) + Toggle(hide) + EditableText + Badge(AI) × N + Badge(user) × N + TagInput + PersonBadge + TimecodeLink + Counter(hidden, at group level)
- **Sessions table row** = PersonBadge × N + JourneyChain + Thumbnail + Sparkline + TimecodeLink (implicit via row click)
- **Transcript segment** = TimecodeLink + PersonBadge + text + Annotation × N
- **Codebook group** = EditableText(title) + EditableText(description) + Badge(draggable) × N + Sparkline(mini) + TagInput
- **Signal card** = Badge(sentiment) + Metric × 4 + TimecodeLink + EditableText(title, future) + PersonBadge × N

---

## Relationship to milestones

The original milestone roadmap (`docs/design-serve-migration.md`) defined milestones by page:

| Original milestone | Becomes |
|--------------------|---------|
| Milestone 2: Quote cards | Round 1–3 primitives → QuoteCard composition |
| Milestone 3: API replaces localStorage | Already done (6 data API endpoints, 94 tests) |
| Milestone 4: Dashboard stats | Reuses primitives from rounds 1–3 + Metric from round 4 |
| Milestone 5+: Codebook, analysis | Reuses all primitives; only new compositions needed |

The primitive-first approach means Milestone 2 produces more than a quote card — it produces a component library that accelerates every subsequent milestone.

---

## Conventions

- **File location:** `frontend/src/components/` for primitives, `frontend/src/islands/` for page-level compositions
- **Naming:** PascalCase component files matching this dictionary (`Badge.tsx`, `EditableText.tsx`, `TagInput.tsx`, etc.)
- **Testing:** each primitive gets a Vitest unit test file. `data-testid` attributes on every interactive element from day one (convention: `data-testid="bn-{component}-{element}"`)
- **CSS:** reuse existing atomic CSS classes from `bristlenose/theme/`. React components emit the same class names as the vanilla JS they replace — no new styling needed for visual parity
- **State:** primitives are controlled components. State ownership lives in the composition (QuoteCard, CodebookGroup, etc.) or in a React context for cross-cutting concerns (focus/selection)

---

## CSS ↔ React alignment

**Naming rule:** React component name wins. CSS files and classes are renamed to match the React primitive name using the `bn-{component-name}` pattern.

| CSS File | React Primitive | Alignment | Status |
|----------|----------------|-----------|--------|
| `atoms/badge.css` | Badge | 1:1 | Done (Round 1) |
| `molecules/person-badge.css` | PersonBadge | 1:1 (renamed from `person-id.css`) | Done (Round 1) |
| `atoms/timecode.css` | TimecodeLink | 1:1 | Done (Round 1) |
| `atoms/button.css` | Toggle | Partial — star/hide/toolbar split across `button.css` + `hidden-quotes.css` | Round 2 |
| `molecules/quote-actions.css` + `molecules/name-edit.css` | EditableText | States scattered | Round 2 |
| `molecules/tag-input.css` | TagInput | 1:1 | Round 2 |
| `organisms/blockquote.css` | (composition: QuoteCard) | N/A — composition, not primitive | Round 2 |
| `templates/report.css` (sparkline section) | Sparkline | Buried in template CSS | Round 3 |
| `templates/report.css` (journey section) | JourneyChain | Buried in template CSS | Round 4 |
| `organisms/analysis.css` | Metric | Buried in organism CSS | Round 4 |
| `templates/report.css` (thumbnail section) | Thumbnail | Buried in template CSS | Round 4 |
| `atoms/modal.css` | Modal | 1:1 | Round 4 |
| `atoms/toast.css` | Toast | 1:1 | Round 4 |

---

## Per-round CSS refactoring schedule

### Round 1 (done)
- Renamed `molecules/person-id.css` → `molecules/person-badge.css` (`.bn-person-id` → `.bn-person-badge`)
- No other CSS changes needed — Badge and TimecodeLink are already 1:1

### Round 2
- Create `atoms/toggle.css` — extract star/hide toggle states from `button.css` and `hidden-quotes.css`
- Consolidate editing states from `quote-actions.css` + `name-edit.css` into a coherent EditableText pattern

### Round 3
- Create `molecules/sparkline.css` — extract sparkline bar styles from `templates/report.css`
- Create `molecules/annotation.css` if transcript annotations need their own file (currently in `molecules/transcript-annotations.css` — may be 1:1 already)

### Round 4
- Extract `atoms/metric.css` from `organisms/analysis.css`
- Create `molecules/journey-chain.css` from `templates/report.css`
- Create `atoms/thumbnail.css` from `templates/report.css`
