# Milestone 1 — Sessions Table as React Island

## What we're building

Replace the Jinja2-rendered sessions table with a React component that fetches data from a FastAPI endpoint. At the end of this milestone, `bristlenose serve ./project` opens a browser where the sessions tab renders via React, hitting a real API, with full visual parity.

## Current state (milestone 0)

- FastAPI serves the static HTML report at `/report/`
- SQLite database exists with a single `projects` table
- React + Vite tooling works — `HelloIsland` fetches `/api/health` and renders
- Pipeline writes intermediate JSON (`screen_clusters.json`, `theme_groups.json`, `metadata.json`) to `.bristlenose/intermediate/`
- `_build_session_rows()` in `render_html.py` already produces structured dicts with all the session table data

---

## Decision 1: Domain model — what are the first-class citizens?

The database should model the world of user research, not the needs of this week's UI. If we get the entities right, the API endpoints and React components follow naturally. If we get them wrong, every milestone fights the schema.

Here's an inventory of every concept in Bristlenose, grouped by whether it's already a named entity in the codebase, or exists implicitly but isn't modelled.

### Already named (Pydantic models or dataclasses)

| Concept | Current type | Stored where |
|---|---|---|
| Project/Study | `project_name: str` on PipelineResult | `metadata.json` |
| Session | `InputSession` | In-memory only |
| Input file | `InputFile` | In-memory only |
| Person | `PersonEntry` (computed + editable) | `people.yaml` |
| Speaker role | `SpeakerRole` enum | On transcript segments |
| Transcript | `FullTranscript` | `.txt` files |
| Transcript segment | `TranscriptSegment` | Inside FullTranscript |
| Word (with timing) | `Word` | Inside TranscriptSegment |
| Topic boundary | `TopicBoundary` | `topic_boundaries.json` |
| Quote | `ExtractedQuote` | `extracted_quotes.json` |
| Sentiment | `Sentiment` enum (7 values) | Field on ExtractedQuote |
| Screen cluster | `ScreenCluster` | `screen_clusters.json` |
| Theme group | `ThemeGroup` | `theme_groups.json` |
| Signal | `Signal` dataclass | Ephemeral (analysis module) |
| Matrix / MatrixCell | Dataclasses | Ephemeral |
| Coverage stats | `CoverageStats` | Ephemeral |

### Exists but not named as its own entity

These are real things in the research world that the codebase uses but hasn't given first-class status:

**Speaker code** — `"p1"`, `"m1"`, `"o1"`. Currently a string field scattered across transcript segments and `people.yaml` keys. In reality, a speaker code is the join between a person and a session — it's how this person appeared in this session, with this role. It's the linchpin for Phase 2 cross-session moderator linking (`m1` in session 1 = `m1` in session 3). Not modelled as its own entity.

**User journey** — a per-participant ordered list of screens visited, derived at render time by `_derive_journeys()` from screen clusters. In domain terms, a journey is a first-class concept: "participant p1 went Dashboard → Search → Product Detail". It's currently computed on-the-fly and thrown away. Worth storing if we ever want to query "which participants visited this screen?" or "what's the most common path?".

**Codebook** — the researcher's tag taxonomy. Groups of tags, each with a name, description, and colour set. Currently client-side only (localStorage). In domain terms, a codebook is the researcher's analytical framework — it's how they're making sense of the data. It's as important as the pipeline's output.

**Codebook group** — a named category within the codebook (e.g. "Friction", "Trust issues"). Organises tags. Has an order, a colour set, a subtitle/description.

**User tag** — a free-text label the researcher applies to a quote. Many-per-quote, distinct from the AI-assigned sentiment. Currently localStorage only. In domain terms, this is the researcher's annotation layer — their manual coding. It's the primary user-generated data.

**Tag-group assignment** — which tag belongs to which codebook group. Currently a nested object in the codebook localStorage blob.

**Quote state: hidden** — "volume quote" the researcher wants to suppress. Boolean per quote, currently localStorage. In domain terms, this is an analytical decision: "this quote is evidence, but it's not worth showing in the final report."

**Quote state: starred** — "notable quote" flagged by the researcher. Boolean per quote, currently localStorage. In domain terms, this is the inverse of hidden: "this quote is particularly important."

**Quote text edit** — researcher-corrected transcription text. Per quote, currently localStorage. In domain terms, this preserves a chain: original speech → editorial cleanup → researcher correction.

**Heading edit** — researcher-renamed section or theme title/description. Currently localStorage. In domain terms, the researcher is disagreeing with the AI's labelling — a meaningful analytical act.

**Deleted AI badge** — the researcher removed the AI-assigned sentiment from a quote. Currently localStorage. In domain terms, this is the researcher overriding the AI's analytical judgment.

**Friction point** — a quote with negative sentiment. Currently a render-time filter, not stored. In domain terms, friction points are a key deliverable of user research — "where did users struggle?" They emerge from the data but could be a named view.

**Featured quote** — a high-signal quote selected for the dashboard. Currently computed at render time by a scoring function. In domain terms, featured quotes are the researcher's "headline findings" — the quotes you'd put on slide 1.

**Persona** — an archetype label on a person. A string field on `PersonEditable`. Currently unused in pipeline logic or rendering. In domain terms, personas are a standard UX research output: "Power User", "Cautious Beginner", "Mobile-First".

**Display name** — the human-readable name for a participant. Currently resolved at render time from `short_name` with fallback. In domain terms, display names are an editorial decision about anonymisation.

**Intensity** — 1-3 scale on every quote, stored but not surfaced in the UI. In domain terms, intensity matters: "confused" vs "completely lost" is a different severity. The analysis module uses it for composite signal scoring.

### Proposed domain model

The key insight: not everything belongs to a project. Some things belong to the researcher and span projects. Getting this boundary right now avoids painful migrations later.

**Instance-scoped** (no `project_id`) — things that belong to this Bristlenose installation:
- People (a person exists in the world; their *appearance in a session* is project-scoped)
- Codebook groups (a shared library of reusable analytical categories)
- Tag definitions (the tags within a group)

**Project-scoped** (has `project_id`) — things born from a specific pipeline run:
- Sessions, source files, transcripts, topic boundaries
- Quotes, clusters, themes, signals
- Quote states (hidden, starred, edited), heading edits, deleted badges
- The join tables that connect researcher-scoped things to project data (which codebook groups are active, which tags are applied to which quotes)

**Why this split matters:**
- A longitudinal study reuses the same codebook groups to compare wave 1 vs wave 2
- A researcher grabs their "Friction" and "Trust" groups from a previous study but not the rest
- The same moderator appears across multiple projects — today they're separate person records, but the schema allows merging them later via `session_speaker.person_id`
- Two different "Jim Smith" participants stay as two person rows until a human explicitly links them

**Future: multi-researcher, access control.** Today Bristlenose is one researcher on one laptop, so instance-scoped and researcher-scoped feel identical. In a team setting, codebook groups become a shared library — multiple researchers pull from it, but not everyone should see everything (e.g. groups revealing secret client concerns about an unannounced feature). This is a permissions layer on top of the data model, not a change to the data model. We don't need `user`, `team`, or `owned_by` today. The schema just needs groups to not be welded to a single project or researcher — which it isn't.

```
── INSTANCE-SCOPED (no project_id) ───────────────────────

person
  id, full_name, short_name, role_title, persona, notes,
  created_at

codebook_group  (the reusable unit — not the whole codebook)
  id, name, subtitle, colour_set, sort_order, created_at

tag_definition  (belongs to its group)
  id, codebook_group_id, name

── PROJECT-SCOPED ─────────────────────────────────────────

project
  id, name, slug, input_dir, output_dir,
  created_at, imported_at

project_codebook_group  (which groups are active in this project)
  id, project_id, codebook_group_id, sort_order

── THE RAW MATERIAL ───────────────────────────────────────

session
  id, project_id, session_id, session_number,
  session_date, duration_seconds, has_media, has_video

source_file
  id, session_id, file_type, path, size_bytes,
  duration_seconds, created_at, verified_at

session_speaker  (the join — "this person in this session")
  id, session_id, person_id, speaker_code, speaker_role,
  words_spoken, pct_words, pct_time_speaking, source_file

transcript_segment
  id, session_id, speaker_code, start_time, end_time,
  text, source

── THE AI'S ANALYSIS ──────────────────────────────────────

quote
  id, project_id, session_id, participant_id,
  start_timecode, end_timecode,
  text, verbatim_excerpt,
  topic_label, quote_type,
  researcher_context,
  sentiment, intensity,
  last_imported_at  (null = researcher-created or stale from previous run)

screen_cluster  (product-anchored grouping)
  id, project_id, screen_label, description, display_order,
  created_by ("pipeline" | "researcher"), last_imported_at

theme_group  (emergent cross-cutting grouping)
  id, project_id, theme_label, description,
  created_by ("pipeline" | "researcher"), last_imported_at

cluster_quote  (join: which quotes belong to which cluster)
  cluster_id, quote_id,
  assigned_by ("pipeline" | "researcher"), assigned_at

theme_quote  (join: which quotes belong to which theme)
  theme_id, quote_id,
  assigned_by ("pipeline" | "researcher"), assigned_at

(quotes with no cluster_quote or theme_quote row = unsorted pool)

topic_boundary
  id, session_id, timecode_seconds, topic_label,
  transition_type, confidence

── THE RESEARCHER'S ANALYSIS ──────────────────────────────

quote_tag  (join: project quote → researcher tag)
  id, quote_id, tag_definition_id, created_at

quote_state
  id, quote_id,
  is_hidden, hidden_at,
  is_starred, starred_at

quote_edit
  id, quote_id, edited_text, edited_at

heading_edit
  id, project_id, heading_key, edited_text, edited_at

deleted_badge
  id, quote_id, sentiment, deleted_at

dismissed_signal  ("I've seen this, it's not interesting")
  id, project_id, signal_key, dismissed_at

import_conflict  (pipeline wanted to change something the researcher touched)
  id, project_id, import_run_at,
  entity_type, entity_id,
  conflict_type, description,
  resolved, resolved_at

── DERIVED (recomputed, not stored) ───────────────────────

signal          = concentration pattern, recomputed from current data
                  (respects hidden quotes, heading edits, dismissed state)
user_journey    = ordered screen_clusters per participant
friction_point  = quotes where sentiment in (frustration, confusion, doubt)
featured_quote  = top-scored quotes by signal strength
```

### Things to notice

1. **`person` has no `project_id`.** People exist in the world. The pipeline creates a new person row on every import (two separate "Jim Smith" rows are fine). Merging them — declaring "these are the same human" — is a future feature that just updates `session_speaker.person_id` foreign keys. The schema doesn't prevent it.

2. **`codebook_group` is the reusable unit, not the whole codebook.** There is no `codebook` table. A project activates groups via `project_codebook_group`. Groups live in a shared instance-level library. A researcher might reuse their "Friction" group across five studies but create a fresh "Pricing" group for one study. Tags belong to groups, not to projects. Cross-project queries ("all quotes tagged 'pricing concern' across all studies") work because tags span projects. Who can *see* which groups is a future permissions concern, not a data model concern.

3. **`session_speaker` is the missing entity.** It's the join between person and session, carrying the speaker code, role, and per-session stats. This is what makes cross-session moderator linking possible — you can say "session_speaker row 7 and row 12 are the same person" without touching the transcript data.

4. **`signal` is recomputed, not stored.** A signal is a view of the current data — it reflects hidden quotes, heading renames, and unlinked quotes. Storing signals creates a staleness problem every time the researcher edits anything. The analysis module is fast (<100ms), so the API recomputes on the fly. The one researcher action that needs storage is "dismiss this signal" — handled by `dismissed_signal` (signal key + timestamp), checked after recomputation. A researcher renaming a signal's location is really renaming the underlying section/theme (→ `heading_edit`). Unlinking a quote from a signal is removing it from the cluster/theme that generated the signal.

5. **`source_file` tracks the link to original media.** Paths break when files move. `verified_at` lets us detect staleness and offer relinking — critical for the video player, transcript page links, and future clip-export packaging.

6. **Quote state is a single table, not three.** Hidden, starred, and edited are all researcher states on a quote. One row per quote, nullable timestamps. Simpler than separate tables, and a quote's full state is one query.

7. **`heading_edit` is separate from quote edits.** Different domain: the researcher is renaming a section or theme, not correcting a transcript. The `heading_key` format (`"section-{slug}:title"`, `"theme-{slug}:desc"`) comes from the current localStorage convention.

8. **`transcript_segment` is stored.** Currently only in `.txt` files. Storing segments in the database enables transcript search, coverage queries ("which segments aren't quoted?"), and per-speaker statistics without parsing text files.

9. **Signals, journeys, friction points, featured quotes are all derived.** Recomputed from current data by the API. No staleness risk. Signals respect researcher edits (hidden quotes, heading renames, dismissed signals).

### Resolved questions

- **`source_file` — yes.** Needed for the Interviews column, video player, and future clip-export. `verified_at` enables stale-path detection and relinking.
- **`signal` — recompute, don't store.** Signals are a view of the current data. Researcher edits (hidden quotes, heading renames, unlinked quotes) change what signals exist. Only `dismissed_signal` is stored. Analysis module is fast enough (<100ms) to recompute per API request.
- **`codebook_group.colour_set` — string, not enum.** Colour sets are a UI/CSS concern. Storing a string means new colour sets don't require schema changes. Validation at the application layer.
- **Person identity on import — always create new rows.** No automatic matching. Two "Jim Smith" rows stay separate until a human links them. Matching is error-prone and the consequences of a wrong match are worse than the cost of a manual merge.

### Remaining open question

- **Quote identity.** Quotes don't have a natural unique key. `(session_id, participant_id, start_timecode)` is close but overlapping speakers could collide. Lean: synthetic auto-increment ID, with a unique constraint on `(project_id, session_id, participant_id, start_timecode, text[:80])` as a dedup guard. Fine to resolve during implementation.

---

## Decision 2: What triggers the import?

Three options:

| | When | Pros | Cons |
|---|---|---|---|
| **A: On `serve` startup** | `bristlenose serve ./project` reads JSON + `people.yaml`, writes to SQLite, then starts the server | Simple. One-shot. <1 sec for typical project | Server doesn't start until import is done (negligible for our data sizes) |
| **B: Lazy on first request** | Server starts immediately. First API call triggers import if `imported_at` is stale | Fastest startup. Good for multi-project | More code paths. Race conditions on concurrent first requests |
| **C: Explicit `import` command** | `bristlenose import ./project` then `bristlenose serve` | Clean separation of concerns | Extra step for the user. Easy to forget |

**Decision: A.** Import on `serve` startup. The data is tiny (hundreds of quotes, not millions). Import takes <1 second. An `imported_at` timestamp on the project row lets us skip re-import if nothing changed. If the user re-runs the pipeline, restarting `serve` re-imports.

But "import" is more nuanced than it first appears — see "The re-run problem" below.

---

## The re-run problem: pipeline → workspace

The current pipeline is one-directional: recordings → transcribe → analyse → render → done. The researcher's edits (renames, tags, hidden quotes) live in localStorage and never flow back.

The database changes this. Once researcher edits live in the same database as pipeline output, two things become possible — and eventually necessary:

1. **Re-running the pipeline with more data.** You do 8 interviews, run the analysis, spend a day tagging and renaming. Then you do 2 more interviews and re-run. The new pipeline output should appear (new quotes, updated clusters), but your day of work should survive.

2. **The researcher becoming an editor, not just an annotator.** Renaming a section. Rewriting a quote. Moving a quote to a different cluster. Splitting a theme. These aren't annotations on top of the pipeline's output — they're changes *to* the analysis. The database is the living state of the analysis, and both the pipeline and the researcher write to it.

### The AI is a draft, not the truth

The pipeline's initial analysis is typically a 7/10 — it saves hours or days of manual work and reveals patterns a human might miss. But it's guaranteed to be wrong in some fundamental ways that require human contextual knowledge to fix. The database must treat the AI's output as a strong first draft that the researcher refines, not as ground truth with annotations on top.

This means every structural decision the AI makes must be editable: moving quotes between groupings, merging themes, splitting clusters, renaming sections, deleting groupings entirely. These are the researcher's core workflow, not edge cases.

### Incremental analysis is the normal workflow

Running 2-3 interviews, getting an initial analysis, then adding more data later is standard qualitative research practice. The system must support this as a first-class operation:

1. Run 3 interviews → pipeline produces initial analysis
2. Researcher spends a day reorganising: moves quotes, renames sections, merges themes, tags
3. Run 2 more interviews → pipeline produces updated analysis with 5 sessions
4. New quotes and groupings appear, but the researcher's day of work survives

### What this means for import

"Full replace" is wrong. The import needs to be a **merge**, governed by `assigned_by` and `created_by` fields that track who made each decision:

| Data category | On re-import | Why |
|---|---|---|
| **Pipeline output** (sessions, transcripts, quotes, topic boundaries) | Upsert by stable key | The pipeline is authoritative for what it found. New rows appear, matching rows update. |
| **Groupings** (clusters, themes) | Upsert pipeline-created, never touch researcher-created | If the researcher created a "Pricing concerns" theme, it persists. If the pipeline created "Dashboard" and now calls it "Dashboard v2", it updates. |
| **Quote assignments** (cluster_quote, theme_quote) | Replace where `assigned_by = "pipeline"`, never touch where `assigned_by = "researcher"` | If the researcher moved a quote to a different cluster, that move sticks. New quotes from the pipeline get pipeline assignments. |
| **Researcher state** (tags, hidden/starred, edits, heading renames, dismissed signals, deleted badges) | Never touched | This is the researcher's work. Import doesn't delete it. |

### Stable identity for quotes

For researcher state to survive re-import, quotes need a **stable key** that the pipeline produces consistently. The dedup constraint `(project_id, session_id, participant_id, start_timecode, text[:80])` serves this purpose — if the same person said the same thing at the same timecode, it's the same quote regardless of the synthetic ID.

On re-import:
1. Match incoming quotes to existing quotes by stable key
2. Matched quotes: update pipeline fields (sentiment, topic_label, etc.), keep researcher state
3. New quotes (no match): insert with fresh IDs
4. Gone quotes (in DB but not in new pipeline output): **keep, flag as stale** — the researcher may have tagged them, so deleting would destroy work. A `last_imported_at` timestamp on each quote lets the UI show "this quote was in a previous run but not the current one"

### Researcher operations on groupings

These are common, everyday actions — not edge cases:

| Operation | DB effect |
|---|---|
| **Move a quote** to a different cluster | Delete old `cluster_quote` row, insert new one with `assigned_by = "researcher"` |
| **Ungroup a quote** (return to unsorted pool) | Delete `cluster_quote` / `theme_quote` row |
| **Merge two themes** | Move all `theme_quote` rows from theme B to theme A (set `assigned_by = "researcher"`), delete theme B |
| **Split a theme** | Create new theme with `created_by = "researcher"`, move selected `theme_quote` rows to it |
| **Delete a theme/cluster** | Delete `theme_quote`/`cluster_quote` rows (quotes return to unsorted pool), delete theme/cluster row |
| **Create a new theme/cluster** | Insert row with `created_by = "researcher"`, researcher assigns quotes to it |
| **Rename a section/theme** | `heading_edit` (already modelled) |
| **Reorder clusters** | Update `display_order` on `screen_cluster` |

All of these are simple CRUD on existing tables. No new tables needed.

### The unsorted pool

Quotes with no `cluster_quote` or `theme_quote` row are **unassigned** — they sit in a visible "To be sorted" section. This is a first-class UI concept, not a hidden state. It's where quotes go when:

- The researcher deletes a grouping
- The researcher ungroups a quote
- The pipeline extracts a quote but doesn't assign it to any cluster/theme (edge case, but possible)
- A stale quote from a previous run loses its grouping after re-import

Query: `SELECT * FROM quote WHERE id NOT IN (SELECT quote_id FROM cluster_quote) AND id NOT IN (SELECT quote_id FROM theme_quote)`.

### Researcher edits always win

The governing principle: **researcher edits always win over pipeline output.** The pipeline provides the initial state; the researcher refines it. Re-running the pipeline updates the AI's contribution but doesn't undo the researcher's work.

| Edit type | Re-import behaviour |
|---|---|
| Tag a quote | Survives — tag stays regardless of pipeline changes |
| Star/hide a quote | Survives |
| Rename a section heading | Survives — researcher knows better than the AI what to call this section |
| Rewrite quote text | Survives — researcher corrected a transcription error |
| Move a quote between clusters | **Survives** — `assigned_by = "researcher"` protects it |
| Create a new theme | **Survives** — `created_by = "researcher"` protects it |
| Delete an AI sentiment badge | Survives |
| Merge/split themes | **Survives** — researcher-created groupings and researcher-assigned quotes are untouched |

### Import conflicts, not assignment history

When the pipeline re-runs with new data, it will sometimes clash with researcher decisions. Example: researcher renamed "Homepage" to "Landing page". Pipeline re-runs with more interviews and creates a new cluster also called "Landing page" (because two participants used that phrase). Now there are two things called "Landing page" — one is the researcher's renamed cluster, the other is a new pipeline cluster.

These clashes aren't automatable. They require human judgment: are these the same thing? Should they merge? The system needs to:

1. **Detect the conflict during import.** When the pipeline wants to create/update something that collides with a researcher edit, write to `import_conflict` instead of silently resolving it.
2. **Surface it after import.** "3 conflicts from the latest import — review?" The researcher resolves each one manually (merge, rename, keep both, discard).
3. **Never silently destroy work.** Researcher edits survive. The conflict table is a "review needed" queue.

Full assignment history (audit log of every move) is not worth the schema complexity. The researcher doesn't need to know "this quote was in Homepage, then moved to Navigation, then the pipeline tried to put it back." They need to know the current state and "what changed since I last looked?" The `import_conflict` table provides the latter without an audit trail.

If full history becomes useful later, an `assignment_log` table can be added without changing existing tables — it's purely additive.

### Milestone 1 implication

For milestone 1 (sessions table only), the import is simple — sessions don't have researcher overrides. The merge complexity kicks in at milestone 2 (quotes) and milestone 3 (researcher state moves from localStorage to DB). But we should design the schema with `assigned_by`, `created_by`, and `last_imported_at` from the start, and the import function should be built as an upsert rather than a drop-and-replace. Building the right habit early is cheaper than retrofitting.

---

## Decision 3: Sessions table — full visual parity from day one

The sessions table UI is settled after many iterations. The columns and features are:

| Column | What renders | Data needed |
|---|---|---|
| ID | `#1` linking to transcript page | session_id, session_number |
| Speakers | Badge + name per speaker | speaker_code, short_name/full_name, role |
| Start | Finder-style relative date + journey below | session_date, journey_labels |
| Duration | `MM:SS` or `HH:MM:SS` | duration_seconds |
| Interviews | Filename with middle-ellipsis, link to source | source file path, source_folder_uri |
| Thumbnail | Play icon if media exists | has_media |
| Sentiment | Inline sparkline bars | per-session sentiment counts |

Plus moderator/observer header above the table.

**There's no reason to ship half a table.** The UI is non-negotiable, the data is available, and building a partial version just means we test/debug something we're about to throw away. The only question is work sequencing within the milestone — we can build column by column in separate commits, but the milestone isn't done until it matches.

**Approach:** API returns the complete data shape from the start. React component builds up column by column in commits, but the milestone gate is full parity.

---

## Decision 4: How React replaces the server-rendered table

This is the core architectural question. Three strategies, each with real trade-offs:

### Option A — Islands on existing HTML

`bristlenose serve` still runs `render_html.py` to produce the full static report. The server serves it at `/report/`. But it also serves the React bundle, which finds specific mount points in the HTML (e.g. `<div id="bn-sessions-table-root">`) and mounts React components into them. The rest of the page stays vanilla JS.

**How it works:**
1. Pipeline runs → produces static HTML as normal
2. `bristlenose serve` serves that HTML at `/`
3. React bundle loads, finds `#bn-sessions-table-root`, mounts `<SessionsTable>`
4. The React component fetches from `/api/sessions` and renders, replacing a placeholder `<div>`
5. Everything else (dashboard, quotes, toolbar, search) stays vanilla JS

**Pros:**
- **Everything works from day one.** All tabs, all features — the vanilla JS report is the baseline. React islands enhance specific sections.
- **Incremental.** Each milestone replaces one section. No "coming soon" dead ends. The report is always fully functional.
- **Shared CSS.** React components render the same HTML structure with the same CSS classes. No duplicate styling.
- **Low risk.** If a React island breaks, the static report is still there at `/report/` as fallback.
- **Matches the migration doc.** "The report is always shippable at every step."

**Cons:**
- **Two rendering paths for the same section.** `render_html.py` renders the Jinja2 sessions table (for static export). React renders the sessions table (for serve mode). They must match visually. Changes to the table need updating in two places until Jinja2 is retired.
- **Flash of unhydrated content.** User might briefly see an empty placeholder (or the static table) before React mounts. Manageable with a loading skeleton, but it's there.
- **Vanilla JS interference.** The existing report JS (17 modules) is still running. If vanilla JS binds event listeners to the sessions table DOM, React will replace that DOM and the listeners break. Need to audit which JS modules touch the sessions table.
- **Conditional `render_html.py`.** Need to teach the Jinja2 template to emit either the full table (static export) or a mount-point div (serve mode). Adds a `serve_mode` flag that flows through the renderer.

### Option B — React replaces on hydration

`render_html.py` renders the full Jinja2 sessions table as it does today. React loads and replaces the entire `<section class="bn-session-table">` element with a React-rendered version that fetches live data from the API.

**How it works:**
1. Static HTML renders the full sessions table (Jinja2)
2. React loads, finds `.bn-session-table`, unmounts it, renders its own version
3. The React version fetches from the API (same data, but live)

**Pros:**
- **No flash of empty content.** The Jinja2 table is visible until React swaps it. User sees content immediately.
- **No conditional rendering in Jinja2.** `render_html.py` always renders the same output. React decides whether to take over.
- **Graceful degradation.** If React fails to load, the static table is still there.

**Cons:**
- **Visual flash.** Even if the content is similar, React replacing the DOM may cause a flicker — especially if the API is slow and the React version re-renders with fresh data.
- **Two rendering paths (same as A).** Table exists in both Jinja2 and React. Must match.
- **Heavier page load.** The browser renders the Jinja2 table, then React tears it down and renders its own. Wasted work.
- **Confusing semantics.** The Jinja2 table uses pipeline data baked at render time. The React table uses API data from SQLite. If they disagree (stale import), the table visibly changes on hydration.

### Option C — Standalone React shell, no render_html.py

`bristlenose serve` doesn't produce or serve the static HTML report at all. It serves a React SPA that fetches everything from APIs. The pipeline's `render_html.py` path is untouched — it still produces static exports for `bristlenose render`.

**How it works:**
1. `bristlenose serve ./project` imports data into SQLite, starts FastAPI
2. Browser loads `index.html` — a React SPA with its own tab bar, layout, etc.
3. Sessions tab fetches from `/api/sessions`, renders React component
4. Other tabs are either not implemented yet, or link out to the static report

**Pros:**
- **Clean separation.** React app is its own thing. No entanglement with Jinja2 templates, vanilla JS, or the static report's DOM.
- **No "two rendering paths" problem.** Sessions table only exists in React. Jinja2 only exists for static export. They never compete.
- **Freedom to rethink layout.** Not constrained by the existing HTML structure. Can use a proper React router, proper state management, etc.
- **This is where we end up anyway.** Milestone N is "drop vanilla JS shell, full React SPA." Option C starts there.

**Cons:**
- **Incomplete report.** Until every tab is ported, the serve experience is partial. Sessions tab works, but quotes/dashboard/codebook/analysis are missing or stub pages. Users have to open the static report for anything else.
- **Duplicate chrome.** The React app needs its own header, tab bar, theme toggle, search — all features that already exist in the vanilla JS report. Rewriting them in React before porting the content they wrap is front-loaded work.
- **CSS divergence risk.** If the React app uses different markup, the atomic CSS from `bristlenose/theme/` may not apply cleanly. Could end up maintaining two style systems during the transition.
- **Longer time to a useful milestone.** Before the sessions table even renders, we need a React shell (header, tabs, layout). More scaffolding before value.

### Summary

| | Everything works day one | No duplicate rendering | Clean architecture | Time to useful |
|---|---|---|---|---|
| **A: Islands on HTML** | Yes | No (two paths) | Medium | Fast |
| **B: Hydration** | Yes | No (two paths) | Medium | Fast |
| **C: Standalone SPA** | No (stubs) | Yes (one path) | High | Slower |

**Decision: A (islands on existing HTML).** Keeps the report fully functional at every step. The "two rendering paths" problem is real but manageable: the sessions table Jinja2 template is 49 lines, and once the React version is proven, we stop rendering the Jinja2 version in serve mode (a one-line `{% if not serve_mode %}` guard). Each milestone replaces one section — the report is never broken.

---

## Decision 5: Tabs and navigation in serve mode

This only matters if we go with option C above (standalone SPA). If we go with A or B (islands on existing HTML), the tab bar and navigation already work — they're vanilla JS in the existing report.

But even with islands, it's worth thinking about:

### If islands (option A or B)

Tabs just work. The vanilla JS tab system (`tabs.js`) is already in the report. The React sessions island mounts inside the Sessions tab content area. No extra work.

**One consideration:** The existing tab system uses `#hash` navigation. If we later want React Router to own routing, there'll be a migration. But that's a milestone N problem, not milestone 1.

### If standalone SPA (option C)

We need to build tab navigation in React. Three sub-options:

- **Stubs + link to static report.** Tabs exist but non-sessions tabs say "Open in full report" with a link to the static HTML. Fast to build but poor UX.
- **Iframe embed.** Non-sessions tabs load the corresponding section of the static report in an iframe. Technically works but ugly (nested scrollbars, broken deep links, no shared state).
- **Port tab by tab.** Only show tabs that are implemented. Start with Sessions only, add Dashboard in milestone 4, Quotes in milestone 2. Honest but sparse.

> **Not blocking if we go with A.** This decision only matters for option C.

---

## Implementation plan

Assuming: full domain schema, import on startup, full visual parity, islands on existing HTML (option A).

### Step 1 — Database schema + import logic
- Full schema in `server/models.py` (all tables from the domain model — instance-scoped and project-scoped)
- `import_project(project_dir)` reads intermediate JSON + `people.yaml` + session data → populates all tables
- Import built as **upsert by stable key** from the start (not drop-and-replace), even though milestone 1 doesn't strictly need it — building the right habit early
- `assigned_by` / `created_by` fields on groupings and join tables from the start — the pipeline writes `"pipeline"`, future researcher edits write `"researcher"`
- `last_imported_at` on quote, cluster, and theme rows to detect stale data after re-runs
- Signals not stored — recomputed by the analysis module when the API needs them
- Import called from `create_app()` startup with `imported_at` check
- Tests: import from `smoke-test` fixture, verify all tables populated; test re-import preserves researcher state

### Step 2 — Sessions API endpoint
- `GET /api/projects/{id}/sessions` — full session data including speakers, journey, sentiment counts, media flags, source files
- Pydantic response models matching the data shape the React component needs
- Tests: FastAPI test client against imported fixture

### Step 3 — Mount point in existing HTML
- `render_html.py` gains a `serve_mode` flag
- In serve mode: sessions table section renders `<div id="bn-sessions-table-root" data-project-id="...">` instead of the Jinja2 table
- In normal mode: unchanged (Jinja2 table for static export)
- Audit which vanilla JS modules bind to session table DOM → ensure no conflicts

### Step 4 — React sessions table (full parity)
- `SessionsTable` component fetches from API, renders full table
- Same HTML structure + CSS classes as Jinja2 template
- All columns: ID with transcript link, speakers with badges, Finder-style dates, journey, duration, filename with truncation, thumbnail, sentiment sparkline
- Moderator/observer header
- Build column by column in commits, but milestone gate is full match

### Step 5 — Integration + polish
- `bristlenose serve ./project` imports, starts server, opens browser
- Verify: sessions tab shows React table, all other tabs work via vanilla JS
- Dev mode: Vite proxy, hot reload
- Production: Vite build → `server/static/`

---

## Open questions (not blocking)

1. **Re-import trigger while server is running.** If the user re-runs the pipeline while `serve` is running, the database is stale. Options: (a) require server restart, (b) watch intermediate JSON for changes, (c) "refresh" button in UI. Lean: (a) for now — restart is cheap. The merge/upsert logic handles the data correctly regardless of trigger mechanism.

2. **Multi-project.** `projects` table implies multi, CLI takes one dir. Lean: one project for now, multi later.

3. **Dashboard sessions table.** The dashboard has a simplified sessions table (no journey, no sparkline, no thumbnail). Separate React component or same component with a `variant` prop? Lean: same component, `compact` prop, but not in milestone 1.

4. **Transcript page links.** Session rows link to `/sessions/transcript_s1.html`. In serve mode these are static files. Lean: serve them from the output dir as-is. React transcript pages are a future milestone.

5. **Testing strategy.** Python: pytest for API + import. React: Vitest from the start — at minimum, test that the component renders with mock data and that the API integration works. Not exhaustive, but establishes the pattern.

6. **Quote primary key.** Synthetic auto-increment ID, with a unique constraint on `(project_id, session_id, participant_id, start_timecode, text[:80])` as a dedup guard. Fine to refine during implementation.

7. **Researcher state migration.** Existing reports have researcher state in localStorage (tags, hidden, starred, edits, codebook). When a user switches from static report to `serve`, do we import their localStorage into the database? Lean: yes, a one-time migration endpoint that accepts the localStorage blob and writes it to the DB tables. But not in milestone 1.

8. **Source file relinking.** When source files move, the video player and transcript links break. `verified_at` on `source_file` lets us detect staleness. A future "relink" UI updates the path. Not in milestone 1 but the schema supports it.

---

## Implementation status (Feb 2026)

### ✓ Complete

**Step 1 — Database schema** (`bristlenose/server/models.py`)
- 22 SQLAlchemy ORM tables covering the full domain model
- Instance-scoped: `Person`, `CodebookGroup`, `TagDefinition`
- Project-scoped: `Project`, `Session`, `SourceFile`, `SessionSpeaker`, `TranscriptSegment`, `Quote`, `ScreenCluster`, `ThemeGroup`, `ClusterQuote`, `ThemeQuote`, `TopicBoundary`, `ProjectCodebookGroup`
- Researcher state: `QuoteTag`, `QuoteState`, `QuoteEdit`, `HeadingEdit`, `DeletedBadge`, `DismissedSignal`, `ImportConflict`
- `assigned_by`/`created_by` fields, `last_imported_at` timestamps, unique constraints, foreign keys
- 38 tests in `tests/test_serve_models.py`

**Step 1 — Import logic** (`bristlenose/server/importer.py`)
- Reads `metadata.json`, `screen_clusters.json`, `theme_groups.json`, raw transcripts
- Parses transcript headers for session date, duration, source file
- Creates sessions, speakers, persons, transcript segments, quotes, clusters, themes, all join tables
- Built as upsert by stable key (idempotent)
- Called from `create_app()` on startup
- 17 tests in `tests/test_serve_importer.py`

**Step 2 — Sessions API** (`bristlenose/server/routes/sessions.py`)
- `GET /api/projects/{project_id}/sessions`
- Pydantic response models: `SessionsListResponse`, `SessionResponse`, `SpeakerResponse`, `SourceFileResponse`
- Returns speakers (sorted m→p→o), journey labels (from screen clusters by display_order), sentiment counts, source files, moderator/observer names
- FastAPI dependency injection via `app.state.db_factory`
- 17 tests in `tests/test_serve_sessions_api.py`

**Infrastructure:**
- `db.py`: `init_db()` registers all models; `StaticPool` for in-memory SQLite testing
- `app.py`: registers sessions router, stores DB factory in app state, auto-imports on startup
- All 1050 existing tests pass, lint clean

**Step 4 — Mount point in existing HTML** (`bristlenose/stages/render_html.py`)
- `render_html()` gains `serve_mode: bool = False` parameter
- When `serve_mode=True`, Sessions tab renders `<div id="bn-sessions-table-root" data-project-id="1">` instead of Jinja2 table
- Dashboard compact table stays static (no React replacement needed)
- Audit confirmed: only `global-nav.js` binds to session table DOM (`tr[data-session]`, `a[data-session-link]` in both dashboard and sessions grid). React replaces the sessions grid DOM; the JS is null-safe (queries return empty NodeLists when mount point is empty)

**Step 5 — React SessionsTable component** (`frontend/src/islands/SessionsTable.tsx`)
- Full visual parity with Jinja2 `session_table.html`
- Reads `data-project-id` from mount point, fetches `GET /api/projects/{id}/sessions`
- All columns: ID with transcript link, speakers with badges (`.bn-person-id`, `.badge`), Finder-style relative dates, journey arrow chains, duration (MM:SS or HH:MM:SS), filename with middle-ellipsis, thumbnail play icon, sentiment sparkline bars (7 sentiments with coloured bars)
- Moderator/observer header above the table
- Loading and error states
- `main.tsx` updated to mount SessionsTable into `#bn-sessions-table-root`
- TypeScript compiles clean, Vite build succeeds

### Milestone 1 complete

All 5 steps done. 72 new tests (38 schema + 17 import + 17 API), full suite (1050) passing, lint clean. The served sessions table is now a React island backed by a real API reading from SQLite.
