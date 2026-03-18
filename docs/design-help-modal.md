# Help Modal

> **Status:** in progress — Settings modal landed (commit `2f530cf`), blocker cleared.
> ModalNav genericised into a reusable design system organism.

_Last updated: 18 Mar 2026_

---

## Why

The current About page (`/report/about/`) is a full-page tab that wastes a
route on reference material. It also separates keyboard shortcuts (the `?`
HelpModal) from product documentation (the About page) into two unrelated
surfaces. Researchers who open their first analysis need a single place that
teaches them how to read and use the output — not a feature catalogue and a
disconnected shortcut overlay.

## Design

A **Help modal** triggered by the navbar info icon (ⓘ), rendered as a modal
overlay using `ModalNav` — the same two-column sidebar-nav shell that Settings
uses.

### Navigation structure

```
Help          ← default landing (core concepts, how to use the analysis)
Shortcuts     ← keyboard shortcuts (absorbs old HelpModal grid)
Signals       ← sentiment taxonomy, academic foundations
Codebook      ← qualitative coding methodology, framework codebooks
▸ About       ← disclosure group — "how it was made" (classic About box)
  Developer   ← architecture, stack, APIs, dev tools
  Design      ← design system, dark mode, component library, mockups
  Contributing← licence, CLA, links
```

### Help section (landing)

This is the first thing a researcher reads after their first analysis run.
**Not a feature list** — teaches how to read and interpret:

- What sections and themes mean
- How sentiment tagging works
- What signals tell you and how to read the analysis grid
- How to use stars, tags, filters to build findings
- How to export

Stubbed with headings initially; prose content written in a separate pass.

### Shortcuts section

Absorbs the existing `HelpModal.tsx` keyboard shortcut grid (4 groups:
Navigation, Selection, Actions, Global) with platform-aware kbd badges
(⌘ on Mac, Ctrl on Windows).

The `?` keyboard shortcut opens the Help modal pre-navigated to Shortcuts.
The navbar icon opens to Help (default).

### Signals and Codebook

The more academic/reference material. Already written — can be refined later.

### About disclosure group

In the classic tradition of the Photoshop About box — "how it was made" info.
Same disclosure-triangle pattern as Config in Settings:

- **Developer** — architecture, stack, APIs, dev tools (DB path, endpoints
  conditionally rendered when `devInfo` present)
- **Design** — design system, dark mode, component library, mockups
  (mockup links conditionally rendered when `devInfo` present)
- **Contributing** — AGPL-3.0, CLA, contributing guide link, bug report link

---

## Design system: ModalNav as organism

### Atomic layer placement

ModalNav is an **organism** — it composes atoms (`.bn-overlay`, `.bn-modal`,
`.bn-modal-close`) into a complex two-column layout with internal state
(disclosure groups, focus trap, responsive dropdown). This follows the existing
hierarchy where organisms are "complex compositions" (Sidebar, Codebook,
Analysis grid).

### CSS file structure

| Layer | File | Contents |
|-------|------|----------|
| **Atom** | `atoms/modal.css` | `.bn-overlay`, `.bn-modal`, `.bn-modal-close` (no changes) |
| **Organism** | `organisms/modal-nav.css` | `.modal-nav-shell`, all `.modal-nav-*` layout classes, `.modal-nav-overlay` transition |
| **Organism** | `organisms/settings-modal.css` | `.settings-modal` sizing only |
| **Molecule** | `molecules/help-overlay.css` | `.help-columns`, `.help-section`, kbd styles — shortcuts content only |

### Parameterised sizing

`modal-nav.css` provides the **generic shell** (`.modal-nav-shell` — flex
column, no padding, overflow hidden). Each consumer applies its own **sizing
class** on the same element:

- `.settings-modal { max-width: 42rem; height: min(32rem, 80vh); }`
- `.help-modal { max-width: 42rem; height: min(36rem, 85vh); }` — slightly
  taller for reference content
- Future modals add their own class — no changes to the organism

The `ModalNav` React component always adds `.modal-nav-shell`. The consumer
passes `className="settings-modal"` or `className="help-modal"` which stacks
on top. The overlay always uses `.modal-nav-overlay` for the shared transition.

### Transition pattern

```css
.modal-nav-overlay .modal-nav-shell {
    transform: scale(0.97); opacity: 0;
    transition: transform 0.2s ease-out, opacity 0.2s ease-out;
}
.modal-nav-overlay.visible .modal-nav-shell {
    transform: scale(1); opacity: 1;
}
```

Shared by all ModalNav modals — no per-consumer duplication.

---

## Accessibility fixes (from UX review)

1. **Unique `titleId` per modal** — `id="modal-nav-title"` is shared when both
   Settings and Help are in the DOM. Add `titleId` prop to ModalNav; each
   consumer passes a unique value (e.g. `"settings-modal-title"`,
   `"help-modal-title"`). `aria-labelledby` uses this ID.

2. **Remove `role="navigation"` from `<ul>`** — the parent `<nav>` already
   provides the navigation landmark. The `<ul>` should be a plain list.

3. **Focus trap, Escape close, focus restore** — already implemented in
   ModalNav. No changes needed.

4. **Responsive dropdown** — `<select>` with `<optgroup>` for disclosure
   children at ≤500px. Already accessible.

---

## Implementation

### Component: `HelpModal.tsx`

Replaces the existing simple keyboard-shortcut `HelpModal.tsx` with a
ModalNav-based version.

```tsx
const NAV_ITEMS: NavItem[] = [
  { id: "help", label: "Help" },
  { id: "shortcuts", label: "Shortcuts" },
  { id: "signals", label: "Signals" },
  { id: "codebook", label: "Codebook" },
  { id: "about", label: "About", children: [
    { id: "developer", label: "Developer" },
    { id: "design", label: "Design" },
    { id: "contributing", label: "Contributing" },
  ]},
];
```

Props: `open`, `onClose`, `initialSection?: string` (defaults to `"help"`;
`?` shortcut passes `"shortcuts"`), `health: HealthResponse` (passed from
AppLayout — not re-fetched).

Resets `activeId` to `initialSection` on each open (false→true transition).
Lazy-fetches `/api/dev/info` on first open only.

### Section components

Already extracted into `frontend/src/components/about/`:

| File | Content | Notes |
|------|---------|-------|
| `HelpSection.tsx` | Researcher guide | **New** (stub, headings only) |
| `ShortcutsSection.tsx` | Keyboard grid | **New** (extracted from old `HelpModal.tsx`) |
| `AboutSection.tsx` | Product guide | **Deprecated** (kept for legacy island) |
| `SignalsSection.tsx` | Sentiment taxonomy + citations | As-is |
| `CodebookSection.tsx` | Coding methodology | As-is |
| `DeveloperSection.tsx` | Architecture, stack, dev tools | As-is |
| `DesignSection.tsx` | Design system, mockups | As-is |
| `ContributingSection.tsx` | Licence, CLA, links | As-is (complete) |
| `types.ts` | Shared interfaces | As-is |
| `index.ts` | Barrel export | Updated |

### NavBar change

Change the About info icon from `<NavLink to="/report/about/">` to a
`<button>` with `onHelp` callback. Same pattern as Export and Settings buttons.

### AppLayout wiring

- Add `helpSection` state (`"help"` | `"shortcuts"`)
- Navbar `onHelp` → opens to `"help"`; `?` shortcut → opens to `"shortcuts"`
- Pass `initialSection`, `health` to `<HelpModal>`
- `health` already fetched on mount — no duplicate request

### Route removal

- Replace `{ path: "about" }` with `<Navigate to="/report/" replace />` —
  graceful redirect for bookmarks (not a silent 404)
- Delete `AboutTab.tsx`
- Keep `AboutPanel.tsx` for legacy island mount with `@deprecated` comment

### CSS changes

**`help-overlay.css`** — remove layout/transition rules replaced by ModalNav:
- Remove `.help-modal { max-width; transform; transition }` and
  `.help-overlay.visible .help-modal { ... }` and `.help-modal h2 { ... }`
- Keep: `.help-columns`, `.help-section`, `.help-key-*`, `.help-modal kbd`

### Tests

- Rewrite `HelpModal.test.tsx` — modal lifecycle, section nav, disclosure,
  initial section, escape, overlay click, kbd rendering, unique ARIA IDs
- Update `NavBar.test.tsx` — button not NavLink
- Update `router.test.tsx` — `/report/about/` redirects

---

## File map

| File | Action |
|------|--------|
| `bristlenose/theme/organisms/modal-nav.css` | **New** — generic organism |
| `bristlenose/theme/organisms/settings-modal.css` | Reduced to sizing |
| `bristlenose/theme/molecules/help-overlay.css` | Trimmed to content styles |
| `bristlenose/stages/s12_render/theme_assets.py` | Add `modal-nav.css` |
| `frontend/src/components/ModalNav.tsx` | Generic overlay, `titleId`, ARIA fix |
| `frontend/src/components/SettingsModal.tsx` | Minor (verify) |
| `frontend/src/components/HelpModal.tsx` | Rewrite |
| `frontend/src/components/about/ShortcutsSection.tsx` | **New** |
| `frontend/src/components/about/HelpSection.tsx` | **New** (stub) |
| `frontend/src/components/about/index.ts` | Updated exports |
| `frontend/src/components/NavBar.tsx` | Button |
| `frontend/src/layouts/AppLayout.tsx` | Wiring |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | Minor |
| `frontend/src/router.tsx` | Redirect |
| `frontend/src/pages/AboutTab.tsx` | Delete |
| `frontend/src/components/HelpModal.test.tsx` | Rewrite |
| `frontend/src/components/NavBar.test.tsx` | Update |

## Verification

1. `npm run build` — no type errors
2. `npm test` — all tests pass
3. `bristlenose serve --dev` — click ⓘ → Help modal with all sections
4. Press `?` → opens to Shortcuts section
5. Escape closes, Tab traps focus, responsive dropdown at ≤500px
6. "About" disclosure group expands to show Developer/Design/Contributing
7. `/report/about/` URL → redirects to `/report/` (not 404)
8. Settings modal still works (gear icon + ⌘,)
9. Both modals have unique `aria-labelledby` IDs
10. `cd e2e && npm test` — E2E tests pass
