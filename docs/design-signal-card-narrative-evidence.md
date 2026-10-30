---
status: proposed
last-trued: 2026-10-28
depends-on:
  - docs/design-signal-card.md
  - docs/design-signal-snapshot-lifecycle.md
  - docs/design-signal-evidence-narrative.md
---

# Signal-card visual evidence treatment

## Decision

Give a selected signal card one contextual colour family, then use it
consistently and quietly: the selected-card keyline, the classification/score
control, evidence highlighter ink, cited-speaker flash, and contribution strip
all derive from the card's existing sentiment or codebook-group hue.

The card must not use colour merely as decoration. It makes one argument
legible:

```
classification and score
        ↓ same contextual hue
finding title → claim → supported evidence assertions → source quotes
        ↓                                      ↓
  selected-card keyline                 cited participant / quote
```

This is a presentation specification. The evidence-assertion schema, prompt,
validation and snapshot lifecycle are owned by
`design-signal-evidence-narrative.md`. This document consumes its validated
reader contract; it does not alter signal calculation, quote selection,
navigation, or the meaning of the score.

## Scope and non-goals

This specification restores the work missing from the present Signals lens:

- a hue-consistent selected card and hero disclosure;
- the generous editorial claim already tokenised in the system;
- structured, attributable evidence assertions between claim and quotes;
- inline highlighted evidence language that remains grammatical when wrapped;
- direct links from an assertion to its source participant(s) and quote(s);
- the compact / micro participant-contribution treatment designed for this
  card, rather than the legacy `.p-box` presence grid.

It does not:

- change the existing Section/Theme navigator or its scroll-and-focus model;
- generate narrative when a card is opened; snapshots remain the reader
  contract in `design-signal-snapshot-lifecycle.md`;
- introduce a new semantic hue palette, a valence scale, or a second score;
- introduce a visible stale-snapshot warning. The lifecycle retains that state
  for a later product decision.

## Card anatomy and reading order

The hierarchy is intentional. Only the title is a heading-like app element;
the claim is the large reading statement.

1. **Signal title** — short, evidence-earned finding name, for example
   “Stock clarity arrives late”.
2. **Classification and score control** — for example
   “Problem: Frustration 0.40”; opens the working chart. It is not a title.
3. **Signal claim** — the primary interpretation, set in the editorial face.
4. **Evidence assertions** — two to four compact, attributable statements
   explaining exactly what in the source supports the claim.
5. **Evidence quotes** — source excerpts with timecode, code tag and
   intensity. Four remain open; “Show all *N* quotes →” remains the local
   expansion control.
6. **Contribution array** — a right-aligned texture showing the distribution
   and relative weight of supporting evidence across participants.

The source DOM must read in this same order. The current float emits the hero
first so that the claim wraps around it; that visual convenience must not
leave the control announced before the finding. Resolve this while implementing
the treatment: keep a visually floated/positioned hero but put title and claim
before it in reading order, or provide an equivalent non-duplicated accessible
name/order. Do not use CSS `order` to pretend to solve source order.

## Contextual colour system

### Source hue

Each card exposes semantic custom properties. They are assigned once by the
card adapter, not recalculated independently by the hero, bullets and footer.

| Property | Purpose | Source |
|---|---|---|
| `--bn-signal-accent` | canonical contextual hue | sentiment token when the card has one; otherwise existing group/bar hue |
| `--bn-signal-accent-wash` | selected surface | accent mixed lightly into `--bn-colour-bg` |
| `--bn-signal-accent-keyline` | selected border and quiet control border | accent mixed with the current surface to normal keyline contrast |
| `--bn-signal-accent-ink` | readable text/highlight ink | contrast-safe darker/lighter derivation of the canonical hue |
| `--bn-signal-accent-highlight` | inline evidence marker fill | a stronger tint of the same hue than the card wash |
| `--bn-signal-accent-strength-1..3` | ordinal contribution fills | three lightness/opacity steps of the same hue |

For a sentiment card, use the existing named sentiment tokens:
`--bn-sentiment-frustration`, `--bn-sentiment-confusion`, and so on, plus
their existing `-bg` partners. For a group card, use the existing group/bar
colour (`getBarColour` / its design-token equivalent), never a newly invented
semantic colour.

The current selection treatment is the correct starting ratio and should be
promoted from ad-hoc per-card names to the properties above:

```css
--bn-signal-accent-wash:
  color-mix(in srgb, var(--bn-signal-accent) 10%, var(--bn-colour-bg));
--bn-signal-accent-keyline:
  color-mix(in srgb, var(--bn-signal-accent) 40%, var(--bn-colour-bg));
```

The named hue is allowed as a fill, border or small-chip ink. It is **not
automatically safe as light-mode body text**: for example,
`--bn-sentiment-frustration` is documented as 3.56:1 on white. The
implementation must derive `--bn-signal-accent-ink` against the current card
surface and verify ordinary text contrast before using it in highlighted
phrases. It may use a documented darker palette counterpart or a colour mix
towards `--bn-colour-ink`; it must not reuse `--bn-colour-error-text` for
every sentiment, because that would falsely make the accent system orange.

### Application

- **Selected card:** `background: var(--bn-signal-accent-wash)` and
  `border-color: var(--bn-signal-accent-keyline)`.
- **Hero control:** text, caret and hover/focus border use the same contextual
  ink/keyline. Its existing badge surface remains a restrained tint, not a
  separate competing colour patch.
- **Claim:** remains ordinary `--bn-colour-ink`; it must not be recoloured.
- **Evidence marker:** contextual ink on contextual highlight fill, not the
  bright generic `--bn-colour-new-highlight`.
- **Contribution cells:** one hue family, with ordinal strength encoded by
  lightness/opacity; no second sentiment/participant palette.

Dark appearance follows the existing `light-dark()` sentiment values. Every
derived property is mixed with the active surface, not hard-coded for the
light canvas; the selected border therefore stays a normal keyline rather than
becoming a glowing outline.

## Typography and spacing

Use the existing type ladder; do not add a one-off size merely to make this
card look designed.

| Role | Token treatment |
|---|---|
| signal title | `--bn-text-signal-title` / `--bn-text-signal-title-lh` / `--bn-weight-signal-title` (15px, 1.5, 700) |
| claim | `--bn-font-editorial`, `--bn-text-signal-claim` / line-height / tracking / weight (20.7px, 1.4, -0.005em, 500), max `76ch` |
| evidence assertions | body face, `--bn-text-body` / `--bn-text-body-lh`, normal weight, muted supporting ink |
| participant cell label | `--bn-text-micro`; it is the bottom of the established ladder and is deliberately subordinate |
| hero and local “Show all” control | existing `--bn-text-label` treatment |

Keep the semantic signal-card spacing aliases. They are the agreed snapped
values, not tunable arbitrary pixels:

| Relationship | Token | Current value |
|---|---|---:|
| card inset | `--bn-signal-card-inset` | `--bn-space-2xl` / 48px |
| claim/evidence-to-quote region | `--bn-signal-card-section-gap` | `--bn-space-xl` / 32px |
| quote inner gutter | `--bn-signal-card-quote-inset` | `--bn-space-md` / 12px |
| adjacent quote separation | `--bn-signal-card-evidence-gap` | `--bn-space-md` / 12px |
| quote region-to-footer | `--bn-signal-card-footer-gap` | `--bn-space-lg` / 24px |

Add only semantic aliases for the new relationship, for example
`--bn-signal-card-assertion-gap: var(--bn-space-sm)` and
`--bn-signal-card-assertions-top: var(--bn-space-lg)`, if a measurement is
needed in more than one card state. Do not introduce `17px`, `31px` or `50px`
values.

## Evidence assertions

### Reader contract

The card consumes the `SignalEvidenceAssertion` reader contract from
`design-signal-evidence-narrative.md`: ordered playback text, one optional
fragment range, a durable source quote ID, and a participant ID. It must not
infer fragments, citations or participants in the browser.

When assertions are absent — including a legacy snapshot containing only an
unstructured evidence summary — render the existing ordinary supporting
paragraph. Do not manufacture a highlight or speaker badge.

### Markup and wrapping

Use real list semantics and ordinary inline content:

```html
<ul class="signal-evidence-assertions">
  <li>
    One participant was
    <mark class="signal-evidence-highlight">the warning did not name
      which specific items were unavailable</mark>
    <a class="speaker-link" href="…transcript at that moment">p1</a> (a link to the transcript, as the speaker badge is everywhere; the highlighted words are the control that flashes the quote, 30 Oct 2026).
  </li>
</ul>
```

The important constraint is that `<mark>` and the speaker control stay inline.
Do not use a flex row, `inline-block`, or a fixed-width prefix that strands
“One participant was” in a narrow column. Wrapped continuation lines align
with the assertion text, not beneath the bullet. Use normal list flow or a
marker/text grid with `minmax(0, 1fr)`; test at the tight pane.

The highlight is a reading marker, not a pill:

```css
.signal-evidence-highlight {
  display: inline;
  color: var(--bn-signal-accent-ink);
  background: var(--bn-signal-accent-highlight);
  border-radius: var(--bn-radius-sm);
  padding-inline: 0.08em;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
```

It may wrap across lines; `box-decoration-break: clone` makes each continuation
look intentionally marked while the phrase still reads inline. It must not
force a line break before or after itself.

### Speaker attribution and evidence focus

Every assertion has one durable participant/source-quote pair in V1 and ends
with an inline speaker badge. It is a data pointer, not redundant decoration.

- Focus, hover or click on an assertion badge temporarily marks its source
  quote(s) and matching contribution cell(s) with the existing restrained
  yellow-flash/attention treatment.
- Clicking a quote, or using its keyboard evidence control, applies the same
  focused state to every assertion that cites it. Escape, a second activation,
  or moving focus away clears a transient focus; persistent selection follows
  the current card interaction model.
- The visual badge may say `p1`; its accessible label names the relationship,
  for example “Participant p1; highlights quote at 12:22 supporting this
  assertion”.
- The badge must not navigate away. If a quote is initially hidden, the
  interaction expands the local quote list before moving focus to it.

This needs a local `focusedEvidenceQuoteIds` state keyed by durable quote ID,
not list index. Avoid nested click handlers: the selected-card surface itself
should not masquerade as a button when it contains real buttons. Use an
explicit noninteractive selection treatment for the card or move the card
focus control to a dedicated element.

## Hero and working chart

Keep the existing single hero chip, label vocabulary and disclosure behaviour:
`Problem: Frustration 0.40` + caret. Do not split it into multiple badges.

At a generous card measure, the expanded working chart is top-right and the
title/claim flow into the remaining measure and underneath it. It stays a
compact audit disclosure, not a competing headline. At the established compact
container threshold, close or hide the detailed chart while retaining the
compact hero control; it must not cause an ellipsis-based participant fallback.
The threshold is a card container query, not the whole window width, so it
works when project and Signals panes are both open.

## Contribution array

The footer is a compact information visual, not a speaker roster.

| Card measure | Appearance | Meaning |
|---|---|---|
| generous / regular | right-aligned compact cells with `p1`, `p2`, … set in micro type inside each cell | attributable inspection remains possible |
| compact | right-aligned micro cells with **no text** | one cell per participant; distribution remains scannable |

Never place the participant ID above a cell, replace omitted IDs with `…`, or
turn the row into a wide bar. A usual study has 12 participants, a large one
about 20 and exceptional studies up to 40; the micro mode must preserve one
cell per participant across that range. It is specifically intended to fit the
ten-participant responsive working layout.

Each cell encodes one variable: the participant's relative attributable
evidence contribution to this signal. The current deterministic basis is the
sum of displayed card-quote intensity per participant, ranked into three
ordinal levels. Preserve that basis until the snapshot builder supplies a
better explicit contribution value:

- absent: no supporting evidence — ghost outline and subdued label;
- 1: low relative contribution;
- 2: medium;
- 3: high relative contribution.

There is no second colour meaning. The cells use three strength steps of the
same card accent; intensity dots remain per-quote and encode quote intensity.
This separation is the information-visual justification: readers can see
“widely distributed”, “a few strong contributors”, or “many weak contributors”
without confusing contribution with valence or identity.

Implement this as a reusable `EvidenceContributionArray` primitive/molecule,
not private `.p-box` rules. Its regular cells retain the tokenised micro label;
its absent state is substantially quieter than present cells; its narrow mode
sets `font-size: 0` only after the accessible labels remain in the DOM. The
array and hero receive `--bn-signal-accent*` from the card rather than separate
`--card-accent` calculations.

## Quote-region invariants

This work must not disturb the improvements already made to quote reading:

- retain the timecode's left float/gutter and the quote body’s natural wrapped
  text relationship;
- retain intensity dots floated at the top right, so quote text wraps around
  them rather than losing a permanent right column;
- retain four open quotes, the existing chronological sequence treatment and
  the dissent marker;
- style “Show all *N* quotes →” as the existing low-emphasis label-sized link
  in `--bn-colour-accent`, never as display/body text.

## Implementation plan

1. **Token layer.** Add documented semantic signal-accent and evidence-
   assertion aliases in `bristlenose/theme/tokens.css` and
   `tokens-typography.css`. Reuse sentiment/group palette sources; add no
   standalone hex values.
2. **React composition.** In `SignalsPage.tsx`, assign the semantic card
   properties once; update `SignalHero`, selected-card styles and the
   contribution array to consume them. Render only validated structured
   assertions between claim and quote region, and use its durable quote IDs for
   cross-highlighting.
3. **CSS.** Replace the legacy `.participant-grid/.p-box` presentation with
   the shared array, add inline assertion/highlighter rules, and keep the
   existing semantic spacing aliases. Use a container query for micro cells and
   chart compaction.
4. **Accessibility and interaction.** Repair the outer-card/button nesting
   while adding citation buttons; test tab sequence, Enter/Space, Escape,
   visible focus, reduced motion and both colour appearances.
5. **Regression tests.** Add component tests for legacy fallback, inline wrapping markup,
   citation-to-quote focus, absent contribution cells and micro-mode accessible
   names; visual checks at the tight working pane, normal pane and generous
   viewport with 10, 12, 20 and 40 participants.

## Acceptance criteria

- A selected Frustration card has a single coherent orange family in its
  keyline, hero, highlight, cited badges and contribution strengths, in both
  light and dark appearances.
- The title is compact heavy sans; the claim is generous serif; evidence
  assertions are visually quieter than both while remaining easy to read.
- An evidence sentence wraps as one sentence: bullet, prefix, highlighted
  fragment, speaker badge and punctuation remain in normal inline flow.
- Every “one participant” assertion gives the reader a real pointer to the
  supporting quote and participant; legacy data never pretends otherwise.
- Contribution cells are right aligned; zero contributors are ghostlike;
  compact mode uses textless micro cells with no ellipsis and still exposes
  accessible participant/contribution names.
- At narrow card widths, the detailed chart closes/compacts before it damages
  the reading measure; the hero remains usable.
- Offline or provider-unavailable reading renders the last complete snapshot,
  including its saved assertions and references, without a generation request.

## Deferred choices

- an explicit user-visible “evidence changed since computed” indication;
- a richer contribution measure than ranked aggregate quote intensity;
- optional, almost-imperceptible selected-surface depth/inner glow. It is not
  part of this implementation and must not distract from the evidence hierarchy.
