---
status: current
last-trued: 2026-09-28
trued-against: HEAD@main on 2026-09-28 (after 0.31.4)
---

# Word-Level Transcript Highlighting

> **Trued 28 Sep 2026 against 0.31.4.** The pipeline diagram put the merge *before* the intermediate file, which is the misreading that let word timings be joined to paragraphs by position for seven months (`a9d6fb47`); redrawn. Added the glow window (the last paragraph's end, `6dd8a1e4`), how the player's messages reach the page, and what renders when words are absent.

## Overview

When playing back a video interview, individual words in the transcript highlight in sync with the audio — like karaoke subtitles. This helps researchers pinpoint exact moments in speech and creates a visceral connection between the written transcript and the recorded conversation.

## How it works

### Data source

The word timing comes from Whisper (the speech-to-text engine). When Whisper transcribes audio, it doesn't just produce text — it records the exact start and end time of every word, along with a confidence score.

A typical word entry:

```
"works"  13.54s → 14.16s  (confidence: 0.96)
```

### Pipeline flow

```
┌─────────────────────────────┐
│  Audio file (mp4, m4a, wav) │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Whisper transcription      │  ← word_timestamps=True
│  (MLX or faster-whisper)    │
│                             │
│  Output per segment:        │
│  • text: "It works well"    │
│  • words: [                 │
│      {It, 12.92–13.54},    │
│      {works, 13.54–14.16}, │
│      {well, 14.16–14.42}   │
│    ]                        │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Intermediate JSON          │  ← persisted to disk BEFORE the
│  session_segments.json      │     merge: raw Whisper segments,
│  (pipeline.py)              │     segment_index = -1
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Segment merging            │  ← same-speaker runs merged;
│  (s06_merge_transcript.py)  │     written to transcripts-raw/
│                             │     *.txt WITHOUT word timings
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Serve-mode importer        │  ← rows from the .txt (merged),
│                             │     words from the JSON (raw)
│  _enrich_words_from_        │  ← reads JSON, matches by
│    intermediate()           │     time, verifies by text
│                             │
│  Compact JSON in SQLite:    │
│  [{"t":"It","s":12.92,     │
│    "e":13.54}, ...]         │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Transcript API             │
│  GET /api/.../transcripts/  │
│                             │
│  Response per segment:      │
│  "words": [                 │
│    {"text":"It",            │
│     "start":12.92,          │
│     "end":13.54},           │
│    ...                      │
│  ]                          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  React TranscriptPage       │
│                             │
│  Each word = <span> with    │
│  data-start, data-end       │
│                             │
│  PlayerContext adds          │
│  .bn-word-active at ~4Hz    │
│  during playback            │
└─────────────────────────────┘
```

### What happens in the browser

1. User opens a session transcript page
2. The page fetches transcript data from the API — each segment includes an array of words with timing
3. Each word is rendered as a `<span class="transcript-word" data-start="13.54" data-end="14.16">`
4. User clicks a timecode → popout video player opens
5. The player sends `bristlenose-timeupdate` messages ~4 times per second with the current playback position — on every `timeupdate`, so scrubbing drives it too. It posts to `window.opener` (`player.html`); a `BroadcastChannel` is opened only when there is no opener. In the Mac app the popout is created by `WKUIDelegate.createWebViewWith` and **does** get a live opener (measured 28 Sep 2026 with a harness mirroring `WebView.swift`), so the channel is a dormant fallback, not the live path
6. `PlayerContext` receives each update, finds the active segment (via the glow index), then scans its word spans to find which word matches the current timestamp. Word highlighting runs **only inside the glowing paragraph**, so a word outside that paragraph's `[start, end)` window never lights
7. The matching word gets a `.bn-word-active` CSS class (subtle highlight background)
8. As playback continues, the highlight moves word by word through the paragraph
9. The same update scrolls a newly active paragraph into view and fills its left-border progress bar (`--bn-segment-progress`)

**The glow window.** A paragraph's `start` is its `.txt` timecode and its `end` is the next paragraph's start. The **last** paragraph has no successor: since `6dd8a1e4` its end is the transcript's `# Duration:` header, which s06 writes from that paragraph's own end; the importer falls back to `start + 10 s` only when the header is absent or no later than the start. Before that fix the flat `+10 s` put the glow out — and with it the word highlight — 10 s into any final answer that ran longer.

### Graceful degradation

Not all sessions have word-level data:

| Source | Word timing? | Behaviour |
|--------|-------------|-----------|
| Whisper (MLX) | ✓ Yes | Words highlight individually |
| Whisper (faster-whisper) | ✓ Yes | Words highlight individually |
| VTT subtitle import | ✗ No | Segment-level glow only |
| SRT subtitle import | ✗ No | Segment-level glow only |
| DOCX import | ✗ No | Segment-level glow only |

When `words` is `null`, the paragraph renders its `html_text` (with the `<mark>` quote highlights) or, failing that, plain `text`, and the segment-level glow (background highlight on the whole paragraph) still works. When words *are* kept, the Whisper **word** text is what appears on screen — it can differ from the `.txt` text by the few tokens the ≥ 0.9 check tolerates, and it omits the `(Speaker A)` label the `.txt` carries.

Two more cases carry no word timings, by design:

- **PII-redacted projects** (`transcripts-cooked/` present). The intermediate JSON predates redaction and holds the original words, so the importer refuses to backfill and clears any rows an older import left.
- **Any paragraph whose words don't read as its text.** The word spans *replace* the paragraph text on screen, so a wrong pairing hides the real transcript. The importer keeps a paragraph's words only when they match its text (≥ 0.9 on the token sequence — Whisper's word and segment text disagree by a word or two on long segments).

### Matching words to transcript paragraphs

`session_segments.json` is written **before** stage 6 merges consecutive same-speaker segments, so it holds Whisper's raw segments (263 for an 18-minute interview), all with `segment_index = -1`, while the `.txt` the importer reads holds the merged ones (37). Each raw segment is assigned to the paragraph with the latest start at or before its own; the `.txt` timecode is the floor of the merged paragraph's first raw start, so the first raw segment always lands in its own paragraph.

Until 27 Sep 2026 the `-1` fell back to **list position**: paragraph 36 (17:32) got raw segment 36's words (2:30). Every diarised interview showed its first few minutes of speech smeared across the whole timeline, with most of the transcript missing. Pinned by `tests/test_serve_importer.py::TestWordEnrichment::test_merged_segments_get_their_own_words`.

## Storage format

Word data is stored in the SQLite `transcript_segments.words_json` column as compact JSON:

```json
[{"t":"It","s":12.92,"e":13.54},{"t":"works","s":13.54,"e":14.16}]
```

Short keys (`t`=text, `s`=start, `e`=end) and no whitespace keep the payload small. A 30-minute interview with ~5,000 words adds ~125KB to the database — negligible.

Confidence scores are captured by Whisper but not stored in the compact JSON (not needed for highlighting). They could be added later for visual confidence indicators (e.g. dimming low-confidence words).

## Files involved

| Layer | File | Role |
|-------|------|------|
| Pipeline | `bristlenose/stages/s05_transcribe.py` | Whisper word extraction |
| Pipeline | `bristlenose/models.py` | `Word` Pydantic model |
| Pipeline | `bristlenose/stages/s06_merge_transcript.py` | Preserves words during merge |
| Pipeline | `bristlenose/pipeline.py` | Writes `session_segments.json` (inline, after transcription, before s06) |
| Serve | `bristlenose/server/models.py` | `TranscriptSegment.words_json` ORM column |
| Serve | `bristlenose/server/db.py` | Schema migration for existing DBs |
| Serve | `bristlenose/server/importer.py` | `_enrich_words_from_intermediate()` |
| Serve | `bristlenose/server/routes/transcript.py` | `WordTimingResponse` in API |
| Frontend | `frontend/src/utils/types.ts` | `WordTiming` TypeScript type |
| Frontend | `frontend/src/islands/TranscriptPage.tsx` | Word span rendering |
| Frontend | `frontend/src/contexts/PlayerContext.tsx` | Word-level glow |
| Theme | `bristlenose/theme/atoms/timecode.css` | `.bn-word-active` style |

## Limitations and future work

- **VTT inline timestamps**: Some VTT files use `<00:01:02.500>word` inline timestamps. The current VTT parser doesn't extract these. A future enhancement could parse inline VTT word timestamps for imported subtitles
- **Quote highlighting reconciliation**: When word spans are rendered, the inline `<mark>` quote highlighting (from `html_text`) is skipped. Margin annotations still work. Reconciling word boundaries with quote boundaries is a future task
- **Confidence visualisation**: Whisper confidence scores could dim or underline low-confidence words, helping researchers spot potential transcription errors
- **Click-to-seek on words**: Individual words could become clickable — click a word to seek the player to that exact moment
