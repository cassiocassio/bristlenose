---
status: Phases 0–2 and 4 built 12 Oct 2026 (unreleased), whole-feature review fixed 13 Oct (§5.7); Phase 3 deferred behind §7 item 17; Phase 5 blocked on the Project lens call
last-trued: 2026-10-13
trued-against: HEAD@main on 2026-10-13 (c6b9890d plus the review's fixes)
owner: run progress across the pipeline, the report server, the SPA and the Mac app
mockup: docs/mockups/progressive-lenses-replay.html
---

## Changelog

- _2026-10-13_ — Whole-feature review (correctness, privacy, silent failures) and
  its fixes: §5.7 is the as-built record. §5.1, §5.2, §5.4–§5.6 point at it. §7:
  items 12 and 15 carry what was built; item 18 (a Mac Re-analyse is a first
  analysis) and item 19 (the Mac on a withheld lens) are new.
- _2026-10-12, late_ — Phase 2 built: as-built note replaces its build plan. Phase 3
  deferred behind §7 item 17, with the reason (the backend blocks the event loop, so
  chained quote calls would slow the run). §7: the duplicated item 6 renumbered (the second 6 and
  everything after it go up by one, to 7–17); items 1, 9, 15 and 16 carry what was built provisionally. §2
  and Phase 4 item 5: scene colours arrived at the barrier, not after the turns.
  Front matter says what is built.
- _2026-10-12, later_ — Phase 4 built: option-click, the scale rule, the refetch merge
  and scene colours per session; as-built note under Phase 4.
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
  theme spans** at the barrier. These are real turns, not a skeleton. (Under
  redaction there is no per-session chain, so scene colours arrive at the barrier.)
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

> **Built 12 Oct 2026** — `3f1bd013`, `0a366b3c`, `0fbb8f68` and the Swift commit
> after them (`git log --grep "progressive lenses phase 0"`). Inert for users: the
> server reports every lens available and `app.state.progress` stays `None` until
> Phase 1, so the only visible change is step 1's fix. What changed against the
> plan below:
> - **Step 1** landed as WS1 steps 1–4 and 7 of the lifecycle plan (the handoff in
>   the maintainer's private notes); steps 5–6 (the `status` resolver, `_auto_render`'s
>   input dir) and WS2 belong to the lifecycle sessions. One finding from the WS1/WS2
>   session's mutation pass: reverting `db.py` alone stays green, because the
>   `setup_logging` call in `create_app` also creates the output folder before
>   `db_url_for_project` runs; only reverting both turns the scenario test red.
> - **Step 4 moved to Phase 1, narrowed.** The reload at run end also clears the
>   remembered session route, because a re-analyse can renumber sessions (a
>   remembered `s3` would restore to a different participant). So it cannot simply
>   be switched off. In Phase 0 the SPA is never mounted during a first analysis,
>   so there is nothing to gate; Phase 1 skips the reload only for a progressive
>   first analysis, and keeps it for a re-analyse.
> - **Step 6:** the theme has no disabled tier distinct from the inactive tab's
>   muted text, so a disabled web nav tab looks like an inactive one at rest
>   (it refuses the hover and the pointer). A design call (§7).
> - **Step 5** is wired, not only declared: `detect_status` reads
>   `app.state.sessions_imported`, a server fact Phase 1's per-session import sets.
>   It was first wired to the progress overlay, but a session is readable in the
>   manifest before its rows reach the database, so the status page would have
>   stepped aside to an empty grid (review).
> - **`data_version` moves only on a per-session import, never at run end.** The
>   first build bumped it after every import, so at run end `/last-run` and
>   `data_version` both moved and every lens refetched twice (review). With no
>   per-session import until Phase 1, nothing moves it today.
> - **A visible side effect of step 1:** selecting a never-analysed project now
>   creates an empty `bristlenose-output/` in the interview folder, where the old
>   (forking) behaviour left a hidden `.bristlenose/`. Nothing misreads it (the
>   Mac's "is this analysed?" checks need the manifest; `run` reuses a folder
>   holding only `.bristlenose/`); `bristlenose status` says "No pipeline manifest"
>   rather than "No pipeline data found". The CHANGELOG entry carries the caveat.
> - **Owed from the review, for the lifecycle sessions:** a database written by
>   `serve <p>/bristlenose-output` under the old resolver holds rows keyed
>   (output, output) and forks under the new key; the importer must also match
>   that legacy shape (taken by the WS1+WS2 session).

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
4. **No cold reload at the end of the run.** *(Moved to Phase 1, narrowed to first
   analyses: see the note above.)* `scheduleReportReloadOnCompletion`
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

> **Built 12 Oct 2026** (`git log --grep "progressive lenses phase 1"`). What
> landed, and what changed against the steps below:
> - **The chain** is `bristlenose/readable_chain.py`, fed by `_gather_all_segments`
>   (which now always consumes `iter_transcribe_sessions`). Per session, in session
>   order: incremental `session_segments.json`, the speaker pass
>   (`bristlenose/speaker_pass.py`, shared with stage 5b), codes, merge, the
>   transcript files, then the manifest's `merge_transcript` record and a
>   `run_progress` line carrying `sessions_readable`. Stage 5b reuses each session
>   through the speaker cache (no second LLM call); stage 6 reuses the chain's
>   paragraph rule and marks merge per session. Speaker passes start on hand-over
>   and run concurrently; only delivery takes turns, so a project of platform
>   transcripts is not slower than the batch. **A failed delivery stops the
>   chain** — the rest go to stage 5b — because delivering N+1 past a failed N
>   would number N+1's participant first, and the registry keeps codes.
> - **On only for a first analysis with every session this run's**: off when the
>   previous manifest has a finished render, when any session is cached at
>   transcription (a resume), under redaction, and without intermediate files.
>   **Under redaction stage 6 writes no per-session merge records either**: those
>   files are the unredacted ones (review — the server would have shown them for
>   the rest of the run). The per-session importer also reads the redacted folder
>   first, as the whole import does.
> - **Steps 4, 5, 7, 8 partly deferred.** Thumbnails and scene colours stay at
>   render; PII is not per session (so redacted runs are not progressive yet);
>   `ingest-facts.json` records `has_video` by extension, not by the probed stream,
>   and the waiting row shows no thumbnail placeholder. Timing: the chain's wall
>   time is moved from transcription to speakers in the CLI lines and the Welford
>   actuals.
> - **Server:** `server/progressive.py` follows the manifest from the watcher's
>   `on_change`; one session per transaction, a session that will not import is
>   said once at WARNING and left to the whole import; `sessions_imported` comes
>   from what the database holds (a serve restarted mid-run must not cover its
>   imported sessions with the in-progress page); the overlay lasts until the
>   `run_completed` import has published. Export is refused (409) and its menu
>   item disabled while the overlay is set.
> - **Grid:** a row the database holds is always readable (progress only moves
>   forward); the rest come from ingest facts. Treatment A (muted) is built — one
>   CSS rule, reversible if §7 settles on B. Known limitation: "processing" is
>   the first unread transcribing session after the last readable one, so a
>   Whisper failure keeps the shimmer on the failed session until the next one
>   is delivered.
> - **Mac:** the shoal gives way at `sessions_readable ≥ 1`; the completion
>   reload is skipped only for a progressive run that succeeded under a live SPA.
> - **Not done:** the folder-of-horrors acceptance walk through the app.

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

> **As built, 12 Oct 2026.**
> - **Pipeline.** `extract_quotes` takes `on_session_done(sid, quotes)`
>   (`s09_quote_extraction.py`), called once per session that succeeded, zero quotes
>   included, never for a failed one; a callback that raises is logged and the
>   extraction goes on. Stage 9's fresh branch (`pipeline.py`, `_deliver_quotes`)
>   rewrites `extracted_quotes.json` (cached sessions plus those delivered so far),
>   then records the session complete and writes the manifest: file before record.
>   It runs on every run, not only a first analysis, so a crash mid-stage resumes
>   from the sessions already recorded. `write_intermediate_json` is now atomic
>   (temp file, then replace), so a reader never sees half a file; on Windows,
>   where a replace fails while the server has the file open, it retries briefly
>   and then writes in place as before.
> - **Redacted runs.** Stage 7 records each session it redacted (`pii_removal`, per
>   session). While that stage record exists, readable means redacted
>   (`lens_readiness.readable_in_manifest`), so a redacted run's sessions arrive
>   together at the end of redaction, then quotes per session. Unredacted text is
>   never imported.
> - **Server.** `ProgressiveImport` follows `quote_extraction` too
>   (`lens_readiness.quoted_in_manifest`). For a session recorded there whose
>   session row is already in the database, `import_session_quotes` (`importer.py`)
>   reads its quotes through `_get_or_create_quote` — the stable key, so curation
>   survives the whole import — and never deletes. A quote for a session not yet
>   imported waits. One session per transaction; a session that fails is not asked
>   again during the run. `Progress.quoted` is the sessions with at least one
>   imported quote, so a session with none does not light the Quotes lens.
>   Every session a run delivers takes one `first_imported_at` (`run_stamp`), so
>   the sessions of one first analysis are not "New" to each other. A manifest
>   created before the run started is the previous run's (the pipeline first
>   writes its own after ingest) and reads as nothing yet, so a re-run of a failed
>   first analysis does not import its predecessor's sessions or quotes, which may
>   be unredacted or at old timecodes.
> - **The barrier.** `joined` stays false until `run_completed`: the whole import
>   then builds sections and themes, and the overlay ends. The overlay is kept until
>   that import finishes, so the lens never shows sections before they exist.
>   Signals, and with it the grouping control, waits for that import even once
>   the cluster files exist (§2: Signals at the barrier).
> - **Route.** `GET /quotes` returns `unjoined`: quotes in no section or theme and
>   not on the floor, ordered by session and time. A whole import retires
>   join-less quotes, so a finished report has none; a first analysis that fails
>   or is stopped after extraction keeps them, and the researcher reading By
>   session keeps reading them. (Gating on the overlay, as first built, made
>   them vanish the moment such a run ended.)
> - **Quotes lens.** `islands/QuoteSessions.tsx` groups every quote the route
>   returns — sections, themes, `unjoined`, the floor — by session, each quote once,
>   one `QuoteGroup` per session with `itemType="session"`: the heading is the
>   dashboard's `Session N`, not editable, no description. While Signals is not
>   ready (`lenses.signals`) the lens shows only this grouping and no control. After
>   it, `islands/QuoteGroupingToggle.tsx` — two `toolbar-btn toolbar-btn-toggle`
>   buttons in `.section-heading-action` — switches between *By session* and
>   *Sections & themes*, remembered per project in `localStorage`. Default: Sections
>   & themes. A researcher reading during the run stays By session when sections
>   arrive, until they pick (§2: themes arriving never move them); that is the
>   visit's state, and only a click on the control is remembered. By session holds
>   the floor's quotes in their sessions (exclusivity in this grouping), so the
>   floor's "needs a home" heading is a Sections & themes view only. Three new keys
>   (`quotes.groupBy.{label, session, sectionsAndThemes}`) in 21 locales.
> - **Floor quotes seed the store** (`QuotesContext.initFromQuotes`). Every write is a
>   full-map PUT, so a floor quote missing from the maps lost its star, hide, tags
>   or edit on the first gesture anywhere. Latent before Phase 2; reachable once a
>   lens other than Sections drew the floor's quotes.
> - **Group actions (§7 item 9, provisional):** none per session group. Moving and
>   heading edits do not exist in this grouping. Freezing and pinning are neither
>   created nor shown.
> - **Not built:** the counts-only `run_progress` from s09 (step 1) — the server
>   reads the manifest, and nothing on the Mac reads a quote count during the run;
>   the sparkline (step 8) fills from the quotes as they arrive with no change.
> - **Accepted for v1:** every per-session import refetches the lens (replace, not
>   merge), as the Sessions grid does; a Signals deep link into By session lands
>   on the lens without scrolling; quotes stage 10 drops are silent, as before.
> - **Gate tests.** `tests/test_progressive_quotes.py`: the manifest reads under
>   redaction; a quoted session lights the lens and moves `data_version` once;
>   zero quotes do not light it; quotes wait for their session; a star and a tag
>   made during the run survive the whole import; `on_session_done` fires only for
>   succeeded sessions; one run's sessions are not New to each other; quotes stay
>   served when a run ends without the whole import; the previous run's manifest
>   is not this run's; an intermediate write survives a refused replace.
>   `test_progressive_lenses.py`: each session's quotes are on disk before the
>   manifest records them. Vitest: `QuoteSessions.test.tsx` (grouping, headings,
>   control, persistence), `QuotesTab.test.tsx` (forced during the run, kept after,
>   not remembered),
>   `QuotesContext.test.tsx` (floor quotes seed the maps). The floor seeding, the run
>   stamp, file-before-record, the route without the overlay gate, the manifest age
>   check and the unremembered grouping were each proved red on a mutant of the fix.

### Phase 3 — Pipelining topics and quotes per session (speed)

Topic segmentation and quote extraction join the per-session chain, so a session's
LLM calls run while the next session is in Whisper. Whisper is local GPU and the
quote calls are network: they do not compete. FOSSDA's projection: barrier at 38:56
instead of 51:22. This is the "per-participant chaining" `design-perf-fossda-baseline.md`
already anticipates. Independent of the UX; can land before or after phase 2.

> **Deferred, 12 Oct 2026, behind §7 item 17.** The projection assumes the quote calls
> run *while* Whisper decodes the next file. They cannot today: `transcribe_sessions`
> calls the backend synchronously on the event loop (`s05_transcribe.py`, the
> `transcribe_fn(...)` call in its session loop), so a coroutine started between files
> makes no progress until the next file is decoded. Putting topics and quotes in the
> readable chain as it stands would add their latency between Whisper files — the
> run gets *slower*, the opposite of the phase's point. The owner chose to keep
> Whisper serial for now (item 17), which is the change this phase needs. When that
> is revisited, Phase 3 is: the backend in a worker thread, the chain's speaker pass
> followed by `segment_topics` and `extract_quotes` for the one session (both
> already take a session list), and the per-session records Phase 2 writes, so the
> stage-9 batch skips what the chain already did. Phase 2 already delivers quotes per
> session as stage 9 finishes each one, so the visible half is in; only the wall
> time is left.

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
5. **Scene colours per session.** `extract_scene_colours` runs in `Pipeline.run`
   just before render, after clustering (`pipeline.py`, "Scene colour per speaker
   turn"), so under progressive the colour layer arrives at the barrier with the
   sections. §2's order needs it in the readable chain: it is keyed by video and
   turn boundaries, about 1.5 s per hour of video, and both are known once a
   session is readable.

> **As built, 12 Oct 2026.**
> - **Option-click** (`SessionsTable.tsx`, `toggleTapestry`) opens the rows whose
>   state is readable; a row readable later arrives closed.
> - **The route** needed nothing: during a run a readable session comes back with
>   turns, empty `sections` and empty `quotes`, then with quotes whose `section` and
>   `theme` are null (`test_progressive_quotes.py`, through the real follower).
> - **The scale** (`utils/tapestryScale.ts`, `fitScale(durations, width)`) is §4.6's
>   rule, from every row's ingest `duration_seconds` — a platform transcript's from
>   its last cue (§7 item 11) — so it is fixed from the first second; a duration of 0
>   is left out. The six table rows are cases in
>   `SessionTapestry.test.tsx`. `zoomScale`'s far end is `min(0.25, fit / 4)`.
> - **The merge** (`utils/tapestryMerge.ts`) folds every refetch — a session imported,
>   a speaker write, a strip poll — into what the slices hold: a layer whose content
>   is unchanged keeps its reference, and a session with nothing changed keeps its
>   object. Gated: an open quote popover survives a session arriving. The existing
>   strip-poll test could not fail (its mock returned the same objects every call);
>   it now clones per answer, and both go red on a replacing grid.
> - **Scene colours per session** (item 5): the readable chain runs
>   `extract_scene_colours` for the one session after writing its transcript and
>   before recording it merged (`readable_chain.py`), so the row arrives with its
>   colours; the pass before render then finds them cached. A colour failure is
>   logged and the session is delivered. Not for redacted runs, which have no chain.
> - **The merge's idle cost**: a held layer's serialisation is cached by reference,
>   and a refetch that changed nothing returns the same record, so an idle strip poll
>   re-renders nothing (`tapestryMerge.test.ts`).
> - **Accepted:** a zoom saved before the change (sessionStorage, this tab) reopens at a
>   different scale once, since both ends of the slider moved; double-click resets it.
>   With two sessions more than about 7× apart the shorter is left out, which is the
>   rule as written (§4.6 step 1) even when it is not a test file. Option-click selects
>   by row state, the §2 rule, rather than by having a timeline (the same set today).

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
incremental run (new files) is a later question. **But** the Mac's Re-analyse passes
`--clean`, which stashes the report: to the pipeline and the server that run is a
first analysis, so it is progressive (§7 item 18).

### 5.2 Stop

Stopping mid-run keeps every readable session readable (principle 4). Resume
continues from the manifest's per-session record. As built, the cancelled status
page covers them (§7 item 15); what an SPA still open shows is in §5.7.

### 5.3 Mixed projects (recordings and platform transcripts)

A platform transcript is readable in seconds, but its participant codes depend on
the earlier sessions' speaker counts. v1 **holds** it until the sessions before it
are readable (state: waiting, not processing). Rockclimbing's recording is s1, so the
measured run never exercises this.

### 5.4 PII

A transcript is never shown before its PII pass. A session is recorded readable in the
manifest only after it. The server's three locks on the same door are in §5.7.

### 5.5 The chat lens and MCP

Both ground in `server/grounding.py`. Before `joined`, an answer must state coverage
("based on 6 of 10 sessions"), in `INVARIANTS`. Not in phase 1 (neither surface is
usable before the run ends today); required before either is reachable mid-run.
Built 13 Oct 2026, once Phase 2 made quotes reachable mid-run (§5.7).

### 5.6 The HTML export

Disabled until the run ends. Refused (409) by the server while the overlay exists,
including after a run that ended without a whole report (§5.7).

### 5.7 As built after the whole-feature review (13 Oct 2026)

Three reviews read Phases 0–4 end to end: the seams between phases and the run's
lifecycle, the PII boundary, and swallowed errors. What they found, and what changed.
Every fix has a test that goes red when the fix is reverted.

**PII.**
- A session already in the database when the run calls it readable is re-read from
  the redacted copy (`import_readable_sessions`, `rebuild_session_paragraphs`), so its
  edits are re-made on redacted text. Before, an unredacted import from an earlier
  run (redaction off, failed) or from a serve started before stage 7 was kept, and
  served as readable, until the run's end.
- A serve started during a first analysis creates the project row and imports no
  transcripts (`_import_on_startup`): the follower brings each session in when the
  run says it is readable, and the watcher calls it once at start.
- The follower reads the run's own folder: `transcripts-cooked/` when the manifest
  records redaction, `transcripts-raw/` otherwise (`redacting_in_manifest`). A
  redacted copy left by an earlier run is not read.
- "The manifest is the previous run's" compared a `Z` timestamp (events) with a
  `+00:00` one (manifest). Python 3.10 refuses the first and the check failed open.
  Both forms parse now, and a timestamp that will not parse reads as the previous
  run's.

**A run that ends without a whole report** (stopped, failed, or its whole import
failed): the overlay stays, marked `ended` (`progressive.mark_ended`). No row is
processing, the lenses that wait for the whole report stay withheld, the Quotes lens
stays By session, and export is refused with its own message. Before, every lens lit
over a partial database: Quotes showed empty sections and no way to the quotes, and
a partial report could be exported. A failed import left the overlay up with "still
running" for good. A failed `--clean` run that puts the previous report back lifts
the overlay and moves `data_version`, so the SPA refetches.

**Smaller.**
- The New flag: a first analysis's sessions are one generation after its whole
  import (`importer.one_generation`). The run's stamp is its start time, so a serve
  restarted mid-run stamps as the first did.
- An import that raises is tried three times before the session waits for the whole
  report (`_ATTEMPTS`): one "database is locked" while the researcher edits no longer
  hides a session for an hour-long run.
- The Mac's shoal: the redaction stage says `sessions_readable` on a first analysis
  (the chain is off under redaction), so the shoal hands over when the server serves.
- The web nav: a reader on a withheld lens goes to Sessions (`NavBar`, §7 item 12).
  The status page hands over to `/report/`, the Project lens, which is withheld.
- By session: a failed refetch's message clears when the next one answers.
- MCP and the chat lens state coverage (§5.5): `grounding.delivery_coverage`, attached
  to every MCP result as `coverage` and added beside the chat lens's invariants, with an
  invariant telling the model to say it.
- A test that could not fail: the Quotes control with sections and themes now
  asserts the control is passed.

**Known, not fixed.**
- When the chain stops after a failed delivery, the next session shimmers as processing
  until stage 6, while Whisper is further on.
- If the chain counts a session the server refused, the Mac drops the shoal for a
  status page that has nothing to say.
- A progressive run's completion is not announced (`LastRunStore` reads its first id
  as a seed).
- `data_version` restarts at 0 when the serve restarts, so an SPA that last saw the
  same number skips one refetch.
- On a resumed run (the chain off, §7 item 16) the server still imports at stage 6,
  so a browser sees sessions before the end while the Mac's shoal covers them.

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
   read as links; Edo dark and Default are distinct. **Built provisionally as A**
   (Phase 1, `organisms/sessions-grid.css`, `.bn-sessions-row[aria-disabled]`);
   one rule to change if B wins.
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
7. **Transcription failure** as a fourth row state, and the failed-session message
   (M4).
8. **Messages Q1–Q6:** how chatty (each arrival, milestones, or the count only);
   anything when the app is not frontmost; mixed-project hold vs show; partial
   export; where a failed session's message lives; whether to say that an edit made
   before extraction will not steer it.
9. **Bulk actions per session group** in By session. **Built provisionally as
   none** (Phase 2): a session group has no star-all or hide-all; quotes are acted on
   one at a time or through a selection, as everywhere else.
10. **Tick steps under a minute** (30 s, 15 s) for short sessions at wide widths.
11. ~~**Platform-transcript durations at ingest**~~ **Built 12 Oct 2026 (Phase 4):** the
    last cue's end (`readable_chain._last_cue_end`, `.srt`/`.vtt`/`.docx`), so the scale
    is fixed from the first second. Left out: a Word file with no timings, and a file
    still an iCloud placeholder at ingest (reading it would start a download); those
    rows read 0 until imported, and the scale can move once each.
12. **A reader on a lens that becomes withheld** (project switch, Re-analyse): no
    tab reads active, and the route stays. Phase 1 needs a rule. **Built
    provisionally in the browser** (13 Oct 2026): the web nav goes to Sessions
    (`NavBar.tsx`). The Mac is item 19.
13. **The disabled web nav tab's look.** It keeps the inactive tab's muted text
    (there is no disabled tier in the theme); only hover and pointer differ.
14. **The motion spec's status-line shimmer.** §4.7.1 names the pipeline status line
    as a shimmer target; this design makes it static. Amend §4.7.1. (Nothing ships
    the native status shimmer yet: `SidebarShimmerText` is used only in the tuner.)
15. **Stopping a progressive run.** §5.2 says stopping keeps every readable session
    readable; step 11 keeps the cancelled status page, which covers them. Phase 1
    built step 11. Which wins? **Built provisionally as the cancelled page**, so
    the rule is today's: a stopped run shows the cancelled status page, and the
    sessions already imported are in the database for the next run to keep. An SPA
    still open after the stop keeps what was delivered, with nothing processing and
    export refused (§5.7).
16. **Progressive on resume.** A crash at session 6 of 10 turns the chain off for
    the rest (codes fold across the study). The registry already holds the first
    five sessions' codes, so a chain starting at the first uncached session would
    fold correctly. Simplification, or decision? **Built provisionally as off on
    resume** (Phase 1): a resumed run delivers nothing early, which is today's
    behaviour, and the per-session quote records Phase 2 writes make the resume
    itself cheaper.
17. ~~**Serial Whisper.**~~ **Decided 12 Oct 2026: live with it for now.** The chain's
    LLM latency is added between Whisper files (transcription is a blocking call on
    the event loop). Running Whisper in a thread so the next decode overlaps would
    reopen Ctrl-C and the GIL; revisit if the added time is felt on real runs.
18. **A Mac Re-analyse is a first analysis.** It passes `--clean`, which stashes the
    output folder and its report, so the pipeline turns the chain on and the server
    follows the run (§5.1 said a re-analyse behaves as today). Sessions arrive one by
    one where the status page used to cover the run. Two costs: the Mac skips its
    completion reload, so a transcript route remembered from the old numbering stays
    live; and a run that fails restores the stash. The server lifts the overlay and
    moves `data_version` then (§5.7), but nothing on the Mac reacts. Accept (a clean
    re-analyse is a first analysis), or have the pipeline record "progressive" in
    `ingest-facts.json` and gate both sides on it?
19. **The Mac on a withheld lens.** The web nav goes to Sessions (item 12); the Mac's
    lens rail does not. Activate `.sessions` on the same condition?
