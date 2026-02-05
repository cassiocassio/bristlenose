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
| `Enter` | Open transcript | At quote's timecode anchor |
| `Space` | Play in video player | Opens/seeks popup |

### Global (no focus needed)

| Key | Action | Notes |
|-----|--------|-------|
| `/` | Focus search input | Near-universal (Gmail, GitHub, Slack) |
| `?` | Help overlay | Gmail, GitHub convention |
| `Escape` | Close/clear/unfocus | Context-dependent |

### Rejected/Deferred

| Key | Reason |
|-----|--------|
| `e` (edit) | Not obvious; pencil icon is discoverable |
| `v` (view cycle) | Toolbar territory |
| `c` (copy CSV) | Toolbar territory |
| `x` (toggle select) | Future: multi-select |
| `Shift+j/k` | Future: extend selection |

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

Navigation
  j / ↓    Next quote
  k / ↑    Previous quote

Actions
  s        Star quote
  t        Add tag
  Enter    View in transcript
  Space    Play in video

Global
  /        Search
  ?        This help
  Esc      Close / clear
```

Future: Expand to include feature explanations (tags, starring, CSV export).

## Implementation Phases

### Phase 1: Rename favourites → starred ✅ READY TO IMPLEMENT
- CSS class: `.favourited` → `.starred`
- JS: `favStore` → `starStore`, `initFavourites()` → `initStarred()`, `favourites.js` → `starred.js`
- localStorage: migrate `bristlenose-favourites` → `bristlenose-starred`
- View switcher: "Favourite quotes" → "Starred quotes"
- Token: `--bn-colour-favourited` → `--bn-colour-starred`
- Effort: ~1 hour

### Phase 2: Add focus/selection CSS tokens
- Add `--bn-focus-shadow` and `--bn-selection-bg` to `tokens.css`
- Create `atoms/interactive.css` with `.bn-focused` and `.bn-selected` classes
- Effort: ~30 minutes

### Phase 3: Global shortcuts
- New module: `keyboard.js`
- `isEditing()` guard function
- `/` → focus search
- `?` → help overlay
- `Escape` → close help, clear search
- Effort: ~2 hours

### Phase 4: Focus system
- `focusedQuoteId` state
- `.focused` CSS class (shadow lift)
- `j`/`k`/arrow handlers
- Click to focus, Escape/background-click to blur
- Scroll-into-view on focus change
- Effort: ~3 hours

### Phase 5: Actions on focused quote
- `s` → toggle star
- `t` → open tag input
- `Enter` → navigate to transcript
- `Space` → open video player
- Effort: ~2 hours

### Future: Multi-select
- `selectedQuoteIds: Set<string>`
- `.selected` CSS class (light blue bg + blue bar)
- `x` → toggle selection
- `Shift+j/k` → extend selection
- Bulk actions TBD

## Outstanding Design Questions

### Still to confirm:
1. **Dark mode colours** for selection bg — proposed `#1a2332` but needs testing
2. **Help overlay styling** — simple modal vs more elaborate design
3. **Dropdown keyboard highlights** — should use same selection colour (`#f5f9ff`)

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
