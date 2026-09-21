---
status: current
last-trued: 2026-09-21
trued-against: HEAD@main on 2026-09-21 — built the same day it was proposed; §4 is what landed
---

# Focus Mode on the Signals lens

**Status: BUILT 21 Sep 2026**, the same day it was proposed, with variant A (§3) as drawn. §4 is the record of what landed; the mockup's proposal layer is now a copy of the shipped rules plus the rejected variant B, kept so the choice can be re-judged. The parent feature is
[`design-focus-mode.md`](design-focus-mode.md) (shipped 0.24.0, Quotes lens
only); this doc extends it to one more lens and changes nothing about how it
works there.

**Mockup: [`docs/mockups/signals-focus-mode.html`](mockups/signals-focus-mode.html)** —
real signal-card markup over the baked shipped theme, Focus off beside Focus on,
the two candidate treatments of the finding switchable, light/dark and
default/edo one click each. The candidate CSS is quarantined at the bottom of
its `<style>` block and is the CSS this plan proposes to move into
`templates/focus-mode.css`. Decide there, not here.

## 1. What exists today, measured

Focus can only be **entered** on the Quotes lens. All three affordances are
gated to it:

| Affordance | Gate | Where |
|---|---|---|
| bare `z` | `pathMatches(pathname, "/report/quotes")` | `useKeyboardShortcuts.ts:635` |
| View ▸ Focus Mode (`⌘⌥F`) | `.disabled(bridgeHandler.activeTab != .quotes)` | `MenuCommands.swift:1034` |
| Moon toolbar button | `<Toolbar />` is mounted only by `QuotesTab.tsx` | `pages/QuotesTab.tsx:28` |

The Swift comment above the menu item says why, and names this plan's
precondition: *"the recede transform is defined for quote cards only, and a
live-but-inert menu item is worse than a dimmed one. Un-dimming later, once the
other lenses have a defined transform, is a free upgrade."*

But the mode is **not** confined to Quotes once entered. `FocusModeStore` is
module state that survives route changes by design, and it writes
`.bn-focus-mode` onto `<html>`. So a reader who presses `z` on Quotes and
clicks through to Signals arrives in a **half-state** that nobody designed,
produced by quote-card selectors that happen to match signal-card markup:

- `.bn-focus-mode .description` — the source banner (`SourceBanner` renders
  `<p class="description">`) drops to 0.4.
- `.bn-focus-mode blockquote .timecode` — every timecode in every signal card
  drops to 0.14 …
- … **except** continuation timecodes in a sequence.
  `.signal-card-quotes blockquote.seq-middle .timecode { opacity: 0.6 }`
  (`organisms/signals.css`) is (0,3,1) against the ghost rule's (0,2,1), so a
  run's first timecode ghosts and its continuations stay brighter — the
  inverse of the sequence treatment.
- Nothing else recedes: hero chip, tag chips, dots, footer, borders, all lit.

This is not a bug report against 0.24.0 — the doc's non-goals never claimed
the other lenses — but it is the state this plan replaces, and it is why the
plan is worth doing at all: the mode already leaks onto Signals, and what it
does there is arbitrary.

## 2. The transform — two axes, applied to the card

The parent doc's rule is enough; no third axis is needed. **Axis 1:** keep the
source's marks and the researcher's own; recede the machine's annotations.
**Axis 2:** anything acted *through* stays live and returns to full presence
while engaged — receding is a resting state, never a disabled one.

| Part of the card (`SignalsPage.tsx`) | Treatment | Axis |
|---|---|---|
| `.quote-text`, `.speaker` (`PersonBadge`) | **lit** | 1 — the source's marks |
| `.signals-codebook-heading` (location) | `--bn-focus-heading-opacity` (0.4); returns on `:hover`/`:focus-within` (it holds a link) | 1 — the twin of `.bn-group-header`, which takes 0.4 as wayfinding |
| `.signal-card-location` (headline), `.signal-elaboration` (claim + evidence) | **0.4 — variant A, proposed**; variant B keeps them lit. See §3 | 1 — the machine's reading of the quotes |
| `.signal-card-hero` (group + score, a `<button>`) | ghost 0.14; returns on card hover / focus-within / `[aria-expanded="true"]`; **keeps `pointer-events`** | 2 — a control: receded, never disabled |
| `.signal-card-metrics` (the working) | untouched | 2 — only rendered when the researcher opened it, which is engagement |
| `.signal-quote-tag`, `.intensity-dots`, `blockquote .timecode` | ghost 0.14; chips and dots take `pointer-events: none` at rest; all return on card hover / focus-within | 1 — same as the Quotes lens's badges and timecodes |
| `.signal-card-alternates` ("Also read as") | ghost 0.14; returns on engagement | 1 — annotation about annotation |
| `.signal-card-footer` (show-all toggle + `ParticipantGrid`) | ghost 0.14; returns on card hover / focus-within; the toggle keeps `pointer-events` | 2 — the lean-in action is one hover away |
| `.signal-card` box | `background: transparent`, `border-color` → `color-mix(… 40%, transparent)`, **guarded `:not(.bn-selected)`** | the quote-card dissolve, same formula; the fused seam survives as a faint line |
| `.signal-card-quotes` box | `background: transparent`, same guard | a second container inside the first — dissolving one and not the other leaves a slab inside a ghost |
| `.signal-card.bn-selected` (inspector-pointed) | **untouched** | the parent doc's invariant 3: selection expresses itself through `background`, the property the dissolve sets |
| `blockquote.bn-dissenting` hairline | untouched | already at the floor (2px inset at `--bn-colour-border-hover`) and it is about the evidence, not the card |
| Nav sidebar, heatmap `InspectorPanel`, page title, source banner | untouched (the banner already takes 0.4 through `.description`) | the parent doc's standing non-goal: not the sidebars; `[` and `m` close them in one key |

Every value is a formula over existing tokens — `--bn-focus-ghost-opacity`,
`--bn-focus-heading-opacity`, `--bn-colour-border`. No colour is named, no
palette file is touched, no new token. The transform composes with default/edo
× light/dark for the same reason the Quotes one does, and the ground is never
touched (recede-only; `background` only ever goes *to* transparent on a card,
never onto html/body).

**Two specificity notes, both load-bearing.**

1. The timecode ghost must be written at (0,3,1) —
   `.bn-focus-mode .signal-card-quotes blockquote .timecode` — to tie the
   organism's `seq-middle` rule and win on source order (`focus-mode.css` is
   later in `_THEME_FILES`). The engaged-state restore then puts continuation
   timecodes back to **0.6, not 1**, because 0.6 is their ordinary reading.
2. The card dissolve must carry `:not(.bn-selected)`. `.signal-card.bn-selected`
   is (0,2,0); a bare `.bn-focus-mode .signal-card` is (0,2,0) and later, so it
   wins and blinds the inspector's pointer — the same trap
   `tests/test_focus_mode_css.py` already pins for quote cards, and the reason
   §5 extends that test rather than writing a new one.

## 3. The one real decision — what happens to the finding

The headline and the elaboration are the object the lens exists to show. Two
readings are coherent; the mockup draws both.

**A — wayfinding at 0.4 (proposed).** The finding is the machine's reading of
the quotes. On the Quotes lens the machine's reading is the theme title and its
description, and those recede to 0.4 — legible enough to know where you are,
quiet enough not to compete with the evidence. A is the same rule applied to
the same kind of object. It also gives Focus a *job* on this lens: you enter it
to check the evidence against the claim, which is the one thing the lens's
ordinary reading does not privilege. And it is one rule to learn across both
lenses: *the participants' words stay lit, the machine's words recede to
wayfinding, the machine's numbers recede to nothing.*

**B — the finding stays lit.** Recede only the numbers and chrome; the
headline and claim keep full presence. Calmer than today, but Focus then
privileges the machine's text over the participants', which is the opposite
of what it does on Quotes — the same key would mean two different things one
click apart.

The recommendation is A. The mockup is there so the choice is made by eye, not
by this paragraph; if B reads better on real data, §4 is unchanged and only
two opacity declarations move.

## 4. Build plan — as built

Ordered so each step is green on its own and the affordances are ungated
**last** — a live-but-inert menu item is the failure the Swift comment warns
against, and it is avoided by defining the transform before exposing it.

**Step 1 — CSS.** Add a `── Signals lens ──` section to
`bristlenose/theme/templates/focus-mode.css` carrying the proposal layer from
the mockup verbatim: transitions under `.bn-focus-ready`, the guarded card and
quote-box dissolve, the 0.4 wayfinding rules, the 0.14 chrome rules with the
(0,3,1) timecode selector, the axis-2 restores (including the 0.6 continuation
restore and `[aria-expanded="true"]` on the hero), the `@media print` restore
for every new receded value and both backgrounds, and the new selectors added
to the `prefers-reduced-motion` set. Drop the `.lab-hovered` block — it is
harness only. One file, one section; the tests read one file.

**Step 2 — tests, Python.** Extend `tests/test_focus_mode_css.py` with a
`TestSignalsLens` class in the same idiom — invariants, not taste:

- every rule in the file that sets `background` on a `.signal-card` inside
  `.bn-focus-mode` carries `:not(.bn-selected)` (the silent one);
- every `.bn-focus-mode` selector that names a signal-card element has a
  `.bn-focus-ready` transition twin and a `prefers-reduced-motion` entry
  (extend the existing symmetry test's element list rather than copying it);
- the print block restores every property the Signals rules recede;
- the timecode ghost's specificity ties the organism's `seq-middle` rule
  (assert the selector contains `.signal-card-quotes`, or the half-state
  inversion of §1 comes back silently).

Prove each red first by deleting its target declaration, as the parent suite's
`_positive()` note records having had to.

**Step 3 — the `z` key.** Gate on `/report/quotes` **or** `/report/signals` — and **move the handler above the Quotes-lens gate** (`// Everything below acts on quotes`), which the plan missed: the first cut widened the route check and the new test still read `false`, because the handler sat below a `return` that fires on every non-Quotes route. The `m` key already lives above that gate for the same reason. `useKeyboardShortcuts.test.ts` pins
the route guard at `:847` (off-route `z` returns false) and the table at
`:1082`; add the signals-route positive case and keep the negative one on a
third route so the guard is still asserted to exist.

**Step 4 — the native menu.** `MenuCommands.swift:1034`:
`.disabled(![.quotes, .signals].contains(bridgeHandler.activeTab))`, and
rewrite the comment above it — it currently documents the Quotes-only scope as
a deliberate choice and would become the next session's false evidence.
`focusModeActive` is already mirrored from the SPA over the existing
`focus-mode` bridge message; nothing on the wire changes. Run
`desktop/scripts/test-swift.sh`, never a hand-rolled `xcodebuild`.

**Step 5 — the toolbar.** Nothing. The moon button lives in `<Toolbar />`,
which is Quotes-only because everything else in it is (search, view switcher).
In the browser the Signals lens gets `z`; in the app it gets the menu and
`⌘⌥F`. Mounting a lone moon button on Signals would be a new surface with one
control in it — raise it separately if the key alone proves undiscoverable.

**Also landed: a fifth knob.** `--bn-focus-outline-mix` (40%) in `tokens.css`, read by both the quote-card and signal-card dissolves — the percentage was a literal in one place and would have been in two. Speed and depth are now four numbers for both lenses, all in `tokens.css`; `test_reads_only_the_shared_knobs` refuses a Signals rule that declares its own.

**Step 6 — docs.** In `design-focus-mode.md`: the affordance table's route
column, the non-goals (the lens list, not the sidebar rule), and a one-line
pointer to this doc. Flip this doc's status. Register the mockup's outcome in
`docs/mockups/STATUS.md`. `CHANGELOG.md` under **Improved** — Focus Mode is
not new, its reach is; 0.30.0 was tagged the same morning, so the entry waits for the next version's heading.

**Not touched:** `FocusModeStore.ts` (route-independent already, correctly),
the bridge, the locale files (no new string), `theme/js/analysis.js` (frozen,
and the class is only ever set by the SPA), `print.css`, the export (it inlines
the theme, so this rides along as the Quotes rules did).

## 5. Non-goals, restated for this lens

- **No reflow.** Only `opacity`, `background`, `border-color`. The metrics
  block is not collapsed or hidden by Focus — it is simply left alone.
- **Not the inspector.** The heatmap is the loudest coloured thing on the
  page, and the temptation to fade it is real. It is a sidebar; the parent doc
  settled sidebars, and `m` closes it. Revisit only if closing it proves not to
  be what people do.
- **Not the nav.** Same rule.
- **Not the static byproduct.** `analysis.js` never receives the class.

## 6. Open questions

1. **A or B** (§3). The only decision that changes what is built.
2. **The pending skeleton** (`.signal-card-location-pending`) sits inside
   `.signal-card-identity` next to the headline and would take 0.4 under A. It
   already breathes 0.45–1. Probably fine; look once in the app with a cold
   cache.
3. **Phase 2 of the parent doc is still owed** — `--bn-focus-ghost-opacity`
   was shipped at 0.14 with the prose ("faint outline") unreconciled. This lens
   adds five more elements at that value. Settle the number once, in the lab,
   for both lenses; do not fork it.
