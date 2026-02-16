# Serve Migration: Static HTML → React Islands → SPA

## Decision (Feb 2026)

Build a new served version of Bristlenose alongside the existing CLI. The pipeline stays unchanged. A FastAPI server + SQLite database replaces `file://` and `localStorage`. React components replace vanilla JS modules one at a time using the **islands pattern** — the report is always shippable at every step.

### Why now

Every new JS feature added to the static report (vanilla JS, IIFEs, implicit globals) is more frontend code that eventually needs migrating. The pipeline output (intermediate JSON, `people.yaml`, transcripts) is already well-structured and ready for a new frontend to consume. Starting the React app now means new features can be built in the target architecture directly.

### Why not start over

The pipeline, data models (`models.py`), LLM orchestration, analysis module, and theme CSS are production-quality code. Only the rendering/frontend layer needs replacing. This is a new view layer on an existing backend — not a rewrite.

### Why not the old plan (Phase A→F in-place migration)

The original "100 pushes" strategy (`docs/private/frontend-evolution.md`) called for Jinja2 templates as an intermediate step before React. That Jinja2 step (~20 pushes) is work that gets replaced by React. Going directly to React islands inside the existing HTML report skips the Jinja2 intermediate without sacrificing the incremental delivery model.

## Architecture

```
Pipeline (unchanged)
    │
    ├── writes intermediate JSON to .bristlenose/intermediate/
    ├── writes transcripts to transcripts-raw/
    ├── writes people.yaml
    └── renders static HTML report (render_html.py — continues to work)

FastAPI server (new)
    │
    ├── serves the existing HTML report over HTTP (replaces file://)
    ├── /api/* endpoints return JSON (replaces localStorage)
    ├── reads/writes SQLite database
    └── serves React bundle (islands mount into existing HTML)

SQLite database (new)
    │
    ├── projects, quotes, clusters, themes, participants
    ├── user state: tags, edits, hidden quotes, starred quotes
    └── eventually: swap to Postgres for multi-tenant SaaS
```

## Tech stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Web framework | FastAPI | Async-native (matches pipeline), Pydantic-native (models work directly) |
| ASGI server | Uvicorn | Standard for FastAPI |
| Frontend | React + TypeScript | Industry standard, hiring pool, TS matches strict-mypy philosophy |
| Build tool | Vite | Instant hot-reload, standard for React |
| Database | SQLite via SQLAlchemy 2.0 | Local-first. Swap to Postgres = connection string change |
| Migrations | `create_all()` for now | Add Alembic when schema stabilises |

All choices are cross-platform. Electron desktop app is possible later. Node.js is dev-only — end users never need it.

## Migration roadmap

| Milestone | What | Approach |
|-----------|------|----------|
| **0** | Serve existing report + React tooling ready | `<div id="bn-react-root">` + HelloIsland proof of concept |
| **1** | Sessions table as React island | React component replaces `<table>` in existing HTML |
| **2** | Component library + quote cards | Build 14 reusable primitives, compose into QuoteCard island |
| **3** | API endpoints replace localStorage | Already done (6 data API endpoints, 94 tests) |
| **4** | Dashboard stats as React island | Reuses primitives from milestone 2 + Metric |
| **5+** | Codebook, analysis, toolbar... | New compositions from existing primitives |
| **N** | Drop vanilla JS shell | Full React SPA |

At every milestone, the report works. Never broken.

**Milestone 2 builds primitives, not pages.** The quote card's interactive elements (star, edit, tag badge, tag suggest) all reappear on other surfaces (codebook, analysis, transcripts). Building them as reusable components means milestones 4+ are compositions, not rewrites. See `docs/design-react-component-library.md` for the 14-primitive dictionary, 4-round build sequence, and coverage matrix.

## Key principles

1. **Static export stays forever.** `bristlenose render` always produces a self-contained HTML file. The React app is the "workspace"; static HTML is the "deliverable."

2. **Islands, not big bang.** Each React component mounts into a DOM node in the existing HTML. The surrounding page stays vanilla JS until it's replaced.

3. **Database from the start.** SQLite replaces localStorage immediately. User state (edits, tags, hidden quotes) persists across sessions. Schema evolves with `create_all()` until it stabilises, then Alembic.

4. **Pipeline is the product.** The 12-stage analysis pipeline doesn't change. The server reads its output. The React app displays it.

## Dev setup

**Prerequisites:** Node.js (for frontend dev only — not needed by end users)

```bash
# One-time setup (after creating the serve worktree)
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/pip install -e '.[dev,serve]'
cd frontend && npm install && cd ..
```

**Running in dev mode (two terminals):**

```bash
# Terminal 1 — Python API server (auto-reloads on .py changes)
.venv/bin/bristlenose serve --dev

# Terminal 2 — React dev server (hot-reloads on .tsx changes)
cd frontend && npm run dev
```

- Visit `http://localhost:5173` — Vite serves the React app, proxies `/api/*` to FastAPI on :8150
- Visit `http://localhost:8150/api/health` — FastAPI health check (JSON)
- Visit `http://localhost:8150/api/docs` — auto-generated API documentation

**Production build:**

```bash
cd frontend && npm run build   # compiles React → bristlenose/server/static/
bristlenose serve               # serves React + API on :8150 (single port)
```

**Serving a project report:**

```bash
bristlenose serve ./my-interviews    # serves bristlenose-output/ from that dir at /report/
```

**Running tests:**

```bash
.venv/bin/python -m pytest tests/test_serve.py -v   # server tests only
.venv/bin/python -m pytest tests/                     # full suite (978 tests)
```

## Supersedes

- `docs/design-reactive-ui.md` — framework comparison (still relevant for rationale, but migration strategy is replaced by this doc)
- `docs/private/frontend-evolution.md` — "100 pushes" phased roadmap (Jinja2 intermediate step no longer planned)
- `docs/design-export-sharing.md` "dependency on React migration" section — export/sharing still deferred until React, but islands approach changes the timeline
