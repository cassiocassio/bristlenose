# Pipeline Resilience & Data Integrity

> **Status**: Design research — not yet implemented
> **Scope**: Big-picture architecture for crash recovery, incremental re-runs, provenance tracking, and human/LLM merge
> **Trigger**: Plato stress test (Feb 2026) — pipeline ran out of API credits mid-run, stale SQLite data from previous project leaked into serve mode, intermediate JSON files weren't written by `analyze` command, recovery required re-spending $3.50 on LLM calls already made

## The problem

People force-quit processes. Internet connections to LLMs drop. API credits run out halfway through a run. Right now, Bristlenose treats every run as all-or-nothing: if it's interrupted, the user must pass `--clean` (which deletes everything) and re-run from scratch — re-transcribing audio, re-extracting quotes, re-spending money on LLM calls that already succeeded.

The current pipeline has **no checkpointing, no resume, no integrity verification, and no provenance tracking**. The `analyze` command doesn't even write intermediate JSON for its later stages (a bug discovered during the Plato run). The serve-mode SQLite DB is global (`~/.config/bristlenose/bristlenose.db`), so stale data from previous projects leaks across sessions.

### What we need now

- **Crash recovery**: resume from the last completed stage (or last completed session within a stage)
- **Data integrity**: know what's trustworthy and what's incomplete/corrupt
- **Status reporting**: tell the user what state their data is in before and during a run
- **Incremental re-runs**: only redo what's stale, reuse everything that's still valid

### What we need in the future

- **Add/remove interviews**: merge new findings without breaking existing data
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

#### 0a. Fix `analyze` to write intermediate JSON

**What's wrong**: `run()` writes `screen_clusters.json` and `theme_groups.json` to `.bristlenose/intermediate/`. The `analyze` command doesn't — it was just missing the same `write_intermediate_json()` calls. This means `bristlenose render` fails after `bristlenose analyze` because the files it needs don't exist.

**The fix**: Add the same 4 lines to `run_analysis_only()` that `run()` already has. Copy-paste.

**What it touches**: `pipeline.py` only.

**Risk**: None. Just writes files that should have been written already.

#### 0b. Make `write_intermediate` default to `True`

**What's wrong**: The setting defaults to `False`, meaning intermediate JSON is never written unless the user sets it. This means `render` (which is free — no LLM cost) fails because there's nothing to render from.

**The fix**: Change the default in `config.py` from `False` to `True`.

**What it touches**: `config.py` only.

**Risk**: Writes a few extra JSON files to `.bristlenose/intermediate/`. They're small (KB to low MB). No downside.

#### 0c. Make the SQLite DB per-project instead of global

**What's wrong**: The serve-mode DB lives at `~/.config/bristlenose/bristlenose.db` — one DB for all projects. If you serve project A, then serve project B, project A's data is still in the DB. Stale sessions, stale quotes, stale everything.

**The fix**: Put the DB inside the output directory: `.bristlenose/bristlenose.db`. Each project gets its own DB. The serve command creates/opens the DB in the project's output dir.

**What it touches**: `server/database.py` (DB path), `server/app.py` (DB initialization). Maybe 10-20 lines.

**Risk**: Low. Existing global DB becomes unused. New projects get clean DBs automatically. Old projects that were served before won't have a local DB yet — serve creates one fresh (which is what you want).

---

### Phase 1: Crash recovery (the manifest)

**Goal**: If the pipeline is interrupted, re-running it picks up where it left off instead of starting from scratch. The user sees a status report of what's done and what's left.

This is the foundational change. Everything else builds on it.

#### 1a. Define the manifest model

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

#### 1b. Write manifest after each stage

**What it is**: After each stage completes in `pipeline.py`, write the manifest to disk. This is the "journal" — a record of what's done.

**How it works**: At the start of `run()`, create a manifest (or load an existing one). After each stage succeeds, update the manifest and write it to `.bristlenose/pipeline-manifest.json`. If the pipeline is interrupted, the manifest records everything up to the last completed stage.

**What it touches**: `pipeline.py` — add ~5 lines after each stage (call a helper that updates and writes the manifest). `manifest.py` — add read/write helpers.

**Risk**: Very low. The manifest is a new file that nothing reads yet. Writing it is a side effect that doesn't change pipeline behavior. Existing tests still pass — they don't check for the manifest.

**Backward compatibility**: Projects without a manifest still work exactly as before. The manifest is created on the next run.

#### 1c. Read manifest on startup and skip completed stages

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

#### 1d. Per-session tracking for expensive stages

**What it is**: Steps 1a-1c track at the stage level: "quote extraction is complete" or "quote extraction is incomplete." But quote extraction processes sessions independently — if 7 of 10 sessions succeeded, we should save those 7 and only re-run 3.

**How it works**: The manifest gets a `sessions` field on the per-session stages (transcription, topic segmentation, quote extraction):

```python
class SessionRecord(BaseModel):
    status: StageStatus
    session_id: str
    completed_at: str | None = None

class StageRecord(BaseModel):
    # ... existing fields ...
    sessions: dict[str, SessionRecord] | None = None  # only for per-session stages
```

Each per-session stage writes its results incrementally — after processing each session, update the manifest. On resume, only sessions marked incomplete are re-processed.

**What it touches**: `pipeline.py` (the LLM-calling loops in topic segmentation and quote extraction), `manifest.py` (the session-level model). The stage functions themselves (`topic_segmentation.py`, `quote_extraction.py`) don't change — they already return per-session results. The change is in how `pipeline.py` calls them and saves results.

**Risk**: Medium. Need to handle the merge of old cached results + new results for the same stage. But it's straightforward — load existing quotes for sessions s1-s7, extract new quotes for s8-s10, concatenate.

#### 1e. Status report and `--resume` flag

**What it is**: Before running anything, print a status report showing what's cached and what needs doing. Add a `--resume` flag that's on by default (and `--clean` becomes "delete everything and start fresh").

**How it works**: Read the manifest, validate file existence, print a summary. If there's nothing to resume from, run normally. If there is, show the plan and ask for confirmation.

**What it touches**: `cli.py` (flag handling, status display), `manifest.py` (validation helper).

**Risk**: Low. It's just printing and flag parsing. The actual resume logic is already in place from 1c/1d.

**What the user sees**:
```
$ bristlenose run interviews/

Project status:
  ✓ 10 sessions ingested
  ✓ 10 transcripts (all valid)
  ✓ 10 topic maps
  ⚠ 7/10 sessions have quotes (3 failed — credit exhaustion)
  ✗ Clusters and themes not generated yet

Resuming from quote extraction (3 sessions remaining).
Estimated cost: ~$0.45
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

**Goal**: Add or remove interviews from an existing project without starting over.

#### 5a. Detect new/removed sessions

**What it is**: On re-run, compare the current set of input files against the manifest's recorded sessions. Identify added, removed, and unchanged sessions.

#### 5b. Per-session incremental processing

**What it is**: Only transcribe, segment, and extract quotes for new sessions. Keep existing sessions' data.

#### 5c. Re-cluster and re-theme with merged data

**What it is**: After extracting quotes for new sessions, re-run clustering and theming on the full set (old + new quotes). These stages are cross-session and relatively cheap (one LLM call each).

#### 5d. Handle removed sessions

**What it is**: When a session is removed, exclude its quotes from clustering/theming and re-run those stages. Don't delete the transcript — mark it as excluded in the manifest.

---

## Sequencing: what to build when

The key insight: **each sub-step is a single PR-sized change**. None of them requires a feature branch. They land on main incrementally.

| Step | Size | Depends on | Can ship with |
|------|------|-----------|---------------|
| **0a** Fix analyze intermediate writes | Tiny (4 lines) | Nothing | Anything |
| **0b** write_intermediate defaults True | Tiny (1 line) | Nothing | Anything |
| **0c** Per-project SQLite DB | Small (20 lines) | Nothing | Anything |
| **1a** Manifest model | Small (new file) | Nothing | Anything |
| **1b** Write manifest after stages | Medium (30 lines in pipeline.py) | 1a | Nothing breaking |
| **1c** Skip completed stages on resume | Medium-large (100 lines) | 1b | Core feature work |
| **1d** Per-session tracking | Medium (50 lines) | 1c | Core feature work |
| **1e** Status report + --resume flag | Small (CLI only) | 1c | Core feature work |
| **2a** Content hashes on outputs | Small (10 lines) | 1b | Core feature work |
| **2b** Verify hashes on load | Small (20 lines) | 2a, 1c | Core feature work |
| **2c** Input change detection | Medium (50 lines) | 2a | Core feature work |
| **2d** `bristlenose status` command | Small (CLI only) | 1b | Anything |
| **3a** `bristlenose reset` command | Small-medium | 0c, 1b | Anything |
| **4a-d** Event log + provenance | Large (new subsystem) | 1b | Needs design |
| **5a-d** Incremental sessions | Large (new subsystem) | 2c, 4b | Needs design |

**Recommended order**:
1. Ship 0a + 0b + 0c first (bugs and config — do in the next session, 30 minutes)
2. Ship 1a + 1b together (manifest foundation — one session, 2 hours)
3. Ship 1c (resume from completed stages — one session, 3-4 hours, the biggest single step)
4. Ship 1d + 1e together (per-session tracking + UI — one session, 2-3 hours)
5. Ship 2a + 2b + 2d (hashing + status command — one session, 2 hours)
6. Ship 2c (input change detection — one session, 2 hours)
7. Ship 3a (reset command — one session, 1-2 hours)
8. Phases 4-5: design and schedule when Phases 1-3 are stable

After steps 1-4, users have crash recovery. After steps 1-7, users have crash recovery + integrity verification + clean re-runs. That's "I can trust this tool with real work" level.

Phases 4-5 (event log, provenance, incremental sessions) are "I can build a long-lived research practice on this tool" level. Important, but the trust foundation comes first.

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
