# Keyboard Navigation — Design Document

Reference doc for keyboard shortcuts and focus system in the HTML report.

## Design Principles

1. **Leverage muscle memory** — use conventions from Gmail, GitHub, Linear (the apps researchers already use)
2. **Ring for focus, background for selection** — keep visual language extensible for future multi-select
3. **No focus is a valid state** — user must opt-in to keyboard navigation via click or keypress
4. **Focus is logical, not visual** — scrolling away doesn't lose focus; j/k resumes from where you were

## Terminology

**Starred** (not "favourites") — neutral annotation. A quote about your software being terrible is worth starring without it being a "favourite". Gmail muscle memory: `s` = star.

## Focus vs Selection

| Concept | Purpose | Visual | Count | Persistence |
|---------|---------|--------|-------|-------------|
| **Focus** | Keyboard target ("cursor") | Ring/outline | 0 or 1 | Session, survives scroll |
| **Selection** | Operand set for bulk actions | Background highlight | 0 to N | Session, cleared on nav |
| **Starred** | Persistent annotation | Star icon filled | 0 to N | localStorage |

Phase 1 implements focus only. Selection is future work.

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

## Visual Design

### Background Tint

Page background gets a very pale grey tint (`#f7f7f8` light / `#141414` dark). This allows focused/selected elements to appear "lifted" with white background.

```css
--bn-colour-background: light-dark(#f7f7f8, #141414);
--bn-colour-surface: light-dark(#ffffff, #1c1c1c);
```

### Focus Ring (not background)

Focus uses outline ring only — reserves background for future selection.

```css
blockquote.focused {
  box-shadow: 0 0 0 2px var(--bn-colour-accent);
  border-radius: 4px;
  /* no background change — that's for .selected */
}
```

### Future: Selection (multi-select)

```css
blockquote.selected {
  background: var(--bn-colour-surface);  /* white/lifted */
}

blockquote.focused.selected {
  background: var(--bn-colour-surface);
  box-shadow: 0 0 0 2px var(--bn-colour-accent);
}
```

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

## Implementation Phases

### Phase 1: Rename favourites → starred
- CSS class: `.favourited` → `.starred`
- JS: `favStore` → `starStore`, `initFavourites()` → `initStarred()`
- localStorage: migrate `bristlenose-favourites` → `bristlenose-starred`
- View switcher: "Favourite quotes" → "Starred quotes"
- Effort: ~1 hour

### Phase 2: Background tint
- Add `--bn-colour-background` token
- Apply to `body` or `article`
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
- `.focused` CSS class (ring only)
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
- `.selected` CSS class (background)
- `x` → toggle selection
- `Shift+j/k` → extend selection
- Bulk actions TBD

## Research Sources

Keyboard conventions researched across: Gmail, GitHub, Linear, Slack, VS Code, macOS Finder, Windows Explorer, Notion, Figma, Trello, Superhuman, Outlook, YouTube.

Key findings:
- j/k (Vim-style) adopted by keyboard-first web apps (Gmail, GitHub, Linear)
- Arrow keys universal fallback
- `/` for search is near-universal in web apps
- `?` for help is Gmail/GitHub convention
- `s` for star is Gmail's most iconic shortcut
- Enter = Open (not Edit) is dominant web convention
- Focus ring + selection background is standard two-tier visual model
