# Video Clip Extraction — Design Document

Extract trimmed video clips of key quotes for stakeholder playback and slide decks.

**Status:** Not started. Design complete. Separate standalone feature.

---

## Context

Researchers spend hours in Final Cut Pro scrubbing through footage to find 15-second moments for stakeholder playbacks. Bristlenose already knows exactly where every quote starts and ends. This feature turns "3 hours of Final Cut Pro" into seconds.

**Who it's for:**
- A researcher preparing clips for a stakeholder playback or slide deck
- Anyone in a meeting who says "play me the one about onboarding"
- A researcher who wants a folder of clips visible as thumbnails in Finder

**Core insight:** The clip is the value add. The researcher already has the full recordings. What they don't have is precise in/out points trimmed to individual quotes.

---

## What exists today

- Bristlenose stores timecodes for every quote (start/end seconds)
- `bristlenose/utils/video.py` — existing FFmpeg integration (thumbnail extraction)
- `bristlenose doctor` — already checks for FFmpeg on PATH
- No clip extraction feature

---

## Design

### Clip selection

```
clip pool = starred quotes UNION signal card hero quotes
```

| Source | Who chose it | Typical count | Has timecode? |
|--------|-------------|---------------|---------------|
| Starred quotes | Researcher (manual) | 10-30 | Yes |
| Signal card heroes | Pipeline (`_pick_featured_quotes()`) | Up to 9 | Yes |
| Overlap | Both | Some | — |

The union typically lands at 20-40 clips, ~5-8 minutes of footage total (~60-100MB).

**Adjacent merge:** If two clips from the same session are within 10 seconds of each other, merge into one clip. Merged clip keeps the first quote's name.

**Padding:** 3 seconds before the quote, 2 seconds after.

### Two extraction backends

| Backend | Platform | How | FFmpeg required? |
|---------|----------|-----|------------------|
| FFmpeg stream-copy | CLI (all platforms) | `ffmpeg -ss {start} -to {end} -c copy` | Yes |
| AVFoundation | macOS desktop app | Native framework — Macs are excellent at video snipping | No |

The CLI path uses FFmpeg stream-copy (fast, no re-encoding). The macOS desktop app uses native AVFoundation — no FFmpeg dependency. `bristlenose doctor` already checks for FFmpeg; disable clips if missing with explanation.

```bash
# FFmpeg command
ffmpeg -i input.mp4 -ss 36 -to 54 -c copy output.mp4
```

### Clip naming

The researcher is looking at 5-15 clips in a Finder window, deciding which 3 to play at the meeting. The filename is the only information they have without opening each one.

**Format:** `{code} {timecode} {speaker} {gist}.{ext}`

```
Good:  p1 03m45 Sarah onboarding was confusing.mp4
Bad:   s1_00m39s.mp4
Bad:   clip-q-p1-42.mp4
```

| Component | Source | Example |
|-----------|--------|---------|
| Code | Participant code from quote | `p1`, `p3` |
| Timecode | Quote start | `03m45`, `0h03m45` |
| Speaker | Display name (short_name) | `Sarah`, `James` |
| Gist | First ~6 words of quote text | `onboarding was confusing` |

**Timecode format:**
- Sessions under 1 hour: `{mm}m{ss}` — e.g. `03m45`
- If *any* session in the project exceeds 1 hour: all timecodes switch to `{h}h{mm}m{ss}` — e.g. `0h03m45`, `1h02m10`

The format is chosen per-export based on `max(duration_seconds)` across all sessions. This keeps lexical sort = chronological sort.

**Gist rules:**
- First ~6 words of quote text
- Lowercase
- Strip `' ' " " ? ! . , ; : ( )`
- Spaces preserved (not converted to hyphens)
- Max ~40 characters, break at word boundary
- No Windows-illegal characters (no `: ? * < > | "`)

**When anonymised:**

Speaker name removed. Participant code zero-padded:

```
p01 03m45 onboarding was confusing.mp4
p01 17m02 i gave up after day two.mp4
p02 02m15 search never finds anything.mp4
```

### Participant code zero-padding

Applied in the export layer only, based on participant count:

| Participants | Padding | Example |
|-------------|---------|---------|
| 1-9 | No padding | `p1`, `p2` |
| 10-99 | 2 digits | `p01`, `p02` |
| 100+ | 3 digits | `p001` (unlikely) |

### Async job with toast progress

Reuse the persistent cross-tab toast from codebook application (AutoCodeToast pattern):

1. User triggers clip extraction (dialog or CLI)
2. Dialog closes. Toast appears: "Extracting clips... (3 of 15)"
3. Toast updates with progress as clips complete
4. Toast persists across tab switches
5. On completion: "Clips ready" with "Reveal in Finder" link
6. "Reveal" calls `open -R /path/` (macOS) or `xdg-open` parent dir (Linux)

### Menu placement

**File menu, not Video menu.** Video menu is playback control (play, pause, skip). Export actions belong in File menu grouped with other exports. This matches Final Cut Pro and HIG.

**Serve-mode export dropdown:** Add "Extract Video Clips..." to the tab-contextual dropdown on the Quotes tab (see `design-export-quotes.md` for the dropdown design). Dimmed if no media files in project.

**Project ID:** Must come from route params, not hardcoded. See cross-cutting concerns in `design-export-html.md`.

### CLI

```bash
# Extract clips
bristlenose export --clips interviews/

# With anonymisation
bristlenose export --clips --anonymise interviews/
```

CLI shows Cargo-style progress:

```
  Exporting Acme Onboarding Research
  ✓ Clip 1/15: p1 03m45 Sarah                   0.8s
  ✓ Clip 2/15: p2 02m15 James                   0.6s
  ...
  ✓ Clips complete (15 clips)                   12.3s

  → clips/ (47 MB)
```

### Audio-only sessions

Extract as-is. FFmpeg stream copy preserves container format. If source is `.mp3`, clip is `.mp3`. Filename follows the same pattern. No video frame — audio-only playback.

### Size estimates and warnings

| Clip count | Estimated size | Notes |
|-----------|---------------|-------|
| 15 clips | 30-80 MB | ~15s each, stream copy from source |
| 40 clips | 80-200 MB | Upper bound for large studies |

If clip count exceeds 50 or estimated zip exceeds 500 MB, show warning in dialog. Warn but don't block.

---

## Implementation

### Data model

```python
@dataclass
class ClipSpec:
    quote_id: str           # "q-p1-42"
    participant_id: str     # "p1"
    session_id: str         # "s1"
    source_path: Path       # absolute path to source media
    start: float            # seconds (with padding applied)
    end: float              # seconds (with padding applied)
    speaker_name: str       # display name (or "" if anonymised)
    quote_gist: str         # first ~6 words, lowercase, spaces
    is_starred: bool
    is_hero: bool           # signal card hero
```

### `safe_filename()` utility (DONE — `bristlenose/utils/text.py`)

Shared across all export features. Strips path separators, traversal sequences, null bytes, and Windows-illegal chars while preserving spaces, case, and accents. 21 adversarial tests in `tests/test_text_utils.py`.

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/projects/{id}/export/clips` | POST | Start async clip extraction job |
| `GET /api/projects/{id}/export/clips/status` | GET | Job progress: `{state, progress, total, current_clip}` |

### Tasks

| Task | Description |
|------|-------------|
| 2.1 | Clip manifest builder: query starred quotes + `_pick_featured_quotes()` heroes, deduplicate, apply padding |
| 2.2 | Adjacent clip merge: if two clips from same session are within 10s, merge into one |
| 2.3 | Clip filename builder: `{code} {timecode} {speaker} {gist}.{ext}`, anonymisation, zero-padding |
| 2.4 | FFmpeg wrapper: `ffmpeg -i {source} -ss {start} -to {end} -c copy {output}`. Skip missing media gracefully (warning, no error). Preserve source container format |
| 2.5 | Async job runner: reuse AutoCode `asyncio.create_task()` pattern |
| 2.7 | Toast progress UI: reuse AutoCodeToast pattern. "Extracting clips... (3 of 15)". "Reveal in Finder" on completion |
| 2.8 | CLI: `bristlenose export --clips` with Cargo-style progress |
| 2.9 | Doctor check: verify FFmpeg on PATH when `--clips` is requested |
| 2.10 | Tests: clip manifest, filename generation, merge logic, FFmpeg command construction (mock) |

### Files to create

| File | Purpose |
|------|---------|
| `bristlenose/server/clip_extractor.py` | FFmpeg wrapper, adjacent merge, naming, `safe_filename()` |
| `bristlenose/server/routes/clips_export.py` | Async clip extraction endpoints |
| `frontend/src/components/ClipExportToast.tsx` | Progress toast (or reuse AutoCodeToast) |
| `tests/test_clip_extractor.py` | Manifest, filenames, merge logic, FFmpeg mock |
| `tests/test_serve_clips_export.py` | Endpoint tests |

### Files to modify

| File | Change |
|------|--------|
| `bristlenose/server/app.py` | Register clips export routes |
| `bristlenose/cli.py` | Add `export --clips` command |
| `bristlenose/server/routes/dashboard.py` | Expose `_pick_featured_quotes()` for clip manifest |

---

## Decisions

1. **Separate feature, separate dialog.** Clips are not bundled with XLS/CSV. Own dialog, own menu item, own async flow. Later, the HTML export modal can offer clips as a checkbox, but the feature stands alone.
2. **FFmpeg stream-copy, no re-encoding.** Fast, preserves quality.
3. **Padding: 3s before, 2s after.** Sensible default. May expose in export dialog later if researchers ask.
4. **Adjacent merge within 10s.** Avoids near-duplicate clips from quotes close together in a session.
5. **New board per clip extraction, never modify existing clips.** Each extraction produces a fresh set.
6. **Participant code, not session number, in clip filenames.** A clip is always one person speaking. The code groups clips per person in sort order.
7. **Spaces, not hyphens.** The gist is lowercase, the capitalised speaker name provides the visual boundary.
8. **Audio-only: extract as-is.** No special handling needed — FFmpeg stream copy works on audio containers.
9. **File menu, not Video menu.** Export is a file operation, not a playback operation.

---

## Open questions

1. **Clip source beyond stars.** For v1, starred + signal heroes is the right default. Future: export dialog adds clip source picker — "Include clips for: starred / [tag picker]". The TagInput component already exists. A researcher creates a "deck" tag, tags the 5 quotes they want, and exports just those.
2. **Clip padding controls.** 3s before / 2s after is a sensible default. Expose in export dialog if researchers ask.
3. **Cross-platform `file://` video.** Inline `<video src="clips/...">` may not work on all browsers from `file://` due to security restrictions. Needs testing. Relevant when clips are later wired into the exported report (Stage 3 of HTML export).

---

## Verification

1. Extract clips from a project with starred quotes — verify clips appear in output folder
2. Verify clip filenames: participant code, timecode, speaker name, gist
3. Play clips in QuickLook (spacebar in Finder) — verify correct segment plays
4. Verify adjacent merge: two starred quotes 5s apart in same session produce one clip
5. Verify padding: clip starts ~3s before quote, ends ~2s after
6. Test with anonymisation — verify speaker name removed, code zero-padded
7. Test with audio-only session — verify clip extracted as audio file
8. Test with missing media file — verify graceful skip with warning
9. Test with project where sessions exceed 1 hour — verify `0h03m45` timecode format
10. Test CLI: `bristlenose export --clips` — verify Cargo-style progress output
11. Test FFmpeg missing: verify `bristlenose doctor` reports it, clips disabled with explanation
12. `pytest tests/` + `ruff check .`

---

## Related docs

- `docs/design-export-html.md` — HTML report export (Stage 3 wires clips into the report)
- `docs/design-export-quotes.md` — CSV/XLS quotes export
- `docs/design-export-sharing.md` — original monolith (superseded, kept for git history)
- `bristlenose/utils/video.py` — existing FFmpeg integration (thumbnails)
- `bristlenose/server/autocode.py` — async job pattern to reuse
