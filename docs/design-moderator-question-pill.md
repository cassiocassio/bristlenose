# Design: Moderator Question Pill

## What it does

Reveals the preceding moderator question/statement before a participant quote in the report. Helps researchers see conversational context without cluttering the default view.

## Interaction

1. **Hover** the first ~3 words of a quote (cursor changes to `?` via `cursor: help`)
2. After **300ms**, a "Question?" pill drops in from above (float-down animation)
3. **Click** the pill → moderator question expands **above the quote row** (not inline with it — the timecode belongs to the participant's quote)
4. **Hover** the moderator badge → red × dismiss button appears
5. **Click ×** → question dismissed, pill hidden, localStorage cleared
6. **Long text** → first sentence shown, then `more…` button to reveal the rest
7. **Refresh** → previously-opened questions restore from localStorage

## Visual design

- **Pill** (`.moderator-pill`): mono font, 0.65rem, badge-bg colour, subtle shadow. Positioned absolutely inside `.quote-body` at `top: calc(-1.1rem - 1px); left: 0` — floats 1rem above the first word of the quote text (not the timecode). Float-down entrance animation: `translateY(-8px) → translateY(0)` + opacity fade. Three states: hidden (default), `.visible` (hovering), `.moderator-pill-active` (question pinned open, accent tint)
- **Moderator question row** (`.moderator-question-row`): sits above the participant's `.quote-row` at `<blockquote>` level. Uses the same `display: flex` layout as `.quote-row` with a **hidden timecode spacer** (`visibility: hidden`, same text as the real timecode) — this gives identical left alignment regardless of timecode length. `margin-bottom: 0` (no gap between moderator row and quote row)
- **Moderator question block** (`.moderator-question`): `display: block; flex: 1; min-width: 0` — fills the flex column. Block layout means the badge sits inline at the start of the first line, and long text wraps to the **left margin** (not indented past the badge). Muted colour, 0.85rem
- **Question text** (`.moderator-question-text`): italic. Badge is non-italic
- **Badge wrapper** (`.moderator-question-badge`): `inline-flex` with `margin-right: 0.4rem`, `vertical-align: baseline` — reuses PersonBadge component
- **Dismiss ×** (`.moderator-question-dismiss`): reuses `.badge-delete` pattern (red circular button, `position: absolute` on badge, `opacity: 0` → `1` on hover of `.moderator-question`)
- **`more…` button** (`.moderator-question-more`): mono font, accent colour, `margin-left: 0.3rem`, no border/background. Splits at first sentence boundary via `splitFirstSentence()` regex
- **Hover zone** (`.quote-hover-zone`): `position: absolute; width: 14em; height: 1.6em; cursor: help` — covers first ~3 words only, hidden when question is open
- **Researcher context**: hidden when `segment_index > 0` (verbatim moderator question available) — still shows for legacy quotes (`segment_index <= 0`)

## DOM structure

```
<blockquote class="quote-card">
  [context line — hidden when hasModeratorContext]
  <div class="quote-row moderator-question-row">       ← above the quote, same flex layout
    <span class="timecode" visibility:hidden>[00:26]</span>  ← ghost spacer for alignment
    <div class="moderator-question">
      <span class="moderator-question-badge">
        <PersonBadge code="m1" role="moderator" />
        <button class="moderator-question-dismiss">×</button>
      </span>
      <span class="moderator-question-text">
        First sentence.
        <button class="moderator-question-more">more…</button>
      </span>
    </div>
  </div>
  <div class="quote-row">
    <span class="timecode">[00:26]</span>
    <div class="quote-body">
      <button class="moderator-pill [visible] [moderator-pill-active]">Question?</button>
      <span class="quote-hover-zone" />  <!-- hidden when question open -->
      <EditableText ... />
      <span class="speaker">— p1 Rachel</span>
      <div class="badges">...</div>
    </div>
  </div>
</blockquote>
```

## Files

### Backend
| File | Purpose |
|------|---------|
| `bristlenose/server/routes/quotes.py` | `GET /api/projects/{id}/quotes/{dom_id}/moderator-question` endpoint — queries `TranscriptSegment` for preceding moderator segment using `segment_index` |
| `bristlenose/server/routes/quotes.py` | `ModeratorQuestionResponse` Pydantic model (text, speaker_code, start_time, end_time, segment_index) |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/islands/QuoteCard.tsx` | Renders pill, moderator question block, hover zone, dismiss button |
| `frontend/src/islands/QuoteGroup.tsx` | State management: `openQuestions` (Set from localStorage), `modQuestionCache` (Record), `pillVisibleFor` (string\|null), 300ms hover timer, toggle/hover handlers |
| `frontend/src/utils/types.ts` | `ModeratorQuestionResponse` TypeScript interface |
| `frontend/src/utils/api.ts` | `getModeratorQuestion(domId)` fetch helper — returns null on 404 |

### CSS
| File | Purpose |
|------|---------|
| `bristlenose/theme/atoms/moderator-question.css` | All moderator question CSS: hover zone, pill, expanded block, badge wrapper, dismiss button, more… button, reveal animation |
| `bristlenose/stages/render_html.py` | `"atoms/moderator-question.css"` included in `_THEME_FILES` list |

### Tests
| File | Count | Coverage |
|------|-------|----------|
| `tests/test_moderator_question_api.py` | 9 tests | 404s, happy path, response shape, non-adjacent moderator, edge cases |
| `frontend/src/islands/QuoteCard.test.tsx` | 20 tests | Pill rendering, visibility, active class, click handlers, question block, more… button, first-sentence splitting, hover zone, context hiding, dismiss button, quote-body alignment |

### Mockup
| File | Purpose |
|------|---------|
| `docs/mockups/moderator-question-pill.html` | Interactive mockup with 6 states, toggle controls, uses real design system classes |

## Key decisions

- **Lazy per-quote fetch**: API call only when user clicks the pill — no batch pre-fetch on page load
- **localStorage persistence**: `bristlenose-mod-questions` key stores array of open quote dom_ids — survives page refresh
- **Hover zone scoping**: 14em × 1.6em absolute overlay covers only first ~3 words — not the entire quote text
- **Block layout for wrapping**: `.moderator-question` uses `display: block` so long moderator text wraps to left margin, not indented past the badge
- **Pill inside `.quote-body`**: positioned relative to `.quote-body` (not `.quote-card`) so `left: 0` aligns with the first word of the quote, not the timecode
- **Moderator question above the quote**: sits in its own `.quote-row.moderator-question-row` with a hidden timecode spacer (`visibility: hidden`) — aligns moderator text with quote text using the same flex layout. The timecode belongs to the participant's quote, not the moderator's context
- **Ghost timecode spacer**: the hidden timecode renders the same text as the real timecode so the flex column widths match exactly, regardless of timecode length (e.g. `[00:26]` vs `[1:02:34]`)

## Design iterations (why it's this way)

These decisions were reached through iterative design review on the rendered mockup:

1. **Pill position: above quote text, not timecode.** First attempt used `left: 1rem` on `.quote-card` — pill ended up above `[00:26]`. Fix: move pill into `.quote-body` with `left: 0`
2. **Pill height: 1rem above, not flush.** First attempt used `top: calc(-0.1rem - 1px)` — pill crashed into the moderator text below. Fix: `top: calc(-1.1rem - 1px)` for 1rem clearance
3. **Moderator text alignment: same indent as quote.** First attempt had the moderator block at full `<blockquote>` width (starting at the left card edge, alongside the timecode). Fix: wrap in `.quote-row` with hidden timecode spacer so the flex layout gives identical indentation
4. **Moderator text above, not inline.** First attempt put the moderator block inside `.quote-body` (same column as the quote text, after the timecode). But the timecode is the participant's timecode — it doesn't belong to the moderator's utterance. Fix: lift to its own `.quote-row` above the quote row
5. **Long text wraps to left margin.** First attempt used `display: flex` — text wrapped indented to the right of the badge. Fix: `display: block` so badge is inline and text wraps naturally
6. **300ms hover delay.** First attempt used 400ms — felt sluggish. 300ms feels responsive
7. **Badge not italic.** First attempt had `font-style: italic` on `.moderator-question` — made the PersonBadge italic too. Fix: move italic to `.moderator-question-text` only
8. **Dismiss via × on badge, not click-pill-again.** Reuses the `.badge-delete` pattern from tag badges — familiar affordance, no teaching needed
9. **`more…` not `...more`.** Real ellipsis character (U+2026) after the word, not ASCII dots before it
10. **Hover zone extends above quote text.** First attempt had `top: 0; height: 1.6em` — mouse left the zone before reaching the pill (1rem gap). Fix: extend zone upward to `top: calc(-1.1rem - 1px - 4px)` covering the pill position. Pill at `z-index: 2` stays clickable on top of zone at `z-index: 1`
11. **Pill hover keeps it alive.** Belt-and-suspenders: `onMouseEnter`/`onMouseLeave` on the pill itself set `pillVisibleFor` immediately (no 300ms delay) so hovering the pill keeps it visible
12. **Pill hidden when question expanded.** First attempt kept the pill visible with an `.active` class — clashed visually with the moderator question row above. Fix: remove pill from DOM entirely when `isQuestionOpen` is true; dismiss × on the badge handles closing
