# Pipeline Resilience & Data Integrity

> **Status**: Phase 0–1e implemented (crash recovery, per-session caching, `bristlenose status` command, pre-run resume summary); Phase 2 (hashing + integrity) next
> **Scope**: Big-picture architecture for crash recovery, incremental re-runs, provenance tracking, human/LLM merge, source material change detection, mid-run provider switching, and analytical context preservation
> **Trigger**: Plato stress test (Feb 2026) — pipeline ran out of API credits mid-run, stale SQLite data from previous project leaked into serve mode, intermediate JSON files weren't written by `analyze` command, recovery required re-spending $3.50 on LLM calls already made

## The problem

People force-quit processes. Internet connections to LLMs drop. API credits run out halfway through a run. Right now, Bristlenose treats every run as all-or-nothing: if it's interrupted, the user must pass `--clean` (which deletes everything) and re-run from scratch — re-transcribing audio, re-extracting quotes, re-spending money on LLM calls that already succeeded.

The current pipeline has **no checkpointing, no resume, no integrity verification, and no provenance tracking**. The `analyze` command doesn't even write intermediate JSON for its later stages (a bug discovered during the Plato run). The serve-mode SQLite DB is global (`~/.config/bristlenose/bristlenose.db`), so stale data from previous projects leaks across sessions.

### What we need now

- **Crash recovery**: resume from the last completed stage (or last completed session within a stage)
- **Data integrity**: know what's trustworthy and what's incomplete/corrupt
- **Status reporting**: tell the user what state their data is in before and during a run
- **Incremental re-runs**: only redo what's stale, reuse everything that's still valid
- **Mid-run provider tolerance**: if the user switches from Claude to Gemini after 7 of 10 sessions, don't discard the 7 completed sessions — track which provider processed each session and resume with the new provider

### What we need in the future

- **Add/remove interviews**: merge new findings without breaking existing data
- **Source material change detection**: when a user edits a video (trims the last 20 minutes) or edits a transcript (removes personal chat), detect the content change via file hashing, invalidate downstream stages for that session, and re-extract — quotes from removed content vanish automatically, other sessions stay cached
- **Incremental session addition**: when new interview recordings appear in the input directory, transcribe and analyse only the new material, then re-cluster and re-theme with the combined quote pool (old + new)
- **Analytical context preservation**: remember the researcher's codebook choices (which framework, what confidence threshold, which tags they accepted/denied) and suggest reapplying those same settings when new quotes arrive from new sessions
- **Provenance**: know the source of every quote, tag, label — which LLM, which prompt version, which human edit
- **Edit history**: track human overrides (hidden tags, renamed themes, section reordering, merged/renamed tags)
- **Human/LLM merge**: re-run analysis without losing human edits to the report

## Computer science foundations

This is a well-studied category of problems. The key insight: **we're building a combination of a build system and an event-sourced data store.** The pipeline stages form a dependency DAG (like Make); the human edits and LLM outputs form an event history (like event sourcing). We need both.

### 1. Build system: "only rebuild what's stale"

**Core reference**: Mokhov, Mitchell & Peyton Jones (2018), _"Build Systems à la Carte"_ — classifies every build system along two axes: scheduling (how to order stages) and rebuilding (how to detect staleness).

The pipeline is a **topological scheduler** (fixed stage order with minor branching) with **verifying traces** (record input/output hashes; if input hashes match, output is still valid). This is the same model as Shake (Haskell build system) and Bazel.

Each stage gets a **trace**:

```
StageTrace:
  stage: "quote_extraction"
  input_hashes:
    transcript_s1: "a1b2c3..."
    transcript_s2: "d4e5f6..."
    prompt_version: "7g8h9i..."
    model: "claude-sonnet-4-20250514"
  output_hash: "j0k1l2..."
  completed_at: "2026-02-20T14:32:15Z"
  cost_usd: 1.83
```

On re-run: compute current input hashes → compare against stored traces → skip stages where inputs haven't changed → re-run stale stages from the first point of divergence.

**Key influence**: Nix (Dolstra, 2006) — treats builds as pure functions where output = f(inputs). The output path includes a hash of all inputs. If inputs haven't changed, the output already exists. This is content-addressable caching.

**Key influence**: dbt's incremental materialisation — within a stage, track per-item completeness. "I extracted quotes from 7 of 10 sessions; only extract from the remaining 3."

### 2. Event sourcing: "the event log is the source of truth"

**Core reference**: Kleppmann (2017), _Designing Data-Intensive Applications_, Ch. 11; Fowler (2005), _"Event Sourcing"_; Helland (2015), _"Immutability Changes Everything"_.

> "Accountants don't use erasers." — Pat Helland

Every change to the project data — LLM output, human edit, tag rename, quote hide — is an immutable event appended to a log. The current state is a **projection** (materialised view) rebuilt by replaying events. This gives us:

- **Full provenance**: filter events by quote_id to see its complete history
- **"What did the LLM originally say?"**: replay only LLM events
- **"What did the human change?"**: filter for source=human
- **Undo/redo**: drop the last N events and rebuild
- **Merge after re-run**: replay human edits on top of new LLM outputs

Example event stream:

```jsonl
{"ts":"...","event":"quote_extracted","id":"q001","text":"...","source":"llm","model":"claude-sonnet-4-20250514","session":"s3"}
{"ts":"...","event":"quote_tagged","id":"q001","tag":"justice","source":"llm","model":"claude-sonnet-4-20250514"}
{"ts":"...","event":"quote_hidden","id":"q001","source":"human","reason":"off-topic"}
{"ts":"...","event":"quote_unhidden","id":"q001","source":"human"}
{"ts":"...","event":"tag_renamed","old":"justice","new":"legal-principles","source":"human"}
{"ts":"...","event":"theme_reordered","theme":"Ethics","from":3,"to":1,"source":"human"}
```

### 3. Write-ahead logging: "never lie about what's complete"

**Core reference**: Mohan et al. (1992), _"ARIES"_; ext4 journaling (ordered mode).

The rule: **write the stage output file to disk before writing the completion record to the manifest.** If the process dies between these two operations, the manifest doesn't claim the stage completed, and recovery re-runs it. The manifest is never a lie — it may be behind (missing a completed stage) but never ahead (claiming an incomplete stage is done).

This is the ext4 "ordered mode" insight: data written before metadata committed. Applied to the pipeline: stage output written before manifest updated.

### 4. Content-addressable storage: "if the hash matches, it's valid"

**Core reference**: Git object model (Chacon & Straub, 2014); Nix store (Dolstra, 2006); IPFS (Benet, 2014).

Every artifact's identity is its content hash. Change the content → change the hash → invalidate downstream artifacts. This provides:

- **Corruption detection**: rehash and compare on load
- **Change detection**: "has this transcript changed since last analysis?"
- **Deduplication**: same audio file transcribed twice → same hash → cached
- **Dependency invalidation**: transcript hash changed → all downstream hashes invalid → re-run from quote extraction forward

### 5. Saga pattern / forward recovery: "save what you have, resume from where you stopped"

**Core reference**: Garcia-Molina & Salem (1987), _"Sagas"_; Temporal.io durable workflow execution.

When the pipeline fails mid-stage, we use **forward recovery**, not backward compensation:

- Completed stages: keep their outputs, mark as done
- Failed stage: discard partial output (or keep partial per-session output), mark as incomplete
- On next run: resume from the incomplete stage

There's no "undo" for an LLM call — the tokens are spent. Forward recovery maximises the value of money already spent.

**Within a stage**, sagas apply at per-session granularity. Quote extraction processes sessions concurrently; if 7 of 10 succeed before credit exhaustion, save those 7 and mark 3 as pending. On resume, only the 3 remaining sessions need LLM calls.

### 6. Merge strategy: "humans always win"

**Core reference**: Shapiro et al. (2011), _"CRDTs"_; three-way merge (Git).

When the pipeline re-runs (new interviews added, prompt updated, model changed) and the user has made edits to the previous output:

1. **Common ancestor**: the last pipeline output before human edits
2. **Branch A**: human-edited version (hidden quotes, renamed themes, reordered sections)
3. **Branch B**: new pipeline output

Merge rules:
- Human changed, LLM didn't → keep human's version
- LLM changed, human didn't → keep LLM's version
- Both changed the same item → human wins (with notification)
- LLM added new items → include them
- Human deleted items → keep them deleted (unless the user asks for "full refresh")

Full CRDTs are overkill for a single-user tool. Event sourcing gives us the merge for free — replay human events on top of new LLM outputs.

**Source content removal and quote vanishing**: When the user edits source material (trims a video, deletes personal chat from a transcript), the merge has a special case: quotes that existed in the old output but don't exist in the new output — because the source content was removed.

The merge rule: **if the pipeline didn't produce a quote in the new run, and the reason is that the source content no longer exists (hash changed for that session), the quote vanishes.** Any researcher state attached to that quote (stars, tags, text edits) vanishes with it. This is the correct behaviour: the researcher trimmed the video precisely because they wanted that content gone. Preserving stars on quotes from deleted content would be confusing — "why is there a starred quote from content I removed?"

**Contrast with "human hidden"**: If the researcher hid a quote (`QuoteState.is_hidden=True`) and the pipeline re-runs _without_ source changes, the quote is still extracted by the LLM but the hidden state is preserved. The quote exists in the output but is marked hidden. This is different from source removal — the content is still there, the researcher just chose not to surface it.

**Re-clustering after source changes**: When quotes vanish due to source editing, clustering and theming must re-run on the reduced pool. Clusters that lose all their quotes may vanish entirely. Themes may consolidate. HeadingEdits (renamed sections/themes) are matched by `screen_label` or `theme_name` — if the cluster no longer exists, the rename is orphaned but harmlessly ignored (no cluster to apply it to).

## Architecture: what to build

### The manifest file

`pipeline-manifest.json` in the output's `.bristlenose/` directory. The manifest is the **source of truth for pipeline state**. It records:

```json
{
  "schema_version": 1,
  "project": "socratic-dialogues",
  "pipeline_version": "0.11.0",
  "created_at": "2026-02-20T14:00:00Z",
  "updated_at": "2026-02-20T14:32:15Z",
  "stages": {
    "ingest": {
      "status": "complete",
      "input_hashes": {"input_dir": "a1b2c3..."},
      "output_hash": "d4e5f6...",
      "completed_at": "2026-02-20T14:00:02Z",
      "sessions_discovered": ["s1", "s2", "s3"]
    },
    "transcribe": {
      "status": "complete",
      "sessions": {
        "s1": {"input_hash": "...", "output_hash": "...", "completed_at": "..."},
        "s2": {"input_hash": "...", "output_hash": "...", "completed_at": "..."},
        "s3": {"status": "skipped", "reason": "existing_vtt"}
      },
      "completed_at": "2026-02-20T14:05:30Z"
    },
    "quote_extraction": {
      "status": "partial",
      "sessions": {
        "s1": {"input_hash": "...", "output_hash": "...", "completed_at": "..."},
        "s2": {"status": "failed", "error": "credit_exhausted"},
        "s3": {"status": "pending"}
      },
      "completed_at": null
    }
  },
  "total_cost_usd": 1.83,
  "total_input_tokens": 87143,
  "total_output_tokens": 19517
}
```

### The event log

`pipeline-events.jsonl` — append-only NDJSON. Every mutation is an event. The manifest is a materialised projection of the event log. If the manifest is corrupted, rebuild it by replaying events.

Events cover:
- Pipeline operations: stage starts, completions, failures, LLM calls with cost
- Human edits: quote text changes, tag additions/removals, theme renames, section reordering, hide/unhide
- Provenance: which model, prompt version, and transcript produced each artifact

### Recovery logic

On `bristlenose run` (or `analyze`), before doing anything:

1. **Check for manifest**: if it exists, read it
2. **Validate artifacts**: for each "complete" stage, verify output file exists and hash matches
3. **Report status**: tell the user what's valid, what's stale, what's missing
4. **Compute work plan**: determine which stages need (re-)running
5. **Estimate cost**: only for stages that will actually run
6. **Execute**: run stages, updating manifest atomically after each completion

```
$ bristlenose run interviews/

Bristlenose v0.11.0 · Claude · Apple M2 Max · MLX

Project status:
  ✓ 10 sessions ingested
  ✓ 10 transcripts (all valid)
  ✓ 10 topic maps (all valid)
  ⚠ 7/10 sessions have quotes (3 failed — credit exhaustion)
  ✗ Screen clusters missing (depends on quotes)
  ✗ Theme groups missing (depends on quotes)
  ✗ Report not generated

Plan:
  • Extract quotes for s4, s7, s9 (3 sessions)
  • Cluster all quotes (re-run — new quotes added)
  • Group themes (re-run — new quotes added)
  • Render report

Estimated LLM cost: ~$0.45 for 3 sessions
Continue? [Y/n]
```

### Per-session granularity

The expensive stages (transcription, quote extraction) operate per-session. Track completion at session level so partial runs are maximally useful:

- Transcribe 8 of 10 files → crash → resume transcribes only files 9 and 10
- Extract quotes from 5 of 10 sessions → credit exhaustion → resume extracts from sessions 6-10
- Cross-session stages (clustering, theming) always run on the full set — but they're comparatively cheap (one LLM call for all quotes, vs. one per session for extraction)

### Input change detection

When the user modifies source material (re-transcribes, corrects a transcript, adds an interview):

1. Hash all current inputs
2. Compare against manifest's recorded input hashes
3. Invalidated stages: everything downstream of the first change
4. Report: "Session s3's transcript changed. Quotes, clusters, themes, and report will be re-generated. Estimated cost: ~$0.30"

Config changes (model, prompt version, max_tokens) are also inputs. Changing the model invalidates all LLM stages. Changing a stage-specific prompt invalidates that stage and downstream.

### Atomic writes

Stage outputs use write-then-rename:

```python
# Write to temp file
tmp = output_path.with_suffix('.tmp')
tmp.write_text(json.dumps(data))

# Atomic rename (POSIX guarantees this is atomic)
tmp.rename(output_path)

# Only NOW update manifest
update_manifest(stage, status="complete", output_hash=hash_content(data))
```

If the process dies before rename: no output file, manifest still says "pending" → clean re-run of that stage. If the process dies after rename but before manifest update: output file exists but manifest is stale → recovery detects the completed output and updates manifest.

### Schema versioning

Every intermediate JSON file includes a schema version:

```json
{
  "schema_version": 1,
  "stage": "quote_extraction",
  "pipeline_version": "0.11.0",
  "data": [...]
}
```

Loaders check the version and apply migrations if needed. Migrations are forward-only (no downgrade). Each migration is a pure function: `data_v1 → data_v2`.

### Analytical context as project state

The manifest tracks pipeline execution state: which stages ran, what inputs they had, what outputs they produced. But there's a second category of state that the pipeline must respect: **the researcher's analytical choices**.

Resilience isn't just about the pipeline surviving crashes. It's about respecting all the choices the user has made, and having situational awareness — doing the right thing when the source material changes.

**What counts as analytical context**:

| Choice | Where it lives today | How the pipeline should use it |
|--------|---------------------|-------------------------------|
| Active codebook frameworks | `ProjectCodebookGroup` rows | Suggest same frameworks for new quotes |
| AutoCode confidence threshold | Derivable from `min(ProposedTag.confidence WHERE status='accepted')` | Pre-fill threshold for new runs |
| Accept/deny decisions | `ProposedTag.status` | Training signal: "You denied 'Visibility of System Status' on navigation quotes 4 times — exclude navigation quotes from that tag?" |
| Manual tags | `QuoteTag` rows | Preserved on surviving quotes; inform AutoCode about the researcher's vocabulary |
| Starred quotes | `QuoteState.is_starred` | Survive re-import; new quotes start unstarred |
| Hidden quotes | `QuoteState.is_hidden` | Survive re-runs unless source content was removed |
| Text corrections | `QuoteEdit` rows | If a quote is re-extracted with slightly different text (model change), the correction may still apply — fuzzy match on timecode range |
| Section/theme renames | `HeadingEdit` rows | If clustering produces the same screen label, the rename is reapplied |

**The key insight**: this is not a new data store — the SQLite database already contains all of this. What's missing is:

1. A **query layer** that aggregates analytical context into a project summary: "This project uses Garrett (78% acceptance rate, 0.6 threshold) and Norman (62% acceptance rate, 0.5 threshold). The researcher has starred 23 quotes, hidden 7, and applied 89 manual tags."
2. A **suggestion engine** that, when new quotes arrive, proposes: "Run AutoCode on 15 new quotes using Garrett at 0.6?" — with the researcher's previous stats as context.
3. A **re-application pass** in the importer that, when clustering produces a screen label that matches a HeadingEdit key, reapplies the rename. (The importer already preserves researcher state on surviving quotes — this extends that to structural edits.)

**Academic context**: this is a form of **user modelling** (Fischer, 2001, _"User Modeling in Human-Computer Interaction"_) applied to analytical tools. The system builds an implicit model of the researcher's preferences from their actions, then uses it to reduce manual effort on subsequent runs. The key constraint: **the model is transparent** — the researcher can see exactly what settings are being suggested and why, and override any of them. No black-box adaptation.

## Scenarios: what users expect

These are the real-world situations that the architecture above must handle. Each scenario describes what the user does, what they expect to happen, and which phases deliver that behaviour.

### Scenario A: Credit exhaustion and provider switch

**What happens**: A researcher is running Bristlenose on 10 sessions. Quote extraction completes for sessions s1–s7, then Claude's API returns "credit balance too low." The researcher tops up their Gemini credits instead (cheaper, available now) and sets `BRISTLENOSE_LLM_PROVIDER=google` in `.env`.

**What the user expects**: "I re-run the same command. It picks up where it left off. Sessions s1–s7 keep their Claude-extracted quotes. Sessions s8–s10 get Gemini-extracted quotes. The tool doesn't throw away $1.80 of completed work just because I changed providers."

**What the pipeline must do**:
- The manifest records `provider: "anthropic"` and `model: "claude-sonnet-4-20250514"` on each completed SessionRecord (Phase 1d)
- On re-run, input change detection (Phase 2c) sees that sessions s1–s7 have completed output with valid hashes. The provider/model change is recorded as a *session-level input*, not a *stage-level input*. Completed sessions are not invalidated by a global config change
- Sessions s8–s10 are processed with the new provider. Their SessionRecords record `provider: "google"`, `model: "gemini-2.5-flash"`
- Cross-session stages (clustering, theming) always re-run because the quote pool is now complete
- The provenance trail (Phase 4c) records that quotes from s1–s7 came from Claude and quotes from s8–s10 came from Gemini — visible in `bristlenose status` and in the event log

**Phases involved**: 1d (per-session tracking with provider/model), 2c (input change detection at session level), 4c (provenance metadata)

### Scenario B: Editing source material

**What happens**: After reviewing the report, the researcher:
1. Opens a Teams transcript file and deletes 5 minutes of "how are your kids" personal chat
2. Opens the video in iMovie, trims the last 20 minutes (where they accidentally bad-mouthed the CEO on camera), and exports a shorter version

**What the user expects**: "I re-run Bristlenose. The quotes about kids and the CEO vanish. Everything else stays. I don't pay to re-transcribe the other 9 interviews."

**What the pipeline must do**:
- Ingest hashes all source files (Phase 2c). The edited transcript file has a new hash. The replaced video file has a new hash
- For the session with the edited transcript: topic segmentation and quote extraction are invalidated (transcript changed). Transcription is NOT invalidated if the transcript came from a platform VTT (the VTT itself changed, so re-parse — but no Whisper call needed). If the video was the transcription source, the shorter video triggers re-transcription (audio hash changed)
- For the session with the trimmed video: the audio extraction output changes → transcription re-runs → everything downstream re-runs for that session
- Other sessions: untouched. Their hashes match. Cached
- Cross-session stages (clustering, theming): must re-run because the quote pool changed. But they're cheap — one LLM call for all quotes
- Quotes that came from deleted content simply don't appear in the new extraction. They vanish from the report, the clusters, and the themes. No explicit "delete quote" action needed — they were never extracted in the first place

**Cascade logic**:
```
source file hash changed
  → ingest (re-run for this session — file metadata may have changed)
    → transcription (re-run if this was the audio source)
      → merge transcript (re-run)
        → PII removal (re-run if enabled)
          → topic segmentation (re-run)
            → quote extraction (re-run)
              → [cross-session: always re-run when any session's quotes change]
              → clustering (re-run)
                → theming (re-run)
                  → report (re-render)
```

**Phases involved**: 2c (input change detection via file hashing), 5b (per-session incremental processing), 5c (re-cluster with merged data)

### Scenario C: Adding new interviews

**What happens**: A researcher ran Bristlenose on 8 interviews. Two weeks later, they record 2 more interviews and drop the files into the same input directory.

**What the user expects**: "I re-run. It transcribes only the 2 new recordings. It extracts quotes from only those 2. Then it re-clusters everything (old + new) and gives me an updated report. The stars and tags I put on quotes from the first 8 sessions are still there."

**What the pipeline must do**:
- Ingest discovers 10 sessions. The manifest records 8 completed sessions. 2 are new (no manifest entry) — Phase 5a
- Transcription runs only for the 2 new sessions
- Topic segmentation runs only for the 2 new sessions
- Quote extraction runs only for the 2 new sessions
- Clustering and theming re-run on the full quote pool (old 8 + new 2) — these are cross-session stages and must see the complete picture
- The report is re-rendered with the updated clusters and themes
- In serve mode: the importer detects new quotes (new session_ids), preserves researcher state (stars, tags, edits) on surviving quotes from old sessions, and adds new quotes from the 2 new sessions to the database

**The autocode opportunity**: If the researcher previously ran AutoCode with the Garrett framework at 0.6 confidence and accepted 47 of 60 proposals, the pipeline can suggest: "You have 15 new quotes from 2 new sessions. Run AutoCode (Garrett, 0.6 confidence) on the new quotes? Your previous acceptance rate was 78%." This is Scenario D.

**Phases involved**: 5a (detect new sessions), 5b (per-session incremental processing), 5c (re-cluster with merged data), merge strategy (human curation preserved)

### Scenario D: Preserving and reapplying analytical choices

**What happens**: After Scenario C completes, the researcher has 15 new quotes from 2 new sessions. They had previously used the Garrett codebook with a 0.6 confidence threshold and reviewed every proposal. Now they want the same treatment for the new quotes.

**What the user expects**: "Bristlenose remembers what I did last time and offers to do the same thing for the new quotes. I don't have to re-configure everything."

**What the pipeline must do**:
- The `AutoCodeJob` table already records: `framework_id="garrett"`, `llm_provider`, `llm_model`, `total_quotes`, `proposed_count`
- `ProposedTag` rows record per-quote: confidence, status (accepted/denied), `reviewed_at`
- From this we can derive: effective confidence threshold (the min confidence of any accepted proposal), acceptance rate, denial patterns by tag
- On re-run with new quotes: the system detects quotes that have no `ProposedTag` rows (they're from the new sessions). It suggests running AutoCode on just those quotes, using the same framework and displaying the researcher's historical acceptance stats
- Previously accepted tags on surviving quotes are `QuoteTag` rows — preserved by the importer. Previously denied proposals are `ProposedTag` rows with `status="denied"` — preserved for telemetry

**What "user choices as project state" means in practice**:
- **Codebook selection**: which frameworks are active (`ProjectCodebookGroup` rows)
- **Confidence threshold**: derivable from the lowest-confidence accepted `ProposedTag`
- **Accept/deny decisions**: `ProposedTag.status` — forms a training signal for future suggestions
- **Tag additions/removals**: `QuoteTag` rows (manual tags), `DeletedBadge` rows (dismissed sentiments)
- **Curation state**: `QuoteState` (starred, hidden), `QuoteEdit` (corrected text), `HeadingEdit` (renamed sections)

All of this is already in the database. The missing piece is the *workflow* — the pipeline doesn't yet know how to query this state and use it to pre-configure new runs.

**Phases involved**: 4b (record human edits as events), 4d (three-way merge), Phase 5 (incremental sessions), new concept: analytical context preservation

## Why this matters (the trust problem)

A researcher runs Bristlenose on 15 hours of interview recordings. It costs them $8 in LLM fees and 45 minutes of wall time. Then their laptop sleeps, or Claude runs out of credits, or they force-quit because they need to get on a Zoom call.

Right now: they must pass `--clean` and start over. $8 wasted. 45 minutes wasted. The tool ate their work.

No researcher will trust that. They'll say "clever, but I'll stick to Excel and Miro." And they'd be right — a spreadsheet never loses your data when you close the lid.

This isn't a nice-to-have. It's the difference between a toy and a tool.

## How we're going to build this

Four phases, each broken into small steps. Every step ships independently, nothing breaks between steps, and each step delivers something the user can feel.

The key constraint: **this runs alongside everything else** — UI work, codebook features, desktop app. So each step must be small enough to land in a single session, testable in isolation, and backward-compatible with existing projects.

### Branch strategy

Phase 1 is small enough to land on `main` as a series of commits. Each sub-step is a single focused change. No feature branch needed — just merge as we go.

Phases 2-4 are bigger and may need branches, but by then Phase 1 has established the manifest format and the patterns. Later phases extend rather than replace.

---

### Phase 0: Quick fixes (do immediately, no architecture needed)

These are bugs and config mistakes found during the Plato run. Zero risk, immediate value.

#### ~~0a. Fix `analyze` to write intermediate JSON~~ ✓ Already done

Verified: `run_analysis_only()` already writes all 4 intermediate files (topic_boundaries, extracted_quotes, screen_clusters, theme_groups) with the same `write_intermediate_json()` calls as `run()`.

#### ~~0b. Make `write_intermediate` default to `True`~~ ✓ Already done

Verified: `write_intermediate: bool = True` in `config.py` line 89.

#### ~~0c. Make the SQLite DB per-project instead of global~~ ✓ Already done

**What's wrong**: The serve-mode DB lives at `~/.config/bristlenose/bristlenose.db` — one DB for all projects. If you serve project A, then serve project B, project A's data is still in the DB. Stale sessions, stale quotes, stale everything.

**The fix**: Put the DB inside the output directory: `.bristlenose/bristlenose.db`. Each project gets its own DB. The serve command creates/opens the DB in the project's output dir.

**What it touches**: `server/database.py` (DB path), `server/app.py` (DB initialization). Maybe 10-20 lines.

**Risk**: Low. Existing global DB becomes unused. New projects get clean DBs automatically. Old projects that were served before won't have a local DB yet — serve creates one fresh (which is what you want).

---

### Phase 1: Crash recovery (the manifest)

**Goal**: If the pipeline is interrupted, re-running it picks up where it left off instead of starting from scratch. The user sees a status report of what's done and what's left.

This is the foundational change. Everything else builds on it.

#### ~~1a. Define the manifest model~~ ✓ Done

**What it is**: A Pydantic model for `pipeline-manifest.json`. Just the data structure — no pipeline changes yet.

```python
class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"     # some sessions done, some not
    FAILED = "failed"

class StageRecord(BaseModel):
    status: StageStatus
    started_at: str | None = None
    completed_at: str | None = None
    output_path: str | None = None      # relative path to stage output
    error: str | None = None            # if failed, what went wrong

class PipelineManifest(BaseModel):
    schema_version: int = 1
    project_name: str
    pipeline_version: str
    created_at: str
    updated_at: str
    stages: dict[str, StageRecord]      # stage_name → record
    total_cost_usd: float = 0.0
```

**What it touches**: New file `bristlenose/manifest.py`. Nothing else changes.

**Risk**: None. Just defines a model. No behavior change.

#### ~~1b. Write manifest after each stage~~ ✓ Done

**What it is**: After each stage completes in `pipeline.py`, write the manifest to disk. This is the "journal" — a record of what's done.

**How it works**: At the start of `run()`, create a manifest (or load an existing one). After each stage succeeds, update the manifest and write it to `.bristlenose/pipeline-manifest.json`. If the pipeline is interrupted, the manifest records everything up to the last completed stage.

**What it touches**: `pipeline.py` — add ~5 lines after each stage (call a helper that updates and writes the manifest). `manifest.py` — add read/write helpers.

**Risk**: Very low. The manifest is a new file that nothing reads yet. Writing it is a side effect that doesn't change pipeline behavior. Existing tests still pass — they don't check for the manifest.

**Backward compatibility**: Projects without a manifest still work exactly as before. The manifest is created on the next run.

#### ~~1c. Read manifest on startup and skip completed stages~~ ✓ Done

**What it is**: This is where resume actually works. At the start of `run()`, check for an existing manifest. For each stage marked "complete," check that the output file still exists on disk. If it does, skip the stage and load the data from the file.

**How it works**:
1. Load manifest
2. For each stage in pipeline order: is it marked complete AND does the output file exist?
3. If yes: load the output from disk, skip the stage, print `✓ Transcripts (cached)` instead of `✓ Transcribed 10 sessions 4m 30s`
4. If no: run the stage normally

**What it touches**: `pipeline.py` — the main `run()` method needs conditional logic around each stage. This is the biggest change in Phase 1. Maybe 50-100 lines of new code, but it's structurally simple — each stage gets an "if cached, load; else, compute" wrapper.

**Risk**: Medium. The skip logic must correctly load data from disk in the same format that the stage produces in memory. But we already have this — `run_render_only()` already loads quotes, clusters, and themes from JSON. The loading code exists; we're just using it in more places.

**What it looks like to the user**:
```
$ bristlenose run interviews/    # first run — interrupted during quote extraction
✓ Ingested 10 sessions                    0.1s
✓ Transcribed 10 sessions                 4m 30s
✓ Segmented 87 topic boundaries           35s
⚠ Extracted 42 quotes (5/10 sessions)     2m 10s
  Credit balance too low — stopping.

$ bristlenose run interviews/    # second run — resumes
✓ Ingested 10 sessions                    (cached)
✓ Transcribed 10 sessions                 (cached)
✓ Segmented 87 topic boundaries           (cached)
✓ Extracted 78 quotes (10/10 sessions)    1m 45s   ← only 5 new sessions
✓ Clustered 12 screens · Grouped 8 themes 15s
✓ Rendered report                          0.1s
```

#### ~~1d. Per-session tracking for expensive stages~~ ✓ Done

**What it is**: Steps 1a-1c track at the stage level: "quote extraction is complete" or "quote extraction is incomplete." But quote extraction processes sessions independently — if 7 of 10 sessions succeeded, we should save those 7 and only re-run 3.

**How it works**: The manifest gets a `sessions` field on the per-session stages (transcription, topic segmentation, quote extraction):

```python
class SessionRecord(BaseModel):
    status: StageStatus
    session_id: str
    completed_at: str | None = None
    provider: str | None = None       # "anthropic", "google", etc.
    model: str | None = None          # "claude-sonnet-4-20250514", "gemini-2.5-flash"

class StageRecord(BaseModel):
    # ... existing fields ...
    sessions: dict[str, SessionRecord] | None = None  # only for per-session stages
```

Each per-session stage writes its results incrementally — after processing each session, update the manifest. On resume, only sessions marked incomplete are re-processed.

**Provider/model tracking**: Each SessionRecord captures the provider and model that processed it. This enables mid-run provider switching (Scenario A). When the user changes `BRISTLENOSE_LLM_PROVIDER` between runs, completed sessions retain their original provider metadata. The input change detection logic (Phase 2c) treats provider/model as a *per-session* attribute, not a *per-stage* attribute. A global config change from Claude to Gemini does NOT invalidate sessions already completed by Claude — those sessions have valid output regardless of which model produced it.

**Why per-session, not per-stage**: If provider were a stage-level input, changing from Claude to Gemini would invalidate ALL quote extraction (all 10 sessions), forcing re-extraction of the 7 already-completed sessions. This wastes money and contradicts user expectations. The correct granularity is: "session s3 was extracted by `claude-sonnet-4-20250514` and its output hash is valid. Don't re-extract it just because the config now says Gemini."

**Exception**: If the user *wants* to re-extract with a different model (e.g. testing whether Gemini produces better quotes), they can use `bristlenose reset --stage quote_extraction --session s3` (from Phase 3a) to selectively invalidate specific sessions.

**What it touches**: `pipeline.py` (the LLM-calling loops in topic segmentation and quote extraction), `manifest.py` (the session-level model). The stage functions themselves (`topic_segmentation.py`, `quote_extraction.py`) don't change — they already return per-session results. The change is in how `pipeline.py` calls them and saves results.

**Risk**: Medium. Need to handle the merge of old cached results + new results for the same stage. But it's straightforward — load existing quotes for sessions s1-s7, extract new quotes for s8-s10, concatenate.

#### ~~1d-ext. Per-session caching for stages 1–7~~ ✓ Done

**What it is**: Extend per-session caching to stages that currently always re-run on resume. Transcription is the biggest win; speaker identification also saves LLM money.

**Measured data (project-ikea, 4 sessions, Apple M2 Max, Feb 2026):**

| Stage | Time | % of resume | LLM cost | Cacheable? |
|---|---|---|---|---|
| Ingest | 0.4s | <1% | — | No (fast, always re-run) |
| Extract audio | 0.5s | <1% | — | Easy (`.wav` on disk) |
| **Transcribe** | **56s** | **52%** | — | **Yes — biggest win** |
| **Identify speakers** | **7.5s** | **7%** | **~$0.02** | **Yes — saves time + money** |
| Merge transcripts | 0.0s | <1% | — | No (instant) |
| Topic segmentation | (cached) | 0% | $0 | Done (Phase 1d) |
| Quote extraction | 34.5s | 32% | ~$0.22 | Done (Phase 1d) |
| Cluster + group | 8.9s | 8% | ~$0.02 | Phase 1c stage-level |

Caching transcription alone would cut resume time from 1m 48s to ~52s (52% reduction). For a 20-session project (~4 min transcription), the savings scale linearly.

**How it differs from stages 8–9**: Transcription produces one file per session in `transcripts-raw/` (not a single merged JSON). The caching check is file-existence-based rather than JSON-filtering-based — check which session transcript files already exist on disk. `load_transcripts_from_dir()` already reloads them. The infrastructure exists; the wiring in `pipeline.py` does not.

**Priority order:**
1. Transcription — biggest time win by far
2. Speaker identification — saves both time and LLM money
3. Audio extraction — marginal gain, probably not worth the complexity

**Open questions**: (1) Should audio extraction (stage 2) also be cached per-session? It's fast but not free. (2) How does this interact with speaker identification (stage 4) and transcript merging (stage 5), which are downstream of transcription? (3) What about subtitle parsing and docx parsing — are those per-session too?

**Status**: ✓ Done. Transcription caches `session_segments.json`, speaker ID caches `speaker-info/{sid}.json`. 10 tests. Audio extraction not cached (marginal gain).

#### ~~1e. Status report and pre-run summary~~ ✓ Done

**What it is**: `bristlenose status <folder>` — standalone read-only command that prints project state from the manifest. Plus a one-line pre-run summary when `bristlenose run` resumes.

**Implementation**: `bristlenose/status.py` (pure logic — `get_project_status()`, `format_resume_summary()`), `bristlenose/cli.py` (status command + `_resolve_output_dir()` + `_print_project_status()`). 14 tests in `tests/test_status.py`.

**Design decisions**:
- Resume is automatic (no `--resume` flag) — if a manifest exists, the run command resumes and prints a summary. `--clean` deletes everything and starts fresh. This matches the existing Phase 1c behaviour.
- Status command accepts input dir or output dir (auto-detects via `_resolve_output_dir()`)
- `-v` flag shows per-session detail with provider/model info
- Shows 7 display stages (skips extract_audio, merge_transcript, pii_removal — trivial/fast)
- Validates intermediate file existence for completed stages, warns if missing
- Enriches detail from intermediate JSON (counts quotes, boundaries, clusters, themes)

**What the user sees**:
```
$ bristlenose status interviews/

  usability-study-feb-2026
  Pipeline v0.10.2
  Last run: 20 Feb 2026 14:32

  ✓ Ingest                10 sessions
  ✓ Transcribe            10 sessions
  ✓ Speakers              10 sessions
  ✓ Topics                87 boundaries
  ⚠ Quotes                7/10 sessions (3 incomplete)
  ✗ Clusters & themes
  ✗ Report

$ bristlenose run interviews/
Resuming: 7/10 sessions have quotes, 3 remaining.
 ✓ Ingested 10 sessions                    (cached)
 ...
```

---

### Phase 2: Data integrity (hashing and validation)

**Goal**: Know whether cached data is trustworthy. Detect corruption, detect input changes, invalidate stale downstream stages.

Phase 1 trusts the manifest blindly — "it says complete, so it must be fine." Phase 2 adds verification.

#### 2a. Content hashes on stage outputs

**What it is**: When writing a stage output (JSON, transcript text), compute its SHA-256 hash and store it in the manifest alongside the file path.

**How it works**: `write_intermediate_json()` returns the hash of what it wrote. The manifest records it.

**What it touches**: `render_output.py` (return hash from write function), `manifest.py` (add hash field), `pipeline.py` (pass hash to manifest update).

**Risk**: None. Just adds a field. Doesn't change behavior.

#### 2b. Verify hashes on load

**What it is**: When loading cached data (the skip logic from 1c), re-hash the file on disk and compare to the manifest. If they don't match, the file is corrupt or was tampered with — treat the stage as incomplete and re-run it.

**How it works**: Before loading `extracted_quotes.json`, compute `sha256(file_contents)` and compare to the hash in the manifest. Mismatch → log a warning, mark stage as stale, re-run.

**What it touches**: The loading logic in `pipeline.py` (add hash check before using cached data).

**Risk**: Low. The only behavioral change is: corrupted files trigger re-runs instead of producing garbled output.

#### 2c. Input change detection

**What it is**: Hash the inputs to each stage (the transcript text, the prompt template, the model name). If any input changed since the last run, the stage's output is stale even though it exists.

**Example**: You correct a typo in a transcript file. The transcript hash changes. Quotes, clusters, themes, and the report all need re-generating — but transcription doesn't.

**How it works**: Each stage record in the manifest stores `input_hashes` (what the inputs looked like when the stage ran). On re-run, compute current input hashes. If they differ from recorded ones, the stage is stale.

**What it touches**: `manifest.py` (input hash fields), `pipeline.py` (compute input hashes before each stage, compare against manifest).

**Risk**: Medium. The tricky part is defining "inputs" correctly for each stage. Transcription inputs = audio file hashes. Quote extraction inputs = transcript hashes + prompt hash + model name. Get this wrong and you either skip stages that should re-run (dangerous) or re-run stages unnecessarily (annoying but safe). Err on the side of re-running.

**Source material changes (Scenario B)**: The most impactful input changes are edits to source files — the researcher trims a video, edits a transcript, or corrects a VTT file. The cascade logic:

| What changed | Hash that changes | Stages invalidated |
|-------------|-------------------|-------------------|
| Audio/video file replaced or trimmed | Source file content hash | Extract audio → transcribe → all downstream |
| Platform transcript (VTT/SRT/DOCX) edited | Source file content hash | Parse subtitles/DOCX → merge transcript → all downstream |
| Transcript text file edited manually | Transcript output hash | Topic segmentation → quote extraction → clustering → theming → report |
| Config: model changed | Model name in session input hash | All LLM stages for uncompleted sessions (see Phase 1d — completed sessions are not invalidated) |
| Config: prompt changed | Prompt content hash | The specific stage + everything downstream |
| Config: `min_quote_words` changed | Config hash | Quote extraction + downstream |

**File hash computation**: Hash the raw bytes of each source file (SHA-256). For audio/video, this means re-hashing a potentially large file on each run. Two optimisations:

1. **Size+mtime fast path**: if `(file_size, mtime)` match the manifest record, skip the full hash. Only compute SHA-256 when size or mtime differ. This is the rsync/Make optimisation (Tridgell & Mackerras, 1996) — not cryptographically reliable (mtime can be spoofed) but sufficient for a local-first tool where the user is not adversarial.
2. **Partial hash for large files**: for files over 100 MB, hash the first 1 MB + last 1 MB + file size. This catches trims, appends, and re-encodes without reading the entire file. A full hash can be triggered with `--verify` for paranoid mode.

**The "quotes vanish" mechanism**: When a trimmed video produces a shorter transcript, or an edited transcript file has personal chat removed, quote extraction simply doesn't find quotes in the removed content. There's no explicit "delete old quotes" step. The old quotes existed because the old transcript contained that content; the new transcript doesn't, so they're never extracted. The manifest records the new output hash, and cross-session stages re-run on the reduced quote pool.

In serve mode, the importer handles the database side: quotes with `last_imported_at < now` are cleaned up (existing behaviour in `importer.py`). Researcher state (stars, tags, edits) on surviving quotes is preserved; state on vanished quotes is deleted along with the quote rows.

**Per-session vs. global invalidation**: Source file changes invalidate only the affected session's per-session stages. Other sessions keep their cached results. Cross-session stages (clustering, theming) always re-run when any session's quotes change — but this is by design. Clustering and theming are cheap: one LLM call for all quotes combined, typically ~$0.10.

#### 2d. `bristlenose status` command

**What it is**: A CLI command that reads the manifest and reports the state of a project without running anything.

```
$ bristlenose status interviews/

Project: usability-study-feb-2026
Pipeline version: 0.11.0
Last run: 20 Feb 2026 14:32

Stages:
  ✓ Ingest          10 sessions
  ✓ Transcribe      10 transcripts (all hashes valid)
  ✓ Topic segments  87 boundaries
  ⚠ Quotes          42 quotes (7/10 sessions — 3 failed)
  ✗ Clusters        not generated
  ✗ Themes          not generated
  ✗ Report          not generated

Cost so far: $4.20 (87K input tokens, 19K output tokens)
```

**What it touches**: New subcommand in `cli.py`, reads from manifest. Pure read-only.

**Risk**: None. Read-only command.

---

### Phase 3: The nuke button and clean re-runs

**Goal**: When data is too broken to repair, make it easy to start fresh — with granularity (don't delete transcripts if you only need to re-run analysis).

This is independent of Phases 1-2 but much more useful once the manifest exists.

#### 3a. `bristlenose reset` command

**What it is**: Guided cleanup. Instead of `--clean` which deletes everything silently, `reset` shows what exists and lets you choose what to delete.

```
$ bristlenose reset interviews/

This will delete pipeline data for usability-study-feb-2026.
What do you want to clear?

  [1] Analysis only (quotes, clusters, themes — keeps transcripts)
      Re-run cost: ~$2.50
  [2] Everything except source files
      Re-run cost: ~$6.00 + 20 min transcription
  [3] Cancel

Choice:
```

**What it touches**: New subcommand in `cli.py`. Deletes selected files, clears relevant manifest entries.

**Risk**: Low. It's a guided `rm` — but it asks first and tells you the cost of regenerating.

#### 3b. Per-project SQLite DB cleanup

**What it is**: If the DB is per-project (from Phase 0c), `reset` also clears the SQLite DB. If 0c hasn't landed yet, `reset` at least tells you the global DB might have stale data and suggests restarting serve mode.

---

### Phase 4: Event log and provenance (future)

**Goal**: Know where every piece of data came from. Track human edits. Enable merge after re-runs.

This is the "accountants don't use erasers" layer. It's important but not urgent — Phases 1-3 solve the immediate pain (crash recovery, trust, clean re-runs).

#### 4a. Append-only event log file

**What it is**: `pipeline-events.jsonl` in `.bristlenose/`. One JSON line per event. Events are immutable — never edited or deleted.

Events for pipeline operations:
```jsonl
{"ts":"...","event":"stage_start","stage":"quote_extraction","model":"claude-sonnet-4-20250514"}
{"ts":"...","event":"session_complete","stage":"quote_extraction","session":"s3","quotes":12,"cost_usd":0.18}
{"ts":"...","event":"stage_complete","stage":"quote_extraction","total_quotes":78}
```

**What it touches**: `pipeline.py` (append event after each significant action). New file `bristlenose/events.py` for event models and append logic.

**Risk**: None. It's just appending to a log file. Nothing reads it yet. Can't break anything.

#### 4b. Record human edits as events

**What it is**: When a user hides a quote, renames a theme, or edits quote text in serve mode, append an event to the same log.

**What it touches**: The serve-mode API handlers in `server/`. Each mutation endpoint appends an event in addition to updating SQLite.

**Risk**: Low. The SQLite DB remains the source of truth for serve mode. The event log is a second copy for audit purposes. If the event log is corrupted, nothing breaks — serve mode still works from SQLite.

#### 4c. Provenance metadata on artifacts

**What it is**: Each quote in `extracted_quotes.json` gets extra fields: `extracted_by_model`, `extracted_with_prompt_hash`, `extracted_from_transcript_hash`, `extracted_at`. Similarly for clusters and themes.

**What it touches**: The Pydantic models for quotes, clusters, themes (add optional fields with defaults so old data still loads). The stage functions that create these objects (populate the new fields).

**Risk**: Low. New optional fields with defaults don't break deserialization of old data.

#### 4d. Three-way merge for re-runs

**What it is**: When re-running analysis on a project where the user has made edits, preserve the human edits. Compare the old LLM output (common ancestor), the human-edited version (from event log), and the new LLM output (fresh run). Merge with human-wins precedence.

This is the hardest piece. It needs:
- Event log with human edits (from 4b)
- A way to identify "the same quote" across runs (stable quote IDs based on transcript position)
- Merge logic for each data type (quotes, tags, themes)

**What it touches**: New file `bristlenose/merge.py`. Called from `pipeline.py` after LLM stages, before rendering.

**Risk**: Medium-high. Merge logic is subtle. Needs extensive testing with real scenarios. This is the one piece that could go wrong in ways that lose user data — so it needs the most careful design and testing.

---

### Phase 5: Incremental sessions (future)

**Goal**: Add or remove interviews from an existing project without starting over. Detect changes to existing source material and refresh only what's affected. This is where the pipeline becomes truly situationally aware — it understands what changed in the source material and does the right thing.

#### 5a. Detect new/removed/changed sessions

**What it is**: On re-run, compare the current set of input files against the manifest's recorded sessions. Classify each session as unchanged, changed, new, or removed.

**How it works**:
1. `ingest()` scans the input directory and returns the current session list
2. Compare against manifest's `stages.ingest.sessions_discovered`
3. Classify each session:
   - **Unchanged**: same session_id, same source file hash(es) — fully cached
   - **Changed**: same session_id, different source file hash — re-process from first changed stage (Scenario B)
   - **New**: session_id not in manifest — process from scratch (Scenario C)
   - **Removed**: session_id in manifest but not in current scan — mark as excluded

**What it touches**: `pipeline.py` (comparison logic after ingest), `manifest.py` (session classification model).

**What the user sees**:
```
$ bristlenose run interviews/    # 2 new recordings added, 1 transcript edited

Project status:
  ✓ 7 sessions cached (all valid)
  ✎ 1 session changed (s3 — transcript edited, quotes will be re-extracted)
  ★ 2 new sessions detected (interview_09.mp4, interview_10.mp4)

Plan:
  • Re-extract quotes for s3 (transcript changed)
  • Transcribe 2 new sessions (~4 min)
  • Segment + extract quotes for 2 new sessions
  • Re-cluster all quotes (quote pool changed)
  • Re-theme all quotes (quote pool changed)
  • Render report

Estimated cost: ~$0.90 (1 changed + 2 new sessions + clustering + theming)
Continue? [Y/n]
```

#### 5b. Per-session incremental processing

**What it is**: Only transcribe, segment, and extract quotes for new or changed sessions. Keep existing sessions' data intact.

**How it works**: For each per-session stage (transcription, topic segmentation, quote extraction):
1. Check the manifest for each session in the current scan
2. If the session has a completed record with a valid output hash and unchanged input hash: skip, load from cache
3. If the session is new or its source file hash changed: run the stage for that session
4. Merge results: cached sessions' output + newly computed output

**The merge is simple**: per-session stages produce independent output per session. Merging is concatenation — transcripts for s1–s8 from cache + transcripts for s9–s10 from fresh processing. The pipeline already collects results into lists; the only change is that some items come from cache and some from live computation.

**What it touches**: `pipeline.py` (the per-session stage loops), loading code for each stage's intermediate JSON. The stage functions themselves don't change — they already operate per-session.

**Risk**: Medium. The merge of cached + fresh results must produce the same data structure as a full run. But this is structurally the same as the Phase 1d resume merge (cached sessions s1–s7 + fresh sessions s8–s10).

#### 5c. Re-cluster and re-theme with merged data

**What it is**: After extracting quotes for new or changed sessions, re-run clustering and theming on the full set (old + new quotes). These stages are cross-session and must see the complete picture.

**Why not incremental clustering?** Clustering assigns quotes to screens/features. A new quote might belong to an existing cluster, or it might create a new cluster. The LLM needs to see all quotes to make coherent assignments. Since clustering is a single LLM call (all quotes, one prompt), the cost is low (~$0.10) compared to per-session quote extraction (~$0.30 per session).

**Same for theming**: themes emerge from the full quote pool. Adding 15 new quotes might surface a new theme or strengthen an existing one. The LLM re-themes from scratch on the combined pool.

**What it touches**: No changes to the stage functions. The pipeline just feeds them the combined quote list (cached + fresh). The re-run is triggered whenever any session's quotes change.

#### 5d. Handle removed sessions

**What it is**: When a session is removed (file deleted from input directory, or added to `.bristlenose-ignore` — see `docs/design-session-management.md`), exclude its quotes from clustering/theming and re-run those stages.

**How it works**:
1. The manifest marks the session as "removed" (not deleted — the record stays for audit)
2. Per-session cached data for the removed session is retained on disk but excluded from stage inputs
3. Clustering and theming re-run on the reduced quote pool
4. The report is re-rendered without quotes from the removed session

**In serve mode**: the importer already handles this. Sessions not in the current pipeline output get their child rows deleted (SourceFile, TranscriptSegment, TopicBoundary, SessionSpeaker), then the session itself. Researcher state on quotes from removed sessions is deleted. This is existing behaviour (`importer.py`, tested in `test_serve_importer.py`).

**What it touches**: `pipeline.py` (session exclusion logic), `manifest.py` (removed session state). The `.bristlenose-ignore` mechanism (from session management design) provides the input; Phase 5d provides the pipeline response.

#### 5e. Suggest autotagging for new quotes

**What it is**: When new sessions produce new quotes, and the project has prior AutoCode history, suggest re-running AutoCode on just the new quotes with the same settings.

**How it works**:
1. After incremental processing, the pipeline knows which quotes are new (from new/changed sessions)
2. Query the `AutoCodeJob` table for this project — any completed jobs?
3. For each completed job: count accepted/denied `ProposedTag` rows, derive effective confidence threshold (min confidence of any accepted proposal)
4. Present a suggestion to the researcher:

```
AutoCode history:
  • Garrett framework: 47 accepted, 12 denied (78% acceptance rate, threshold ≥0.6)
  • Norman framework: 31 accepted, 19 denied (62% acceptance rate, threshold ≥0.5)

15 new quotes from 2 new sessions are untagged.
Suggest AutoCode with Garrett at 0.6 confidence? [Y/n]
```

5. If accepted, run `run_autocode_job()` scoped to only the new quote IDs
6. Present proposals using the same review UI the researcher used before

**What it touches**: New helper in `autocode.py` (query historical acceptance stats, scope to specific quote IDs). New logic in `cli.py` or serve-mode UI (display suggestion after incremental run). The actual AutoCode execution reuses the existing `run_autocode_job()` infrastructure.

**Key implementation detail**: `run_autocode_job()` currently processes all quotes in the project. It needs a `quote_ids: list[int] | None` filter parameter — when set, only batch and tag the specified quotes. The rest of the machinery (batch building, LLM calls, proposal storage) stays the same.

**Risk**: Medium. The main complexity is scoping AutoCode to "only new quotes" and presenting the suggestion at the right moment in the workflow. The suggestion UX must be non-intrusive — the researcher might not want autotagging at all.

---

## Sequencing: what to build when

The key insight: **each sub-step is a single PR-sized change**. None of them requires a feature branch. They land on main incrementally.

| Step | Size | Depends on | Can ship with |
|------|------|-----------|---------------|
| ~~**0a** Fix analyze intermediate writes~~ | ✓ Done | — | — |
| ~~**0b** write_intermediate defaults True~~ | ✓ Done | — | — |
| ~~**0c** Per-project SQLite DB~~ | ✓ Done | — | — |
| ~~**1a** Manifest model~~ | ✓ Done | — | — |
| ~~**1b** Write manifest after stages~~ | ✓ Done | 1a | — |
| ~~**1c** Skip completed stages on resume~~ | ✓ Done | 1b | — |
| ~~**1d** Per-session tracking~~ | ✓ Done | 1c | — |
| ~~**1d-ext** Per-session caching (transcription + speaker ID)~~ | ✓ Done | 1d | — |
| ~~**1e** Status report + pre-run summary~~ | ✓ Done | 1c | — |
| **2a** Content hashes on outputs | Small (10 lines) | 1b | Core feature work |
| **2b** Verify hashes on load | Small (20 lines) | 2a, 1c | Core feature work |
| **2c** Input change detection | Medium (50 lines) | 2a | Core feature work |
| **2d** `bristlenose status` command | Small (CLI only) | 1b | Anything |
| **3a** `bristlenose reset` command | Small-medium | 0c, 1b | Anything |
| **4a-d** Event log + provenance | Large (new subsystem) | 1b | Needs design |
| **5a-d** Incremental sessions + change detection | Large (new subsystem) | 2c, 4b | Needs design |
| **5e** Suggest autotagging for new quotes | Medium (50 lines) | 5a, AutoCode | Anything |
| **6a** Analytical context query layer | Small (new helper) | AutoCode tables | Anything |
| **6b** Suggestion engine for re-runs | Medium | 6a, 5a | Core feature work |

**Recommended order**:
1. ~~Ship 0c (per-project DB)~~ ✓ Done
2. ~~Ship 1a + 1b together (manifest foundation)~~ ✓ Done
3. ~~Ship 1c (resume from completed stages)~~ ✓ Done
4. ~~Ship 1d + 1d-ext (per-session tracking for all stages)~~ ✓ Done
5. ~~Ship 1e (status report + pre-run summary)~~ ✓ Done
6. Ship 2a + 2b + 2d (hashing + verification — one session, 2 hours)
7. Ship 2c (input change detection — one session, 2 hours)
8. Ship 3a (reset command — one session, 1-2 hours)
9. Phases 4-5: design and schedule when Phases 1-3 are stable
10. Ship 5a-5d (incremental sessions + source change detection — needs Phases 1-3 as foundation)
11. Ship 5e + 6a-6b (analytical context preservation — depends on AutoCode being used in the wild; need real accept/deny data to make suggestions meaningful)

After steps 1-4, users have crash recovery. After steps 1-7, users have crash recovery + integrity verification + clean re-runs. That's "I can trust this tool with real work" level.

Phases 4-5 (event log, provenance, incremental sessions) are "I can build a long-lived research practice on this tool" level. Important, but the trust foundation comes first.

Phase 6 (analytical context preservation) is "the tool knows me and adapts to my workflow" level. It requires AutoCode to be shipping and researchers to be generating accept/deny data. The infrastructure is already there (SQLite tables) — what's missing is the query/suggestion layer on top.

## References

**Build systems**
- Mokhov, Mitchell & Peyton Jones (2018), _"Build Systems à la Carte"_, ICFP
- Feldman (1979), _"Make"_, Software: Practice and Experience
- Mitchell (2012), _"Shake Before Building"_, ACM SIGPLAN
- Dolstra (2006), _"The Purely Functional Software Deployment Model"_, PhD thesis

**Data integrity & recovery**
- Mohan et al. (1992), _"ARIES"_, ACM TODS
- Rosenblum & Ousterhout (1992), _"Log-Structured File System"_, ACM TOCS
- Bonwick et al. (2003), _"The Zettabyte File System"_, FAST
- Gray & Reuter (1993), _Transaction Processing_, Morgan Kaufmann

**Event sourcing & immutability**
- Kleppmann (2017), _Designing Data-Intensive Applications_, O'Reilly
- Helland (2015), _"Immutability Changes Everything"_, ACM Queue
- Kreps (2013), _"The Log"_, LinkedIn Engineering

**Distributed workflows**
- Garcia-Molina & Salem (1987), _"Sagas"_, ACM SIGMOD
- Helland (2012), _"Idempotence Is Not a Medical Condition"_, ACM Queue

**Content-addressable storage**
- Git object model (Chacon & Straub, 2014, _Pro Git_)
- Benet (2014), _"IPFS"_

**Conflict resolution**
- Shapiro et al. (2011), _"CRDTs"_, SSS
- Kleppmann & Beresford (2017), _"Conflict-Free Replicated JSON"_, IEEE TPDS

**Data pipelines**
- Zaharia et al. (2012), _"Resilient Distributed Datasets"_ (Spark), NSDI
- dbt documentation (docs.getdbt.com)
- DVC documentation (dvc.org)

**User modelling**
- Fischer (2001), _"User Modeling in Human-Computer Interaction"_, User Modeling and User-Adapted Interaction, Springer

**Incremental computation**
- Acar et al. (2006), _"Adaptive Functional Programming"_, ACM TOPLAS — self-adjusting computation where outputs update incrementally when inputs change
- Hammer et al. (2014), _"Adapton"_, ACM OOPSLA — demand-driven incremental computation with precise dependency tracking

**Change detection**
- Tridgell & Mackerras (1996), _"The rsync algorithm"_, Australian National University — the size+mtime fast path optimisation for file change detection
