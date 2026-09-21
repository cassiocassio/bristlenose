---
status: archived-historical
last-trued: 2026-09-21
trued-against: HEAD@main on 2026-09-21
superseded-by: [../CLAUDE.md, ../bristlenose/server/CLAUDE.md]
---

> **Superseded — 21 Sep 2026. This document describes a mechanism that no longer
> runs, and it is kept as the record of how the React migration got off the
> ground, not as a guide.**
>
> Measured at HEAD: **`serve_report_html()` does not exist** anywhere in the
> tree — the only hits are prose in two CLAUDE.md files, now corrected. Nor does
> `_REACT_APP_MOUNT`. Serve mode emits `<div id="bn-app-root" data-project-id="1">`
> directly (`bristlenose/server/app.py:657`) and the browser mounts the whole SPA
> into it; there is no per-island regex substitution and no per-island mount div.
>
> The sealed Jinja2 renderer still *writes* `<!-- bn-app -->` and
> `<!-- bn-session-table -->` (`s12_render/report.py:189`, `:219`, `:235`,
> `:485`), which is why a grep finds the markers and reads as though the pattern
> survives. Nothing consumes them. The frontend hits for `bn-session-table` are a
> CSS class of the same name, not the marker.
>
> §"Current React islands" below lists four, and names the two lenses as
> vanilla JS. Both are React now (`CodebookV2.tsx`, `SignalsPage.tsx`) and there
> are **18** islands. §"Adding a new React island" step 3 instructs an edit to a
> function that is gone — do not follow it.
>
> _It is left in `docs/` rather than moved to `docs/archive/` only because the
> move wants a pointer sweep; that is owed, not done._

# React Islands — Integration Pattern

React islands replace static Jinja2 content at serve time using a **marker-based substitution** pattern. No changes to the render pipeline or Jinja2 templates beyond adding comment markers. Working context lives in `bristlenose/server/CLAUDE.md`.

## How it works

1. **Render time** (`render/report.py`): wraps content regions in comment markers:
   ```html
   <!-- bn-quote-sections -->
   <section>...Jinja2 content...</section>
   <!-- /bn-quote-sections -->
   ```

2. **Serve time** (`app.py:serve_report_html()`): regex replaces marker regions with React mount divs:
   ```html
   <!-- bn-quote-sections -->
   <div id="bn-quote-sections-root" data-project-id="1"></div>
   <!-- /bn-quote-sections -->
   ```

3. **Browser**: React `main.tsx` finds `#bn-quote-sections-root`, calls `createRoot().render(<QuoteSections />)`

## Current React islands

| Mount point | Component | Markers | API endpoint |
|------------|-----------|---------|-------------|
| `#bn-sessions-table-root` | `SessionsTable` | `bn-session-table` | `GET /api/projects/{id}/sessions` |
| `#bn-quote-sections-root` | `QuoteSections` | `bn-quote-sections` | `GET /api/projects/{id}/quotes` |
| `#bn-quote-themes-root` | `QuoteThemes` | `bn-quote-themes` | `GET /api/projects/{id}/quotes` |
| `#bn-about-developer-root` | `AboutDeveloper` | (created by JS) | `GET /api/dev/info` |

## Adding a new React island

1. Add `<!-- bn-{name} -->` / `<!-- /bn-{name} -->` markers in `render/report.py`
2. Add `_REACT_{NAME}_MOUNT` constant in `app.py` with the mount div
3. Add `re.sub()` call in `serve_report_html()` to swap markers for mount div
4. Register the mount point in the renderer overlay CSS (4 places: `position:relative`, `:not(:has())` exclusions, cancel-inside-React, green overlay+outline)
5. Add mount logic in `frontend/src/main.tsx`
6. Re-open the project with `bristlenose serve <folder>` — serve mode auto-renders intermediate data on open, so the new markers are baked in without a separate render step. (Pre-A3 this step was `bristlenose render`, removed 12 May 2026.)

## Renderer overlay (dev-only)

The `_build_renderer_overlay_html()` function injects CSS that colour-codes the page by renderer origin:
- **Blue** — Jinja2 (static pipeline HTML)
- **Green** — React islands
- **Amber** — Vanilla JS regions (codebook grid, analysis)

Toggle with the palette button in the top-right corner. When adding a new React island, register it in all 4 CSS blocks (see step 4 above) or it will show as blue instead of green.
