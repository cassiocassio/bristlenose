# Export and Sharing — Design Document

Reference doc for making Bristlenose reports shareable. Covers the research package format, video clip extraction, transcript export, anonymisation, and implementation plan.

## Problem statement

Researchers spend hours curating findings in Bristlenose — starring quotes, editing text, adding tags, identifying themes. Then they need to share this work:

- **With stakeholders** — a PM or exec who wants the headline findings, maybe 3 video clips to play at a meeting
- **With colleagues** — a fellow researcher or designer who needs to read transcripts in context
- **With themselves** — dragging 5 clips into a slide deck for tomorrow's playback session

Today, sharing means: copy-paste quotes into slides, open Final Cut Pro, scrub through 8 hours of footage to find the 15-second moments, trim, export. That's 3 hours of mechanical work the pipeline has already done — it knows exactly where every quote starts and ends.

**Core principle:** The recipient should never need to install Bristlenose. The output must be completely standalone.

## Scenarios

These are the real workflows the export serves. Not "export formats" — working researcher situations.

### Scenario 1: "Give me the deck clips"

**Who:** The researcher, preparing for a stakeholder playback.

**What they're doing:** Building a slide deck in Keynote / PowerPoint / Google Slides. They want 3–5 video clips, 15–20 seconds each. One per key finding. They need to **browse, choose, preview, and drag** with zero friction.

**What they need:**
- A folder of clips visible as thumbnails in Finder / Explorer
- Named so they can tell which is which without opening each one
- Short enough to hold attention
- Easy to preview (QuickLook on macOS — spacebar on .mp4 in Finder)

**What they do NOT need:** The full report, transcripts, or analysis. They've already done that work in Bristlenose. Now they're in PowerPoint-land and just want the files.

### Scenario 2: "Send me the highlights"

**Who:** The PM / product lead / exec who commissioned the research.

**What they're doing:** Prepping for a meeting, or catching up after missing one. They want the summary.

**What they need:**
- The report HTML — open it, scan the signal cards, read the exec summary
- Maybe click play on 1–2 hero quotes to hear the participant's voice
- That's it

**What they do NOT need:** Transcripts, a folder of 30 clips, the ability to edit. They want to consume, not curate.

### Scenario 3: "I need the full context"

**Who:** A fellow researcher doing secondary analysis, or a designer who wants nuance before making decisions.

**What they're doing:** Reading transcripts. Ctrl+F across sessions. Going back and forth between a quote and its surrounding context.

**What they need:**
- Readable transcripts (.txt files)
- The full report for the researcher's analysis
- Ability to click from a quote in the report to the right spot in the transcript

**What they do NOT need:** Video clips. They want text depth.

### Scenario 4: "Play me the one about onboarding"

**Who:** Anyone in a meeting. The PM says "wait, can you play that quote about day one?"

**What the researcher does:** They're screen-sharing. They need the right clip in under 10 seconds. Alt-tab to clips folder, names are human-readable, find it, double-click, it plays.

Or they stay in the report, find the quote, hit play inline.

**What matters:** Speed to the right clip. Recognisable filenames.

## The end-state package

These aren't four export modes. They're one folder that serves all four scenarios:

### 1:1 sessions (typical — one participant per session)

```
Acme Onboarding Research/
|
|-- report.html                                       <- double-click, opens in browser
|
|-- clips/                                            <- drag into decks, play at meetings
|   |-- p1 03m45 Sarah onboarding was confusing.mp4
|   |-- p1 17m02 Sarah i gave up after day two.mp4
|   |-- p2 02m15 James search never finds anything.mp4
|   |-- p2 12m03 James it took me three days.mp4
|   +-- p3 08m11 Priya i dont trust the results.mp4
|
+-- transcripts/                                      <- deep reading, Ctrl+F, paste into docs
    |-- p1 Sarah.txt
    |-- p2 James.txt
    +-- p3 Priya.txt
```

### 1:many sessions (focus groups, dyads)

```
Acme Onboarding Research/
|
|-- report.html
|
|-- clips/                                            <- clip speaker = the one person speaking
|   |-- p1 03m45 Sarah onboarding was confusing.mp4
|   |-- p2 05m22 James but i thought it was fine.mp4
|   +-- p3 08m11 Priya i dont trust the results.mp4
|
+-- transcripts/                                      <- transcript lists all speakers in session
    |-- 01 p1 Sarah p2 James.txt
    +-- 02 p3 Priya p4 Mike p5 Jo.txt
```

**report.html** is for browsing and playing. **clips/** is for dragging into other tools. **transcripts/** is for reading in depth. Same data, three surfaces, zero overlap in workflow.

**Note:** Full session recordings are NOT included. The researcher already has the original video folder — that's what they fed into Bristlenose. The clips are the value add: precise in/out points that would take 3 hours to find in Final Cut Pro.

### Naming principles

**Clips always have one speaker.** A quote has exactly one voice. Even in a focus group, the clip is "the moment p3 Sarah said this thing." So clip naming is identical for 1:1 and 1:many sessions — no session number needed, the participant code is the identifier.

**Transcripts differ by session type.** In 1:1, the transcript filename is just the participant (`p1 Sarah.txt`). In 1:many, it lists all speakers in the session with a session number prefix (`01 p1 Sarah p2 James.txt`).

**Participant code sorts the folder.** `p1` groups all of Sarah's clips together. The timecode (`03m45`) sorts clips within a participant chronologically. No sequence numbers needed — the natural sort order tells the story.

**Spaces, not hyphens.** Components are separated by spaces. The gist text flows naturally in lowercase after the capitalised speaker name — no separator character needed because the case change is the visual boundary.

### Session numbering in filenames

The UI uses `#1`, `#2` to refer to sessions. Internal IDs are `s1`, `s2`. Neither works in filenames: `#` is a problem character in shells and URLs; `s3` looks like a speaker code alongside `m1`, `p1`, `o1`.

**Decision:** Session numbers only appear in transcript filenames for 1:many sessions, as a plain zero-padded number prefix (`01`, `02`). In 1:1 sessions, the participant code *is* the session identifier — no session number needed. Clips never need session numbers because they always have a participant code.

### Timecode format in clip filenames

Timecodes use `{mm}m{ss}` format: `03m45` means 3 minutes 45 seconds. Reads naturally, no punctuation issues in filenames.

**Sessions over one hour:** If *any* session in the project exceeds one hour, all clip timecodes switch to `{h}h{mm}m{ss}` format with a zero-padded hour prefix. This keeps lexical sort = chronological sort:

| All sessions < 1h | Any session ≥ 1h |
|---|---|
| `03m45` | `0h03m45` |
| `17m02` | `0h17m02` |
| — | `1h02m10` |

The format is chosen per-export based on `max(duration_seconds)` across all sessions.

### What the report.html does

Self-contained React SPA with all data embedded as JSON (shipped in v0.11.2). Hash router for `file://` compatibility. Blob-URL'd JS chunks. Works offline in any modern browser.

When clips are present:
- Starred quotes get a play button that opens `clips/<filename>.mp4` via relative path
- Signal card hero quotes also get play buttons (even if not starred)
- Inline `<video>` element — no popout window, no server needed
- If a clip doesn't exist (audio-only session, or clips not included), the play button doesn't appear

Transcript pages within the report (React-rendered from embedded JSON) remain the in-context reading experience. The .txt files in the folder are for people who want to work outside the browser.

## Implementation stages

Each stage delivers a usable export that's better than the previous one. The scenarios guide where we're going; the stages are how we get there incrementally.

### Shipped: single HTML export (v0.11.2)

What exists today:

- Self-contained HTML download (single file, no folder structure)
- Anonymisation (report data only)
- Blob-URL'd JS chunks, hash router for `file://`
- Basic export dialog with anonymise checkbox

**Serves:** Scenario 2 partially (exec can browse findings, but no video playback)

### Stage 1: Zip with transcripts

**Upgrade the single HTML file to a zip with a folder structure and transcript .txt files.**

| What it delivers |
|-----------------|
| Zip instead of bare HTML — recipient unzips, gets a named folder |
| `report.html` inside the folder (identical to today's export) |
| `transcripts/` folder with one `.txt` per session |
| Human-readable transcript filenames |
| Anonymisation extended to transcript filenames and speaker labels |
| Updated export dialog with "Include transcripts" checkbox (default ON) |

**Serves:** Scenario 2 (exec gets report) + Scenario 3 (colleague gets readable transcripts)

**What the user sees after Stage 1 (1:1 sessions):**

```
Acme Onboarding Research/
|-- report.html
+-- transcripts/
    |-- p1 Sarah.txt
    |-- p2 James.txt
    +-- p3 Priya.txt
```

**What the user sees after Stage 1 (1:many sessions):**

```
Acme Onboarding Research/
|-- report.html
+-- transcripts/
    |-- 01 p1 Sarah p2 James.txt
    +-- 02 p3 Priya p4 Mike p5 Jo.txt
```

**Implementation:**

| Task | Description |
|------|-------------|
| 1.1 | Transcript renderer: API transcript data → .txt with inline timecodes. Reuse `markdown.py` formatting (timecodes, speaker labels). New: resolve speaker names from DB, human-readable filenames |
| 1.2 | Filename builder: 1:1 → `{code} {name}.txt`; 1:many → `{session_nn} {code} {name} {code} {name}.txt`. Anonymised: names removed, codes zero-padded |
| 1.3 | Anonymisation pass for transcript body: swap speaker display names for participant codes. Keep moderator names |
| 1.4 | Zip builder: Python `zipfile` — `{project_name}/report.html` + `{project_name}/transcripts/*.txt`. Folder name uses `slugify()` with spaces preserved |
| 1.5 | Update export endpoint: return `application/zip` with `Content-Disposition` filename. The HTML builder is unchanged — just wrapped in a zip now |
| 1.6 | Update ExportDialog: add "Include transcripts (.txt)" checkbox, default ON |
| 1.7 | Tests: transcript rendering (timecodes, speaker names, anonymisation), zip structure, filename edge cases (long names, special characters, zero-padding) |

**Dependencies:** Existing `markdown.py` formatters. Existing export endpoint.

**Can ship independently:** Yes. Useful on its own.

### Stage 2: Video clip extraction

**Add a `clips/` folder with trimmed video clips of starred quotes and signal card heroes.**

| What it delivers |
|-----------------|
| `clips/` folder with one .mp4 per starred quote / signal card hero |
| Human-readable clip filenames (sequence, session, speaker, quote gist) |
| FFmpeg stream-copy extraction (fast, no re-encoding) |
| Adjacent clip merging (within 10s in same session) |
| Async processing with toast progress and "Reveal" completion link |
| CLI flag: `bristlenose export --clips` |

**Serves:** Scenario 1 (researcher drags clips into deck) + Scenario 4 (find and play clip by filename)

**What the user sees after Stage 2:**

```
Acme Onboarding Research/
|-- report.html
|-- clips/
|   |-- p1 03m45 Sarah onboarding was confusing.mp4
|   |-- p1 17m02 Sarah i gave up after day two.mp4
|   +-- p2 02m15 James search never finds anything.mp4
+-- transcripts/
    |-- p1 Sarah.txt
    +-- p2 James.txt
```

**Implementation:**

| Task | Description |
|------|-------------|
| 2.1 | Clip manifest builder: query starred quotes + `_pick_featured_quotes()` heroes → deduplicated `ClipSpec` list with padded timecodes (3s before, 2s after) |
| 2.2 | Adjacent clip merge: if two clips from same session are within 10s, merge into one. Merged clip keeps first quote's name |
| 2.3 | Clip filename builder: `{code} {timecode} {speaker} {gist}.{ext}`. Gist = first ~6 words, lowercased, punctuation stripped, spaces preserved, max ~40 chars. Anonymised: speaker name removed, code zero-padded. Timecode format: `{mm}m{ss}` or `{h}h{mm}m{ss}` if any session ≥ 1 hour |
| 2.4 | FFmpeg wrapper: `ffmpeg -i {source} -ss {start} -to {end} -c copy {output}`. Skip missing media gracefully (warning, no error). Preserve source container format (.mp4, .m4a, .mp3, etc.) |
| 2.5 | Async job runner: reuse AutoCode `asyncio.create_task()` pattern. `POST /api/projects/{id}/package` starts job. `GET /api/projects/{id}/package/status` returns `{state, progress, total, current_clip}` |
| 2.6 | Toast progress UI: "Extracting video clips... (3 of 15)". On completion: "Package ready — Reveal". Reveal calls `open -R` (macOS) / `xdg-open` parent dir (Linux) |
| 2.7 | CLI: `bristlenose export --clips` with Cargo-style progress. Instant without `--clips` (zip with report + transcripts only) |
| 2.8 | Update ExportDialog: add "Include video clips" checkbox, default OFF. When checked, Export triggers async job instead of instant download |
| 2.9 | Doctor check: verify FFmpeg on PATH when `--clips` is requested |
| 2.10 | Tests: clip manifest (deduplication, merge logic, padding), filename generation (edge cases, anonymisation, zero-padding, gist truncation), FFmpeg command construction (mock — don't shell out in tests) |

**Dependencies:** Stage 1 (zip builder). FFmpeg on PATH.

**Can ship independently:** Yes. Clips appear as standalone files in the folder. The report.html doesn't link to them yet (that's Stage 3), but the researcher can browse and drag them. This alone serves Scenario 1.

### Stage 3: Playable clips in the report

**Wire up the report.html so starred quotes and signal card heroes play their clips inline.**

| What it delivers |
|-----------------|
| Play button on starred quotes (when clip exists) |
| Play button on signal card hero quotes (even if not starred) |
| Inline `<video>` playback from relative `clips/` path |
| Graceful degradation: no play button when clip missing |

**Serves:** Scenario 2 fully (exec clicks play on hero quote) + Scenario 4 fully (find quote → play inline)

**Implementation:**

| Task | Description |
|------|-------------|
| 3.1 | Clip-aware video map: embed `videoMap` in `BRISTLENOSE_EXPORT` keyed by quote DOM ID → relative clip path. Built during zip assembly from the clip manifest |
| 3.2 | Export-mode player: inline `<video>` element that loads from relative path. No popout window in export mode. Controls: play/pause, scrub, mute. Minimal chrome |
| 3.3 | Play button on signal card heroes: `FeaturedQuote` component checks `videoMap` for its `dom_id`, shows play button if present. Clicking plays inline |
| 3.4 | Play button on starred quotes: `QuoteCard` component checks `videoMap`, shows play button if present |
| 3.5 | Graceful degradation: `videoMap` missing or quote not in map → no play button. Audio-only clips → play button works, no video frame (audio-only playback) |
| 3.6 | Tests: video map generation, play button visibility logic, export-mode player rendering |

**Dependencies:** Stage 2 (clips exist in the zip).

**Can ship independently:** Yes. This completes the full scenario set.

### Stage 4: Polish and branding

**Fit-and-finish items that improve the experience but aren't blocking.**

| Task | Description |
|------|-------------|
| 4.1 | Branding footer: "Made with Bristlenose" CTA at bottom of exported report. Muted, dark mode aware, hidden in print. `--no-branding` flag for enterprise |
| 4.2 | Inline logo as base64 (currently a broken external reference in export) |
| 4.3 | Size warning: if clip count >50 or estimated zip >500MB, show warning in export dialog |
| 4.4 | Export filename polish: `{project-name}.zip` with clean slugification |

**Can ship independently:** Yes. Each sub-task is independent.

### Future iterations (not blocking)

These are known improvements to revisit after the core stages ship.

**Decouple clip source from stars.** Stars mean "this is important" (Miro, synthesis wall). Clips mean "play this at a meeting." For v1, starred + signal heroes is the right default. Future: export dialog adds clip source picker — "Include clips for: ⭐ starred / 🏷 [tag picker]". The TagInput component already exists. A researcher creates a "deck" tag, tags the 5 quotes they want, and exports just those. This is a query-filter change, not an architecture change — the clip manifest already references quotes by ID.

**VTT transcript format.** Useful for re-import and subtitle tooling. Add as an option alongside .txt. Not needed for any current scenario.

**Locked read-only mode.** Exported reports currently allow recipient editing (localStorage). Future: option to disable editing for stakeholder-facing packages.

**Clip padding controls.** 3s before / 2s after is a sensible default. Expose in export dialog if researchers ask.

## Clip extraction details

### Which quotes get clips

```
clip pool = starred quotes UNION signal card hero quotes
```

| Source | Who chose it | Typical count | Has timecode? |
|--------|-------------|---------------|---------------|
| Starred quotes | Researcher (manual) | 10–30 | Yes |
| Signal card heroes | Pipeline algorithm (`_pick_featured_quotes()`) | Up to 9 (top 3 displayed) | Yes |
| Overlap | Both | Some | — |

The union typically lands at 20–40 clips, ~5–8 minutes of footage total (~60–100MB).

### FFmpeg extraction

```bash
ffmpeg -i input.mp4 -ss 36 -to 54 -c copy output.mp4
```

- `-ss 36` — start 3 seconds before quote
- `-to 54` — end 2 seconds after quote
- `-c copy` — stream copy (fast, no re-encoding)

**Padding:** 3 seconds before, 2 seconds after.

**Adjacent clip merging:** If two clips from the same session are within 10 seconds of each other, merge into one clip. The merged clip gets the name of the first quote.

### Clip naming

The researcher in Scenario 1 is looking at 5–15 clips in a Finder window, deciding which 3 to play at the meeting. The filename is the only information they have without opening each one.

```
Bad:   s1_00m39s.mp4                                    <- means nothing
Bad:   clip-q-p1-42.mp4                                 <- means nothing
OK:    sarah-onboarding-was-confusing.mp4                <- no order, no grouping
Good:  p1 03m45 Sarah onboarding was confusing.mp4      <- code, timecode, speaker, gist
```

**Format:** `{code} {timecode} {speaker} {gist}.{ext}`

| Component | Source | Example |
|-----------|--------|---------|
| Code | Participant code from quote | `p1`, `p3` |
| Timecode | Quote start as `{mm}m{ss}` (or `{h}h{mm}m{ss}` if any session ≥ 1h) | `03m45`, `0h03m45` |
| Speaker | Display name (short_name) | `Sarah`, `James` |
| Gist | First ~6 words of quote text, lowercased | `onboarding was confusing` |

**Why participant code, not session number:** A clip is always one person speaking. The participant code groups all clips from one person together in sort order (`p1` before `p2`). The timecode sorts clips within a participant chronologically. No sequence numbers needed — natural sort order tells the story. This works identically for 1:1 and 1:many sessions because the clip always has exactly one speaker.

**Why spaces, not hyphens:** The gist is already lowercase, so the capitalised speaker name provides a natural visual boundary. Using hyphens in the gist *and* as a separator between components creates visual noise. Spaces are valid in filenames on all modern OSes (macOS, Windows 10+, Linux).

**Gist rules:**
- First ~6 words of quote text
- Lowercase
- Strip `' ' " " ? ! . , ; : ( )`
- Spaces preserved (not converted to hyphens)
- Max ~40 characters, break at word boundary
- No characters that break on Windows (no `: ? * < > | "`)

**When anonymised:**

Speaker name removed. Participant code zero-padded:

```
p01 03m45 onboarding was confusing.mp4
p01 17m02 i gave up after day two.mp4
p02 02m15 search never finds anything.mp4
```

### Participant code zero-padding in filenames

The pipeline uses `p1`, `p2` everywhere. Changing that globally is a huge surface area. But in export filenames, lexical sort order matters:

```
Unsorted:  p1, p10, p11, p2, p3, p9    <- wrong
Sorted:    p01, p02, p03, p09, p10, p11  <- correct
```

Zero-padding is applied **in the export layer only**, based on participant count:

| Participants | Padding | Example |
|-------------|---------|---------|
| 1–9 | No padding | `p1`, `p2` |
| 10–99 | 2 digits | `p01`, `p02`, `p12` |
| 100+ | 3 digits | `p001`, `p002` (unlikely) |

Display names in the report stay `p1`. This is `str.zfill()` — trivial code, conscious decision.

## Transcript export details

### Format: .txt with inline timecodes

Plain text. Opens in Notepad, searchable in Spotlight, pasteable into anything. No markup.

```
Acme Onboarding Research
p1 Sarah (Manager)
Recorded 14 Mar 2026 — 42 minutes

────────────────────────────────────────

[00:00] Moderator: Thanks for joining. Can you walk me through
your first day?

[00:15] Sarah: Sure. So I started on Monday, and honestly the
onboarding was really confusing. I didn't know where to start
and nobody showed me anything.

[01:02] Sarah: I think I clicked around for about twenty minutes
before I found the dashboard. And even then I wasn't sure if I
was looking at the right thing.

[01:35] Moderator: What would have helped?

[01:38] Sarah: Honestly just a checklist. Like "do this first,
then this." I ended up asking Jamie on Slack and he sent me a
screenshot.

────────────────────────────────────────
```

### Transcript naming

Transcript filenames use the same `{code} {name}` pattern as clips for consistency. The difference: transcripts don't have timecodes (one file per session) and 1:many sessions list all speakers.

**1:1 sessions:**

```
p1 Sarah.txt
p2 James.txt
p3 Priya.txt
```

Participant code gives sort order. Name gives the person.

**1:many sessions (focus groups, dyads):**

```
01 p1 Sarah p2 James.txt
02 p3 Priya p4 Mike p5 Jo.txt
```

Session number prefix (zero-padded) because the file contains multiple speakers — you need to know which session this was. All participant codes and names listed.

**When anonymised (1:1):**

```
p01.txt
p02.txt
```

**When anonymised (1:many):**

```
01 p01 p02.txt
02 p03 p04 p05.txt
```

Names removed. Codes zero-padded. Role titles removed entirely (role titles can be identifying — "the one manager in the study" narrows the person down).

### Transcript content with anonymisation

Speaker labels in the transcript body use participant codes instead of names. The transcript header uses the code only:

```
Acme Onboarding Research
p01
Recorded 14 Mar 2026 — 42 minutes

────────────────────────────────────────

[00:00] Moderator: Thanks for joining.

[00:15] p01: Sure. So I started on Monday, and honestly the
onboarding was really confusing.
```

Moderator names are preserved (they're the research team, not subjects).

### Existing infrastructure

The pipeline already writes `.txt` transcripts with inline timecodes:

- `bristlenose/utils/markdown.py` — formatting templates (`TRANSCRIPT_SEGMENT_RAW_TXT`, `format_timecode()`)
- `bristlenose/stages/s06_merge_transcript.py` — `write_raw_transcripts()` writes to `transcripts-raw/`
- `bristlenose/stages/s07_pii_removal.py` — `write_cooked_transcripts()` writes PII-redacted versions

The export transcript renderer reuses these formatters. The main new work is: (1) human-readable filenames instead of `s1.txt`, (2) speaker name resolution from the DB, (3) anonymisation pass on speaker labels.

## Anonymisation

The "Anonymise participants" checkbox provides lightweight anonymisation for external sharing. It is **not** a replacement for `--redact-pii`.

### What it strips

| Surface | What changes |
|---------|-------------|
| Report HTML | Participant full_name/short_name emptied, codes preserved |
| Clip filenames | Speaker name replaced with zero-padded participant code |
| Transcript filenames | Speaker name replaced with zero-padded participant code, role → "Participant" |
| Transcript body | Speaker labels use participant codes, not names |
| Folder name | Speaker names removed if present |

### What it keeps

- Moderator names (m1, m2) — they're the research team, not subjects
- Observer names (o1) — same logic
- Raw participant codes (p1, p2) — these are the anonymised identifiers
- All quote text, tags, stars, edits
- Names mentioned **within quote text** (use `--redact-pii` for that)
- Names in user-edited headings (user's responsibility)

### Messaging

> "Anonymise removes participant names from report metadata, filenames, and transcript headers. Names mentioned within quote text are not affected — use `bristlenose run --redact-pii` for deeper anonymisation."

## Export dialog

### Stage 1 dialog (transcripts only)

```
+---------------------------------------------------+
|  Export report                                     |
+---------------------------------------------------+
|                                                    |
|  [x] Include transcripts (.txt)                    |
|      Readable transcripts with timecodes.          |
|                                                    |
|  ------------------------------------------------  |
|                                                    |
|  [ ] Anonymise participants                        |
|      Remove participant names from report,         |
|      filenames, and transcripts. Keeps codes       |
|      (p1, p2). Moderator names preserved.          |
|                                                    |
+---------------------------------------------------+
|                          [Cancel]    [Export]       |
+---------------------------------------------------+
```

Export is instant — zip downloads immediately.

### Stage 2 dialog (transcripts + clips)

```
+---------------------------------------------------+
|  Export report                                     |
+---------------------------------------------------+
|                                                    |
|  [x] Include transcripts (.txt)                    |
|      Readable transcripts with timecodes.          |
|                                                    |
|  [ ] Include video clips                           |
|      Clips of starred quotes and signal card       |
|      highlights. Requires FFmpeg.                   |
|                                                    |
|  ------------------------------------------------  |
|                                                    |
|  [ ] Anonymise participants                        |
|      Remove participant names from report,         |
|      filenames, and transcripts. Keeps codes       |
|      (p1, p2). Moderator names preserved.          |
|                                                    |
+---------------------------------------------------+
|                          [Cancel]    [Export]       |
+---------------------------------------------------+
```

- Transcripts checkbox: default ON. Lightweight, always useful, instant
- Clips checkbox: default OFF. Heavy (FFmpeg processing), async
- Anonymise: available regardless of other options
- When clips is OFF: Export is instant — zip downloads immediately
- When clips is ON: Export triggers async server job

### Async clip processing (serve mode)

1. User checks "Include video clips", clicks Export
2. `POST /api/projects/{id}/package` — server starts background FFmpeg job
3. Export dialog closes. Toast appears: "Extracting video clips... (3 of 15)"
4. Toast updates with progress as clips complete
5. When done: toast changes to "Package ready" with a "Reveal" link
6. "Reveal" calls the OS to open the containing folder and select the zip file
7. On macOS: `open -R /path/to/zip` (Finder reveal). On Linux: `xdg-open` parent dir

### CLI mode

```bash
# Report + transcripts only (instant)
bristlenose export interviews/

# Report + transcripts + clips (requires FFmpeg)
bristlenose export --clips interviews/

# With anonymisation
bristlenose export --clips --anonymise interviews/
```

CLI shows Cargo-style progress for clip extraction:

```
  Exporting Acme Onboarding Research
  ✓ Report HTML                         0.4s
  ✓ Transcripts (3 sessions)            0.1s
  ✓ Clip 1/15: p1 03m45 Sarah                   0.8s
  ✓ Clip 2/15: p2 02m15 James                   0.6s
  ...
  ✓ Package complete                    12.3s

  → Acme Onboarding Research.zip (47 MB)
```

### Desktop app (future)

The macOS desktop app would trigger the same server endpoint but present the download as a native browser-style "download complete — click to reveal" notification. Standard macOS UX. Not a v1 concern.

## Folder naming

The zip extracts to a folder named after the project:

```
{project_name}.zip  →  {project_name}/
```

Project name comes from `slugify()` but with **spaces preserved** (not hyphenated) for human readability. Special characters stripped, but spaces and capitalisation kept:

```
"Acme Onboarding Research"  →  "Acme Onboarding Research/"
"Q1 2026: Mobile app"       →  "Q1 2026 Mobile app/"
```

## Branding footer

Every exported report includes a subtle CTA at the bottom:

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
- Optional `--no-branding` flag for enterprise users

## Technical details

### Zip structure

Built server-side with Python's `zipfile` module (no browser-side fflate needed — the server does all the work).

```python
with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"{folder_name}/report.html", html_content)
    for name, content in transcripts:
        zf.writestr(f"{folder_name}/transcripts/{name}", content)
    for name, path in clips:
        # MP4 is already compressed — ZIP_STORED avoids wasting CPU
        zf.write(path, f"{folder_name}/clips/{name}", compress_type=zipfile.ZIP_STORED)
```

HTML compresses well (~70% reduction). Video clips are already compressed (MP4) — storing them with `ZIP_STORED` avoids wasting CPU on incompressible data.

### Video map for export mode

When clips are included, the embedded `BRISTLENOSE_EXPORT` data includes a video map with relative paths:

```javascript
window.BRISTLENOSE_EXPORT.videoMap = {
  "q-p1-42": "clips/p1 03m45 Sarah onboarding was confusing.mp4",
  "q-p2-135": "clips/p2 02m15 James search never finds anything.mp4"
}
```

Keyed by quote DOM ID (not session ID) because multiple clips can come from the same session. The React player resolves quote ID → clip path → `<video src>`.

### Clip manifest (internal)

The server builds this in memory (not written to disk):

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
    is_starred: bool        # for future filtering
    is_hero: bool           # signal card hero
```

### Async job pattern

Reuses the AutoCode background task pattern:

1. `POST /api/projects/{id}/package` creates an `ExportJob` and starts `asyncio.create_task()`
2. `GET /api/projects/{id}/package/status` returns `{state, progress, total, current_clip, output_path}`
3. Frontend polls status, updates toast
4. On completion: `{state: "complete", output_path: "/path/to/Acme Onboarding Research.zip"}`
5. Frontend shows "Reveal" button that calls `GET /api/open-folder?path=...` → server runs `open -R` (macOS) or `xdg-open` (Linux)

### Media fallback

If the source media file is missing for a quote (text-only transcript, deleted file):
- That quote is skipped in clip extraction (no error, just a warning in progress output)
- No play button appears in the report for that quote
- The clip folder contains only clips that could actually be extracted

## Size estimates

| Component | Typical size | Notes |
|-----------|-------------|-------|
| report.html | 1–3 MB | Compressed in zip: ~300 KB |
| transcripts/ | 50–200 KB | Plain text, very small |
| clips/ (15 clips) | 30–80 MB | ~15s each, stream copy from source |
| clips/ (40 clips) | 80–200 MB | Upper bound for large studies |
| Total (no clips) | 1–3 MB | Instant download |
| Total (with clips) | 30–200 MB | Fine for SharePoint, email attachment borderline |

## Open questions

1. **Audio-only sessions** — extract clips as `.m4a` / `.mp3`? Or skip? Recommendation: extract as-is (FFmpeg stream copy preserves container format). If source is `.mp3`, clip is `.mp3`. Filename still follows the same pattern
2. **Maximum clip count** — should we warn if >50 clips? The zip could be 500MB+. Recommendation: warn but don't block
3. **Cross-platform file:// video** — inline `<video src="clips/...">` may not work on all browsers from `file://` due to security restrictions. Needs testing on Chrome, Firefox, Safari, Edge. Fallback: link opens the file in the OS default player

## Related files

### Existing (shipped)
- `bristlenose/server/routes/export.py` — current export endpoint (single HTML)
- `frontend/src/components/ExportDialog.tsx` — export dialog UI
- `frontend/src/utils/exportData.ts` — export mode detection, API path resolution
- `bristlenose/utils/markdown.py` — transcript formatting templates
- `bristlenose/stages/s06_merge_transcript.py` — raw transcript writing
- `bristlenose/stages/s07_pii_removal.py` — PII-redacted transcript writing
- `bristlenose/server/routes/dashboard.py` — `_pick_featured_quotes()` (signal card heroes)
- `bristlenose/server/autocode.py` — async job pattern to reuse

### New (to build)
- `bristlenose/server/routes/package.py` — async package job endpoint
- `bristlenose/server/packager.py` — zip builder, clip manifest, transcript renderer
- `bristlenose/server/clip_extractor.py` — FFmpeg wrapper, adjacent merge, naming
- `bristlenose/export/` — shared export utilities (naming, anonymisation, slugification)
- `frontend/src/components/PackageToast.tsx` — progress toast with reveal link

### Reference
- `docs/design-html-report.md` — report architecture
- `bristlenose/utils/video.py` — existing FFmpeg integration (thumbnails)
- `bristlenose/output_paths.py` — path construction patterns
