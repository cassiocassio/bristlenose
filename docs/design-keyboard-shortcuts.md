# Design: Platform-Aware Keyboard Shortcuts & Discoverability

**Status:** Phase 1–2 shipped, Phase 3 future
**Date:** 13 Mar 2026

## Problem

The keyboard shortcuts help modal (`HelpModal.tsx`) hardcodes Mac-style symbols (`⌘`, `Shift` spelled out with `+` separator) regardless of the user's platform. This looks wrong on Windows and Linux. More broadly, shortcuts are only discoverable if the user happens to press `?` — there's no tooltip layer on toolbar buttons and no progressive disclosure system.

Three related problems:

1. **Platform display** — wrong symbols on non-Mac platforms
2. **Discoverability** — no tooltips on actionable UI elements
3. **Help modal polish** — missing close button, unstyled separators, no visual polish

## Platform display conventions

### Sources

- [Apple Style Guide — key, keys](https://support.apple.com/guide/applestyleguide/k-apsgf9067ae8/web) — official Apple documentation rules
- [Gruber — Modifier Key Order for Keyboard Shortcuts](https://daringfireball.net/2026/03/modifier_key_order_for_keyboard_shortcuts) — glyphs have no hyphens, words have hyphens
- [Microsoft Style Guide — Keys and keyboard shortcuts](https://learn.microsoft.com/en-us/style-guide/a-z-word-list-term-collections/term-collections/keys-keyboard-shortcuts) — official Microsoft documentation rules
- [GNOME HIG — Keyboard shortcuts](https://developer.gnome.org/hig/reference/keyboard.html) — GNOME desktop conventions
- [Knock.app — How to design great keyboard shortcuts](https://knock.app/blog/how-to-design-great-keyboard-shortcuts) — cross-platform web app best practices

### macOS (Apple Style Guide + Gruber)

**Modifier order:** Fn → Control → Option → Shift → Command

**Symbols (Unicode glyphs):**

| Modifier | Symbol | Unicode |
|----------|--------|---------|
| Control  | ⌃      | U+2303  |
| Option   | ⌥      | U+2325  |
| Shift    | ⇧      | U+21E7  |
| Command  | ⌘      | U+2318  |

**Separator:** None when using glyphs. Glyphs concatenate directly: `⌘C`, `⇧⌘S`, `⌃⌥⇧⌘Q`. Apple menus have displayed shortcuts this way since 1984. Using a hyphen or plus sign between glyphs is incorrect (Gruber is emphatic about this).

**With words** (prose context): hyphens between names: `Command-R`, `Control-Shift-N`. But in compact UI (menus, help modals, tooltips), always use glyphs.

### Windows (Microsoft Style Guide)

**Modifier order:** Windows logo → Ctrl → Alt → Shift

**Labels:** Text names, sentence-cased: `Ctrl`, `Alt`, `Shift`, `Esc`

**Separator:** Plus sign, no spaces: `Ctrl+S`, `Ctrl+Shift+?`, `Alt+F4`

**Special characters:** Always spell out `Plus sign`, `Minus sign`, `Hyphen`, `Period`, `Comma` when they are the target key in a combination (to avoid confusion with the separator). In compact UI (like our help modal) the symbol itself is clear enough in context.

### Linux (GNOME HIG)

**Modifier order:** Super → Ctrl → Alt → Shift

**Labels:** Text names: `Ctrl`, `Alt`, `Shift`, `Super`

**Separator:** Plus sign: `Ctrl+S`, `Super+Tab`

Linux follows Windows conventions for text shortcuts. The only difference is "Super" instead of "Windows logo key" — but Bristlenose has no Super/Windows shortcuts, so Linux and Windows share an identical display path.

### Decision: two display paths

Mac vs non-Mac (Windows + Linux). Binary detection. They share:
- Single-letter keys: identical (`j`, `x`, `s`, `?`)
- Arrow keys: identical (`↓`, `↑`)
- Named keys: identical (`Enter`, `Esc`)

They differ only on modifier display:

| Modifier | Mac | Non-Mac |
|----------|-----|---------|
| Shift    | `⇧` (glyph, no separator) | `Shift+` (text, plus separator) |
| Command/Ctrl | `⌘` (glyph, no separator) | `Ctrl+` (text, plus separator) |

## Platform detection

```typescript
// frontend/src/utils/platform.ts
let _isMac: boolean | null = null;

export function isMac(): boolean {
  if (_isMac === null) {
    const uad = (navigator as any).userAgentData;
    if (uad?.platform) {
      _isMac = /mac/i.test(uad.platform);
    } else {
      _isMac = /Mac/.test(navigator.platform);
    }
  }
  return _isMac;
}

export function _resetPlatformCache(): void {
  _isMac = null;
}
```

- `navigator.userAgentData.platform` — modern Chromium API (93+). Not available in Safari or Firefox yet. Case-insensitive match for `"macOS"`
- `navigator.platform` — deprecated but universally supported fallback. Case-sensitive match for `"Mac"` prefix (values: `"MacIntel"`, `"MacPPC"`, `"Mac68K"`)
- Memoised: platform doesn't change mid-session
- `_resetPlatformCache()` — test-only export (underscore convention) for mocking in tests
- No SSR concern — Bristlenose is a client-only SPA

## Bristlenose shortcut mapping

Every shortcut in the help modal, with platform-specific display:

| Action | Mac display | Windows/Linux display | Key handler |
|--------|------------|----------------------|-------------|
| Next quote | `j` / `↓` | `j` / `↓` | `j` / `ArrowDown` |
| Previous quote | `k` / `↑` | `k` / `↑` | `k` / `ArrowUp` |
| Toggle select | `x` | `x` | `x` |
| Extend selection | `⇧J` / `⇧K` | `Shift+J` / `Shift+K` | `Shift+j` / `Shift+k` |
| Star | `s` | `s` | `s` |
| Hide | `h` | `h` | `h` |
| Add tag | `t` | `t` | `t` |
| Repeat last tag | `r` | `r` | `r` |
| Play in video | `Enter` | `Enter` | `Enter` |
| Toggle contents | `[` | `[` | `[` |
| Toggle tags | `]` | `]` | `]` |
| Toggle both | `\` | `\` | `\` |
| Toggle both (alt) | `⌘.` | `Ctrl+.` | `metaKey`/`ctrlKey` + `.` |
| Search | `/` | `/` | `/` |
| This help | `?` | `?` | `?` |
| Close / clear | `Esc` | `Esc` | `Escape` |

The key handler (`useKeyboardShortcuts.ts`) already handles both `e.metaKey` (Mac) and `e.ctrlKey` (non-Mac) for the `⌘.` / `Ctrl+.` shortcut. No handler changes needed — this is purely a display concern.

## Rendering approach

### Mac: single `<kbd>` for modifier+key

```html
<kbd>⇧J</kbd>     <!-- Shift+J -->
<kbd>⌘.</kbd>      <!-- Cmd+. -->
```

Modifier glyph and key concatenated in one element, no separator. Matches macOS menu bar rendering. Visually compact.

### Non-Mac: separate `<kbd>` elements with `+` separator

```html
<kbd>Shift</kbd><span class="help-key-sep">+</span><kbd>J</kbd>
<kbd>Ctrl</kbd><span class="help-key-sep">+</span><kbd>.</kbd>
```

Text modifier labels with `+` separator. Matches Microsoft Style Guide. The `+` is a `<span>` (not `<kbd>`) because it's a separator, not a key.

### Uppercase convention

Keys shown with a modifier are uppercased: `⇧J` not `⇧j`, `Shift+J` not `Shift+j`. Standalone keys stay lowercase: `j`, `k`, `x`. This matches VS Code, Figma, Slack, and macOS menus — you're physically pressing Shift+J, so the display reflects that.

## Custom tooltips (Phase 3 — future)

### Why non-native

The browser's native `title` attribute is inadequate:
- **Delay**: ~500ms hover delay, not configurable
- **No styling**: plain text, OS-rendered, can't include `<kbd>` badges
- **No keyboard trigger**: only hover, not focus
- **No positioning control**: OS decides placement
- **Accessibility**: screen readers read `title` but the visual tooltip is unreliable

### Vision

A custom `<Tooltip>` React component that:

1. **Shows shortcut badges**: `Star s` with a styled `<kbd>s</kbd>` inline
2. **Hover intent**: ~200ms enter delay (avoid flicker on mouse traverse), immediate close on leave
3. **Positioning**: auto-flip (prefers above, flips below if viewport clipped). Floating UI or hand-rolled with `getBoundingClientRect()` — TBD based on complexity
4. **Accessible**: `aria-describedby` linking trigger to tooltip content. Shows on focus-visible too (keyboard users)
5. **Styled**: matches the `<kbd>` badge styling from the help modal. Muted background, subtle shadow, 0.75rem mono font for keys

### Candidate placements

Toolbar buttons and nav elements that have shortcuts:

| Element | Tooltip content | Shortcut |
|---------|----------------|----------|
| Search icon/input | Search quotes | `/` |
| Star button | Star quote | `s` |
| Hide button | Hide quote | `h` |
| Tag button | Add tag | `t` |
| Help `?` in footer | Keyboard shortcuts | `?` |
| TOC rail button | Table of contents | `[` |
| Tags rail button | Tags sidebar | `]` |

### Implementation options

1. **Hand-rolled**: `useTooltip()` hook + `<TooltipPortal>`. Minimal dependencies, full control. Follows our existing pattern (headless hooks like `useDropdown()`, `useDragResize()`). Positioning via `getBoundingClientRect()` + viewport clamp
2. **Floating UI** (`@floating-ui/react`): battle-tested positioning engine, ~3KB. Handles edge cases (scroll containers, viewport overflow, arrow positioning). We'd still write our own component/hook on top
3. **Radix Tooltip** (`@radix-ui/react-tooltip`): complete accessible tooltip with animations. ~8KB. Heavier, more opinionated, but handles everything including animation exit

**Recommended**: option 1 (hand-rolled) for now. Our existing hooks (`useDropdown`, `useTocOverlay`) prove we can handle hover intent and positioning. If viewport-edge cases get hairy, graduate to Floating UI. Radix is overkill for our needs.

### Tooltip component API sketch

```tsx
<Tooltip content="Star quote" shortcut={{ keys: ["s"] }}>
  <button className="star-btn">...</button>
</Tooltip>

<Tooltip content="Toggle both sidebars" shortcut={{ keys: ["."], modifier: "cmd" }}>
  <button className="sidebar-toggle">...</button>
</Tooltip>
```

The `shortcut` prop uses the same `KeyDef` type as the help modal, so platform rendering is shared. The `content` prop is the descriptive text. Both render inside the tooltip bubble.

## Help modal visual redesign (Phase 2 — ready to build)

Phase 1 shipped close button, `.help-key-sep` CSS, and platform-aware key rendering. The modal is functional but the visual treatment is plain compared to other modals (feedback, autocode report) which have refined spacing, entrance animations, and considered typography.

### Current state

What works:
- Three-column grid layout with responsive collapse at 500px
- `<kbd>` badge styling (mono font, border, shadow, badge-bg)
- Close `×` button (`.bn-modal-close` from `atoms/modal.css`)
- `.help-key-sep` styled (muted colour, tight padding)
- Platform-aware key display (Mac glyphs vs Windows/Linux text labels)

What needs polish:
- **Typography inconsistency** — section headings use hardcoded `0.75rem`, descriptions use `0.875rem`. Should migrate to `--bn-text-caption` / `--bn-text-body-sm` tokens for consistency with the design system
- **Cramped vertical rhythm** — the `dl` grid has `gap: var(--bn-space-xs)` (2.4px) row gap which packs shortcuts tight. Other modals use `var(--bn-space-sm)` (5.6px) minimum
- **No section dividers** — sections flow into each other with only the uppercase heading as separation. A subtle bottom border or extra bottom margin on each `.help-section` would help scanning
- **Heading lacks breathing room** — `h2` has `font-size: 1.25rem` but no bottom padding before the grid starts; the first column's `h3` feels immediately abutted
- **No entrance animation** — the overlay fades in (`var(--bn-transition-normal)`) but the card itself has no scale or translate animation. The feedback modal doesn't either, but the tooltip pattern uses a subtle `translateY(-8px) → 0` float-down that could elevate the help modal's feel
- **`<kbd>` sizing** — keys are `0.75rem` which is correct for inline badges, but for the help modal (where `<kbd>` elements are the primary content, not inline annotations), slightly larger keys (0.82rem) would improve readability
- **Dark mode contrast** — `--bn-colour-badge-bg` works but the `box-shadow: 0 1px 0 var(--bn-colour-border)` on `<kbd>` is barely visible in dark mode. Could strengthen to `0 1px 0 0.5px` or use a slightly lighter border colour
- **3-column grid with 4 sections** — Navigation + Selection + Actions fill 3 columns; Global wraps to a second row alone, looking orphaned. Options: (a) merge into 2 wider columns, (b) rebalance content so Global isn't alone, (c) accept it

### Design direction

**Conservative polish, not a redesign.** The layout is correct; the three-column `dl` grid is information-dense in a good way. Changes should refine spacing, typography tokens, and add one visual flourish (entrance animation), not restructure.

### Scope

#### Typography token migration

Replace hardcoded font sizes with design system tokens:

| Element | Current | Target |
|---------|---------|--------|
| `.help-section h3` | `font-size: 0.75rem` | `font-size: var(--bn-text-caption)` |
| `.help-section dd` | `font-size: 0.875rem` | `font-size: var(--bn-text-body)` |
| `.help-modal h2` | `font-size: 1.25rem` | Keep (no matching token — between heading 1.125rem and title 1.375rem) |
| `.help-modal kbd` | `font-size: 0.75rem` | `font-size: var(--bn-text-caption)` |

#### Spacing refinement

| Element | Current | Target | Rationale |
|---------|---------|--------|-----------|
| `.help-section dl` row gap | `var(--bn-space-xs)` (2.4px) | `var(--bn-space-sm)` (5.6px) | Less cramped, easier to scan |
| `.help-section` | No bottom margin | `margin-bottom: var(--bn-space-md)` (12px) | Section breathing room |
| `.help-section:last-child` | — | `margin-bottom: 0` | No trailing space |
| `.help-columns` gap | `var(--bn-space-lg)` (24px) | Keep — already generous |
| `.help-modal h2` | `margin: 0 0 var(--bn-space-lg)` (inherited from `.bn-modal h2`) | Keep |

#### Card entrance animation

Subtle scale-up on open, matching the overlay's fade:

```css
.help-modal {
    transform: scale(0.97);
    opacity: 0;
    transition: transform var(--bn-transition-normal), opacity var(--bn-transition-normal);
}

.help-overlay.visible .help-modal {
    transform: scale(1);
    opacity: 1;
}
```

97% → 100% scale is barely perceptible but adds life. `var(--bn-transition-normal)` (0.2s ease) matches the overlay fade timing.

Note: this only affects the CSS. The React `HelpModal` component already conditionally renders (`if (!open) return null`), so the CSS transition needs the overlay wrapper to exist in the DOM before the `.visible` class is added. Currently the component unmounts entirely when closed, meaning CSS transitions won't play. **Two options:**

1. **Always render the overlay** (change `if (!open) return null` to conditionally apply `.visible` class). This is how the vanilla JS modals work — the DOM is always present, `.visible` toggles visibility. Cost: the help modal DOM stays in the tree while invisible
2. **Keep current unmount** and skip the CSS entrance animation. The overlay fade still works because it's on the wrapper div. The card just appears instantly (no scale transition)

**Recommended: option 1.** The help modal is a small DOM tree (~30 elements). Always-present-but-invisible matches the pattern used by `createModal()` in `modal.js` and avoids the unmount/remount flash.

#### Dark mode `<kbd>` refinement

Strengthen the bottom shadow in dark mode only:

```css
@supports (color: light-dark(black, white)) {
    .help-modal kbd {
        box-shadow: 0 1px 0 light-dark(var(--bn-colour-border), rgba(255,255,255,0.1));
    }
}
```

This keeps the current light mode shadow but gives dark mode a slightly more visible bottom edge.

### Files

| File | Action | Description |
|------|--------|-------------|
| `bristlenose/theme/molecules/help-overlay.css` | Modify | Token migration, spacing, entrance animation, dark mode kbd |
| `frontend/src/components/HelpModal.tsx` | Modify | Always-render pattern (remove `if (!open) return null`, use class toggle) |
| `frontend/src/components/HelpModal.test.tsx` | Modify | Update tests for always-rendered DOM |

### Non-goals

- Restructuring the 3-column grid to 2 columns (if the orphaned Global row is annoying, revisit later)
- Adding section icons (adds complexity for marginal visual value)
- "Shortcuts you've used" highlighting (requires tracking shortcut usage in a store — Phase 4 idea)

## Implementation phases

### Phase 1: Platform-aware display (shipped)

`isMac()` utility, `KeyCombo` data model, platform-conditional rendering (Mac glyphs vs Windows/Linux text labels), `.help-key-sep` + `.help-key-group` CSS, 26 tests.

### Phase 2: Help modal visual polish (shipped)

Typography token migration, spacing refinement, card entrance animation (always-render pattern), dark mode `<kbd>` shadow fix. See "Help modal visual redesign" section above for full spec. Always-render pattern: overlay DOM stays in tree with `visibility: hidden`; `.visible` class toggles visibility + entrance animation (scale 0.97→1 + fade). `aria-hidden` tracks open state.

### Phase 3: Custom tooltips

- `<Tooltip>` component + `useTooltip()` hook
- Toolbar/nav shortcut annotations
- Depends on Phase 1 (shares platform detection + `KeyDef` types)

## File map

```
frontend/src/
  utils/
    platform.ts          ← Phase 1: isMac() detection (shipped)
    platform.test.ts     ← Phase 1: tests (shipped)
  components/
    HelpModal.tsx        ← Phase 1–2 shipped: always-render pattern, class toggle
    HelpModal.test.tsx   ← Phase 1–2 shipped: updated for always-render
    Tooltip.tsx          ← FUTURE (Phase 3)
  hooks/
    useKeyboardShortcuts.ts  ← NO CHANGE (already cross-platform)
    useTooltip.ts        ← FUTURE (Phase 3)

bristlenose/theme/
  molecules/
    help-overlay.css     ← Phase 1–2 shipped: tokens, spacing, animation, dark kbd
  atoms/
    tooltip.css          ← FUTURE (Phase 3)
```
