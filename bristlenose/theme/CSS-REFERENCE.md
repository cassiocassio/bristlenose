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

`.tag-filter` (relative wrapper). The tag filter button uses dual classes `toolbar-btn tag-filter-btn` — shared round-rect from `atoms/button.css`, dropdown-specific overrides in this file. SVG icons use `.toolbar-icon-svg` and `.toolbar-arrow` (shared toolbar classes). `.tag-filter-label` (inline-block, text-align right, min-width set by JS for layout stability). `.tag-filter-menu` (absolute dropdown, right-aligned, `z-index: 200`, `max-height: 32rem`, width locked by JS on open). `.tag-filter-actions` (Select all · Clear row), `.tag-filter-search` / `.tag-filter-search-input` (search field, only shown for 8+ tags, placeholder "Search tags and groups…"). `.tag-filter-group` (tinted background container for codebook groups, `border-radius: var(--bn-radius-sm)`, background set inline via `var(--bn-group-{set})`). `.tag-filter-group-header` (uppercase group name label inside tinted container). `.tag-filter-item` (flex row: checkbox + badge + count), `.tag-filter-badge` (design-system `.badge .badge-user` with ellipsis truncation at `max-width: 16rem`, codebook colour applied inline), `.tag-filter-item-muted` (italic for "(No tags)"), `.tag-filter-count` (right-aligned, muted, tabular-nums). `.tag-filter-divider` between "(No tags)" and user tags. Ungrouped tags appear first as flat items; codebook groups follow with tinted containers. Search matches both tag names and group names.

## badge.css (atom)

Badge base, sentiment variants, AI/user badge variants, animations.

- **`.badge`** — base: inline-block, mono font, small padding, neutral background
- **Sentiment variants** (`.badge-frustration` … `.badge-confidence`) — 7 research-backed sentiments with distinct bg/text colours from tokens
- **`.badge-ai`** — AI-assigned badges. Hover reveals `::after` delete circle (red `×` on white chip, `var(--bn-colour-danger)`). `body.hide-ai-tags .badge-ai { display: none }`
- **`.badge-user`** — user tags. Dark-on-light (light mode), white-on-saturated (dark mode). Codebook colour via inline style. `.badge-delete` positioned same as AI `::after`, red `×` (`var(--bn-colour-danger)`)
- **`.badge-add`** — dashed ghost button for adding tags. Accent on hover
- **`.badge-proposed`** — autocode-proposed tags. Pulsating dashed border (`bn-proposed-pulse`, 3s, opacity 50–78%). Animation pauses on hover. `position: relative` for pill positioning
- **`.badge-action-pill`** — floating `[✗ | ✓]` pill above proposed badge. Absolute positioned at delete-circle location (`top: calc(-0.3rem - 1px)`), `✗` aligns with delete `×`, `✓` hangs right past badge edge. 16px compartments, `border-radius: 8px`. `opacity: 0` → `1` on badge hover. Shadow matches delete circles
- **`.badge-action-deny`** — pill left compartment (`✗`). Red (`var(--bn-colour-danger)`), `#fef2f2` bg on hover
- **`.badge-action-accept`** — pill right compartment (`✓`). Green (`var(--bn-colour-success)`), `#dcfce7` bg on hover, `border-left` divider
- **`.badge-accept-flash`** — 0.4s brightness burst (`filter: brightness(1.35)` → `1`) on newly accepted badge. Applied by React `QuoteCard`
- **`.badge-removing`** — fade-out + scale-down (0.15s). Used by `animateBadgeRemoval()` in `badge-utils.js`
- **`.badge-appearing`** — fade-in + scale-up (0.15s). Opt-in by callers
- **`.badge-bulk-flash`** — blue `box-shadow` ring pulse (0.8s, asymmetric: 0.2s in / 0.6s out). Applied by `closeTagInput()` in `tags.js` during bulk tag commit. Uses `--bn-selection-border` token for consistent selection-associated colour in both themes
- **Colour unification** — all delete/deny `×` circles use `var(--bn-colour-danger)` (red). This applies to `.badge-ai::after`, `.badge-user .badge-delete`, and `.badge-action-deny`. Previously delete circles were grey (`--bn-colour-muted`)

## toggle.css (atom)

On/off icon buttons extracted from `button.css` and `hidden-quotes.css` (Round 2 CSS refactoring). Groups all toggle-style buttons together — star, hide, and toolbar toggle.

- **`.star-btn`** — absolute positioned (top-right, `right: 0.65rem`), icon-idle colour, accent on hover. React: `Toggle` component with `className="star-btn"`
- **`.hide-btn`** — absolute positioned at `right: 2rem` (between star at `0.65rem` and pencil at `3.35rem`), eye-slash SVG icon, `opacity: 0` by default → 1 on `blockquote:hover` / `.bn-focused`. React: `Toggle` component with `className="hide-btn"`
- **`.toolbar-btn-toggle`** — binary active/inactive state for toolbar buttons (AI tag visibility). `.active` class adds accent border + colour; `:not(.active)` shows muted. React: `Toggle` component with `className="toolbar-btn toolbar-btn-toggle"` and `activeClassName="active"`

## editable-text.css (molecule)

Shared editing and committed states for inline contenteditable fields. Extracted from `quote-actions.css` and `name-edit.css` (Round 2 CSS refactoring). Groups all editing visual patterns together.

- **Editing state** — yellow background (`--bn-colour-editing-bg`) + outline (`--bn-colour-editing-border`) + `border-radius: sm` + cursor: text. Applied to `blockquote.editing .quote-text`, `.editable-text.editing`, `.name-cell.editing .name-text`, `.role-cell.editing .role-text`
- **`blockquote.editing .edit-pencil`** — pencil turns accent colour during edit
- **Committed state** — dashed underline indicating text was edited. `.quote-text.edited` and `.editable-text.edited` use `--bn-colour-muted`; `.name-text.edited` and `.role-text.edited` use `--bn-colour-accent`
- **React**: `EditableText` component with `committedClassName="edited"` (default)

## hidden-quotes.css (molecule)

Styles for hidden quotes feature. Researchers often encounter "volume quotes" — repetitive or low-value quotes that clutter the report. The hide feature lets them suppress these while keeping them recoverable via per-subsection badges with dropdown previews. (`.hide-btn` rules moved to `atoms/toggle.css` in Round 2.)

- **`blockquote.bn-hidden`** — `display: none !important` (defence-in-depth; JS also sets `style.display = 'none'`)
- **`blockquote.bn-hiding`** — CSS collapse transition for React hide animation: `max-height: 0`, `opacity: 0`, zero margins/padding/border, `transition: all 300ms ease`. Applied by React `QuoteGroup` during the 300ms before setting `isHidden: true`
- **`.bn-hidden-badge`** — lives inside `.bn-group-header` (flex row alongside the h3 heading), right-aligned via `justify-content: space-between` on the parent. Contains toggle button + dropdown
- **`.bn-hidden-toggle`** — accent-coloured text button ("3 hidden quotes ▾"), underline on hover
- **`.bn-hidden-dropdown`** — absolute below badge, `z-index: 200`, card styling (border, shadow, radius), scrollable
- **`.bn-hidden-header`** — flex row: "Unhide:" label + "Unhide all" link (when 2+ hidden). `justify-content: space-between`
- **`.bn-unhide-all`** — accent link in dropdown header, underline on hover
- **`.bn-hidden-item`** — flex row: timecode | preview (ellipsis-truncated) | participant code, border-bottom separator
- **`.bn-hidden-preview`** — clickable text to unhide, cursor pointer, underline on hover, `title="Unhide"`

## quote-actions.css (molecule) — bulk preview classes

Hover preview feedback for selection-aware bulk star/hide operations. Applied by `starred.js` and `hidden.js` when hovering action buttons on a selected quote with 2+ quotes in the selection.

- **`blockquote.bn-preview-star .star-btn`** — accent colour at `opacity: 0.6`, signals "will be starred"
- **`blockquote.bn-preview-unstar .star-btn`** — accent colour at `opacity: 0.35`, signals "will be unstarred". Overrides `.starred` star colour
- **`blockquote.bn-preview-hide`** — `opacity: 0.85` with fast transition, signals "will be hidden"
- **`blockquote.bn-preview-hide .hide-btn`** — forced `opacity: 1` + accent colour (makes eye icon visible even without hover)

## modal.css (atom)

Shared base styles for overlay modal dialogs, used by help-overlay, feedback, and confirmation modals. Provides a consistent modal pattern across the app — any new modal should build on these base classes rather than creating custom overlay/card styles.

`.bn-overlay` (fixed fullscreen backdrop, `z-index: 1000`, opacity/visibility transition), `.bn-modal` (centred card, relative position, `--bn-colour-bg` background, `--bn-radius-lg`, shadow, `max-width: 24rem` default — override per-modal for wider content), `.bn-modal-close` (absolute top-right × button, muted → text on hover), `.bn-modal-footer` (centred footer text, small muted), `.bn-btn-primary` (accent-coloured action button). Each modal adds its own content-specific classes on top (e.g. `.help-modal { max-width: 600px }`, `.feedback-modal { max-width: 420px }`).

## feedback.css (molecule)

Feedback modal content styles, extends `.bn-modal` from `modal.css`. `.feedback-modal` (max-width), `.feedback-sentiments` (flex row of emoji buttons), `.feedback-sentiment` (column layout, border highlight on `.selected`), `.feedback-label` (above textarea), `.feedback-textarea` (accent border on focus), `.feedback-actions` (Cancel + Send buttons), `.feedback-btn-send:disabled` (dimmed).

## name-edit.css (molecule)

Styles for participant name inline editing layout. Researchers need to assign real names to anonymised participant codes (p1, p2) — this editing UI appears in the participant table. (Editing/edited state rules moved to `molecules/editable-text.css` in Round 2.)

`.name-cell` / `.role-cell` positioning (relative, padding-right for pencil), `.name-pencil` (absolute, opacity 0 → 1 on row hover, accent on hover), `.unnamed` muted italic placeholder. Print-hidden.

## coverage.css (organism)

Styles for the transcript coverage section at the end of the report. This section addresses a key researcher concern: "did the AI silently drop important material?" It shows what percentage of participant speech made it into quotes and lets researchers triage omitted segments.

- **`.coverage-summary`** — percentages line below heading (muted colour)
- **`.coverage-details`** — `<details>` element for session list with custom disclosure triangle (▶/▼ via `::before` pseudo-element)
- **`.coverage-details summary`** — clickable "Show omitted segments" text, styled with custom list-style-none and `::before` for arrow
- **`.coverage-body`** — inner content wrapper
- **`.coverage-session`** — per-session group
- **`.coverage-session-title`** — "Session 1" heading (emphasis weight)
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

## Session table (report.css + molecules/person-badge.css)

The sessions table in both the Sessions tab and Project tab. Shows per-session metadata: speaker badges, user journey paths, video thumbnails, and sentiment sparklines. Styled primarily in `templates/report.css` with the `bn-person-badge` molecule from `molecules/person-badge.css`.

### Structure

- **`.bn-session-table`** — `<section>` wrapper. Contains optional moderator header paragraph + `<table>`
- **`.bn-session-moderators`** — paragraph above table: "Sessions moderated by [m1] Rachel and [m2] Kerry". Uses `.bn-person-badge` molecule for badge+name pairs. Names are regular weight (not semibold) in the header
- **`.bn-session-table tr`** — `border-bottom: 1px solid var(--bn-colour-border)`. Applied to `<tr>` rather than `<td>` to ensure full-width horizontal rules (avoids gaps from varying cell heights)
- **`.bn-session-table td`** — `border-bottom: none` (overrides default, since the border is on `<tr>`)

### Columns

- **`.bn-session-id`** — `#N` link, accent colour, `white-space: nowrap`. Links to inline transcript via `data-session-link`
- **`.bn-session-speakers`** — `display: flex; flex-direction: column; gap: 0.35rem`. Contains one `.bn-person-badge` per speaker (vertically stacked)
- **`.bn-person-badge`** (molecule) — `inline-flex, align-items: center, gap: 0.4rem, white-space: nowrap`. Contains `.badge` (flex-shrink: 0) + `.bn-person-badge-name` (font-weight: var(--bn-weight-emphasis) / 490)
- **`.bn-session-meta`** — Start date cell, contains date div + optional `.bn-session-journey`
- **`.bn-session-journey`** — user journey path below start date. `font-size: 0.82rem`, `color: var(--bn-colour-muted)`, `white-space: normal` (wraps). Content: "Homepage → Tropical Fish → Equipment → …"
- **`.bn-session-duration`** — `text-align: right` on both `<th>` and `<td>`. Format: `MM:SS` or `HH:MM:SS`
- **Interviews column** — source filename. Header uses `.bn-interviews-link` with `.bn-folder-icon` SVG (legacy: `file://` link to input folder; React island: copies `file://` URI to clipboard). Cell shows truncated filename (via `format_finder_filename()`) with `title` for full name on hover. Media sessions (video/audio) render the filename as `<a class="timecode">` — `player.js` event delegation opens the popout player at 0:00. Non-media sessions show plain `<span>` text
- **`.bn-session-thumb`** — thumbnail cell. `.bn-video-thumb`: `width: 96px; height: 54px` (16:9 HD), `background: var(--bn-colour-border)`, `border-radius: var(--bn-radius-sm)`, flex-centred `.bn-play-icon` (▶ triangle, 1.2rem, muted)
- **`.bn-session-sentiment`** — sentiment sparkline cell. `.bn-sparkline` container: `display: inline-flex; align-items: flex-end; height: 54px` (matches thumbnail height so baselines align). `.bn-sparkline-bar` spans: height set inline (normalised), colour via `--bn-sentiment-{name}` tokens, `border-radius` on top corners

### Feature flag

`BRISTLENOSE_FAKE_THUMBNAILS=1` env var shows thumbnail placeholders for all sessions (even VTT-only). For layout testing only — the shipped version uses real `video_map` logic.

## analysis.css (organism)

Analysis page signal cards and heatmap table. The analysis page presents statistical patterns detected across sections/themes and sentiments, helping researchers identify where sentiment is concentrated.

### Signal cards

- **`.signal-cards`** — flex column container for all cards
- **`.signal-card`** — bordered card. `--card-accent` custom property set inline (maps to sentiment colour), used by participant grid highlight. Hover adds box-shadow. `.expanded` class triggers quote list expansion
- **`.signal-card-top`** — flex row: identity (location + sentiment) left, metrics right
- **`.signal-card-identity`** — location name, source type label (section/theme), sentiment badge
- **`.signal-card-metrics`** — 3-column grid: label | value | visualisation (concentration bar, Neff, intensity dots)
- **`.conc-bar-track`** / **`.conc-bar-fill`** — horizontal bar showing concentration ratio (0–100% of track width)
- **`.intensity-dots-svg`** — inline container for 1–5 dot SVGs
- **`.signal-card-quotes`** — expandable quote list with `--bn-colour-quote-bg` background. Blockquotes use hanging-indent layout (timecode | body | intensity dots). Consecutive quotes from the same session get `.seq-first`/`.seq-middle`/`.seq-last` classes (tighter spacing, dimmed timecodes)
- **`.signal-card-expansion`** — max-height/opacity transition for expand/collapse animation (max-height set by JS)
- **`.signal-card-footer`** — participant count + link back to report section
- **`.participant-grid`** — flex-wrap row of `.p-box` participant code chips. `.p-present` gets accent-tinted background via `color-mix()`

### Confidence badges (hidden from UI, preserved for future)

- **`.confidence-badge`** — base: small uppercase label
- **`.confidence-strong`** / **`.confidence-moderate`** / **`.confidence-emerging`** — colour variants using `light-dark()` for dark mode

### Heatmap

- **`.analysis-heatmap`** — full-width collapsed-border table
- **`.analysis-heatmap th`** — column headers (sentiment names with badge), first column left-aligned (row labels)
- **`.heatmap-cell`** — data cell with OKLCH background set inline by JS. Clickable cells (`.has-card`) scroll to matching signal card. `.heat-strong` class inverts text colour for readability on dark backgrounds using `light-dark(#fff, #111)`
- **`.heatmap-cell[data-count="0"]`** — zero cells: muted colour, no cursor, no hover outline
- **`.heatmap-total`** — row/column total cells: transparent background, no interaction
