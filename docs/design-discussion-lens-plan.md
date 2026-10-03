---
status: pending
last-trued: 2026-10-03
trued-against: HEAD on 2026-10-03
---

# Discussion lens — implementation plan

*How the Discussion lens becomes a first-class part of the Bristlenose
architecture rather than a spike. Companion to
[design-discussion-lens.md](design-discussion-lens.md), which holds the design,
the measurements and the decisions; this file holds the build. Every touchpoint
below was located in the code on 3 Oct 2026 (file:line as of that day).
**SILENT** marks a place where forgetting it leaves every test green while the
behaviour goes missing; those are the ones this plan exists to stop.*

---

## 0. Decisions needed before Phase 1

1. **Channels — DECIDED 3 Oct 2026: both.** The lens ships in the Mac app and
   the CLI's SPA, and in exported HTML read-only. It reverses the July call that
   made it a macOS-only paid lever: the free/paid line is the CLI versus
   multi-project, not individual lenses. The extra work for the web is small
   and sits in Phase 5 — the NavBar entry, the export embed and its
   anonymisation — plus guide input: no upload route exists, so for v1 a CLI
   user places the guide in the reserved location by hand and `bristlenose run`
   picks it up; a browser upload is a later nicety.
2. **Zero or one guide per project — DECIDED 3 Oct 2026.** One slot: adding
   fills it, replacing overwrites it, removing empties it. No guide history,
   no multiple guides per study.
3. **Where the guide file lives — DECIDED 3 Oct 2026: a reserved subfolder** beside the recordings.
   Reasoning kept: It must survive **Re-analyse, which runs with
   `--clean` and deletes the whole output folder** — database and `.bristlenose/`
   included (`cli.py:1241-1263`). The July plan (guide in `.bristlenose/`) would
   lose it. It is an *input*, so it belongs beside the recordings, in a place
   ingest and the folder watcher both skip. Options: a reserved subfolder
   (visible in Finder, replaceable by hand); a reserved filename; or a
   dot-folder (survives, but invisible to the researcher). **Recommend the
   reserved subfolder.**
4. **When the stage runs — DECIDED 3 Oct 2026: on by default** (Merged only with no guide).
   Reasoning kept: It is an LLM stage (≈ $0.18 for three 30-minute
   sessions on Sonnet 4.6, measured). Run it on every analysis by default, or
   only once the researcher opens the lens / adds a guide? **Recommend: on by
   default with no guide (Merged only), cheap enough to always have; a guide
   added later triggers a scoped re-run of this stage alone.**
5. **Session-specific questions — DECIDED 3 Oct 2026: no marking in v1.** ("did you have trouble getting here?"). Merged
   is a record, so they appear (design doc, 3 Oct). Whether the reconcile step
   should also *mark* them, keeping them out of the cross-session structure, is
   open. **Recommend no for v1** (simplicity), revisit with the gold labels.

## 1. The pipeline stage

### 1.1 Shape

One stage, `discussion`, after s11 (thematic grouping), before render. Runs with
or without a guide. **Optional: it never abandons the run** — a failure marks
the lens degraded and leaves the report intact (raising `PipelineAbandonedError`
would kill a good report for an optional view).

Four steps, the LLM judging meaning and code deciding structure (the spike's
lesson: the same guide drew 4, 6 and 5 sections across three runs):

1. **Parse the guide once per guide hash** and persist it — a frozen spine of
   planned sections and items. No guide: skip.
2. **Classify each moderator turn** against the frozen spine: matches planned
   item *N* / ad-lib in section *X* / new-cluster label / not a question. One
   batched call per session, not one call over the whole corpus. Then
   **consolidate** the unplanned residue in one small call across sessions:
   which unplanned questions are the same question, one name per new topic,
   with the planned section titles given for scale.
3. **Code builds the structure**: invented ids dropped (and skipped turns
   counted), the promotion rule (**≥2 sessions, ≥3 asks** — asks, not distinct
   items; measured 3 Oct, §9), sections ordered by median relative time,
   homeless questions placed by flow, standalone. Ported from
   `experiments/discussion-lens/structure.py`, which is tested rule by rule.
4. **Route quotes** by the **conversational anchor** first (the last question
   asked before the quote, fresh within 240 s; code) with the topic (batched
   LLM) as corroboration. The spike measured anchor alone at 0.97 against 0.94
   when a confident topic may override it — see §9.F before choosing the rule.

**Input is the in-memory redacted transcripts**, moderator turns selected by
`seg.speaker_role == RESEARCHER`, after s07. Never `session_segments.json`
(written before speaker codes are assigned, `pipeline.py:1229-1240`, and before
redaction) and never re-parsing `transcripts-raw/*.txt`. **The guide never passes
through s07** — a guide naming a client is unredacted text; say so in the
transparency copy.

### 1.2 Models

- `bristlenose/models.py`, after `ThemeGroup` (`:410`): `DiscussionGuide`,
  `DiscussionStructure` (sections → items; provenance planned/asked/both; role
  opener/closer; **ask-sites as `(session_id, start_seconds)`**, resolved by time,
  never by segment position), `DiscussionRoute` (quote key → section, confidence,
  anchor agreement).
- **Stable ids are new work.** `ExtractedQuote` has no id (`models.py:366`); s10/s11
  route by list index. Key quotes the way the importer does —
  `(session, participant, start_timecode)` (`importer.py:967`). Sections and items
  need ids that survive a re-run: planned items take the guide item's id; asked
  items are matched across runs by ask-site overlap, as themes are by quote
  overlap (`importer.py:1037`).
- LLM response schemas in `bristlenose/llm/structured.py`, beside
  `ThematicGroupingResult` (`:225`).
- `PipelineResult` (`models.py:423`) gains a slot.

### 1.3 Prompts

- Productionise the three spike prompts. **Remove the literal
  `<untrusted_guide>` / `<untrusted_asked>` / `<untrusted_quotes>` tags** and wrap
  at the call site with `wrap_untrusted(name, text)` (`llm/boundary.py:60`), which
  adds a nonce and escapes closing tags. Archive the spike versions to
  `prompts-archive/`.
- Load with `get_prompt_template` (`llm/prompts/__init__.py:73`) and pass
  `prompt_template=` to `analyze`, or telemetry loses the prompt id and sha.
- **SILENT** hand-kept lists: `tests/test_prompts.py:11` `PROMPT_NAMES` and `:20`
  `EXPECTED_VARIABLES`; `tests/test_prompt_boundary.py:29` and `:149`.
- **Language.** Generated labels follow the steer
  (`system_prompt=_tmpl.system + output_language_steer()`, as `s08:166`), and the
  stage joins `tests/test_output_language.py:24` `STAGES` (**SILENT**). With a
  guide, labels should follow the *guide's* language (design doc, open decision
  6) — the steer needs a guide-language override.

### 1.4 Registration — the four stage vocabularies, and the rest

| Where | What | Fails |
|---|---|---|
| `manifest.py:95-118` | `STAGE_DISCUSSION` + `STAGE_ORDER` | loud (`test_manifest.py:75` counts 10) |
| `timing.py:26-51` | `discussion` in `ALL_STAGES` (not `_SESSION_STAGES`) | loud (`test_swift_python_contract.py:264`, `test_run_inspector.py:158,190`); **SILENT** if skipped — time folds into a neighbour, progress freezes on the previous verb |
| `pipeline.py` | `_llm_telemetry.stage("s11b_discussion")` on full and analyse-only paths (`:1880–2227`, `:2719–2812` show the siblings) | **SILENT** — no row in `llm-calls.jsonl`, no cost |
| `llm/pricing.py:326` | id must **not** start `s05b`/`s08`/`s09` (prefix match → billed per session) | **SILENT** |
| `llm/pricing.py:258` | id must match `s<digit>…` or it is ignored | **SILENT** |
| `llm/cohort-baselines.json` | regenerate (`scripts/regenerate-cohort-baselines.py`) | **SILENT** — pre-run forecast omits the stage |
| `server/run_inspector.py:42-53, 76-84` | `STAGE_LABELS` (with `is_llm=True`), progress→manifest map | **SILENT** (only three stages' `is_llm` asserted) |
| `status.py:25, 39, 86, 163-185` | intermediate file, display name, detail line | **SILENT** — `bristlenose status` omits it |
| `pipeline_view/catalogue.py:310-440` | `PipelineStageDef(kind="llm")` | loud (`test_catalogue.py:70` counts 5) |
| `pipeline_view/catalogue.py:584-674` | `_LLM_QUALITY` cells | loud (`test_quality.py:69`) |
| `tests/fixtures/pipeline-view-contract.json` | add the stage | loud |
| Swift `RunProgressSubtitle.swift:30, 64` | `knownStages` (pinned), `nonSessionStages` | **SILENT** for the second — stale "N of M" |
| `locales/*/desktop.json:282-290` | `desktop.chrome.pipeline.stage.discussion` in 21 locales | **SILENT** outside the Swift suite |

### 1.5 Journal and summary

- `events.py:302-330`: `PipelineSummary.discussion: StageOutcome | None = None`.
  Truncation picks it up (`events.py:546`).
- **SILENT**: `run_condition.py:120-121` hard-codes the bucket tuple — a failing
  discussion bucket would not mark the run degraded.
- **SILENT**: Swift `PipelineSummary.swift` property (:19-23), `allBuckets`
  (:27-34), `BucketName` case and label (:82-97). The parity test compares only
  shared fields (`test_swift_contract_parity.py:176`), so Python-only passes.
- Fixture `tests/fixtures/pipeline-summary-contract.json`: bump to v8 and add a
  scenario that *uses* the bucket.
- Copy s09's pattern (`pipeline.py:2150-2180`); the A4 invariants
  (`stages/CLAUDE.md:251-292`): `StageFailure` before any fallback, `Cause.message`
  from `_build_cause` only. Pick one `Cause.stage` vocabulary deliberately (s10
  uses the manifest id, others the module name).
- Progress: `_emit_stage_entry` (`:847`), `_emit_remaining` (`:740`); Welford
  actuals into `_stage_actuals` (`:2250`).
- Lazy `LLMClient` guard (`stages/CLAUDE.md:233`).

### 1.6 Cache and resume

- Writes `.bristlenose/intermediate/discussion.json` (and a parsed-guide file)
  via `write_intermediate_json`. Pass `output_path` to `mark_stage_complete` so
  the empty-output guard applies (cluster+group omits it, `pipeline.py:2292`).
- **SILENT**: `input_hashes` must include the guide file's hash, with a sentinel
  when there is no guide — present from the first release, because a key first
  seen on an old record is not treated as a change (`_inputs_changed :243`).
  Otherwise adding or editing a guide never invalidates the cache.
- Upstream hash: extracted quotes + redacted transcripts. New sessions re-run the
  whole stage, as s10/s11 do — fine at this cost; the frozen spine keeps the
  structure stable across the re-run.
- Wire the three other paths: `run_analysis_only` (`:2633`), `run_render_only`
  (`:3166`), and the importer.

### 1.6a Lifecycle — any order, re-merged on every change

The lens must work in whatever order the study happens: a merged structure
from the first one or two interviews with no guide, a guide uploaded later,
more interviews after that, a guide replaced or removed. Every one of those is
an ordinary incremental run, because the guide's fingerprint and the session
set are both inputs to the stage's cache key (§1.6).

| Event | Re-runs | Cost (Sonnet 4.6, measured ≈ $0.06 per session) |
|---|---|---|
| Interviews, no guide | classify each session, structure in code, route quotes | ≈ $0.06 per session |
| Guide added | parse once, re-merge all sessions, re-route | whole stage + one small parse |
| More interviews | the whole stage (v1) | ≈ $0.06 per session in the study |
| Guide replaced | as added | as added |
| Guide removed | re-merge with no guide | whole stage |

Three requirements that make a re-merge feel stable rather than reshuffled:

1. **Identity across runs.** Planned sections are anchored to guide items.
   Emergent sections are matched to the previous run's by ask-site overlap,
   the way themes are matched by quote overlap (`importer.py:1037`), so a new
   interview does not rename and reorder the navigator.
2. **Overrides across a guide swap.** Researcher edits key on item ids, and a
   new guide brings new planned ids. Re-attach by ask-site where possible;
   **show** the researcher any that cannot be re-attached — never drop them
   silently.
3. **Say what it rests on.** The header states the number of sessions the merge
   is built from. With one session the promotion rule (≥2 sessions) cannot
   apply at all, and an early merge must not read as settled.

**Optimisation path, not v1:** classify only new sessions against the frozen
spine (per-session cache, as s08/s09 do), plus one small corpus-level call to
reconcile their new-cluster labels with the existing emergent sections; re-route
only quotes whose section could have changed. Worth it when studies are large;
at ≈ $1.20 a pass for 20 sessions the whole-stage re-run is fine.

### 1.7 Ingest must not eat the guide

Today **a `.docx` guide becomes a fake interview**: `classify_file`
(`models.py:122-143`) treats `.docx` as a transcript, s04 falls through to plain
paragraphs (`s04_parse_docx.py:191, 346`), and its questions are extracted as
quotes. A `.md`/`.txt` guide is refused as unsupported and lands in
`summary.ingest.failed`. Fix both sides together:

- `s01_ingest.py`: skip the reserved guide location (decision 0.3).
- Swift `ProjectFolderWatcher.swift:142-159` `eligibleExtensions` and
  `ContentView.swift:1701` `acceptedExtensions`: skip it too.
  `tests/test_accepted_extension_parity.py:50,59` holds the two lists together.
- Correct the stale comment at `ContentView.swift:1699` (Python does not accept
  `.txt`).

## 2. Data and serve

### 2.1 Tables (all per-project, `project_id`)

`discussion_guides`, `discussion_sections`, `discussion_items`,
`discussion_ask_sites` (session, start seconds), `discussion_quote_routes`
(FK `quotes.id`), `discussion_overrides`. Migration `012_discussion` in
`server/alembic/versions/`, tables guarded with `_has_table`
(`002_tag_prompts.py:29-36`).

- **SILENT, and the most dangerous**: stale-quote and stale-session deletion use a
  hand-written table list (`importer.py:1774-1802`, `1870-1925`). A routes table
  missing from it makes every re-import that drops a quote fail on a foreign key,
  and the failure is only logged (`app.py:1118`) — the UI quietly keeps old data.
- Ask-sites key on **time, not segment position**: segments are deleted and
  re-inserted on every import (`importer.py:612`).

### 2.2 Import

`_import_discussion(...)` in `import_project` (`importer.py:202`) after
quotes/themes (`:357-362`), before `_cleanup_stale_data` (`:374`). Copy the
established survival rules: pipeline rows and researcher rows kept apart
(`created_by`), sections matched across runs by membership overlap, researcher
overrides keyed on durable ids, never on labels.

- **Do not store renames in `HeadingEdit`**: `PUT /edits` replaces the whole map
  from what the Quotes page sends (`routes/data.py:413-457`,
  `QuotesContext.tsx:205-225`), so the next Quotes save would wipe them. Use
  `discussion_overrides`.
- Re-analyse (`--clean`) deletes the database, so overrides die with it — the
  same as every other researcher edit today. Not this lens's problem to solve,
  but name it in the lens's copy if overrides become substantial.

### 2.3 API

- `routes/discussion.py`, shaped like `routes/quotes.py`: `APIRouter(prefix="/api")`,
  Pydantic response models, `_get_db` with `try/finally`, pipeline label **and**
  override label per row. Register in `app.py:34-52, 229-245`.
- `GET /api/projects/{id}/discussion` returns the structure, the guide, each
  session's linked turns **with their verbatim text**, and per-question quote ids
  — one request. Don't build on `get_moderator_question`: one fetch per quote
  (`api.ts:302`), and it needs `segment_index`, which is −1 for untimed
  transcripts (`quotes.py:606`).
- A `status` field for the lens's own states: not run / no guide / guide failed
  to parse / ready. `run_condition.py` is run-level only; AutoCode's status route
  is the precedent for per-feature state.
- `PUT /api/projects/{id}/discussion/overrides`.

### 2.4 Export and MCP

- Every new GET goes in `EMBED_PATH_TEMPLATES` or `SERVER_ONLY_PATH_TEMPLATES`
  (`routes/export.py:48-104`), enforced by `test_serve_export_coverage.py`. With
  both channels (decision 0.1) the read route is **embedded**, read-only via
  `isExportMode()`.
- **SILENT, privacy**: `_anonymise_data` (`export.py:111-205`) only rewrites
  endpoints it knows by name — a new key fails open — and never touches text, so
  moderator wording that names a participant ("So, Sarah…") ships as is. Add the
  discussion key to the anonymiser, and make unknown keys fail closed.
- Not in MCP for v1. If ever exposed: extend an existing tool, apply overrides
  and `resolve_speaker_names`, and add an `INVARIANTS` line — discussion sections
  are a second view of the same quotes and their counts never add to section
  counts (`grounding.py:49-63`).

## 3. The SPA lens

- **Routing**: `router.tsx:35-55` (catch-all at `:55` redirects unknown paths
  silently); `shims/navigation.ts:20-33` `TAB_ROUTES` (key = Swift rawValue;
  `test_tab_route_parity.py`); `utils/hashRedirect.ts:11-22` (**SILENT**).
- **Layout arms** in `layouts/AppLayout.tsx` — all **SILENT** fall-throughs:
  `:224-241` match + `showSidebar`, `:745` `leftPanel` (falls through to the Quotes
  TOC), `:751` title, `:375-381` bridge `getActiveTab`, `:410-421` screen-reader
  announcement. `LensSubtitleSync.tsx:22-34`.
- **NavBar** `components/NavBar.tsx:21-27` — `IS_DEV` link first (the Codebook v2
  precedent), real entry in Phase 5.
- **Page**: `main > section > .section-heading` as a direct chain
  (`templates/report.css:106-109`) or it renders 40px low; add a row to
  `e2e/tests/lens-datum.spec.ts:51-56`. h1 per content zone
  (`design-lens-template.md:229-262`); add a variants-table row.
- **Navigator**: modelled on `components/SignalsSidebar.tsx`, in the shared left
  panel (`SidebarLayout.tsx:123-135`, width from `SidebarStore.ts:26-41`). Rows
  use `.toc-heading` / `.toc-link` — the Quotes TOC style, chosen over the Signals
  rows on 3 Oct 2026. In Planned every row carries the solid "planned" dot, so the
  mark explains itself before the researcher switches to Merged.
- **Sticky header — decided 3 Oct 2026.** The two views are named **Normalised
  questions | Your guide** (in that order — the first is the one the lens opens
  on; renamed from Merged | Planned the same day), in the shipped
  `.dimension-toggle` (the Signals inspector's Section | Theme) at its natural
  width. Your guide carries two small native radios, **Summary | Original**: the
  guide's short labels, or its own wording. Each session is the shipped `PersonBadge` with `#N` as its code and the
  participant names as its name half — no session-badge styling of our own, and
  no duration (that stays in the line under the session heading). Names cap at
  two: `Sarah and Mike`, else `Bettina and 4 others` — one new counted string with
  plural forms; the list itself comes from `Intl.ListFormat` in the UI locale
  (`en` is British: no serial comma); the full list goes in the tooltip.
  **Selected = "you are here"** — option C of the badge playground, chosen
  3 Oct 2026 over A (the shipped `.bn-person-badge-highlighted` ring): the
  navigator's own selection vocabulary (`.toc-link.active`), no ring. The `#N` in
  accent, the same mark on that session's badge in every navigator row and on the
  `#N ▾` pull-down; in the header the name half also sits on the selection fill
  (`--bn-nav-selection-bg`) in accent. Not solved:
  with many sessions the header still wraps to a second line — the cap only
  removes the long-names case.
- **Session heading line**: one `PersonBadge` per participant, then duration,
  question and quote counts; it wraps, the counts staying one unit.
- **Non-question turns: hidden by default — decided 3 Oct 2026**, with nothing
  marking where they were. A toggle still shows them; where it lives in the app
  (View menu or lens toolbar) is not decided.
- **Never-asked guide lines: shown by default — decided 3 Oct 2026** (hollow dot in
  Merged, dimmed). A toggle can hide them.
- **Store**: `DiscussionStore` on the `SignalStore.ts` pattern (module-level
  `useSyncExternalStore`, `reset*()` for tests): mode, selected session, focused
  item.
- **Content**: each asked question as the moderator-question row, followed by
  its quote cards. **Extract the row from `QuoteCard.tsx:633-668` into its own
  component; don't flip `moderatorQuestionPill`**, and fix its hard-coded English
  (`more…` `:661`, `Question?` `:711`) on the way. Quote cards via `QuoteGroup` —
  its `itemType: "section" | "theme"` (`QuoteGroup.tsx:144-183`) needs a third
  value and aria-label keys (`test_aria_label_enrolment.py`).
- **Wires** between navigator and content: genuinely new — an SVG layer spanning
  two `SidebarLayout` panes, redrawn on scroll and resize; off-screen ends drawn
  as stubs with chevrons (the mockup's solution). Respect reduced motion.
- **Keyboard — SILENT**: every quote key returns early unless the path is
  `/report/quotes` (`useKeyboardShortcuts.ts:575`), and so does the menu-action
  mirror (`:73`, `:693-698`). Extend both, plus the `[` (`:477-495`) and `z`
  (`:533-551`, must match `focus-mode.css`) lens lists.
- **Responsive — decided 3 Oct 2026**: under the narrow breakpoint, **the session
  column only** — the questions in the order they were asked, with their answers.
  The navigator, the wires and the Planned/Merged switch drop away; the session
  badges stay. (This reverses the earlier "Merged only": the transcript is the
  useful half when only one fits.)
- **Focus is sticky and click-driven — decided 3 Oct 2026.** Nothing reacts to the
  pointer passing over; hover tracing flickered and was dropped. Clicking a
  navigator row (shipped `.toc-link.active`) or a question locks focus — its wires,
  questions and quotes lit, the rest dimmed — until the same thing is clicked
  again or Esc. Focus on a navigator row survives a session switch, so one topic
  can be stepped through every session.
- **Navigator width — decided 3 Oct 2026: up to 60% of the lens**, not the shared
  480px. With many sessions a row of session badges is wide (10 badges ≈ 250px), and
  dragging the split wider is how the researcher gets them back in full; below a
  row's share of the width they collapse to a `#N ▾` pull-down. The SPA shares one
  left-panel width across lenses with fixed 200–480px bounds (`useDragResize`
  `MIN_WIDTH`/`MAX_WIDTH`, `SidebarStore.ts`), so this needs a per-lens maximum
  there — and a decision on whether the Discussion width is remembered separately
  from the other lenses'.
- **Unanswered questions fold forward.** Consecutive questions that drew no quotes
  join the next question that did, as one group (questions, then its quotes);
  groups are separated by the keyline, and the moderator's turn renders as a
  transparent `blockquote.quote-card` so its timecode and text columns align with
  the participants' by construction.
- **Empty state, no guide**: drop target + **Add a discussion guide**. In the
  browser this needs an upload route (there is none today — import is native);
  on the Mac it is the native path below. CLI users can place the file in the
  reserved location by hand.

## 4. The macOS app

- `Tab.swift`: case `:8`, label `:13-21`, `route` `:46-54` (keep the
  `case .x: "…"` shape — the parity test parses it), `hasLeftPanel` `:65-70`,
  `from(path:)` `:77-93` (new prefix before any shorter shared prefix).
- `LensItem.swift:32-41`: the rail row, symbol **`questionmark.bubble`** — chosen
  3 Oct 2026 over `bubble.left.and.bubble.right`, knowing a question mark can read
  as Help. **⌘6 is automatic** —
  `MenuCommands.swift:915-928` numbers from `LensItem.all`.
- `MenuCommands.swift`: `leftPanelKey` `:863-870` (**SILENT** — the View menu says
  "Contents"), `focusModeTabs` `:846`, Quotes-only gates `:836, 900, 1045, 1053,
  1416`.
- `ContentView.swift` `default:` arms (all **SILENT**): count subtitle `:475-485`,
  toolbar label/tooltip `:2327-2347`, search slot `:2528`, search list `:631`.
- `LensAnchor.swift:52-68` (exhaustive — won't compile until handled),
  `WebView.swift:39,51` (Quotes-only key interception), `BridgeHandler.swift:396,
  416, 489, 787`, `LensMemory.restore`.
- **Guide import**: a native drop target and `NSOpenPanel` (with
  `allowedContentTypes`) on the Discussion empty state, copying to the reserved
  location, then a scoped re-run of the discussion stage. Today's intake paths
  (`ContentView.swift:1701, 1767, 1848, 2051, 1169-1191`) all treat `.docx` and
  `.txt` as transcripts.
- **Built 3 Oct 2026 as a preview**: `Tab.discussion` (route
  `/report/discussion/`, no shared left panel, restores to the top), the rail row
  last (⌘6, `questionmark.bubble`) behind `BristlenoseFlags.discussionLens`, which a
  tester switches from Diagnostics ▸ Discussion Lens (Preview). The SPA route opens
  in dev builds and inside the app (`isEmbedded()`); the app has no address bar, so
  the flagged row is the only way in. It still reads the synthetic study.
- **Parking while it is built**: `Tab` case always present; the rail row appended
  behind a flag. `design-feature-flags.md:290-295` recommends an
  `enum FeatureFlags { static var … }`, defaulting off in every configuration —
  never built; build it here. `LensItemTests` assert both states.
- Swift tests that fail loudly: `TabTests.swift:65-67, 100, 117, 138`,
  `LensItemTests.swift:15-17, 28, 51`. **SILENT**:
  `SidebarFitSPAHarnessTests.swift:462`.

## 5. i18n

- `common.nav.discussion`; `desktop.toolbar.discussion` / `.showDiscussion`,
  `desktop.menu.view.showDiscussion` / `.hideDiscussion` (built at runtime by
  `PanelToggle.labelKey`, `SidebarVisibilityFocus.swift:133`); `titlebar.discussion_one/_other`;
  the stage verb; every lens string; aria labels; a `glossary.csv` row.
- 21 full locales; `check-locales.py --strict`, `--stamp` for the new English
  values. **SILENT**: the Swift keys are built at runtime, so
  `test_swift_i18n_keys_resolve.py` skips them and a missing key falls back to
  English (`Tab.swift:25-44`).
- Copy is settled in English first, from the mockup — Merged is a record, never a
  guide (design doc, 3 Oct).

## 6. Tests

**Will fail loudly (good):** `test_manifest`, `test_swift_python_contract`,
`test_run_inspector`, `test_catalogue`, `test_quality`, pipeline-view and
pipeline-summary fixtures, `test_tab_route_parity`, `test_serve_export_coverage`,
`NavBar.test.tsx:76-80` (length 5), `TabTests`, `LensItemTests`,
`test_accepted_extension_parity`, `test_aria_label_enrolment`.

**Won't notice a new lens unless a row is added:** `lens-datum.spec.ts:51`,
`lenses-load-clean.spec.ts:52-58`, `export-file-url.spec.ts:41-46`,
`e2e/fixtures/routes.ts:15-23`, `router.test.tsx:91-96`,
`LensSubtitleSync.test.tsx:37`, `test_prompts.py`, `test_prompt_boundary.py`,
`test_output_language.py`, the importer stale-table list.

**New tests the feature needs:**
- `structure()` rules as pure functions (promotion, flow placement, ordering,
  invented-id drop) — deterministic, no LLM.
- The cache invalidates on adding, editing and removing a guide.
- A guide in the reserved location is never a session (Python and Swift).
- Re-import with a dropped quote does not fail on the routes FK.
- Overrides survive a re-run.
- Export: discussion embed is anonymised; unknown keys fail closed.
- **Quality, not correctness:** a scorer against the gold-label workbook
  (unplanned share, item recall, promotion, section agreement) and the planned
  synthetic corpus with ground truth written first (design doc, "Synthetic
  data"). Paid; `slow`-marked; outside CI.

## 7. Sequencing

Each phase lands on `main` behind the flags and leaves the product unchanged
until Phase 5.

1. **Decisions** (§0) — all taken 3 Oct 2026.
1a. **A serious spike, outside the package.** In `scripts/` and `experiments/` only — no
   change under `bristlenose/`. Build the four-step design for real: the frozen
   spine (parse once, classify turns per session against it), `structure()` as
   tested pure functions, routing with the anchor, and a scorer against the gold
   labels. Exit: the structure holds across three runs of the same input; agreement
   with the researcher's labels meets a threshold agreed before the run (unplanned
   share within ±5 points, section agreement on quotes); cost measured per session.
   Needs the labelling pass on the workbook. Only then does Python in the package move.
   **Status 3 Oct 2026: built in `experiments/discussion-lens/`; all four exit
   criteria pass on a synthetic answer key (README there). Scoring on the real,
   gold-labelled sessions is still owed — the gate stays closed until it passes.**
2. **Pipeline stage, off by default** — models, productionised prompts, stage
   module, the four vocabularies and the rest of §1.4, journal, cache keys, the
   ingest guard. Exit: the stage runs on the real three-session corpus, scores
   against the gold labels, and `bristlenose pipeline` / `status` / the run
   inspector / the cost forecast all show it.
3. **Data and serve** — tables, migration, importer, API, status field,
   overrides, export classification and anonymisation. Exit: a re-run preserves
   overrides; a dropped quote re-imports cleanly.
4. **SPA lens** behind `IS_DEV` — store, navigator, page, wires, keyboard,
   responsive, empty state. Exit: lens-datum and lenses-load-clean green with
   the new rows; usable in a browser on the real corpus.
5. **macOS** — Tab, flagged rail row, menus, guide import, scoped re-run. Exit:
   Swift suite green; guide added in the app re-runs only this stage.
6. **Ship** — i18n across 21 locales, NavBar entry, export embed, flags on,
   design doc trued, a public mockup with synthetic data in `docs/mockups/`,
   CHANGELOG under **New** (a minor bump).

## 8. Reuse, not reinvention

Quote cards, the moderator-question row, `.toc-*` rows, session-id badges, the
section-heading datum, `SignalsSidebar` and `SignalStore` shapes, the importer's
survival rules, AutoCode's per-feature status, `wrap_untrusted`, the output
language steer, `_build_cause`, Welford timing, and the anchor already computed
by `get_moderator_question`'s logic (re-expressed by time). The genuinely new
parts are the stage's structure rules, the guide input, the overrides layer and
the wires.

## 9. Impact and safety review — 3 Oct 2026

Three read-only reviews of this plan against the code at HEAD — impact on the
rest of the app, silent failure, and security/privacy — plus the Phase 1a spike's
measurements. **Verdict: Phase 2 is safe to build behind an off switch once A–D
below are in it. Phase 3 is not safe as written** until C is decided: the
contract the spike inherited carries participant names and the whole guide into
an endpoint the export anonymiser does not know. The dev-gated lens (Phase 4
preview, built the same day) changes nothing a user can reach: a registered
route, lazy chunks outside first paint (202.5 of 220 kB, unchanged set), no
server, Swift or locale change.

### A. Failure must be recorded, and must not hijack project status

The highest risk, found by two reviews independently.

- **Report this stage's failure on the lens, not as a run bucket.** A bucket in
  `run_condition.py` and Swift's `totalFailureCount` (`PipelineSummary.swift:39`)
  turns a provider hiccup in an optional, on-by-default stage into a Partial
  project — and a scoped re-run's terminus then replaces the last report's status
  (`run_condition.py:52, 216-219`; `EventLogReader.swift:264`), hiding real
  transcript failures. Use an AutoCode-style status on the lens.
- **Per-session records.** Mark each session complete or failed
  (`manifest.py:370-402`) so a lost session derives PARTIAL. A stage-level
  `mark_stage_complete` alone repeats the s09 incident (`manifest.py:247-250`,
  `pipeline.py:235-240`).
- **No state may be "absence".** A failed or partial stage needs its own lens
  status (§2.3 lists only not-run / no-guide / parse-failed / ready). Delete
  `discussion.json` when the stage starts and stamp it with the quotes hash it
  was built from, so last run's file is never imported against new quotes. A
  guide that is present but parses to nothing is a failure, not "no guide".
- **Skipped turns are counted and shown.** A turn the model never labelled must
  not default to chat (hidden by default): count it (`unlabelled_turns`) and give
  it a visible "unclassified" kind. Fixed in the spike.

### B. Cost and time forecasts must grow with the study

- Give the classify step its **own telemetry id with a per-session prefix**
  (`pricing.py:326, 360`) and add it to `timing.py`'s per-session stages. One id
  for parse + N classify + consolidate + route counts once per run, so the
  forecast falls further short as studies grow — for spend that is on by default.
- `timing.py:305, 340` needs a skip-when-off branch, like PII.
- **The off switch does not exist yet**: a `config.py` field (pattern:
  `pii_enabled`, `:188`) plus an environment variable from Swift (pattern:
  `PIIModelPack.swift:102`).

### C. Privacy and export — decide before Phase 3

- **Codes, not names, in the payload.** The discussion GET returns speaker codes
  only; the SPA takes names from `/people`, which `_anonymise_data`
  (`server/routes/export.py:111-205`) already blanks. The dev lens already
  resolves names in one function for this swap.
- **The guide is not all evidence.** Store titles only for `instruction`
  sections (consent, logistics, welfare). Never return a guide path. In an
  anonymised export, leave out the guide's filename and its never-asked lines,
  and say in the export copy that the guide is included. Removing the guide
  deletes its rows and its parsed intermediate.
- **Gate the anonymiser like the route list.** A test that fails when an
  `EMBED_PATH_TEMPLATES` entry declares no anonymiser handling — and note that
  `test_serve_export_coverage.py` checks classification only, not that the
  assembly at `export.py:418-500` actually calls the handler.

### D. Prompt safety

- **No `fill()`.** The spike's repeated `str.replace` re-scanned substituted
  text (fixed there, single pass); production uses `get_prompt_template`
  (`llm/prompts/__init__.py:108`) and `.format`.
- Add all four prompt ids to `PROMPTS_WITH_BOUNDARY`
  (`tests/test_prompt_boundary.py:29`) and every untrusted keyword — guide,
  spine, turns, planned, questions, sections, quotes — to `CALL_SITES` (`:149`).
  Model output fed to the next step (spine, topics, section list) is untrusted
  too, and stays wrapped.
- Clip over-long labels rather than fail a call (one field must not fail a
  session); log the exception type, never `str(exc)` — a `ValidationError`
  prints guide text into `bristlenose.log`.

### E. The guide's location and the paths that cannot see it

- Put the reserved-folder exclusion in `is_bristlenose_artefact`
  (`utils/fs.py:75`) so every scan site gets it — ingest scans three levels deep
  (`s01_ingest.py:99, 207`) and the importer has its own scan (`importer.py:504`).
- **Existing projects:** a guide `.docx` already in a project was ingested as a
  session. Moving it to the reserved folder makes the stale-session path
  (`importer.py:1870-1925`) delete that session and its edits — write the
  migration note.
- The Mac folder watcher looks at the top level only (`ProjectFolderWatcher`
  `filterEligible` `:343-353`), so a guide replaced by hand in Finder is never
  noticed — decision 0.3's "replaceable by hand" has no trigger on the Mac.
- `bristlenose analyze` (`cli.py:1487`) gets a transcripts folder, not the
  project, so it cannot find the guide; it also re-parses `.txt`, so §1.1's
  "never re-parse" cannot hold there.
- Untimed `.docx` transcripts (`s04_parse_docx.py:355`) give no moderator turns
  and a meaningless anchor: a per-session "no timing" state. A guide in a cloud
  folder may be dataless (`utils/fs.py:108`).

### F. Routing — what the spike measured

- **Anchor first.** On the synthetic key the anchor alone placed 0.97 of quotes;
  letting a confident topic override it, 0.94. Measure on the real sessions
  (where July's anchor agreed with the topic on 69 of 101) before fixing the rule.
- A quote anchored to a **standalone** question loses its anchor (the spike's
  `section_of_item` excludes standalone items) — give standalone an explicit
  route. Show an Unrouted bucket and assert routed + unrouted equals the count.
- **Quote identity drifts**: the importer matches on exact float timecodes
  (`importer.py:977-988`), so a re-extraction at 63.2 instead of 63.0 orphans a
  route. Count unmatched route keys at import and expose the count.

### G. Corrections to this plan

`get_prompt_template` is at `llm/prompts/__init__.py:108`, not `:73`;
`ContentView.swift` citations moved ~21 lines on 3 Oct (`acceptedExtensions`
`:1722`, intake paths `:1160/:1196/:1736/:1788/:1803/:2072`, toolbar
`:2347-2367`); `_emit_stage_entry`/`_emit_remaining` are `:848/:741`;
`--clean` (`cli.py:1242-1265`) now stashes the output aside rather than deleting
it — a guide outside `bristlenose-output/` survives either way. About 70 other
citations held.

### What the dev-gated lens does and does not settle

Built 3 Oct 2026 in `frontend/src/islands/discussion/` (route
`/report/discussion`, NavBar link under `IS_DEV`). It settles the screen: the
navigator, the sticky header with person-badge sessions and the "you are here"
mark, the session column with questions folding forward, sticky click focus,
wires, the 200px–60% split, the narrow layout, page scroll like every lens. It
does **not** settle: the shared left panel (`SidebarLayout`, 480px cap — the
lens uses its own column so it can reach 60%), quote cards with actions (they
arrive with `QuoteGroup` once quotes have store ids), the macOS `Tab`, locale
keys (English until Phase 6), and the screen-reader announcement for this route
(falls through to "Project", as Specimen does).

**Reviewed the same day** (code, accessibility, design system) and fixed: kept
out of exported reports by an alias stub (the export inlines every dynamic
import — the same leak the locale files had) and redirected outside dev; badge
rows that flickered between full and collapsed; digit keys acting under an open
dialog; focus shown by the shipped active and selection styles instead of
opacity (which took readable text to ~2:1); arrow keys in both radio groups;
provenance and "not asked here" in words; session and focus changes announced;
navigator titles as headings; the shipped `.drag-handle`; no Planned view
without a guide; unclassified turns shown; state kept across a lens switch. The
person badge's highlight ring is now inset in shipped CSS — the split badge
clips its overflow, so the old outer ring showed as a sliver.

**Left open, deliberately:** quotes are matched to questions by time, not by
the record's `after_item` (an item asked twice in a session makes that key
ambiguous; recomputing guarantees no quote is dropped) — decide when Phase 3
fixes the key; a quote after an instruction or chat turn folds into the
previous question, which is wrong after a task instruction; one Tab stop per
badge makes a long Tab path through a big guide (roving tabindex inside the
navigator is the fix); the app-only top bleed is written but unverified in the
app; bare digit keys share the house-wide WCAG 2.1.4 exposure.
