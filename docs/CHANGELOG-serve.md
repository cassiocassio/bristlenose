# Changelog — Serve Branch

Development log for the `bristlenose serve` feature branch. Tracks milestones, architectural decisions, and the reasoning behind them. This branch runs in parallel with `main` and won't merge until the served version is production-ready.

---

## Backlog

- **Jinja2 vs React overlay toggle.** Dev-only feature: a toggle at the top of the report that tints Jinja2-rendered regions and React island regions with distinct pale pastel backgrounds (e.g. pale blue for Jinja2, pale green for React). Shows at a glance which parts of the report are still static HTML and which have been migrated to React islands. Implementation: inject a small inline `<script>` + `<style>` block in dev mode that adds `[data-source="jinja2"]` / `[data-source="react"]` data attributes and a toggle button. The pipeline renderer (`render_html.py`) would tag its wrapper `<div>`s with `data-source="jinja2"`; React islands add `data-source="react"` to their mount points. The toggle applies the pastel tints via CSS `[data-source] { background: ... }`. Off by default, toggled via a button or keyboard shortcut.

---

## Visual parity testing (15 Feb 2026)

### Visual diff tool + dev URL directory

**Built a dev-only visual comparison tool** to verify the React sessions table matches the Jinja2 static report. Three view modes: side-by-side (synced scroll), overlay (opacity slider blends between the two), and toggle (Space key instant swap).

**Results:** Near-perfect visual parity confirmed. Both tables render with the same CSS classes, same sparkline bars, same badge styling, same hover states. Minor differences in the Interviews column (filename wrapping differs slightly between `<a>` links in the static report vs `<span>` in the dev endpoint) and journey line-break points (consequence of column width differences). These are dev endpoint rendering differences, not React component bugs — the React version matches the real report.

**Dev URL directory:** `bristlenose serve --dev` now prints all available URLs on startup (Cmd-clickable in iTerm): report, visual diff, API docs, sessions API, sessions HTML, health check.

**What shipped:**
- `bristlenose/server/routes/dev.py` — dev-only API router: `GET /api/dev/sessions-table-html?project_id=1` renders the Jinja2 sessions table template from DB data, returns raw HTML fragment. Reuses `_render_sentiment_sparkline()`, `format_finder_date()`, `format_finder_filename()`, and the Jinja2 template environment from `render_html.py`
- `bristlenose/server/app.py` — recovers `_BRISTLENOSE_DEV` env var, registers dev router when dev mode, prints dev URL directory on startup
- `bristlenose/cli.py` — stashes `_BRISTLENOSE_DEV=1` and `_BRISTLENOSE_PORT` env vars for uvicorn factory recovery
- `frontend/visual-diff.html` + `frontend/src/visual-diff-main.tsx` — separate Vite entry point for the diff page (excluded from production build)
- `frontend/src/pages/VisualDiff.tsx` — diff UI with three view modes (side-by-side, overlay with opacity slider, toggle with Space key), keyboard shortcuts (1/2/3 for modes), synced scroll
- `frontend/src/pages/visual-diff.css` — toolbar and layout styles
- `frontend/vite.config.ts` — `visual-diff.html` added as second Vite entry point

---

## Milestone 1 — Sessions Table as React Island (complete)

### 15 Feb 2026 — Dev mode fixes and live testing

**Live-tested `bristlenose serve trial-runs/project-ikea --dev` end-to-end.** Three bugs found and fixed during hands-on testing:

1. **`--dev` mode lost `project_dir` on reload.** Uvicorn's `factory=True` + `reload=True` calls `create_app()` with no arguments on child process spawn — the `project_dir` arg from the CLI was lost. Fix: CLI stashes `project_dir` in `_BRISTLENOSE_PROJECT_DIR` env var; `create_app()` recovers it. Also separated dev and non-dev code paths in `cli.py` — dev mode never calls `create_app()` directly (only uvicorn's factory does), non-dev mode creates the app instance directly and opens the browser.

2. **`/report/` returned 404.** `StaticFiles(html=True)` expects `index.html` but the report file is `bristlenose-project-ikea-report.html` (includes project slug). Fix: `_ensure_index_symlink()` creates a relative `index.html → *-report.html` symlink at serve startup. Idempotent, portable. Noted in `docs/windows-tech-debt.md` — symlinks need admin/Developer Mode on Windows.

3. **Vite proxy missing `/report` route.** `vite.config.ts` only proxied `/api` to the backend. Added `/report` proxy so the Vite dev server forwards report requests to FastAPI.

**What shipped:**
- `bristlenose/cli.py` — separated dev/non-dev serve paths, env var passthrough
- `bristlenose/server/app.py` — env var recovery, `_ensure_index_symlink()`, warning on missing output dir
- `frontend/vite.config.ts` — `/report` proxy
- `docs/windows-tech-debt.md` — new file tracking platform assumptions (symlinks, config dirs, FFmpeg, etc.)
- `.gitignore` — font files in mockups directory

### 14 Feb 2026 — Steps 4-5 complete (milestone done)

**Mount point and React component.** `render_html.py` gains `serve_mode` flag; `SessionsTable.tsx` replaces the Jinja2 sessions table as a React island.

**What shipped:**

- `serve_mode: bool = False` parameter on `render_html()`. When True, the Sessions tab renders `<div id="bn-sessions-table-root" data-project-id="1">` instead of the Jinja2 `session_table.html` template. Dashboard compact table stays static. Static export path unchanged.

- JS audit: only `global-nav.js` binds to session table DOM (`tr[data-session]`, `a[data-session-link]`). React replaces that DOM in serve mode; the JS queries return empty NodeLists gracefully.

- `SessionsTable.tsx` — full-parity React component. Reads project ID from mount point, fetches `GET /api/projects/{id}/sessions`, renders the identical table structure with all CSS classes. All columns: ID with transcript link, speaker badges, Finder-style relative dates with journey arrows, duration, filename with middle-ellipsis, thumbnail play icon, sentiment sparkline bars, moderator/observer header. Loading and error states included.

- `main.tsx` updated with island pattern: finds `#bn-sessions-table-root`, reads `data-project-id`, mounts `<SessionsTable>`.

**What's next:** Milestone 2 planning — likely the quotes/codebook workspace.

### 14 Feb 2026 — Steps 1-3 complete

**Schema, importer, and sessions API.** 3,215 lines across 10 files. 72 new tests, full suite (1050) passing.

**What shipped:**

- Full 22-table SQLAlchemy domain schema (`server/models.py`). Instance-scoped tables (person, codebook_group, tag_definition) and project-scoped tables (session, quote, cluster, theme, plus all researcher state and conflict tables). Every grouping join table has `assigned_by` ("pipeline" | "researcher") from day one. Every AI-generated entity has `last_imported_at` for stale-data detection.

- Pipeline importer (`server/importer.py`). Reads `metadata.json`, `screen_clusters.json`, `theme_groups.json`, and raw transcript files. Creates sessions (with date and duration from transcript headers), speakers, persons, transcript segments, quotes, clusters, themes, and all join tables. Built as upsert by stable key — idempotent, safe to re-run. Called automatically on `bristlenose serve` startup.

- Sessions API endpoint (`server/routes/sessions.py`). `GET /api/projects/{project_id}/sessions` returns the full data shape needed by the React sessions table: speakers sorted m→p→o, journey labels derived from screen clusters by display_order, per-session sentiment counts aggregated from quotes, source files, moderator/observer names. Pydantic response models.

- Infrastructure: `db.py` updated to register all models and use `StaticPool` for in-memory SQLite testing. `app.py` registers sessions router, stores DB factory in app state for dependency injection, auto-imports on startup.

**What's next:** Step 4 (mount point in HTML — `serve_mode` flag) and Step 5 (React SessionsTable component with full visual parity).

### 14 Feb 2026 — Design session: domain model and pipeline→workspace paradigm

Extended design discussion that shaped the schema. Key decisions and the reasoning behind them:

**1. "Model the world, not this week's UI."** The user pushed back on a minimal schema (just enough for the sessions table) and asked: "is it smart to model all the data schema as a big picture exercise?" Yes — getting the entities right now means API endpoints and React components follow naturally. Getting them wrong means every milestone fights the schema.

**2. Instance-scoped vs project-scoped split.** Born from the question: "the same moderators, observers, and possibly participants might reappear across multiple projects." People, codebook groups, and tag definitions exist independently of any project. Everything else is project-scoped. This enables:
- Cross-session moderator linking (same person_id across session_speaker rows)
- Codebook reuse across studies (project_codebook_group join table)
- Future longitudinal analysis (same participant across wave 1 and wave 2)

Originally called "researcher-scoped" — renamed to "instance-scoped" after the user clarified that codebook groups belong to the Bristlenose installation, not to a particular researcher. Multi-researcher access control is a future permissions layer on top of this data model, not a change to it.

**3. Codebook groups as the reusable unit, not whole codebooks.** There is no `codebook` table. The user noted that a researcher might reuse their "Friction" group across five studies but create a fresh "Pricing" group for one study. The atom of reuse is the group, not the codebook.

**4. The AI is a "7 out of 10" draft.** The user's framing: "the initial analysis is often very good, like a 7 out of 10 and saves hours or days of work, and reveals insights a human might have missed — but it's also guaranteed to be wrong in some fundamental ways that humans can spot with contextual knowledge of the world." This is the philosophical foundation for the entire `assigned_by`/`created_by` pattern. The database treats pipeline output as a strong first draft, not ground truth with annotations on top.

**5. `assigned_by` over `is_override`.** Originally proposed as a boolean `is_override` on join tables. The user's question about what happens when the pipeline re-runs led to the realisation that "override" is the wrong mental model. Both pipeline and researcher are first-class authors. `assigned_by ("pipeline" | "researcher")` tracks who made each assignment. On re-import, the pipeline replaces its own assignments but never touches the researcher's. This was a correction from the user — the distinction matters because "override" implies a hierarchy (pipeline is default, researcher is exception), while "assigned_by" implies equal authorship with different sources.

**6. Moving quotes between clusters is "very common."** The user emphasised this is a core workflow, not an edge case. Likewise merging/splitting/deleting groups and putting quotes back into an unsorted pool. This validated the design of the unsorted pool (quotes with no join rows are visible in a "To be sorted" section) and the simple CRUD model for grouping operations.

**7. Incremental analysis is the normal workflow.** Running 2-3 interviews, getting an initial analysis, then adding more data later is standard qualitative research practice. The user: "this needs to be a first-class part of the system rather than a hack." This drove the upsert-based import design, `last_imported_at` timestamps for stale data, and the "researcher edits always win" principle.

**8. Import conflicts, not assignment history.** When the pipeline re-creates "Homepage" after the researcher renamed it to "Landing page", we need conflict detection — not a full audit trail. The `import_conflict` table logs clashes for human review. Full history can be added later as an additive `assignment_log` table if needed.

**9. Signals are recomputed, not stored.** The analysis module runs in <100ms. Storing signals creates a staleness problem every time the researcher hides a quote, renames a heading, or unlinks a quote from a grouping. Only `dismissed_signal` is persisted.

**10. `session_speaker` as the missing entity.** Identified during the concept inventory: a speaker code is really a join between a person and a session. Modelling it explicitly (with speaker_code, role, and per-session stats) is what makes cross-session moderator linking possible in Phase 2.

Full design rationale in `docs/design-serve-milestone-1.md`.

---

## Milestone 0 — Serve Shell (complete)

### 13 Feb 2026

**FastAPI + React + SQLite scaffolding.** `bristlenose serve` command, FastAPI application factory, SQLite with WAL mode, React + Vite + TypeScript tooling, HelloIsland proof of concept, Vite proxy for `/api/*` to FastAPI, health check endpoint.

Design docs: `docs/design-serve-migration.md` (architecture, tech stack, migration roadmap).
