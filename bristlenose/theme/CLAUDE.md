# Theme / Design System Context

## Atomic CSS architecture

Tokens → Atoms → Molecules → Organisms → Templates. All visual values via `--bn-*` custom properties in `tokens.css`, never hard-coded. `render_html.py` concatenates files in order defined by `_THEME_FILES`.

## Dark mode

Uses CSS `light-dark()` function (supported in all major browsers since mid-2024, ~87%+ global). No JS involved. The cascade:

1. **OS/browser preference** → `color-scheme: light dark` on `:root` respects `prefers-color-scheme` automatically
2. **User override** → `color_scheme` in `bristlenose.toml` (or `BRISTLENOSE_COLOR_SCHEME` env var). Values: `"auto"` (default), `"light"`, `"dark"`
3. **HTML attribute** → when config is `"light"` or `"dark"`, `render_html.py` emits `<html data-theme="light|dark">` which forces `color-scheme` via CSS selector
4. **Print** → always light (forced by `color-scheme: light` in `print.css`)

### How tokens work

`tokens.css` has two blocks:
- `:root { --bn-colour-bg: #ffffff; ... }` — plain light values (fallback for old browsers)
- `@supports (color: light-dark(...)) { :root { --bn-colour-bg: light-dark(#ffffff, #111111); ... } }` — modern browsers get both values, resolved by `color-scheme`

### Adding a new colour token

Add both light and dark values in the `light-dark()` call inside the `@supports` block, and the plain light fallback in the `:root` block above it.

### Logo

The `<picture>` element swaps between `bristlenose-logo.png` (light) and `bristlenose-logo-dark.png` (dark) using `<source media="(prefers-color-scheme: dark)">`. Dark logo is currently a placeholder (inverted version) — needs replacing with a proper albino bristlenose pleco image.

### No JS theme toggle

Dark mode is CSS-only. No localStorage, no toggle button, no JS involved.

## Template CSS files

Template-level CSS in `templates/`: `report.css` (main report layout), `transcript.css` (per-participant transcript pages — back button, segment layout, meta styling), `print.css` (print overrides, hides interactive elements). Quote attribution links styled via `.speaker-link` in `organisms/blockquote.css` (inherits muted colour from `.speaker`, accent on hover).

## JS modules

9 standalone files in `js/` concatenated at render time (same pattern as CSS): storage, player, favourites, editing, tags, histogram, csv-export, names, main. Transcript pages use only `storage.js` + `player.js` (no favourites/editing/tags/names).

### names.js

Inline name editing for the participant table. Follows the same `contenteditable` lifecycle as `editing.js` (start → accept/cancel → persist).

- **Store**: `createStore('bristlenose-names')` — shape `{pid: {full_name, short_name, role}}`
- **Edit flow**: pencil icon on hover → click makes cell `contenteditable` → Enter/click-outside saves, Escape cancels
- **Auto-suggest**: `suggestShortName(fullName, allNames)` mirrors the Python heuristic — first name, disambiguate collisions with last-name initial ("Sarah J.")
- **DOM updates**: `updateAllReferences(pid)` propagates name changes to quote attributions (`.speaker-link`) and participant table cells
- **Reconciliation**: `reconcileWithBaked()` prunes localStorage entries that match `BN_PARTICIPANTS` (baked-in JSON from render time) — after user pastes edits into `people.yaml` and re-renders, browser state auto-cleans
- **Export**: "Export names" toolbar button copies a YAML snippet via `copyToClipboard()` + `showToast()` (from `csv-export.js`)
- **Dependencies**: must load after `csv-export.js` (needs `showToast`, `copyToClipboard`) and before `main.js` (boot calls `initNames()`)
- **Data source**: `BN_PARTICIPANTS` global — JSON object `{pid: {full_name, short_name, role}}` emitted by `render_html.py` in a `<script>` block

### Inline heading/description editing

Section titles, descriptions, theme titles, and theme descriptions use `.editable-text` spans with pencil icons for inline editing. Handled by `initInlineEditing()` in `editing.js` (same file as quote editing, separate state tracker).

- **`.edit-pencil-inline`** in `atoms/button.css` — overrides `.edit-pencil` absolute positioning with `position: static; display: inline` for flow-inline placement after text
- **`.editable-text.editing`** in `molecules/quote-actions.css` — editing highlight (same visual as `.quote-text` editing)
- **`.editable-text.edited`** in `molecules/quote-actions.css` — dashed underline indicator for changed text
- **Bidirectional ToC sync** — ToC entries and section headings share the same `data-edit-key`; `_syncSiblings()` keeps all matching spans in sync on edit

### name-edit.css (molecule)

Styles for participant name inline editing: `.name-cell` / `.role-cell` positioning, `.name-pencil` (opacity 0 → 1 on row hover), editing state background, `.edited` dashed-underline indicator, `.unnamed` muted italic placeholder. Print-hidden.
