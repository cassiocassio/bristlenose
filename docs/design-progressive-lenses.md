---
status: designed, not built — reviewed against the code 12 Oct 2026 (Fable), findings folded in
last-trued: 2026-10-12
trued-against: HEAD@main on 2026-10-12 (df8128c6, scene strips)
owner: run progress across the pipeline, the report server, the SPA and the Mac app
mockup: docs/mockups/progressive-lenses-replay.html
---

## Changelog

- _2026-10-12_ — trued up against the scene strips that shipped the same afternoon
  (`df8128c6`): §2 lists the fifth tapestry layer and the fact that it waits for the
  whole run; §1.2 no longer says the mockup inlines the CSS verbatim; Phase 4 names the
  strip fields, records what is pinned with layers absent, and adds the refetch merge
  rule the strip poll already needs; §7 carries the strips-during-a-run question.
  Anchors: `routes/tapestry.py` (`strip`, `strips_pending`), `server/scene_strips.py`,
  `SessionsTable.tsx` (the strip-only merge), `experiments/session-tapestry/README.md`
  § Scene stripes.

# Progressive lenses — read session 1 while session 2 is being transcribed

## 1. What and why

Today a run shows nothing until it ends. Serve intercepts every `/report/*` route
with the status page until a terminus event arrives (`server/status_page.py`,
`page_for`), the database is filled once, on `run_completed`
(`server/app.py`, `_on_run_completed`), and the Mac shows the shoal for the whole
run (`DetailPaneKind.resolve`, `.shoal`). On an 8-hour corpus that is 51 minutes of
nothing.

Every transcript is finished long before that. Whisper runs one session at a time,
and session 1 is done in under two minutes; it then waits for every other session
to be transcribed, because speaker identification gathers over all of them, and
then for the whole analysis, because the SPA cannot mount without a finished run.

**The single highest-value outcome:** the researcher reads session 1, for five or
ten minutes, while the rest are processed. The Sessions lens is usable from the
first second, each row opens as soon as its transcript is readable, and the other
lenses light when they have something true to show.

### 1.1 Measured

Replayed from two real runs kept on the maintainer's machine: per-session times
from `bristlenose.log` (Whisper) and `llm-calls.jsonl` (each LLM call's
completion). "Progressive" is a projection: each session readable after its own
transcription and its own speaker call, in session order; its quotes after its own
topic and quote calls, reusing the wall time each took in the real run.

| | FOSSDA, 10 recordings, 8 h 10 min | | Rockclimbing, 7 `.vtt` + 1 recording | |
|---|---|---|---|---|
| | Today | Progressive | Today | Progressive |
| First transcript readable | 51:27 | **1:45** | 3:10 | **0:10** |
| All transcripts readable | 51:27 | 19:50 | 3:10 | 0:11 |
| First quotes | 51:27 | 4:21 | 3:10 | 0:22 |
| Sections, themes, Signals | 51:22 | 38:56 | 3:05 | 2:38 |

FOSSDA s3 (94 min) spent 30 minutes in quote extraction and returned nothing
(a truncated response). That one session holds the barrier up, and it is a real
failed-session case for §6.

Teams and Meet projects (platform transcripts) skip Whisper, so every row is
readable within seconds; progressive matters much less there, and the design must
simply not make them worse.

### 1.2 The mockup is the spec for the visible half

`docs/mockups/progressive-lenses-replay.html` replays both runs in the shipped
design system: `sessions-grid.css`, `session-tapestry.css` and the rest inlined
as they stood on 12 Oct (the CSS has since gained the scene strip's `.bn-tp-strip*`,
`.bn-tp-clip-edge` and `.bn-tp-notch` rules, which the mockup does not carry), rows
built as `SessionsTable.tsx` builds them, a window-width control to
walk the grid's container queries. Its commentary lists the surgical edits; this
doc is the whole plan, including the half the mockup cannot show.

**The grid's responsive geometry is not in scope.** Tracks, subgrid, the shrink
pair, the seven container thresholds and the name ladder stay exactly as they are
(`organisms/sessions-grid.css` header). Nothing here edits that file.

## 2. Decisions (settled with the owner, 12 Oct 2026)

**Lens rail**
- At the start only **Sessions** is selectable, in normal type. Every other lens is
  disabled and turns normal when it has content: Quotes at the first quotes,
  Signals at the barrier.
- **Nothing in the rail shimmers.** No "next lens" signal.
- **Codebooks is disabled during the run** in v1 (expected to be browsable at all
  times later; too big for this brief).
- The flocking (shoal) shows only when nothing at all is selectable, which with
  Sessions available at ingest is the first second or so.

**Sessions grid: three row states**

| State | Meaning | Markup |
|---|---|---|
| Readable | transcript, speakers and (if on) PII done | the shipped row: `data-session`, ID link, hover |
| Being processed | becoming readable now; exactly one row | no `data-session`; its **filename** in `.bn-thinking-shimmer` |
| Waiting | exists; processing not begun | no `data-session`; `aria-disabled="true"` |

- One shimmering row at a time — the row heading towards readable. Rows already
  readable stay normal while their quotes are extracted.
- **No shimmer** for a session that arrives with a platform transcript: it becomes
  readable almost at once.
- The shimmer is the AI-working cue on the row's own text, `atoms/shimmer.css`
  unchanged. Never a skeleton (that is a latency cue for page geometry, a different
  signal).
- **Every true fact known at ingest is shown:** number, start, duration, filename,
  in the shipped formats. **Facts not yet known stay empty.** The sparkline's "—"
  means *no quotes with a sentiment*, so it appears only once a session's quotes are
  back.
- **Thumbnails:** a very subtle placeholder (the empty `.bn-video-thumb` box) only
  for files the probe confirms are video, then the frame (0.14 s per grab, measured
  on a 1.25 GB file; all ten FOSSDA frames in about 1.5 s after ingest).

**Progress text**
- Only in the window subtitle and the project's status line, from the shipped
  strings (`desktop.chrome.pipeline.stage.*` + `sessionsCount`), **static** — a
  count is a real fraction, so the motion spec (`design-motion.md` §4.7.1) makes it
  static text. No new in-progress messages.

**Quotes**
- Grouped **by session** until sections and themes exist. Then a permanent choice
  of grouping, *By session* / *Sections & themes*, in the heading's
  `.section-heading-action` slot. The researcher's choice wins; themes arriving
  never move them.
- Dragging a quote between groups is off in By session (membership is a fact).

**Counts**
- A split-flap on pipeline increments of counts, coalescing bursts (one move to the
  latest value when updates land inside the window). Only pipeline increments, never
  a researcher's own edit.

**Session tapestry**
- The disclosure appears once a row is readable, and the tapestry arrives in
  layers: **turns** with the transcript; **scene colours** about 1.5 s per hour of
  video later; **sentiment marks** with that session's quotes; **section flags and
  theme spans** at the barrier. These are real turns, not a skeleton.
- A fifth layer shipped on 12 Oct 2026 and is the one later-arriving layer the app
  has: **scene strips and notches** (`utils/scene_strip.py`, every frame at 4 fps),
  computed by serve on a background thread (`server/scene_strips.py`) and **deferred
  for the whole run** — the job will not start while the project's latest run is in
  progress, so under progressive a readable row has no strip until the barrier. The
  route says `strips_pending` and the grid polls it (§7 item 6 on whether to allow
  the job alongside Whisper). Record: `experiments/session-tapestry/README.md`
  § Scene stripes.
- **Option-click** on a disclosure opens or closes every *readable* row. A row that
  becomes readable later arrives closed.
- **Scale: no animated zoom.** One shared scale, fixed at ingest from every
  session's duration (§4.6).

## 3. State model

Principles, in the house's own terms (`docs/design-project-condition.md` §2.1:
"every new state enters through a fixture case"):

1. **Facts, not phases.** Each session's progress is a recorded fact (its manifest
   record, §3.1); lens and row state are derived from those facts, never stored.
2. **Per artefact, three states:** not yet / ready / failed. Absence is not a state
   (the s09 manifest lesson, root `CLAUDE.md`): a failure is recorded, not omitted.
3. **The unit of work is the unit of display, caching and failure:** the session,
   for everything before the barrier.
4. **Progress only moves forward within a run.** A lens never goes ready → not
   ready except through an explicit Re-analyse.
5. **Barriers are named.** Per-session stages fan out; cross-session stages
   (clustering, themes, Discussion) are joins, and no partial version of a join is
   shown — anything that claims a proportion waits.
6. **Readers never interpret the log themselves.** Lens readiness is a projection
   the condition endpoint serves.

### 3.1 Where per-session progress lives: the manifest, not the events log

The first draft added three event types to `pipeline-events.jsonl`. Review found two
reasons not to:

- **Every reader of the log treats a line that is not `run_started` or
  `run_progress` as the run's terminus.** `run_condition.reduce_lines` assigns it to
  `run.terminus` (`run_condition.py:209`), `events.tail_run_state` does the same, and
  Swift's `EventLogReader` takes the newest non-`run_progress` line as the lifecycle
  event. A `session_readable` line would make a running analysis read as ended, on
  both sides.
- **The log carries no ids by rule.** `RunProgressEvent`'s docstring: counts and
  timings only, never an id, filename or speaker label, so the log never becomes a
  re-identification surface (sibling to `pii_summary.txt` and `llm-calls.jsonl`).

So:

1. **The manifest carries each session's progress.** It already has per-session
   records and `FAILED` (`manifest.py`). Phase 1 writes it *per session* (§4 step 6),
   for every stage of the chain.
2. **A counts-only `run_progress` event wakes the watcher** each time a session
   becomes readable (`sessions_complete` already exists on it). The watcher's
   `on_change` already fires on any write to the log.
3. **Serve reads the manifest as an overlay.** In `design-project-condition.md`'s
   layering (§2.1), facts only one host knows are overlays, beside `importing`.
   Per-session readiness is one: `progress: {readable, quoted, quote_failed, joined}`,
   computed from the manifest by a pure function with its own tests. The reducer is
   unchanged.

If a future change does add event types to the log, the three readers must first move
from "anything but progress is lifecycle" to an allowlist of lifecycle types, with a
fixture case (`session-events-are-not-lifecycle`).

### 3.2 What the condition endpoint serves

`GET /api/projects/{id}/condition` (`routes/runs.py`) gains two fields:

- `lenses: {sessions, quotes, signals, project, codebook, discussion}`: booleans,
  derived (§3.3).
- `data_version`: a counter bumped after each per-session import. **This is the SPA's
  refresh key during a run.** `/last-run` stays as it is: it is pinned "do not extend",
  the SPA refetches only when its `run_id` changes (`LastRunStore.ts`), and every change
  announces "Pipeline completed".

### 3.3 Lens readiness, derived

| Lens | Ready when |
|---|---|
| Sessions | at ingest (sessions known) |
| Quotes | `quoted` holds a session with quotes |
| Signals | `joined` |
| Project | **open** (§7) |
| Codebooks | run ended (v1) |
| Discussion | its own stage done (not in either measured run) |

## 4. Implementation, by phase

Each phase ships on its own. Phase 1 is the outcome in §1; the rest add to it. Phase 0
is what Phase 1 stands on: without it, Phase 1 is not shippable alone (review, 12 Oct).

### Phase 0 — Prerequisites

1. **Fix the project-row fork first.** A serve started before `bristlenose-output/`
   exists stores `output_dir == input_dir`; the run then creates the output dir,
   `import_project` matches rows on `(input_dir, output_dir)` (`importer.py:246-264`),
   creates row 2, and the SPA, hardcoded to project 1, reads an empty row
   (`server/CLAUDE.md`, measured 12 Oct 2026; the fix is in `TODO.md`, 12 Oct). A first
   analysis under a live Mac serve is exactly Phase 1's scenario. Add
   `assert project.id == 1` to every import handler, including the new per-session one.
2. **A refresh key that is not `/last-run`:** `data_version` on `/condition` (§3.2), and
   a store that drives the SPA's `refreshKey` from it while a run is in progress.
3. **Lens availability reaches the Mac.** Nothing in Swift reads `/condition` today, and
   `LensAvailability.derive` returns one Bool from `documentState`, plumbed as
   `lensesEnabled` through `ProjectSidebarOutline`, `LensRail` and the View menu. Make it
   per lens, and carry `lenses` over the bridge as a message from the SPA (the
   `panel-state` pattern). **This ships in the same change as Phase 1's `page_for`
   change**, or the SPA mounting makes `documentState == .spa` and every lens lights at
   once.
4. **No cold reload at the end of the run.** `scheduleReportReloadOnCompletion`
   (`ContentView.swift:3062`) reloads the report on analysing → settled. With the SPA
   mounted from the first second, that would remount it under someone reading session 1.
   Gate it on `documentState != .spa`; the `data_version` refetch replaces it.
5. **`page_for` gets a new server fact**, `sessions_imported` (it has only `importing` and
   `has_data` today, and `has_data` is `bool(last_run)`). `test_first_run_in_progress`
   (`tests/test_server_status_page.py`) and `design-project-condition.md` §3.5's row
   "latest in progress, no report → intercept" change with it.
6. **Web nav lens tabs need a disabled state.** They are bare `NavLink`s (`NavBar.tsx`).
   Disabled, per §2: not navigable, `aria-disabled`.

### Phase 1 — Sessions readable one by one

**Pipeline (`bristlenose/pipeline.py`, `run`)**
1. **Ingest writes the session list** to `.bristlenose/intermediate/ingest-facts.json`
   (not `sessions.json`: `.bristlenose/sessions.json` is already the session registry,
   `session_registry.py`, which holds identity and pins):
   id, number, source files, start and its source, duration, and **has a video
   stream** — add `stream=codec_type` to the `-show_entries` of the one `ffprobe`
   ingest already runs (`utils/audio.py`, `probe_media`), so "video" is the stream,
   not the extension (today `_guess_file_type` decides by extension). A cloud file
   that has not been downloaded is not probed (ingest refuses to download it) and
   gets no placeholder.
2. **A per-session chain through PII**: transcribe → identify speakers → merge →
   PII → write that session's transcript files → record it in the manifest → emit a
   counts-only `run_progress`. Today
   s05b gathers over all sessions (`pipeline.py`, the `_sem_5b` block), so session 1
   waits for session 10's transcription.
3. **Participant codes are a sequential fold** (`assign_speaker_codes` threads
   `next_participant_number`). Session N's codes wait for N−1. Whisper already runs
   in session order, so this costs nothing on recorded projects.
4. **Thumbnails per session**, grabbed right after ingest for probe-confirmed video,
   at the 60 s fallback frame (§7: whether to swap in the transcript-chosen frame at
   readable). Today `extract_thumbnails` runs at render.
5. **Scene colours per session** after its turns exist (`utils/scene_colour.py`,
   ~1.5 s per hour of video). Today computed just before render.
6. **Manifest, per session.** Today `write_manifest` runs at stage boundaries,
   `session_segments.json` is written once after all sessions (`pipeline.py:1620`), and
   merge and PII have no per-session records. Write the manifest after each session;
   write `session_segments.json` incrementally; add per-session records for merge and
   PII. Failures as `FAILED` (§3 principle 2). Then resume and progressive agree.
7. **PII once, not per session.** `remove_pii` initialises Presidio on every call
   (`s07_pii_removal.py`), so a per-session chain would load spaCy N times. Hoist the
   engines; append to `pii_summary.txt` per session instead of writing it whole.
8. **Timing and telemetry per session.** The CLI's checkmark lines, the Welford stage
   actuals (`timing.py`), the remaining-time estimate and `_llm_telemetry.stage(...)`
   are bound once around today's gathers. In a chain they need per-session binding,
   and the CLI lines need a shape for interleaved stages.

**Report server**
9. `run_event_watcher` (`server/event_watcher.py`), on a `run_progress` write, reads
   the manifest overlay and imports any newly readable session:
   import that session (step 10), then bump `data_version` so the SPA refetches.
10. **Importer, per session.** `import_project` today rebuilds the session list from
   transcripts and clusters and *cleans up sessions it does not find* — called
   mid-run, it would delete every session not yet transcribed. Add an import that
   (a) reads `ingest-facts.json` for the full list, so waiting rows exist with their
   ingest facts, (b) imports transcript segments and speakers for the sessions in
   `progress.readable`, (c) never deletes. The full `import_project` still runs on
   `run_completed`.
11. `page_for` (`server/status_page.py`): an in-progress run with no report yet
   returns `None` (SPA renders) once `sessions_imported` is true (Phase 0 step 5), not
   `"in-progress"`. The status page keeps "no-run", failed and cancelled. Precedent:
   a transcribe-only run already lets Sessions and transcripts render
   (`page_for`, the `TRANSCRIBE_ONLY` branch).
12. `GET /sessions` (`server/routes/sessions.py`, `SessionResponse`) gains
    `state: "readable" | "processing" | "waiting"`. The TS type in
    `frontend/src/utils/types.ts` in the same change.

**SPA**
13. `SessionRow` (`islands/SessionsTable.tsx`): `data-session` and the ID link only
    when `state === "readable"`; otherwise `aria-disabled="true"`. That alone removes
    pointer and hover, through the grid's existing `[data-session]` rules.
14. The processing row: `.bn-thinking-shimmer` on its filename span; base colour =
    the row's resting colour; contrast set for this surface (the web chip ships 20%).
15. Speakers, sentiment and thumbnail render nothing until known.
16. Row treatment **A or B** (§7). If A: one rule, muted text on a row without
    `data-session`.
17. The web nav's lens tabs follow `lenses` from the condition endpoint.

**Mac**
18. `DetailPaneKind.resolve`: `.shoal` only while no lens is ready; then `.report`.
19. `LensAvailability.derive` becomes per lens, reading `lenses` from the bridge (Phase 0 step 3). The rail's rows
    (`LensRail.swift`, `LensItem.swift`) take the disabled state per lens; ⌘1–⌘5 in
    the View menu follow the same derivation (it is already the single source for
    them).
20. Status line and subtitle: the shipped `RunProgressSubtitle` strings. When
    transcription and quote finding overlap (phase 3), it names Transcribing while
    any session is still to transcribe.

**Gate tests for phase 1**
- **An edit made mid-run survives the next per-session import** — a speaker rename,
  a role recode, a paragraph split on session 1 while session 2 is imported. This is
  the test the whole phase rests on.
- The importer never deletes during a run.
- The manifest overlay (§3.1): a pure function, with cases for none readable, some,
  one quote failure, joined, cancelled with three readable (they stay readable).
- `run_progress` per session does not change the condition's `latest` (it is already
  skipped by every reader; pin it).
- `DetailPaneKindTests`, `LensAvailabilityTests`: shoal → report at the first
  readable session; per-lens truth table.
- vitest: the three row states, by markup (`data-session`, `aria-disabled`, the
  shimmer class on exactly one element).
- One acceptance run of the folder-of-horrors corpus through the app, looked at
  (root `CLAUDE.md`: a test suite hides the rendered surface).

### Phase 2 — Quotes per session, and the grouping

1. s09 writes each session's quotes as it finishes, records it in the manifest, and
   emits a counts-only `run_progress`.
2. The importer imports **unclustered** quotes for quoted sessions. Clusters are the only
   import path today (`importer.py`, `_import_quotes_from_clusters`), so this is a new
   reader of the per-session quote output, and `_cleanup_stale_data` must not retire
   join-less quotes during a run. The quotes route serves join-less quotes only when
   pinned (`routes/quotes.py`); before `joined` it must serve them grouped by session. The quote's
   stable key `(project, session, participant, start_timecode)`
   (`importer.py`, `_get_or_create_quote`) is unchanged at the barrier, so stars,
   hides and tags made before it survive it. Gate test for exactly that.
3. Quote exclusivity (`bristlenose/stages/CLAUDE.md`) is a sections-and-themes
   invariant; before the barrier every quote sits in its session's group.
4. Quotes lens: a By session grouping (`QuoteGroup` per session; the
   group-by-session pattern already exists in `ProposalZoneList.tsx` and
   `AutoCodeReportModal.tsx`). The grouping control appears at `joined`, in
   `.section-heading-action`. Remembered per project as a per-viewer convenience.
5. The grouping control's two strings are new keys, in all 21 locales.
6. Audit every group-level action in By session: moving a quote and renaming a
   heading are off; bulk star or hide per session is yours to decide (§7);
   freezing and pinning neither created nor shown.
7. The rail's Quotes turns normal at the first session with quotes.
8. The sparkline fills per session.

### Phase 3 — Pipelining topics and quotes per session (speed)

Topic segmentation and quote extraction join the per-session chain, so a session's
LLM calls run while the next session is in Whisper. Whisper is local GPU and the
quote calls are network: they do not compete. FOSSDA's projection: barrier at 38:56
instead of 51:22. This is the "per-participant chaining" `design-perf-fossda-baseline.md`
already anticipates. Independent of the UX; can land before or after phase 2.

### Phase 4 — Session tapestry in layers

1. `toggleTapestry(sid, all)` (`SessionsTable.tsx:607`): the open-all set is the
   readable sessions, not every session.
2. The tapestry route (`server/routes/tapestry.py`) returns what exists. Its shape
   already allows a missing layer: `colour` null, `strip` null, `sections` empty, a
   quote's `section` and `theme` null; `strips_pending` says the strip job is still
   running. No schema change. The component is pinned with `colour` null and `strip`
   null (`SessionTapestry.test.tsx`, and the route without either file in
   `test_serve_tapestry.py`); empty `sections`, empty `quotes` and a quote with both
   `section` and `theme` null are still untried in either test file.
3. The scale rule, §4.6, in `utils/tapestryScale.ts`.
4. **The refetch must merge, not replace.** The strip poll already has the rule: a
   poll builds new session objects and `SessionsTable.tsx` keeps the ones the slices
   hold, taking only `strip`, because an open quote popover rests on the quotes
   array's identity (`SessionTapestry.tsx` resets the selection when `session.quotes`
   changes). A `data_version` bump that drove the same fetch as attempt 0 would
   replace every object and close the popover under the reader §1 is for, once per
   session import. Extend the merge to turns, quotes and sections, and gate it: an
   open quote popover survives a per-session import.

#### 4.6 The opening scale

Today: `fitScale(longest, width) = clamp(longest / (width − 96), 1, 4)` s/px, from
the longest *loaded* session, so an open timeline shrinks when a longer one arrives
(FOSSDA at 1280 px: s1's timeline goes from 1000 to 691 px when s2 arrives). The
new rule, fixed at ingest so it never moves:

1. **Leave out outliers either way:** sessions shorter than a quarter of the median
   or longer than 4× it. A minority must not set the scale for the rest; a majority
   moves the median, so stays in. Left-out sessions still draw at this scale.
2. **Fit the shortest that remain** to the usable width: no timeline opens with
   white space on its right, and a single 5-minute first try fills the width.
3. **Cap:** the longest that remain opens at no more than 4× the width; if the
   spread is wider, the cap wins and only the shortest show white space.
4. The shipped **4 s/px ceiling** wins over everything (bites only below a ~220 px
   table). The 1 s/px floor goes.
5. The slider's far end: `min(0.25, fit / 4)`, so there is always room to zoom in.

The mockup's `fitShortest` is the reference implementation. Checked at a 1280 px
window (906 px usable):

| Project | Scale | Shortest | Longest |
|---|---|---|---|
| One 5-minute first try | 0.33 s/px | 1.00× | 1.00× |
| One 5-min test + three 60-min | 3.97 s/px | 0.08× (left out) | 1.00× |
| Mostly 5-min, one 40-min | 0.33 s/px | 1.00× | 8.00× (left out) |
| Homogeneous 20–60 min | 1.32 s/px | 1.00× | 3.00× |
| FOSSDA | 1.65 s/px | 0.87× (cap wins) | 4.00× |
| Rockclimbing | 0.08 s/px | 1.00× | 3.31× |

Across windows (500 px to 1920 px) for projects of one length: wide and laptop
windows fill with no white space from 5 to 60 minutes; at 1920 every length opens
with labelled turns. At 500 px the 4 s/px ceiling makes 40–60 minute interviews
scroll (1.7–2.5×). Ticks start at 1 minute, so a 5-minute session at 1920 has
ticks 316 px apart (§7).

**Platform transcripts:** a `.vtt`/`.srt`/`.docx` session's duration is not probed at
ingest today (no media). Read it from the last cue's end time at ingest, which is cheap,
so the scale is fixed from the first second; otherwise the scale moves once when those
durations arrive (§7).

Gate tests: the table above, as `tapestryScale` cases.

### Phase 5 — Counts

The split-flap (`N4` in the mockup) needs a visible count during the run. With the
Project lens disabled during the run, there is none until the end (the window
subtitle is a native string and cannot animate). Blocked on §7's Project lens call.

## 5. Scope edges

### 5.1 Re-analyse over an existing report

`page_for` deliberately keeps showing the previous report during a re-run. Progressive
import would replace it session by session. **v1: progressive applies only to a
project with no report yet** (first analysis). A re-analyse behaves as today. An
incremental run (new files) is a later question.

### 5.2 Stop

Stopping mid-run keeps every readable session readable (principle 4). Resume
continues from the manifest's per-session record.

### 5.3 Mixed projects (recordings and platform transcripts)

A platform transcript is readable in seconds, but its participant codes depend on
the earlier sessions' speaker counts. v1 **holds** it until the sessions before it
are readable (state: waiting, not processing). Rockclimbing's recording is s1, so the
measured run never exercises this.

### 5.4 PII

A transcript is never shown before its PII pass. A session is recorded readable in the
manifest only after it.

### 5.5 The chat lens and MCP

Both ground in `server/grounding.py`. Before `joined`, an answer must state coverage
("based on 6 of 10 sessions"), in `INVARIANTS`. Not in phase 1 (neither surface is
usable before the run ends today); required before either is reachable mid-run.

### 5.6 The HTML export

Disabled until the run ends.

## 6. Failure

- **A session's quotes fail** (FOSSDA s3): the row stays readable, the sparkline
  shows "—" once quotes are back, and the barrier waits for it. How the failure is
  *said* is M4 (§7).
- **A session's transcription fails:** the row will never be readable. Not one of
  the three states (§7).

## 7. Open

1. **Row treatment A or B.** A: rows that cannot open take `--bn-colour-muted` (AA in
   both palettes). B: normal text. Recommendation A. Caveat: in Edo light, muted
   `#4a698a` and accent `#0f5c9e` are close in hue (1.21:1), so A's waiting rows can
   read as links; Edo dark and Default are distinct.
2. **Project lens during the run** — and with it whether the split-flap has a home.
3. **Thumbnail frame:** the 60 s fallback for good, or swap in the transcript-chosen
   frame at readable.
4. **Playback before readable.** The media exists from the first second, and the
   shipped thumbnail and filename both open the player.
5. **With motion off,** the processing row looks like a waiting row (the spec's
   static state). `aria-busy` on it would be new.
6. **Scene strips during a run.** Shipped behaviour defers the strip job until the
   project's latest run ends (`SceneStripJob.start` and the between-sessions check in
   `server/scene_strips.py`), which under progressive means a readable row waits the
   whole run for its strip — 51 minutes on FOSSDA. The decode is about 8 s per hour of
   video; the cost of allowing it alongside Whisper is CPU, not correctness. Either
   "strips arrive at the barrier" or "the job runs per readable session" needs
   deciding with the §3 state model.
6. **Transcription failure** as a fourth row state, and the failed-session message
   (M4).
7. **Messages Q1–Q6:** how chatty (each arrival, milestones, or the count only);
   anything when the app is not frontmost; mixed-project hold vs show; partial
   export; where a failed session's message lives; whether to say that an edit made
   before extraction will not steer it.
8. **Bulk actions per session group** in By session.
9. **Tick steps under a minute** (30 s, 15 s) for short sessions at wide widths.
10. **Platform-transcript durations at ingest** (§4.6): read from the last cue, or accept
    one scale move.
11. **The motion spec's status-line shimmer.** §4.7.1 names the pipeline status line
    as a shimmer target; this design makes it static. Amend §4.7.1. (Nothing ships
    the native status shimmer yet: `SidebarShimmerText` is used only in the tuner.)
