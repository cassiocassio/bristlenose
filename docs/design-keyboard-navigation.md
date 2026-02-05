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

| Key | Action | Notes |
|-----|--------|-------|
| `j` / `↓` | Focus next quote | From no-focus: focuses first visible |
| `k` / `↑` | Focus previous quote | From no-focus: focuses last visible |

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
| `Shift+j/k` | Extend selection | Moves focus and adds to selection |

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

**Known issue:** Dark mode selection highlight (`--bn-selection-bg: #1a2838`) is hard to see — needs a more visible variant.

## Outstanding Design Questions

### Still to confirm:
1. **Dark mode selection visibility** — current `#1a2838` is hard to see; needs brighter variant
2. **Help overlay styling** — simple modal vs more elaborate design
3. **Dropdown keyboard highlights** — should use same selection colour (`#eef4fc`)

### Future considerations:
1. **Left-hand navigation** — will use page tint; keep page white for now
2. **Media player keyboard controls** — separate window, own shortcuts (space=play/pause, j/k/l=seek)

## Experiments

Visual experiments in `experiments/` directory:
- `focus-selection-styles.html` — initial explorations
- `focus-selection-styles-v2.html` — refined options
- `focus-selection-styles-v3.html` — **final design** with all 8 state combinations

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
