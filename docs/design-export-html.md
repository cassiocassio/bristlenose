# HTML Export — Design Document

Read-only HTML report export with transcript bundling, anonymisation, and polish.

**Status:** Shipped (v0.11.2 single HTML). Transcript zip and polish are next.

---

## Context

The HTML export is the "accountability copy" — a stakeholder or client can open it in any browser, no Bristlenose needed. It's not for the researcher's future analysis; it's for the record.

**Who it's for:**
- A PM or exec who wants the headline findings
- A client who needs proof the research was done
- A colleague who wants to browse without installing anything

**Core principle:** The recipient should never need to install Bristlenose. The output must be completely standalone.

---

## What exists today (v0.11.2)

- Self-contained HTML download (single file, all data embedded as JSON)
- Hash router for `file://` compatibility
- Blob-URL'd JS chunks
- Optional anonymisation (report data only)
- Basic ExportDialog with anonymise checkbox
- Works offline in any modern browser

**Known rough edges (from TODO "Export polish"):**
- Inline logo is a broken external reference (not base64)
- Footer has "Bristlenoseversion" missing space
- In-report navigation links fragile on hash router

---

## Design

### Polish items (Stage 0)

| Item | Detail |
|------|--------|
| Inline logo | Embed logo as base64 data URI — no external fetch |
| Footer spacing | Fix "Bristlenoseversion" → "Bristlenose version" |
| Nav links | Audit hash router links for `file://` compatibility |
| Purpose line | Add to ExportDialog: "Creates a standalone report that anyone can open in a browser. Recipients can view and search but cannot edit." |

### Stage 1: Zip with transcripts

Upgrade the single HTML file to a zip with a folder structure and transcript `.txt` files.

**Format is always zip** — even without transcripts, the export is a single-file zip. Users want a folder of well-named docs. They download a zip, drag it from Downloads into SharePoint/Dropbox in one swipe, expand it there. No single-HTML fallback needed.

**What the user sees (1:1 sessions):**

```
Acme Onboarding Research/
|-- report.html
+-- transcripts/
    |-- p1 Sarah.txt
    |-- p2 James.txt
    +-- p3 Priya.txt
```

**What the user sees (1:many sessions):**

```
Acme Onboarding Research/
|-- report.html
+-- transcripts/
    |-- 01 p1 Sarah p2 James.txt
    +-- 02 p3 Priya p4 Mike p5 Jo.txt
```

**Transcript format:** Plain text with inline timecodes. Opens in Notepad, searchable in Spotlight, pasteable into anything. No markup.

```
Acme Onboarding Research
p1 Sarah (Manager)
Recorded 14 Mar 2026 — 42 minutes

────────────────────────────────────────

[00:00] Moderator: Thanks for joining. Can you walk me through
your first day?

[00:15] Sarah: Sure. So I started on Monday, and honestly the
onboarding was really confusing.
```

**Transcript naming:**

| Session type | Filename format | Anonymised |
|-------------|----------------|------------|
| 1:1 | `{code} {name}.txt` | `p01.txt` |
| 1:many | `{session_nn} {code} {name} {code} {name}.txt` | `01 p01 p02.txt` |

**Anonymised transcript body:** Speaker labels use participant codes instead of names. Moderator names preserved (they're the research team, not subjects). Role titles removed entirely (can be identifying).

**Export dialog (Stage 1):**

```
+---------------------------------------------------+
|  Export report                                     |
+---------------------------------------------------+
|                                                    |
|  Creates a standalone report that anyone can       |
|  open in a browser. Recipients can view and        |
|  search but cannot edit.                           |
|                                                    |
|  [x] Include transcripts (.txt)                    |
|      Readable transcripts with timecodes.          |
|                                                    |
|  ------------------------------------------------  |
|                                                    |
|  [ ] Remove participant names from labels          |
|      Removes names from report metadata,           |
|      filenames, and transcript headers.             |
|      Keeps participant codes (p1, p2).              |
|      Moderator names preserved. Names within        |
|      quote text are NOT removed.                    |
|                                                    |
+---------------------------------------------------+
|                          [Cancel]    [Export]       |
+---------------------------------------------------+
```

Note: "Anonymise participants" renamed to "Remove participant names from labels" — the old label is a procurement blocker (overpromises).

### Stage 4: Branding footer (post-beta)

```html
<aside class="made-with">
  <strong>Made with Bristlenose</strong>
  <p>Turn interview recordings into research insights.
  Free, open source, runs on your laptop.</p>
  <a href="https://github.com/cassiocassio/bristlenose">
    github.com/cassiocassio/bristlenose
  </a>
</aside>
```

- Muted colours, doesn't compete with content
- Dark mode aware
- Hidden in print
- `--no-branding` flag for enterprise users

---

## Implementation

### Security fixes (done or in progress)

| Fix | Detail | Status |
|-----|--------|--------|
| `ensure_ascii=True` | Prevents `</script>` XSS breakout in `export.py:167` | Done |
| Path stripping | Strip absolute paths from exported `source_files[].path` — use `filename` only | Done |
| Anonymise label clarity | "Remove participant names from labels" + scope explanation | Done |

### Tasks

| Task | Description |
|------|-------------|
| 0.1 | Embed logo as base64 data URI in `export.py` |
| 0.2 | Fix footer spacing ("Bristlenose version") |
| 0.3 | Audit and fix hash router nav links for `file://` |
| 0.4 | Add purpose line to ExportDialog |
| 1.1 | Transcript renderer: API transcript data to `.txt` with inline timecodes. Reuse `markdown.py` formatting. Resolve speaker names from DB |
| 1.2 | Filename builder: 1:1 vs 1:many logic, anonymisation, zero-padding |
| 1.3 | Anonymisation pass for transcript body: swap display names for participant codes |
| 1.4 | Zip builder: Python `zipfile` — `{folder_name}/report.html` + `{folder_name}/transcripts/*.txt`. HTML compresses well (~70% reduction) |
| 1.5 | Update export endpoint: return `application/zip` with `Content-Disposition` |
| 1.6 | Update ExportDialog: add "Include transcripts (.txt)" checkbox (default ON), purpose line, renamed anonymise label |
| 1.7 | Tests: transcript rendering (timecodes, speaker names, anonymisation), zip structure, filename edge cases |

### Files to modify

| File | Change |
|------|--------|
| `bristlenose/server/routes/export.py` | Zip builder, base64 logo, path stripping |
| `frontend/src/components/ExportDialog.tsx` | Transcript checkbox, purpose line, anonymise label |
| `bristlenose/utils/markdown.py` | Reuse existing transcript formatting |

### Files to create

| File | Purpose |
|------|---------|
| `bristlenose/server/packager.py` | Zip builder, transcript renderer, filename builder |

### Existing infrastructure

The pipeline already writes `.txt` transcripts with inline timecodes:
- `bristlenose/utils/markdown.py` — formatting templates (`TRANSCRIPT_SEGMENT_RAW_TXT`, `format_timecode()`)
- `bristlenose/stages/s06_merge_transcript.py` — `write_raw_transcripts()`
- `bristlenose/stages/s07_pii_removal.py` — `write_cooked_transcripts()`

The export transcript renderer reuses these formatters. New work: human-readable filenames, speaker name resolution from DB, anonymisation pass on speaker labels.

---

## Decisions

1. **Zip is always the format.** Even without transcripts, the export is a zip. No single-HTML fallback. Users drag one file into SharePoint/Dropbox.
2. **Transcripts default ON.** Lightweight, always useful, instant. No reason to exclude.
3. **Anonymise label renamed.** "Remove participant names from labels" — accurate, not overpromising.
4. **Moderator names preserved.** They're the research team, not subjects.
5. **Role titles removed when anonymised.** "The one manager in the study" narrows the person down.
6. **ExportDialog project ID.** Current code hardcodes `1` at line 70. All new endpoints must use correct project ID from route params.
7. **Folder name uses `safe_filename()`** (from `bristlenose/utils/text.py`) — preserves spaces and case: `"Acme Onboarding Research"` not `"acme-onboarding-research"`. `slugify()` would lowercase and hyphenate.

---

## Cross-cutting concerns (shared across all export features)

This section is the canonical reference. The other export docs (`design-export-quotes.md`, `design-export-clips.md`, `design-miro-bridge.md`) reference it rather than duplicating.

### Anonymisation matrix

The "Remove participant names from labels" checkbox applies to HTML export, transcripts, clip filenames, and (future) Miro stickies. This is the full scope:

| Surface | What changes | What stays |
|---------|-------------|------------|
| Report HTML | Participant `full_name`/`short_name` → empty | Moderator/observer names, participant codes (p1, p2) |
| Report dashboard | Speaker names on session cards → empty | Codes, sentiment, journey labels |
| Report quotes | `speaker_name` → empty | Quote text (names WITHIN text are NOT removed), tags, stars |
| Transcript filenames | `p1 Sarah.txt` → `p01.txt` | Zero-padded codes |
| Transcript body | Speaker labels use codes, not names | Moderator names, timecodes |
| Clip filenames | `p1 03m45 Sarah gist.mp4` → `p01 03m45 gist.mp4` | Timecodes, gist |
| XLS/CSV | Participant name column → empty | All other columns |
| Miro stickies (future) | Speaker name omitted | Participant code, timecode |

**What anonymisation does NOT do:**
- Does not remove names mentioned inside quote text ("Sarah told me she was confused")
- Does not redact audio/video content in clips (voices, faces)
- Does not replace `--redact-pii` (Presidio-based content redaction — separate pipeline stage)

### Export audit logging

Every export action should be logged for accountability and debugging:

| Field | Example |
|-------|---------|
| Timestamp | `2026-03-25T14:30:00Z` |
| Export type | `html`, `csv`, `xlsx`, `clips`, `miro` |
| Anonymised | `true` / `false` |
| Quote count | `47` |
| Session count | `3` |
| Settings | `{transcripts: true, clips: false}` |

**Implementation:**
- Log to persistent log file (`bristlenose.log`) via existing logging infrastructure (see `docs/design-logging.md`)
- Add `ExportLog` SQLite table for queryable audit trail
- Both implementations share the same data shape — log first, DB table when needed

### Project ID

`ExportDialog.tsx` line 70 hardcodes project ID `1`. **All new export endpoints must use project ID from route params** (`/api/projects/{id}/export/...`). This applies to quotes CSV/XLS, clips, transcripts, and Miro export — not just HTML.

### `safe_filename()` utility (`bristlenose/utils/text.py`)

Shared filename sanitiser for all export features. Preserves spaces, case, and accents. Strips path separators, traversal sequences, null bytes, and Windows-illegal chars. 21 adversarial tests. Used by:
- Zip folder name (HTML export)
- Transcript filenames
- Clip filenames
- XLS download filename

### Shared infrastructure — what to build once

These abstractions serve multiple export features. Build them during item 0 (security) or item 2 (quotes CSV/XLS) and reuse everywhere:

| Abstraction | Location | Used by | Notes |
|-------------|----------|---------|-------|
| `safe_filename(text, max_length)` | `bristlenose/utils/text.py` | HTML zip folder, transcript filenames, clip filenames, XLS download name | **DONE.** 21 tests. |
| `ExportableQuote` dataclass | `bristlenose/server/export_core.py` | Quotes CSV/XLS, clip manifest builder, Miro sticky content | Single extraction query with all 11 columns. Clips filter by `starred`/`is_hero`. Miro formats differently but reads same data. |
| `extract_quotes_for_export(db, project_id, quote_ids?)` | `bristlenose/server/export_core.py` | CSV endpoint, XLS endpoint, clip manifest, Miro export | The one query that joins Quote → Session → SourceFile → QuoteState → QuoteTag. Every consumer filters/formats the result. |
| `anonymise_export_data(data)` | `bristlenose/server/routes/export.py` | HTML export, transcript body, clip filenames, XLS name column, Miro stickies | Already exists as `_anonymise_data()`. Extend to cover new surfaces (transcript speaker labels, clip filename speaker removal, XLS name column blanking). Keep as one function with the matrix above as its spec. |
| `build_export_filename(participant, timecode, speaker, gist, ext, anonymised)` | `bristlenose/server/export_core.py` | Clip filenames, transcript filenames | Shared naming logic: zero-padding, timecode formatting, `safe_filename()` application. Clips and transcripts both need participant-code-prefixed filenames. |
| `ExportAuditLogger` | `bristlenose/server/export_core.py` | All 5 export types | Wraps both log-file and (future) DB writes. Each export calls `log_export(type, settings, counts)` after success. |
| `ExportDropdown` component | `frontend/src/components/ExportDropdown.tsx` | Toolbar (serve mode) | Tab-contextual menu. Quotes tab → Copy Quotes / Save as Spreadsheet / Export Report / Extract Clips. Other tabs → Export Report. Each feature adds its entry when it ships. |
| `AsyncExportToast` component | `frontend/src/components/` | Clip extraction, (future) Miro export | Generalised from AutoCodeToast pattern. Progress bar, cross-tab persistence, completion action (Reveal / Open in Miro). Parameterised by label and action. |
| Scope display helper | `frontend/src/utils/exportScope.ts` | Toolbar button label, export dialog summary, toast confirmation | `getExportScope(selectedIds, visibleCount, filters) → { count, label, detail }`. One function, reused by every export action. |

**Build order:** `safe_filename` → `export_core.py` (ExportableQuote + extract) → `build_export_filename` → `ExportDropdown` → scope helper → `AsyncExportToast` → `ExportAuditLogger`.

---

## Open questions

1. **Locked read-only mode.** Exported reports currently allow recipient editing (localStorage). Future: option to disable editing for stakeholder-facing packages.
2. **VTT transcript format.** Useful for re-import and subtitle tooling. Add as an option alongside `.txt` if researchers ask. Not needed for any current scenario.

---

## Verification

1. Export with transcripts ON and OFF — verify zip structure
2. Open `report.html` from the unzipped folder in Chrome, Firefox, Safari — verify all content renders, logo displays, footer spacing correct
3. Open `report.html` via `file://` — verify hash router nav links work
4. Verify transcript `.txt` files: timecodes, speaker labels, header format
5. Export with anonymisation ON — verify names removed from report, transcript filenames, transcript body. Verify moderator names preserved
6. Test with 1:1 and 1:many session projects
7. Test filename edge cases: long names, special characters, 10+ participants (zero-padding)
8. `pytest tests/` + `ruff check .`

---

## Related docs

- `docs/design-export-clips.md` — video clip extraction
- `docs/design-export-quotes.md` — CSV/XLS quotes export
- `docs/design-miro-bridge.md` — Miro API integration
- `docs/design-export-sharing.md` — original monolith (superseded, kept for git history)
