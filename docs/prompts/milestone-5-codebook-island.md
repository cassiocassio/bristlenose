# Next session: Milestone 5 — Codebook as React island

## Context

I'm on the `serve` branch in `/Users/cassio/Code/bristlenose_branch serve`. The React migration has reached a satisfying rhythm:

- 14 primitives built across 4 rounds (136 Vitest tests, 12 component files)
- 4 React islands shipped: SessionsTable, QuoteSections/QuoteThemes (via QuoteCard), Dashboard
- 7 API endpoints with 180+ tests (sessions, quotes, dashboard, dev, health)
- Milestones 0–4 complete (see `docs/design-serve-migration.md`)
- 1235 Python tests + 136 Vitest tests all passing

The component library is paying off — the Dashboard island was built entirely from existing primitives with zero new component work. Milestone 5 is "Codebook" — the most interactive remaining surface after quotes.

## Pre-planning audit complete

Before this session, we audited every vanilla JS codebook UI element against the React primitives and made 10 design decisions. **Read `docs/design-codebook-island.md` before planning.** It contains:

- Decision log (all 10 decisions with rationale)
- CSS cleanup list (7 changes to codebook-panel.css)
- Two new primitives to build (MicroBar, ConfirmDialog)
- Interactive audit page at `docs/mockups/codebook-audit.html`

## Key docs to read first

1. **`docs/design-codebook-island.md`** — design decisions (READ THIS FIRST)
2. **`docs/design-serve-migration.md`** — migration roadmap (milestones 0–4 done)
3. **`docs/design-react-component-library.md`** — primitive dictionary, coverage matrix
4. **`docs/CHANGELOG-serve.md`** — development log with architectural decisions
5. **`CLAUDE.md`** — project conventions, test commands, design doc index

## What the Codebook does

Study `bristlenose/theme/js/codebook.js` (981 lines) and the Codebook tab in the report. Key concepts:

- **Groups** — named collections of tags (e.g. "Friction", "Delight"). Each has a title, optional subtitle, and a colour from a pentadic OKLCH palette (5 sets: ux, emo, task, trust, opp)
- **Tags** — individual labels within groups. Draggable between groups. Can be merged, renamed, deleted
- **AI tag visibility toggle** — show/hide AI-generated tags vs user-created tags
- **Inline editing** — group titles and subtitles are editable in place
- **Micro bars** — horizontal frequency bars showing quote count per tag
- **Cross-window sync** — in static report, codebook changes propagate via localStorage. In serve mode, the API is the source of truth

## What to build

### Two new primitives

**MicroBar** (`frontend/src/components/MicroBar.tsx`):
- Horizontal proportional bar, value 0–1
- `track` prop: `false` (codebook, bare bar) or `true` (analysis, bar inside grey track)
- `colour` prop: CSS var string
- Replaces `.tag-micro-bar` (codebook) and `.conc-bar-track`/`.conc-bar-fill` (analysis Metric)
- Existing CSS: `codebook-panel.css` for trackless, `analysis.css` for tracked

**ConfirmDialog** (`frontend/src/components/ConfirmDialog.tsx`):
- Small contextual card positioned near the triggering element (NOT centred overlay)
- Enter = confirm, Escape = cancel
- Optional group colour tint
- Props: `title`, `body` (ReactNode), `confirmLabel`, `variant` ("danger" | "primary"), `onConfirm`, `onCancel`
- Replaces `showConfirmModal()` from vanilla `modal.js` for React consumers

### API endpoint

`GET /api/projects/{id}/codebook` — returns groups with their tags, colours, stats:

```json
{
  "groups": [
    {
      "id": "g1",
      "name": "Friction",
      "subtitle": "Pain points and blockers",
      "colourSet": "emo",
      "order": 0,
      "tags": [
        { "name": "confusion", "count": 12, "colourIndex": 0 },
        { "name": "frustration", "count": 8, "colourIndex": 1 }
      ],
      "totalQuotes": 20
    }
  ],
  "ungrouped": [
    { "name": "misc", "count": 3 }
  ],
  "aiTagsVisible": true,
  "allTagNames": ["confusion", "frustration", "misc", ...]
}
```

Mutation endpoints (PATCH/POST/DELETE) for:
- Create/rename/delete group
- Move tag between groups
- Merge tags
- Add/delete tag
- Toggle AI tag visibility

### CodebookPanel island

`frontend/src/islands/CodebookPanel.tsx` — composition rendering the full codebook grid:

- CSS columns masonry layout (reuse `.codebook-grid`)
- Group columns with EditableText titles/subtitles
- Tag rows with Badge + MicroBar + drag handle
- Native HTML5 drag-and-drop (3 gestures: move to group, merge tags, create group from drag)
- ConfirmDialog for destructive actions (delete tag, delete group, merge)
- TagInput for adding new tags (no autocomplete, duplicate guard only)
- Toggle for AI tag visibility
- "+ New group" placeholder

### Mount point

- `<!-- bn-codebook -->` / `<!-- /bn-codebook -->` markers in `render_html.py`
- Regex swap in `app.py`
- `#bn-codebook-root` in `main.tsx`
- Renderer overlay CSS: turn `#bn-codebook-root` green

### CSS cleanup

Apply the 7 CSS changes listed in `docs/design-codebook-island.md`:
- Tokenise hardcoded spacing values
- Fix merge-target dark mode colour
- Fix placeholder border
- Add `.codebook-group .tag-input` font-size override
- Remove retired `.group-title-input` / `.group-subtitle-input` rules

## Design decisions summary

| # | Decision | Choice |
|---|----------|--------|
| 1 | Badge data attrs | Skip — not needed in serve mode |
| 2 | Editing | EditableText (contentEditable), `trigger="click"` |
| 3 | TagInput | No autocomplete — duplicate guard only |
| 4 | Micro bar | New MicroBar primitive, reuse in analysis |
| 5 | 6px spacing | Round to `var(--bn-space-sm)` (8px) |
| 6 | Merge target colour | `color-mix(in srgb, var(--bn-colour-accent) 6%, transparent)` |
| 7 | Placeholder border | 1px (from 1.5px) |
| 8 | Modal | React ConfirmDialog — contextual, near element, not centred overlay |
| 9 | Drag and drop | Native HTML5 drag API, `useRef` for drag state (not useState) |
| 10 | Interactive from start | Full CRUD — codebook needs mutations to be useful |

## Test commands

```bash
# Python tests (full suite)
.venv/bin/python -m pytest tests/ -x -q

# Frontend tests (Vitest)
cd frontend && npm test

# Lint
.venv/bin/ruff check bristlenose/ tests/

# TypeScript check
cd frontend && npx tsc --noEmit

# Serve with dev mode
bristlenose serve trial-runs/project-ikea --dev
```

## Commit style

Follow existing patterns in `git log --oneline`. Lowercase imperative, concise subject, body explains "why". Always include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`.
