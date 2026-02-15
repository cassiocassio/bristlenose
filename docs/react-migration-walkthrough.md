# React Migration Walkthrough

This is an explanatory walkthrough of the reactive UI migration — what's been done, what each phase involves, and why.

---

## Context

Bristlenose generates static HTML reports with 24 vanilla JS modules (~3,000+ lines) concatenated into a `<script>` block. This architecture is hitting limits:

- **Cross-page state** — name edits on the report don't reach transcript pages without localStorage hacks
- **Manual DOM binding** — every interactive feature needs hand-written `classList.toggle` / `innerHTML` / `TreeWalker` mutation code
- **No file writes** — static HTML can't save; users must clipboard-export YAML, paste into a file, then re-render
- **Growing complexity** — 24 modules with implicit global dependencies between them

The migration moves to **React 19 + Vite + FastAPI**, using an **islands architecture** (mount React components into the existing static HTML progressively).

---

## What's already done (Phase 0 — this `serve` branch)

### FastAPI server (`bristlenose/server/app.py`)
- `bristlenose serve <project_dir>` starts a local server on port 8150
- Serves the existing static HTML report at `/report/`
- API routes: `/api/health`, `/api/projects/{id}/sessions`
- SQLite database (SQLAlchemy ORM) for structured session data
- Dev mode (`--dev`): SQLAdmin browser at `/admin/`, auto-discovered design artifacts, renderer overlay toggle (D key tints regions by origin: Jinja2/React/Vanilla JS)

### Vite + React scaffold (`frontend/`)
- `frontend/vite.config.ts` — React plugin, proxies `/api` → FastAPI, builds to `bristlenose/server/static/`
- `frontend/src/main.tsx` — island entry point, mounts React components into existing HTML via `createRoot()`
- React 19, TypeScript 5.7, Vite 6

### Three React islands (`frontend/src/islands/`)
- **`HelloIsland.tsx`** — proof-of-concept (will be removed)
- **`SessionsTable.tsx`** — full sessions table with speaker badges, sparklines, thumbnails, drill-down. This is production-ready and demonstrates the island pattern
- **`AboutDeveloper.tsx`** — dev-mode info panel in the About tab

### How islands work
The static HTML (rendered by the Python pipeline) includes empty mount points like `<div id="bn-sessions-table-root">`. When served via `bristlenose serve`, `main.tsx` finds these elements and mounts React components into them. The rest of the page stays as vanilla HTML + JS.

---

## Phase 1 — Data API (not started)

**Goal:** Replace localStorage/clipboard with HTTP endpoints. Keep vanilla JS, just swap the storage layer.

### What happens
1. Add API endpoints:
   - `PUT /api/projects/{id}/people` — write name/role edits back to `people.yaml`
   - `PATCH /api/projects/{id}/quotes/{quote-id}` — save quote text edits
   - `GET/PUT /api/projects/{id}/tags` — read/write user-defined tags
   - `GET/PUT /api/projects/{id}/hidden` — read/write hidden quote state
   - `GET/PUT /api/projects/{id}/starred` — read/write favourites

2. Modify existing vanilla JS modules (`editing.js`, `names.js`, `tags.js`, `hidden.js`, `starred.js`) to call these endpoints instead of writing to localStorage

3. Namespace localStorage keys by project slug so multiple reports on `localhost:8150` don't clobber each other

### Why this is first
This delivers the biggest user-facing improvement (no more clipboard export → paste → re-render) without touching the frontend framework. It's also the foundation that all later phases depend on — React components will call the same API.

### What's tricky
- The existing JS modules use synchronous `localStorage.getItem()`. HTTP calls are async. Each module needs an async wrapper, with optimistic UI updates and error fallbacks
- Cross-page state (e.g. name edits propagating to transcript pages) now works naturally — both pages read from the same API — but the existing `storage` event listeners need updating

---

## Phase 2 — Component-by-component migration (not started)

**Goal:** Replace vanilla JS modules one at a time with React components, mounted as islands.

### Migration order (roughly by complexity/dependency)
1. **Settings/appearance toggle** (`settings.js`) — self-contained, no cross-module deps
2. **Search** (`search.js`) — isolated, good candidate for React controlled input
3. **Star/favourite toggle** (`starred.js`) — simple state toggle, FLIP animation can use React Transition Group or framer-motion
4. **Hidden quotes** (`hidden.js`) — badge count + dropdown, moderate complexity
5. **Tag filter** (`tag-filter.js`) — checkbox tree, benefits from React's declarative rendering
6. **Codebook** (`codebook.js`) — complex (drag-drop, colour sets, group CRUD), but self-contained
7. **Names table** (`names.js`) — contenteditable, needs careful ref management
8. **Editing** (`editing.js`) — contenteditable quotes, TreeWalker text mutation — the hardest migration (React's virtual DOM fights contenteditable)
9. **Histogram** (`histogram.js`) — data visualisation, good React fit
10. **Analysis heatmaps** (`analysis.js`) — OKLCH colour maths + grid layout
11. **Player** (`player.js`) — popout window management, postMessage IPC
12. **Tab navigation** (`global-nav.js`) — becomes the router shell in Phase 3

### How each migration works
For each module:
1. Create a new React component in `frontend/src/islands/`
2. Add a mount point `<div id="bn-{feature}-root">` in the Jinja2 template
3. Wire it up in `main.tsx`
4. Remove the corresponding vanilla JS module from the concatenation list in `render_html.py`
5. The renderer overlay (D key) shows the component as green (React) instead of amber (vanilla JS)

### What's tricky
- **contenteditable** — React's reconciler wants to own the DOM. Editable text needs `useRef` + uncontrolled mode + `dangerouslySetInnerHTML` for initial render, with manual DOM reads on blur/change. This is the known "price" of choosing React over Svelte
- **TreeWalker** — search highlighting walks the DOM and wraps text nodes. In React, this must happen via refs after render, not through state
- **Implicit globals** — some modules communicate through shared global state (e.g. `window.BN_TAGS`). Each migration must identify and replace these with proper React context or props

---

## Phase 3 — Hybrid SPA (not started)

**Goal:** Add client-side routing so tab switches don't reload the page.

### What happens
1. Add React Router (or TanStack Router)
2. The tab bar (`global-nav.js` → React component from Phase 2) becomes the router's navigation
3. Each tab becomes a route: `/report/project`, `/report/sessions`, `/report/quotes`, etc.
4. Server-side: FastAPI returns the same HTML shell for all `/report/*` routes (SPA fallback)
5. Transcript pages become nested routes (`/report/sessions/:id/transcript`)

### Why separate from Phase 2
Client-side routing changes how the app bootstraps and navigates. Doing it during component migration would create two moving targets. Better to finish migrating components in the multi-page architecture, then wrap them in a router.

### What's tricky
- **Hash fragment conflict** — the player currently uses `#src=…&t=…` and deep links use `#t-123`. SPA routers typically own the URL. Solution: use search params (`?src=…&t=…`) for the player, hash for deep links within a page
- **`storage` event** — currently used as IPC between report and codebook windows. In a single SPA, both are in the same window so `storage` events don't fire. Replace with React context or a state manager
- **Relative paths** — `assets/…`, `sessions/…` break with nested routes. Need a base URL configuration

---

## Phase 4 — Full SPA (not started)

**Goal:** The entire report is a React app. No more Jinja2 template.

### What happens
1. The Python pipeline renders JSON (it already produces intermediate JSON; this becomes the primary output)
2. The React app hydrates from either:
   - **Served mode:** API calls to FastAPI (`/api/projects/{id}/quotes`, etc.)
   - **Standalone mode:** a JSON blob embedded in the HTML file (for export/sharing)
3. The Jinja2 template (`render_html.py`) is retired — the pipeline outputs data, the React app renders it

### Why this matters beyond developer experience
This is the **prerequisite for the sharing/export story**. Once the React app can hydrate from an embedded JSON blob, exporting a report becomes: "snapshot the project data → embed in the React app shell → output a single HTML file." This is dramatically simpler than the original vanilla JS export design (which required DOM cloning, a zip library, and careful dehydration).

### What's tricky
- **Bundle size** — the full React app + all components need to be small enough for a standalone HTML file. Code splitting helps for served mode but not for export. May need to revisit Preact at this point (same API, ~3 KB vs ~42 KB)
- **SSR/hydration** — for the standalone file, the HTML needs to be pre-rendered (not just a blank `<div id="root">`). Either server-side render in Python (via a Node subprocess or a Python JSX renderer) or ship the app as a client-only SPA with a loading state
- **Backward compatibility** — existing reports (static HTML files) should still work. The pipeline version that generated them predates the React app. These files are self-contained and will continue to work as-is

---

## Phase 4.5 — Export & Sharing (blocked on Phase 4)

**Goal:** Output a standalone, shareable HTML file from the React app.

### What happens
1. `bristlenose export` bundles the React app + project JSON into a single HTML file
2. The file works offline (no server needed) — React hydrates from the embedded JSON
3. Edits in the exported file are local-only (localStorage or IndexedDB)
4. Optionally: a "sync" mode where the exported file can phone home to a served instance

This is the feature that makes Bristlenose useful beyond solo researchers — sharing an interactive report with stakeholders who don't have Bristlenose installed.

---

## Summary timeline

| Phase | What | Depends on | User-facing value |
|-------|------|-----------|------------------|
| **0** (done) | FastAPI server, Vite scaffold, SessionsTable island | — | `bristlenose serve` works, dev tooling |
| **1** | Data API, replace localStorage | Phase 0 | Edits save to files automatically |
| **2** | Component-by-component React migration | Phase 1 | Smoother UI, fewer bugs, easier to add features |
| **3** | Client-side routing (SPA shell) | Phase 2 | Instant tab switches, deep linking |
| **4** | Full React app, retire Jinja2 | Phase 3 | Clean architecture, data-driven rendering |
| **4.5** | Export/sharing | Phase 4 | Shareable interactive reports |

Each phase is independently shippable. The static HTML report continues to work throughout — `bristlenose run` still produces a standalone file. The React path is an enhancement available through `bristlenose serve`.

---

## Prompt for a new session to start Phase 1

Copy this into a new Claude session in the `serve` worktree:

> **Phase 1: Data API for the React migration.**
>
> Context: Read `docs/design-reactive-ui.md` (the full migration plan) and `docs/react-migration-walkthrough.md` (phase-by-phase walkthrough). Phase 0 is done — FastAPI server exists at `bristlenose/server/app.py`, React islands work, `bristlenose serve` runs.
>
> Phase 1 goal: Add REST API endpoints so the vanilla JS modules can save edits via HTTP instead of localStorage/clipboard. No React changes — keep existing JS, just swap the storage layer.
>
> Endpoints needed:
> - `GET/PUT /api/projects/{id}/people` — read/write people.yaml (name/role edits)
> - `PATCH /api/projects/{id}/quotes/{quote-id}` — save quote text edits
> - `GET/PUT /api/projects/{id}/tags` — read/write user-defined tags
> - `GET/PUT /api/projects/{id}/hidden` — read/write hidden quote state
> - `GET/PUT /api/projects/{id}/starred` — read/write favourites
>
> Then modify the vanilla JS modules (`editing.js`, `names.js`, `tags.js`, `hidden.js`, `starred.js`) to call these endpoints instead of localStorage. Use optimistic UI updates with error fallbacks.
>
> Also: namespace localStorage keys by project slug (currently all reports on localhost clobber each other).
>
> Start by exploring the existing server routes in `bristlenose/server/routes/`, the current JS modules in `bristlenose/theme/js/`, and the data models in `bristlenose/server/models.py` and `bristlenose/models.py`.
