# Bristlenose design-system inventory

Generated from `bristlenose/theme/` on 16 May 2026. Source of truth for the Figma specimen pages.

The theme follows the documented atomic structure (`tokens → atoms → molecules → organisms → templates`) per `bristlenose/theme/index.css`. Existing prose documentation worth not duplicating: `bristlenose/theme/CLAUDE.md` (typography scale, dark mode mechanics, tooltip pattern, gotchas) and `bristlenose/theme/CSS-REFERENCE.md` (per-component CSS docs).

## Tokens

Token files at theme root. Structural + analytical tokens in `tokens.css`; typography split between web (`tokens-typography.css`) and macOS (`tokens-desktop.css`). Colour palette tokens live in `colors/` and are theme-overridable via `data-color-theme="<name>"` on `<html>`.

### Colour — neutral / chrome
- `--bn-colour-bg` — page background — `theme/colors/palette-default.css`
- `--bn-colour-text` — primary text
- `--bn-colour-muted` — secondary/footnote text
- `--bn-colour-border` — default border
- `--bn-colour-border-hover` — hover border (3-state progression)
- `--bn-colour-accent` — accent / focus / link colour
- `--bn-colour-hover` — interactive hover background
- `--bn-colour-hover-bg`, `--bn-colour-hover-bg-subtle` — alt hover surfaces
- `--bn-colour-active-bg` — active/pressed background
- `--bn-colour-shadow` — drop-shadow colour
- `--bn-colour-icon-idle` — idle icon tint
- `--bn-colour-quote-bg` — quote-card surface
- `--bn-colour-badge-bg`, `--bn-colour-badge-text` — neutral badge surface
- `--bn-colour-user-tag-bg`, `--bn-colour-user-tag-text` — user-tag fallback
- `--bn-colour-editing-bg`, `--bn-colour-editing-border` — inline-edit state
- `--bn-colour-highlight`, `--bn-colour-cited-bg` — citation/anchor highlight (cited bg currently transparent; see `CLAUDE.md`)
- `--bn-colour-starred` — starred-quote accent
- `--bn-colour-negative` — negative/danger (note: `--bn-colour-danger` is referenced in CSS with a hardcoded `#dc2626` fallback but is not defined; see `theme/CLAUDE.md` gotchas)
- `--bn-colour-suggestion`, `--bn-colour-suggestion-bg` — legacy suggestion tone
- `--bn-selection-bg`, `--bn-selection-border` — multi-select operand state
- `--bn-selection-bg-inactive`, `--bn-selection-border-inactive` — dimmed-when-window-inactive variants
- `--bn-focus-ring`, `--bn-focus-shadow` — keyboard focus indicators
- `--bn-glow-colour`, `--bn-glow-colour-strong` — timecode glow

### Colour — sentiment (analytical, not theme-overridable) — `theme/tokens.css`
- `--bn-sentiment-frustration` / `-bg`
- `--bn-sentiment-confusion` / `-bg`
- `--bn-sentiment-doubt` / `-bg`
- `--bn-sentiment-surprise` / `-bg` (neutral / investigation flag)
- `--bn-sentiment-satisfaction` / `-bg`
- `--bn-sentiment-delight` / `-bg`
- `--bn-sentiment-confidence` / `-bg`
- `--bn-sentiment-{1..7}-bg` — index aliases for codebook integration
- Legacy aliases: `--bn-colour-frustration`, `--bn-colour-confusion`, `--bn-colour-delight` (and `-bg` siblings)

### Colour — codebook user-tag sets (OKLCH pentadic palette, `tokens.css`)
- UX set (blue): `--bn-ux-{1..5}-bg`
- Emotion set (red-pink): `--bn-emo-{1..6}-bg`
- Task set (green-teal): `--bn-task-{1..5}-bg`
- Trust set (purple): `--bn-trust-{1..5}-bg`
- Opportunity set (amber): `--bn-opp-{1..5}-bg`
- Custom/ungrouped: `--bn-custom-bg`
- Group card tints: `--bn-group-ux`, `--bn-group-emo`, `--bn-group-task`, `--bn-group-trust`, `--bn-group-opp`, `--bn-group-sentiment`, `--bn-group-none`
- Histogram bars: `--bn-bar-ux`, `--bn-bar-emo`, `--bn-bar-task`, `--bn-bar-trust`, `--bn-bar-opp`, `--bn-bar-sentiment`, `--bn-bar-none`
- Set indicator dots: `--bn-set-ux-dot`, `--bn-set-emo-dot`, `--bn-set-task-dot`, `--bn-set-trust-dot`, `--bn-set-opp-dot`

### Colour — analysis heatmap (OKLCH ramp, `tokens.css`)
- Hue anchors: `--bn-heat-frustration-h`, `--bn-heat-confusion-h`, `--bn-heat-doubt-h`, `--bn-heat-surprise-h`, `--bn-heat-satisfaction-h`, `--bn-heat-delight-h`, `--bn-heat-confidence-h`
- Ramp shape: `--bn-heat-chroma`, `--bn-heat-l-min`, `--bn-heat-l-max`
- Depleted state: `--bn-heat-depleted-h`, `--bn-heat-depleted-chroma`

### Colour — coverage bar (`tokens.css`)
- `--bn-coverage-report`, `--bn-coverage-moderator`, `--bn-coverage-omitted`

### Colour — palettes (override via `data-color-theme`)
- `theme/colors/palette-default.css` — blue/grey (web default, `:root` fallback)
- `theme/colors/palette-edo.css` — Edo-period art palette (desktop default)
- `theme/colors/_contract.css` — NOT loaded; documents required tokens for theme authors

### Spacing — `theme/tokens.css`
- `--bn-space-xs` — 0.15rem
- `--bn-space-sm` — 0.35rem
- `--bn-space-md` — 0.75rem
- `--bn-space-lg` — 1.5rem
- `--bn-space-xl` — 2rem

### Layout — `theme/tokens.css`
- `--bn-max-width` — 52rem (content)
- `--bn-quote-max-width` — 23rem (quote-card reading measure)
- `--bn-grid-gap` — 1.25rem
- `--bn-toolbar-height` — 3rem
- `--bn-sidebar-width` — 280px (and `-min` 200px, `-max` 480px)
- `--bn-rail-width` — 36px (collapsed icon rail)
- `--bn-minimap-width` — 5rem
- `--bn-overlay-duration` — 0.3s
- `--bn-gutter-left`, `--bn-gutter-right` — content gutters
- Breakpoints (reference values; `@media` can't use `var()`): `--bn-breakpoint-compact` (500px), `--bn-breakpoint-toolbar` (600px), `--bn-breakpoint-content` (1100px)

### Type — `theme/tokens-typography.css` (web) and `theme/tokens-desktop.css` (macOS, `data-platform="desktop"`)
- Font stacks: `--bn-font-body` (Inter Variable / system fallback), `--bn-font-mono`
- Weights: `--bn-weight-light`, `--bn-weight-normal` (420), `--bn-weight-emphasis` (490), `--bn-weight-starred` (520), `--bn-weight-strong` (700)
- Sizes + paired line-heights (Scale D, 8 stops):
  - `--bn-text-micro` / `-lh` — 9.6px
  - `--bn-text-badge` / `-lh` — 11.5px
  - `--bn-text-caption` / `-lh` — 12px
  - `--bn-text-label` / `-lh` — 13px (chrome default)
  - `--bn-text-body` / `-lh` — 15px
  - `--bn-text-heading` / `-lh` — 18px
  - `--bn-text-title` / `-lh` — 22px
  - `--bn-text-display` / `-lh` — 28px

### Radius — `theme/tokens.css`
- `--bn-radius-sm` — 3px
- `--bn-radius-md` — 6px
- `--bn-radius-lg` — 8px
- `--bn-radius-pill` — 999px

### Transitions — `theme/tokens.css`
- `--bn-transition-fast` — 0.15s ease
- `--bn-transition-normal` — 0.2s ease
- `--bn-transition-slow` — 0.3s ease

### Span bar — `theme/tokens.css`
- `--bn-span-bar-width`, `--bn-span-bar-gap`, `--bn-span-bar-offset`, `--bn-span-bar-colour`, `--bn-span-bar-opacity`, `--bn-span-bar-radius`

### Minimap — `theme/tokens.css`
- `--bn-minimap-heading`, `--bn-minimap-quote`, `--bn-minimap-viewport-bg`, `--bn-minimap-viewport-border`

### Crop handles — `theme/tokens.css`
- `--bn-crop-handle-colour`, `--bn-crop-handle-hover`

### Overlay — `theme/tokens.css`
- `--bn-overlay-shadow`

### Legacy aliases (deprecated but live, used by inline styles)
- `--font-body`, `--font-mono`, `--colour-bg`, `--colour-text`, `--colour-muted`, `--colour-border`, `--colour-accent`, `--colour-quote-bg`, `--colour-badge-bg`, `--colour-badge-text`, `--colour-confusion`, `--colour-frustration`, `--colour-delight`, `--colour-suggestion`, `--max-width`

## Atoms

All atom files live in `bristlenose/theme/atoms/`. Twenty files.

### Badges, tags, pills — `atoms/badge.css`
- `.badge` — base badge
- `.badge-frustration`, `.badge-confusion`, `.badge-doubt`, `.badge-surprise`, `.badge-satisfaction`, `.badge-delight`, `.badge-confidence` — sentiment variants
- `.badge-ai`, `.badge-user`, `.badge-proposed`, `.badge-add`, `.badge-restore` — provenance / action variants
- `.badge-narration`, `.badge-task_management` — speaker-role badges
- `.badge-action-pill`, `.badge-action-accept`, `.badge-action-deny` — floating accept/deny pill on proposed badges (see `docs/design-badge-action-pill.md`)
- `.badge-accept-flash`, `.badge-bulk-flash`, `.badge-appearing`, `.badge-removing` — animation states
- Deprecated/legacy variants kept for backward compat: `.badge-suggestion`, `.badge-frustrated`, `.badge-delighted`, `.badge-confused`, `.badge-amused`, `.badge-critical`, `.badge-sarcastic`, `.badge-judgment`

### Buttons — `atoms/button.css` and `atoms/toggle.css`
- `.edit-pencil`, `.edit-pencil-inline` — inline edit affordance
- `.toolbar-btn` — generic toolbar button (dual-class pattern; see CLAUDE.md)
- `.star-btn`, `.hide-btn`, `.toolbar-btn-toggle` — toggle buttons in `atoms/toggle.css`
- `.histogram-bar-delete` — histogram delete-on-hover button

### Checkbox — `atoms/checkbox.css`
- `.bn-checkbox` — ghost-style custom checkbox

### Input — `atoms/input.css`
- `.tag-input-box`, `.tag-input`, `.tag-ghost`, `.tag-ghost-layer`, `.tag-ghost-spacer`, `.tag-sizer` — tag-input with inline ghost-text completion

### Logo — `atoms/logo.css`
- `.report-logo`, `.report-logo-link` — header logo + click-to-Project-tab wrapper

### Footer — `atoms/footer.css`
- `.report-footer`, `.footer-logotype`, `.footer-version` — colophon

### Modal primitives — `atoms/modal.css`
- `.bn-overlay`, `.bn-modal`, `.bn-modal-close`, `.bn-modal-footer`, `.bn-modal-actions`, `.bn-modal-subtitle`
- `.bn-btn`, `.bn-btn-primary`, `.bn-btn-secondary`, `.bn-btn-cancel`, `.bn-btn-danger` — modal button variants

### Toast / floating notifications
- `atoms/toast.css`: `.toast-spinner`, `.toast-check`, `.toast-error`, `.toast-link`, `.toast-close`, `.toast-content`, `.toast-elapsed`, `.toast-progress-track`, `.toast-progress-fill`
- `atoms/autocode-toast.css`: `.autocode-toast` — AutoCode progress chip
- `atoms/activity-chip.css`: `.activity-chip`, `.activity-chip-stack`, `.activity-chip-summary`, `.activity-chip-collapse` — non-dismissable background-job chips
- `.chip-spinner`, `.chip-check`, `.chip-error`, `.chip-link`, `.chip-cancel`, `.chip-close`, `.chip-toggle` — chip internals

### Timecode — `atoms/timecode.css` and `atoms/context-expansion.css`
- `.bn-timecode-glow`, `.timecode-bracket` — timecode rendering
- `.timecode-expandable`, `.expand-arrow`, `.context-segment` — context-expansion chevrons

### Span bar — `atoms/span-bar.css`
- `.span-bar` — vertical extent indicator for quote ranges

### Thumbnail / video — `atoms/thumbnail.css`
- `.bn-video-thumb`, `.bn-play-icon` — 96×54 video thumbnail + play glyph

### Tooltip — `atoms/tooltip.css`
- `.bn-tooltip`, `.bn-tooltip-wrap` — base tooltip (system pattern documented in `theme/CLAUDE.md`)

### Moderator-question pill — `atoms/moderator-question.css`
- `.moderator-question`, `.moderator-question-text`, `.moderator-question-badge`, `.moderator-question-row`, `.moderator-question-dismiss`, `.moderator-question-more`, `.moderator-pill` — see `docs/design-moderator-question-pill.md`

### Journey label — `atoms/journey-label.css`
- (file scoped to journey markers; classes consumed by transcript renderer — see `bn-journey--fade-*` in templates)

### Interactive states — `atoms/interactive.css`
- `.bn-focused` — keyboard cursor state
- `.bn-selected` — multi-select operand state
- `.bn-window-inactive` — applied to `<html>` when macOS window loses focus (chrome dimming)
- `.bn-hide-ai-tags`, `.bn-no-animations`, `.bn-refresh-icon-spin` — global utility flags

### Bar atom — `atoms/bar.css`
- `.sentiment-bar`, `.sentiment-bar-count`, `.sentiment-bar-label`, `.sentiment-divider` — single histogram row primitives

### Confirm-delete modal — `atoms/modal.css` (composed)
- `.confirm-delete-modal`, `.clipboard-toast` — shared modal variant + clipboard feedback

### Report header — `atoms/modal.css` (block lives here historically)
- `.report-header`, `.header-left`, `.header-right`, `.header-title`, `.header-doc-title`, `.header-logotype`, `.header-meta`, `.header-project`

### Quote card primitives — `atoms/modal.css`
- `.quote-card`, `.quote-body`, `.quote-hover-zone` — base quote-card chrome (extended in molecules/organisms)

### Transcript primitives — `atoms/modal.css`
- `.transcript-segment`, `.transcript-word`

### Feedback — `atoms/modal.css`
- `.feedback-links` — footer feedback link container

## Molecules

All molecule files live in `bristlenose/theme/molecules/`. Sixteen files.

### Person badge — `molecules/person-badge.css`
- `.bn-person-badge`, `.bn-person-badge-name` (implicit), `.bn-person-badge-highlighted` — badge + name pattern for speaker cells
- `.bn-name-pencil` — inline edit affordance (Notion convention)
- `.bn-speaker-badge--split`, `.bn-speaker-editable-name`, `.bn-session-speaker-entry`

### Badge row — `molecules/badge-row.css`
- (utility row layout for badge groupings — minimal class surface, primarily layout)

### Bar group — `molecules/bar-group.css`
- `.sentiment-bar-group` — single histogram bar (label + bar + count via `display: contents` grid)

### Sparkline — `molecules/sparkline.css`
- `.bn-sparkline`, `.bn-sparkline-bar` — per-session sentiment mini bar chart

### Quote actions — `molecules/quote-actions.css`
- (hover-action layer on quote cards — see `CSS-REFERENCE.md` for class list)

### Tag input — `molecules/tag-input.css`
- `.tag-input-wrap`, `.tag-suggest`, `.tag-suggest-header`, `.tag-suggest-item`, `.tag-suggest-pill`, `.tag-suggest-hidden-icon` — tag entry with autosuggest

### Tag filter — `molecules/tag-filter.css`
- `.tag-filter`, `.tag-filter-menu`, `.tag-filter-search`, `.tag-filter-search-input`
- `.tag-filter-item`, `.tag-filter-item-muted`, `.tag-filter-label`, `.tag-filter-badge`, `.tag-filter-count`
- `.tag-filter-group`, `.tag-filter-group-header`, `.tag-filter-separator`, `.tag-filter-divider`
- `.tag-filter-actions`, `.tag-filter-action`

### Search — `molecules/search.css`
- `.search-container`, `.search-toggle`, `.search-field`, `.search-input`, `.search-clear`, `.search-mark`

### Editable text — `molecules/editable-text.css`
- `.editable-text` — generic inline editor

### Name edit — `molecules/name-edit.css`
- `.name-cell`, `.name-text`, `.name-pencil`, `.role-cell`, `.role-text`, `.unnamed` — speaker-name edit row

### Hidden quotes — `molecules/hidden-quotes.css`
- `.bn-hidden-badge`, `.bn-hidden-chevron`, `.bn-hidden-dropdown`, `.bn-hidden-header`, `.bn-hidden-item`, `.bn-hidden-preview`, `.bn-hidden-toggle`, `.bn-unhide-all`

### Feedback — `molecules/feedback.css`
- `.feedback-modal`, `.feedback-actions`, `.feedback-btn`, `.feedback-btn-cancel`, `.feedback-btn-send`, `.feedback-label`, `.feedback-textarea`
- `.feedback-sentiments`, `.feedback-sentiment`, `.feedback-sentiment-face`, `.feedback-sentiment-label`

### Help overlay — `molecules/help-overlay.css`
- `.help-modal`, `.help-columns`, `.help-section`, `.help-key-group`, `.help-key-sep`

### AutoCode report — `molecules/autocode-report.css`
- `.report-table`, `.report-row`, `.report-quote`, `.report-speaker`, `.report-timecode`, `.report-tag`, `.report-session-header`, `.report-deny`, `.report-deny-btn`
- `.has-tooltip` — tooltip-host utility (CSS-only tooltip implementation, see CLAUDE.md)

### Threshold review — `molecules/threshold-review.css`
- `.threshold-histogram`, `.threshold-histogram-axis`, `.threshold-histogram-bar`, `.threshold-histogram-bar--amber/--green/--grey`, `.threshold-histogram-bin`, `.threshold-histogram-square`
- `.threshold-slider`, `.threshold-slider-label`, `.threshold-slider-thumb`, `.threshold-slider-track`, `.threshold-slider-segment`, `.threshold-slider-segment--amber/--green/--grey`
- `.threshold-zone-counters`, `.threshold-zone-counter`, `.threshold-zone-counter--accept/--exclude/--tentative`, `.threshold-zone-counter-count`
- `.threshold-zone-list`, `.threshold-zone-list-header`, `.threshold-zone-list-body`, `.threshold-zone-list-body--open`, `.threshold-zone-list-chevron`, `.threshold-zone-list-chevron--open`, `.threshold-zone-list-count`
- `.threshold-action-btn`, `.threshold-actions`, `.threshold-action-accept`, `.threshold-action-deny`, `.threshold-instruction`, `.threshold-confidence`, `.threshold-footer`, `.threshold-proposal-table`

### Transcript annotations — `molecules/transcript-annotations.css`
- `.margin-annotation`, `.margin-label`, `.margin-tags`, `.segment-margin`
- `.crop-editable`, `.crop-ellipsis`, `.crop-handle`, `.crop-included-region`, `.crop-word`
- `.undo-btn`

## Organisms

All organism files live in `bristlenose/theme/organisms/`. Sixteen files.

### Blockquote / quote card — `organisms/blockquote.css`
- `.quote-card`, `.quote-group`, `.quote-body` (extended from atoms) — full quote-card composition with speaker, timecode, badges, span bar
- (See `CSS-REFERENCE.md` for full class list; key extensions of the `quote-card` atom)

### Sentiment chart — `organisms/sentiment-chart.css`
- `.sentiment-chart`, `.sentiment-chart-title`, `.sentiment-row` — twin AI + user-tag histograms (CSS-grid, `display: contents` pattern)

### Toolbar — `organisms/toolbar.css`
- `.toolbar`, `.toolbar-btn-label`
- `.view-switcher`, `.view-switcher-label`, `.view-switcher-menu`
- `.export-dropdown-wrapper`, `.export-dropdown-menu`, `.export-dropdown-item`, `.export-dropdown-separator`, `.export-dropdown-hint`

### Global nav / tabs — `organisms/global-nav.css`
- `.bn-global-nav`, `.bn-tab`, `.bn-tab-icon`, `.bn-tab-spacer`, `.bn-tab-panel`
- `.bn-dashboard`, `.bn-dashboard-full`, `.bn-dashboard-nav`, `.bn-dashboard-pane`, `.bn-dashboard-pane--pair`, `.bn-dashboard-pane--pair-half`
- `.bn-project-stat`, `.bn-project-stats`, `.bn-project-stat--pair`, `.bn-project-stat--pair-half`, `.bn-project-stat--text`, `.bn-project-stat-label`, `.bn-project-stat-value`
- `.bn-featured-quote`, `.bn-featured-row`, `.bn-featured-footer`, `.bn-empty-state`, `.bn-group-header`
- `.bn-session-back`, `.bn-session-label`, `.bn-session-subnav`
- `.bn-refetching`

### TOC — `organisms/toc.css`
- `.toc`, `.toc-link`, `.toc-heading`, `.toc-sub-heading`, `.toc-row`, `.toc-drag-handle`, `.toc-rail`, `.toc-rail-drag`
- `.toc-sidebar`, `.toc-sidebar-header`, `.toc-sidebar-body`

### Sidebar (left, primary) — `organisms/sidebar.css`
- `.sidebar-header`, `.sidebar-close`, `.sidebar-mini-btn`, `.rail-btn`
- `.layout`, `.center`, `.collapsed`

### Sidebar tags — `organisms/sidebar-tags.css`
- `.tag-sidebar`, `.tag-sidebar-header`, `.tag-sidebar-body`, `.tag-sidebar-subtitle`, `.tag-sidebar-actions`
- `.tag-rail`, `.tag-rail-drag`, `.tag-drag-handle`
- `.tag-list`, `.tag-row`, `.tag-name-area`, `.tag-bar-area`, `.tag-count`
- `.tag-edit-inline`, `.tag-add-row`, `.tag-add-badge`, `.tag-add-input`
- `.tag-search-container`, `.tag-search-input`
- `.tag-preview`, `.tag-solo-active`
- `.tag-micro-bar`, `.tag-micro-bar-stack`, `.tag-micro-bar-accepted`, `.tag-micro-bar-tentative`
- `.tag-filter-action-active`, `.tag-filter-group-header-row`, `.tag-filter-group-info`, `.tag-filter-group-name`, `.tag-filter-group-subtitle`, `.tag-filter-group-tags`
- `.new-group-icon`, `.new-group-label`
- `.proposed-count`

### Codebook panel — `organisms/codebook-panel.css`
- `.codebook-panel`, `.codebook-header`, `.codebook-body`, `.codebook-grid`, `.codebook-group`
- `.codebook-title`, `.codebook-description`, `.codebook-author`, `.codebook-info`, `.codebook-eye`, `.codebook-disclosure`, `.codebook-framework`
- `.codebook-modal`, `.codebook-modal-overlay`, `.codebook-modal-header`, `.codebook-modal-body`, `.codebook-modal-close`, `.codebook-modal-title`, `.codebook-modal-subtitle`
- `.framework-section-header`, `.framework-section-title`, `.framework-section-author`, `.framework-section-actions`, `.framework-remove-btn`
- `.picker-card`, `.picker-card-title`, `.picker-card-desc`, `.picker-card-author`, `.picker-card-tags`, `.picker-card-create`, `.picker-card-coming`, `.picker-card-restore`
- `.picker-row`, `.picker-section-header`, `.picker-section-title`
- `.preview-back`, `.preview-header`, `.preview-header-left`, `.preview-title`, `.preview-subtitle`, `.preview-desc`, `.preview-body`, `.preview-body-main`, `.preview-body-sidebar`, `.preview-section-label`, `.preview-groups`, `.preview-author`, `.preview-author-name`, `.preview-author-bio`, `.preview-author-links`, `.preview-cta-help`
- `.group-header`, `.group-title`, `.group-title-area`, `.group-title-text`, `.group-subtitle`, `.group-close`, `.group-eye`, `.group-total-row`, `.group-total-label`, `.group-total-count`
- `.merge-overlay`, `.drag-ghost`, `.drag-handle`
- `.confidence-badge`, `.confidence-emerging`, `.confidence-moderate`, `.confidence-strong`

### Coverage bar — `organisms/coverage.css`
- `.bn-coverage-box`, `.bn-coverage-bar`, `.bn-coverage-bar-segment`, `.bn-coverage-bar-segment--report/--moderator/--omitted`
- `.bn-coverage-segment`, `.bn-coverage-fragments`, `.bn-coverage-empty`, `.bn-coverage-session-title`
- `.bn-coverage-legend`, `.bn-coverage-legend-item`, `.bn-coverage-legend-dot`, `.bn-coverage-legend-dot--report/--moderator/--omitted`, `.bn-coverage-legend-value`
- Also: `.coverage-body`, `.coverage-details`, `.coverage-summary`, `.coverage-session`, `.coverage-session-title`, `.coverage-segment`, `.coverage-fragments`, `.coverage-empty`, `.pattern-gap`, `.pattern-recovery`, `.pattern-success`, `.pattern-tension`, `.pattern-label`

### Analysis (heatmap + signals) — `organisms/analysis.css`
- `.analysis-layout`, `.analysis-center`, `.analysis-heatmap`, `.analysis-heatmap-label`, `.analysis-codebook-section`, `.analysis-codebook-heading`
- `.heatmap-cell`, `.heatmap-col-label`, `.heatmap-row-hl`, `.heatmap-header-hl`, `.heatmap-total`, `.heatmap-grand-total`
- `.cell-tooltip`, `.cell-tooltip-body`, `.cell-tooltip-footer`, `.cell-tooltip-metrics`, `.cell-tooltip-pips`, `.cell-tooltip-pip`, `.cell-tooltip-quotes`, `.cell-tooltip-quote`, `.cell-tooltip-quote-text`, `.cell-tooltip-speaker`, `.cell-tooltip-val`
- `.signal-cards`, `.signal-card`, `.signal-card-top`, `.signal-card-right`, `.signal-card-identity`, `.signal-card-location`, `.signal-card-location-link`, `.signal-card-source`, `.signal-card-badges`, `.signal-card-metrics`, `.signal-card-quotes`, `.signal-card-expansion`, `.signal-card-footer`, `.signal-card-link`
- `.signal-entry`, `.signal-entry-name`, `.signal-group-badge`, `.signal-quote-tag`, `.signal-rank`, `.signal-sparkbar`, `.signal-sparkbars`, `.signal-elaboration`
- `.metric-label`, `.metric-value`, `.metric-viz`, `.conc-bar-track`, `.conc-bar-fill`, `.dimension-btn`, `.dimension-toggle`, `.intensity-dots-svg`
- `.participant-grid`, `.rewatch-item`, `.rewatch-participant`, `.autocode-btn`

### Inspector — `organisms/inspector.css`
- `.inspector-panel`, `.inspector-body`, `.inspector-handle`, `.inspector-handle-grip`, `.inspector-handle-title`, `.inspector-icon-btn`, `.inspector-tab`, `.inspector-tabs`

### Minimap — `organisms/minimap.css`
- `.bn-minimap-content`, `.bn-minimap-viewport`, `.bn-minimap-heading`, `.bn-minimap-group-heading`, `.bn-minimap-quote`, `.bn-minimap-division`, `.minimap-slot`

### Modal nav — `organisms/modal-nav.css`
- `.modal-nav`, `.modal-nav-overlay`, `.modal-nav-shell`, `.modal-nav-sidebar`, `.modal-nav-content`, `.modal-nav-content-heading`
- `.modal-nav-list`, `.modal-nav-item`, `.modal-nav-sub`, `.modal-nav-sub-list`
- `.modal-nav-arrow`, `.modal-nav-dropdown`, `.modal-nav-search`, `.modal-nav-title`

### Settings — `organisms/settings.css` and `organisms/settings-modal.css`
- `.settings-modal`
- `.bn-setting-group`, `.bn-setting-description`, `.bn-radio-label`, `.bn-locale-select`
- `.bn-config-ref`, `.bn-config-ref-chip`, `.bn-config-ref-chips`, `.bn-config-ref-envvar`, `.bn-config-ref-file`, `.bn-config-ref-intro`, `.bn-config-ref-label`, `.bn-config-ref-meta`, `.bn-config-ref-options`, `.bn-config-ref-row`, `.bn-config-ref-section`, `.bn-config-ref-value`

### Responsive grid — `organisms/responsive-grid.css`
- (utility — quote-group grid behaviour; layout-only, minimal class surface)

### Confirm dialog — `organisms/codebook-panel.css` (lives here historically)
- `.confirm-dialog-actions`, `.confirm-dialog-body`, `.confirm-dialog-title`, `.confirm-dialog-btn`, `.confirm-dialog-btn--cancel`, `.confirm-dialog-btn--primary`, `.confirm-dialog-btn--danger`

### Session entry (sidebar list row) — `organisms/codebook-panel.css` (lives here historically)
- `.session-entry`, `.session-entry-row`, `.session-entry-name`, `.session-entry-date`, `.session-entry-duration`, `.session-entry-thumb`, `.session-entry-right`, `.session-entry-sep`, `.session-entry-speaker-row`, `.session-entry-speakers`

## Templates

Template files in `bristlenose/theme/templates/`. Five CSS files (`report.css`, `transcript.css`, `print.css`, `export.css`, `status-page.css`) and fourteen Jinja2 HTML templates — listed below for completeness.

### Report page layout — `templates/report.css`
- `.bn-about`, `.bn-about-content`, `.bn-about-sidebar`, `.bn-about-footer`, `.bn-about-citation` — About tab
- `.bn-session-table`, `.bn-session-moderators`, `.bn-session-speakers`, `.bn-session-duration`, `.bn-session-id`, `.bn-session-journey` — session table
- `.bn-interviews-link`, `.bn-folder-icon` — input-folder link
- `.bn-sort-active`, `.bn-sort-arrow`, `.bn-sort-ghost` — sortable column headers
- `.description` — generic description block

### Transcript page — `templates/transcript.css`
- `.bn-cited` — inline citation highlight (currently transparent; mechanism intact)
- `.bn-journey--fade-left`, `.bn-journey--fade-right`, `.bn-journey--fade-both` — journey label fades
- `.bn-transcript-journey-header`, `.bn-transcript-roles`, `.bn-transcript-roles__name`, `.bn-transcript-roles__person`
- `.transcript-body`, `.transcript-meta`, `.transcript-segment`, `.segment-moderator`
- `.bn-selector`, `.bn-selector__trigger`, `.bn-selector__caret`, `.bn-selector__menu`, `.bn-selector__item`, `.bn-selector__item--active`, `.bn-selector__detail`, `.bn-session-selector__label` — session/speaker selector dropdowns

### Status page — `templates/status-page.css`
- `.bn-status-page`, `.bn-status`, `.bn-status-glyph`, `.bn-status-short`, `.bn-status-long`, `.bn-status-details`, `.bn-status-footer`

### Export — `templates/export.css`
- `.bn-export-mode` — body modifier when rendering for HTML export
- `.bn-export-checkbox`, `.bn-export-hint`, `.bn-export-error` — export modal controls
- `.bn-session-journey--overflow`

### Print — `templates/print.css`
- Print overrides; hides interactive elements (`.feedback-links`, `.feedback-overlay`, `.footer-logo-picture`, etc.). Forces `color-scheme: light`.

### Jinja2 HTML templates — `templates/*.html`
- `document_shell_open.html` — `<html>` + `<head>` shell
- `report_header.html` — report header
- `global_nav.html` — tab bar
- `toolbar.html` — toolbar
- `toc.html` — table of contents
- `content_section.html` — generic content section wrapper
- `quote_card.html` — quote-card render
- `dashboard_session_table.html` / `session_table.html` — session listings
- `sentiment_chart.html` — twin histograms
- `coverage.html` — coverage bar
- `friction_points.html` — friction-points section
- `user_journeys.html` — journeys section
- `analysis.html` — analysis tab body
- `player.html` — popout player shell
- `footer.html` — colophon

## Notes

- **Structure matches docs.** The tree follows the canonical `tokens → atoms → molecules → organisms → templates` order documented in `theme/index.css` and `theme/CLAUDE.md`. No surprises in the tier hierarchy.
- **Token file split.** Structural + analytical tokens live in `tokens.css` (theme root); typography is split between `tokens-typography.css` (web, Inter Variable) and `tokens-desktop.css` (macOS, SF Pro overrides activated by `data-platform="desktop"`). Colour palettes live in `colors/` and are switchable via `data-color-theme`. Historical drafts (`tokens-desktop-v1.css`, `tokens-desktop-v2.css`, `tokens-typography-v1.css`, `tokens-typography-v2.css`) sit alongside the live files; they are **not** loaded by the build — keep as design history.
- **`colors/_contract.css`** is documentation only (not loaded). Lists the tokens a new palette must define.
- **Legacy token aliases** at the bottom of `tokens.css` (`--font-body`, `--colour-*`, `--max-width`) exist so inline `style=""` attributes from older renderers keep working. Don't reuse them in new CSS.
- **Deprecated badge variants** (`.badge-frustrated`, `.badge-delighted`, `.badge-confused`, `.badge-amused`, `.badge-critical`, `.badge-sarcastic`, `.badge-judgment`, `.badge-suggestion`) are still in `atoms/badge.css` for compatibility with old intermediate JSON. New work uses the v0.7+ taxonomy variants.
- **Atom/organism cross-pollination.** `atoms/modal.css` carries more than modal primitives — it also defines `.report-header`, `.quote-card` base, `.transcript-segment` base, and `.feedback-links`. These are atom-tier base classes that organisms extend; if Figma renames it would be cleaner to split, but the current file is the source of truth.
- **Some organism classes live in cousin files.** `.confirm-dialog-*` and `.session-entry-*` are physically in `organisms/codebook-panel.css` though they are independent components. Treat them as separate Figma components even though they share a CSS file.
- **`--bn-colour-danger` / `--bn-colour-success`** are referenced in CSS (with hardcoded `#dc2626` / `#16a34a` fallbacks) but are **not defined** in any token file. `--bn-colour-negative` is defined and serves a similar role. Future cleanup item (see `theme/CLAUDE.md` gotcha).
- **JavaScript modules** are not part of this inventory — see `theme/js/MODULES.md`. CSS-side hooks (`bn-no-animations`, `bn-hide-ai-tags`, `bn-refresh-icon-spin`, `bn-window-inactive`) are included under Atoms / Interactive.
- **Tooltip pattern is dual implementation** — CSS-only (`molecules/autocode-report.css` via `.has-tooltip`) and JS-controlled (analysis cell tooltips in React). Spec documented in `theme/CLAUDE.md` "Tooltip pattern (system-wide)".
- **PersonBadge has a React equivalent** — `frontend/src/components/PersonBadge.tsx`. The CSS class names match. The same pattern applies broadly: theme CSS is shared by static render and React SPA; React component boundaries are being aligned to CSS file boundaries (see `docs/design-react-component-library.md`).
- **Static render is sealed scaffolding** — per project `CLAUDE.md`, design intent lives in the React SPA; the CSS in `theme/` is shared but new design work targets `frontend/` first. Treat the inventory as the *current* surface, not the design destination.
