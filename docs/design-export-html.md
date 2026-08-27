---
status: partial
last-trued: 2026-08-22
trued-against: HEAD@main (ff444036) on 2026-08-22
---

# HTML Export — Design Document

> **Trued 2026-07-26** against the export-hardening work (commits `8895c794`
> single-file build, `4f0b9855` hash-router links, `30c5c2f7`/`22980677` locale
> bake, `427cfc6a` anti-drift coverage gate, `bac75661` XSS fix, `a2880e7e`
> read-only). Several "future pass" / "open question" items below shipped this
> session and are marked Done inline. Transcript-zip bundling (Stage 1+) remains
> aspirational.

> **Truing status:** Current with targeted edits (trued 2026-08-22).
> §"Open questions" item 1 was rewritten — it claimed the export had been
> "fully read-only" since 26 Jul, which was measurably false until `cb4f1e28`
> (20 Aug). The rest of the body is verbatim-accurate. See changelog below.

## Changelog

- _2026-08-22_ — trued up: rewrote §"Open questions" item 1, which summarised the
  export as fully read-only from 26 Jul while three mutation paths stayed live
  until 20 Aug (`denyProposedTag` ungated, five `export.css` selectors matching
  nothing, the codebook "+ tag" row hidden only by one of them). Original claim
  preserved inline as the 26 Jul baseline. Front-matter had reported
  `last-trued: 2026-07-26` while the body already carried the 20 Aug selector-gate
  bullet. Anchors: `bristlenose/theme/templates/export.css`,
  `tests/test_export_css_selectors.py`, `frontend/src/contexts/QuotesContext.tsx:383`,
  `frontend/src/islands/CodebookPanel.tsx:449`, commit subject "export mode: five
  selectors that matched nothing, and a gate so they can't again".
- _2026-07-26_ — trued up against the export-hardening work (single-file build,
  hash-router links, locale bake, anti-drift coverage gate, XSS fix, read-only).

Read-only HTML report export with transcript bundling, anonymisation, and polish.

**Status:** Shipped and hardened. The self-contained export renders from `file://`
via a **single inline module** (not blob-URL'd chunks — those are blocked from an
opaque origin), is **read-only** (mutating controls stripped), **XSS-safe**, baked
to the **researcher's locale**, and guarded by a **link-integrity crawl** + an
**anti-drift coverage gate**. Transcript-zip bundling (Stage 1+) is still
aspirational.

---

## Context

The HTML export is the "accountability copy" — a stakeholder or client can open it in any browser, no Bristlenose needed. It's not for the researcher's future analysis; it's for the record.

**Who it's for:**
- A PM or exec who wants the headline findings
- A client who needs proof the research was done
- A colleague who wants to browse without installing anything

**Core principle:** The recipient should never need to install Bristlenose. The output must be completely standalone.

---

## What exists today

- Self-contained HTML download (single file, all data embedded as path-keyed JSON
  under `window.BRISTLENOSE_EXPORT.endpoints`)
- Hash router for `file://` compatibility; every intra-app `<a href>` goes through
  `reportHref()` (`#`-prefixed offline) — plain pathname URLs broke Cmd+click/new-tab
- **Single inline `<script type="module">` bundle** from a dedicated build
  (`frontend/vite.export.config.ts`, `codeSplitting:false`) — replaced the blob-URL'd
  chunk bootstrap, which browsers block as module scripts from an opaque `file://`
  origin (the reason the export never rendered from disk before `8895c794`)
- **Anti-drift coverage gate** (`tests/test_serve_export_coverage.py`) — every GET
  read endpoint is EMBED or explicitly SERVER_ONLY, so a new endpoint is
  offline-by-default and can't silently drift
- **Read-only**: mutating affordances (star/hide/tag/edit, codebook authoring) gated
  at the store-action layer; `apiGet` fails loud on an uncovered read offline
- **Anti-drift selector gate** (`tests/test_export_css_selectors.py`) — the CSS half
  of read-only (`theme/templates/export.css`) can't fail loudly on its own, so every
  class it hides must still be rendered somewhere in `frontend/src`. Renaming a
  control now fails the build instead of silently un-hiding it in every export.
  Added 15 Aug 2026 after five selectors were found stale at once (`.badge-accept`,
  `.bn-counter`, `.bn-tag-input`, `.codebook-add-tag`, `.codebook-picker-btn`);
  matching is whole-class-token, because `.badge-accept` substring-matches the live
  `badge-accept-flash` and a naive search would have passed the original bug
- **Locale baked** to the researcher's current UI language (not the recipient's browser).
  Note the cost, measured 23 Aug 2026: the single-file build inlines **all 22 locales × 9
  namespaces** (1,802 KB, ~half the export) so the baked one is available offline. Making
  that a choice at export time, and carrying one language, is proposed in
  [`design-export-locale.md`](design-export-locale.md).
- Optional anonymisation (report data + source filenames)
- Works offline in any modern browser (Chromium + WebKit e2e, incl. a link-integrity crawl)

---

## Design

### Polish items (Stage 0) — done

| Item | Status | Detail |
|------|--------|--------|
| Inline logo | Done | Light + dark logos base64-embedded in export payload, Footer + Header read from `BRISTLENOSE_EXPORT.logos` in export mode |
| Footer spacing | Done (already fixed) | React Footer.tsx `{" "}` provides correct spacing; the Jinja2 bug doesn't affect exports (React path used) |
| Nav links | Done (`4f0b9855`) | The pathname-URL problem was broader than Dashboard/SessionsTable (also Analysis, Sessions sidebar, AutoCode proposals). Fixed with a shared `reportHref()` helper (`#`-prefix offline) routed through every intra-app `<a href>`; journey clicks use a router-agnostic `navigate({pathname,hash})`. Guarded by an e2e link-integrity crawl that follows every internal link + asserts no browser-router path |
| Purpose line | Done | `export.subtitle` updated in all 6 locales (en, es, fr, de, ko, ja) |

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

**Anonymised transcript body:** Speaker labels use participant codes instead of names. Moderator *and observer* names preserved — the boundary is participant / not-participant, not team membership (`design-people.md` §E decision 2, settled 25 Aug 2026). Role titles removed entirely (can be identifying).

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
| Escape `<` `>` `&` in the data script | **`ensure_ascii=True` does NOT prevent `</script>` breakout** — it escapes only code points > 127; `<` is ASCII and passes through. The earlier belief was false (`bac75661`). After `json.dumps(ensure_ascii=True)`, chain `.replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")`. Regression test `test_embedded_data_cannot_break_out_of_script`. **Audit sibling embed sites** (serve `/report`, quote CSV/HTML) for the same false belief | Done (`bac75661`) |
| Path stripping | Strip absolute paths from exported `source_files[].path` — use `filename` only | Done |
| Anonymise source filenames | Neutralise `source_files[].filename` to `<session_id><ext>` under anonymise — `jane-doe.mov` otherwise re-carries the name (`5379e3df`) | Done |
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
5. **Role titles removed when anonymised.** "The one manager in the study" narrows the person down. **Implemented 25 Aug 2026** — `_anonymise_data` now blanks `role` alongside the names for `p*` codes, pinned by `test_anonymise_strips_participant_job_titles`. Participant-side only: moderators and observers keep their titles, because the boundary is the participant line and they are named anyway (`design-people.md` §E decision 2).
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

1. ~~**Locked read-only mode.**~~ **Shipped 2026-07-26 (`a2880e7e`), completed
   2026-08-20 (`cb4f1e28`).** Decided (user): a baked handover shouldn't offer the
   pretence of editing.

   The 26 Jul pass recorded this as settled — "the export is fully read-only —
   mutating store actions (star/hide/tag/edit) early-return offline, the two bypass
   paths (quote-text click, keyboard) are gated, and the Codebook tab is read-only."
   That was the intent, not the state. Three paths stayed live for ~3.5 weeks:

   - `denyProposedTag` had no `isExportMode()` guard, though its sibling
     `acceptProposedTag` did. Clicking ✗ on an autocode proposal removed it
     optimistically and POSTed to a server that isn't there.
   - Five `export.css` selectors named classes nothing rendered. The worst pair,
     `.badge-accept` / `.badge-deny`, had been renamed to `.badge-action-accept` /
     `.badge-action-deny` by the badge-action-pill redesign, so the accept/deny
     control was **visible and clickable** in every export from that rename onward.
   - The codebook "+ tag" row is gated by `!isFramework`, never by `isReadOnly` —
     one of those dead CSS rules was the only thing hiding it.

   Two lessons encoded rather than recorded. **CSS is not the load-bearing half:**
   the per-project baked theme copy can be stale, and `display:none` leaves handlers
   and key bindings live — `denyProposedTag` binds a document-level `d` while the
   badge is hovered, which no rule can reach. Mutation controls are now *removed*
   under `isExportMode()`, not hidden. **And a pure-CSS gate cannot fail loudly:**
   `tests/test_export_css_selectors.py` asserts every class `export.css` hides is
   still rendered in `frontend/src`, matching on whole class tokens because
   `.badge-accept` substring-matches the live `badge-accept-flash`.
2. **VTT transcript format.** Useful for re-import and subtitle tooling. Add as an option alongside `.txt` if researchers ask. Not needed for any current scenario.
3. **Video in the export (v1/v2).** v1 ships no video/thumbnails. v2 middle-ground =
   "report + starred clips have working video" (inline `<video src="clips/…">` packaged
   alongside — the deferred "Stage 3", `design-export-clips.md`). Reuses the quote
   identity/timecode data already embedded — no re-plumbing. Distinct from the deprecated
   static-render `_build_video_map`→`file://`-to-local-originals (same-machine only, leaks
   absolute paths).

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
