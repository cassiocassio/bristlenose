# CSS Component Reference

Per-component documentation for the theme CSS files. Read this when modifying specific CSS components. For the overall design system architecture (tokens, dark mode, atomic layers), see `CLAUDE.md` in this directory.

## Toolbar button styling

All toolbar controls use the shared `.toolbar-btn` round-rect atom from `atoms/button.css`. Controls with additional behaviour (dropdowns, toggles) use dual classes:

- Codebook: `class="toolbar-btn"` (plain)
- Tag filter: `class="toolbar-btn tag-filter-btn"` (dropdown)
- View switcher: `class="toolbar-btn view-switcher-btn"` (dropdown)
- Copy CSV: `class="toolbar-btn"` (plain)

Shared child elements: `.toolbar-icon-svg` (SVG icon), `.toolbar-arrow` (dropdown chevron). Three-state border: rest (`--bn-colour-border`) → hover (`--bn-colour-border-hover`) → active (`--bn-colour-accent`).

**Design rationale**: the dual-class pattern keeps the base button visual consistent across all toolbar controls while allowing dropdown-specific overrides (arrow positioning, active states) without class name collisions.

## search.css (molecule)

Collapsible search filter in the toolbar. Designed to be unobtrusive when inactive (just a magnifying glass icon) and expand inline when clicked, keeping the researcher's focus on the report content.

`.search-container` (flex, `margin-right: auto` for left alignment), `.search-toggle` (muted icon, accent on hover), `.search-field` (relative wrapper, hidden until `.expanded`), `.search-input` (right padding for clear button), `.search-clear` (absolute right inside field, hidden until `.has-query`, muted ×, accent on hover). `.search-mark` (highlight background via `--bn-colour-highlight`, 2px radius).

## tag-filter.css (molecule)

Dropdown filter for quotes by user tag. Lets researchers focus on specific tags they've applied, filtering the report to show only quotes with those tags. Essential for iterative analysis — researchers tag quotes across sessions, then filter to see all quotes for a given tag.

`.tag-filter` (relative wrapper). The tag filter button uses dual classes `toolbar-btn tag-filter-btn` — shared round-rect from `atoms/button.css`, dropdown-specific overrides in this file. SVG icons use `.toolbar-icon-svg` and `.toolbar-arrow` (shared toolbar classes). `.tag-filter-label` (inline-block, text-align right, min-width set by JS for layout stability). `.tag-filter-menu` (absolute dropdown, right-aligned, `z-index: 200`, `max-height: 32rem`, width locked by JS on open). `.tag-filter-actions` (Select all · Clear row), `.tag-filter-search` / `.tag-filter-search-input` (search field, only shown for 8+ tags). `.tag-filter-item` (flex row: checkbox + name + count), `.tag-filter-item-name` (ellipsis truncation at `max-width: 16rem`), `.tag-filter-item-muted` (italic for "(No tags)"), `.tag-filter-count` (right-aligned, muted, tabular-nums). `.tag-filter-divider` between "(No tags)" and user tags.

## hidden-quotes.css (molecule)

Styles for hidden quotes feature. Researchers often encounter "volume quotes" — repetitive or low-value quotes that clutter the report. The hide feature lets them suppress these while keeping them recoverable via per-subsection badges with dropdown previews.

- **`blockquote.bn-hidden`** — `display: none !important` (defence-in-depth; JS also sets `style.display = 'none'`)
- **`.hide-btn`** — absolute positioned at `right: 2rem` (between star at `0.65rem` and pencil at `3.35rem`), eye-slash SVG icon, opacity 0 by default → 1 on `blockquote:hover` / `.bn-focused`
- **`.bn-hidden-badge`** — right-aligned in `.quote-group` via `align-self: flex-end`, contains toggle button + dropdown
- **`.bn-hidden-toggle`** — accent-coloured text button ("3 hidden quotes ▾"), underline on hover
- **`.bn-hidden-dropdown`** — absolute below badge, `z-index: 200`, card styling (border, shadow, radius), scrollable
- **`.bn-hidden-item`** — flex row: timecode | preview (ellipsis-truncated) | participant code, border-bottom separator
- **`.bn-hidden-preview`** — clickable text to unhide, cursor pointer, underline on hover, `title="Unhide"`

## modal.css (atom)

Shared base styles for overlay modal dialogs, used by help-overlay, feedback, and confirmation modals. Provides a consistent modal pattern across the app — any new modal should build on these base classes rather than creating custom overlay/card styles.

`.bn-overlay` (fixed fullscreen backdrop, `z-index: 1000`, opacity/visibility transition), `.bn-modal` (centred card, relative position, `--bn-colour-bg` background, `--bn-radius-lg`, shadow, `max-width: 24rem` default — override per-modal for wider content), `.bn-modal-close` (absolute top-right × button, muted → text on hover), `.bn-modal-footer` (centred footer text, small muted), `.bn-btn-primary` (accent-coloured action button). Each modal adds its own content-specific classes on top (e.g. `.help-modal { max-width: 600px }`, `.feedback-modal { max-width: 420px }`).

## feedback.css (molecule)

Feedback modal content styles, extends `.bn-modal` from `modal.css`. `.feedback-modal` (max-width), `.feedback-sentiments` (flex row of emoji buttons), `.feedback-sentiment` (column layout, border highlight on `.selected`), `.feedback-label` (above textarea), `.feedback-textarea` (accent border on focus), `.feedback-actions` (Cancel + Send buttons), `.feedback-btn-send:disabled` (dimmed).

## name-edit.css (molecule)

Styles for participant name inline editing. Researchers need to assign real names to anonymised participant codes (p1, p2) — this editing UI appears in the participant table and follows the same contenteditable pattern as quote editing.

`.name-cell` / `.role-cell` positioning, `.name-pencil` (opacity 0 → 1 on row hover), editing state background, `.edited` dashed-underline indicator, `.unnamed` muted italic placeholder. Print-hidden.

## coverage.css (organism)

Styles for the transcript coverage section at the end of the report. This section addresses a key researcher concern: "did the AI silently drop important material?" It shows what percentage of participant speech made it into quotes and lets researchers triage omitted segments.

- **`.coverage-summary`** — percentages line below heading (muted colour)
- **`.coverage-details`** — `<details>` element for session list with custom disclosure triangle (▶/▼ via `::before` pseudo-element)
- **`.coverage-details summary`** — clickable "Show omitted segments" text, styled with custom list-style-none and `::before` for arrow
- **`.coverage-body`** — inner content wrapper
- **`.coverage-session`** — per-session group
- **`.coverage-session-title`** — "Session 1" heading (semibold)
- **`.coverage-segment`** — omitted segment text (muted colour, left padding); timecode links to transcript page
- **`.coverage-fragments`** — summary line for short fragments (`.label` italic, `.verbatim` roman)
- **`.coverage-empty`** — "Nothing omitted" message (muted, italic)

## codebook-panel.css (organism)

Codebook page grid layout and interactive components. The codebook gives researchers a visual way to organise their tags into meaningful groups (similar to a coding scheme in qualitative research). The masonry layout lets researchers see all their tag groups at a glance.

Uses CSS columns masonry (`columns: 240px`) for space-efficient tiling with `break-inside: avoid` on group cards. All values via design tokens — no hard-coded colours/spacing. Dark mode handled automatically via `light-dark()` tokens.

- **`.codebook-grid`** — masonry container, `max-width: 1200px`
- **`.codebook-group`** — group card with rounded corners, transparent border (accent on `.drag-over`), coloured background via `--bn-group-*` tokens
- **`.group-header`** — flex row: title area + close button (close fades in on group hover)
- **`.group-title-text`** / **`.group-subtitle`** — click-to-edit text with hover highlight
- **`.group-title-input`** / **`.group-subtitle-input`** — inline edit inputs with focus ring
- **`.group-total-row`** — tag count + total quote count summary
- **`.tag-row`** — grid row: badge + bar area, `cursor: grab`, drag states (`.dragging`, `.merge-target`)
- **`.tag-bar-area`** / **`.tag-micro-bar`** / **`.tag-count`** — micro histogram with bar colours from `--bn-bar-*` tokens
- **`.tag-add-row`** / **`.tag-add-badge`** / **`.tag-add-input`** — dashed "+" button → inline input
- **`.new-group-placeholder`** — dashed border card for creating new groups, also a drop target
- **`.drag-ghost`** — fixed-position ghost element during drag
- **`.tag-preview`** — inline badge in merge confirmation modal
