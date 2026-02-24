# Quote Editing Redesign

_Design document — Feb 2026, iteration 3_

---

## Problem statement

Long interview quotes are excellent for analysis but poorly suited for stakeholder handoff. Researchers routinely need to:

1. **Fix transcription errors** — typos, misheard words, garbled punctuation
2. **Add bracketed context** — `[referring to the homepage]`, `[laughs]`
3. **Trim quotes for presentations** — a 3-sentence quote becomes the 1 sentence that matters

The third operation is by far the most common. When researchers prepare quotes for a Miro board or slide deck, they are aiming for the _minimum text that makes the point_. Long quotes cause stakeholder brain-melt — they stop reading, skim past, or misinterpret the emphasis.

### What's wrong with the current flow

| Problem | Impact |
|---------|--------|
| **Pencil icon is an extra click** | Adds friction to a high-frequency action |
| **Select-all on focus** | A single accidental keystroke destroys the entire quote — researchers want surgical edits, not replacement |
| **No trimming affordance** | To shorten a quote, users must manually select and delete text from each end — fiddly, slow, error-prone |

---

## Design overview

A single unified mode activated by clicking on quote text. Text editing and crop trimming are **simultaneous capabilities** — no separate "crop mode" toggle, no mode switching. The user can freely alternate between typing and dragging crop handles before committing.

---

## Behaviour specification

### 1. Idle state

Quote card looks completely normal. No handles, no yellow background, no pencil icon. Clean. Nothing interactive is visible until the user clicks.

**Rationale:** Every idle-state affordance (pencil icons, dotted borders, hover outlines) was removed to reduce visual noise. The report is primarily a reading surface. Edit discoverability comes from the `text` cursor on hover and from `…` ellipsis on previously-cropped quotes.

### 2. Click → enter edit mode

A single click on the quote text enters edit mode. All of the following happen simultaneously:

| What | Detail |
|------|--------|
| **Yellow background** | Appears immediately on the entire quote text (`--bn-colour-editing-bg`). This is the first visual signal that the quote is now editable. |
| **Gold bracket handles** | `[` and `]` appear at the start and end of text. They are **hidden for 250ms**, then fade in over 150ms (`bracket-delayed` → `bracket-visible` CSS class swap). The delay lets the yellow background register first, establishing context before the interactive handles arrive. |
| **Blinking caret** | The system text cursor appears at the click position (not select-all). Uses `caretRangeFromPoint` / `caretPositionFromPoint` to place the caret exactly where the user clicked. |
| **No select-all** | The old `range.selectNodeContents()` behaviour is gone. Clicking places the caret; the user can then type, arrow-key navigate, or select text normally. |

**Rationale (caret-at-position):** Select-all is hostile to surgical editing. If the user clicks mid-sentence to fix a typo, the caret should be right there. Placing the caret at the click position signals "you can type here" without destroying anything.

**Rationale (bracket delay):** Showing brackets simultaneously with the yellow background is visually abrupt. The 250ms gap creates a two-beat sequence: (1) "this is editable" (yellow), then (2) "you can also trim" (brackets appear). Removes the feeling of controls popping in all at once.

### 3. Text editing (contenteditable)

Standard browser contenteditable behaviour. The user can:

- Type to insert text at the caret position
- Delete/backspace to remove characters
- Arrow keys to navigate
- Select text with mouse or keyboard for copy/paste
- Add `[bracketed context]` anywhere

The contenteditable span sits between the two bracket handles. The brackets are separate DOM elements — they are not inside the editable region.

### 4. Crop handles — drag interaction

Each bracket (`[` and `]`) is a drag handle. The interaction:

1. **Hover** a bracket → cursor changes to `col-resize` (horizontal resize)
2. **Pointerdown** on a bracket → the contenteditable text is snapshotted, `suppressBlur` is set (see §7)
3. **Drag past 5px threshold** → transitions from contenteditable to word-span crop mode:
   - Text is split into individual word `<span>` elements
   - Each word gets class `included` (yellow bg) or `excluded` (grey + strikethrough)
   - The bracket being dragged tracks the pointer and snaps to word boundaries
4. **During drag** — the crop boundary updates as the pointer moves:
   - Nearest word is found using **2D distance** (not X-only — see §8)
   - Only re-renders if the boundary actually changed (avoids flicker)
   - Status bar shows "Keeping X of Y words"
5. **Pointerup** — drag ends, the card gains focus so Enter/Escape work

**Rationale (word-level granularity):**
- Character-level is too fine-grained — researchers trim at word boundaries
- Sentence-level is too coarse — many quotes are one sentence
- Word-level matches the mental model: "cut the first few words and the last few words"

**Rationale (5px minimum drag):** Prevents accidental crops. A click-and-release on a bracket (without moving 5px) is treated as a no-op — the user stays in edit mode.

### 5. Included vs excluded text — visual treatment

| Region | Background | Text colour | Decoration | Purpose |
|--------|------------|-------------|------------|---------|
| **Included** (between handles) | Yellow (`--bn-colour-editing-bg`) | Normal | None | "This text will be kept" |
| **Excluded** (outside handles) | None (transparent) | Grey (`--bn-colour-muted`) | Strikethrough | "This text will be removed" |

The included words are wrapped in a `<span class="crop-included-region">` with a continuous yellow background. Individual word spans inside it do not carry their own background — this prevents white gaps between words where bare text-node spaces have no background.

**Rationale (grey + strikethrough, not opacity):** Opacity alone fails for colourblind users and in dark mode. Grey + strikethrough is a double signal that works across all visual contexts. The two states (yellow vs grey+strikethrough) are mutually exclusive — a word is never both.

### 6. Alternating between editing and cropping

After dragging a handle, the quote is in "crop mode" (word spans, no contenteditable). The user can **click on any included word** to switch back to contenteditable:

1. Click on yellow included text → `reenterTextEdit()` is called
2. The view switches to the **hybrid layout**: grey excluded word spans + `[` + contenteditable span (with included text) + `]` + grey excluded word spans
3. The caret appears at the click position inside the contenteditable
4. The user can type freely, then drag a handle again to re-enter crop mode

This cycle can repeat any number of times before committing. When switching from text-edit to crop, the contenteditable text is snapshotted and spliced back into the words array (preserving any edits the user made).

**Rationale:** In the original design, entering crop mode was a one-way door — once you dragged a handle, you couldn't fix a typo in the middle of the text. This was the "stuck in drag mode" bug. The hybrid view solves it: free alternation between typing and trimming, with crop boundaries preserved across transitions.

### 7. The suppressBlur problem

**The bug:** Clicking a bracket handle causes the contenteditable span to lose focus (blur). The blur handler treats blur as "commit" (same as clicking outside). So clicking a bracket would commit the edit before the drag could start.

**The fix:** `suppressBlur` flag, set synchronously in the bracket's `pointerdown` handler. The blur handler defers its commit check by 150ms (`setTimeout`). By the time the deferred check runs, `suppressBlur` is true, so the commit is skipped.

The timing chain:
1. User clicks bracket
2. Browser fires `pointerdown` on bracket → sets `suppressBlur = true`, clears any pending `blurTimeout`
3. Browser fires `blur` on contenteditable → `handleEditBlur()` sets a 150ms timeout
4. 150ms later: timeout fires, checks `suppressBlur` → true → skips commit
5. Drag proceeds normally

**Why 150ms?** Must be long enough for the synchronous pointerdown to fire before the deferred blur check. 150ms is conservative. The browser's event dispatch is synchronous within a single user gesture, so the pointerdown always fires before the blur timeout callback — but 150ms gives margin for edge cases.

### 8. Hit detection — 2D distance with boundary snap

During drag, the nearest word to the pointer is found using 2D Euclidean distance (not X-only). For each word span:

```
cx = clamp(pointer.x, rect.left, rect.right)
cy = clamp(pointer.y, rect.top, rect.bottom)
distance = sqrt((pointer.x - cx)² + (pointer.y - cy)²)
```

**Why not X-only?** On a multi-line quote, a word on line 3 can have a closer X than the correct word on line 1 near the pointer. The handles would jump across lines unpredictably. 2D distance ensures the pointer finds the word that's actually nearest in both dimensions.

**Boundary snap:** If the pointer moves outside the text area entirely:
- **Above all text** (`pointer.y < firstWord.top`) → snap to word 0 (start of quote)
- **Below all text** (`pointer.y > lastWord.bottom`) → snap to last word (end of quote)

This means dragging `]` downward past the quote = "include everything to the end." Dragging `[` upward past the quote = "go back to the start." Natural gestures that match user intent — overshooting should snap to the boundary, not pick a random word.

### 9. Document-level event listeners for drag

Drag listeners (`pointermove`, `pointerup`) are attached to `document`, not to the bracket element. This is critical because `renderCropWords()` destroys and recreates the DOM on every boundary change (`textSpan.innerHTML = html`). If listeners were on the bracket element, they would be orphaned after the first re-render and the drag would freeze.

The bracket element is only used for the initial `pointerdown`. Everything after that is document-level.

### 10. Commit (Enter, blur, click-outside)

Three ways to commit:

| Trigger | Mechanism |
|---------|-----------|
| **Enter** | `keydown` handler on contenteditable (or card in crop mode) calls `commitEdit()` |
| **Blur** | `handleEditBlur()` deferred check — commits if `isEditing && !isCropping`. In crop mode, blur doesn't commit (the card is focused, not the contenteditable) |
| **Click outside** | Document-level `pointerdown` checks `activeCard.contains(e.target)` — if outside, commits the active card |

On commit:
1. All visual treatment vanishes (yellow, brackets, grey, strikethrough)
2. The kept text is rendered as plain text
3. If the text was cropped from the start: a leading `…` (real ellipsis, U+2026) is rendered flush against the first word (no space)
4. If the text was cropped from the end: a trailing `…` is rendered flush against the last word (no space)
5. The undo button becomes visible on card hover
6. Status bar briefly shows "Saved. Trimmed to N words."

**Rationale (real ellipsis, no space):** Three dots (`...`) look like a typo; the ellipsis character (`…`) is correct typography. No space between the ellipsis and the adjacent word because the ellipsis replaces removed text — it's a continuation mark, not a separate element. `…the user said` reads as "something came before this." `… the user said` reads as a pause, which is wrong.

### 11. Cancel (Escape)

Escape reverts everything — text edits AND crop — to the pre-click state. All visual treatment vanishes. The quote returns to its idle appearance.

### 12. Tab behaviour

Tab does its normal browser thing: moves focus to the next focusable element. This triggers blur on the contenteditable, which is treated as commit (same as Enter). We do NOT override Tab with custom semantics.

**Rationale:** Tab is a navigation key. Overriding it breaks keyboard users' expectations. The blur-as-commit behaviour is consistent with how contenteditable works everywhere (Google Docs, Notion, etc.).

### 13. Undo

An undo button (`↩`) appears at the former pencil icon position (`right: 3.35rem`). Only visible when:
- The quote has been edited or cropped (not in its original state)
- The user is hovering over the quote card (fades in, like the hide button)
- The quote is NOT currently in edit mode

Click → reverts to `state.originalText`. Clears all edits and crops in one action. No partial undo — it's all or nothing.

**Rationale (all-or-nothing):** Partial undo (undo just the crop, keep the text edits) adds complexity for minimal benefit. The common case is "I cropped too aggressively, give me the original back." The undo button does exactly that.

### 14. Ellipsis as persistent crop indicator

After a crop is committed, the `…` ellipsis remains visible in the idle state. This serves two purposes:
1. **Visual signal** — "this quote was trimmed, you're not seeing the full text"
2. **Discoverability prompt** — the ellipsis implicitly says "there's an undo button if you hover"

Even when the undo button is not visible (user not hovering), the ellipsis provides a persistent "this was trimmed" indicator.

### 15. Only one quote in edit mode at a time

Clicking a second quote while one is already being edited commits the first. `activeCard` tracks which quote is currently in edit mode.

---

## Rendering modes

The mockup has three rendering states for the quote text area. Understanding these is essential for debugging:

### Mode 1: Idle

```
<span class="quote-text">the plain text of the quote</span>
```

No interactivity. Just text.

### Mode 2: Hybrid / editable (the default edit mode)

```
<span class="quote-text">
  <span class="crop-word excluded" data-i="0">excluded</span>
  <span class="crop-word excluded" data-i="1">words</span>
  <span class="crop-handle bracket-visible" data-handle="start">[</span>
  <span class="crop-editable" contenteditable="true">the editable included text</span>
  <span class="crop-handle bracket-visible" data-handle="end">]</span>
  <span class="crop-word excluded" data-i="8">trailing</span>
  <span class="crop-word excluded" data-i="9">words</span>
</span>
```

Used when: first entering edit mode, and when clicking included text after a crop drag. The contenteditable span contains the included text as a single editable string. Excluded words (if any) are rendered as grey spans flanking the brackets. If no crop has happened yet (`cropStart=0, cropEnd=words.length`), the excluded spans are absent.

### Mode 3: Crop / word-span

```
<span class="quote-text">
  <span class="crop-word excluded" data-i="0">excluded</span>
  <span class="crop-word excluded" data-i="1">words</span>
  <span class="crop-handle" data-handle="start">[</span>
  <span class="crop-included-region">
    <span class="crop-word included" data-i="2">included</span>
    <span class="crop-word included" data-i="3">text</span>
  </span>
  <span class="crop-handle" data-handle="end">]</span>
  <span class="crop-word excluded" data-i="4">trailing</span>
</span>
```

Used when: a handle is being dragged. Each word is a separate span for hit-detection. The `crop-included-region` wrapper provides a continuous yellow background across included words and their inter-word spaces (prevents white gaps). No contenteditable — the text is read-only during drag.

### Mode transitions

```
idle ──click──→ hybrid (mode 2)
                 │
                 ├──drag handle──→ crop (mode 3) ──click included word──→ hybrid (mode 2)
                 │                  │                                       │
                 │                  └──drag handle again──→ crop (mode 3)──┘
                 │
                 ├──Enter/blur──→ idle (committed)
                 └──Escape──→ idle (reverted)

crop (mode 3) ──Enter──→ idle (committed)
               ──Escape──→ idle (reverted)
```

The user can cycle between modes 2 and 3 any number of times. Crop boundaries are preserved across transitions. Text edits made in mode 2 are snapshotted and spliced into the word array when transitioning to mode 3.

---

## CSS classes reference

| Class | Element | Purpose |
|-------|---------|---------|
| `.crop-handle` | `<span>` | The `[` or `]` bracket. `cursor: col-resize`, gold colour, `user-select: none` |
| `.bracket-delayed` | `.crop-handle` | Initial state: hidden (`opacity: 0; visibility: hidden`). Removed after 250ms |
| `.bracket-visible` | `.crop-handle` | Fade-in state: `opacity: 1` with 150ms animation |
| `.crop-editable` | `<span contenteditable>` | The editable text region. Yellow background, no outline |
| `.crop-word` | `<span>` | Individual word during crop mode. Has `data-i` attribute (word index) |
| `.crop-word.included` | `.crop-word` | Word inside the crop range. No own background (inherits from `.crop-included-region`) |
| `.crop-word.excluded` | `.crop-word` | Word outside the crop range. Grey text, strikethrough, no background |
| `.crop-included-region` | `<span>` | Wrapper around included words. Continuous yellow background, 2px border-radius |
| `.crop-ellipsis` | `<span>` | The `…` character after commit. Grey, `user-select: none` |
| `.undo-btn` | `<button>` | The `↩` button. Hidden by default, `.visible` class shown on hover |
| `.editing` | `blockquote` | Added to the card when in edit mode. Used for scoping CSS |

---

## Design tokens used

| Token | Value (light) | Purpose |
|-------|---------------|---------|
| `--bn-colour-editing-bg` | `#fffbe6` | Yellow background for editable/included text |
| `--bn-colour-editing-border` | `#e5e0c0` | Not currently used by crop (reserved) |
| `--bn-colour-muted` | `#6b7280` | Grey for excluded text, ellipsis, status bar |
| `--bn-crop-handle-colour` | `#c9a63c` | Gold bracket colour |
| `--bn-crop-handle-hover` | `#a68529` | Darker gold on bracket hover |
| `--bn-colour-accent` | `#2563eb` | Accent colour for undo hover |

All tokens have `light-dark()` variants for dark mode.

---

## Bugs fixed during development (and their causes)

These are documented here because the same patterns will recur in the production React implementation.

### 1. Bracket drag didn't work at all (orphaned listeners)

**Cause:** `pointermove`/`pointerup` listeners were attached to the bracket element. `renderCropWords()` does `textSpan.innerHTML = html`, which destroys the bracket DOM node. Listeners on a detached node are dead.

**Fix:** Attach `pointermove`/`pointerup` to `document`, not the bracket element.

### 2. Second handle drag committed instead of starting drag

**Cause:** After dragging one handle, `renderCropWords()` creates new bracket elements. The new brackets had no `pointerdown` listener (only `renderCropWords` attached them; the in-place update function didn't). Clicking an unhandled bracket fell through to a parent handler that committed.

**Fix:** Always call `attachHandleDrag()` on freshly created bracket elements after any DOM update.

### 3. Handles jumped across lines during drag (X-only hit detection)

**Cause:** Hit detection measured `Math.abs(pointer.x - word.x)` only. On multi-line text, a word on a distant line could have a closer X than the correct word on the pointer's line.

**Fix:** 2D Euclidean distance with clamped coordinates (see §8).

### 4. White gaps between yellow-highlighted words

**Cause:** Yellow background was on individual `.crop-word.included` spans. The spaces between words (bare text nodes) had no background, creating visible white gaps.

**Fix:** Wrap all included words in `<span class="crop-included-region">` with the yellow background. Individual words no longer carry their own background.

### 5. Clicking a bracket blurred contenteditable (premature commit)

**Cause:** Browser fires blur on the contenteditable when another element receives focus. The blur handler treated blur as "commit."

**Fix:** `suppressBlur` flag pattern (see §7).

### 6. Stuck in crop mode (couldn't edit text after dragging)

**Cause:** After dragging a handle, the view switched to word spans (no contenteditable). There was no way back to text editing.

**Fix:** `reenterTextEdit()` — clicking on included text in crop mode switches back to the hybrid editable view, preserving crop boundaries.

### 7. Dragging outside quote picked random word

**Cause:** 2D distance found the nearest word even when the pointer was far above/below the text.

**Fix:** Boundary snap — pointer above text → word 0; pointer below text → last word (see §8).

### 8. Three dots instead of ellipsis, with spurious space

**Cause:** Commit rendered `'... '` and `' ...'` (three dots with a space).

**Fix:** Render `'\u2026'` (real ellipsis character) flush against the adjacent word, no space.

---

## Timecode identity

### The constraint

Quote DOM IDs are `q-{participant_id}-{int(start_timecode)}` (e.g. `q-p1-123`). This ID is the lookup key for localStorage edits, server lookups, transcript deep-links, CSV export, and video seek.

### Design decision

**Cropping does NOT change the quote's `start_timecode` or DOM ID.** The crop only changes the displayed text. The original timecode remains as the identity anchor.

The displayed timecode label (`[0:02:03]`) stays at the original position even after cropping. A slight inaccuracy — the cropped text may start a few seconds later — but the full quote _did_ start there. The timecode is a navigation aid, not a precision instrument.

### Future: segment_index

The `segment_index` field (added v0.11) is designed to eventually replace timecode-based identity. Immutable ordinal position in the transcript. Migration tracked separately.

---

## Data model

### Option 1: Store trimmed text only ★ chosen for MVP

Cropping produces a new `edited_text` value. The existing `QuoteEdit.edited_text` stores the result, same as a text edit. The original `Quote.text` stays in the database.

- **Pros**: Zero schema changes, zero API changes, zero migration
- **Cons**: Cannot distinguish crop from hand-edit; cannot re-expand a crop

### Option 2: Store crop indices (deferred)

Add `crop_start_word` and `crop_end_word` to `QuoteEdit`. The UI can reconstruct full text with dimmed portions, allow re-expanding.

**Decision**: Start with Option 1. The undo button provides "get back the original." Migrate to Option 2 if user testing shows re-expansion is needed.

---

## Open questions

1. ~~**Short quotes**: Hide crop handles on quotes < 5 words?~~ **Resolved**: No threshold. Brackets appear on all quotes regardless of length. Keeps the interaction consistent.

2. ~~**Entrance animation**: Slide in or pop in?~~ **Resolved**: Brackets are hidden for 250ms after click, then fade in over 150ms. Yellow background appears immediately. Two-beat sequence: "editable" then "trimmable."

3. ~~**Re-entering after crop**: Can user expand back?~~ **Resolved**: User can drag handles back outward to their original positions before committing. After commit, undo is the only way to restore. For MVP this is acceptable.

4. **Touch devices**: Drag brackets work via pointer events, which abstract mouse/touch/pen. Risk of conflict with scroll gestures on mobile. Needs testing. **TODO.**

5. **More visual bracket/handle design**: Current `[ ]` brackets are functional but minimal. Consider more visual handles inspired by video editing software crop handles. **TODO.**

6. **Export impact**: CSV exports the edited/trimmed text. The original stays in the database. Should the original be a separate CSV column?

7. **RTL text**: Handle directions must use logical properties (inline-start/inline-end), not physical (left/right).

---

## Accessibility

- Crop handles: `tabindex="0"`, `role="slider"`, `aria-valuemin/max/now`, `aria-label="Trim start/end of quote"`
- Keyboard: Arrow keys move crop boundary word-by-word (following `DualThresholdSlider.tsx` pattern)
- Screen reader: announce crop state — "Showing words 3 through 12 of 15"
- Excluded text uses strikethrough + grey colour (not opacity alone)
- Undo button: `aria-label="Revert to original quote"`, in tab order

---

## Critique

### What could go wrong

1. **Handle vs. text-selection conflict**: Near the edges, selecting text for copy might accidentally initiate a drag on a nearby bracket. Mitigated by: brackets being _outside_ the contenteditable region; 5px minimum drag distance.

2. **Discoverability**: Nothing is visible until the user clicks — they must click the quote text to discover that editing and crop handles exist. Mitigated by: (a) cursor changes to `text` on hover (signals clickability), (b) the `…` ellipsis on previously-cropped quotes signals the feature exists, (c) onboarding documentation.

3. **Performance**: Wrapping every word in a `<span>` for all quotes on the page is expensive. Mitigated by lazy word-wrapping — only wrap when the quote enters crop mode (drag), collapse back on commit. Only one quote is in edit mode at a time.

4. **State complexity**: QuoteCard already has `isEditingText`, `isStarred`, `isHidden`, plus tag state. Adding `cropStart`, `cropEnd` within the single edit mode is manageable — these are just two numbers that are active only while `isEditingText` is true.

5. **"Where did my text go?"**: After committing a crop, the excluded text is gone (stored as trimmed `edited_text`). The `…` ellipsis and undo button are the safety nets. The undo button is only visible on hover — but the ellipsis is always visible, providing a persistent "this was trimmed" signal.

6. **Re-entering a cropped quote**: The handles wrap the trimmed text. The user can crop further but cannot expand. This is fine for MVP (undo restores the full original), but may frustrate users who just want to include one more word. Option 2 data model would solve this later.

### Alternatives not pursued

| Approach | Why not |
|----------|---------|
| **Hover-reveal handles** (iteration 1) | Adds visual noise on every hover; conflates "browsing" with "ready to edit" |
| **Separate crop mode** | Mode switching is confusing; two modes where one suffices |
| **Highlight-to-trim** (select → "Trim to selection") | Requires precise selection; extra step; hard on touch |
| **Slider below quote** | Takes vertical space; disconnects control from content |
| **Opacity for excluded text** | Fails for colourblind users and in dark mode; grey + strikethrough is a stronger double signal |
| **Three dots `...` for ellipsis** | Typographically incorrect; reads as a typo. Real ellipsis `…` is correct |
| **Space between ellipsis and word** | `… the user said` reads as a pause. `…the user said` reads as a continuation, which is the correct semantics |

---

## Files affected (future production implementation)

| File | Change |
|------|--------|
| `frontend/src/components/EditableText.tsx` | Remove select-all; add cursor-at-position via `caretRangeFromPoint` |
| `frontend/src/components/CropHandles.tsx` | **New**. Word wrapping, bracket rendering, pointer-capture drag, `onCrop(start, end)` |
| `frontend/src/islands/QuoteCard.tsx` | Remove pencil button; wrap text in `<CropHandles>`; add undo button; change trigger to `"click"` |
| `bristlenose/theme/molecules/editable-text.css` | Add `.crop-handle`, `.crop-excluded`, `.crop-word`, `.crop-included-region` styles |
| `bristlenose/theme/atoms/button.css` | Remove `.edit-pencil`; add `.undo-btn` |

---

## Related documents

- [Interactive mockup](mockups/quote-editing.html) — unified single-mode interaction prototype (self-contained HTML with inline CSS + JS)
- [HTML report design](design-html-report.md) — quote card layout, editing, persistence
- [React component library](design-react-component-library.md) — `EditableText` primitive
- [Pipeline resilience](design-pipeline-resilience.md) — quote identity, `segment_index`
