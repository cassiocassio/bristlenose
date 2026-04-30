---
status: mixed
last-trued: 2026-04-30
trued-against: HEAD@first-run on 2026-04-30
split-candidate: true
---

# Multi-Project Awareness — Design Doc

## Changelog

- 2026-04-30 — Trued against shipped reality. Phase 1 (Project Index, Folders, VolumeWatcher / availability) shipped via `port-v01-ingestion` (commit `e781ebe`, merged to v0.15.0 on 26 Apr 2026); per-section `status:current` markers added. Person identity (§2), Archive (§3a), cross-project search (§3b), `bristlenose forget` (§3c), CLI `bristlenose projects` / `--recent` / `--all` all stay pending.

## Status

**Mixed — Phase 1 shipped, Phase 2+ pending.** Project Index, folders + drag-reorder + Move-To submenu, volume mount/unmount tracking and `Project.availability` enum, "Plug in [volume]" UX shipped via `port-v01-ingestion` (v0.15.0, 26 Apr 2026). Anchors: `desktop/Bristlenose/Bristlenose/ProjectIndex.swift:1-779`, `VolumeWatcher.swift`, `MenuCommands.swift:317-415`. Person identity model, Archive, cross-project search, `forget` command remain pending. The home-screen design in §1 below describes a sidebar-list-centric view; a separate detail-pane welcome placeholder shipped in commit `4772c3a` (parked for full design post-alpha — see 100days §3 Should "Desktop home view"). This doc maps assumptions, designs the data model, and documents the identity problem.

## Context

Bristlenose currently assumes a single project per server instance. The DB schema already has a `Project` table and routes accept `{project_id}`, but the frontend hardcodes project ID 1 and there's no cross-project awareness.

Multi-project is the natural consequence of a subscription model — nobody pays monthly for a single study. It's a commercial wedge for the paid tier. The desktop app is the natural home for multi-project UX (project list, switching, cross-project views). CLI stays directory-native but accumulates awareness over time.

### The core scenario

A freelance UX researcher with a MacBook. Over 8 months she runs 5 projects for 3 clients. Each client gets a folder. Storage is mixed:

- **On the client's SharePoint** — accessible when on VPN at the client site
- **On a 2TB USB-C external drive** — the overflow drive, because nobody wants work videos filling up the main SSD. Available when plugged in at home
- **Local on the Mac** — projects done in cafes and co-working spaces where there's no external storage

At any given moment, some projects are available and some aren't. The home screen shows all of them — available projects are full cards, unavailable ones are greyed out with a hint ("External drive — Samsung T7", "SharePoint — Acme Corp") so she knows how to bring them back. Each project lives in the right folder for its client. This is the day-to-day experience the design must get right.

### What this doc covers

This doc does **not** propose building multi-project now. It:
1. Maps where single-project assumptions live in the codebase
2. Classifies which assumptions are safe vs. dangerous
3. Designs the data model so it doesn't paint us into corners
4. Documents the identity problem (cross-project persons, moderators, name collisions)

---

## 1. Project Index — How Bristlenose Discovers and Remembers Projects

> **Status (`current`):** Project index, JSON persistence, and folder grouping shipped (26 Apr 2026, `port-v01-ingestion`). Schema below matches `ProjectIndex.swift:30-115`.

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

The index stores only pointers (path, name, timestamps, location hints). All project data stays in its own directory. This means:
- Projects on unmounted volumes appear greyed out, not broken — the index remembers where they live (see §3: Unavailable projects)
- Moving a folder on a mounted volume breaks the pointer — the desktop app detects this (volume mounted but path gone) and prompts to relocate
- Two users can share a project folder (Dropbox, git) without sharing an index
- Deleting the index loses the project list but not the data — `bristlenose serve <folder>` still works

### Folders — one level of grouping

> **Status (`current`):** Folders, drag-reorder, "Move to" submenu, inline rename, expand/collapse persistence all shipped (`MenuCommands.swift:317-415`, `FolderRow.swift`, `ProjectIndex.swift` `Folder` struct). One-level depth as designed.

The project index supports **one level of folders** — a flat grouping that maps to how researchers naturally organise work (by client, product, team, or research programme). No nesting.

```json
{
  "folders": [
    {
      "id": "uuid-f1",
      "name": "Acme Corp",
      "position": 0,
      "collapsed": false,
      "created_at": "2026-01-05T09:00:00Z"
    }
  ],
  "projects": [
    {
      "id": "uuid-1",
      "name": "Q1 2026 Usability Study",
      "path": "/Users/cassio/Research/q1-usability",
      "location": {
        "type": "local",
        "volume_name": null,
        "volume_relative_path": null,
        "display_hint": "On this Mac"
      },
      "folder_id": "uuid-f1",
      "position": 0,
      "last_opened": "2026-03-15T14:30:00Z",
      "created_at": "2026-01-10T09:00:00Z",
      "archived": false,
      "previous_folder_id": null,
      "previous_folder_name": null
    },
    {
      "id": "uuid-2",
      "name": "Onboarding Pilot",
      "path": "/Volumes/Samsung T7/Research/onboarding-pilot",
      "location": {
        "type": "volume",
        "volume_name": "Samsung T7",
        "volume_relative_path": "Research/onboarding-pilot",
        "display_hint": "External drive — Samsung T7"
      },
      "folder_id": null,
      "position": 1,
      "last_opened": "2026-03-10T11:00:00Z",
      "created_at": "2026-02-20T14:00:00Z",
      "archived": false,
      "previous_folder_id": null,
      "previous_folder_name": null
    }
  ]
}
```

**Schema fields explained:**

| Field | On | Purpose |
|-------|-----|---------|
| `position` | folder, project | Explicit sort order for drag-and-drop reorder. Without this, the home screen defaults to alphabetical or created-date, both brittle |
| `collapsed` | folder | Persisted expand/collapse state. Critical for managing grey-out noise — collapse the folders you're not working with today |
| `location` | project | Where the project lives on disk — type, volume name, relative path within the volume, human-readable hint. Auto-populated on first add |
| `volume_relative_path` | location | Path within the volume (e.g. `Research/onboarding-pilot`). Enables auto-resolution when a volume mounts with a slightly different name (`Samsung T7` vs `Samsung T7 1`) |
| `previous_folder_id` / `previous_folder_name` | project | Set when a project is archived from a folder. Enables "Restore to Acme Corp?" instead of silent placement at root on un-archive |

**Design rules:**

1. **One level only** — folders contain projects, not other folders. This is a deliberate constraint: deeper nesting adds complexity without matching how research is actually organised
2. **Optional** — `folder_id: null` means the project sits at the root. Researchers who only run a few studies never need folders
3. **Desktop app only** — folders are a UI/index concept, not a filesystem concept. The project folder on disk can live anywhere; the "folder" in Bristlenose is just a label for grouping. Researchers will assume Bristlenose folders map to Finder folders — the desktop app should make this distinction visible on first use (brief onboarding tooltip: "Bristlenose folders are labels for grouping, not folders on your disk")
4. **Drag-and-drop** — projects can be dragged between folders and to/from the root in the desktop home screen. Keyboard equivalent via context menu: right-click a project → "Move to…" submenu with folder list + "Root" option
5. **Folder-level actions** — archive all projects in a folder, expand/collapse in the home screen
6. **Cross-project queries respect folders** — "all quotes tagged [trust] in Acme Corp projects" is a natural filter once folders exist

**CLI:** `bristlenose projects` could optionally show folder grouping (`bristlenose projects --group`), but this is low priority. The CLI is project-at-a-time; folders matter most in the desktop app's home screen where you're browsing visually.

### Home screen UX — the freelancer who moves around

The primary persona is a freelance researcher with 3–5 clients, projects scattered across local SSD, client SharePoint, external drives, and a home NAS. At any given moment, only some volumes are mounted. The home screen must work when 60% of projects are greyed out.

**Project search** — a search bar at the top of the home screen for finding projects by name, folder, or location hint. Typing "mobile" surfaces "Mobile Banking Pilot" whether it's active, archived, or on an unmounted drive. Keyboard-accessible via Cmd+K or just start typing with window focus. This is navigation search (finding a project to open), not content search — folder-scoped content search (quotes, tags) is a separate feature (see §3b).

**No view toggles.** The home screen shows all projects, always. Grey means "not here right now", with the smallest possible hint about what to do ("Plug in Samsung T7", "Connect to Acme Corp VPN"). No available/unavailable toggle, no filtering modes — the researcher just wants a list of her stuff. The app should not be needy about offering helpful slicing when a simple grey state communicates everything.

**Folder collapse persistence** — `collapsed: true/false` in the index, persisted across launches. A freelancer at a client site collapses the other client folders, and they stay collapsed next time she opens the app.

**New project creation** — the desktop app's drag target should accept **individual files** (not just folders). Dragging 12 .mp4 files onto the window offers to create a project folder: "Create a new project from these 12 files? Name: [___] Location: [~/Research/]". This removes Finder as a prerequisite step. The folder picker defaults to the parent directory of the most recently created project (researchers tend to keep projects for the same period in the same area). After creating, offer to assign to a folder: "Add to folder: [Acme Corp ▾] [New folder…] [No folder]".

**Read-only volume handling** — if a project's target directory is on a read-only volume (USB stick, write-protected drive), the FolderValidator checks write permissions before enabling "Analyse". If read-only, show: "This folder is on a read-only drive. Copy it to your Mac first, or choose a different output location with --output." Better yet, offer a one-click "Copy to Desktop and analyse" action.

**Concurrent serve sessions** — a freelancer switching between clients mid-day may want both projects open in different browser tabs. The desktop app should support running serve for two different projects simultaneously (different ports). If not feasible, document the limitation and the workflow (close one, open the other).

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
  person_a_id     TEXT NOT NULL     -- UUID, globally unique across all project DBs
  person_b_id     TEXT NOT NULL     -- UUID
  folder_id       TEXT              -- folder context in which the link was created
  link_type       TEXT  -- 'same' | 'not_same'
  created_at      DATETIME
  created_by      TEXT  -- 'researcher' (manual), 'suggestion' (auto-proposed)
  UNIQUE(person_a_id, person_b_id)
```

**Person IDs must be UUIDs, not auto-increment integers.** This is a design-time decision, not a deferral. Person IDs in `person_links` reference rows across separate per-project SQLite databases. Auto-increment integers are not globally unique — project A and project B can both have Person ID 7 (different people). A bug in the mapping layer would silently link wrong people. UUIDs eliminate this entire class of cross-DB reference bugs. The cost of adding UUIDs now is near-zero; retrofitting after `person_links` rows exist requires a migration touching every row.

- **`same`**: "Person 7 and Person 12 are the same individual." Queries can union their data
- **`not_same`**: "Person 7 and Person 15 are NOT the same person despite sharing a name." Prevents re-suggesting the match
- **Transitivity**: if A=B and B=C, then A=C. The linking UI must show the full chain when any link is created or broken: "Linking A to B will also link A to C (because B and C are already linked). Confirm?" And conversely: "Unlinking A from B will also unlink A from C. Confirm?" Breaking one link in a chain has cascading effects — the researcher needs a before/after preview, not a silent cascade. **Cross-folder transitivity must be flagged:** if A is in "Acme Corp" and C is in "Beta Inc", the confirmation must say: "This link chain spans Acme Corp and Beta Inc projects." Refuse transitive links that cross folder boundaries unless the researcher explicitly acknowledges it
- **Canonical person**: when persons are linked, the one with the most data (sessions, quotes, filled fields) becomes the display representative. No data is deleted — the link just changes how they're presented. **The canonical choice must be researcher-overridable** — auto-selecting by data volume may pick "Sarah" (8 sessions) over "Dr. Sarah Chen" (2 sessions), losing the professional title. Auto-suggest the canonical based on data volume, but let the researcher override with one click
- **Export isolation**: when exporting from project A, never include linked data from project B. Export is always project-scoped regardless of person links

### Where this table lives

Currently each project has its own SQLite file (`<output_dir>/.bristlenose/bristlenose.db`). Person links are cross-project by definition, so they belong in a **shared instance database** — the same `~/.config/bristlenose/bristlenose.db` that `_default_db_url()` in `db.py` already points to.

This means the architecture becomes:
- **Per-project DB**: quotes, sessions, clusters, themes, researcher state — everything project-scoped
- **Instance DB**: person links, negative links, future app-wide settings

The desktop app manages the instance DB. CLI single-project mode doesn't need it (person linking is a multi-project feature).

### Suggestion algorithm (future)

When a new project is imported into a folder, scan existing Person rows **across project DBs within the same folder** for:
- Exact name match (full_name or short_name)
- Similar name (Levenshtein ≤ 2)
- Same email (if ever added to Person)

The scan is folder-scoped — never cross-folder (see §3c, Finding 1). Projects at root (no folder) receive no suggestions.

Present matches as suggestions with a "Link" / "Not the same" action. Store the researcher's decision in `person_links`.

---

## 3. Project Lifecycle — Active → Archived → Reopened

### States

| State | Serve mode | Desktop home screen | CLI `bristlenose projects` |
|-------|-----------|--------------------|----|
| **Active** | Works normally | Full card, recent activity | Listed with path |
| **Unavailable** | Clear message naming the volume/location | Greyed out, location hint shown | Listed with `[unavailable: volume]` marker |
| **Archived** | Works if path exists | Greyed, collapsed archive section | Listed with `[archived]` marker |

### Unavailable projects (volumes that come and go)

> **Status (`current`):** `Project.availability` enum (`ProjectIndex.swift:132-145`) + `VolumeWatcher.swift` shipped. Volume mount/unmount tracking, availability re-computation, "Plug in [volume]" UX live (26 Apr 2026, `port-v01-ingestion`). Mid-session SQLite-relocation discussion further down stays `pending` — DB still lives at `<output_dir>/.bristlenose/bristlenose.db`.



Researchers work across multiple storage locations: local SSD, a SharePoint at a client site, an external drive, a NAS at home. At any given moment, half the projects in the index may be on a volume that isn't mounted. This is **normal, not an error**.

The project index stores enough information to tell the researcher *where* the project lives and *how to get it back*:

```json
{
  "id": "uuid-3",
  "name": "Mobile Banking Pilot",
  "path": "/Volumes/Research NAS/mobile-banking",
  "location": {
    "type": "volume",
    "volume_name": "Research NAS",
    "display_hint": "Network drive — Research NAS"
  },
  "folder_id": "uuid-f2",
  "last_opened": "2026-02-28T16:00:00Z",
  "created_at": "2026-01-15T10:00:00Z",
  "archived": false
}
```

**`location` field** — populated automatically when a project is first added to the index, by inspecting the path:

| `type` | Detection | `display_hint` example |
|--------|-----------|----------------------|
| `local` | Path under `/Users/` or home dir | "On this Mac" |
| `volume` | Path under `/Volumes/` | "External drive — Samsung T7" |
| `network` | SMB/AFP mount or `/Volumes/` with network filesystem | "Network drive — Research NAS" |
| `cloud` | Path under known cloud sync dirs (OneDrive, Dropbox, iCloud) | "SharePoint — Acme Corp" |

**Desktop home screen behaviour:**

- **Available projects**: full card, normal interaction
- **Unavailable projects**: greyed out, with the `display_hint` shown as a subtitle (e.g. "External drive — Samsung T7"). Not hidden, not alarming — just obviously not accessible right now. Clicking shows a message: "Connect [volume name] to open this project"
- **Relocated projects**: if the path doesn't exist but the volume is mounted, the project was moved or deleted. This is the actual error case — show a "Locate…" button to re-point the index entry

This means the home screen naturally reflects the researcher's storage reality: local projects are always there, client SharePoint projects appear when connected to the VPN, the NAS projects appear when at home. No manual state management needed — the desktop app checks path existence on launch and on volume mount/unmount events (macOS `NSWorkspace.didMountNotification`).

**Cloud storage nuance (SharePoint, OneDrive, Dropbox, iCloud):** macOS creates placeholder directories for cloud-synced folders even when the actual files are evicted (not downloaded locally). A project path may *exist* while the content is cloud-only. For `location.type = "cloud"`, do not rely solely on path existence — check whether at least one file inside the project directory is actually available (not a placeholder). macOS extended attributes (`com.apple.ubiquity.isEvicted`) or a simple "can I read `metadata.json`?" check prevents false positives. Display "Syncing…" rather than "Available" when the directory exists but content is not yet local.

**Volume mount transition:** when an external drive or NAS is plugged in / mounted, run the path-existence check asynchronously (off the main thread). Show a brief "reconnecting…" state on affected cards (subtle pulse on the location hint text). Transition from greyed-out to full-colour with a 200ms fade. The plug-in moment should feel responsive and intentional, not a janky jump. Total transition time ≤ 300ms from the user's perspective.

**Volume-relative path for auto-resolution:** the `location.volume_relative_path` field (e.g. `Research/onboarding-pilot`) enables automatic reconnection when a volume mounts with a slightly different name — macOS appends a number if two volumes share a name (`Samsung T7` vs `Samsung T7 1`). When a volume mounts and a project's stored `volume_name` doesn't match exactly, try resolving `volume_relative_path` against the mounted volume. This handles the common case of external drives after a laptop swap or dual-boot scenario.

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

### Mid-session disconnect (VPN drop, drive eject)

A researcher is working on a SharePoint project and the VPN drops, or she's on an external drive and it's ejected. The project directory becomes inaccessible while serve mode is running.

**Failure modes without mitigation:**
- **SQLite on the remote volume**: WAL corruption possible if the filesystem disappears mid-write
- **API requests for media files**: video/audio playback fails silently or with broken player state
- **In-progress pipeline operations**: any running operation crashes

**Design:**

1. **SQLite DB lives locally** — store the per-project SQLite in `~/Library/Application Support/Bristlenose/projects/<project-id>/bristlenose.db` rather than on the remote volume. The DB is a materialised view of the JSON anyway (rebuilt on import), so the worst case on disconnect is stale data rather than corruption. The JSON source files remain on the remote volume
2. **Volume unmount detection** — the desktop app listens for `NSWorkspace.didUnmountNotification`. If the current project's volume disappears, show a modal: "Connection to [Samsung T7 / Acme Corp SharePoint] was lost. Your work is safe — Bristlenose doesn't modify source files. Reconnect to continue, or close this project."
3. **Graceful API degradation** — serve mode handles filesystem errors on read with 503 + human-readable message ("Project files are temporarily unavailable") rather than a Python traceback
4. **Reconnection** — when the volume remounts, the app detects it via `didMountNotification`, re-checks the project path, and resumes normally. No manual action needed if the volume mounts at the same path

This means a brief VPN blip is a non-event: the SQLite DB is local, the browser shows a temporary "unavailable" state, and everything resumes when the connection returns.

### Laptop swap (Migration Assistant)

A researcher gets a new MacBook and migrates via Migration Assistant. `~/Library/Application Support/Bristlenose/projects.json` transfers along with local projects. But:

- External volumes may mount with different names (`Samsung T7` → `Samsung T7 1`)
- Cloud storage paths may include the user's email (`/Users/cassio/Library/CloudStorage/OneDrive-cassio@acme.com/`)
- The username itself might change (`/Users/cassio/` → `/Users/c.santos/`)

**Batch relocate wizard:** when the app detects multiple broken paths on first launch (likely after migration), instead of showing individual "Locate…" buttons on 8 different cards, offer a single "Some projects have moved. Let's find them." wizard that:

1. Groups broken paths by former volume/location
2. Asks "Where is [Samsung T7] now?" once per volume rather than once per project
3. Updates all paths for that volume in one action

This transforms an N-project problem into an M-volume problem (where M ≪ N). The `volume_relative_path` field enables auto-resolution for the common case of slightly different volume names.

---

## 3a. Archive — Phase 2 Feature

> **Not phase 1.** We don't have enough users with enough old projects to justify building this yet. The thinking is here so we don't paint ourselves into a corner. The schema fields (`archived`, `previous_folder_id`, `previous_folder_name`) are cheap to include from the start.

Archiving is a UI-only action — it sets `archived: true` in the project index. No files are moved or deleted. The project folder stays where it is. Archiving means "I'm done with this study for now" — it reduces clutter in the home screen.

**Two archive patterns:**

1. **Archive a project** — individual project moves to a flat "Archive" section at the bottom of the home screen. This is the junk drawer: finished studies, one-off pilots, anything you're done with but might revisit. No folder structure in the archive — it's deliberately flat to avoid organising things you're not actively working on
2. **Archive a folder** — when a client leaves or a product is discontinued, archive the whole folder. All projects inside move to the archive section. The folder disappears from the active view. In the archive section, projects show their former folder name as a label ("was: Acme Corp") so you can still find them by client

Archiving a folder does not prevent individual projects from being un-archived back into an active folder. The operations are independent: archive-folder is a batch convenience, not a permanent grouping.

**Archive confirmation:** when archiving a folder, show: "Archive Acme Corp? Your 3 projects stay where they are on disk. They'll move to the Archive section and you can restore them any time." The word "restore" signals reversibility. After archiving, show a toast with an "Undo" action (10-second window).

**Un-archiving with folder restore:** when archiving from a folder, `previous_folder_id` and `previous_folder_name` are stored on each project. When un-archiving, offer: "Restore to Acme Corp?" — recreates the folder if it no longer exists. Without this, un-archived projects silently land at root and the researcher has to manually recreate the folder and drag each project in.

**Archive search and filter:** the flat archive is the right default, but it needs search/filter once it exceeds ~8 items. A freelancer who archives 3 client folders over 2 years could have 30+ archived projects. Sort by: last opened (default), date archived, name, former folder. Filter by: former folder name as clickable chip filters ("was: Acme Corp" label becomes a filter). The global search bar (see §1 Home screen UX) also covers the archive.

---

## 3b. Cross-Project Search — Folder-Scoped

> **Potentially more important than archive.** Even with a handful of projects, researchers ask "where did I see that quote about trust?" Cross-project search has immediate value from the moment someone has 2 projects for the same client.

### The right search boundaries

The meaningful search scopes are **project** (already exists) and **folder**. Not global.

A folder represents a client or product — the projects inside it share a user base and a research context. Searching across "Acme Corp" folder for quotes about "onboarding" is a natural query: you're looking for patterns across studies for the same client. Searching across *all* projects (Acme Corp + Beta Inc + personal experiments) is nonsensical — those user bases have nothing in common.

By adding multiple projects to a folder, the researcher implicitly declares "these belong together." That declaration is what makes cross-folder search meaningful.

| Scope | Query example | When it makes sense |
|-------|--------------|-------------------|
| **Project** | "All quotes about trust in Q1 Usability" | Always — this is existing in-project search |
| **Folder** | "All quotes about onboarding across Acme Corp studies" | When a client has multiple studies and you want patterns |
| **Global** | Not supported | Searching across unrelated clients has no research value |

### What's searchable (within a folder)

- Quote text (full-text search across projects in the folder)
- Tag names (which projects have quotes tagged [trust]?)
- Participant names (which projects did "Sarah" appear in?)
- Session names / filenames

**Results show provenance:** every result includes the project name and availability status. "Found in: Mobile Banking Pilot — External drive — Samsung T7 [unavailable]". The researcher knows where the result lives even if she can't open it right now.

### Implementation path

1. **CLI** — `bristlenose search "onboarding" --folder "Acme Corp"` searches projects in that folder. Simple, no UI needed
2. **Desktop app** — folder-level search bar within the folder view. Or a search scope picker: "Search in: [Acme Corp ▾]"
3. **Serve mode** — when multi-project serve ships, search becomes an API: `GET /api/folders/{id}/search?q=onboarding`

### Constraints

- Only searches projects whose DB is available (volume mounted). Unavailable projects noted in results: "2 projects on unmounted volumes were not searched"
- No central search index — each query hits per-project SQLite databases within the folder. Fine for ≤20 projects per folder
- Quote text search uses SQLite FTS5 (already available in the per-project schema for in-project search)

---

## 3c. Security & Privacy Review

> **Two independent security reviews were conducted against this design** — a Bristlenose-specific review (attacker/blocker/defender personas) and a standard security/privacy/compliance review. This section synthesises the consensus findings. Both reviews agreed on the same top priorities, which strengthens confidence in the recommendations.

### Threat model: the freelancer with competing clients

The primary threat is **accidental cross-client data leakage**. A freelance researcher working for Acme Corp and Beta Inc has both clients' participant data on one machine. Every cross-project feature (person linking, search, folder grouping, suggestion algorithm) is a potential leakage vector. The design must treat folders as **adversarial trust boundaries between competing clients**, not just filing categories.

Secondary threats: laptop theft/seizure exposing the client roster, managed-device MDM agents harvesting metadata, re-identification of anonymised participants via cross-project links, and GDPR erasure obligations across linked identities.

### Finding 1: Folder is the trust boundary — cross-folder linking is out of scope

**Severity: CRITICAL** (both reviews)

Both reviews flagged cross-folder person links as the highest-risk feature. But the right response isn't a complex override mechanism — it's **not building cross-folder linking at all** in this phase.

**The folder contract:** by putting projects in the same folder, the researcher declares "these belong together." Within a folder, cross-project linking and search are legitimate — the researcher chose to group them. A folder might be a client (Acme Corp), or it might be a product (Photoshop vs Illustrator studies for the same Adobe engagement). The researcher knows the relationship; the tool trusts the grouping.

**Design constraint:** Person linking, cross-project search, and the suggestion algorithm are **folder-scoped only**. No cross-folder operations exist. Transitive chains cannot span folder boundaries — if A and B are in the same folder and B and C are in different folders, linking A to B does not create any relationship with C. Cross-folder linking is a different problem with different trust assumptions, deferred to a future design iteration.

This is simpler and safer than an override mechanism. The folder boundary is the confidentiality boundary. Period.

### Finding 2: Instance DB encryption

**Severity: CRITICAL** (both reviews)

The instance DB (`~/.config/bristlenose/bristlenose.db`) containing `person_links` is the single point where cross-project identity mingles. An unencrypted SQLite file in a well-known location is trivially readable by any process with home-directory access — MDM agents, backup tools, malware, or a curious IT admin imaging the machine.

**Design constraint:** Encrypt the instance DB at rest. Options: SQLCipher (transparent encryption layer for SQLite) or application-level encryption with a key derived from the macOS Keychain / Linux Secret Service. The Keychain pattern is already established for API key storage. The instance DB has a **higher sensitivity classification** than any individual project DB — it's the cross-client correlation store.

**Consider folder-scoped storage:** an alternative to a single instance DB is per-folder link storage (one `links.db` per folder). This reduces blast radius — compromising one folder's links reveals nothing about other clients. Trade-off: cross-folder links (when enabled) need a coordination mechanism.

### Finding 3: Project index is a client roster

**Severity: HIGH** (both reviews)

`projects.json` contains project names, folder names (= client names), filesystem paths (may include client names, SharePoint tenant names), volume names, and timestamps. Even without accessing project data, this file maps out the researcher's entire client portfolio, project cadence, and storage infrastructure.

**Risk amplifiers:**
- **Cloud sync** — if `~/Library/Application Support/Bristlenose/` is within a synced directory (iCloud, Dropbox), the index propagates to the cloud
- **Managed devices** — MDM agents (Jamf, Kandji, Intune) routinely backup `~/Library/Application Support/` to the company's cloud. A researcher on Client A's managed laptop has Client B and Client C names backed up to Client A's infrastructure
- **Dotfile managers** — the CLI path (`~/.config/bristlenose/projects.json`) is commonly synced by chezmoi, yadm, etc.
- **Time Machine** — the index is backed up with full history, so even deleted/archived projects are recoverable

**Design constraints:**
1. Document in `SECURITY.md` that `projects.json` and the instance DB contain metadata about all projects and should be treated as confidential
2. Consider encrypting the index at rest using the same Keychain-derived key as the instance DB
3. Add a `--no-index` flag for paranoid users who don't want cross-project memory
4. Store in `~/Library/Application Support/` (macOS, not synced by iCloud by default) rather than `~/.config/` for the desktop app path
5. Allow **display aliases** on folders — a folder internally named "Acme Corp" could display as "Client A" during presentations. This also enables a **focus mode**: show only the selected folder's projects during screen-shares, hiding other client folders entirely

### Finding 4: `bristlenose forget` — right to erasure

**Severity: HIGH** (both reviews)

Under GDPR Article 17, a research participant can request erasure. Today this is straightforward: delete from the project directory. Person links in the instance DB create a second location where identity persists — a researcher following `SECURITY.md`'s advice to "delete the project folder" would miss it entirely.

**Design constraint:** Ship a `bristlenose forget <speaker-code> --project <path>` command that:
1. Deletes Person rows from the per-project DB
2. Deletes all `person_links` rows referencing that person's UUID from the instance DB
3. Purges quotes attributed to that speaker code
4. Breaks transitive chains: if A=B=C and B is deleted, the A=C link is also removed (safer default — don't silently preserve chains with a missing middle)
5. Produces an audit receipt (JSON: what was deleted, when, from which databases)
6. Document this in `SECURITY.md`

### Finding 5: Cross-project search must not leak participant names

**Severity: HIGH** (both reviews)

Section 3b proposes searching "Participant names (which projects did 'Sarah' appear in?)" across a folder. A participant who consented to Study A may not have consented to Study B. Casually surfacing cross-study participation patterns violates consent boundaries.

**Design constraint:** Cross-project people search uses **speaker codes by default**, not display names. Full-name search requires explicit opt-in with a warning: "This search reveals participant names across projects. Ensure all participants have consented to cross-study identification." Alternatively, limit cross-project people search to already-linked persons only.

**Search result provenance** must be visually impossible to miss — project name prominently on every result row, not just fine print.

### Finding 6: Person linking weakens anonymisation

**Severity: HIGH** (both reviews)

Person linking creates a back-channel from anonymised speaker codes to named identities via a different project. If Project A is exported anonymised (participant = "p3") but the cross-project People tab shows "p3 in Project A = Sarah Chen in Project B", anyone with access to both views can de-anonymise.

**Design constraints:**
1. Export must strip all person link references — the export artifact is self-contained with no breadcrumbs back to linked identities
2. The cross-project People tab must respect per-project anonymisation settings. If Project A has anonymisation enabled, show "p3 (Project A)" not "Sarah Chen (Project A)" even in cross-project views
3. When a researcher opens a single project for client work, linked-person data from other projects must be invisible. Cross-project views are only accessible from the home screen / project library, never from within an open project's UI
4. Document this re-identification risk explicitly — researchers under IRB/ethics board approval need to understand that person linking fundamentally weakens anonymisation guarantees

### Finding 7: Resolve UUID contradiction

**Severity: HIGH** (both reviews)

Section 2 states "Person IDs must be UUIDs, not auto-increment integers" and calls it "a design-time decision, not a deferral." The Appendix contradicts this: "This is a decision to make when building the linking feature, not now."

**Resolution:** Section 2 is correct. UUIDs are required. Auto-increment integers across separate SQLite databases would silently link wrong people — a data integrity bug with direct privacy consequences. The Appendix hedging language is removed.

### Finding 8: Suggestion algorithm must be folder-scoped

**Severity: MEDIUM** (both reviews)

The suggestion algorithm (§2) proposes scanning "existing Person rows across all project DBs" on import. Importing a personal side-project would trigger a scan of all client databases, surfacing participant names from Client A in the context of Client B.

**Design constraint:** Scope the suggestion algorithm to the same folder. Cross-folder suggestions require explicit opt-in: "Also check other clients' projects for matches?" If declined, no cross-folder scan occurs and no `not_same` links are created.

### Finding 9: Concurrent serve CORS

**Severity: MEDIUM** (both reviews)

If concurrent serve sessions run on different ports, a browser extension or XSS vulnerability on one project's page could make fetch requests to the other project's localhost port.

**Design constraint:** Each serve instance must set strict CORS: `Access-Control-Allow-Origin` must be the exact origin (including port), not `*` or `localhost`. Add a test that verifies no permissive CORS headers are returned. Current behaviour (no CORS middleware, 127.0.0.1 binding) is correct — document it as a constraint that must be maintained.

### Finding 10: Export isolation integration test

**Severity: MEDIUM** (both reviews)

The "export is always project-scoped" promise (§2) is currently enforced by per-project DB isolation. In multi-project serve mode with instance-scoped tables (Person, CodebookGroup, TagDefinition), the export must be re-verified.

**Design constraint:** Before multi-project serve ships, add a CI-gated integration test that loads two projects and verifies Project A export contains zero data from Project B. This test covers Person rows, codebook groups, tag definitions, and any other instance-scoped data.

### Additional findings (individual reviews)

| Finding | Source | Severity | Recommendation |
|---------|--------|----------|----------------|
| `not_same` links are a negative knowledge store | Standard review | Medium | Two people with the same name across projects — even a negative link reveals they exist. Mitigated by instance DB encryption. Consider bloom filter approach |
| No data sensitivity classification | Bristlenose review | Medium | Optional `sensitivity` field on projects (standard/sensitive/special_category). Sensitive projects cannot participate in cross-project linking or search |
| DPIA prompt for person linking | Bristlenose review | Medium | One-time notice when linking is first used: "Cross-project person linking tracks participant identity across studies. Your organisation may require a DPIA." |
| Person link audit log | Standard review | Medium | `person_link_events` table: `(event_id, person_a_id, person_b_id, action, timestamp, reason)`. Cheap now, required for ethics compliance |
| `created_by_user` on person_links | Bristlenose review | Low | Nullable text column, defaults to null for local use. Populate with user ID when RBAC ships |
| Folder membership confirmation | Standard review | Low | When adding a project to a folder: "Projects in a folder can appear in cross-project search results for this folder" |
| Volume path reveals storage infrastructure | Standard review | Low | Allow researcher to edit `display_hint` values. Sanitise cloud tenant identifiers |
| Volume-relative path collision | Bristlenose review | Low | After auto-resolution, verify `metadata.json` project ID before connecting |
| RBAC admin escalation via folder moves | Standard review | Low | Moving project out of shared folder must warn about access removal (future SaaS only) |

### What's already strong

Both reviews acknowledged these design decisions as correct:
- **Per-project SQLite isolation** — physically separate databases, not multi-tenant
- **No auto-merge** for person identity — human-driven linking only
- **Export isolation promise** — project-scoped by design
- **Localhost binding** (127.0.0.1) — no 0.0.0.0
- **No CORS middleware** — safe by default
- **`apiBase()` abstraction** — already parameterised for multi-project
- **`SessionSpeaker` join pattern** — Person queries scoped through joins, not direct table reads
- **Ollama option** — available for fully local processing when needed (though most production use requires a network LLM for credible performance)

### Trust-centre talking points this design enables

- "Each project is a separate SQLite database. There is no multi-tenant risk — your data is physically isolated."
- "Cross-project features (person linking, search) are opt-in. By default, projects are islands."
- "Cross-client data flow is blocked by default. Folders are confidentiality boundaries."
- "Export is always project-scoped. Linked person data from other projects never appears in exports."
- "LLM calls send transcript content to the configured provider (Claude, ChatGPT, etc.), but project metadata, person links, and the project index never leave the machine. The Ollama option exists for users who need fully local processing, but most production use requires a network LLM."

### Trust-centre talking points weakened if findings are not addressed

- "Data never leaves the project directory" — becomes false when `person_links` live in the instance DB and `projects.json` stores client names
- "Delete the project folder and it's gone" — becomes false when cross-project identity state persists in the instance DB

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
| Project archive/restore | Desktop app feature — not enough users with old projects yet | Index schema `archived` field (§1), re-open path (§3), archive section UX (§3a) |
| Profile → moderator connection | UX research needed | Person linking is general-purpose, not moderator-specific |
| `bristlenose projects` CLI command | Low priority vs. desktop | Index file location (§1) |
| Multi-project serve mode | Architectural work (multiple DB connections, project switching API) | Per-project DB isolation, `apiBase()` abstraction |
| Person suggestion algorithm | Needs linking UI first | `person_links.link_type = 'not_same'` for negative links |
| Shared codebook across projects | `CodebookGroup` is already instance-scoped | `ProjectCodebookGroup` join table already exists |
| Folder-level RBAC | SaaS-only, no multi-user yet | Folder as permission boundary (§1) |
| Batch relocate wizard | Needs real users hitting laptop swap | `volume_relative_path` field, per-volume resolution (§3) |
| Concurrent serve sessions | Needs desktop app port management | Different ports per project, or explicit single-session model |
| File-drag project creation | v0.2 desktop app | FolderValidator, write-permission check (§1 Home screen UX) |

The current architecture supports all of these without schema migration. The work is in the server (loading multiple projects), the frontend (project context in React Router), and the desktop app (project list, switching, linking UI).

### SaaS future: RBAC and folder ownership

In a hosted/team SaaS world, folders become the natural **permission boundary**. Ownership and access control attach to folders, not individual projects:

- **Folder owner** — the user or team that created it. Can add/remove projects, invite collaborators, archive
- **Folder-level roles** — viewer (read-only), editor (tag/annotate), admin (manage members, archive). Projects inherit their folder's permissions
- **Root-level projects** — projects outside any folder default to the creating user's private workspace
- **Cross-folder visibility** — cross-project search and person linking respect folder permissions. You can't link a person from a folder you can't see

This is far future — local-first desktop app has no multi-user concept. But the folder data model (flat, one level, `folder_id` on projects) is the right foundation. When RBAC arrives, add `owner_id` and a `folder_members` join table to the index — no structural redesign needed.

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

The instance DB stores only cross-project relationships. Person IDs in `person_links` reference rows in project-specific DBs using **UUIDs** (not auto-increment integers) — see §2 for rationale. UUIDs make Person IDs globally unique across all project databases, eliminating the class of bugs where auto-increment IDs from different databases collide silently.

### Migration path

No migration needed for existing projects. The instance DB is created when the desktop app first launches (or when `bristlenose projects` is first run). Existing per-project DBs continue to work unchanged.
