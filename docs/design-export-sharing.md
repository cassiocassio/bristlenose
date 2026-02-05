# Export and Sharing — Design Document

Reference doc for making Bristlenose reports shareable. Covers the export feature, anonymisation, media handling, and the phased implementation plan.

## Problem Statement

Users curate their reports in the browser — starring quotes, editing text, adding tags, renaming participants. They want to share this curated view with colleagues who don't have Bristlenose installed.

**Current barriers:**

1. **Edits live in localStorage** — tied to the browser and file path origin
2. **Media paths are absolute** — `file:///Users/cassio/interviews/video.mp4` breaks on any other machine
3. **No single "share this" action** — user must manually understand what to copy

**Core principle:** The recipient should never need to install Bristlenose. The output must be completely standalone.

## Audience Tiers

| Audience | What they need | Anonymisation? |
|----------|----------------|----------------|
| Managers, PMs, engineers | Curated findings, maybe video evidence | Often yes |
| Fellow researchers | Full transcripts, all media, people.yaml | Usually no |

This maps to two export modes:

- **Report only** — curated HTML with optional video clips of starred quotes
- **Full archive** — everything, for project handoff

## Export Dialog

```
┌─────────────────────────────────────────────────┐
│  Export report                                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ○ Report only                                  │
│    Starred quotes with your edits.              │
│    ☐ Include video/audio clips of starred       │
│      quotes                                     │
│                                                 │
│  ○ Full archive                                 │
│    Report + transcripts + all media files.      │
│    Useful for further analysis.                 │
│                                                 │
│  ─────────────────────────────────────────────  │
│                                                 │
│  ☐ Anonymise participants                       │
│    Remove participant names, keep codes (p1,    │
│    p2). Moderator names are preserved.          │
│                                                 │
├─────────────────────────────────────────────────┤
│                           [Cancel]   [Export]   │
└─────────────────────────────────────────────────┘
```

**Logic:**

- "Include video/audio clips" checkbox only enabled when "Report only" is selected
- "Anonymise participants" available for Report only; greyed out for Full archive (researcher handoff assumes full access)

## What Each Export Contains

### Report only

| Item | Included |
|------|----------|
| Curated HTML report | Yes (with embedded state) |
| Transcript pages (HTML) | Yes |
| CSS and logos | Yes (inlined or in assets/) |
| Raw transcript files (.txt, .md) | No |
| people.yaml | No |
| Intermediate JSON | No |
| Media files | No (unless clips checkbox selected) |

### Report only + clips

Same as above, plus:

| Item | Included |
|------|----------|
| Video/audio clips of starred quotes | Yes (trimmed, in media/clips/) |

**Note:** Clips require a CLI step for the curator (FFmpeg). The recipient still needs nothing.

### Full archive

| Item | Included |
|------|----------|
| Curated HTML report | Yes (with embedded state) |
| Transcript pages (HTML) | Yes |
| CSS and logos | Yes |
| Raw transcript files (.txt, .md) | Yes |
| people.yaml | Yes |
| Intermediate JSON | Yes |
| All media files | Yes |

This is a complete project handoff. Fellow researcher can re-render, continue analysis, or pick up where you left off.

## Anonymisation

The "Anonymise participants" checkbox provides a lightweight anonymisation for sharing externally. It is **not** a replacement for `--redact-pii`.

**What it strips:**

- `full_name` and `short_name` for participant codes (p1, p2, etc.)
- Names from the `BN_PARTICIPANTS` embedded JSON
- Names from the embedded `CURATED_STATE`
- Display names in the DOM (participant table, anywhere names are shown)

**What it keeps:**

- Moderator names (m1, m2) — they're the research team, not subjects
- Observer names (o1) — same logic
- Raw participant codes (p1, p2) — these are the anonymised identifiers
- All quote text, tags, stars, edits
- Names mentioned within quote text (use `--redact-pii` for that)
- Names in user-edited headings (user's responsibility)

**When greyed out:**

- Full archive mode (researcher handoff assumes full access)
- Reports generated with `--redact-pii` (already anonymised — checkbox pre-checked and disabled)

## Technical Architecture

### State Hydration

**Current:** JS reads localStorage on page load.

**New:** JS checks for embedded `CURATED_STATE` first, then overlays localStorage on top.

```javascript
const embedded = window.CURATED_STATE || {};
const local = loadFromLocalStorage();
const state = merge(embedded, local);  // local wins on conflict
```

This allows:
- Recipients to see the curator's state immediately
- Recipients to make their own edits (saved to their localStorage)
- Round-trip: recipient could re-export with their additions

**State schema:**

```javascript
CURATED_STATE = {
  version: 1,
  favourites: { "q-p1-42": true, "q-p2-187": true },
  edits: { "q-p1-42": "Edited quote text..." },
  tags: { "q-p1-42": ["key-insight", "onboarding"] },
  deletedBadges: { "q-p3-99": ["doubt"] },
  names: { "p1": { full_name: "Sarah", short_name: "S", role: "Manager" } }
}
```

Version field enables future schema migrations.

### Media Paths

**Current:** `BRISTLENOSE_VIDEO_MAP` contains absolute `file://` URIs.

```javascript
BRISTLENOSE_VIDEO_MAP = {
  "s1": "file:///Users/cassio/interviews/session1.mp4"
}
```

**New:** Support relative paths when media is in the output folder.

```javascript
BRISTLENOSE_VIDEO_MAP = {
  "s1": "media/session1.mp4"
}
```

Triggered by:
- `--include-media` flag at render time (copies files, uses relative paths)
- `--portable` flag (uses relative paths assuming media will be copied manually)

**Fallback:** If media file is missing at the relative path, timecodes degrade gracefully (grey, non-clickable, or show "media not available").

### Browser-Side Export

For "Report only" (no clips), everything happens in the browser:

1. Serialise all `bristlenose-*` localStorage keys into JSON
2. If anonymise checked, strip participant names from state and `BN_PARTICIPANTS`
3. Clone the HTML document (or reconstruct from source)
4. Inject `<script>var CURATED_STATE = {...}</script>`
5. Fetch transcript pages via relative URLs
6. Bundle into zip using fflate (~8KB library)
7. Trigger download

No server, no CLI, instant export.

### Clips Manifest

For "Include clips" option, browser generates a manifest file:

```json
{
  "version": 1,
  "exported_at": "2026-02-05T14:32:00Z",
  "state": {
    "favourites": { "q-p1-42": true },
    "edits": {},
    "tags": {},
    "deletedBadges": {},
    "names": {}
  },
  "clips": [
    {
      "session": "s1",
      "source": "../session1.mp4",
      "start": 39,
      "end": 52,
      "quote_id": "q-p1-42"
    }
  ],
  "options": {
    "padding_before": 3,
    "padding_after": 2,
    "anonymise": true
  }
}
```

Browser shows instructions:

```
To include video clips, run:

  bristlenose package bristlenose-output/

Then share the generated zip.
```

The `bristlenose package` command reads the manifest, extracts clips via FFmpeg, and assembles the final zip.

### Clip Extraction

**FFmpeg command pattern:**

```bash
ffmpeg -i input.mp4 -ss 36 -to 52 -c copy output.mp4
```

- `-ss 36` — start 3 seconds before quote (padding)
- `-to 52` — end 2 seconds after quote
- `-c copy` — stream copy (fast, no re-encoding)

**Adjacent clip merging:** If two starred quotes are within 10 seconds of each other, merge into one clip to avoid awkward cuts.

**Output structure:**

```
media/clips/
  s1_00m39s.mp4
  s1_02m15s.mp4
  s2_05m22s.mp4
```

**Player update:** For clip-based exports, `BRISTLENOSE_VIDEO_MAP` points to clips. Player seeks to the quote's offset within the clip (accounting for padding).

## Branding Footer

Every report includes a subtle CTA at the bottom:

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

**Styling:**
- Muted colours, doesn't compete with content
- Subtle top border separating from coverage section
- Dark mode aware
- Hidden in print (via `print.css`)

**Rationale:** The recipient is looking at the output — perfect context for discovery. Their colleague (a researcher they trust) used it and thought it worth sharing. Low-friction awareness.

**Optional suppression:** `--no-branding` flag for enterprise users who've contributed back. Or accept it as the "price" of free software.

## Implementation Plan

### Phase 0: Foundation (no user-visible changes)

| Step | Description |
|------|-------------|
| 0.1 | State hydration architecture: check `CURATED_STATE` before localStorage |
| 0.2 | Relative media path option: `--portable` flag or default behaviour |
| 0.3 | Audit all embedded data for shareability concerns |

### Phase 1: Save curated report (browser-only)

| Step | Description |
|------|-------------|
| 1.1 | "Save" button in toolbar: serialise localStorage, inject into HTML, download |
| 1.2 | Anonymise checkbox: strip participant names from state and embedded JSON |
| 1.3 | Export dialog modal UI |

### Phase 2: Include transcript pages

| Step | Description |
|------|-------------|
| 2.1 | Bundle transcript pages into zip using fflate |
| 2.2 | Fix relative paths in bundled HTML files |
| 2.3 | Optional: inline CSS/logos for true single-file output |

### Phase 3: Full archive

| Step | Description |
|------|-------------|
| 3.1 | `--include-media` flag at render time (copies files into output) |
| 3.2 | Full archive export from browser (if media already present) |
| 3.3 | Include people.yaml in full archive zip |

### Phase 4: Video clips (requires CLI for curator)

| Step | Description |
|------|-------------|
| 4.1 | Browser writes `clips-manifest.json` with starred quote timecodes |
| 4.2 | `bristlenose package` command: read manifest, extract clips via FFmpeg |
| 4.3 | Update player to use clip-relative seeking |
| 4.4 | Merge adjacent clips (within 10 seconds) |

### Phase 5: Branding footer (independent)

| Step | Description |
|------|-------------|
| 5.1 | "Made with Bristlenose" CTA in report footer |
| 5.2 | Styling (muted, dark mode aware, print hidden) |

### Suggested Order

```
Phase 5 → Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4
```

**Rationale:**
- Phase 5 is independent and quick — ship early for brand awareness
- Phase 0 is foundation — no visible changes but unblocks everything
- Phase 1 is core value — basic export with anonymise
- Phase 2 completes "Report only" — transcript pages included
- Phase 3 enables researcher handoff — full archive
- Phase 4 is power feature — clips require CLI, can wait

### Dependency Graph

```
Phase 0.1 (state hydration) ─┬─► Phase 1 (save button)
                             │
Phase 0.2 (relative paths) ──┼─► Phase 3 (include media)
                             │
Phase 0.3 (audit) ───────────┘

Phase 1 ─────────────────────► Phase 2 (transcript pages)

Phase 2 ─────────────────────► Phase 3 (full archive)

Phase 3 ─────────────────────► Phase 4 (clips)

Phase 5 (branding) ──────────► Independent, ship anytime
```

## Long-term Considerations

### State Schema Versioning

As the app evolves, `CURATED_STATE` shape will change. The `version` field enables migrations:

```javascript
function hydrateState(embedded) {
  if (embedded.version === 1) {
    return migrateV1toV2(embedded);
  }
  return embedded;
}
```

### Large File Limits

Browser zip generation is comfortable up to ~500MB. Beyond that:
- Show a warning for Full archive exports
- Suggest manual zipping for very large projects
- Or fall back to CLI: `bristlenose package --full-archive`

### Shallow vs. Deep Anonymisation

The checkbox is shallow — metadata only. Names in quote text or user-edited headings remain. Clear messaging needed:

> "Anonymise removes participant names from the report metadata. Names mentioned in quote text are not affected — use `bristlenose run --redact-pii` for deeper anonymisation."

### Offline Playback

If media is present and paths are relative, playback works offline. If media is missing:
- Timecodes should degrade gracefully
- Grey styling, non-clickable
- Tooltip: "Media file not included"

### Recipient Editing

Recipients can make their own edits (localStorage still works). Their edits overlay the embedded state. This enables collaborative curation:
- Original researcher stars 20 quotes
- Manager stars 5 more, adds comments
- Manager re-exports with their additions

Future consideration: "locked" mode for read-only sharing.

### Collaboration and Merge

Out of scope for now, but the JSON state format makes merge theoretically possible. Two curators could export, and a third could merge their states.

## Open Questions

1. **Default to relative paths?** Or keep absolute and add `--portable`? Recommendation: default to relative if feasible, absolute as fallback.

2. **Single HTML vs. zip for Phase 1?** Single is simpler to share but breaks transcript links. Recommendation: start with single HTML, add zip option in Phase 2.

3. **Clip padding defaults?** 3 seconds before, 2 after feels right. Should it be configurable in the UI or just sensible defaults?

4. **Export button placement?** Toolbar alongside Copy CSV? Or a more prominent position given its importance?

5. **Filename convention?** `{project}-curated.html`? `{project}-report-{date}.zip`?

## Related Files

- `bristlenose/theme/js/storage.js` — localStorage abstraction
- `bristlenose/theme/js/*.js` — all state-mutating modules
- `bristlenose/stages/render_html.py` — HTML generation, embedded globals
- `bristlenose/output_paths.py` — path construction
- `docs/design-html-report.md` — report architecture reference
