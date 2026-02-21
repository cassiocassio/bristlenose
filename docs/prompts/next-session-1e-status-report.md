# Next session prompt: Phase 1e — Status report and resume visibility

## Context

Phases 1a–1d-ext are done. The pipeline now:
- Writes a manifest after every stage (1a/1b)
- Skips completed stages on resume, loading from intermediate JSON (1c)
- Tracks per-session completion for topic segmentation and quote extraction (1d)
- Caches transcription and speaker identification per-session (1d-ext)

But the user has **no visibility** into what's cached. When they re-run a pipeline, they see `(cached)` next to stages but don't get an upfront summary of what state their project is in. They also can't inspect the manifest without reading JSON by hand.

Phase 1e adds a status report — both as a standalone command and as a pre-run summary.

## What to build

### 1. `bristlenose status <folder>` command

A read-only CLI command that reads the manifest and prints project state.

**Output format** (from the design doc):
```
Project: usability-study-feb-2026
Pipeline version: 0.10.2
Last run: 20 Feb 2026 14:32

Stages:
  ✓ Ingest          10 sessions
  ✓ Transcribe      10 transcripts
  ✓ Speakers        10 sessions identified
  ✓ Topics          87 boundaries
  ⚠ Quotes          42 quotes (7/10 sessions — 3 incomplete)
  ✗ Clusters        not generated
  ✗ Themes          not generated
  ✗ Report          not generated

Cost so far: $4.20
```

**Design decisions**:
- `✓` = COMPLETE, `⚠` = PARTIAL/RUNNING (has some data), `✗` = PENDING/no data
- Show session counts where available (from SessionRecord entries)
- Show cost from `total_cost_usd` in manifest (currently always 0 — we can populate this later or skip for now)
- If no manifest exists, print "No pipeline data found. Run `bristlenose run <folder>` to start."
- Use the same `Console(width=min(80, Console().width))` pattern as pipeline output

**Per-session detail** (optional, with `-v`):
```
  ⚠ Quotes          42 quotes (7/10 sessions)
      ✓ s1  (claude-sonnet-4-20250514)
      ✓ s2  (claude-sonnet-4-20250514)
      ...
      ✗ s8
      ✗ s9
      ✗ s10
```

### 2. Pre-run summary in `bristlenose run`

Before the pipeline starts, if a manifest exists, print a brief status summary:

```
$ bristlenose run interviews/

Resuming: 7/10 sessions have quotes, 3 remaining.

 ✓ Ingested 10 sessions                    (cached)
 ✓ Transcribed 10 sessions                 (cached)
 ...
```

This is lightweight — just 1-2 lines before the pipeline output, not a full status report. The information comes from scanning the manifest's stage records and session records.

### 3. Validate intermediate files exist

The status command should validate that intermediate JSON files exist for stages marked complete. If the manifest says "quotes complete" but `extracted_quotes.json` is missing (someone deleted it), report a warning:

```
  ⚠ Quotes          marked complete but file missing — will re-extract on next run
```

This is the precursor to Phase 2's hash verification — for now, just file existence.

## Implementation approach

### New file: `bristlenose/status.py`

Pure logic — reads manifest, checks file existence, returns a data structure. No printing (that's the CLI's job).

```python
@dataclass
class StageStatusInfo:
    """Status of one pipeline stage for display."""
    name: str                          # "Ingest", "Transcribe", etc.
    status: StageStatus                # from manifest
    detail: str                        # "10 sessions", "87 boundaries", etc.
    session_total: int | None = None   # for per-session stages
    session_complete: int | None = None
    file_exists: bool = True           # intermediate file validated
    provider: str | None = None        # most recent provider used

@dataclass
class ProjectStatus:
    """Full project status for display."""
    project_name: str
    pipeline_version: str
    last_run: str                      # ISO timestamp from manifest.updated_at
    stages: list[StageStatusInfo]
    total_cost_usd: float

def get_project_status(output_dir: Path) -> ProjectStatus | None:
    """Read manifest and validate file existence. Returns None if no manifest."""
```

### Changes to `bristlenose/cli.py`

- Add `status` subcommand that calls `get_project_status()` and prints it
- Add pre-run summary in the `run` command (after loading manifest, before pipeline starts)

### Stage detail logic

For each stage, derive the detail string from available information:

| Stage | Detail source |
|-------|--------------|
| Ingest | Count from manifest (or "N sessions" from session records) |
| Transcribe | Count session records in manifest |
| Speakers | Count session records |
| Topics | Load `topic_boundaries.json`, count boundaries (or just "complete") |
| Quotes | Load `extracted_quotes.json`, count quotes + session records |
| Clusters | Load `screen_clusters.json`, count clusters |
| Themes | Load `theme_groups.json`, count themes |
| Report | Check if report HTML exists |

**Lightweight loading**: For counts, we can read just the JSON array length without deserializing all objects. Or just show "complete" without counts for stages where counting requires full deserialization.

## Files to change

| File | Change |
|------|--------|
| `bristlenose/status.py` | New file — `get_project_status()` logic |
| `bristlenose/cli.py` | Add `status` subcommand, add pre-run summary |
| `tests/test_status.py` | New file — test status report with various manifest states |

## Key constraints

- The `status` command must work offline — no LLM calls, no network, just manifest + file checks
- Must handle legacy projects without a manifest gracefully
- Must handle partially complete manifests (crashed mid-run)
- The `output_dir` for status is the *output* directory (contains `.bristlenose/`), not the input directory. But the CLI convention is `bristlenose status <input_dir>` and the output dir is `<input_dir>/bristlenose-output/`. Resolve this the same way `render` does — check for output dir inside input dir

## Open questions (resolve before implementing)

1. **Should `status` accept the input dir or output dir?** The `run` command accepts input dir. Consistency says input dir. But what if `--output` was used? Maybe accept either and auto-detect.
2. **How much detail to show without `-v`?** The design doc shows session counts but no per-session breakdown. Is that the right level?
3. **Should the pre-run summary be opt-out?** It's one line — probably always show it when resuming.
4. **Cost tracking**: `total_cost_usd` in the manifest is currently always 0. Should we populate it from `LLMUsageTracker` as part of this work, or defer?

## Risk

Low. This is purely read-only — no pipeline behavior changes. The main risk is getting the output formatting right and handling edge cases (no manifest, partial manifest, missing files).

## Size

Small-medium (~100 lines in status.py, ~40 lines in cli.py, ~80 lines in tests).
