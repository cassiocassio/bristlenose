---
status: current
last-trued: 2026-04-26
trued-against: HEAD@port-v01-ingestion on 2026-04-26 (commit 9585bcb)
---

> **Truing status:** Current — Phase 1f / 4a-pre shipped on `port-v01-ingestion` in 4 slices + a review-fix pass; doc reconciled against shipped code on 2026-04-26. Phase 0–2c CLI-side claims remain accurate. The Swift consumer side now exists (`desktop/Bristlenose/Bristlenose/EventLogReader.swift`); see updated §"Desktop consumer mapping" and §"Cross-boundary naming". Phase 3+ remain design-only. See round-3 changelog below.

## Changelog

- _2026-04-26_ — **Phase 1f / 4a-pre shipped on `port-v01-ingestion` (4 slices + review-fix pass).** Doc reconciled against shipped code via `/true-the-docs --topic pipeline-resilience`. Reality vs spec deltas captured below; the spec largely held. Slices: (1) `bristlenose/events.py` — Pydantic event models, ULID, append+fsync writer, NUL/partial-line tail reader (commit `2caa3ed`); (2) `bristlenose/run_lifecycle.py` — context manager, PID file, signal handler, exception → `Cause` categoriser (commit `b2ce911`); (3) `bristlenose/cost.py` — `RunCost` + `format_cost_estimate` + `RunHandle.set_cost` wired into terminus events (commit `ea62963`); (4) `desktop/Bristlenose/Bristlenose/EventLogReader.swift` + extended `PipelineFailureCategory` / `PipelineState` (commit `059a9af`). Test target wiring: commits `1c263ae` + `5fff720` (BristlenoseTests target + `@MainActor` suite isolation, 90 Swift tests passing). **Round-3 review pass** (commit `9585bcb`) made these post-spec adjustments worth recording:
    - **`FileNotFoundError` removed from `MISSING_DEP`.** Pipelines raise `FileNotFoundError` for missing input/audio/people files all the time; the original spec wording ("FileNotFoundError on a binary lookup is also missing-dep") was wrong because the categoriser can't tell binary lookups apart from data-file lookups. `MISSING_DEP` now matches `ImportError` / `ModuleNotFoundError` only. `FileNotFoundError` lands in `UNKNOWN`.
    - **Substring matchers anchored with `\b` word boundaries.** Spec used substring `in` checks; `"credit"` matched `"credentials"`, `"authentication"` matched generic `OSError` quoting it. Now `re.compile(r"\b…\b")`.
    - **File mode hardening.** Both `pipeline-events.jsonl` and `run.pid` now open with `O_NOFOLLOW` + mode `0o600`. Defensive: events log carries OS username + hostname in the process envelope; restrict readability to project owner and refuse symlink-attacked targets. Spec didn't address.
    - **`/bin/ps` absolute path in Python `_ps_start_time`.** Matches Swift `psLstart` and refuses hostile `$PATH` shadowing.
    - **`atexit.register(_remove_pid_file, ...)` removed.** The `try/finally` already cleans up every path; `atexit` was unbounded list growth on re-entry. Spec implied atexit; reality is the context manager handles it cleanly.
    - **Synthesised stranded-run message rewritten user-side.** `"Process exited without writing a terminus event"` → `"Analysis stopped unexpectedly."` Both Python (`bristlenose/run_lifecycle.py:_reconcile_stranded_run`) and Swift (`EventLogReader.deriveState`) updated.
    - **Swift `parseManifest` reads manifest once.** Spec implied a duplicate `Data(contentsOf:)` between `stagesCompleteFromManifest` and the fallback path. Refactored to read the JSON once and thread `stages` through both paths — saves 1 read × N projects on launch.
    - **Swift ISO8601 fallback formatter.** `iso8601WithFractional` requires fractional seconds, but Python's `datetime.isoformat()` omits them when `microsecond == 0`. Added `iso8601Plain` fallback + new `parseISO8601(_:)` helper. Spec didn't anticipate.
    - **Swift `readBoundedTail` returns `(data, wasTruncated)`.** When the events log exceeds 64 KB, `tailEvent` drops the first slice (likely chopped mid-line). Was a real correctness bug for files past Phase 4a's growth horizon — fixing prospectively.
    - **Sidebar copy reverted from verb-presuming.** `"Stopped — resume or re-analyse"` → `"Stopped"`; `"Transcribed · ready to analyse"` → `"Transcribed"`. The Resume / Re-analyse… verbs are deferred to a separate desktop-UX iteration (`docs/private/desktop-ux-iteration.md` §3); the sidebar copy must not promise verbs that don't exist yet.
    - **Failure-category copy alignment.** `"A required tool isn't installed"` → `"Setup needed — a required tool isn't installed"`; pill label `"Missing dependency"` → `"Setup needed"`; dropped leading `"The"` from the new category labels for tone parity with the existing set.
    - **Python `_signal_handler` keeps the spec's flag-and-flush pattern.** Records `_caught_signal` and re-raises `KeyboardInterrupt`; the wrapper catches at the outer scope and writes `RunCancelledEvent`. Verified by 31 lifecycle tests including subprocess SIGINT + SIGTERM paths.
    - **Tests:** 2328 Python passed (4 new test files: `tests/test_events.py` 37, `tests/test_run_lifecycle.py` 31, `tests/test_cost.py` 12), 90 Swift passed (BristlenoseTests target wired up; `EventLogReaderTests.swift` covers all event-type × cause-category mappings, NUL/partial-line recovery, PID-liveness).
    - **Parked architectural questions** (still open after round-3, kept for explicit user decision): cost on cancelled runs (RunHandle currently sets cost only after `pipeline.run()` returns; cancelled mid-stage runs report `cost=None` for partial work that already cost the user money); categoriser refactor to typed-exception `isinstance` dispatch; Swift forward-compat fallback for unknown `Cause.category` values; OS-username hashing in process envelope; PID liveness across network volumes (hostname check); `/bin/ps` sandbox blocker (Track C C0 — needs `proc_pidinfo`/libproc port for shipped builds); fsync cadence revisit when Phase 4a stage-level events land.
- _2026-04-25 (afternoon)_ — **Round-2 review pass on Phase 1f / 4a-pre.** Re-fanned-out (code-review + design-doc-review + community-practice). Round-2 fixes scrubbed field-name drift (`cost_usd` → `cost_usd_estimate` in 5 places) and corrected the Swift cause-name cross-reference (the rename narrative was based on a stale snapshot of `PipelineFailureCategory` — actual cases are `auth | network | quota | disk | whisper | unknown`, no rename needed; new entries added additively). Round-2 decisions recorded:
    - **`stages_complete` snapshot dropped — derive from manifest** at display time. Removes dual-write drift risk. Manifest is the single source of truth for stage state.
    - **`kind: render` dropped** — render runs don't write the events log. Aligns with the project rule "actively remove static render, don't find clever uses".
    - **`cause.retryable` field dropped** — derivable from `category` via `is_retryable()`. Storing it duplicates the rule.
    - **PID-file ownership: Python writes its own** at `<output_dir>/.bristlenose/run.pid` containing `(pid, start_time)`. Defeats PID reuse on busy macOS. Pure-CLI users get correct behaviour; Swift's existing PID file stays for orphan-attach (different concern).
    - **`process` envelope** added on `run_started` (`pid, start_time, hostname, user, bristlenose_version, python_version, os`) — Sentry / OTel / Dagster precedent.
    - **`signal_name` field** added alongside `signal: int` for grep-friendly forensics.
    - **`currency` field** added to the price table for future EUR / GBP support.
    - **Durability contract** documented: `os.fsync()` survives process crashes, not power loss; explicit non-goal.
    - **`cause.message` capped at 4 KB** at the writer; protects Swift's existing `readLogTail` 64 KB window.
    - **OTel-aligned `cause` field naming** noted (not renamed; future tooling reads our shape with minimal mapping).
    - **`O_APPEND` atomicity citation corrected** — POSIX kernel-level vnode lock on regular files, not PIPE_BUF (which is the pipe / FIFO guarantee).
- _2026-04-25 (morning)_ — **Drafted Phase 1f (run outcomes + cost) and Phase 4a-pre (run-level event log).** Two new sections added: "Run outcomes and intent" inside Architecture (after "Per-session granularity"), and Phase 1f / 4a-pre entries in the phases list. Trigger: 25 Apr 2026 design discussion — Swift `parseManifest` was reading interrupted runs as `.ready` because there was no explicit terminal-outcome record on disk. Reviewed by code-review + design-doc-review + community-practice fan-out (Airflow / Dagster / Prefect / Celery / LangSmith / CPython signal docs), then iterated. Round-1 decisions recorded:
    1. **Single source of truth (events log, not dual store).** Run-level outcome data lives **only** in `pipeline-events.jsonl` (append-only). It does not live on the manifest. The manifest keeps its existing per-stage-resume job, unchanged. "Current run state" is derived by tail-reading the events log. Rejected the Dagster/Prefect dual-store pattern as overkill for a CLI tool with one consumer.
    2. **Structured `cause` object, not flat enum.** Captures the full forensic story so users get an honest answer to "why did it fail?". Flat enum would lose detail we'll thank ourselves for later as failure modes proliferate.
    3. **No heartbeat field, no daemon thread.** Liveness is derived from a Python-owned PID file (round 2 sharpened: with `(pid, start_time)` to defeat PID reuse). One less file, one less correctness surface than a heartbeat thread.
    4. **Cost honestly framed as estimate.** Token counts (`input_tokens`, `output_tokens`) are real and authoritative — provider returns them in `usage`. Dollar amount is `cost_usd_estimate` (not `cost_usd`) with a `price_table_version` field; UI must render as "~$X (est.)", never bare.
    5. **Three-verb UX** (Resume / Retry / Re-analyse…). Resume and Retry are mechanically identical (both `start()` with cache); the labels signal *cause of interruption* honestly. Re-analyse… is the destructive option. Validates against Time Machine + Apple Software Update + git rebase precedent.
    Forward-compat callouts ensure the shape survives Phase 4a (full event log extends additively), Phase 4d (3-way merge), and Phase 5 (incremental re-runs). **Not yet shipped — design only.**
- _2026-04-24_ — Tier 2 truing follow-up: anchor precision in desktop-consumer paragraph (`PipelineRunner.swift:504-583` covers both `readManifestState` and `parseManifest`; partial-state strict check at `:561-579`); added `applyScanResult` anchor (`:469-487`); added `.unreachable` to the desktop pill enumeration (was `.ready`/`.idle`/`.failed` only); replaced "fix tracked separately" with a commit anchor (the strict all-stages check is the current code at `:561-579`; partial-state was never reachable post-Slice 7).
- _2026-04-23_ — trued up during port-v01-ingestion QA: added cross-ref to `design-subprocess-lifecycle.md`; noted Swift desktop consumer collapses partial → `.idle` and uses all-stages-complete criterion for `.ready`; noted PID file sidecar (`<App Support>/Bristlenose/pids/`) is Swift-owned and not part of the manifest schema. Anchors: `PipelineRunner.swift:534-583`. No status-line changes.
- _Previous_ — Phase 0–2c implemented per status header below.

# Pipeline Resilience & Data Integrity

> **Status**: Phase 0–1e implemented (crash recovery, per-session caching, `bristlenose status` command, pre-run resume summary); Phase 2a implemented (SHA-256 content hashes on stage outputs stored in manifest); Phase 2b implemented (verify hashes on load — corrupted/tampered files trigger re-run instead of silent use); Phase 2c implemented (input change detection — source file metadata hashing via size+mtime, upstream content_hash propagation, cascade invalidation); **Phase 1f + 4a-pre shipped 2026-04-26 on `port-v01-ingestion`** in 4 slices + a review-fix pass (run-level outcome + structured cause + estimated cost in a single-source append-only `pipeline-events.jsonl` event log; manifest unchanged); Phase 3 (reset command) next
> **Scope**: Big-picture architecture for crash recovery, incremental re-runs, provenance tracking, human/LLM merge, source material change detection, mid-run provider switching, and analytical context preservation
> **Trigger**: Plato stress test (Feb 2026) — pipeline ran out of API credits mid-run, stale SQLite data from previous project leaked into serve mode, intermediate JSON files weren't written by `analyze` command, recovery required re-spending $3.50 on LLM calls already made
> **Desktop consumer**: the macOS app reads the same manifest via `PipelineRunner.readManifestState` (`PipelineRunner.swift:504-532`, delegates to `parseManifest` at `:534-583`) and `applyScanResult` (reconcile after scan, `:469-487`). Desktop-side semantics: `.ready` requires every stage in the manifest to be `complete` (strict loop at `:561-579`); missing-status / partial / pending collapse to `.idle`; unreachable folders return `.unreachable` from `readManifestState` directly. Partial-state surfacing described elsewhere in this doc (e.g. "7/10 sessions" examples) is CLI-only — the post-scan desktop pill shows `.ready` / `.idle` / `.failed` / `.unreachable`; `.running` and `.queued` are runner-owned live states. PID file sidecar lives in `~/Library/Application Support/Bristlenose/pids/<uuid>.pid` (`:441-452`) — Swift-owned, not part of the manifest schema, placed in App Support so it stays writable under TestFlight App Sandbox without bookmark juggling. See `design-subprocess-lifecycle.md` for orphan attach mechanics and the Stop-semantics distinction (`intentionalStop` flag at `:206`) added by commit `49930e4`. **Shipped (Phase 1f / 4a-pre, 2026-04-26):** [`EventLogReader.deriveState`](desktop/Bristlenose/Bristlenose/EventLogReader.swift:103) is the new primary; [`PipelineRunner.parseManifest`](desktop/Bristlenose/Bristlenose/PipelineRunner.swift:676) consults it first and falls back to the strict render-present check only when no `pipeline-events.jsonl` exists (back-compat for projects predating this work). Run outcome data lives in the events log, not the manifest.

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
  cost_usd_estimate: 1.83
  price_table_version: "2026-02-20"
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

> **Zombie-fields warning.** `total_cost_usd` / `total_input_tokens` / `total_output_tokens` shown below are Phase 1a-declared but **never populated in code** — `PipelineManifest.total_cost_usd: float = 0.0` exists in `bristlenose/manifest.py` and stays at zero. Treat as decorative; lifetime cost is derived from `SessionRecord.cost_usd_estimate` (Phase 1f) and `pipeline-events.jsonl` `run_completed` events (Phase 4a-pre). The zombie fields will be removed in a future cleanup; not load-bearing.

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

**Note (2026-04-25 design pivot).** Run-level outcome data (`kind`, `outcome`, `cause`, per-run cost) does **not** live on the manifest. It lives in a single append-only `pipeline-events.jsonl` event log alongside the manifest. The manifest keeps its existing job — per-stage progress for resume — and stays the single source of truth for *that*. The event log is the single source of truth for *run-level* outcome and history. Two files, two non-overlapping concerns. See "Run outcomes and intent" below for the lifecycle and "Phase 4a-pre" for the event log shape.

The top-level `total_*` fields above (Phase 1a-declared but never implemented) are pre-existing zombie fields. Lifetime project cost is derived at read time from the event log (sum across `run_completed` events) and per-session records (Phase 1d). The zombie fields will be removed in a future cleanup; not load-bearing.

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

### Run outcomes and intent

> **Status:** **shipped** 2026-04-26 on `port-v01-ingestion` (commits `2caa3ed`, `b2ce911`, `ea62963`, `059a9af` + review-fix pass `9585bcb`). Replaced the implicit `parseManifest` inference (Swift desktop) with an explicit on-disk record of how each run ended. Closes the desktop-consumer drift documented in the status header above. Implementation refs throughout the section below.

**The problem this solves.** The shipped manifest schema records *per-stage* progress (running / complete) but not *run-level* outcome. The desktop's `PipelineRunner.parseManifest` has to infer "did the pipeline finish?" from "are all observed stages marked complete?" — which is wrong, because the Python side writes the manifest incrementally (one `write_manifest` per `mark_stage_complete`). A crash mid-run leaves a manifest with only the stages that got that far, all marked complete. Inference says `.ready`. Reality is "interrupted, no report" (QA, 23 Apr 2026 — see `gentle-brewing-penguin.md`).

The deeper issue is that "where we are" depends on three orthogonal dimensions the schema currently flattens onto a single per-stage status field:

1. **Outcome** — what happened? (running / completed / cancelled / failed)
2. **Kind** — what was attempted? (`run` / `analyze` / `transcribe-only` / `render`)
3. **Cause** — why did it end this way? (user signal / parent died / API auth / API quota / network / missing dependency / unknown)

Plus orthogonal to all three: **what work has value right now** (artifacts on disk) and **what it cost to produce** (tokens, dollars, wall time). Without these, the desktop has to choose between under-honesty ("Analysed 5 min ago" for a project with no report) and over-conservatism ("Idle" for a project with eight hours of valid transcripts).

**The shape: an append-only `pipeline-events.jsonl` event log.** (Earlier drafts proposed a `last_run` block on the manifest; the 2026-04-25 single-source pivot rejected that — see changelog entry above and "Open decisions" below for the resolution.)

```json
// pipeline-events.jsonl — append-only, one JSON object per line
{"schema_version":1,"ts":"2026-04-25T09:00:00Z","event":"run_started","run_id":"01HZX4N9MXQ5T7B3YJZP2K8FCV","kind":"run","started_at":"2026-04-25T09:00:00Z","process":{"pid":48312,"start_time":"2026-04-25T09:00:00.124Z","hostname":"martins-mbp","user":"cassio","bristlenose_version":"0.14.6","python_version":"3.12.3","os":"darwin-arm64"}}
{"schema_version":1,"ts":"2026-04-25T09:12:34Z","event":"run_cancelled","run_id":"01HZX4N9MXQ5T7B3YJZP2K8FCV","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:12:34Z","outcome":"cancelled","cause":{"category":"user_signal","exit_code":null,"signal":2,"signal_name":"SIGINT","code":null,"message":"SIGINT received","provider":null,"stage":"transcribe","session_id":"s4"},"input_tokens":12420,"output_tokens":0,"cost_usd_estimate":0.46,"price_table_version":"2026-04-25"}
```

**Single source of truth.** Run-level outcome data lives **only** in `pipeline-events.jsonl`. It does not live in the manifest. The manifest keeps its existing job (per-stage progress for resume) and stays the single source of truth for that. Two files, two non-overlapping concerns; no projection to keep in sync. "Current run state" is **derived at read time** by tail-reading the event log (most recent `run_*` line). Decision recorded 2026-04-25 — see changelog. The dual-store pattern (Dagster, Prefect, Airflow) is overkill for a CLI-invoked indie tool with one consumer.

**Liveness without heartbeat.** When the most recent event is `run_started` (no following terminus), the run is in flight. Liveness is determined from the **PID file** (`<App Support>/Bristlenose/pids/<uuid>.pid`, Swift-owned, already shipped) — not a manifest heartbeat field. PID alive → `.running`. PID dead → stale; display as `.failed(cause: unknown)`. One less file, one less daemon thread, one less correctness surface. The PID file already exists for orphan-attach; we just lean on it.

Per-event field semantics:

| Field | Type | Where | Meaning |
|---|---|---|---|
| `schema_version` | int | every line | Event-line envelope version. Starts at 1. Future Phase 4a extends additively without bumping. |
| `ts` | ISO8601 | every line | When this event was written. |
| `event` | `str, Enum` | every line | One of `run_started` / `run_completed` / `run_cancelled` / `run_failed`. (Phase 4a will add stage-level + human-edit events; the four run-level types stay as-is.) |
| `run_id` | str (ULID) | every line | Stable identifier for this run. ULID for sortability. Stamped on every event so terminus can be correlated back to start (Dagster/Airflow/Prefect convention). |
| `kind` | `str, Enum` | every line | What was attempted. `KindEnum(str, Enum)`: `run` / `analyze` / `transcribe-only` (same convention as `StageStatus` in `manifest.py:23`). New kinds require code change + migration. **Note:** the `render` command does not write the events log — see "Open decisions" resolution below. |
| `started_at` | ISO8601 | every line | The run's `started_at` is repeated on each event so terminus events are self-contained — a future reader can reconstruct duration without joining back to `run_started`. |
| `ended_at` | ISO8601 | terminus only | When the run ended. Wall time is `ended_at - started_at`, computed not stored. |
| `outcome` | `str, Enum` | terminus only | `completed` (kind reached its terminal stage) / `cancelled` / `failed`. (No `running` enum value — "in flight" is the absence of a terminus event.) |
| `cause` | object or null | terminus only | Structured cause object — see below. Null on `run_completed`. Required on `run_cancelled` / `run_failed`. |
| `process` | object | `run_started` only | Diagnostics envelope: `pid`, `start_time` (ISO8601 — process creation time, used together with `pid` to defeat PID reuse on busy machines), `hostname`, `user`, `bristlenose_version`, `python_version`, `os` (e.g. `darwin-arm64` / `linux-x86_64`). Captured once on `run_started`; the `(pid, start_time)` pair is the canonical PID-liveness record (also written to the project's PID file — see lifecycle below). Sentry / OTel / Dagster all capture this; we'll want it the first time a user reports cross-machine variation. |
| `input_tokens` / `output_tokens` | number | terminus only | **Source of truth** for "what work was done". These are the actual counts the LLM provider returned in `usage` fields — we know them exactly. Real, not estimated. |
| `cost_usd_estimate` | number or null | terminus only | **Plausible estimate**, not authoritative — explicitly named to prevent misreading. Derived from `input_tokens` × `output_tokens` × per-model price table. We don't know the internals of provider billing (rate-limit penalties, cache discounts, batch tiers, custom pricing on enterprise plans), so any USD number we compute is a best guess. UI must surface as "~$0.46 (est.)", never as "$0.46". Null when no LLM calls were made (e.g. `kind=transcribe-only` with local Whisper). |
| `price_table_version` | str or null | terminus only | Which price table generated the estimate. Lets a reader recompute with a newer table later if pricing changes. ISO date or version string. Null when `cost_usd_estimate` is null. The price table itself is a JSON file shipped inside the package and includes a `currency` field (USD today; future-proofs against EUR / GBP price leaks). |

(*Removed* in 2026-04-25 round-2 review: `stages_complete` snapshot — drop, derive from `manifest.stages` at read time. The system refuses concurrent runs, so the manifest can't have advanced between the events-log write and the read. Deriving avoids dual-write drift; manifest is the single source of truth for stage state.)

**The `cause` object.** Structured to capture the full forensic story — community recommendation §5, code-review Q2, decision recorded 2026-04-25. A flat enum would lose the kind of detail the user reads when they ask "it just failed, why". Field shape loosely aligns with OpenTelemetry exception semantic conventions (`exception.type` ≈ `category`, `exception.message` ≈ `message`) and Sentry's `mechanism` schema (`mechanism.type` ≈ `category`, `mechanism.data.signal` ≈ `signal`) — future tooling that speaks either of those reads our shape with minimal mapping.

```json
{
  "category": "quota",              // top-level enum, source of truth for desktop UI dispatch
  "code": "rate_limit_exceeded",    // provider-specific code if available (e.g. Anthropic 429 subtype)
  "message": "Anthropic 429: rate limit exceeded for sonnet-4. Retry after 60s.",  // raw error string, capped at 4 KB
  "provider": "anthropic",          // null if not provider-attributable
  "stage": "quote_extraction",      // stage emitting the failure / cancellation point
  "session_id": "s4",               // null if not session-attributable
  "exit_code": null,                // process exit status, when known
  "signal": null,                   // POSIX signal number, when terminated by signal (e.g. 2 = SIGINT, 15 = SIGTERM)
  "signal_name": null               // human-readable signal name ("SIGINT") — duplicates `signal` for grep-friendliness
}
```

**Pydantic discipline.** `Cause` is a `BaseModel` with explicit `Optional[X] = None` defaults on every field except `category`. Writer-side rule: `message` must be populated whenever `category != user_signal` — even if it's just `str(exc)`. The schema must not permit "we know it failed but we lost the why."

**Message size cap.** `message` is capped at 4 KB at the writer (`Cause._cap_message` validator in [`bristlenose/events.py`](bristlenose/events.py:128)). Two reasons: (1) Single event lines must fit in Swift's existing `readLogTail` 64 KB read window ([PipelineRunner.swift:570](desktop/Bristlenose/Bristlenose/PipelineRunner.swift:570)) so the line isn't truncated mid-string and silently discarded as malformed JSON. (2) `PIPE_BUF` on macOS is 4 KB for regular files; capping `message` keeps run-level event lines well under that and gives concurrent appenders a defence-in-depth backstop on local filesystems. Note: the cap is enforced via `model_validate` only — `Cause.model_construct(...)` would bypass it, but no call site uses `model_construct` today.

(*Removed* in 2026-04-25 round-2 review: `cause.retryable` — derivable from `category` per the table below; the rule lives in one place — Python `is_retryable(category)` — Swift mirrors. Storing it duplicates the rule.)

`category` is the dispatch enum (`CauseCategoryEnum(str, Enum)`):

| `category` | Outcome | Retryable? | Set by |
|---|---|---|---|
| `user_signal` | `cancelled` | yes | SIGINT/SIGTERM handler (via flag-and-flush) |
| `auth` | `failed` | no — fix credentials first | Any provider auth/credential error |
| `quota` | `failed` | yes — eventually, or switch provider | Rate limit or credit exhaustion |
| `api_request` | `failed` | sometimes (depends on `code`) | Provider rejected request (4xx other than auth/quota) |
| `api_server` | `failed` | yes — usually transient | Provider 5xx |
| `network` | `failed` | yes | TCP/DNS/timeout, no provider response |
| `whisper` | `failed` | sometimes (depends on `code`) | Whisper model load / transcription failure (e.g. corrupted audio, OOM) |
| `missing_dep` | `failed` | no — install dependency first | ffmpeg / whisper model / spaCy etc. not installed |
| `disk` | `failed` | no — free space first | ENOSPC / write failure |
| `unknown` | `failed` | yes — try again | Catch-all. Used by stale-running recovery (no handler ran) and for anything the categoriser doesn't recognise. |

The "retryable" column is the rule the desktop and CLI both apply via `is_retryable(category) -> bool` (Python source, Swift mirrors). It's *not* an on-disk field. Other `cause` fields are best-effort — populated when known, null when not. The desktop reads `category` for verb dispatch (`Fix credentials → Retry` for `auth`, `Switch provider → Retry` for `quota`, etc.) and surfaces `message` + `code` + `provider` + `stage` + `signal_name` in the failure popover for forensics.

**Cross-boundary naming.** Python [`CauseCategoryEnum`](bristlenose/events.py:62) and Swift [`PipelineFailureCategory`](desktop/Bristlenose/Bristlenose/PipelineRunner.swift:9) use the **same snake_case raw values** so JSON round-trips losslessly through the events log. Both enums currently carry the same 10 cases: original 6 (`auth | network | quota | disk | whisper | unknown`) plus the Phase 1f-added 4 (`user_signal | api_request | api_server | missing_dep`). Swift uses `camelCase` Swift names with explicit `String` rawValues (`case userSignal = "user_signal"`) so the language conventions hold on both sides while the wire format stays canonical. No existing case is renamed; pre-pivot drafts proposed renames based on a stale snapshot of the Swift enum and were rejected. Adding a new category requires coordinated changes on both sides (Python first, Swift in the next desktop release); the design doc currently treats this contract as stable, but a "decode unknown category as `.unknown` for forward-compat" question is parked (see round-3 changelog).

**`kind` × terminal-stage matrix.** What constitutes "completed" depends on `kind`:

| `kind` | "Completed" means | Terminal stage |
|---|---|---|
| `run` | All stages including render | `render` |
| `analyze` | All post-transcription stages including render | `render` |
| `transcribe-only` | All sessions transcribed | `transcribe` |

The `render` command does **not** write the events log — it's a read-only re-emission of cached JSON, no project-state change, no run-level outcome to record. This matches the project rule "static render is being phased out, don't find clever uses for it" (root CLAUDE.md, MEMORY `feedback_static_html_actively_remove.md`). If a future "I exported on date X" history is wanted, that's an export-tracking concern, not pipeline resilience.

This replaces the hardcoded `terminalStage = "render"` in Swift `PipelineRunner` (current commit `9ca4461`) — the Python side is the source of truth for "done", and Swift derives state from the event log.

**Lifecycle: writing the event log.**

The event log is **append-only**. There is no in-place update of any field, ever. Crash safety: write one full line + `fsync` per event; on read, discard the trailing line if it doesn't end in `\n` or fails to parse (standard JSONL recipe).

1. **`run_started`** — at the top of each CLI command. Generates a new ULID `run_id`. Captures the `process` envelope (`pid`, `start_time` from `psutil.Process(pid).create_time()`, `hostname`, `user`, `bristlenose_version`, `python_version`, `os`). Appends a `run_started` line including the envelope. **Also writes** a Python-side PID file at `<output_dir>/.bristlenose/run.pid` containing `(pid, start_time)` as JSON — this is the canonical PID-liveness record for "is a Python pipeline alive for this project?". Cleaned up by an `atexit` hook on clean exit and overwritten on next `run_started`. Distinct from Swift's `<App Support>/Bristlenose/pids/<UUID>.pid` (which stays for orphan-attach). Emits one INFO log line `run_started run_id=X kind=Y` to `<output_dir>/.bristlenose/bristlenose.log` (per CLAUDE.md "Logging" — desktop tails this for the popover). Per-stage progress continues to land in the manifest as today (Phase 1b/1c, shipped). The manifest does **not** record run-level outcome.
2. **`run_completed`** — at successful exit of the CLI command. Appends `run_completed` with `outcome: "completed"`, `cause: null`, `exit_code: 0`, `cost_usd_estimate` and token totals. INFO log line.
3. **`run_failed`** — top-level try/except wrapping the CLI command body. Appends `run_failed` with `outcome: "failed"`, structured `cause`, `exit_code` from `sys.exit` (or non-zero default), `error_summary`. INFO log line.
4. **`run_cancelled`** — SIGINT/SIGTERM handler. **Does not write from the handler.** The handler sets a module-level `_cancel_requested = True` flag and captures the signal number; the main loop checks the flag at safe points (between stages, between sessions, between LLM calls — natural break points the pipeline already has) and from there does the regular append with `outcome: "cancelled"`, `cause.category: "user_signal"`, `cause.signal: <num>`. Production pattern (CPython signal docs, Gunicorn arbiter, Sentry SDK). Avoids the re-entrancy hazard of writing from a handler.

There is no heartbeat loop and no daemon thread. No second writer. One file, one writer, append-only.

**Recovery: when a run's process dies without a terminus event.** Possible after kill -9 of the CLI subprocess, hard reboot, OOM-killer, parent app force-quit. The recovery rule is two-sided:

- **Swift desktop, on read:** tail the event log; if the most recent `run_*` event is `run_started` (no terminus), check PID liveness via the existing PID file (`PipelineRunner.aliveOwnedRunPID`). PID alive → display as `.running`. PID missing or dead → display as `.failed(cause.category: unknown)`. The desktop **does not write** the event log.
- **Python CLI, on next `start_run`:** if the tail of the event log is a stranded `run_started` (no terminus), append a synthesised `run_failed` for that prior run (`cause.category: unknown`, `cause.message: "Analysis stopped unexpectedly."`, preserving prior `kind` / `started_at` / `run_id`) before appending the new `run_started`. Implementation: [`run_lifecycle.py:_reconcile_stranded_run`](bristlenose/run_lifecycle.py:284). This is the only path that writes a terminus event without the run actually having ended cleanly — and it's append-only, no rewrite. Stages-complete derivation for the synthesised event is read at display time from the manifest (which captures the true on-disk state at recovery).

This split means the read path stays read-only (no Swift-side writes) and the rewrite-on-next-start happens at a natural transactional boundary in Python.

**Concurrency.** Two CLI processes against the same project race on the event log. The **operative defence is `ConcurrentRunError`** from `run_lifecycle.py:run_lifecycle` — the second process refuses to start if `<output>/.bristlenose/run.pid` matches a live `(pid, start_time)` pair. The atomicity of `O_APPEND` writes is a defence-in-depth backstop, not the primary guarantee. POSIX guarantees seek-to-end-and-write atomicity per `write()` call only up to `PIPE_BUF` (4 KB on macOS, larger on Linux) on regular files; in practice Linux ext4 / macOS APFS extend this further via the kernel-level vnode lock, but committing to ">PIPE_BUF atomicity" is unsafe across filesystems (NFS, SMB, FUSE all weaken it). The 4 KB `cause.message` cap keeps run-level event lines comfortably under PIPE_BUF — single-writer is the contract; multi-writer "won't tear" only on local filesystems and only because event lines are small. Two pipelines simultaneously would race on the per-stage manifest and the SQLite DB anyway.

The rule: **`start_run` refuses to start if `<output_dir>/.bristlenose/run.pid` exists AND its `(pid, start_time)` pair matches a live process** — exits with "another run is already in progress for this project (started <time>, run_id <X>)". The `start_time` comparison defeats PID reuse on busy machines (macOS PIDs cycle through ~99,999 — a stale PID file from a long-dead run can collide with an unrelated live process; without the start-time check, the new run would refuse erroneously). If the PID is dead OR its start_time doesn't match → recovery rule kicks in (synthesised `run_failed`, then proceed). `--force` flag for explicit override is a future affordance, doesn't break the schema.

**Honesty requirement.** Cancelled and failed runs are distinguishable when both writers ran cleanly. The flag-and-flush cancellation path makes `outcome: cancelled` reliable for SIGINT/SIGTERM. For SIGKILL of the CLI process or kill-9 of the parent app, no handler runs — the recovery rule kicks in and the user sees `.failed(cause.category: unknown)`, the honest fallback. No fictional `parent_died` category that isn't actually detected.

**Backward compatibility.** Existing manifests (no event log on disk):
- CLI: continues to use per-stage `status` for resume logic. The event log is a new file; its absence means "no runs yet recorded" — same effect as `.idle`.
- Desktop: `parseManifest` falls back to the current strict "render present + complete" check (commit `9ca4461`) when no event log exists. Same behaviour as today. Once the Python side writes events, desktop reads them preferentially.
- Manifest schema version stays at 1; the manifest never gained run-level fields. The event log has its own `schema_version` per line.

**SessionRecord cost extension.** Phase 1f also extends the existing `SessionRecord` (Phase 1d) with optional `cost_usd_estimate: float | None`, `price_table_version: str | None`, `input_tokens: int | None`, `output_tokens: int | None`. Today `SessionRecord` carries only `status / session_id / completed_at / provider / model` — no cost. Without this extension, lifetime project cost (which sums across all sessions plus non-session-attributable run costs) cannot be computed. Additive change — old records load with `None` via Pydantic defaults. Field naming matches the run-level event field exactly so there's no cost-as-authoritative-vs-estimate split between the two stores. **Phase 5 lifetime aggregation rule: read `SessionRecord.cost_usd_estimate` per session for lifetime totals; the run-level `cost_usd_estimate` covers only sessions processed in *this* run, to avoid double-counting.**

**Forward compatibility — Phase 4a (full event log), Phase 4d (human-edit merge), Phase 5 (incremental sessions).**

- **Phase 4a** extends the event log with stage-level events (`stage_started`, `session_complete`, etc.) and human-edit events (`quote_hidden`, `theme_renamed`, etc.). The four run-level event types stay as-is. The envelope (`schema_version`, `ts`, `event`, `run_id`) is the contract — new event types extend it additively.
- **Phase 4d** (3-way merge for human edits) emits a `run_completed` with `kind: "run"` and a future-additive `merge_summary` field. The structured `cause` object can also gain a `merge_conflict` category if a re-run fails because human edits and fresh LLM output can't be reconciled. Open-ended object structure leaves room.
- **Phase 5** (incremental sessions) emits a `run_completed` whose `cost_usd_estimate` reflects only the new/changed sessions in *this* run. Lifetime project cost is derived at read time from `SessionRecord.cost_usd_estimate` aggregated across all sessions, plus any non-session-attributable run-level costs (clustering, theming) — *not* by summing `run_completed.cost_usd_estimate` events, which would double-count sessions kept across re-runs. No third stored aggregate; no zombie field.

**Cost as a judgement input.** Even if the alpha UI doesn't surface cost prominently, capturing it now unlocks future judgement calls:

- "Resume vs re-analyse" — "Resume cancelled run (~30s, $0.12)" vs "Re-analyse from scratch (~12 min, $1.83)". The user picks based on the gap.
- "What did this failure cost me?" — surface "Cost incurred before failure: $0.46" alongside the structured `cause`.
- "Should I rescue these transcripts?" — if a `cancelled` `transcribe-only` run produced 8 of 10 transcripts, the dollar value of that work changes the calculus on whether to delete-and-retry vs continue.
- "How much have I spent on this project this month?" — derive from `SessionRecord.cost_usd_estimate` across all sessions (manifest data) rather than summing `run_completed` events (which double-counts sessions reused across re-runs). The event log is still plain text and grep-friendly for forensic queries — `grep run_completed pipeline-events.jsonl | jq '{run_id, cost_usd_estimate, ended_at}'` shows per-run cost history.

The cost fields also let the perf-baselining work in `docs/design-perf-fossda-baseline.md` step 6 cross-reference per-run cost against per-call latency.

### Open decisions (within this design)

Resolved in **round 1** (2026-04-25 morning):

- **Two stores or one?** → **One.** Single source of truth in `pipeline-events.jsonl`. Manifest stays focused on per-stage resume.
- **`cause` flat enum or structured?** → **Structured.** Pydantic `BaseModel` with explicit `Optional` defaults; OpenTelemetry / Sentry-aligned field names.
- **Heartbeat or PID-liveness?** → **PID-liveness** with `(pid, start_time)` pair to defeat PID reuse. No heartbeat field, no daemon thread.
- **Cost as authoritative or estimate?** → **Estimate.** Fields are `cost_usd_estimate` + `price_table_version`; UI renders as "~$X (est.)". Token counts stay authoritative.
- **Resume / Retry vs single "Continue" verb?** → **Three-verb split.** Resume (after cancellation), Retry (after failure), Re-analyse… (destructive). Mechanically identical between Resume and Retry; labels honestly signal cause of interruption. Validates against Time Machine + git rebase precedent.

Resolved in **round 2** (2026-04-25 afternoon, after the post-pivot review fan-out):

- **`stages_complete` snapshot vs derive?** → **Derive.** Manifest is the single source of truth for stage state. The system refuses concurrent runs, so the manifest is consistent with the events-log read. Snapshotting added duplication risk for no real win.
- **Should `kind: render` exist?** → **No.** Render is a read-only re-emission, doesn't change project state, and the static-render path is being actively phased out. `KindEnum` is `run | analyze | transcribe-only`. Render runs do not write the events log.
- **`cause.retryable` field?** → **Drop.** Derivable from `category` via `is_retryable(category)` — Python source, Swift mirrors. Storing it duplicates the rule.
- **Cause-category names across boundary?** → **Match shipped Swift exactly.** Python and Swift both use `auth | network | quota | disk | whisper | unknown` plus the new `user_signal | api_request | api_server | missing_dep`. Pre-pivot proposal to rename (`api_auth`, `api_quota`, etc.) was based on a stale Swift snapshot — rejected.
- **Process diagnostics envelope?** → **Add.** `process: {pid, start_time, hostname, user, bristlenose_version, python_version, os}` on `run_started` only. Sentry / OTel / Dagster precedent. The `(pid, start_time)` pair is also the canonical PID-liveness record.
- **PID-file ownership: Swift, Python, or both?** → **Python writes its own.** A Python-side PID file at `<output_dir>/.bristlenose/run.pid` containing `(pid, start_time)` is the source of truth for "is a Python pipeline alive for this project?". Swift's existing `<App Support>/Bristlenose/pids/<UUID>.pid` (`PipelineRunner.writePIDFile`) stays as-is for orphan-attach (Swift knowing which subprocess belongs to it). The two files solve different problems and can both exist; the events-log refuse-if-running check reads the Python-side one. Pure-CLI users (no desktop) get correct behaviour because the Python file is always written.

Still open (deferred):

- **Events log file rotation strategy.** Today: never rotate. Threshold to revisit: ~10 MB or ~10k events (Phase 4a's stage-level + human-edit events will push file sizes up). Document the rotation policy explicitly *before* it's needed so a future contributor doesn't add it ad hoc and break Phase 4d's history-replay contract. Default position when revisited: rotate to `pipeline-events.jsonl.1` at 10 MB; tail-reader checks both.
- **`fsync` cadence under Phase 4a load.** Today: `fsync` per event. Fine for 4 run-level events. Phase 4a (stage-level + per-LLM-call events) on a 12-min run with 200+ events accrues 200ms-2s of fsync overhead on macOS APFS. When Phase 4a lands, decide: (a) only fsync on terminus events, (b) batch fsync at safe break points, (c) accept the cost. Default position: (b).
- **Durability guarantee.** macOS `os.fsync()` is *not* `F_FULLFSYNC` — survives process crashes, not power loss. Documented contract: Phase 1f / 4a-pre survive process crashes only. Power-loss durability is not promised. Revisit if a user reports an unrecoverable crash on a UPS-less laptop.

### Desktop consumer mapping

> **Status:** **shipped** 2026-04-26. Implemented as [`EventLogReader.deriveState`](desktop/Bristlenose/Bristlenose/EventLogReader.swift:103); [`PipelineRunner.parseManifest`](desktop/Bristlenose/Bristlenose/PipelineRunner.swift:676) consults it first, falling back to the strict render-stage-complete check only when no events log exists (back-compat for projects predating this work). The `.partial(kind, stagesComplete)` and `.stopped(stagesComplete)` cases are state-layer only — UI verb wiring (Resume / Retry / Re-analyse…) is deferred to a separate desktop UX iteration tracked in [`docs/private/desktop-ux-iteration.md`](docs/private/desktop-ux-iteration.md) §3.

How the desktop `PipelineState` enum maps to event-log tail × PID-file liveness:

| Event log tail | Python PID file | Desktop state | Verbs offered |
|---|---|---|---|
| _missing or empty_ | — | `.idle` | Analyse |
| `run_started` (no terminus) | `(pid, start_time)` matches a live process | `.running` (runner-owned) | Stop |
| `run_started` (no terminus) | PID dead OR PID alive but `start_time` mismatch | display-synthesised `.failed(cause.category: unknown)` * | Retry / Re-analyse… |
| `run_completed` (kind=run/analyze) | — | `.ready(ended_at)` | Re-analyse… |
| `run_completed` (kind=transcribe-only) | — | `.partial(kind, stagesCompleteFromManifest)` | Continue (analyse) / Re-analyse… |
| `run_cancelled` (cause.category=user_signal) | — | `.stopped(stagesCompleteFromManifest)` | Resume / Re-analyse… |
| `run_failed` (cause.category=auth) | — | `.failed(cause)` | Fix credentials → Retry / Re-analyse… |
| `run_failed` (cause.category=quota) | — | `.failed(cause)` | Retry / Switch provider → Re-analyse… |
| `run_failed` (cause.category=network/whisper/missing_dep/disk/api_request/api_server/unknown) | — | `.failed(cause)` | Retry / Re-analyse… |

\* The Swift side **does not write** the events log even on a stranded `run_started`. It synthesises a display-only `.failed` state for the user. The on-disk truth gets written by Python on the next `start_run` (which appends the synthesised `run_failed` event before starting the new run). Until then, the events log still ends in `run_started` — the desktop's display is a derivation, not a write.

`stagesCompleteFromManifest` is read at display time from the manifest's per-stage dict (`status: complete`), not stored in the events log. Manifest is the single source of truth for stage state; events log is the source of truth for run-level outcome.

**Precedence with `applyScanResult`.** Today's `applyScanResult` ([PipelineRunner.swift:531](desktop/Bristlenose/Bristlenose/PipelineRunner.swift:531)) refuses to overwrite `.running` / `.queued` / `.failed` from a passive scan. The new `tailEventLog` reader produces `.running` only when the events log says `run_started` *and* the PID is live — exactly the case where the runner is also tracking the run live. So the runner-owned `.running` and the events-log-derived `.running` agree, and the existing `applyScanResult` guard remains correct: passive scans still don't clobber active runs, but the events log gives them an honest read of recently-finished runs they couldn't classify before.

**Cause-enum naming across the boundary.** Same case names on both sides — Python `CauseCategoryEnum` matches the shipped Swift `PipelineFailureCategory` exactly (existing: `auth | network | quota | disk | whisper | unknown`). Phase 1f extends both sides additively with `user_signal | api_request | api_server | missing_dep`. No existing case is renamed. The existing Swift `.failed(summary, category)` constructor stays — only the enum gains new cases. Phase 1f Swift change also adds `.partial(kind, stagesComplete)` and `.stopped(stagesComplete)` cases per #4 alpha-blocker, with `stagesComplete` derived from the manifest at display time (not stored).

The matrix replaces #4 alpha-blocker's pure state-enum split (`.idle` vs `.stopped`) with a state-plus-payload model that carries enough history to drive honest copy. Three-verb UX (Resume / Retry / Re-analyse…) resolved in §"Open decisions" — Resume and Retry remain mechanically identical (both call `start()` with cache); the labels honestly signal cause of interruption.

**Mid-run provider switch.** Scenario A in this doc (line ~463) describes a user switching LLM providers mid-run after credit exhaustion; per-session caching means already-completed sessions keep their original provider/model, new sessions use the new one. The matrix's "Retry / Switch provider" verb on `failed (cause.category=quota)` is the front door for that scenario — the underlying machinery (per-session provider preservation) is unchanged.

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

#### 1f. Run outcomes and intent (events log)

**Status: shipped 2026-04-26 on `port-v01-ingestion`** in 4 slices + a review-fix pass — see round-3 changelog at the top of this doc for the per-slice commit refs and the post-spec adjustments made in review.

**What it is**: An append-only `pipeline-events.jsonl` file recording how each run ended (kind / outcome / structured cause / token counts / estimated cost). Plus a `SessionRecord` extension for per-session token + estimated cost. Replaces the inference path the Swift desktop previously used (which mis-classified interrupted runs as `.ready`). The event log is the single source of truth for run-level state; the manifest stays focused on per-stage resume. Schema and lifecycle defined in §"Run outcomes and intent" above; envelope and event-line shape in §"Phase 4a-pre" below.

**What it touches** (post-2026-04-25 pivot — single-source event log, no manifest changes for run-level state):
- New `bristlenose/events.py` — Pydantic models for the four terminus events (`RunStartedEvent`, `RunCompletedEvent`, `RunCancelledEvent`, `RunFailedEvent`) sharing a base envelope; `KindEnum`, `OutcomeEnum`, `CauseCategoryEnum` as `str, Enum` (same convention as `StageStatus` in `manifest.py:23`). `KindEnum` is `run | analyze | transcribe-only` (no `render`). `CauseCategoryEnum` matches the shipped Swift `PipelineFailureCategory` plus new entries: `auth | network | quota | disk | whisper | unknown | user_signal | api_request | api_server | missing_dep`. `Cause` model: `BaseModel` with `category` required and all other fields `Optional[X] = None` (`code`, `message`, `provider`, `stage`, `session_id`, `exit_code`, `signal`, `signal_name`); writer rule enforces `message` populated for any non-`user_signal` category; `message` capped at 4 KB. `is_retryable(category) -> bool` lives here as the single source of the retryable rule. `Process` model captures `(pid, start_time, hostname, user, bristlenose_version, python_version, os)`. Single append-only writer (`append_event()`) using `O_APPEND` + `fsync` + line-framed JSON. Reader (`tail_run_state(events_path, manifest) -> RunState`) returns the derived current state from the tail of the log, with stages-complete sourced from the manifest.
- `bristlenose/manifest.py` — extend `SessionRecord` with optional `cost_usd_estimate`, `price_table_version`, `input_tokens`, `output_tokens` (additive — old records load with `None` via Pydantic defaults). `PipelineManifest` is **not** otherwise modified.
- `bristlenose/run_lifecycle.py` — `run_lifecycle(output_dir, kind)` context manager wraps each CLI command body. On entry: writes Python-side PID file `<output_dir>/.bristlenose/run.pid` (mode 0o600, `O_NOFOLLOW`) with `(pid, start_time, run_id)`; appends `RunStartedEvent` to `pipeline-events.jsonl` (also 0o600, `O_NOFOLLOW`); installs SIGINT/SIGTERM handler that records the signal number and re-raises `KeyboardInterrupt`. On clean exit: appends `RunCompletedEvent` and removes PID file via `try/finally`. On `KeyboardInterrupt`: appends `RunCancelledEvent` with `Cause(category=user_signal, signal=..., signal_name=...)`. On other exceptions: `categorise_exception(exc)` produces a `Cause` (word-boundary regex on the message; `ImportError`/`ModuleNotFoundError` → `MISSING_DEP`; `OSError(errno=ENOSPC)` → `DISK`; everything else falls through to `UNKNOWN`) and appends `RunFailedEvent`. Stale-running recovery: `_reconcile_stranded_run` checks the events log tail; if it's a `run_started` with no terminus, appends a synthesised `RunFailedEvent(cause.category=unknown, cause.message="Analysis stopped unexpectedly.")` before starting the new run. Concurrent-run refusal: `ConcurrentRunError` raised when an existing PID file matches a live `(pid, start_time)` pair (verified via `kill(pid, 0)` + `/bin/ps -o lstart=`); cli.py converts to `typer.Exit(1)` with a clear message. The PID file is **always** removed via the context manager's `try/finally`; the spec's `atexit` hook was removed in round-3 review (unbounded list growth on re-entry, redundant with `finally`).
- New `bristlenose/cost.py` (or extend `timing.py`) — accumulate per-run token counts from per-session `SessionRecord` updates and non-session LLM calls (clustering, theming). The price-table is a JSON file shipped alongside the package, with a `version` (ISO date) and a `currency` field (USD today; future-proofs against EUR / GBP price leaks). `cost_usd_estimate` is derived from raw tokens × table; `None` when no LLM calls were made.
- `bristlenose/cli.py` — wire the entry-point hooks for each command. Pre-start check: read `<output_dir>/.bristlenose/run.pid` if present; if `(pid, start_time)` matches a live process → refuse with "another run in progress". If PID dead OR `start_time` mismatch → recovery path (synthesised `run_failed` for the stranded prior, then proceed).
- `desktop/Bristlenose/Bristlenose/PipelineRunner.swift` — replace `parseManifest`'s "render present + complete" inference with `tailEventLog(...)` reading `pipeline-events.jsonl`. Falls back to the existing strict check (commit `9ca4461`) for projects with no event log file (backward compat). Add `.partial(kind, stagesComplete)` and `.stopped(stagesComplete)` cases to `PipelineState`. `stagesComplete` is read from the manifest at display time (not stored in the events log). **Extend** `PipelineFailureCategory` with new cases (`userSignal`, `apiRequest`, `apiServer`, `missingDep`) — no rename of existing cases (`auth | network | quota | disk | whisper | unknown` keep their names; pre-pivot rename proposal rejected based on stale-snapshot review finding). Stranded-`run_started` rule: read `<output_dir>/.bristlenose/run.pid`; if missing or `(pid, start_time)` doesn't match a live process → display as `.failed(cause.category: unknown)` without writing the event log from Swift. PID-liveness check uses both `kill(pid, 0)` and process creation time (Foundation `Process` doesn't expose start_time directly — use `proc_pidinfo` via the existing pattern in `aliveOwnedRunPID` extended to capture `pbi_start_tvsec`, OR use `psutil`-equivalent helper).
- UI cost display — anywhere `cost_usd_estimate` reaches user-facing text it must be rendered as "~$X.XX (est.)" or similar; never bare "$X.XX". Add a helper / locale string convention so this is consistent.

**Risk**: Low for the events file (new file, append-only, no schema break to existing manifest). Low for the signal-handler change once flag-and-flush is used (production-standard pattern). Low for backward compat (event log absence falls through to existing inference). Low-medium for the PID-file `(pid, start_time)` discipline (well-trodden Unix daemon pattern; postmaster, OpenSSH, systemd). Medium for cost estimation correctness (price-table maintenance, provider edge cases like batch tiers, cached prompts). Deployment order is Python-first — Swift reads what Python writes.

**Durability contract.** `os.fsync()` after each write survives **process crashes, not power loss** — macOS `os.fsync()` is not `F_FULLFSYNC`, so it returns when data hits the disk buffer, not the platter. Linux `fsync()` is stronger by default. Phase 1f / 4a-pre commit to crash-survival only. UPS-less laptop power loss can corrupt the trailing event line; the JSONL recovery rule (discard malformed trailing line) handles this gracefully — at worst, one event is lost, and the next `start_run` recovery synthesises a `run_failed` for the stranded run anyway. Power-loss durability for the event log is not a Phase 1f goal.

**Tests needed**:
- Round-trip Pydantic serialisation of each event type with each `Cause.category` value.
- Round-trip `SessionRecord` with the new optional cost fields (None and populated).
- Append-only events writer: write 100 events, read back, assert order preserved and all parse cleanly.
- **Concurrent `O_APPEND` writers** (subprocess test): spawn 2 subprocesses each writing 100 events, assert all 200 lines parse and none are torn. Run on macOS arm64 (APFS) and Linux ext4 (CI).
- **Oversized `cause.message`**: write an event with a 64 KB message, assert it's truncated to 4 KB at the writer (not silently lost in Swift's `readLogTail` window).
- **NUL-padded trailing line**: simulate power-loss-style trailing zeros at end of file, assert reader discards malformed trailing and recovers cleanly.
- Crash-safety: write a partial line (truncate mid-write), assert reader discards trailing malformed line and continues.
- Tail reader: assert correct `RunState` derivation for each tail-event scenario (empty log; only `run_started`; `run_started` then `run_completed`; orphaned `run_started` after a previous run's `run_completed`; etc.).
- Lifecycle (subprocess test): spawn a child running a synthetic long stage, observe `run_started` in the log, observe terminus matches the actual exit (success → `run_completed`; raise → `run_failed`).
- Signal handling — **subprocess test, not unit test**: spawn a child running a long stage, send SIGINT to the child, read the events log, assert the tail is `run_cancelled` with `cause.category: user_signal`, `cause.signal: 2`, `cause.signal_name: "SIGINT"`. Pytest's own SIGINT handler intercepts in-process tests, so this must cross the process boundary.
- **Stale PID + reused PID** (subprocess test): write a PID file with `(pid, start_time)` where `pid` belongs to a live unrelated process but `start_time` doesn't match. Run `start_run`, assert recovery doesn't refuse erroneously and the unrelated process is left alone.
- Stale-running recovery: write an events log ending with `run_started` and no PID file (or PID file pointing to a dead process). Run `start_run`, assert a synthesised `run_failed` (`cause.category: unknown`, `cause.message: "Analysis stopped unexpectedly."`) was appended before the new `run_started`. Implemented + tested: see [`tests/test_run_lifecycle.py:test_stranded_run_started_synthesises_failed_on_next_start`](tests/test_run_lifecycle.py).
- Concurrency (subprocess test): spawn two CLI processes against the same project simultaneously, assert the second exits with "another run in progress".
- **TOCTOU window**: simulate two CLI processes both reading the empty PID-file state and racing to write — accept that one wins, assert the loser exits cleanly (gets the "another run in progress" path on its second check) without corrupting the events log.
- Backward compat: project with no events log file → `tail_run_state` returns "no run yet"; CLI resume logic continues to work from per-stage manifest status as today.
- **Cost rendering**: any helper that surfaces `cost_usd_estimate` to UI must produce "~$X.XX (est.)"; assert no bare-dollar paths exist (lint or unit test).
- Swift: fixture-driven `tailEventLog` tests for each `event` × `cause.category` combination map to the right `PipelineState` case. Stale-running test (events log ends in `run_started`, no PID file → `.failed(cause.category: unknown)`). PID-reuse test (events log ends in `run_started`, PID file exists, PID alive but `start_time` mismatches → `.failed`).
- **Very-large events log Swift fixture**: synthesise an events log with 1000+ stage-level events from Phase 4a (simulated) and a `run_completed` at the tail; assert `tailEventLog` reads from end backward bounded, doesn't load the whole file.

---

### Phase 4a-pre: Run-level event log (single source of truth for run outcomes)

**Status: shipped 2026-04-26 on `port-v01-ingestion`.** Subset of Phase 4a's full event log brought forward because the desktop needed run-level outcome data now, AND (per 2026-04-25 single-source pivot) this file is the canonical home for that data — it's not duplicated to the manifest. Phase 4a's stage-level + human-edit events still pending; the envelope shipped here (`schema_version`, `ts`, `event`, `run_id`, `kind`, `started_at`) is the contract Phase 4a extends additively.

**What it is**: An append-only `pipeline-events.jsonl` file in `.bristlenose/` that records the four run-level events from §"Run outcomes and intent": `run_started`, `run_completed`, `run_cancelled`, `run_failed`. Same file format as the eventual full event log (Phase 4a) — Phase 4a extends it additively with stage-level and human-edit events, never breaks the envelope. There is **no heartbeat** — liveness is derived from the existing PID file, not from a heartbeat field.

```jsonl
{"schema_version":1,"ts":"2026-04-25T09:00:00Z","event":"run_started","run_id":"01HZX4N9MXQ5T7B3YJZP2K8FCV","kind":"run"}
{"schema_version":1,"ts":"2026-04-25T09:12:34Z","event":"run_cancelled","run_id":"01HZX4N9MXQ5T7B3YJZP2K8FCV","kind":"run","started_at":"2026-04-25T09:00:00Z","ended_at":"2026-04-25T09:12:34Z","outcome":"cancelled","cause":{"category":"user_signal","signal":2,"signal_name":"SIGINT","exit_code":null,"code":null,"message":"SIGINT received","provider":null,"stage":"transcribe","session_id":"s4"},"input_tokens":12420,"output_tokens":0,"cost_usd_estimate":0.46,"price_table_version":"2026-04-25"}
```

**Envelope contract.** Every event line carries `schema_version` + `ts` + `event` + `run_id`. Terminus events (`run_completed`, `run_cancelled`, `run_failed`) additionally carry the full run-level fields enumerated in §"Run outcomes and intent" — so the event log alone is sufficient to reconstruct any past run's outcome. This is the contract Phase 4d (3-way merge) depends on for history replay; full event log (Phase 4a) extends the envelope additively with stage-level and human-edit events, never breaks it.

**Why this is the canonical home, not a parallel store**: run-level outcome is *terminus-bound history* — once a run ends, the fact of how it ended is immutable, which is the natural shape for an append-only log. The manifest's job is "current mutable state for resume" (which stages are cached); the events log's job is "immutable history of what happened". Two files, two non-overlapping concerns. See "Open decisions" in §"Run outcomes and intent" for the resolved trade-off.

**What it touches**: `bristlenose/events.py` (new) — append-only writer + tail reader for the four run-level event types. Called from the lifecycle hooks in `pipeline.py` / `cli.py`. Swift consumer reads it via `tailEventLog` to derive `PipelineState`; falls back to the existing per-stage manifest inference when no events log exists.

**JSONL crash safety.** Append-only + line-framed: `write` + `fsync` one full line at a time; on read (Phase 4a), discard the trailing line if it doesn't end in `\n` or fails to parse. Standard JSONL recipe.

**Risk**: None. Append-only file, no readers in the alpha. If corrupted, nothing breaks.

**Decision (2026-04-25): single source of truth.** The Dagster/Prefect dual-store pattern (mutable run record on the manifest + append-only event log) was rejected here. For an indie CLI tool with one consumer, it's strictly cleaner to put **all** run-level outcome data in the append-only log and derive "current state" by tail-reading. No projection to keep in sync, no drift risk, one writer. The manifest stays focused on its existing per-stage-resume job (mutable current state for that — naturally a JSON object). Different tools for different jobs, no overlap.

**Forward path to Phase 4a**: extend `events.py` with stage-level and human-edit event types when Phase 4 lands. The terminus events stay as-is.

---

### Phase 2: Data integrity (hashing and validation)

**Goal**: Know whether cached data is trustworthy. Detect corruption, detect input changes, invalidate stale downstream stages.

Phase 1 trusts the manifest blindly — "it says complete, so it must be fine." Phase 2 adds verification.

#### ~~2a. Content hashes on stage outputs~~ ✓ Done

**What it is**: When writing a stage output (JSON, transcript text), compute its SHA-256 hash and store it in the manifest alongside the file path.

**Implementation**: `hash_bytes()` in `bristlenose/hashing.py` (standalone module — will grow in Phase 2c). `content_hash: str | None` field on both `StageRecord` and `SessionRecord` in `manifest.py`. Hashes computed at the call site in `pipeline.py` (read file back and hash) rather than changing `write_intermediate_json()` return type — simpler, no interface changes. Per-session files (speaker-info) hashed individually; merged files (topic_boundaries, extracted_quotes) hashed as the whole file. Cluster+group combines both output files into one hash. 13 tests (5 hashing, 8 manifest).

**Risk**: None. Just adds a field. Doesn't change behavior.

#### 2b. Verify hashes on load

**What it is**: When loading cached data (the skip logic from 1c), re-hash the file on disk and compare to the manifest. If they don't match, the file is corrupt or was tampered with — treat the stage as incomplete and re-run it.

**How it works**: Before loading `extracted_quotes.json`, compute `sha256(file_contents)` and compare to the hash in the manifest. Mismatch → log a warning, mark stage as stale, re-run.

**What it touches**: The loading logic in `pipeline.py` (add hash check before using cached data).

**Risk**: Low. The only behavioral change is: corrupted files trigger re-runs instead of producing garbled output.

#### ~~2c. Input change detection~~ ✓ Done

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

1. **Size+mtime fast path**: if `(file_size, mtime)` match the manifest record, skip the full hash. Only compute SHA-256 when size or mtime differ. This is the rsync/Make optimisation (Tridgell & Mackerras, 1996) — not cryptographically reliable (mtime can be spoofed) but sufficient for a local-first tool where the user is not adversarial. **Cross-machine copies**: copying a project folder (rsync, zip, Finder copy) may change mtimes, causing all stages to re-run on the new machine. This is expected and safe — the pipeline re-verifies everything and caches the new mtimes. **Network filesystems**: `stat()` on NFS/SMB mounts can block for 100ms+ per file if the mount is unresponsive. For local files this is ~1μs. If network-mounted interview folders become a real use case, wrap in `asyncio.to_thread()`.
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
{"ts":"...","event":"session_complete","stage":"quote_extraction","session":"s3","quotes":12,"cost_usd_estimate":0.18,"price_table_version":"2026-02-20"}
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
2. Compare against manifest's `stages.s01_ingest.sessions_discovered`
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
7. ~~Ship 2c (input change detection — one session, 2 hours)~~ ✓ Done
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

## Progress Bar Dead Ends

These are documented to prevent re-exploration of dead ends. Moved here from `bristlenose/stages/CLAUDE.md`.

- **mlx-whisper `verbose` parameter is counterintuitive**: `verbose=False` ENABLES tqdm progress bars (`disable=verbose is not False` → `disable=False`). `verbose=None` DISABLES them (`disable=True`). `verbose=True` also disables the bar but enables text output. We use `verbose=None`
- **`TQDM_DISABLE` env var must be set before any tqdm import**: setting it inside `Pipeline.__init__()` is too late — moved to module level in `pipeline.py`
- **`HF_HUB_DISABLE_PROGRESS_BARS` env var is read at `huggingface_hub` import time** (in `constants.py`): if `huggingface_hub` was already imported before `pipeline.py` loads, the env var has no effect. Belt-and-suspenders: also call `disable_progress_bars()` programmatically in `_init_mlx_backend()` after `import mlx_whisper`
- **tqdm progress bars don't overwrite inside Rich `console.status()`**: Rich's spinner takes control of the terminal cursor. tqdm's `\r` carriage return doesn't work properly, causing bars to scroll line-by-line instead of overwriting in place. This makes tqdm bars useless inside a Rich status context — they produce dozens of non-overwriting lines
- **`TQDM_NCOLS=80` doesn't help**: even with width capped, the non-overwriting bars still produce one line per update. The root issue is tqdm + Rich terminal conflict, not width
- **Conclusion**: suppress all tqdm/HF bars entirely; let the Rich status spinner handle progress indication. The per-stage timing on the checkmark line provides sufficient feedback. Don't try to re-enable mlx-whisper's tqdm bar — it will scroll
