# Server & Data API — Context for Claude

## What this is

FastAPI server (`bristlenose serve`) that serves a React SPA (React Router, pathname-based routes) over HTTP, provides REST API endpoints for researcher state, and stores all pipeline output + researcher edits in SQLite. In serve mode, `app.py` replaces `<!-- bn-app -->` markers in the rendered HTML with `<div id="bn-app-root">`; React Router handles all client-side navigation (tab switching, session drill-down, back/forward). The SPA catch-all route (`GET /report/{path:path}`) returns the same transformed HTML for all `/report/*` paths. Transcript HTML files from `bristlenose render` are still served directly (route defined before the catch-all for priority).

## Architecture

```
bristlenose/server/
  app.py          — FastAPI factory (create_app), dev-mode HTML injection
  db.py           — SQLAlchemy engine, session factory, SQLite with WAL + FK
  models.py       — the ORM tables (count: `grep -c __tablename__ models.py`; history in docs/archive/design-serve-milestone-1.md)
  importer.py     — Pipeline JSON → SQLite on startup (idempotent upsert)
  admin.py        — SQLAdmin browser (dev-only, /admin/)
  autocode.py     — AutoCode engine (taxonomy, batching, async job runner, the register of sent quotes)
  autocode_catch_up.py — the debounced catch-up a quote starting to count schedules (ruling 4; § AutoCode)
  codebook_builder.py — Dynamic codebook builder engine (synthesize/scan/refine)
  routes/
    health.py     — GET /api/health (status/version + footer links/feedback config)
    sessions.py   — GET /api/projects/{id}/sessions (React sessions table, includes source_folder_uri)
    tapestry.py   — GET /api/projects/{id}/tapestry (timeline slice under each Sessions row, and its closed strip), …/turn-frames, …/transcription-quality; full note: gotchas.md § Route notes from the layout tree
    screens.py    — GET /api/projects/{id}/screens, …/screens/still, …/screens/status, …/screens/arrangements (the Screens lens; participants' screens are bearer-only and SERVER_ONLY in the export); full note: gotchas.md § Route notes from the layout tree
    quotes.py     — GET /api/projects/{id}/quotes (quotes grouped by section/theme)
    data.py       — 12 data API endpoints (Phase 1 researcher state sync)
    autocode.py   — 9 AutoCode endpoints (start, status, jobs in flight, cancel, proposals, accept/deny, accept-all/deny-all)
    codebook_builder.py — 5 dynamic-codebook-builder endpoints (per-tag prompt cultivation)
    dev.py        — Dev-only endpoints (visual diff, system info)
  codebook/       — YAML codebook templates (garrett, norman, uxr, plato …); a renamed tag carries renamed_from:
  codebook_sync.py — renames installed framework rows in place after a YAML rewording (AutoCode resolves the model's answers against the ROWS, so a rename in the YAML alone drops every proposal for that tag); runs at startup, before AutoCode, on import relink
  grounding.py    — SHARED CORE for assistant surfaces (chat lens + MCP)
  heading_names.py — a section's or theme's name as the researcher sees it (renames applied) + its id anchor; every surface that prints one reads it here
  chat_lens.py    — in-app cited question box (see docs/design-chat-lens.md)
  mcp_server.py   — the MCP tools (imports the `mcp` SDK at load: 275 ms; see below)
  mcp_mount.py    — the /mcp mount, built on its FIRST REQUEST so a serve start does not import the SDK
  static/         — Vite build output (React Router SPA bundle)
```

## Assistant surfaces: `grounding.py` is the shared core

Two features let a model reason over a project: the **in-app chat lens**
(`chat_lens.py` + `routes/chat_lens.py`) and the **MCP endpoint**
(`mcp_server.py`, for external agents). Both ground themselves in
`grounding.py` — corpus assembly, citation validation, the model-facing
`INVARIANTS`, and curated signal detection. **Do not grow a parallel
sibling**: whichever surface needs more generality extends *this* module.
Contract recorded in `docs/design-chat-lens.md` §7.

`INVARIANTS` is one tuple consumed by both surfaces (quote exclusivity, tag
double-counting, no cross-study speaker joins, denominators, the honesty
rule). Editing it changes both prompts — that's the point.

**Two citation spaces, deliberately.** `resolve_quote_indices` (integers
`[1]`…`[n]`, server-constructed) is the chat lens's — a fabricated citation
is an out-of-range int, caught by arithmetic. `resolve_quote_ids` (report
DOM ids) is the MCP workstream's, because agents cite ids the researcher can
look up. Both validate by **corpus membership**, which is deliberately
stricter than DB presence: a hidden or truncated-out quote is not citable.

**`load_signals(db, project_id, lens, curated=True)` is the REPORT VIEW and
diverges from `routes/signals.py` on purpose** — researcher edits applied,
removed sentiment badges honoured, unreviewed `ProposedTag` rows excluded
(accepted `QuoteTag` rows are the only tag truth), `Uncategorised` filtered
like the route does. The signals routes keep the engine view. The divergence
is pinned by a test; don't "fix" it. **Hidden quotes are no longer part of the
divergence (22 Oct 2026):** both leave them out, the routes through
`speaker_slots.analysis_quotes` (see § Evidence is filtered on read).

## MCP endpoint (`/mcp/`) — the §9a spike

Read-only Model Context Protocol server so a local agent (Claude Code,
Claude Desktop, ChatGPT desktop, Codex) can read ONE project. Design +
acceptance results: `docs/design-mcp-server.md`. Ships on BOTH channels
since 30 Jul 2026: CLI via the optional extra, macOS app via the bundled
sidecar (`build-sidecar.sh` installs `[serve,apple,desktop,mcp,voice]`; the
Connect Agent sheet + sidebar antenna badge are the desktop surface).

- The MCP endpoint's rules and gotchas (optional dependency, lifespan, auth, scoped token, handshake, `/api/health` `mcp` block, transport, error text, hard exclusions, adding a tool) moved to gotchas.md; the index is under Gotchas § MCP endpoint rules.

## Data API (Phase 1)

The data API replaces localStorage with HTTP: each endpoint mirrors one localStorage key (`people`, `edits`, `tags`, `hidden`, `starred`, `deleted-badges` under `/projects/{id}/`), and the frozen vanilla JS calls `apiPut()` after every `localStorage.setItem()`, fire-and-forget. **localStorage stays the source of truth for the page session; a failed sync toasts and does not roll back.** Serve mode is detected by `window.BRISTLENOSE_API_BASE`, injected at serve time. **A quote's DOM id is `q-{participant_id}-{int(start_timecode)}`, with `-{ordinal}` for every later quote the speaker starts in the same second; one builder and one parser, both in `grounding.py`.** The endpoint table, data-flow diagram, serve-mode detection and the full id-to-database mapping are in [`gotchas.md`](gotchas.md#data-api-phase-1--reference).

## api-client.js

The JS-side HTTP abstraction (`bristlenose/theme/js/api-client.js`).  Loaded second in `_JS_FILES` (after `storage.js`, before everything else).

- **`isServeMode()`** — `typeof BRISTLENOSE_API_BASE === 'string'`
- **`apiGet(path)`** — fetch GET, returns JSON or null on error
- **`apiPut(path, data)`** — fetch PUT with JSON body, shows toast on error via `showToast()` (optional dependency from `csv-export.js`)

All calls are **fire-and-forget promises**.  The JS modules don't `await` them.

## Health API contract (footer config)

`GET /api/health` returns:

- `status` (unchanged)
- `version` (unchanged)
- `links.github_issues_url`
- `feedback.enabled`
- `feedback.url`
- `telemetry.enabled`
- `telemetry.url`

This payload is shared by serve mode and export mode (embedded in `BRISTLENOSE_EXPORT.health`).

Default values:

- `links.github_issues_url` = `https://github.com/cassiocassio/bristlenose/issues/new`
- `feedback.enabled` = `true`
- `feedback.url` = `https://bristlenose.app/feedback.php`
- `telemetry.enabled` = `true`
- `telemetry.url` = `https://bristlenose.app/telemetry.php` (prod) or `/api/dev/telemetry` (dev mode, relative → local stub)

Optional env overrides:

- `BRISTLENOSE_GITHUB_ISSUES_URL`
- `BRISTLENOSE_FEEDBACK_ENABLED` (`1/true/yes/on` truthy; everything else false)
- `BRISTLENOSE_FEEDBACK_URL`
- `BRISTLENOSE_TELEMETRY_ENABLED`
- `BRISTLENOSE_TELEMETRY_URL`

### Dev telemetry stub (`--dev` only)

`bristlenose serve --dev` mounts `POST/GET/DELETE /api/dev/telemetry`, a stand-in for the production `telemetry.php` that appends to a JSONL file under the temp directory (spec: `docs/methodology/tag-rejections-are-great.md`). [full entry](gotchas.md#route-notes-from-the-layout-tree)

## Patterns to follow

### Adding a new data endpoint

1. Add the route to `routes/data.py` — follow `get_hidden`/`put_hidden` as the simplest template
2. Use `_get_db(request)`, `_check_project()`, `try/finally db.close()`
3. For quote-keyed data: use `_resolve_quote()` and `_quote_dom_id()` to translate between DOM IDs and DB rows
4. Add tests in `tests/test_serve_data_api.py` — the `client` fixture gives you a TestClient with the smoke-test data pre-imported (4 quotes: `q-p1-10`, `q-p1-26`, `q-p1-46`, `q-p1-66`)
5. If the JS needs to call it: add `if (isServeMode()) apiPut(...)` after the corresponding `store.set()` call

### Adding a new JS module that syncs state

1. Add `isServeMode, apiPut` to the `/* global ... */` comment
2. After every `yourStore.set(data)` call, add: `if (isServeMode()) apiPut('/your-endpoint', data);`
3. That's it.  `apiPut` prepends `BRISTLENOSE_API_BASE` internally — **never** add the base URL at the call site (double-prefix bug)

### DB dependency injection

```python
def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()
```

The factory is stored on `app.state` during `create_app()`.  Each route creates its own session and **must close it** in a `finally` block.

### Testing a route that starts a background task: hold the client open

A test that polls a route which starts a background task needs `with client:` around both calls, and must wait for the job to END before reading its status. [full entry](gotchas.md#background-passes-lifecycle-and-run-state-tests)

## React island integration

> **Dead as of 21 Sep 2026 — nothing reads these markers.** `serve_report_html()` does not exist in the tree, and neither does `_REACT_APP_MOUNT`; serve mode emits `<div id="bn-app-root">` directly (`server/app.py:657`) and the browser mounts the whole SPA there. The sealed Jinja2 renderer still *writes* `<!-- bn-app -->` and `<!-- bn-session-table -->` (`s12_render/report.py:189`, `:219`, `:235`, `:485`), but no Python reads either one. Per-island substitution is history; do not copy the pattern for a new island.

_Superseded; the record of how islands were mounted moved to gotchas.md._ [full entry](gotchas.md#frozen-vanilla-js-static-render-and-island-markers)

**When adding a new island:** register it in the renderer overlay CSS (4 places) so it shows green (React) not blue (Jinja2) under the dev-only overlay.

See `docs/design-react-islands.md` for the 6-step "Adding a new island" checklist, current islands table, and renderer overlay details.

## Dev loop (live JS reload)

**Vanilla JS is stripped in serve mode (Step 8).** `_strip_vanilla_js()` in `app.py` uses the `_JS_MARKER` boundary to remove all concatenated module code from the IIFE, keeping only `window.*` globals (`BRISTLENOSE_VIDEO_MAP`, `BRISTLENOSE_PLAYER_URL`, `BRISTLENOSE_ANALYSIS`) that React reads.  This runs in both dev and prod paths via `_transform_report_html()`.  The `_JS_FILES` list in `render/theme_assets.py` stays for `bristlenose render` (offline HTML).

**CSS changes are live in dev mode.** `_mount_dev_report()` registers a `/report/assets/bristlenose-theme.css` route that calls `_load_default_css()` on every request — no caching, no render step. Edit `bristlenose/theme/*.css` and refresh. This route is defined before the catch-all, so it takes priority over `FileResponse(output_dir / path)`.

**What still requires re-render:** changes to the Jinja2 HTML template itself, changes to data variables (quote map, analysis data). CSS no longer requires re-render in dev mode.

**Python changes** are handled by uvicorn's `--reload` (WatchFiles) — editing `data.py`, `app.py`, etc. triggers an automatic server restart.

## Names architecture — slots and identities (route C Phase 1)

A transcript's speaker token (`m1`) is a **slot**: one speaker in one session.
Moderator and observer tokens restart in every session, so a slot is not a
person. `session_speakers.person_id` is the per-session map: it points at one
`Person` per **identity** — a participant, or a moderator or observer across
however many sessions they ran — or is `NULL` when nothing has identified the
slot. `session_speakers.state` is `NULL` · `proposed` · `confirmed` · `cleared`
(the researcher said *not this person*; sticky across re-imports);
`evidence` says why (`platform-name`, `heard`, `label`, `inherited`,
`participant`, `pick`). **Codes are worked out on read**
(`speaker_slots._derive_codes`): a participant is its slot's code; a moderator or
observer is numbered per **(person, role)** as the pair first appears, so one
person is `m2` where they moderate and `o1` where they observe. The role is the
slot's `speaker_role`, which a recode changes (§J7) — not the tag's letter.
`persons.code` is kept by `renumber` as a record, not read by routes. Migration
013; `docs/design-people.md` §H H9, §J8.

**Every route emits the identity's code, never the slot's**: session 2's
moderator reads `m2` in `/sessions`, `/transcripts/{sid}` (speakers *and*
segments), `/dashboard`, `/people`, the moderator-question route and the MCP
overview, and an unidentified slot reads `m?` / `o?` — lettered `mA?` / `mB?` when
the session has more than one unknown of that role. `/sessions` also carries
`slot_code`, which is how a client addresses a slot, because a pick can renumber
identities. Read slots through `speaker_slots.project_slots` / `slot_map` /
`session_slots` — an outer join. **Never inner-join `session_speakers` to
`persons`**: it drops the unidentified slot (five sites did, before 013). Maps
keyed by `(session_id, slot_code)` (export, clips) stay keyed by slot, as quotes
are.

Moderators and observers are named from the pipeline's evidence (`session-speakers.json`); `PUT …/sessions/{sid}/speakers/{code}` takes the **slot** code only, never the identity code. [full entry](gotchas.md#names-and-people)

**Evidence is filtered on read.** Count quotes through `speaker_slots.evidence_out` / `evidence_quotes` / `analysis_quotes` (hidden quotes count nowhere), never a bare `Quote` query. [full entry](gotchas.md#names-and-people)

**Transcript layout edits** (`transcript_layout_edits`, migrations 015–016): paragraph split, join and move are recorded and replayed on every import. [full entry](gotchas.md#names-and-people)

**Participants are still named from `people.yaml`**, as below — the file is
not yet retired as a store (that is Phase 5's, with the docs that promise an
editable file).

### Import path (YAML → DB)

`_import_speakers()` in `importer.py` reads `people.yaml` via `_load_people_for_import()` and, for **participants**, fills `Person.full_name`, `short_name`, `role_title`, `persona`, `notes` from matching entries — empty fields only, on every import, so browser edits (via `PUT /people`) always win over YAML (`_import_participant`).

### Write-through path (DB → YAML)

`PUT /people` in `routes/data.py` writes to DB first (for UI responsiveness), then calls `_write_through_people_yaml()` which atomically updates `people.yaml` (tempfile + rename). This means pipeline re-runs see browser edits. Write-through is best-effort — if it fails, a warning is logged but the API still succeeds.

### Lifecycle

```
Pipeline run → people.yaml (names from LLM/labels/manual edit)
                    ↓
bristlenose serve → importer reads YAML → Person rows in DB
                    ↓
Browser edit → PUT /people → DB (immediate) + YAML (atomic write-through)
                    ↓
Pipeline re-run → reads YAML → sees browser edits → preserves them
```

### International names (`_extract_given_name` in people.py)

`suggest_short_names()` uses `_extract_given_name()` which handles:
- **CJK ideographic** (田中由紀) — uses full name as short name (no splitting)
- **Honorific prefixes** (Dr., Prof.) — strips via `_strip_honorific()` before taking first token
- **Family-first names** (Tanaka Yuki, Park Ji-hyun) — checks first token against `_FAMILY_FIRST_SURNAMES` (337 entries), takes second token if matched
- Everything else — first token heuristic (works for Western, Spanish double surname, Russian patronymic, Arabic, mononym)

Known false positive: westernized order "Wei Zhang" (where "Wei" is also in `_FAMILY_FIRST_SURNAMES`) flips incorrectly. Acceptable — researcher corrects via inline edit.

## Multi-project scope rules

The server currently loads one project (project ID 1). Multi-project is future work (`docs/design-multi-project.md`), but the data model is already designed for it. **These rules prevent us painting ourselves into corners:**

- **Instance-scoped tables** (no `project_id`): `Person`, `CodebookGroup`, `TagDefinition`. These are shared across projects by design. **Never add `project_id` to these tables** — cross-project identity and codebook reuse depend on them being global
- **Project-scoped tables** (have `project_id` FK): `Quote`, `Session`, `ScreenCluster`, `ThemeGroup`, and all researcher-state tables. **Every new analysis/state table must include `project_id`**
- **Frontend project ID**: read from `data-project-id` attribute via `useProjectId()` hook or `apiBase()` helper. **Never hardcode `/api/projects/1/...` in new code** — use `apiBase()` which reads the injected `BRISTLENOSE_API_BASE` global. Existing hardcoded locations are tracked in the design doc
- **Person rows are created per-import, not deduped** — two "John Smith" rows from different projects is correct. Merging is a future human-driven action via `person_links` table, not an automatic process. **Within one project this changes under route C** (`docs/design-people.md` §E decision 1, corrected 1 Oct 2026): one `Person` per identity, minted when a platform label or a researcher's pick first establishes it, and `session_speakers.person_id` nullable so a session can have a moderator nobody has identified. Built in Phase 1 (migration 013, `speaker_slots`)
- **`SessionSpeaker`** joins Person↔Session (with speaker code + role). It has no `project_id` because it inherits project scope through Session. This is correct — don't add `project_id` to it
- **Per-project SQLite files** — each project gets its own DB at `<output_dir>/.bristlenose/bristlenose.db`. Cross-project data (person links, app settings) will live in the instance DB at `~/.config/bristlenose/bristlenose.db`. Don't store cross-project relationships in per-project DBs

## Middleware stack

Four middleware layers in `create_app()` (plus the `@app.middleware` no-store hook), added in this order (Starlette processes in reverse — last added wraps outermost):

1. **BearerTokenMiddleware** — auth on `/api/*` and `/mcp` (not `/media/*` — see Gotchas)
2. **CORSMiddleware** — blocks all cross-origin requests
3. **GZipMiddleware** (`minimum_size=500`) — compresses text responses (JSON, HTML, CSS, JS). ~83% reduction on the quotes endpoint. Media files opt out via `Content-Encoding: identity` on the `FileResponse` to avoid wasting CPU on incompressible codecs and breaking byte-range video seeking. BREACH is not a concern — no user input is reflected in token-bearing responses
4. **LoopbackHostMiddleware** — outermost, the DNS-rebinding gate: 400 for any `Host` not 127.0.0.1 / localhost / [::1] (any port). CORS can't do this — a rebound page is same-origin — and the token is no defence because `/report/` hands it out. **Must stay added last.** Tests: a bare `TestClient` sends Starlette's default `testserver` and gets 400 — pass `base_url="http://127.0.0.1"` (`AuthTestClient` defaults to it, `tests.conftest.LOOPBACK_BASE_URL`). Never add `testserver` to the allowlist

## Work that must not be cut off: `busy.py` and `GET /api/background-work`

The Mac reaps a study's server about 90 s after its last window closes (`ServeReaping`). That is right for an idle server and wrong for one in the middle of a **paid** pass, whose calls are lost and which nothing restarts on a timer. The server says so: `busy.active_kinds()`, served at `/api/background-work` (`{"busy": bool, "kinds": [...]}`), which the desktop reads on its 20 s poll and holds the reap for, at most 30 minutes from the first hold.

- **A job is busy if an interrupted pass costs money or loses work nothing restarts.** Today: AutoCode (`run_autocode_job`, and a catch-up that is waiting or running) and Signals elaboration (`generate_elaborations`). Mark a new one with `@tracked("kind")` or `with busy.working("kind")`.
- **Screens reading and the scene strips are deliberately not busy.** They spend nothing, are cached by recording and resume at the next start, and holding a server for a study nobody is looking at would keep the Vision engine and the disk working for hours.
- **It is behind the bearer, not on `/api/health`.** Health is auth-exempt and refuses to publish when the researcher is working; this answer is coarse kinds with no timestamps. Do not move it.
- **Pin the caller, not only the helper:** `tests/test_server_busy.py` checks that the paid entry points carry the marker, because removing a decorator leaves every helper test green and makes a paid pass reapable again.

## Sidecar lifecycle (parent-death detection + structured exit logging)

`lifecycle.py` exposes two install functions, both safe to call once at server startup; both already wired into `cli._start_server`:

`install_exit_logger()` (always) logs one `sidecar_exit reason=…` line on shutdown; `install_parent_death_watcher()` (only with `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`) SIGTERMs the sidecar when it is reparented. [full entry](gotchas.md#background-passes-lifecycle-and-run-state-tests)

The watcher thread is a separate kernel thread (not an asyncio task) so a busy event loop or long-running LLM call doesn't delay parent-death detection.

Tests: `tests/test_server_lifecycle.py` (unit + 1 SIGTERM-delivery smoke test).

## Localhost access control

`middleware.py` — `BearerTokenMiddleware` validates `Authorization: Bearer <token>` on `/api/*` and `/mcp` (not `/media/*` — `<video>` cannot send the header; see Gotchas). `LoopbackHostMiddleware` refuses any non-loopback `Host` on every route (see Middleware stack). Token generated per server instance in `create_app()` via `secrets.token_urlsafe(32)`, stored on `app.state.auth_token`. Injected into SPA HTML via `json.dumps()`, printed to stdout for desktop app. Exempt: `/api/health`, `/api/docs`, `/report/*`, `/static/*`. **The exempt file routes are guarded by `_contained_path()` in `app.py`, and that guard is the only thing between a local process and the disk:** `/report/*` serves files only from `<output_dir>/assets/` (the SPA loads nothing else — the static report and transcript pages carry full names and are not served), `/media/*` from the project dir but **recordings only** (`AUDIO_EXTENSIONS | VIDEO_EXTENSIONS` from `models.py` — until 28 Sep 2026 it also served `.txt`/`.docx`/`.srt`/`.vtt`/images, so `transcripts-raw/*.txt`, the unredacted transcript, was one unauthenticated GET away), and both refuse any `.`-prefixed component (so `.bristlenose/pii_summary.txt` and `llm-calls.jsonl` stay unreachable), anything resolving outside the root, and suffixes off their allowlists. Until 28 Sep 2026 `/report/<path.ext>` was a bare `output_dir / path` — it served the re-identification key and `..%2F` escaped the output dir. Any new unauthenticated file route goes through the same helper (`tests/test_server_report_asset_guard.py`). Tests use `AuthTestClient` (from `tests/conftest.py`) which auto-injects the auth header. Design doc: `docs/design-localhost-auth.md`.

## Gotchas

**The full entries — the incident, the measurement, the fix — are in [`gotchas.md`](gotchas.md), by theme.** Read the theme's section before working in that area. This index is the rule and the tell, nothing more: one line per entry, same order as the file. Add a new gotcha to `gotchas.md` and its headline here.

**Database, migrations and test harness** (8) — [full entries](gotchas.md#database-migrations-and-test-harness)

- **`import_project` PASSIVE-checkpoints the WAL after its final commit (`_checkpoint_wal`) — don't remove it.**
- **Alembic: on a fresh DB every revision's `upgrade()` RUNS, after `create_all()`**
- **The migration head is derived, not pinned — `tests/test_migrations.py::_migration_head()` reads the version…**
- **TagDefinition foreign key — `codebook_group_id` is non-nullable. New tags go to the "Ungrouped" group.…**
- **`Session` name collision — SQLAlchemy's `Session` (the DB session) clashes with the `Session` model. Import…**
- **`db.close()` in finally — every route must close its session. Leaking sessions exhausts the SQLite…**
- **`caplog` sees what is logged after `create_app(project_dir=…)` since 20 Oct 2026; before that it saw…**
- **`db_url="sqlite://"` is ONE connection for every thread — a test that polls while a re-import runs will…**

**Project identity and the importer** (5) — [full entries](gotchas.md#project-identity-and-the-importer)

- **The SPA always reads project 1, but the importer can create a second row — and when it does, the report…**
- **A study's own database holds one study, found by its marker — never by path (15 Oct 2026).**
- **The match branch also heals `name`/`slug` — but ONLY from the `"Untitled"` sentinel.**
- **Transcript headers carry the path relative to the input folder, subfolder included**
- **`session_segments.json` is PRE-merge; the transcript `.txt` and the DB are POST-merge — never join them by…**

**Auth, media, downloads and locale** (4) — [full entries](gotchas.md#auth-media-downloads-and-locale)

- **The auth cookie is for the SPA's own navigations, nothing else.**
- **`/media/` must NOT require bearer token auth — HTML `<video>` and `<audio>` elements fetch their `src` URL…**
- **A download's `Content-Disposition` goes through `export_core.attachment_disposition()`, never an f-string.**
- **Server-rendered pages localise via `BRISTLENOSE_LANG`, NOT the bridge.**

**Quotes, headings, Signals and the data API** (9) — [full entries](gotchas.md#quotes-headings-signals-and-the-data-api)

- **PUT replaces entire state — PUT `/hidden` with `{}` unhides everything. PUT `/tags` with `{}` deletes all…**
- **Quote timecode range match — DOM ID uses `int(start_timecode)` which truncates. A quote at 123.45s becomes…**
- **Journey deep-links anchor by timecode, NOT by an index hand-off.**
- **A section or theme name is read through `heading_names.HeadingNames`, never `screen_label` / `theme_label`…**
- **Codebook tab stale counts on initial load — the CodebookPanel re-fetches via MutationObserver when its…**
- **Why the ordinal (R86, 21 Oct 2026) — Stage 9 cuts two quotes from one paragraph with one start, and the…**
- **The curation maps take a PATCH, and the SPA sends only that (20 Oct 2026).**
- **Signals snapshot: the reader filters, it never recalculates…**
- **Signals is withheld while its first report is built (30 Oct 2026, `docs/design-signals-lens-readiness.md`).**

**Names and people** (6) — [full entries](gotchas.md#names-and-people)

- **Moderators and observers are identities, named from evidence (route C Phase 1).**
- **Importer reads people.yaml for participants — `_import_speakers()` requires `output_dir` to find it; empty…**
- **Write-through is best-effort — `_write_through_people_yaml()` in `routes/data.py` logs a warning on failure…**
- **Moderators and observers come from the pipeline's evidence file; the slot PUT takes the slot code only**
- **Evidence is filtered on read — `speaker_slots.evidence_out` / `evidence_quotes` drop quotes credited to a…**
- **Transcript layout edits (`transcript_layout_edits`, migrations 015–016): a paragraph split, join, or move…**

**Frozen vanilla JS, static render and island markers** (8) — [full entries](gotchas.md#frozen-vanilla-js-static-render-and-island-markers)

- **Offline graceful degradation — static HTML files (opened from disk, not served) have no…**
- **No `await` on API calls — the JS modules fire `apiPut()` without awaiting. This means rapid clicks send…**
- **Always use `apiGet()`/`apiPost()` from `frontend/src/utils/api.ts`**
- **Ruff ignores JS files — `ruff check .` skips `.js` files. Don't pass JS files to ruff directly…**
- **IIFE wrapper around the script block — `render/report.py` wraps data variables + concatenated JS in…**
- **Baked HTML requires re-render to pick up new JS**
- **`pip install -e .` and render are separate steps**
- **Superseded: marker-based React island substitution (bn-{name} comments), kept as history**

**Background passes, lifecycle and run-state tests** (5) — [full entries](gotchas.md#background-passes-lifecycle-and-run-state-tests)

- **A GET that starts a background pass when the disk looks stale must find every failure written down, or the…**
- **A started run with no PID file reads as STRANDED, not in progress — so a test that wants "a run is in…**
- **A test that polls a route which starts a background task needs `with client:` and must wait for the job to END**
- **`install_exit_logger()` — registers signal/excepthook/atexit handlers that capture *why* the sidecar exited…**
- **`install_parent_death_watcher()` — daemon thread polls `os.getppid()` every 2s; if reparented…**

**MCP endpoint rules** (10) — [full entries](gotchas.md#mcp-endpoint-rules)

- **Optional dependency, and not imported at startup.**
- **Lifespan composition must be the LAST lifespan touch in `create_app`.**
- **Auth is bearer-only — `/mcp` is in `_AUTH_REQUIRED_PREFIXES` unconditionally…**
- **The MCP token is scoped — When `_BRISTLENOSE_MCP_TOKEN` is inherited…**
- **The handshake contract (desktop) — the Swift host writes `mcp-handshake.json`…**
- **`/api/health` carries `mcp: {mounted, instance_id, active}`**
- **Stateless streamable HTTP + JSON responses — no SSE through `BaseHTTPMiddleware`, and aligned with the…**
- **Tool errors never leak `str(exc)` — SQLAlchemy messages carry SQL and DB paths. Every tool body is wrapped…**
- **Hard exclusions, pinned by tests — no tool takes a filesystem path (input-schema allowlist), no writes, no…**
- **Adding a tool? — Put `project_id` in the signature (folder scope is phase 2), return JSON primitives only…**

**AutoCode and the codebook builder** (11) — [full entries](gotchas.md#autocode-and-the-codebook-builder)

- **`TagPrompt` is instance-scoped (mirrors `TagDefinition`) — a code's boundary is a property of the concept…**
- **Decision reasons are LOCAL ONLY — free-text reasons + quote content never leave the device. Consistent with…**
- **`version` is a content hash (`sha256(definition\napply_when\nnot_this)[:8]`) — same discipline…**
- **`default=""` applies at INSERT, not attribute access**
- **Test LLM override — routes read `app.state.settings` if set (tests inject a mock), else `load_settings()`.…**
- **One proposal per quote, on both store paths — `ProposedTag` is unique on `(job_id, quote_id)`…**
- **A fire-and-forget `asyncio.create_task()` MUST hold a strong ref.**
- **No AutoCode job survives a serve restart, so orphans are reconciled at boot.**
- **Which quotes a codebook has coded is its register of sent quotes, never a timestamp and never a session…**
- **A quote that starts counting is coded by itself, a few seconds on…**
- **An AutoCode incremental DB write MUST be write-only + non-fatal, or a locked DB silently eats a whole…**

**Route notes from the layout tree** (3) — [full entries](gotchas.md#route-notes-from-the-layout-tree)

- **tapestry.py route note: timeline slice, turn-frames, transcription-quality**
- **screens.py route note: the Screens lens, its env switch, bearer-only stills, arrangements**
- **Dev telemetry stub: three /api/dev/telemetry routes mounted only under serve --dev**
## Tests

48 tests in `tests/test_serve_quotes_api.py` (response shape, grouping, field values, researcher state round-trips via data PUT endpoints, speaker name resolution, error handling).  37 happy-path tests in `tests/test_serve_data_api.py`, 57 stress tests in `tests/test_serve_data_api_stress.py`, 43 dashboard tests in `tests/test_serve_dashboard_api.py`, 36 codebook CRUD tests in `tests/test_serve_codebook_api.py`.  All use the smoke-test fixture at `tests/fixtures/smoke-test/input/` which provides:
- 1 project, 1 session (`s1`), 2 speakers (`m1`, `p1`)
- 4 quotes: `q-p1-10` (Dashboard/confusion), `q-p1-26` (Dashboard/frustration), `q-p1-46` (Search/delight), `q-p1-66` (Onboarding/frustration)

Stress tests cover: Unicode (emoji, CJK, RTL, combining chars), large payloads (10 KB edits, 50 tags), rapid sequential PUTs (fast clicking), empty/whitespace values, malformed DOM IDs, duplicate tags and badges (unique constraint dedup), cross-endpoint interactions, and idempotency

### Future: Playwright E2E tests (post-React migration)

After the React migration, Playwright E2E tests will cover the full browser → JS → API → DB path. Currently deferred because E2E tests target DOM selectors which all change during migration. The React components will emit `data-testid` attributes from day one to provide stable selectors. See `docs/archive/design-reactive-ui.md` "Testing strategy" section for the full plan.

## React migration status

Migration complete (Steps 1–10). M5 (Feb 2026) landed 14 primitives + 2 infrastructure and 8 islands; there are **18** islands at HEAD, the two once listed as next among them — `TranscriptPage.tsx` and `SignalsPage.tsx`. Toast is the only unbuilt infrastructure primitive (build when first consumer needs it). See `docs/archive/design-react-migration-status.md` for the primitive inventory (16 rows), island inventory (8 rows), and CSS alignment summary.

## AutoCode (LLM-assisted tag application)

`autocode.py` engine + `routes/autocode.py` (9 endpoints) + three ORM tables (`AutoCodeJob`, `ProposedTag`, `AutoCodeSentQuote`, the register). First feature to call LLMs from serve mode — uses `asyncio.create_task()`, no Celery/Redis. Cloud-only (prompt weight ~14K-17K tokens doesn't fit Ollama's 4K context). Unique constraint `(project_id, framework_id)` — one job per codebook per project.

**Gotcha:** `LLMClient(settings)` takes only settings, not an LLMUsageTracker — creates its own internally.

- AutoCode's gotchas moved to gotchas.md; the index is under Gotchas § AutoCode.

See `docs/design-autocode.md` for the 7-step workflow, API endpoints, and testing notes.

## Dynamic codebook builder (cultivate a tag into a code)

`codebook_builder.py` engine + `routes/codebook_builder.py` (5 endpoints) + two ORM tables (`TagPrompt`, `TagPromptDecision`). Where AutoCode *applies* a fixed framework's discrimination prompts to all quotes, this *builds* those prompts for the researcher's **own** tags — synthesised from the quotes they coded by hand, then refined through accept/reject-**with-reasons** review.

Loop: `synthesize` (≥3 coded exemplars → `definition`/`apply_when`/`not_this`) → `candidates` (non-destructive ranked scan of the uncoded pool) → `decisions` (accept applies the tag + becomes an exemplar; reject + reason tightens the boundary; both refine the prompt in the same call). `PUT …/builder/prompt` lets the researcher edit the prompt directly; re-running `candidates` shows the set move.

Gotchas:
The codebook builder's gotchas (instance- vs project-scoped tables, decision reasons stay local, content-hash `version`, `default=""` at INSERT, test LLM override) moved to gotchas.md. [full entry](gotchas.md#autocode-and-the-codebook-builder)

See `docs/design-dynamic-codebook-builder.md`.

## Reference docs

- **Domain model rationale**: `docs/archive/design-serve-milestone-1.md`
- **Migration architecture**: `docs/archive/design-serve-migration.md`
- **React component library** (16 primitives, build sequence, coverage matrix): `docs/design-react-component-library.md` — **read this before building any React component**
- **Codebook lens**: `docs/design-codebook-v2.md` (the navigator that ships) and
  `docs/design-codebook-state-model.md` (what the enable/disable switch means).
  The v1 island's audit and CSS cleanup are history:
  `docs/archive/design-codebook-island.md`
- **React migration plan**: `docs/archive/design-reactive-ui.md`
- **Phase-by-phase walkthrough**: `docs/archive/react-migration-walkthrough.md`

**Signals snapshot: the reader filters, it never recalculates…** [full entry](gotchas.md#quotes-headings-signals-and-the-data-api)

**Signals is withheld while its first report is built (30 Oct 2026, `docs/design-signals-lens-readiness.md`).** [full entry](gotchas.md#quotes-headings-signals-and-the-data-api)
