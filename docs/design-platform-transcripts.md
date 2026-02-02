# Platform transcript ingestion — design doc

**Status**: Phase 1 in progress — session matching (1a, 1b, 1c) and audio extraction skip done
**Created**: 2026-02-01

## Problem

Researchers run interviews on Microsoft Teams, Zoom, or Google Meet. These platforms
produce their own transcripts with real participant names from directory lookups — often
better speaker identification than local Whisper. They also produce video/audio recordings.

Bristlenose needs to:

1. Accept platform transcripts alongside (or instead of) its own Whisper transcription
2. Match a platform transcript to its corresponding video/audio file so timecodes in the
   report deep-link into the correct recording
3. Extract maximum metadata (speaker names, meeting title, date, participant list) from
   platform-native files
4. Handle the variety of file formats and naming conventions across the big three platforms

## What we already have

- **Stem matching** in `ingest.py` → `group_into_sessions()`: files sharing a filename
  stem (after stripping `_transcript`, `_subtitles`, `_captions`, `_sub`, `_srt`) are
  grouped into one session
- **VTT parser** handles `<v Speaker Name>text</v>` voice tags (Teams VTT works today)
- **SRT parser** handles `Speaker Name: text` colon prefix (Zoom VTT/SRT works today)
- **DOCX parser** handles Teams-style `Speaker Name  HH:MM:SS` headers
- **Name extraction** in `people.py` filters generic labels, keeps real names
- FFmpeg handles MP4, MOV, MKV, M4A, etc. for audio extraction

## Platform catalogue

### Microsoft Teams

| Artifact | Format | Naming convention | Metadata inside file |
|----------|--------|-------------------|---------------------|
| Recording | MP4 | `{Title} {YYYYMMDD}_{HHMMSS}-Meeting Recording.mp4` | No meeting ID; standard MP4 atoms only |
| Transcript | VTT | `{Title}.vtt` (downloaded via Recap UI) | Speaker names via `<v>` tags; ms timestamps; no meeting ID |
| Transcript | DOCX | `{Title}.docx` | Speaker names as styled text; elapsed-time timestamps |
| Transcript-only | MP4 shell | `{Title} {YYYYMMDD}_{HHMMSS}-meeting transcript.mp4` | VTT embedded in container, no A/V |

**Speaker names**: Entra ID display names ("Sarah Jones") — highly reliable for remote
participants joining from their own device. Real directory names, not voice recognition.

**Matching strategy**: Recording and transcript share the meeting title prefix. The
recording has `{Title} {date}_{time}-Meeting Recording.mp4`; the transcript is
`{Title}.vtt` / `{Title}.docx`. Match by title prefix after stripping the date/time
suffix and `-Meeting Recording` / `-meeting transcript` suffixes.

**Permissions**: Organizer/co-organizer can download both. Regular attendees typically
cannot download transcripts.

**Known issues**:
- VTT `<v>` tags are sometimes missing (known Teams bug); DOCX always has names
- DOCX can be excessively fragmented (one cue per pause, 150+ pages for 1 hour)
- No meeting ID in filenames — matching is title-based only

### Zoom

| Artifact | Format | Naming convention | Metadata inside file |
|----------|--------|-------------------|---------------------|
| Local video | MP4 | `zoom_0.mp4` (in session folder) | Meeting topic in MP4 title atom |
| Local audio | M4A | `audio_only.m4a` (in session folder) | Same |
| Local captions | VTT | `closed_caption.vtt` (in session folder) | Speaker names as `Name: text` prefix |
| Local chat | TXT | `chat.txt` (in session folder) | Wall-clock times, display names |
| Cloud video | MP4 | `{Topic}_{MeetingID}_{Date}.mp4` | — |
| Cloud audio | M4A | `{Topic}_{MeetingID}_{Date}.m4a` | — |
| Cloud transcript | VTT | `Audio Transcript_{Topic}_{MeetingID}_{Date}.vtt` | Speaker names as `Name: text` prefix |
| Cloud chat | TXT | `chat_{MeetingID}_{Date}.txt` | — |

**Session folder naming**: `{YYYY-MM-DD} {HH.MM.SS} {Topic} {MeetingID}/`

**Speaker names**: Zoom display names — reliable when participants are signed in.
Phone dial-in shows as phone number or "Call-in User 1".

**Matching strategy**:
- *Local*: all files are co-located in one folder. The folder IS the session. If a user
  drops the whole folder into the input directory, all files auto-match.
- *Cloud*: meeting ID appears in all filenames — match by extracting the numeric ID.

**Permissions**: host can download everything. Participants need sharing enabled.

### Google Meet

| Artifact | Format | Naming convention | Metadata inside file |
|----------|--------|-------------------|---------------------|
| Recording | MP4 | `{Title} ({YYYY-MM-DD at HH MM GMT±X}).mp4` | Standard MP4 atoms |
| Chat log | SBV | `{Title} ({YYYY-MM-DD at HH MM GMT±X}).sbv` | Speaker names, relative timestamps |
| Transcript | Google Doc | `{Title} ({YYYY-M-DD at HH:MM TZ}) - Transcript` | Speaker names, ~5-min timestamps, attendee list |
| Transcript (downloaded) | DOCX | Same name + `.docx` | Same content |

**Speaker names**: Google Account display names — less reliable than Teams. Known
misattribution issues.

**Matching strategy**: Recording and transcript share the calendar event title and a
date/time stamp. Match by title prefix after stripping the parenthetical date and
`- Transcript` suffix.

**Timestamps**: Only ~5-minute granularity in transcripts. This is a significant
limitation — deep-linking to exact moments in video will be approximate at best.

**Permissions**: requires Business Standard or higher. Meeting organizer gets files.

**New format**: SBV (SubViewer) for chat — not currently parsed by Bristlenose.

### Supplementary sources

| Source | Recording format | Transcript format | Speaker IDs? |
|--------|-----------------|-------------------|-------------|
| Otter.ai | N/A | TXT, DOCX, SRT | Yes (tagged or "Speaker N") |
| macOS Voice Memos | M4A | Plain text (no structure) | No |
| macOS screen recording | MOV | N/A | N/A |
| iOS screen recording | MP4 (`RPReplay_Final{unix}.MP4`) | N/A | N/A |
| OBS Studio | MKV/MP4 | N/A | N/A |
| Loom | MP4 | SRT | No (single speaker) |
| Rev.com | N/A | DOCX, TXT, SRT, VTT | Yes ("Speaker N" or named) |

## Clustered work items

### Cluster 1 — Smarter session matching (file pairing)

Make `group_into_sessions()` understand platform naming conventions so that a video file
and its platform transcript are automatically paired even when stems don't match.

- [x] **1a. Teams suffix stripping**: strip `-Meeting Recording`, date/time suffix
  (`{YYYYMMDD}_{HHMMSS}`), and `-meeting transcript` from stems before matching
- [x] **1b. Zoom folder-as-session**: when an input subdirectory looks like a Zoom local
  recording folder (`YYYY-MM-DD HH.MM.SS {Topic} {ID}/`), treat all files inside as one
  session regardless of individual filenames
- [x] **1c. Zoom cloud ID matching**: extract the numeric meeting ID from Zoom cloud
  download filenames (`{Topic}_{ID}_{Date}`) and group files sharing the same ID
- [x] **1d. Google Meet title+date matching**: strip `({date})` parenthetical and
  `- Transcript` suffix, then match by normalised title (Phase 2 prep — regex ready)
- [ ] **1e. General fuzzy matching fallback**: when exact stem match fails, try Levenshtein
  or token-set similarity on normalised stems; require high threshold (e.g. 0.85) to
  avoid false positives
- [ ] **1f. Manual override**: `bristlenose.toml` option to explicitly pair files:
  ```toml
  [[sessions]]
  video = "User Research 20260130_093012-Meeting Recording.mp4"
  transcript = "User Research.vtt"
  ```

### Cluster 2 — New format parsers

Add parsers for formats not currently handled.

- [ ] **2a. SBV parser** (Google Meet chat subtitles): similar to SRT but with
  `H:MM:SS.mmm,H:MM:SS.mmm` timestamp format and no cue numbers
- [ ] **2b. Otter TXT parser**: `Speaker Name  M:SS` header line, text on next lines,
  blank line between segments — similar structure to Teams DOCX
- [ ] **2c. Rev/Descript TXT parser**: `Speaker N (HH:MM:SS):` header format; also handle
  notation tags like `[inaudible]`, `[crosstalk]`
- [ ] **2d. Google Meet DOCX parser**: different structure from Teams DOCX — has header
  block with meeting title + attendee list, then `Speaker Name  HH:MM` blocks with
  ~5-minute granularity. Needs separate heuristic from Teams DOCX detection

### Cluster 3 — Platform transcript preference ("trust the platform")

When a session has both a platform transcript and an audio file, let the user choose
whether to use the platform transcript or re-transcribe with Whisper.

- [ ] **3a. Transcript source priority config**: `bristlenose.toml` setting:
  ```toml
  transcript_source = "platform"  # "platform" | "whisper" | "auto"
  ```
  `auto` (default): use platform transcript when available, fall back to Whisper.
  `platform`: error if no platform transcript found.
  `whisper`: always re-transcribe (current behaviour).
- [ ] **3b. Skip Whisper when platform transcript exists**: in the pipeline, after
  ingestion + parsing, if a session already has parsed transcript segments from a
  platform file, skip audio extraction + transcription stages for that session
- [ ] **3c. Preserve platform speaker names**: when using platform transcripts, carry
  speaker labels through to `people.yaml` auto-population. These names are directory-
  quality — higher confidence than Whisper + LLM extraction
- [ ] **3d. CLI flag**: `--transcript-source platform|whisper|auto` as a one-off override
  without editing config

### Cluster 4 — Video-to-timecode linking

Ensure that even when using a platform transcript, the HTML report can deep-link into the
original video file via timecodes.

- [ ] **4a. Store video file path per session**: the `Session` model needs to track which
  video file (if any) is associated, separately from the transcript source
- [ ] **4b. Transcript-video time alignment**: platform transcripts use elapsed time from
  meeting start. The video also starts at meeting start. No offset should be needed in
  the common case — but validate this assumption with real files
- [ ] **4c. Video player integration**: transcript pages currently use `initPlayer()`.
  Extend to handle local file paths or a "drop your video here" experience in the
  browser so the researcher can play segments
- [ ] **4d. Google Meet 5-minute granularity**: when transcript timestamps are coarse
  (~5 min), consider interpolating approximate timestamps for individual segments based
  on word count / speaking rate, and flag them as approximate in the UI

### Cluster 5 — Metadata extraction from platform files

Extract meeting metadata that platform files contain but Bristlenose currently ignores.

- [ ] **5a. Meeting title from filename**: parse the meeting/calendar title from Teams,
  Zoom, and Google Meet filename conventions. Use as project name or session label
- [ ] **5b. Meeting date/time from filename**: parse dates from filename patterns. Use as
  session date (more reliable than file creation date, which changes on copy/download)
- [ ] **5c. Attendee list from Google Meet DOCX**: the transcript header contains a list
  of attendees — extract to seed `people.yaml`
- [ ] **5d. Zoom meeting ID preservation**: store the numeric Zoom meeting ID as session
  metadata — useful if the researcher later wants to cross-reference with Zoom admin
  portal or API
- [ ] **5e. Teams VTT metadata format**: if obtained via Graph API, the metadata VTT has
  absolute timestamps and language per utterance — parse this richer format

### Cluster 6 — User workflow documentation

Researchers need clear guidance on how to get files out of each platform.

- [ ] **6a. "Getting your files" guide**: a section in README or a standalone doc covering:
  - Teams: how to download recording + transcript (organizer must do it)
  - Zoom: local vs cloud recordings, where files end up
  - Google Meet: where to find recording + transcript in Drive, how to download DOCX
  - Otter/Rev: export steps
  - Screen recordings: where macOS/iOS save files
- [ ] **6b. Recommended file organisation**: suggest a folder structure for researchers:
  ```
  project/
    input/
      p1-sarah/
        interview.mp4
        interview.vtt
      p2-mike/
        User Research 20260130_093012-Meeting Recording.mp4
        User Research.docx
  ```
- [ ] **6c. Doctor check for session pairing**: add a doctor check or pipeline warning
  when a video file has no matching transcript (or vice versa), suggesting the user
  check their file names or use the manual override

## Market data and sequencing

### Platform market share (2025-2026)

**By videoconferencing software market share (vendor revenue):**

| Platform | Software market share | Daily/monthly active users |
|----------|---------------------|---------------------------|
| Zoom | ~56% | ~300M+ meeting participants/day |
| Microsoft Teams | ~32% | 320M daily active users |
| Google Meet | ~5.5% | Dominant in education (62% of students) |
| Cisco Webex | ~7.6% | Mostly government/regulated industries |

**By professional usage (survey, multi-select):**
- Zoom: 71% of professionals use it
- Teams: 53%
- Google Meet: 44%

**The dual-platform reality**: 61% of hybrid companies use at least two platforms.
Typical pattern: Teams for internal meetings, Zoom for external/client-facing calls.

### Where UX research happens

**Zoom is the de facto standard for qualitative research.** Mentioned 130+ times in
User Interviews' State of Research Report. Researchers prefer it because participants
already know it (56% cite simplicity as key benefit). 91% of virtual conferences use Zoom.

**Teams dominates corporate internal research.** 59% of mid-to-large enterprises use
Teams as primary comms. If you're researching with colleagues or internal users, it's
Teams. If you're researching with external participants, it's Zoom.

**Google Meet is the SMB/startup/education choice.** Strongest in organisations using
Google Workspace. 64% of Meet sessions start on mobile. Low market share but sticky in
its niche.

### Enterprise vs SMB

| Segment | Primary platform | Secondary | Notes |
|---------|-----------------|-----------|-------|
| Enterprise (1000+) | Teams | Zoom | Teams bundled with M365; Zoom for externals |
| Mid-market (100-999) | Teams or Zoom | Google Meet | Split roughly evenly |
| SMB (<100) | Zoom | Google Meet | Price-sensitive; Google Workspace common |
| Startups | Google Meet | Zoom | Workspace is cheap; Zoom for investor calls |
| Education | Google Meet (62%) | Zoom (38%) | — |
| UX research (external participants) | Zoom (~70%+) | Teams | Participants prefer Zoom |
| UX research (internal participants) | Teams | Zoom | Follows org's primary platform |

### Transcription services (for supplementary parser priority)

| Service | Market position | Relevance to Bristlenose |
|---------|----------------|-------------------------|
| Otter.ai | ~95% accuracy, popular with researchers | High — SRT export works today; TXT needs parser |
| Fireflies.ai | 90-93% accuracy, CRM-focused | Low — overlaps with Otter |
| Fathom | Free unlimited tier, disruptive | Low — small user base |
| Rev.com | $0.25/min AI, $1.99/min human | Medium — used when accuracy matters |

### Sequencing by market data

The market data confirms Zoom and Teams should be co-equal P1, with Google Meet as P2.
But we need to factor in what already works vs what needs building:

**What already works today (no code changes needed):**
- Zoom VTT/SRT → `parse_subtitles.py` handles `Name: text` prefix ✓
- Teams VTT → `parse_subtitles.py` handles `<v Name>text</v>` tags ✓
- Teams DOCX → `parse_docx.py` handles `Name  HH:MM:SS` headers ✓
- All video/audio formats → FFmpeg handles MP4/MOV/MKV/M4A ✓

**What breaks today (needs work):**
- File matching: Teams recording + transcript have mismatched stems ✗
- File matching: Zoom local recording folder structure not understood ✗
- File matching: Google Meet `- Transcript` suffix not stripped ✗
- Pipeline always runs Whisper even when platform transcript exists ✗
- Google Meet DOCX has different structure from Teams DOCX ✗
- Google Meet timestamps are ~5-minute granularity ✗

This gives us the implementation sequence:

### Implementation sequence

#### Phase 1 — "It just works for Zoom and Teams" (P1)

Covers ~88% of professional video conferencing. Zoom and Teams files are already
parseable — we just need to match them and skip Whisper.

| Item | Cluster | Scope | Status |
|------|---------|-------|--------|
| 1a. Teams suffix stripping | 1 | Strip `-Meeting Recording` and date from stems | **Done** |
| 1b. Zoom folder-as-session | 1 | Detect Zoom local folder pattern, group contents | **Done** |
| 1c. Zoom cloud ID matching | 1 | Extract meeting ID from cloud download filenames | **Done** |
| 3a. Transcript source config | 3 | `transcript_source` in `bristlenose.toml` | |
| 3b. Skip Whisper + audio extraction | 3 | Skip transcription + FFmpeg when platform transcript parsed | **Done** (audio skip) |
| 3c. Preserve platform names | 3 | Higher-confidence names from directory lookups | |
| 3d. CLI flag | 3 | `--transcript-source` override | |
| 5a. Meeting title from filename | 5 | Parse title from Teams/Zoom conventions | |
| 5b. Meeting date from filename | 5 | Parse date from filename patterns | |

#### Phase 2 — "Google Meet + metadata" (P2)

Covers the remaining ~5% of the market but includes some quick wins.

| Item | Cluster | Scope |
|------|---------|-------|
| 1d. Google Meet title+date matching | 1 | Strip parenthetical date + `- Transcript` |
| 2d. Google Meet DOCX parser | 2 | Different heuristic from Teams DOCX |
| 5c. Attendee list from Meet DOCX | 5 | Extract attendees to seed `people.yaml` |
| 4d. Google Meet timestamp interpolation | 4 | Handle 5-minute granularity |
| 5d. Zoom meeting ID preservation | 5 | Store in session metadata |

#### Phase 3 — "Supplementary sources + polish" (P3)

Long tail of transcription services, video linking, manual overrides.

| Item | Cluster | Scope |
|------|---------|-------|
| 2b. Otter TXT parser | 2 | `Speaker Name  M:SS` format |
| 2c. Rev/Descript TXT parser | 2 | `Speaker N (HH:MM:SS):` format |
| 2a. SBV parser | 2 | Google Meet chat — low priority |
| 1e. Fuzzy matching fallback | 1 | Levenshtein on normalised stems |
| 1f. Manual override in toml | 1 | Explicit file pairing |
| 4a-c. Video player integration | 4 | Local file playback in browser |
| 5e. Teams Graph API VTT | 5 | Rich metadata format — niche |
| 6a-c. Documentation | 6 | Getting-your-files guide |

### Effort rationale

Phase 1 is mostly changes to `ingest.py` (session grouping) and `pipeline.py` (skip
logic). The parsers already exist. Estimated: 6 work items touching 3-4 files.

Phase 2 adds a new DOCX heuristic and some filename parsing. Estimated: 5 work items,
one new parser variant.

Phase 3 is a grab-bag of nice-to-haves. Can be done incrementally as users request them.

## Platform format quick-reference

### Filename patterns (regex-ready)

```
# Teams recording
^(?P<title>.+)\s+(?P<date>\d{8})_(?P<time>\d{6})-Meeting Recording\.mp4$

# Teams transcript (downloaded)
^(?P<title>.+)\.(?:vtt|docx)$

# Zoom local folder
^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}\.\d{2}\.\d{2})\s+(?P<topic>.+?)\s+(?P<id>\d+)$

# Zoom cloud download
^(?:Audio Transcript_)?(?P<topic>.+?)_(?P<id>\d{9,11})_(?P<date>\w+_\d+_\d{4})\.(?:mp4|m4a|vtt|txt)$

# Google Meet recording
^(?P<title>.+?)\s+\((?P<date>\d{4}-\d{1,2}-\d{1,2})\s+at\s+(?P<time>\d{1,2}\s+\d{2})\s+(?P<tz>GMT[+-]\d+)\)\.mp4$

# Google Meet transcript (downloaded DOCX)
^(?P<title>.+?)\s+\((?P<date>.+?)\)\s*[-–]\s*Transcript\.docx$
```

### Speaker label formats by platform

| Platform | Format in VTT/SRT | Example |
|----------|-------------------|---------|
| Teams VTT | `<v Name>text</v>` | `<v Sarah Jones>Hello</v>` |
| Teams DOCX | `Name  HH:MM:SS` header | `Sarah Jones  0:03:12` |
| Zoom VTT/SRT | `Name: text` prefix | `Sarah Jones: Hello everyone` |
| Google Meet DOCX | `Name  HH:MM` header | `Sarah Jones  00:05` |
| Otter TXT | `Name  M:SS` header | `Speaker 1  0:49` |
| Rev TXT | `Name (HH:MM:SS):` | `Speaker 1 (00:00:00):` |

## Open questions

1. **SBV priority**: Google Meet SBV files are chat logs, not spoken transcripts. How
   useful are they for research analysis? Probably low priority.
2. **Zoom `.zoom` files**: very old Zoom clients saved proprietary `.zoom` files needing
   conversion. Worth supporting? Probably not — modern Zoom saves MP4 directly.
3. **Teams Graph API**: the metadata VTT format (absolute timestamps, language, meeting
   ID) is much richer than the download VTT. But it requires API access. Should
   Bristlenose support importing it, or is that too niche?
4. **Google Meet 5-minute timestamps**: is interpolation (estimated per-segment
   timestamps) better or worse than showing approximate "nearest 5 minutes" timecodes?
5. **Multiple transcript sources per session**: what if a researcher has both a Teams VTT
   and an Otter SRT for the same interview? Which wins? Should we merge?
