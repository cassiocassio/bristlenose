---
status: partial
last-trued: 2026-09-12
trued-against: HEAD@main on 2026-09-12
---

> **Truing status:** Partial — the eliding rule, filename scheme and serve-mode flow are current (trued 2026-09-12); the container-preservation claim is superseded inline in three places; the CLI section is deferred and marked so. See changelog and inline banners.

## Changelog

- _2026-09-29_ — added § Future: subtitles on clips (sidecar / embedded track / burned in, speaker colour coding, recommended layering), carried over from the closed issue #59 so the idea outlives the tracker. Proposal only; nothing shipped changed.
- _2026-09-12_ — trued up: named `format_clip_timecode`/`use_hours` and recorded why per-export eliding is sound by construction plus its zero-duration residual (from the time audit's H6 withdrawal); marked the source-container-preservation claim superseded at three sites (fixed `.mp4`/`.m4a`); added `raw_start`/`is_audio_only` to `ClipSpec`; repointed the never-created `clip_extractor.py` to the three shipped modules; marked the CLI deferred inline. Anchors: `server/clip_manifest.py:107,139-140`, `routes/clips_export.py:119,370-371`, `clip_backend.py:47-50`, `docs/time-defects.md` H6.

# Video Clip Extraction — Design Document

Extract trimmed video clips of key quotes for stakeholder playback and slide decks.

**Status:** v0.14.3 — serve-mode extraction shipped (FFmpeg backend, async job, API endpoints, React UI). CLI command deferred. AVFoundation backend deferred to desktop milestone.

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

Implemented as `format_clip_timecode(seconds, use_hours=…)` (`server/clip_manifest.py:107`) with `use_hours = max_duration >= 3600` derived once per export (`routes/clips_export.py:370-371`). **Why eliding is safe, not merely tidy:** a clip's start is bounded by its own session's duration, which is ≤ `max_duration`, so when the flag is `False` no clip start can reach an hour and the omitted field is provably zero — no collision is possible. **Residual:** that bound rests on `duration_seconds` being accurate; a session recorded with `duration_seconds == 0` whose quotes ran past an hour would break it (`clips_export.py:119` reads the field unguarded). Measured 12 Sep 2026: 4 of 98 local sessions carry a zero time axis, none with a quote past an hour.

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

> **Deferred — not shipped.** `bristlenose export --clips` does not exist (`grep '"--clips"' bristlenose/cli.py` is empty). The status banner says so; this marker keeps the section from reading as live. Mockup retained.

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

> **Superseded as implemented (v0.14.3) —** clips are written to a fixed container: `.mp4` for video, `.m4a` for audio (`clip_manifest.py:140`, `clip_backend.py:47-50` — stream-copy into `.mp4`). The source container is not preserved. Original text retained below.

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
    raw_start: float        # original quote start — the FILENAME timecode uses this, unpadded, so it points at the quote, not the clip's first frame 3s earlier (clip_manifest.py:139)
    is_audio_only: bool     # drives the output extension (.m4a vs .mp4)
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
| 2.4 | FFmpeg wrapper: `ffmpeg -i {source} -ss {start} -to {end} -c copy {output}`. Skip missing media gracefully (warning, no error). ~~Preserve source container format~~ (superseded: fixed `.mp4`/`.m4a` output — see Audio-only sessions) |
| 2.5 | Async job runner: reuse AutoCode `asyncio.create_task()` pattern |
| 2.7 | Toast progress UI: reuse AutoCodeToast pattern. "Extracting clips... (3 of 15)". "Reveal in Finder" on completion |
| 2.8 | CLI: `bristlenose export --clips` with Cargo-style progress — **deferred, not shipped** |
| 2.9 | Doctor check: verify FFmpeg on PATH when `--clips` is requested |
| 2.10 | Tests: clip manifest, filename generation, merge logic, FFmpeg command construction (mock) |

### Files to create

| File | Purpose |
|------|---------|
| ~~`bristlenose/server/clip_extractor.py`~~ shipped as three modules: `server/clip_manifest.py` (manifest, gist, naming, merge), `server/clip_backend.py` (FFmpeg), `server/routes/clips_export.py` (endpoints, job) | FFmpeg wrapper, adjacent merge, naming, `safe_filename()` |
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
8. **Audio-only: extract as-is.** No special handling needed — FFmpeg stream copy works on audio containers. _(Superseded as implemented: audio clips are written as `.m4a`, not the source container — `clip_manifest.py:140`.)_
9. **File menu, not Video menu.** Export is a file operation, not a playback operation.

---

## Future: subtitles on clips

_Proposed 29 Sep 2026, from the closed GitHub issue #59 ("overlay subtitles" was its bonus line). Not built. Nothing below changes what ships today._

**Why this is the valuable part of #59.** A clip dropped into a deck is usually played in a meeting room, often with the sound low or off, to people who never heard the interview. Subtitles make the quote legible at a glance and put the participant's exact words on screen, which is the point of showing a clip. The logo and badge overlays from the same issue are cosmetic by comparison.

**Text source.** Take the text from the transcript segments and word timings under the clip range, rebased to the clip's `raw_start`. Don't use the quote card's text: that has been cleaned up and elided (`…`), and a subtitle has to match what is heard. Use the transcript as it stands, including the researcher's corrections. Speaker labels are codes only (`P3`, `M1`), never names, in line with the anonymisation rule (names *and* location). If PII redaction is on, the redacted text is what shows. The audio still says the name, which is the separate problem of #58.

### Three ways to deliver them

| | A. Sidecar file | B. Embedded track | C. Burned in |
|---|---|---|---|
| What | `<clip name>.vtt` (or `.srt`) beside each clip | a `mov_text` (tx3g) subtitle track inside the `.mp4` | text drawn into the video pixels |
| Re-encode? | No | No, video stays stream-copied (`-c:v copy -c:s mov_text`) | **Yes** |
| Plays in | VLC, IINA, browsers via `<track>`; PowerPoint 365 via *Insert ▸ Captions* (needs a manual step per video) | QuickTime Player (*View ▸ Subtitles*), VLC, IINA; PowerPoint and Keynote: **unverified** | everything, including PowerPoint, Keynote, Teams, Slack, LinkedIn and a phone |
| Viewer can turn off | Yes | Yes | No |
| Editable / translatable later | Yes, it's a text file | Only by re-muxing | No |
| Colour per speaker | WebVTT voice spans (`<v P3>`) with `::cue` styling in browsers; elsewhere **unverified** | tx3g can style per cue; players mostly ignore it (**unverified**) | Full control |
| Cost | Trivial | Trivial | A few seconds per clip (**estimate**; 1080p x264 `veryfast`) |
| Failure mode | File separated from its clip; ignored by slide apps | Invisible until someone finds the menu | Wrong text is permanent; small text unreadable on a phone |

Only **C is foolproof** for "drop it into PowerPoint and press play". A and B are cheap and keep the stream-copy guarantee (Decision 2), but each needs the viewer's player to cooperate.

**Burning in is possible with what we already ship.** The bundled ffmpeg (martin-riedl 8.1 build) was configured with `--enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libx264`, and its binary carries the `subtitles` and `drawtext` filter names (read from the binary's strings, 29 Sep 2026). The binary itself exits 133 when run outside the sandbox, so this was **not run**. The path would be: write an `.ass` file per clip, then `-vf subtitles=clip.ass:fontsdir=<bundled fonts>` with x264, or with `h264_videotoolbox` for hardware encoding. **Risk:** inside the sandbox, fontconfig may not find system fonts, so bundle one OFL font (Inter or Atkinson Hyperlegible) and pass `fontsdir`. A future AVFoundation backend would do the same job natively: `AVVideoCompositionCoreAnimationTool` with `CATextLayer`s, hardware encoding and system fonts, with no libass involved.

### Styling — decided 29 Sep 2026

- **White text on a semi-opaque black box, not an outline.** Most Zoom and Teams recordings are screen shares of mostly white UI, where outlined white text disappears. The box stays readable on any background.
- **One colour, white. No speaker labels and no per-speaker colours.** A quote is one participant's voice by construction: quotes are filtered for participant speech and narrowed to a single speaker. Most interviews are 1:1, and a viewer can tell from context who is speaking. `P3:`-style badges would only distract.
- **Kept for later:** exporting an **arbitrary transcript range across speakers** is the one future surface where a clip holds two voices. When it exists, use the BBC convention (speaker colours in the order white, yellow, cyan, green, with a dash on each change of speaker) rather than code labels.
- **Two lines of at most ~42 characters each**, with cues broken on word timings and never mid-word. The characters-per-line figure depends on the font and the size, so it gets settled by the experiments below.

### Font

The two delivery modes answer the font question differently. That is the argument for having both.

- **Soft subtitles (the `.vtt` sidecar and the embedded track) never carry a font.** The player draws them in its own face at playback. On a Mac, *System Settings ▸ Accessibility ▸ Captions* sets the style for AVKit players such as QuickTime. So "the viewer's system font, automatically" is already what soft subtitles do; keep it that way by not styling fonts in the `.vtt`.
- **Burned-in subtitles are pixels.** There is no playback-time font, so whatever we render with is fixed into the file forever. That is the commitment. It is mitigated by keeping the clean clip beside the burned one rather than replacing it.
- **Which font to burn with.** Two candidates:
  - *The machine's system font* (SF on a Mac). It looks native in a Keynote deck, but the output then depends on where it was made: the CLI on Linux would burn DejaVu or whatever fontconfig finds. SF would also only be reachable cleanly through CoreText, i.e. the future AVFoundation backend. Handing libass the SF font file directly is fragile and a licensing grey area (**unverified**).
  - *One bundled font, Inter* (OFL). The pixels come out identical on every channel. The metrics are known, so line wrapping and sizing can be computed and tested once rather than per machine. It costs a few hundred KB in the bundle for one weight (**estimate**).

  **Recommendation: bundle Inter for burn-in.** A deck will be in the client's brand font, which no choice of ours can match, so the aim is a neutral, highly legible sans. Being identical everywhere matters more than feeling native for a file that gets passed from laptop to laptop. If the AVFoundation backend is ever built, it could offer the system font on the Mac, but that is a channel fork to take deliberately, not by default.

### Size — experiments owed

Nothing is decided here until a clip has been seen in a real deck. The case to design for is a **video shrunk inside a slide**, not full screen: a clip often occupies half a slide, so the text must survive at 50% scale on a projector. Proposed matrix:

- Text height at 4%, 5.5% and 7% of frame height (size as a fraction of the frame, so 720p and 1080p come out the same).
- Two box opacities.
- Three sources: a 720p Zoom screen share, 1080p Teams speaker view, and a portrait phone recording.
- Each output placed in a PowerPoint and a Keynote slide at full-slide and half-slide size, viewed on a laptop and on a TV or projector.

**Tooling note:** Homebrew's ffmpeg has **no** `subtitles`/`ass` filter (checked 29 Sep 2026), and the bundled binary exits 133 outside the sandbox. The experiments therefore need the unsigned martin-riedl 8.1 download that `desktop/scripts/fetch-ffmpeg.sh` pins.

### Shape — decided 29 Sep 2026

1. **Always, and nearly free:** write `<clip name>.vtt` beside every clip *and* mux a plain `mov_text` track into the `.mp4`. No re-encode, so Decision 2 still holds.
2. **A single checkbox in the clip export dialog, off by default:** *"Burn subtitles into the video (for slides)"*. That checkbox is the whole of the UI: no font, size or colour controls. It re-encodes with the styling above, and it is the one exception to Decision 2.
3. **Audio-only sessions** (`.m4a`) can't carry burned-in text. A possible extension is an "audiogram": render a plain `.mp4` of a title card (the gist) with the subtitles over it, so audio quotes can go into a deck too. This is not decided.

**Still open:** whether the burned copy replaces the clean clip or sits beside it (`… (subtitled).mp4`; the Font section argues for beside), the font (recommendation above), and the size (experiments).

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
10. ~~Test CLI: `bristlenose export --clips` — verify Cargo-style progress output~~ (CLI deferred)
11. Test FFmpeg missing: verify `bristlenose doctor` reports it, clips disabled with explanation
12. `pytest tests/` + `ruff check .`

---

## Related docs

- `docs/design-export-html.md` — HTML report export (Stage 3 wires clips into the report)
- `docs/design-export-quotes.md` — CSV/XLS quotes export
- `docs/design-export-sharing.md` — original monolith (superseded, kept for git history)
- `bristlenose/utils/video.py` — existing FFmpeg integration (thumbnails)
- `bristlenose/server/autocode.py` — async job pattern to reuse
