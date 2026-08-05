# Keyboard Navigation — Design Document

Reference doc for keyboard shortcuts and focus system in the HTML report.

## Design Principles

1. **Leverage muscle memory** — use conventions from Gmail, GitHub, Linear (the apps researchers already use)
2. **Ring for focus, background for selection** — keep visual language extensible for future multi-select
3. **No focus is a valid state** — user must opt-in to keyboard navigation via click or keypress
4. **Focus is logical, not visual** — scrolling away doesn't lose focus; j/k resumes from where you were
5. **Preserve colour for tags** — starred uses grey (not amber/orange) to keep colour palette available for sentiment tags

## Terminology

**Starred** (not "favourites") — neutral annotation. A quote about your software being terrible is worth starring without it being a "favourite". Gmail muscle memory: `s` = star.

**Rename required:** `.favourited` → `.starred`, `bristlenose-favourites` → `bristlenose-starred`, etc.

## Focus vs Selection vs Starred

| Concept | Purpose | Visual | Count | Persistence |
|---------|---------|--------|-------|-------------|
| **Focus** | Keyboard target ("cursor") | Shadow lift (white bg) | 0 or 1 | Session, survives scroll |
| **Selection** | Operand set for bulk actions | Light blue bg + blue left bar | 0 to N | Session, cleared on nav |
| **Starred** | Persistent annotation | Grey left bar + bold text | 0 to N | localStorage |

Phase 1 implements focus only. Selection is future work.

## Visual Design Decisions (Final)

### Page Background
- **White** (`#ffffff`) — no tint
- Rationale: Save tint for future left-hand navigation panel

### Starred (existing, unchanged)
- **Left border:** `1px solid #999` (grey)
- **Text:** `font-weight: 600`
- **Star icon:** Grey (`#999`) when starred, outline (`☆`) when not
- **Hover:** Blue (`--bn-colour-accent`)
- Rationale: Grey preserves colour palette for sentiment tags; bold text provides "read me first" visual weight

### Focused (new)
- **Background:** `#ffffff` (white)
- **Shadow:** `0 3px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05)`
- **z-index:** Lifted above siblings
- Rationale: Shadow lift is elegant and classy; provides clear visual distinction without colour

### Selected (future, designed now)
- **Background:** `#f5f9ff` (very light blue)
- **Left border:** `1px solid var(--bn-colour-accent)` (blue)
- Rationale: Light blue is distinct from starred grey; 1px matches existing border width

### Combined State Priority
Left border priority: **Starred grey > Selected blue > Default grey**

| State | Background | Left Border | Shadow |
|-------|------------|-------------|--------|
| Normal | `#f9fafb` | `1px #e5e7eb` | none |
| Starred | `#f9fafb` | `1px #999` | none |
| Focused | `#ffffff` | `1px #e5e7eb` | yes |
| Selected | `#f5f9ff` | `1px accent` | none |
| Starred + Focused | `#ffffff` | `1px #999` | yes |
| Starred + Selected | `#f5f9ff` | `1px #999` | none |
| Focused + Selected | `#f5f9ff` | `1px accent` | yes |
| All three | `#f5f9ff` | `1px #999` | yes |

### CSS Tokens (new)

```css
/* Focus state */
--bn-focus-shadow: 0 3px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05);

/* Selection state */
--bn-selection-bg: light-dark(#f5f9ff, #1a2332);
/* Border uses: 1px solid var(--bn-colour-accent) */
```

## Keybindings

### Navigation

**Two models, deliberately.** `j`/`k` are a *list* cursor — "next item in reading
order", whatever the layout. The arrows are *geometric* — "the quote that way on
screen". They coincide in a single column, which is why they were synonyms until
the quote grid arrived. See "Spatial arrow navigation" under Implementation
Phases for why they had to split.

| Key | Action | Notes |
|-----|--------|-------|
| `j` | Focus next quote (reading order) | From no-focus: first visible. The only key that walks *every* quote — arrows follow one lane |
| `k` | Focus previous quote (reading order) | From no-focus: last visible |
| `↓` / `↑` | Focus the quote below / above | Measured geometry, not DOM order |
| `←` / `→` | Focus the quote left / right | No wrap at the edge; masonry has no row to wrap into |

### Actions on Focused Quote

| Key | Action | Notes |
|-----|--------|-------|
| `s` | Toggle star | Gmail convention |
| `t` | Add tag | Opens tag input |
| `Enter` | Play in video player | Opens/seeks popup at timecode |

### Global (no focus needed)

| Key | Action | Notes |
|-----|--------|-------|
| `/` | Focus search input | Near-universal (Gmail, GitHub, Slack) |
| `?` | Help overlay | Gmail, GitHub convention |
| `Escape` | Close/clear/unfocus | Context-dependent |

### Selection (multi-select)

| Key | Action | Notes |
|-----|--------|-------|
| `x` | Toggle select | Add/remove focused quote from selection |
| `Shift+j/k` | Extend selection (reading order) | Moves focus and adds to selection |
| `Shift+arrow` | Extend selection (geometry) | Follows the same path the bare arrow would |

### Rejected/Deferred

| Key | Reason |
|-----|--------|
| `e` (edit) | Not obvious; pencil icon is discoverable |
| `v` (view cycle) | Toolbar territory |
| `c` (copy CSV) | Toolbar territory |
| `Space` | Reserved for browser scroll |

## Focus State Model

### States

```
focusedQuoteId: string | null
```

- `null` = no focus (initial state, or after Escape/background click)
- `string` = ID of focused blockquote

### Transitions

| From | Action | To |
|------|--------|-----|
| No focus | `j` or `↓` | Focus first visible quote |
| No focus | `k` or `↑` | Focus last visible quote |
| No focus | Click on quote | Focus that quote |
| Focused | `j`/`k`/arrows | Move focus, scroll into view |
| Focused | `Escape` | No focus |
| Focused | Click background | No focus |
| Focused | Click different quote | Focus that quote |
| Focused | Scroll away | Focus stays (off-screen) |
| Focused | `t` or click tag-add | Editing (tag input) |
| Editing | `Escape` or blur | Return to Focused |

### Off-screen Focus Behavior

Focus is logical position, not visual highlight. If user scrolls away and presses j/k:
1. Focus moves from current (off-screen) position
2. View scrolls to show newly focused quote

This matches Gmail, GitHub, macOS Finder behavior.

## Help Overlay

Minimal modal listing shortcuts. Triggered by `?`. Closes on Escape or click outside.

```
Keyboard Shortcuts

Navigation              Selection
  j / ↓   Next quote      x           Toggle select
  k / ↑   Previous        Shift+j/k   Extend

Actions                 Global
  s       Star quote(s)   /           Search
  t       Add tag(s)      ?           This help
  Enter   Play in video   Esc         Close / clear
```

Four-column layout with Navigation, Selection, Actions, Global sections.

## Implementation Phases

### Phase 1: Rename favourites → starred ✅ DONE
- CSS class: `.favourited` → `.starred`
- JS: `favStore` → `starStore`, `initFavourites()` → `initStarred()`, `favourites.js` → `starred.js`
- localStorage: migrate `bristlenose-favourites` → `bristlenose-starred`
- View switcher: "Favourite quotes" → "Starred quotes"
- Token: `--bn-colour-favourited` → `--bn-colour-starred`

### Phase 2: Add focus/selection CSS tokens ✅ DONE
- Added `--bn-focus-shadow` and `--bn-selection-bg` to `tokens.css`
- Created `atoms/interactive.css` with `.bn-focused` and `.bn-selected` classes

### Phase 3: Global shortcuts ✅ DONE
- Implemented in `focus.js` (not separate keyboard.js)
- `isEditing()` guard function
- `/` → focus search (expands search container first)
- `?` → help overlay modal
- `Escape` → close help, clear search, or unfocus (in that priority)

### Phase 4: Focus system ✅ DONE
- `focusedQuoteId` state in `focus.js`
- `.bn-focused` CSS class (white bg + shadow lift)
- `j`/`k`/arrow handlers
- Click to focus, Escape/background-click to blur
- Scroll-into-view on focus change

### Phase 5: Actions on focused quote ✅ DONE
- `s` → toggle star
- `t` → open tag input
- `Enter` → open video player at timecode
- `Space` rejected — reserved for browser scroll

### Phase 6: Multi-select ✅ DONE
- `selectedQuoteIds: Set<string>` in `focus.js`
- `.bn-selected` CSS class (light blue bg + blue left bar)
- Finder-like click behavior:
  - Plain click = focus + single-select
  - Cmd/Ctrl+click = toggle selection
  - Shift+click = range selection from anchor
  - Background click = clear selection
- Keyboard selection:
  - `x` → toggle selection on focused quote
  - `Shift+j/k` → extend selection while navigating
  - `Escape` → clear selection (after help/search)
- Header shows "N quotes selected" when selection exists
- Bulk actions:
  - `s` → star/unstar all selected (if any unstarred → star all; if all starred → unstar all)
  - `t` or click `+` → bulk tagging (applies tag to all selected quotes)
  - CSV export respects selection (exports only selected quotes)
- Auto-suggest in bulk mode filters by intersection (only hides tags ALL quotes have)

**Known issue:** Dark mode selection *fill* (`--bn-selection-bg: #1a2838`) is hard to see — ~1.16:1 against a neighbouring card. The 1px `--bn-selection-border` bar clears 3:1 in both themes, so the state is legible; it's the wash that's weak.

### Phase 7: Spatial arrow navigation ✅ DONE (4 Aug 2026)

The quote grid became multi-column `auto-fill` and then masonry (`display: grid-lanes`, WebKit — so the WKWebView always gets it), which broke the arrows: `moveFocus` walked `ids[i ± 1]` in DOM order, so `↓` moved to the card rendered to the **right**, and `←`/`→` were unbound entirely.

- `frontend/src/utils/spatialNav.ts` — pure module. Takes measured `CardRect`s so lanes, column count, section boundaries and filtered cards all resolve without being computed.
- **Rule: nearest-centre in the pressed half-plane, with a 2× cross-axis penalty.** Three rules were prototyped side by side (see Experiments) and felt equivalent on a realistic sample, so the one with no state won. The penalty is not optional: `.quote-group` is `align-items: start`, so same-row cards have different centres once their heights differ, and unweighted nearest-centre answered `↓` with a *sideways* card at ordinary height variance.
- `j`/`k` unchanged, and still what the native Quotes menu's Next/Previous Quote drive.
- Arrows are claimed only when the cursor actually moves, so page scroll survives at grid edges, on empty search results, and before the islands register.
- An arrow another control already claimed (`e.defaultPrevented`) is declined — the sidebar resize separator handles `←`/`→` without `stopPropagation`.
- `block: "nearest"` replaced `block: "center"` on focus scroll: centring lurched the viewport on every horizontal step even when the target was already visible.

**Known gap:** `UncategorisedFloor` renders real quote cards but never registers them, so the floor is unreachable by keyboard and absent from `⌘A` and the copy payload. That's a deliberate boundary at three layers (no registration, no focus/selection rendering, not resolvable in `buildLeanQuotesText`) — bringing the floor into the interactive model is the Phase 0 re-filing work, not a navigation fix.

## Outstanding Design Questions

### Still to confirm:
1. **Dark mode selection visibility** — current `#1a2838` is hard to see; needs brighter variant
2. **Help overlay styling** — simple modal vs more elaborate design
3. **Dropdown keyboard highlights** — should use same selection colour (`#eef4fc`)
4. **Advertising the two models** — `↓` walks one *lane*, so on a three-column
   window it visits roughly a third of the quotes with no visual cue that a lane
   is a lane. The primary task ("go through every quote once, starring as I go")
   is therefore `j`-only. Both models need advertising, with one framing
   sentence — advertising the arrows alone would promote the model that can't do
   the main job. **The only advertised surface is off-repo**:
   `bristlenose.app/docs/keyboard-shortcuts.html` (opened by `?` on both
   channels) still says "`j` / `↓` — Next quote", which is now false, and never
   mentions `←`/`→`. That page lives in the website deploy repo — it is an
   explicit hand-off, not something a later pass here will catch.
5. **Screen readers cannot perceive the cursor at all.** `.bn-focused` is a
   React state variable plus a CSS class; `document.activeElement` never moves,
   there is no roving `tabindex`, and `aria-activedescendant` appears nowhere in
   the frontend. Pre-existing, but the arrows lean on it much harder. Roving
   tabindex + `role="option"`/`aria-selected` would subsume this, the `Enter`
   collision with real controls, the WCAG 2.1.4 single-character-shortcut
   exposure, and the need to `announce()` cursor moves — four findings, one
   piece of work. Scheduled, not done.
6. ~~**The keyboard cursor is near-invisible in dark mode**~~ ✅ **fixed 5 Aug 2026.**
   The hoist this bullet prescribed is what shipped: the accent ring moved out
   of `templates/focus-mode.css` onto `blockquote.quote-card.bn-focused` in
   [`atoms/interactive.css`](../bristlenose/theme/atoms/interactive.css), so it
   applies to every `.bn-focused` in dark, not only inside Focus Mode —
   `box-shadow: var(--bn-focus-shadow), 0 0 0 1px light-dark(transparent,
   var(--bn-colour-accent))`. Light is unchanged (a transparent ring is a
   no-op) because there the background lift already reads.

   Two things the bullet didn't anticipate, both worth knowing here since this
   doc owns `.bn-focused`. The hoist **fixed a second bug**: at the Focus-scoped
   selector the ring scored (0,3,1) and out-specified
   `.bn-window-inactive blockquote.quote-card.bn-focused`, so it kept glowing on
   a background window; at (0,2,1) the inactive-window recede works again, and
   `test_cursor_ring_recedes_when_the_window_is_inactive` now fails any cursor
   rule carrying three or more classes. And the focused card **blanks its own
   left border** in dark (`border-left-color: light-dark(var(--bn-colour-border),
   transparent)`) so the 1px ring and the 1px `border-left` don't double up —
   which means focus now *pre-empts* the starred bracket and the playback edge
   rather than stacking with them.

   `--bn-focus-shadow` itself is still dark-variantless in both palettes; the
   ring makes that harmless for quote cards but not for any other surface that
   relies on the lift. Derivation and the four-cell contrast table:
   [`design-focus-mode.md`](design-focus-mode.md) § The keyboard cursor.

### Future considerations:
1. **Left-hand navigation** — will use page tint; keep page white for now
2. **Media player keyboard controls** — separate window, own shortcuts (space=play/pause, j/k/l=seek)

## Experiments

Visual experiments in `experiments/` directory:
- `focus-selection-styles.html` — initial explorations
- `focus-selection-styles-v2.html` — refined options
- `focus-selection-styles-v3.html` — **final design** with all 8 state combinations

Behaviour prototype in `docs/mockups/` (React-era; the three above predate the SPA):
- `quotes-spatial-arrow-nav.html` — spatial arrow navigation over a real `grid-lanes` grid, with
  **three scoring rules kept side by side** so the choice can be re-felt rather than re-derived:
  **line of sight** (remembered y held across consecutive horizontal moves — the text-editor goal
  column rotated 90°, reversible by construction), **nearest centre** (half-plane filter + distance
  sort, no lane detection, no state), and **max overlap** (adjacent lane, maximise perpendicular
  span overlap, topmost tiebreak). Tried 4 Aug 2026: **all three felt equivalent on the sample**, so
  nearest centre wins on parsimony. The drift that separates them is real but needs greater card-height
  variance to surface — the mockup's own commentary records the caveat and the symptom to watch for.

## Research Sources

Keyboard conventions researched across: Gmail, GitHub, Linear, Slack, VS Code, macOS Finder, Windows Explorer, Notion, Figma, Trello, Superhuman, Outlook, YouTube.

Key findings:
- j/k (Vim-style) adopted by keyboard-first web apps (Gmail, GitHub, Linear)
- Arrow keys universal fallback
- `/` for search is near-universal in web apps
- `?` for help is Gmail/GitHub convention
- `s` for star is Gmail's most iconic shortcut
- Enter = Open (not Edit) is dominant web convention
- Shadow lift for focus is elegant alternative to coloured rings
