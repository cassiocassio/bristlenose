# React Migration — Primitive & Island Inventory

> **Historical inventory** (complete as of Feb 2026). Active migration plan: `docs/design-react-migration.md`. Working context lives in `bristlenose/server/CLAUDE.md`.

## Primitives (`frontend/src/components/`)

| # | Primitive | Round | Tests | Notes |
|---|-----------|-------|-------|-------|
| 1 | Badge | R1 done | 8 | Sentiment/tag labels, deletable variant |
| 2 | PersonBadge | R1 done | 5 | Speaker code lozenges (p1/m1/o1) |
| 3 | TimecodeLink | R1 done | 6 | Clickable timecodes, player integration |
| 4 | EditableText | R2 done | 19 | Click-to-edit + external trigger modes |
| 5 | Toggle | R2 done | 9 | Star/hide buttons |
| 6 | TagInput | R3 done | 23 | Auto-suggest, ghost text, rapid entry |
| 7 | Sparkline | R3 done | 12 | Mini stacked bars (sentiment distribution) |
| 8 | Counter | R3 done | 14 | Hidden-quotes dropdown (pulled from R4) |
| 9 | Metric | R4 done | 13 | Bar fill + SVG intensity dots, for analysis signal cards |
| 10 | JourneyChain | R4 done | 8 | Arrow-separated labels, wired into SessionsTable |
| 11 | Annotation | R4 done | 14 | Transcript page margin labels, composes Badge |
| 12 | Thumbnail | R4 done | 5 | Sessions table media preview, CSS extracted to atom |
| 13 | MicroBar | M5 done | 12 | Horizontal proportional bar (codebook + analysis) |
| 14 | ConfirmDialog | M5 done | 13 | Contextual inline confirmation, Enter/Escape |
| 15 | Modal | Infra | — | Infrastructure (build when needed for viewport-level dialogs) |
| 16 | Toast | Infra | — | Infrastructure (build when needed for feedback notifications) |

**All 4 rounds + M5 complete (14 primitives + 2 infrastructure, 182 Vitest tests).** Modal and Toast are infrastructure — build when first consumer needs them. ConfirmDialog covers the inline confirmation need that Modal was originally earmarked for.

## Islands (`frontend/src/islands/`)

| Island | Status | Mount point | API |
|--------|--------|-------------|-----|
| SessionsTable | Shipped (M1) | `#bn-sessions-table-root` | `GET /sessions` |
| QuoteSections | Shipped | `#bn-quote-sections-root` | `GET /quotes` |
| QuoteThemes | Shipped | `#bn-quote-themes-root` | `GET /quotes` |
| QuoteCard | Built (internal) | — | (composed into above) |
| QuoteGroup | Built (internal) | — | (composed into above) |
| Dashboard | Shipped (M4) | `#bn-dashboard-root` | `GET /dashboard` |
| CodebookPanel | Shipped (M5) | `#bn-codebook-root` | `GET /codebook` + CRUD |
| AboutDeveloper | Built (dev-only) | `#bn-about-developer-root` | `GET /dev/info` |

## Backend APIs — complete

6 data endpoints (hidden, starred, tags, edits, people, deleted-badges) + sessions + quotes + dashboard + 9 codebook CRUD endpoints. 330+ Python serve tests across 8 files.

## CSS alignment — done through M5

Extracted (R1–R3): `toggle.css`, `editable-text.css`, `sparkline.css`. Renamed: `person-id.css` → `person-badge.css`. Metric reuses existing classes from `organisms/analysis.css`. JourneyChain reuses `.bn-session-journey`. Thumbnail extracted to `atoms/thumbnail.css`. M5 tokenised `codebook-panel.css` (spacing, dark mode merge-target via `color-mix()`, sub-pixel border fix). Added `.confirm-dialog` styles to `codebook-panel.css`.

## What's next

1 remaining infrastructure primitive: **Toast** (build when first feedback notification need arises). Modal is deferred — ConfirmDialog covers inline confirmations. Next islands: transcript page, analysis page.
