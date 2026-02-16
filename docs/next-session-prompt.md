# Next Session Prompt — Serve Branch

Copy-paste this into a new Claude session in the `bristlenose_branch serve` worktree.

---

We're on the `serve` branch (worktree: `bristlenose_branch serve`).

## Context

Round 1 of the React component library is done: Badge, PersonBadge, TimecodeLink — 3 components, 19 Vitest tests, CSS rename `.bn-person-id` → `.bn-person-badge`, SessionsTable refactored to use PersonBadge. Frontend tooling in place: Vitest + React Testing Library, ESLint flat config, `npm test` / `npm run lint` / `npm run typecheck`.

See `docs/CHANGELOG-serve.md` for the full Round 1 entry. See `docs/design-react-component-library.md` for the overall plan and CSS ↔ React alignment table.

## What to do next

**Choose one of these based on what's most useful right now:**

### Option A: Round 2 planning (EditableText + Toggle)

Plan the next round of primitives. EditableText is the most reused within a single surface (6+ instances in quote cards alone — quote text, section headings, theme headings, theme descriptions, participant names, roles). Toggle covers star and hide (the two most common researcher actions). Together they unlock a fully interactive quote card minus tagging.

This needs:
1. Read `docs/design-react-component-library.md` (Round 2 section)
2. Read existing JS modules: `editing.js`, `starred.js`, `hidden.js`, `names.js` in `bristlenose/theme/js/`
3. Read `atoms/button.css`, `molecules/quote-actions.css`, `molecules/name-edit.css`, `molecules/hidden-quotes.css`
4. Plan the CSS refactoring needed (extract `atoms/toggle.css`, consolidate editing states)
5. Design the component API (props, state, events)
6. Write a plan doc like the Round 1 plan

### Option B: Quotes API endpoint

The sessions API (`/api/projects/{id}/sessions`) already exists. The next data API needed for the quote card island would be `/api/projects/{id}/quotes` — quotes grouped by section and theme, with sentiment badges, timecodes, speaker info, and star/hide state. This would be Milestone 2's data layer (equivalent to what sessions API was for Milestone 1).

Key files: `bristlenose/server/routes/sessions.py` (pattern to follow), `bristlenose/server/models.py` (Quote, Cluster, Theme tables already exist), `bristlenose/server/importer.py` (already imports quotes).

---

**Automated checks to run first:**
```bash
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/python -m pytest tests/ -x -q
.venv/bin/ruff check .
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```
