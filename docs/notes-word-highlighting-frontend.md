# Word-Level Transcript Highlighting — Frontend Implementation Prompt

**Branch:** `react-router`
**Prerequisite:** Backend plumbing committed (`6772246`) — word timing data flows from pipeline → SQLite → API.

## What exists now

The transcript API (`GET /api/projects/{id}/transcripts/{sid}`) now returns `words` on each segment:

```json
{
  "segments": [
    {
      "speaker_code": "m1",
      "start_time": 12.92,
      "end_time": 18.74,
      "text": "It works well for me. It's lovely.",
      "words": [
        {"text": "It", "start": 12.92, "end": 13.54},
        {"text": "works", "start": 13.54, "end": 14.16},
        {"text": "well", "start": 14.16, "end": 14.42},
        ...
      ],
      ...
    }
  ]
}
```

- `words` is `null` for VTT/SRT-only sessions (no Whisper run) — graceful degradation required.
- Real data verified: project-ikea has 229/229 segments with word timing.

## What needs building (3 files + 1 CSS file + tests)

### 1. Types: `frontend/src/utils/types.ts`

Add `WordTiming` type and `words` field to `TranscriptSegmentResponse`:

```typescript
export interface WordTiming {
  text: string;
  start: number;
  end: number;
}

export interface TranscriptSegmentResponse {
  // ... existing fields ...
  words: WordTiming[] | null;
}
```

### 2. TranscriptPage: `frontend/src/islands/TranscriptPage.tsx`

Currently the segment body renders as (line ~621):

```tsx
<div className="segment-body">
  {seg.html_text ? (
    <span dangerouslySetInnerHTML={{ __html: seg.html_text }} />
  ) : (
    <>{seg.text}</>
  )}
</div>
```

When `seg.words` is available, render each word as a `<span>`:

```tsx
<div className="segment-body">
  {seg.words && seg.words.length > 0 ? (
    seg.words.map((w, i) => (
      <span
        key={i}
        className="transcript-word"
        data-start={w.start}
        data-end={w.end}
      >
        {w.text}{i < seg.words!.length - 1 ? ' ' : ''}
      </span>
    ))
  ) : seg.html_text ? (
    <span dangerouslySetInnerHTML={{ __html: seg.html_text }} />
  ) : (
    <>{seg.text}</>
  )}
</div>
```

**Note:** When words exist, we render from word data and skip `html_text` (the `<mark>` quote highlighting). Margin annotations still show which text is quoted. This is an acceptable trade-off — reconciling word spans with quote marks is a future enhancement.

### 3. PlayerContext: `frontend/src/contexts/PlayerContext.tsx`

Extend `updateGlow` — when the active transcript segment has `.transcript-word` children, highlight the current word:

```typescript
// Inside the newActive.forEach loop, after setting --bn-segment-progress:
if (entry && el.classList.contains("transcript-segment")) {
  // Word-level highlighting
  const wordSpans = el.querySelectorAll<HTMLElement>(".transcript-word[data-start][data-end]");
  wordSpans.forEach((ws) => {
    const wStart = parseFloat(ws.getAttribute("data-start") ?? "");
    const wEnd = parseFloat(ws.getAttribute("data-end") ?? "");
    if (seconds >= wStart && seconds < wEnd) {
      ws.classList.add("bn-word-active");
    } else {
      ws.classList.remove("bn-word-active");
    }
  });
}
```

Also clear `bn-word-active` in the glow-removal path and in `clearAllGlow()`.

### 4. CSS: `bristlenose/theme/atoms/timecode.css`

```css
.transcript-word.bn-word-active {
  background: color-mix(in srgb, var(--bn-colour-accent) 20%, transparent);
  border-radius: 2px;
  transition: background 0.1s ease;
}

@media (prefers-reduced-motion: reduce) {
  .transcript-word.bn-word-active {
    text-decoration: underline;
    text-decoration-color: var(--bn-colour-accent);
    background: none;
    transition: none;
  }
}
```

### 5. Tests

- **TranscriptPage test:** verify word spans render when `words` data present, fallback to `text` when `null`
- **PlayerContext test:** verify `bn-word-active` class applied to correct word element at given timestamp, cleared when moving to next word
- **Types:** no test needed (TypeScript compiler catches mismatches)

## Key constraints

- **Don't break VTT-only sessions** — when `words` is `null`, the existing rendering (plain text or `html_text`) must still work
- **Performance:** `querySelectorAll` inside `updateGlow` runs at ~4Hz. For a typical segment of 10–30 words, this is negligible. If profiling shows issues, consider building a word index alongside the glow index
- **`html_text` trade-off:** When words exist, we skip the inline `<mark>` quote highlighting. Margin annotations (labels, badges, tags) still work. The reconciliation (mapping quote boundaries to word spans) is a future enhancement
- **CSS in `bristlenose/theme/`** — CSS changes need a `bristlenose render` to take effect in serve mode (CSS is baked at render time, not live-reloaded like Vite JS)

## Verification

1. `bristlenose serve trial-runs/project-ikea --dev`
2. Open `/report/sessions/s1`, click a timecode, play video
3. Words should highlight one by one as spoken
4. Test a VTT-only session — should fall back to plain text rendering
5. `npm run build` (includes `tsc -b` which type-checks test files)
6. `npx vitest run`
