# Quotes Export (CSV + Spreadsheet) — Design Document

Structured quotes export for research packages, Miro boards, and onward analysis.

**Status:** Not started. Fills the biggest gap in the export story.

---

## Context

Researchers curate quotes in Bristlenose — starring, tagging, editing — then need to take that structured data into other tools. Today, the only path out is copy-paste from the browser. The CSV export exists in the static render path (`csv-export.js`) but is **not available in React serve mode** — the module is stripped by `_strip_vanilla_js()`.

**Who it's for:**
- A researcher building a Miro affinity wall (drag CSV onto board, get stickies)
- A researcher moving quotes into Excel/Sheets for further analysis or filtering
- A designer who wants a spreadsheet of pain points to share with the team

**Bridge to Miro (Tier 1):** A Miro-shaped CSV ships for free with this feature. Drag it onto a Miro board and get sticky notes with participant codes, quotes, and themes. No API integration needed — that's Tier 2 (see `docs/design-miro-bridge.md`).

---

## What exists today

- `bristlenose/theme/js/csv-export.js` — vanilla JS CSV export in static render path. Extracts columns from DOM. **Not available in serve mode** (stripped by `_strip_vanilla_js()`)
- No server-side CSV or XLS export
- No export dropdown in the serve-mode toolbar

---

## Design

### Two formats

| Format | Action label | Where | Use case |
|--------|-------------|-------|----------|
| CSV (clipboard) | "Copy Quotes" | Toolbar button, Quotes menu | Paste into Miro, Sheets, Numbers. Instant, no file |
| XLS (file download) | "Save as Spreadsheet..." | Export dropdown, Quotes menu | Excel/Numbers with auto-filters, frozen header row |

**Action-oriented labels, not format names.** Researchers don't know what CSV is. Use "Copy Quotes" and "Save as Spreadsheet...", not "Copy CSV" and "Save as XLS".

### Columns (11)

| # | Column | Source | Notes |
|---|--------|--------|-------|
| 1 | Quote text | Quote body (edited version if edited) | The thing itself |
| 2 | Participant code | `p1`, `p2` | For grouping |
| 3 | Participant name | Display name from people file | Human-readable |
| 4 | Section | Report section the quote lives in | Top-level grouping |
| 5 | Theme | Theme grouping | Concatenate multiple with ` / ` separator |
| 6 | Sentiment | Emotion tag | e.g. "frustration", "delight" |
| 7 | Tags (all) | Comma-separated codebook tags | For filtering in Excel |
| 8 | Starred | Boolean | Researcher's highlights |
| 9 | Timecode | `mm:ss` format | For finding the moment |
| 10 | Session | Which interview (session title or ID) | Grouping |
| 11 | Source file | Original recording filename | Reference |

### Selection logic

Same cascade as the existing vanilla JS CSV export:

```
selected quotes (multi-select) → else all visible quotes
```

"Visible" respects current filters:
- Starred-only filter
- Tag checkbox filters
- Search text filter
- Hidden quotes excluded

### Scope display

Every export action must state its scope before commit:

- Toolbar button: "Copy 47 Quotes" (count inline)
- File dialog grey summary: "Exporting 47 quotes from 3 sessions"
- If filtered: "Exporting 47 quotes from 3 sessions (filtered by: Onboarding, starred only)"
- Toast on clipboard copy: "47 quotes copied"
- Zero-results guard: "No quotes match current filters" — extend existing `noQuotesSelected` toast pattern

### Theme column

Quotes can belong to multiple themes. Concatenate with ` / ` separator:

```
Onboarding / First impressions
```

### Serve-mode export dropdown

The web toolbar currently has one export icon. Replace with a **tab-contextual dropdown** that lists available exports for the current context:

- On Quotes tab: "Copy Quotes" | "Save as Spreadsheet..." | "Export Report..."
- On other tabs: "Export Report..."

This is the discovery mechanism — without it, CSV/XLS exports are invisible to serve-mode users.

### Inline hint (not tooltip)

Below the Copy Quotes action:

> Paste into Miro, Excel, or Google Sheets

Visible text, not a hover tooltip. Trackpad users don't hover.

### Desktop app

- **Quotes menu:** "Copy Quotes to Clipboard" and "Save as Spreadsheet..."
- **Unified scope logic:** both menu items use the same selection cascade (selected > visible). Not gated on `hasSelection` — always enabled when on Quotes tab
- **Desktop bridge:** update `exportQuotesCSV` Swift action to hit server endpoint, not build CSV client-side. One source of truth

---

## Implementation

### Shared extraction layer

New file: `bristlenose/server/export_core.py`

```python
@dataclass
class ExportableQuote:
    text: str
    participant_code: str
    participant_name: str
    section: str
    theme: str          # " / " joined if multiple
    sentiment: str
    tags: str           # ", " joined
    starred: bool
    timecode: str       # "mm:ss"
    session: str
    source_file: str
```

Single `extract_quotes_for_export(db, project_id, quote_ids=None)` function. Serves CSV, XLS, and future clip selection.

### Endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/projects/{id}/export/quotes.csv` | GET | `text/csv` with `Content-Disposition` |
| `/api/projects/{id}/export/quotes.xlsx` | GET | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |

Both accept optional `quote_ids` query parameter (comma-separated). Without it, returns all quotes.

**Note:** Project ID must come from route params, not hardcoded. See cross-cutting concerns in `design-export-html.md`.

### Source file column

Column 11 (`source_file`) is not in the current `GET /quotes` API response. Requires a join from `Quote` → `Session` → `SourceFile` in the extraction layer. Add `source_filename` to `ExportableQuote` via `SessionModel.source_files[0].path.name`.

### XLS details

- Sheet name: project name (truncated to 31 chars — Excel limit)
- Auto-filters on all columns
- Frozen header row
- Column widths: auto-fit based on content
- Library: `openpyxl`

### Dependencies

- `openpyxl` added to `pyproject.toml` `[serve]` extras (not core — only needed in serve mode)

### Files to create

| File | Purpose |
|------|---------|
| `bristlenose/server/export_core.py` | `ExportableQuote` dataclass + `extract_quotes_for_export()` |
| `bristlenose/server/routes/quotes_export.py` | CSV and XLSX endpoints |
| `tests/test_export_core.py` | Extraction layer tests |
| `tests/test_serve_quotes_export.py` | Endpoint tests |

### Files to modify

| File | Change |
|------|--------|
| `frontend/src/components/ExportDialog.tsx` | Add quotes export options |
| `frontend/src/utils/api.ts` | Add quotes export API functions |
| `pyproject.toml` | Add `openpyxl` to `[serve]` extras |
| `bristlenose/server/app.py` | Register quotes export routes |

### i18n

New keys needed in all 5 locale files (en, es, fr, de, ko):

- `export.copyQuotes` — "Copy Quotes"
- `export.saveAsSpreadsheet` — "Save as Spreadsheet..."
- `export.quotesCopied` — "{count} quotes copied"
- `export.exportingQuotes` — "Exporting {count} quotes from {sessions} sessions"
- `export.noQuotesMatch` — "No quotes match current filters"
- `export.pasteHint` — "Paste into Miro, Excel, or Google Sheets"

### Tests

- Extraction layer: verify all 11 columns populated correctly
- Theme concatenation with ` / ` separator
- Selection logic: selected vs visible, filter combinations
- CSV format: proper escaping, UTF-8 BOM for Excel compatibility
- XLSX: headers, auto-filters, frozen row, sheet name truncation
- Anonymisation: participant names removed, codes zero-padded
- Zero-results: appropriate error response
- Edge cases: empty quote text, very long text, special characters, quotes with no tags

---

## Decisions

1. **Two formats, shared core.** CSV is clipboard-optimised (instant, Miro-ready). XLS is the considered version (headers, auto-filters, frozen row). Same underlying data extraction.
2. **"Export what you see."** Selected quotes take priority, then all visible. Respects all active filters.
3. **Action-oriented labels.** "Copy Quotes" not "Copy CSV". "Save as Spreadsheet..." not "Save as XLS".
4. **Theme column uses ` / ` separator.** Readable in both CSV and XLS.
5. **openpyxl in `[serve]` extras.** Not a core dependency — only needed for serve-mode spreadsheet export.
6. **Server-side export, not client-side.** One source of truth. Desktop bridge hits the same endpoint. The vanilla JS `csv-export.js` is frozen (static render only).
7. **Inline hint, not tooltip.** "Paste into Miro, Excel, or Google Sheets" — trackpad users don't hover.
8. **Desktop scope logic unified.** Menu items not gated on `hasSelection` — always enabled on Quotes tab.
9. **Download filename uses `safe_filename()`** from `bristlenose/utils/text.py` — preserves spaces and case.

**Cross-cutting concerns** (anonymisation matrix, export audit logging, project ID, `safe_filename()`) are documented in `design-export-html.md`.

---

## Open questions

1. **Clipboard vs spreadsheet columns.** Should clipboard "Copy Quotes" use a simplified subset (quote, participant, section) for clean Miro stickies? Or use the full 11 columns with the inline hint "Paste into Excel, Numbers, or Google Sheets"? Current decision: one full format.
2. **UTF-8 BOM.** Excel on Windows needs a UTF-8 BOM (`\xef\xbb\xbf`) to correctly display non-ASCII characters in CSV. Add it? Probably yes.

---

## Verification

1. Copy Quotes from toolbar — paste into Google Sheets, verify all 11 columns
2. Copy Quotes — drag onto Miro board, verify stickies created with readable content
3. Save as Spreadsheet — open in Excel/Numbers, verify auto-filters and frozen header row
4. Test with starred-only filter active — verify only starred quotes exported
5. Test with tag filter active — verify only matching quotes exported
6. Test with search active — verify only matching quotes exported
7. Test with multi-selection — verify only selected quotes exported
8. Test with zero results — verify error message, no empty file
9. Test with anonymisation — verify participant names removed
10. Verify scope display: count shown in toolbar button, summary in dialog
11. `pytest tests/` + `ruff check .`

---

## Related docs

- `docs/design-export-html.md` — HTML report export
- `docs/design-export-clips.md` — video clip extraction
- `docs/design-miro-bridge.md` — Miro API integration (Tier 2+)
- `bristlenose/theme/js/csv-export.js` — existing vanilla JS CSV logic (reference)
- `docs/design-export-sharing.md` — original monolith (superseded, kept for git history)
