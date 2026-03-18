# Multi-Project Awareness — Design Doc

## Status

**Design only** — no code changes. Maps assumptions, designs the data model, documents the identity problem.

## Context

Bristlenose currently assumes a single project per server instance. The DB schema already has a `Project` table and routes accept `{project_id}`, but the frontend hardcodes project ID 1 and there's no cross-project awareness.

Multi-project is the natural consequence of a subscription model — nobody pays monthly for a single study. It's a commercial wedge for the paid tier. The desktop app is the natural home for multi-project UX (project list, switching, cross-project views). CLI stays directory-native but accumulates awareness over time.

This doc does **not** propose building multi-project now. It:
1. Maps where single-project assumptions live in the codebase
2. Classifies which assumptions are safe vs. dangerous
3. Designs the data model so it doesn't paint us into corners
4. Documents the identity problem (cross-project persons, moderators, name collisions)

---

## 1. Project Index — How Bristlenose Discovers and Remembers Projects

Projects are directory-native — each project is a folder on disk containing input files and a `bristlenose-output/` directory. There is no central database of project data. The "project index" is just a list of pointers.

### Desktop app: active management

The desktop app maintains a project library — create, import, archive, reorder. The index lives in the app's support directory (`~/Library/Application Support/Bristlenose/projects.json` on macOS). Each entry is a pointer:

```json
{
  "projects": [
    {
      "id": "uuid-1",
      "name": "Q1 2026 Usability Study",
      "path": "/Users/cassio/Research/q1-usability",
      "last_opened": "2026-03-15T14:30:00Z",
      "created_at": "2026-01-10T09:00:00Z",
      "archived": false
    }
  ]
}
```

The desktop app owns creation, ordering, and archival. It renders the home screen from this index.

### CLI: passive accumulation

`bristlenose run` appends to a local index as a side-effect — opt-in, stored at `~/.config/bristlenose/projects.json`. The CLI doesn't manage projects actively; it just remembers which directories it has analysed.

Over time, the CLI gains commands:
- `bristlenose projects` — list known projects (path, name, last-run timestamp)
- `bristlenose serve --recent` — pick from history instead of passing a path
- `bristlenose serve --all` — multi-project mode (future, see §7)

### Key constraint: no central storage of project data

The index stores only pointers (path, name, timestamps). All project data stays in its own directory. This means:
- Moving a folder breaks the pointer — the index stores the last-known path, and the desktop app prompts to relocate
- Two users can share a project folder (Dropbox, git) without sharing an index
- Deleting the index loses the project list but not the data — `bristlenose serve <folder>` still works

---

## 2. Person Identity Model

This is the hard problem. Key scenarios:

| Scenario | Challenge |
|----------|-----------|
| "John Smith" is p3 in project A, p6 in project B | Same person, different codes — needs linking |
| "John Smith" is p1 in project C | Different person, same name — must not auto-merge |
| Cassio moderates 5 projects | Should be linkable across all of them |
| A freelance moderator runs 3 studies | m1 in each, but the Person rows are separate |

### Design principles

1. **Human-driven linking** — no automatic merging. Surface possible matches, let the researcher confirm
2. **Person rows stay instance-scoped** (no `project_id`) — this is already correct in the schema. The `Person` table has no `project_id` column, and its docstring says "merging is a future human-driven action"
3. **Speaker codes are session-scoped** — `SessionSpeaker` joins Person↔Session with a speaker code and role. This is already correct
4. **Profile connection is opt-in** — the researcher can say "I'm m1 in this project" but the system never assumes it

### Person linking mechanism

A new table for cross-project identity:

```
person_links
  id              INTEGER PRIMARY KEY
  person_a_id     INTEGER FK → persons.id
  person_b_id     INTEGER FK → persons.id
  link_type       TEXT  -- 'same' | 'not_same'
  created_at      DATETIME
  created_by      TEXT  -- 'researcher' (manual), 'suggestion' (auto-proposed)
  UNIQUE(person_a_id, person_b_id)
```

- **`same`**: "Person 7 and Person 12 are the same individual." Queries can union their data
- **`not_same`**: "Person 7 and Person 15 are NOT the same person despite sharing a name." Prevents re-suggesting the match
- **Transitivity**: if A=B and B=C, then A=C. The linking UI should surface this and let the researcher confirm the chain
- **Canonical person**: when persons are linked, the one with the most data (sessions, quotes, filled fields) becomes the display representative. No data is deleted — the link just changes how they're presented

### Where this table lives

Currently each project has its own SQLite file (`<output_dir>/.bristlenose/bristlenose.db`). Person links are cross-project by definition, so they belong in a **shared instance database** — the same `~/.config/bristlenose/bristlenose.db` that `_default_db_url()` in `db.py` already points to.

This means the architecture becomes:
- **Per-project DB**: quotes, sessions, clusters, themes, researcher state — everything project-scoped
- **Instance DB**: person links, negative links, future app-wide settings

The desktop app manages the instance DB. CLI single-project mode doesn't need it (person linking is a multi-project feature).

### Suggestion algorithm (future)

When a new project is imported, scan existing Person rows across all project DBs for:
- Exact name match (full_name or short_name)
- Similar name (Levenshtein ≤ 2)
- Same email (if ever added to Person)

Present matches as suggestions with a "Link" / "Not the same" action. Store the researcher's decision in `person_links`.

---

## 3. Project Lifecycle — Active → Archived → Reopened

### States

| State | Serve mode | Desktop home screen | CLI `bristlenose projects` |
|-------|-----------|--------------------|----|
| **Active** | Works normally | Full card, recent activity | Listed with path |
| **Archived** | Works if path exists | Greyed, collapsed section | Listed with `[archived]` marker |
| **Missing** | Errors with clear message | Red indicator, "Locate…" button | Listed with `[missing]` marker |

### Archiving

Archiving is a UI-only action — it sets `archived: true` in the project index. No files are moved or deleted. The project folder stays where it is. Archiving means "I'm done with this study for now" — it reduces clutter in the home screen.

### Re-opening after months

`bristlenose serve` on an old project must just work. The design ensures this:

1. **SQLite is rebuilt from intermediate JSON** — the importer runs on every `bristlenose serve` startup (already implemented, see `design-session-management.md`). The DB is a materialized view of the JSON, not the source of truth
2. **People YAML is the canonical source** for names — the DB is populated from it on import, and browser edits write back to it (write-through pattern already implemented)
3. **No database migration surprises** — if the schema has changed since the project was last served, SQLAlchemy `create_all()` handles new tables/columns. For breaking changes, the importer can detect the `bristlenose_version` in `metadata.json` and warn or migrate

### Data versioning

Intermediate JSON files include `bristlenose_version` (written by the pipeline). When serve mode loads a project:
- **Same version or newer compatible**: import normally
- **Old but compatible**: import with deprecation warning (e.g. "This project was analysed with v0.8. Re-run `bristlenose run` to update.")
- **Incompatible future format**: refuse to import, suggest downgrade or re-run

### What Bristlenose does NOT do

- **Backup** — the project is files on disk. Users use Time Machine, cloud sync, git, whatever they prefer. Bristlenose's job is to not corrupt state on re-open
- **Migration wizard** — no "upgrading your project…" spinner. The importer handles format differences silently where possible
- **Lock files** — no exclusive access. Two `bristlenose serve` instances on the same folder is undefined behaviour (SQLite WAL handles concurrent reads, but concurrent imports would race)

---

## 4. Assumptions Audit — What's Safe vs. Dangerous

### Hardcoded project ID locations

| Location | Code | Risk | Action |
|----------|------|------|--------|
| `app.py` ~L235 | `data-project-id="1"` in `_build_dev_html()` | Medium | Parameterise when multi-project ships — desktop app will inject correct ID |
| `app.py` ~L189 | `data-project-id="1"` in export HTML | Medium | Same — export knows which project it's exporting |
| `server/static/index.html` L15 | `data-project-id="1"` in Vite build output | Medium | Template at build time or inject at serve time |
| `s12_render/report.py` ~L90, L222 | `data-project-id="1"` in static render sessions table | Low | Deprecated path — won't receive multi-project support |
| `frontend/src/utils/api.ts` L26 | `|| "/api/projects/1"` fallback | Medium | `useProjectId()` hook already reads `data-project-id` attr; fallback is defensive |
| `frontend/src/contexts/PlayerContext.tsx` L85 | `fetch("/api/projects/1/video-map")` | Medium | Should use `apiBase()` — bug to fix before multi-project |
| `frontend/src/components/ExportDialog.tsx` L51 | `/api/projects/1/export` | Medium | Should use `apiBase()` — same bug class |
| `frontend/src/hooks/useProjectId.ts` L12 | `?? "1"` default | Low | Defensive fallback — correct pattern, just needs the attribute set correctly |
| `frontend/src/main.tsx` (6 locations) | `.getAttribute("data-project-id") \|\| "1"` | Low | Island mount points — same pattern as `useProjectId` |
| `app.py` ~L173-174 | `/api/projects/1/sessions` in dev print | None | Informational only |
| `server/CLAUDE.md` L239 | Documents "Project ID is always 1" | None | Documentation — update when multi-project ships |

### Schema design (already correct)

| Location | Assumption | Risk | Status |
|----------|-----------|------|--------|
| `Person` table (no `project_id`) | Instance-scoped | **Correct** | Already right for cross-project identity |
| `CodebookGroup` table (no `project_id`) | Instance-scoped | **Correct** | Shared codebook library — projects activate groups via `ProjectCodebookGroup` join |
| `TagDefinition` table (no `project_id`) | Instance-scoped | **Correct** | Tags are reusable across projects |
| `Quote.participant_id` is a string, not FK | Loose coupling | **Correct** | Enables offline rendering, cross-project portability |
| `SessionSpeaker` join table | Links Person↔Session | **Correct** | Already supports cross-session moderator tracking |
| All analysis tables have `project_id` FK | Project-scoped | **Correct** | Clean separation |

### Architectural assumptions

| Location | Assumption | Risk | Action |
|----------|-----------|------|--------|
| `app.py` startup | `_import_on_startup()` loads ONE project | High | Multi-project needs either multiple imports or lazy loading |
| `db.py` | `db_url_for_project()` returns per-project SQLite path | **Correct** | Each project already gets its own DB — multi-project = multiple DB connections |
| `importer.py` | Creates one `Project` row per import | Low | Already idempotent — re-import updates, doesn't duplicate |
| `people.yaml` is per-project | No cross-project names | **Correct** | Each project has its own namespace — linking happens at instance DB level |
| Importer creates new Person rows per import | No dedup across projects | Low | Fine — linking is a future human action, not auto-merge |
| `BRISTLENOSE_API_BASE` global | Single base URL | Medium | Multi-project could use `/api/projects/{id}` — the `apiBase()` helper already abstracts this |

### Summary

The **schema is already multi-project ready** — the dangerous assumptions are in the **server startup** (single project import) and **frontend hardcoded IDs** (12 locations, all parameterisable). The data model decisions made in Milestone 1 (`design-serve-milestone-1.md`) were forward-looking: instance-scoped persons, project-scoped analysis tables, and the `SessionSpeaker` join table all support multi-project without migration.

---

## 5. People Tab — Per-Project Now, Cross-Project Later

### Single-project serve mode (now)

A per-project People tab showing all known persons for this project:

| Column | Source |
|--------|--------|
| Name (full + short) | `Person.full_name`, `Person.short_name` |
| Role | `SessionSpeaker.role` (participant/moderator/observer) |
| Sessions | Count of `SessionSpeaker` rows for this person |
| Speaker codes | `SessionSpeaker.speaker_code` per session (e.g. "p3 in Session 1, p1 in Session 4") |
| Quotes | Count of quotes where `participant_id` matches any of this person's speaker codes |
| Tags | Most common tags on this person's quotes |
| Notes | `Person.notes` (editable) |

Data already exists in `Person` + `SessionSpeaker` tables. No new API needed beyond a `GET /api/projects/{id}/people` that joins these.

### Desktop app (future): cross-project view

Graduates to a cross-project People tab — "here are all the people across all your studies":

- **Linked persons** show up once with a combined view: name, all projects they appear in, total sessions, total quotes
- **Unlinked same-name persons** show disambiguation: "John Smith (Q1 Usability)" vs "John Smith (Mobile Pilot)"
- **Link suggestions** surface at the top: "These might be the same person — confirm or dismiss"

### Key queries the People tab enables

| Query | How it works |
|-------|-------------|
| "All projects moderated by X" | Linked Person rows + `SessionSpeaker.role = 'moderator'` filter |
| "This participant appeared in 2 studies" | Person linking — same person, different projects |
| "All quotes tagged [trust] across projects" | Shared `TagDefinition` (instance-scoped) + cross-project quote query |
| "Project timeline" | Project index metadata (created, last analysed, archived) |

### Desktop-first feature

The cross-project People tab is a desktop app feature, not CLI. CLI stays per-project — `bristlenose serve` shows only the people in the loaded project. The desktop app can query across project DBs because it manages the project index and the instance DB.

---

## 6. Commercial Framing

| | Free tier | Paid tier |
|---|-----------|-----------|
| Projects | Single project, CLI-only | Project library (desktop app) |
| Persistence | No cross-project memory | Project index, cross-project identity |
| People | Per-project only | Cross-project linking, moderator views |
| Archive | Manual (just stop serving) | Archive/re-open with state preserved |
| Search | Per-project | Cross-project search |
| App | CLI | Desktop app (macOS native shell) |

Multi-project is the natural upsell — it's what makes the subscription worthwhile over one-off CLI use. The free tier is fully functional for single studies; the paid tier adds the "research practice" layer (managing multiple studies, tracking participants across studies, building a codebook library).

---

## 7. What NOT to Build Yet

Explicit list of things we're future-proofing for but not implementing:

| Feature | Why not now | What we're protecting |
|---------|------------|----------------------|
| Home screen / project switcher | Desktop app dependency | Project index schema (§1) |
| Person linking UI | Needs multi-project serve first | `person_links` table design (§2), instance-scoped Person table |
| Cross-project search | Needs multi-project serve + indexing | Per-project SQLite isolation |
| Project archive/restore | Desktop app feature | Index schema `archived` field (§1), re-open path (§3) |
| Profile → moderator connection | UX research needed | Person linking is general-purpose, not moderator-specific |
| `bristlenose projects` CLI command | Low priority vs. desktop | Index file location (§1) |
| Multi-project serve mode | Architectural work (multiple DB connections, project switching API) | Per-project DB isolation, `apiBase()` abstraction |
| Person suggestion algorithm | Needs linking UI first | `person_links.link_type = 'not_same'` for negative links |
| Shared codebook across projects | `CodebookGroup` is already instance-scoped | `ProjectCodebookGroup` join table already exists |

The current architecture supports all of these without schema migration. The work is in the server (loading multiple projects), the frontend (project context in React Router), and the desktop app (project list, switching, linking UI).

---

## Appendix: Database Architecture for Multi-Project

### Current: one SQLite per project

```
project-a/bristlenose-output/.bristlenose/bristlenose.db  ← project A data
project-b/bristlenose-output/.bristlenose/bristlenose.db  ← project B data
~/.config/bristlenose/bristlenose.db                       ← instance DB (unused today)
```

### Future: instance DB for cross-project data

```
~/.config/bristlenose/bristlenose.db
  ├── person_links          (cross-project identity)
  ├── app_settings          (future)
  └── ...

project-a/.bristlenose/bristlenose.db
  ├── persons, sessions, quotes, ...  (project-scoped)
  └── ...

project-b/.bristlenose/bristlenose.db
  ├── persons, sessions, quotes, ...  (project-scoped)
  └── ...
```

The instance DB stores only cross-project relationships. Person IDs in `person_links` reference rows in project-specific DBs — this requires the desktop app to maintain a mapping of (project_id, person_id) tuples. An alternative is to use UUIDs for Person IDs instead of auto-increment integers, making them globally unique. This is a decision to make when building the linking feature, not now.

### Migration path

No migration needed for existing projects. The instance DB is created when the desktop app first launches (or when `bristlenose projects` is first run). Existing per-project DBs continue to work unchanged.
