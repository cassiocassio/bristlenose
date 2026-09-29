---
status: partial
last-trued: 2026-09-29
trued-against: HEAD@main on 2026-09-29 (subtitles sections only)
---

> **Truing status:** Partial — the eliding rule, filename scheme and serve-mode flow are current (trued 2026-09-12); the container-preservation claim is superseded inline in three places; the CLI section is deferred and marked so. See changelog and inline banners.

## Changelog

- _2026-09-29 (later)_ — subtitles built end to end: a `.vtt` beside every clip plus a language-tagged embedded track; an opt-in burned copy, `<name> (subtitled).mp4`, beside the clean clip; and subtitles in the popout player, switched from Settings, the Export menu and the Mac's Video and Quotes menus. See § Shape and § Subtitles in Bristlenose's own player.
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

**Text source.** Take the text from the transcript segments and word timings under the clip range, rebased to the clip's start. Don't use the quote card's text: that has been cleaned up and elided (`…`), and a subtitle has to match what is heard. Apply the researcher's quote corrections on top (below). No speaker name or code is ever shown. A segment's leading `(Speaker B)`-style label is stripped, because in some projects it is a real name. If PII redaction is on, the redacted text is what shows. The audio still says any name, which is the separate problem of #58.

### Three ways to deliver them

| | A. Sidecar file | B. Embedded track | C. Burned in |
|---|---|---|---|
| What | `<clip name>.vtt` (or `.srt`) beside each clip | a `mov_text` (tx3g) subtitle track inside the `.mp4` | text drawn into the video pixels |
| Re-encode? | No | No, video stays stream-copied (`-c:v copy -c:s mov_text`) | **Yes** |
| Plays in | VLC, IINA, browsers via `<track>`; PowerPoint (Windows, Mac, web) via *Insert Captions*, once per video, then switched on in Slide Show; never picked up automatically | QuickTime Player (*View ▸ Subtitles*), VLC, IINA, PowerPoint for Mac/iOS; **not** PowerPoint for Windows (reads only CEA-608/708); Keynote: no | everything, including PowerPoint, Keynote, Teams, Slack, LinkedIn and a phone |
| Viewer can turn off | Yes | Yes | No |
| Editable / translatable later | Yes, it's a text file | Only by re-muxing | No |
| Colour per speaker | WebVTT's built-in colour classes (`<c.yellow>`); which players honour them is **unverified** (review log, Finding 33) | none — ffmpeg's `mov_text` encoder drops colour (measured) | Full control |
| Cost | Trivial | Trivial | A few seconds per clip (**estimate**; 1080p x264 `veryfast`) |
| Failure mode | File separated from its clip; ignored by slide apps | Invisible until someone finds the menu | Wrong text is permanent; small text unreadable on a phone |

Only **C is foolproof** for "drop it into PowerPoint and press play". A and B are cheap and keep the stream-copy guarantee (Decision 2), but each needs the viewer's player to cooperate.

**Burning in is possible with what we already ship — and the trial ran (29 Sep 2026).** The bundled ffmpeg (martin-riedl build — the binary on disk reports **8.0.1**, though `desktop/scripts/fetch-ffmpeg.sh` pins 8.1, so the bundle predates the pin) was configured with `--enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libx264`, and its binary carries the `subtitles` and `drawtext` filter names (read from the binary's strings, 29 Sep 2026). The binary itself exits 133 when run outside the sandbox, so this was **not run**. The path would be: write an `.ass` file per clip, then `-vf subtitles=clip.ass:fontsdir=<bundled fonts>` with x264, or with `h264_videotoolbox` for hardware encoding. **Risk:** inside the sandbox, fontconfig may not find system fonts, so bundle the chosen font (Inter, below) and pass `fontsdir`. A future AVFoundation backend would do the same job natively: `AVVideoCompositionCoreAnimationTool` with `CATextLayer`s, hardware encoding and system fonts, with no libass involved.

  **Trial, measured 29 Sep 2026.** The bundled binary exits 133 when run outside the sandbox, but a copy re-signed ad hoc (`codesign --remove-signature` then `codesign -s - --force`) runs without a download. It has `subtitles`, `ass` and `drawtext`, plus `libx264` and `h264_videotoolbox`. Two FOSSDA clips (18 s and 21 s, 1280×720) were each converted from their `.vtt` to `.ass`:
  - Inter, from `~/Library/Fonts` via `fontsdir`, at 48 px = 1/15 of the frame height;
  - `BorderStyle=3` for the box, with 75% black (`&H40000000`) and padding 0.15 × font size;
  - side margins of 16% (lines no wider than 68% of the frame) and a bottom margin of 5%;
  - `WrapStyle 2`, keeping the `.vtt`'s own line breaks;
  - speaker colour as a `\c` override.

  They were burned with `libx264 -crf 18 -preset veryfast` and the audio copied: **about 0.6 s per clip, 2–3 MB each.** Frames were checked, and Inter rendered, not a fallback. The maintainer confirmed it in QuickTime ("burn in works"). On these Zoom recordings the text lands in the black letterbox band, so the box is invisible there; a screen share without letterboxing is the case that exercises it.

### Styling — decided 29 Sep 2026

- **The BBC Subtitle Guidelines are the spec.** Where they give a number, we use it. The BBC tested this guidance with viewers; we have no grounds to second-guess it, and it is the tradition the maintainer came into user research through. The figures are listed under Prior art below.
- **White text on a 75% black box, not an outline.** The box geometry is the BBC's (§9.2.4); the opacity is YouTube's reported default rather than the BBC's solid black. Clips are often screen shares, and a solid block hides the interface the participant is talking about (maintainer, 29 Sep 2026). Most Zoom and Teams recordings are screen shares of mostly white UI, where outlined white text disappears. The box stays readable on any background.
- **Everyone audible is subtitled; speakers are told apart by BBC colour, never by label** (maintainer, 29 Sep 2026). The clip's own participant is always white. Anyone else takes yellow, cyan, then green, in order of first appearance (BBC §8.3). In practice that means the moderator's lead-in in the 3 s padding, or a gap inside a merged clip, shows in yellow. `P3:`-style badges would only distract, and a name must never appear. The machinery knows who is speaking in every cue, so a future **arbitrary transcript range across speakers** export needs no new plumbing.
- **Researcher corrections are applied** (maintainer, 29 Sep 2026: they fix acronyms, product names and mis-hearings). A correction is taken as the difference between the pipeline's quote text and the researcher's edit, so the pipeline's own tidying never deletes audible words. Replacements take the replaced words' time. Insertions share a neighbouring word's time. Capitalisation fixes (`ux` → `UX`) apply, keeping the transcript's punctuation. Deletions and elisions (`…`) don't. A bracketed group the researcher put *in place of* spoken words (`Sarah` → `[her]`) is shown, because their edit wins. One that is only inserted, or that sits beside real words (`it [the app] crashed`, `[the] Kubernetes`), is editorial and dropped. Corrected words up to 10 s past the quote's recorded end are reached, because model end times fall early (measured: 19 of 33 IKEA quotes, 40 of 80 Rockclimbing). **A change that can't be placed word by word is not applied at all**, and is logged with the quote's id. The transcript's own words stand. An earlier version spread the corrected quote evenly over its time instead, which deleted and duplicated audible words; the 29 Sep review removed that.
- **Layout per the BBC:** at most 2 lines (§3.3), each no wider than 68% of the frame (§3.1), bottom-centre inside the central 90% of the height (§10). Font size 1/15 of frame height (6.67%) with a line height of 8% (§9.2.1). The box is exactly one line high with no gap between lines, plus 0.5 em each side (§9.2.4). Cues break on word timings, never mid-word (Japanese and Chinese: between characters, below).
- **Japanese and Chinese extend the spec** (decided 29 Sep 2026; review log Finding 11). The BBC gives no figure for either, and a segment with no spaces used to become one 62-character line held for 14 s. What we took:
  - **Line length: 13 full-width characters for Japanese, 16 for Chinese**, from Netflix's [Japanese](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215767517-Japanese-Timed-Text-Style-Guide) and [Traditional Chinese](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215994807-Chinese-Traditional-Timed-Text-Style-Guide) Timed Text Style Guides (read on the page, 29 Sep 2026). Two lines, as everywhere. A half-width character counts 0.5. Netflix says that for Japanese only; we apply it to Chinese too, because a Latin letter is half a Han character's width there as well.
  - **The script comes from the cue's own text, never the UI language.** Any kana means Japanese; Han characters without kana mean Chinese. So a short all-kanji Japanese cue gets 16. Korean is written with spaces and takes the Latin path. Netflix gives Korean 16, which is not adopted.
  - **Breaks fall between characters**, because there are no spaces. A run of Latin letters or digits inside (`Figma`, `2026`) stays whole. Kinsoku follows W3C JLREQ and CLREQ: no line or cue opens on closing punctuation, a small kana or `ー`, and none ends on an opening bracket. No space is ever inserted between two CJK characters, and the transcript's own spaces are kept.
  - **Break at clause ends, not inside words.** A clause mark (`、。，`) is worth up to half a line when choosing a line break. A cue that fills up ends at its last clause mark in its back half, not wherever the characters ran out. If a sentence has no clause mark and a character or two would still be left alone on screen (`ン。` for 0.4 s, on the ja-JP demo), that cue takes characters back from the one before it.
  - **Not taken from Netflix.** Its Japanese guide drops `、。`, and its Chinese guide bans a comma or full stop at a line end. Both rewrite the text, and subtitles are faithful to the transcript, so the punctuation stays. Its reading speeds (4 characters a second for Japanese, 9 for Chinese) are not enforced; Latin cues have no reading-speed rule either, and timing follows speech.
  - **Known limit:** without a morphological analyser a line can still break inside a word (`どん|なふうに`), because only clause marks are known.
  - **Word timings.** Whisper times Japanese and Chinese in chunks of several characters, and each character takes its share of its chunk. But the importer drops these timings at the moment (`importer._words_read_as` compares space-separated runs, and CJK has none), so ja/zh subtitles are spread evenly across each segment until that is fixed.

### Font

The two delivery modes answer the font question differently. That is the argument for having both.

- **Soft subtitles (the `.vtt` sidecar and the embedded track) never carry a font.** The player draws them in its own face at playback. On a Mac, *System Settings ▸ Accessibility ▸ Captions* sets the style for AVKit players such as QuickTime. So "the viewer's system font, automatically" is already what soft subtitles do; keep it that way by not styling fonts in the `.vtt`.
- **Burned-in subtitles are pixels.** There is no playback-time font, so whatever we render with is fixed into the file forever. That is the commitment. It is mitigated by keeping the clean clip beside the burned one rather than replacing it.
- **Which font to burn with.** Two candidates:
  - *The machine's system font* (SF on a Mac). It looks native in a Keynote deck, but the output then depends on where it was made: the CLI on Linux would burn DejaVu or whatever fontconfig finds. SF would also only be reachable cleanly through CoreText, i.e. the future AVFoundation backend. Handing libass the SF font file directly is fragile and a licensing grey area (**unverified**).
  - *One bundled font, Inter* (OFL). The pixels come out identical on every channel. The metrics are known, so line wrapping and sizing can be computed and tested once rather than per machine. It costs a few hundred KB in the bundle for one weight (**estimate**).

  **Decided 29 Sep 2026: bundle Inter** (SIL Open Font License), in regular or medium weight, never light. It meets the BBC's criterion of "a wide font" (§9.1); the BBC's own examples can't be bundled (Reith Sans is the BBC's in-house face, and Verdana is Microsoft's and not redistributable). A deck will be in the client's brand font, which no choice of ours can match, so the aim is a neutral, highly legible sans that comes out identical on every channel. If the AVFoundation backend is ever built, it could offer the system font on the Mac, but that would be a channel fork to take deliberately, not by default.

### Prior art — surveyed 29 Sep 2026

Sources were read on the page unless marked *claimed* (a secondary source or a search snippet only).

- **PowerPoint can show captions, but not by itself.** A `.vtt` sitting next to the file is never picked up. Each video needs *Playback ▸ Insert Captions ▸ Insert Captions* once (Windows 2016+, Mac 16.63+, web; SRT is accepted from Windows 2411 and Mac 16.91). After that, in Slide Show, the viewer turns them on from the play bar's *Audio and Subtitles* menu (Alt/⌥+J). [Add captions](https://support.microsoft.com/en-us/office/add-closed-captions-or-subtitles-to-media-in-powerpoint-df091537-fb22-4507-898f-2358ddc0df18), [playback](https://support.microsoft.com/en-us/office/accessibility-features-in-video-and-audio-playback-on-powerpoint-ef62b701-c0ad-48e8-8473-4e8dbb0f7dd8).
- **PowerPoint and an embedded track:** PowerPoint for Mac and iOS read **MPEG-4 Timed Text**, which is our `mov_text` track. PowerPoint for Windows and mobile web read only **CEA-608/708**, so the `mov_text` track is invisible there. Microsoft's own caveat is that playback "may or may not" work depending on version. [Supported types](https://support.microsoft.com/en-us/accessibility/powerpoint/closed-caption-file-types-supported-by-powerpoint).
  - **Consequence:** soft subtitles reach a PowerPoint audience only if the researcher inserted the file and the presenter remembered to switch them on, live, in front of the client. That is the job the burn-in checkbox does.
- **Keynote has no caption feature** and ignores subtitle tracks (*claimed*, Apple Community threads only). **Google Slides:** Drive accepts `.vtt`/`.srt` on a video, but nothing says Slides shows them.
- **No UX research tool burns captions into exported clips.** Dovetail's highlight-reel download says outright that subtitles are not included "even if they are enabled in the video player". Condens, Great Question and Grain document no caption option on their clip exports; Marvin shows captions only in its own player (*claimed*). This would be a first in the category.
- **BBC Subtitle Guidelines** ([source](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/)):
  - §8.1 white on a black background.
  - §9.1 a wide sans (Reith Sans, Verdana, Tiresias).
  - §9.2.1 font size 1/15 of video height (6.67%) with a line height of 8%, for 16:9.
  - §9.2.4 the box is exactly the line height, with no gap between lines, plus 0.5 em each side.
  - §10 bottom-centre, inside the central 90% vertically and 75% horizontally.
  - §3.1 lines at most 68% of the width online (37 characters for broadcast).
  - §3.3 at most 2 lines.
  - §8.3 speaker colours white, yellow, cyan, green (kept for the later cross-speaker export).
- **Netflix** ([source](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977)): 42 characters per line, 2 lines, 20 characters per second (adult content), white, Arial as a placeholder, and no box specified.
- **DCMP Captioning Key** ([source](https://dcmp.org/learn/captioningkey/597)): white, medium-weight sans, and "a translucent box is preferred … especially on light backgrounds". Light backgrounds are exactly our screen-share case.
- **Box opacity:** sources split — BBC solid, DCMP translucent, YouTube's default reported as 75% black (*claimed*).
- **Social reels** (Hormozi/Submagic style: uppercase, heavy stroke, 4–6 words, pop-in animation; Kapwing defaults to Montserrat) are **not the model**. They are built for silent vertical feeds competing for a thumb. Legibility research also runs against them: all-caps is slower to read at a glance ([NN/g on the MIT AgeLab study](https://www.nngroup.com/articles/glanceable-fonts/)). Their one transferable lesson is short cues.
- **Size on a room display:** AVIXA's DISCAS viewing standard puts the minimum element height at about 2.5–3.5% of *screen* height for typical room geometry. That covers the in-room attendees only; remote attendees are the Teams chain below ([source](https://www.avixa.org/resources/display-image-size-calculators/learn-more-about-display-size)). A clip at half slide height halves our text, so we need about 5–7% of *clip* height. That lands on the BBC's 6.67%.
- **Fonts:** Atkinson Hyperlegible Next (Braille Institute; free, 7 weights, 150+ languages; [source](https://www.brailleinstitute.org/freefont/)) is designed for letterform distinction at low vision, and it is a wide humanist sans of the kind BBC §9.1 and DCMP ask for. It was considered and not chosen; Inter was (29 Sep 2026). No study compares Inter, SF or Netflix Sans for subtitles.

### Who watches, and through what

The typical viewing is **not** a room watching a TV. It is a **Teams (or Zoom) call in which the researcher shares their screen and plays the clip from a slide**. Some attendees are in a meeting room looking at the room display; others are remote, watching the shared screen in a Teams window on a laptop. So a subtitle passes through a chain of shrinks and one lossy encode before anyone reads it:

clip → half a slide → the presenter's screen → Teams screen-share encode → the attendee's Teams window, or the room display.

What that changes, and what it doesn't:

- **Burn-in is the only mode that survives the chain.** A screen share carries pixels. Soft captions reach it only if the presenter switched them on in PowerPoint first, and Teams' own live captions caption the people in the call, not a clip's audio played through *Include computer sound* (**unverified**).
- **The BBC numbers stand** (maintainer, 29 Sep 2026). What makes subtitles legible there — large text, solid black box, short lines, a wide regular-weight sans — is what survives a video encode too. A flat black box with hard white edges is close to the best case for a codec, and thin or light weights are what compression smears. Use a regular or medium weight, never light.
- **Teams trades resolution against frame rate.** By default screen sharing runs at a low frame rate to keep static content sharp; *Optimize for video* (in the presenter toolbar, beside *Include computer sound*) raises the frame rate and may lower the resolution, depending on the device and bandwidth. [Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/microsoftteams/meetings/fix-choppy-video). Interview footage is mostly talking heads and screen shares, and a subtitle cue lasts seconds, so the default (sharp, low frame rate) is probably the better setting for reading. That is a tip for the help text, not a control.

### Size — BBC figures, no experiment

**Use the BBC numbers as they stand; don't reinvent them** (maintainer, 29 Sep 2026). Their guidance was tested with viewers, and what it optimises for survives the Teams chain above. The only check is the ordinary QA of the feature: burn one clip, share it at half-slide size in a real Teams call, and look at it as a remote attendee.

**Tooling note:** Homebrew's ffmpeg has **no** `subtitles`/`ass` filter (checked 29 Sep 2026), and the bundled binary exits 133 outside the sandbox. The experiments therefore need the unsigned martin-riedl 8.1 download that `desktop/scripts/fetch-ffmpeg.sh` pins.

### Shape — decided 29 Sep 2026

1. **Always, and nearly free — built 29 Sep 2026:** write `<clip name>.vtt` beside every clip *and* mux a `mov_text` track into the `.mp4` or `.m4a`. No re-encode, so Decision 2 still holds. Code: `server/clip_subtitles.py` (pure: timing, corrections, cues, WebVTT/SRT), `clip_backend.py` (`subtitles=`), `routes/clips_export.py` (`_build_clip_cues`); `clips_manifest.json` names each clip's `.vtt`. Both cuts, subtitled and plain, take only the source's first video and first audio stream. An audio clip takes no video. A subtitle-build or file error costs that clip its subtitles, never the export, and never leaves the job stuck at "running". The SRT for muxing is written to the system temp directory, never the clips folder. CI's Linux cells install ffmpeg, so the round-trip test runs there. The first review pass is logged in the maintainer's private review notes (`export-clips`); Japanese and Chinese line-breaking followed the same day (Styling, above). Measured the same day:
   - **The cut is frame-exact.** A stream-copied cut at 7.00 s starts on the source frame at 7.00 s, not the keyframe at 5 s (ffmpeg writes an edit list), so cues timed from the clip's start are in sync. `tests/test_clip_subtitles_ffmpeg.py` pins it.
   - **The embedded track has no colour.** ffmpeg 8.1.1's `mov_text` encoder keeps bold and italic but drops a colour override, writing no style record for it. So the embedded track is plain, and the `.vtt` carries speaker colour through WebVTT's built-in classes (`<c.yellow>`, `<c.cyan>`, `<c.lime>`).
   - **A failed subtitle mux still cuts the clip,** without the track rather than losing it.
   - **Real-data check:** on two FOSSDA clips (185 s and 106 s), every cue fit 2 lines of 37 characters and 7 s, with no overlaps. What the run exposed is in the transcript, not here: a diarisation slip in the source colours the interviewer's question white.
2. **A single checkbox, off by default — built 29 Sep 2026:** *"Burn subtitles into the video (for slides)"*. That checkbox is the whole of the UI: no font, size or colour controls. It re-encodes with the styling above, and it is the one exception to Decision 2.
   - **Where it lives.** A checkbox row under *Extract clips* in the Export menu, and *Quotes ▸ Burn Subtitles into Clips* on the Mac. It is a remembered setting (`frontend/src/utils/subtitlePrefs.ts`, localStorage), not a per-export question; the Mac menu's checkmark mirrors it over the bridge (`subtitle-prefs`), the Focus Mode pattern.
   - **What it writes.** `<name> (subtitled).mp4` beside the clean clip, which is untouched; `clips_manifest.json` records it as `burned`. The ASS is built by `to_ass()` in `clip_subtitles.py`; `burn_subtitles()` in `clip_backend.py` renders it with libass and the bundled Inter (`bristlenose/data/fonts/`, OFL). Audio clips and clips with no cues get no copy.
   - **When ffmpeg can't.** `can_burn_subtitles()` checks for the `subtitles` filter and `libx264` once. If either is missing the request goes ahead with plain clips and the response carries `burn_unavailable`, which the page shows as a toast. Homebrew's ffmpeg is the known case.
3. **Audio-only sessions** (`.m4a`) can't carry burned-in text. A possible extension is an "audiogram": render a plain `.mp4` of a title card (the gist) with the subtitles over it, so audio quotes can go into a deck too. This is not decided.

**Decided:** the burned copy sits **beside** the clean clip as `… (subtitled).mp4`, as the Font section argued; it never replaces it. Font (Inter) and size (the BBC's) are decided too.

### The embedded track needs a language tag — found 29 Sep 2026

QuickTime showed nothing for an exported clip until the track was tagged. With the track's language `und`, macOS's own player framework offers two options, "Unknown language" and "Unknown language Forced", and picks the **Forced** one by default. That option shows only lines flagged as forced; ours are none, so *Subtitles ▸ On (Language)* displays nothing. Re-muxed with `language=eng`, it offers "English" and QuickTime shows the track. macOS 27 then also offers a live-translated track ("Spanish (Spain) Translated"), which exists only because the subtitles are real text.

The language is known upstream but lost before the export. Whisper detects it per session (since 0.31.0, `cca68462`), `SessionTranscript.detected_language` holds it, and the transcript header records `# Language: ja (detected)`. But the serve database has **no column** for it and the importer doesn't read the header. The header is also deliberately omitted when the language was pinned with `--whisper-language`, which for tagging is exactly the right value. Proposed chain:
1. a `Session.language` column (Alembic migration);
2. the importer reads it from the header;
3. a pinned language is recorded with its provenance (`(set)` beside `(detected)`);
4. the clip track is tagged with the ISO 639-2 code, and later the player's `<track srclang>`.

Still unknown by construction: platform transcripts (Teams, Zoom, docx) and projects from before 0.31.0.

**Built 29 Sep 2026 (steps 1, 2 and 4; step 3 not yet):**
- `sessions.language`, added by migration 011;
- the importer reads the header on every import;
- `iso639_2()` in `clip_subtitles.py` maps Whisper codes and locale tags to three-letter codes;
- `_subtitle_languages()` in the route tags each clip's track.

**Fallback decided: the app's language, not `und`.** Measured the same day in QuickTime, with the maintainer at the controls:
- **Untagged (`und`):** a double-click plus *Subtitles ▸ On* shows nothing. It needs *Language ▸ Unknown language* chosen by hand as well.
- **Tagged English:** shows on a plain double-click, because QuickTime remembers the viewer's *On (Language)* setting.
- **Flagged "every line forced"** (the `tx3g` display flag): also shows, but the viewer can't hide it, so it is not used.

A slightly wrong label beats subtitles that never appear. A brand-new QuickTime user with subtitles off still needs one click; that is Apple's convention, and burn-in is the path for text that must always show. **Step 3 built the same day:** a pinned `--whisper-language` is written as `# Language: es (set)`, never as a detection (`FullTranscript.pinned_language`, `Pipeline._pinned_languages`), and the importer reads it like a detected one.

### Subtitles in Bristlenose's own player — built 29 Sep 2026

The maintainer wanted the popout player to show the same subtitles, switched on and off from **Appearance** and/or the **Video** menu. What shipped:
- **The switch.** *Show subtitles in the video player*, off by default, in Settings (a *Video* group in the web settings) and as *Video ▸ Subtitles* on the Mac. The setting lives in the page's localStorage (`subtitlePrefs.ts`); the menu dispatches a toggle and shows a mirrored checkmark. It is live whenever the report can hear it, so it can be set before the player opens. It is hidden in an exported report, which has no server to fetch subtitles from.
- **The text.** `GET /api/projects/{id}/sessions/{sid}/subtitles.vtt` builds the whole session from the same cue code as the clips (primary speaker white, the others in BBC colours, researcher corrections applied), with `Content-Language` from the session's language or else the app's. The route is `SERVER_ONLY` in the export classifier.
- **The handover.** `PlayerContext` fetches the text with the bearer token and posts it to the player (`bristlenose-subtitles`), tagged with the recording it belongs to; the player makes a blob URL and attaches a `<track>` only when that recording is the one playing. The player announces `bristlenose-ready` when it loads, and the report answers with the setting and the current recording's subtitles — anything posted before then is lost. A change of setting is sent as the `setSubtitles` command.
- **The live page.** Serve now renders the player from the template (`/report/assets/bristlenose-player.html`, no-store) ahead of the baked copy, so existing projects get the new player.

The original mapping, kept for the reasoning:
- The popout is a web page, `bristlenose/theme/templates/player.html`, opened with `window.open` and hosted in a `WKWebView` window (`WebView.swift` `createWebViewWith`).
- It is controlled over `postMessage` (`bristlenose-seek` and `bristlenose-command`). A `toggleSubtitles` command would sit beside `togglePip`.
- The Video menu reaches it through `bridgeHandler.menuAction` → `useKeyboardShortcuts` → `sendCommand`. A checkmark item follows the Focus Mode `Toggle` pattern (`MenuCommands.swift`).

Three traps:
1. **The player page is a copy baked into each project** by the sealed static renderer (`_write_player_html`), so an edit to the template never reaches existing projects. It needs a live route, as the theme CSS has.
2. **A `<track src>` can't send the bearer token.** The `.vtt` has to come from a route the auth cookie covers, or be fetched with the token and handed to the track as a blob URL.
3. **The popout `WKWebView` isn't registered with the bridge**, so an Appearance toggle reaches the player through the report page (`sendCommand`) or shared `localStorage`. It must not go through `.bristlenosePrefsChanged`, which restarts serve.

A whole-session `.vtt` route can reuse `clip_subtitles.py`'s cue building.

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
