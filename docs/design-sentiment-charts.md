# Sentiment Bar Charts

Two side-by-side horizontal bar charts in the Sentiment section: AI sentiment (server-rendered) and User tags (JS-rendered by `histogram.js`). The dual-chart design lets researchers compare what the AI detected with what they've tagged themselves. Working context lives in `bristlenose/theme/CLAUDE.md`.

## Layout (CSS grid)

`.sentiment-chart` uses `display: grid; grid-template-columns: max-content 1fr max-content` with `row-gap: var(--bn-space-md)`. Each `.sentiment-bar-group` uses `display: contents` so its three children (label, bar, count) participate directly in the parent grid. This is what aligns all bar left edges — the `max-content` first column sizes to the widest label in that chart.

- **Labels** (`atoms/bar.css`): `width: fit-content` + `justify-self: start` — background hugs the text, variable gap falls between label right edge and bar left edge. `max-width: 12rem` with `text-overflow: ellipsis` for long tags
- **Bars**: inline `style="width:Xpx"` set by Python (`_build_sentiment_html()`) and JS (`renderUserTagsChart()`). `max_bar_px = 180`
- **Side-by-side**: `.sentiment-row` is `display: flex; align-items: flex-start` — charts top-align, wrap on narrow viewports
- **Title + divider**: `grid-column: 1 / -1` to span all three columns

## AI sentiment order

Positive (descending by count) → surprise (neutral) → divider → negative (ascending, worst near divider). See `_build_sentiment_html()` in `render/sentiment.py`.

## Histogram delete button

Each user tag label has a hover `×` button (`.histogram-bar-delete` in `atoms/bar.css`, same visual as `.badge-delete`). Click shows a confirmation modal via `createModal()`, then `_deleteTagFromAllQuotes()` removes the tag from all quotes and calls `persistUserTags()`.

## CSS files

- `atoms/bar.css` — `.sentiment-bar`, `.sentiment-bar-label`, `.sentiment-bar-count`, `.histogram-bar-delete`, `.sentiment-divider`
- `molecules/bar-group.css` — `.sentiment-bar-group` (`display: contents`)
- `organisms/sentiment-chart.css` — `.sentiment-row`, `.sentiment-chart`, `.sentiment-chart-title`
