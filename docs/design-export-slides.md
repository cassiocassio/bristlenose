# Design: Export Dropdown + Quote Slides

## Context

Two intertwined features:

1. **Per-quote hover copy** — subtle clipboard icon on individual quote cards and signal cards. Claude/GitHub pattern.
2. **Export dropdown** — replaces the single "Copy CSV" button. Two-level menu: scope first (selected/starred/all), then format (CSV/Excel/Slides). CSV folded into the dropdown — no standalone button.
3. **Quote slides** — new `.pptx` format: one centred quote per slide, conventional research formatting.

The researcher's workflow: **curate first, export second.** Star quotes → tag-filter → select a few → export.

---

## Part 0: Per-Quote Hover Copy Icon

### Interaction

- **Hidden by default** — appears on card hover (`opacity: 0` → `1`, `var(--bn-transition-fast)`)
- **Position: bottom-right** of quote card (avoids star/hide/pencil cluster at top-right)
- **Click** → copies plain quote text (no attribution, no `— p03`). Uses `edited_text` when available
- **Feedback**: icon morphs to checkmark for ~1.5s (Claude pattern). **Plus** `announce("Copied to clipboard")` for screen readers (uses existing `announce.ts`)
- **Keyboard**: focusable with Tab, activates on Enter/Space. `:focus-visible` reveals at full opacity
- **Touch** (`@media (hover: none)`): always visible at `opacity: 0.85` (meets 3:1 non-text contrast)
- **Reduced motion** (`prefers-reduced-motion: reduce`): no opacity transition

### Where it appears

- Quote cards on Quotes tab
- Signal cards on Analysis tab

### CSS (using Bristlenose tokens)

```css
.bn-copy-btn {
  position: absolute;
  bottom: var(--bn-space-sm);
  right: var(--bn-space-sm);
  opacity: 0;
  transition: opacity var(--bn-transition-fast);
  /* Ghost button pattern (matches .edit-pencil in atoms/button.css) */
  background: none;
  border: none;
  color: var(--bn-colour-icon-idle);
  cursor: pointer;
  padding: var(--bn-space-sm);
  border-radius: var(--bn-radius-sm);
}
.bn-copy-btn:hover { color: var(--bn-colour-accent); }
.bn-copy-btn:focus-visible {
  opacity: 1;
  outline: 2px solid var(--bn-colour-accent);
}
.quote-card:hover .bn-copy-btn,
.signal-card:hover .bn-copy-btn { opacity: 1; }

@media (hover: none) { .bn-copy-btn { opacity: 0.85; } }
@media (prefers-reduced-motion: reduce) { .bn-copy-btn { transition: none; } }
```

SVG icons inside the button: `aria-hidden="true"`.

### Component sketch

```tsx
function CopyButton({ text, ariaLabel }: { text: string; ariaLabel: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      announce(t("export.copiedAnnounce")); // screen reader
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);
  return (
    <button className="bn-copy-btn" onClick={handleCopy}
            aria-label={ariaLabel} type="button">
      {copied ? <CheckIcon aria-hidden="true" /> : <ClipboardIcon aria-hidden="true" />}
    </button>
  );
}
```

---

## Part 1: Export Dropdown

### Toolbar layout

CSV is folded into the Export dropdown. The toolbar has **4 elements** (same count as today):

```
┌──────────────────────────────────────────────────────────┐
│ Search  │  Tags ▾  │  View ▾  │  Export ▾                │
└──────────────────────────────────────────────────────────┘
```

Export replaces Copy CSV. Same slot, same width budget. No toolbar overflow issue.

### Menu structure (scope first, then format)

```
Export ▾
├── 7 Selected Quotes           ▸    (web: hidden when 0. macOS: greyed)
│   ├── Copy as CSV
│   ├── Save as Excel…
│   └── Save as Slides…
├── 3 Starred Quotes            ▸    (web: hidden when 0. macOS: greyed)
│   ├── Copy as CSV
│   ├── Save as Excel…
│   └── Save as Slides…
└── All 47 Quotes               ▸    (always shown)
    ├── Copy as CSV
    ├── Save as Excel…
    └── Save as Slides…
```

**Shortcut**: when only "All N" is available (no selection, no starred), skip the cascade — show formats directly. No extra click for the common case.

**v2 additions** per scope (when clip extraction ships):
```
    ├── Export Video Clips…
    └── Export Video in Slides…
```

### Dynamic visibility (web vs native)

| Scope | Web dropdown | macOS menu |
|-------|-------------|------------|
| Selected (0) | Hidden | Greyed out (HIG: dim, never hide) |
| Selected (>0) | Shown | Shown |
| Starred (0) | Hidden | Greyed out |
| Starred (>0) | Shown | Shown |
| All N | Always shown | Always shown |

### Cascading submenu — web implementation

**Hover timing** (reuse `useTocOverlay` direction-aware pattern):
- 200ms delay before opening submenu on hover
- 300ms grace period before closing on leave
- Direction-aware: pointer moving rightward toward submenu keeps it open; moving up/down switches immediately

**Touch devices** (`@media (hover: none)`): tap on scope row expands formats inline (accordion-style, not flyout). Cascading submenus are unusable without hover.

**Keyboard** (full WAI-ARIA menu pattern):
- `role="menu"` on dropdown, `role="menuitem"` on items
- `aria-haspopup="menu"` on scope rows, `aria-expanded` tracking submenu state
- Arrow-down/up: move between scope rows (or format items when submenu open)
- Arrow-right: open submenu. Arrow-left: close submenu
- Escape: close submenu first, then parent on second press (submenu's own `stopPropagation` prevents outer `useDropdown` Escape from firing)
- Enter/Space: activate format item
- Roving `tabindex` (`tabindex="0"` on active item, `-1` on others)

### macOS Quotes menu

Replace single "Copy as CSV" with cascading export submenus. All three scopes always present in the menu, greyed when empty (HIG: dim, never hide). Use `.disabled()`, not `if` guards.

**Bridge action**: single `exportQuotes` with `{ scope, format }` payload.

**New BridgeHandler state** (pushed on every change, not just menu open):
- `starredQuoteCount: Int`
- `visibleQuoteCount: Int`
- `selectedQuoteCount` already exists

### ContentView.swift ExportMenuButton

The toolbar `ExportMenuButton` gains the same scope cascade (not just the menu bar).

---

## Part 2: Quote Slides Format

### The slide

Conventional research quote formatting:

```
                    ┌─────────────────────────────┐
                    │                              │
                    │  "I just gave up after the   │
                    │   second day because nothing  │
                    │   made sense to me at all"    │
                    │                               │
                    │          — p03               │
                    │                              │
                    └─────────────────────────────┘
```

- Centre-aligned, locale-aware quotation marks, em dash + participant code only
- Uses `edited_text` when available
- Slide title: section name (`topic_label`)
- Zero visual design — researcher applies their own org template (`Insert > Reuse Slides`)

### Speaker notes

```
Participant: p03
Session: s2
Timecode: 05:23–05:41
Section: Dashboard
Sentiment: frustration (intensity: 3)
Tags: onboarding, drop-off, first-run
Context: When asked about the settings page
```

- **No names by default** — codes only. Opt-in for names
- Omit empty fields
- No original text when anonymised — defeats manual PII removal
- Slide 1 notes: "To apply your org template: Insert > Reuse Slides"

### Font sizing

| Quote length | Font size |
|-------------|-----------|
| ≤30 words | 32pt |
| 31-60 words | 28pt |
| 61+ words | 24pt |

v1: one quote per slide. Multi-quote layouts (2-4 per slide) deferred until grouping UI ships.

### Safety checklist

1. No names in speaker notes by default — codes only, opt-in
2. `safe_filename()` on all generated filenames + `Path.resolve()` containment check
3. Strip control characters (U+0000–U+001F except `\n`, `\t`) before python-pptx — prevents corrupt OOXML
4. Use `text_frame.text` / `run.text` — never construct XML strings manually. python-pptx's lxml backend auto-escapes
5. No original text in notes when anonymised
6. Export endpoints behind existing bearer token middleware — no new auth surface

---

## i18n

### Quotation marks for slides

```python
QUOTE_MARKS = {
    "en": ("\u201c", "\u201d"),   # \u201c...\u201d
    "es": ("\u201c", "\u201d"),   # \u201c...\u201d (modern digital usage; guillemets are RAE but uncommon in slides)
    "fr": ("\u00ab\u00a0", "\u00a0\u00bb"),  # guillemets with NBSP
    "de": ("\u201e", "\u201c"),   # \u201e...\u201c
    "ko": ("\u201c", "\u201d"),   # \u201c...\u201d
}
```

Spanish: curly quotes per i18n review (modern digital usage). Needs human translator confirmation.

### Locale keys — use `_one`/`_other` pattern

All 5 locale files (`common.json`). Reuse existing keys where they exist:

```json
{
  "export": {
    "selectedQuotes_one": "1 Selected Quote",
    "selectedQuotes_other": "{{count}} Selected Quotes",
    "starredQuotes_one": "1 Starred Quote",
    "starredQuotes_other": "{{count}} Starred Quotes",
    "allQuotes_one": "1 Quote",
    "allQuotes_other": "All {{count}} Quotes",
    "copyAsCsv": "Copy as CSV",
    "saveAsExcel": "Save as Excel\u2026",
    "saveAsSlides": "Save as Slides\u2026",
    "exportingSlides": "Exporting slides\u2026",
    "slidesDownloaded": "Slides downloaded",
    "copyQuote": "Copy quote",
    "copiedAnnounce": "Copied to clipboard"
  }
}
```

**"Slides" must be localised**: de: "Folien", fr: "diapositives", es: "diapositivas", ko: "\uc2ac\ub77c\uc774\ub4dc" (from Apple Keynote localisation).

**Avoid duplicates**: reuse `toolbar.csvCopied` for the CSV copied toast. Don't create `export.button` (use existing `buttons.export`).

**Korean**: only `_other` keys needed (no plural forms).

---

## VTT subtitle files — deferred to v2

Standalone VTT without clips confuses researchers. Ships with clip extraction feature, where they naturally accompany their clips.

---

## v2 roadmap

1. Video clip export (FFmpeg stream-copy + burned subtitles) + video in slides (`add_movie()`)
2. VTT files alongside clips (not standalone)
3. Multi-quote slides (2-4 per slide grouped by section)
4. Localised speaker notes labels
5. CJK font sizing heuristic (character-count scaling)

---

## Review findings incorporated

### Security review
- Speaker notes contain names by default = PII leakage when decks emailed. Changed to codes-only default
- `safe_filename()` + `Path.resolve()` containment on all generated filenames
- Strip control characters before python-pptx (corrupt OOXML prevention)
- No original text when anonymised (defeats manual PII removal)

### UX review
- CSV folded into Export dropdown (eliminates duplication + toolbar overflow)
- CopyButton at bottom-right (avoids star/hide cluster)
- Touch accordion fallback for cascading submenu
- Hover timing reuses `useTocOverlay` direction-aware pattern

### macOS review (HIG)
- `.disabled()` not `if` guard (dim, never hide)
- Menu labels include noun ("Export 7 Selected Quotes")
- ContentView ExportMenuButton gains same scope cascade
- Bridge counts pushed on every change, not on menu open

### Accessibility review
- `announce()` on copy for screen readers
- Full WAI-ARIA menu pattern (roles, roving tabindex, keyboard nav)
- Touch opacity 0.85 (meets 3:1 non-text contrast)
- SVG icons: `aria-hidden="true"`
- `prefers-reduced-motion` disables transitions

### i18n review
- `_one`/`_other` plural key convention (matches codebase)
- "Slides" localised per language (Apple Keynote terms)
- Spanish curly quotes (not guillemets)
- Reuse existing `toolbar.csvCopied` and `buttons.export` keys
