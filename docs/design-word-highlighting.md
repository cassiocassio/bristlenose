# Word-Level Transcript Highlighting

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
│  Segment merging            │  ← word lists concatenated
│  (merge_transcript.py)      │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Intermediate JSON          │
│  session_segments.json      │  ← persisted to disk
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Serve-mode importer        │
│  _enrich_words_from_        │  ← reads JSON, matches by
│    intermediate()           │     segment_index
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
5. The player sends `bristlenose-timeupdate` messages ~4 times per second with the current playback position
6. `PlayerContext` receives each update, finds the active segment (via the glow index), then scans its word spans to find which word matches the current timestamp
7. The matching word gets a `.bn-word-active` CSS class (subtle highlight background)
8. As playback continues, the highlight moves word by word through the paragraph

### Graceful degradation

Not all sessions have word-level data:

| Source | Word timing? | Behaviour |
|--------|-------------|-----------|
| Whisper (MLX) | ✓ Yes | Words highlight individually |
| Whisper (faster-whisper) | ✓ Yes | Words highlight individually |
| VTT subtitle import | ✗ No | Segment-level glow only |
| SRT subtitle import | ✗ No | Segment-level glow only |
| DOCX import | ✗ No | Segment-level glow only |

When `words` is `null`, the transcript renders as plain text and the segment-level glow (background highlight on the whole paragraph) still works.

## Storage format

Word data is stored in the SQLite `transcript_segments.words_json` column as compact JSON:

```json
[{"t":"It","s":12.92,"e":13.54},{"t":"works","s":13.54,"e":14.16}]
```

Short keys (`t`=text, `s`=start, `e`=end) and no whitespace keep the payload small. A 30-minute interview with ~5,000 words adds ~125KB to the database — negligible for a local-first tool.

Confidence scores are captured by Whisper but not stored in the compact JSON (not needed for highlighting). They could be added later for visual confidence indicators (e.g. dimming low-confidence words).

## Files involved

| Layer | File | Role |
|-------|------|------|
| Pipeline | `bristlenose/stages/transcribe.py` | Whisper word extraction |
| Pipeline | `bristlenose/models.py` | `Word` Pydantic model |
| Pipeline | `bristlenose/stages/merge_transcript.py` | Preserves words during merge |
| Pipeline | `bristlenose/stages/render_output.py` | Writes to `session_segments.json` |
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
