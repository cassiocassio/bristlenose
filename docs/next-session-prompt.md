# Next Session Prompt — Serve Branch

Copy-paste this into a new Claude session in the `bristlenose_branch serve` worktree.

---

We're on the `serve` branch (worktree: `bristlenose_branch serve`).

## Context

Rounds 1–2 of the React component library are done. 5 primitives, 47 Vitest tests, CSS architecture aligned to React component boundaries.

- **Round 1**: Badge, PersonBadge, TimecodeLink — 3 render-only components. CSS rename `.bn-person-id` → `.bn-person-badge`. Frontend tooling: Vitest + React Testing Library, ESLint, TypeScript.
- **Round 2**: EditableText, Toggle — 2 interactive components. CSS refactoring: created `atoms/toggle.css` (star/hide/toolbar toggle) and `molecules/editable-text.css` (editing/edited states). EditableText has two trigger modes: `"external"` (pencil-controlled) and `"click"` (click-to-edit). Toggle is a controlled on/off button.

Serve-mode mount point injection also done — `_mount_dev_report()` injects React mount points + Vite HMR scripts.

See `docs/CHANGELOG-serve.md` for full entries. See `docs/design-react-component-library.md` for the overall plan and CSS ↔ React alignment table.

## What to do next

**Choose one of these based on what's most useful right now:**

### Option A: Quotes API endpoint

The sessions API (`/api/projects/{id}/sessions`) already exists. The next data API needed for the quote card island would be `/api/projects/{id}/quotes` — quotes grouped by section and theme, with sentiment badges, timecodes, speaker info, and star/hide state. This would be Milestone 2's data layer (equivalent to what sessions API was for Milestone 1).

Key files: `bristlenose/server/routes/sessions.py` (pattern to follow), `bristlenose/server/models.py` (Quote, Cluster, Theme tables already exist), `bristlenose/server/importer.py` (already imports quotes).

### Option B: Round 3 planning (TagInput + Sparkline)

Plan the next round of primitives. TagInput is the tagging interaction — autocomplete, codebook groups, badge creation/deletion. Sparkline is the per-session sentiment mini-bar chart used in the sessions table. Together with Round 2 components they unlock the full quote card.

This needs:
1. Read `docs/design-react-component-library.md` (Round 3 section)
2. Read existing JS modules: `tags.js`, `badge-utils.js` in `bristlenose/theme/js/`
3. Read `molecules/tag-input.css`, `templates/report.css` (sparkline section)
4. Design the component API (props, state, events)

### Option C: QuoteCard island composition

Compose the first interactive island from existing primitives: a QuoteCard that uses EditableText (quote text), Toggle (star/hide), Badge (sentiment), TimecodeLink, and PersonBadge (speaker). This would be the first visible React island on the Quotes tab — the core researcher interaction surface.

Key files: `bristlenose/theme/js/editing.js`, `starred.js`, `hidden.js` (vanilla JS to replicate), `organisms/blockquote.css` (CSS to match), `frontend/src/islands/SessionsTable.tsx` (island pattern to follow).

---

**Automated checks to run first:**
```bash
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/python -m pytest tests/ -x -q
.venv/bin/ruff check .
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```
