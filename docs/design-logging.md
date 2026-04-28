---
status: current
last-trued: 2026-04-21
trued-against: HEAD@sidecar-signing on 2026-04-21
---

> **Truing status:** Current for Python-side logging (Phase 1 + Phase 2 as described). Scope note added for the Track C desktop channel (sidecar stdout → Swift redactor → unified logging) — that layer is covered in `design-keychain.md` §Secret-leak defences rather than duplicated here.

## Changelog

- _2026-04-21_ — trued up: added scoping note clarifying this doc covers Python-side logging only; corrected "We do not need a third channel" claim (Track C desktop deployment adds a third channel with its own hygiene layer); updated Tier 3 item on keychain resolution to reflect Swift-side partial-ship. Canonical home for desktop-side log hygiene is `design-keychain.md` §Secret-leak defences; this doc cross-references rather than duplicating. Anchors: `desktop/Bristlenose/Bristlenose/ServeManager.swift:409-473`, `desktop/Bristlenose/Bristlenose/ServeManager.swift:382`, `desktop/scripts/check-logging-hygiene.sh`, commits "runtime log redactor for api key shapes", "CI grep gate for Swift logging hygiene".

# Logging Architecture

> **Scope note (Apr 2026):** This doc covers **Python-side logging** — the operational log file (`.bristlenose/bristlenose.log`), CLI stderr, and the PII policy that governs both. The Track C macOS desktop deployment adds a third channel (sidecar stdout → Swift runtime redactor → unified logging); that layer and its secret-leak defences live in **`design-keychain.md` §Secret-leak defences**. Keep the two docs cross-referenced; don't duplicate the mechanism.

> **Status**: Phase 1 (infrastructure) implemented v0.10.2; Phase 2 (tier 1 instrumentation + PII hardening) implemented v0.13.5; tiers 2–3 backlogged
> **Implemented in**: v0.10.2 (infrastructure, Feb 2026), v0.13.5 (instrumentation + PII policy, Mar 2026)

## The problem

Bristlenose had a single logging knob: `-v` on the CLI, which toggled `logging.basicConfig` between `WARNING` and `DEBUG` on stderr. Everything went to the terminal and vanished when you scrolled past it. There was no persistent log file.

This meant:
- If an error happened in serve mode (no `-v` flag), you saw it flash by and it was gone
- If you needed to debug a past run, there was nothing to look at
- If a subtle issue (like the LLM returning a stringified JSON array instead of an actual list) happened intermittently, you'd never catch it unless you happened to be running verbose at the time

### Trigger

An `AutoCodeBatchResult` validation error in serve mode — the Anthropic SDK returned `assignments` as a JSON string instead of a parsed list. The `logger.error()` printed to the terminal, but the surrounding context (what the SDK actually returned, which model, which batch) was invisible because those were `logger.debug()` calls suppressed by the default `WARNING` level.

## Philosophy: who reads these logs, and when?

Bristlenose is a local-first CLI tool that processes sensitive research data. It is not a web service. This changes everything about logging philosophy.

There are exactly three scenarios:

1. **The developer, debugging a reported issue.** A researcher says "it crashed on my interviews" and sends a log file. You need enough context to reproduce without access to their machine or data.

2. **The desktop app, surfacing a diagnostic bundle.** The SwiftUI shell captures stdout for its progress display, but when something goes wrong the user needs a "Send diagnostic info" button that bundles the log file. The log must be self-contained and useful without the researcher explaining what happened.

3. **The researcher themselves, very rarely.** A technically-inclined researcher might open the log file to see why a session was skipped or why the LLM call failed. They need the message to be comprehensible without knowledge of the code.

Nobody is tailing these logs in real time. Nobody is shipping them to Grafana. Nobody is writing alert rules. This means:

- **Human-readable format wins.** The pipe-delimited format (`timestamp | LEVEL | module | message`) is correct. JSON lines would make the file unreadable for scenario 3 and harder to grep for scenario 1.
- **One log file per project.** Already the case. Each project's log lives inside its output directory. No tangling.
- **Log actionable information.** Every log line should answer "what happened and what should I do about it?" (Peter Bourgon, _Logging v. Instrumentation_, 2016). If the answer is "nothing, this is just progress," it probably shouldn't be INFO.

### Two audiences, two channels (already built)

- **Terminal (stderr)**: researcher-facing. Checkmark progress lines, warnings, errors. WARNING by default, DEBUG with `-v`. This is the "did it work?" channel.
- **Log file**: developer-facing. Full operational history. INFO by default, configurable via `BRISTLENOSE_LOG_LEVEL`. This is the "what happened?" channel.

The desktop app reads stderr for progress and reads the log file for diagnostics.

> **Amended 2026-04-21:** the original statement here — "we do not need a third channel" — is load-bearingly wrong for the Track C sandboxed-desktop deployment. That deployment adds a third channel: the Swift host reads sidecar stdout line-by-line, applies a runtime key-shape redactor (`ServeManager.swift:409-473`), then forwards to `os.Logger` unified logging with `.private` markers. A source-time CI grep gate (`desktop/scripts/check-logging-hygiene.sh`) blocks Swift source from interpolating secret-shaped values. Canonical home for these defences: `design-keychain.md` §Secret-leak defences. The two-channel model in this doc remains correct for the Python side; the third channel is layered on top by Swift.

### Research references

| Source | Key insight | Relevance |
|--------|-------------|-----------|
| Peter Bourgon, _Logging v. Instrumentation_ (2016) | Log only actionable information; use metrics for volume data | Confirms our sparse-by-default approach |
| Charity Majors, _Observability 2.0_ | "metrics, logs, and traces are just data types" — real observability = asking any question without predicting it | Argues for wide structured events — solves distributed-systems problems we don't have |
| 12-factor app, _Logs_ | Treat logs as event streams to stdout; let infrastructure handle routing | Validates our separation: app emits events, environment decides what to do |
| Stripe, _Canonical Log Lines_ | One rich event per operation, not scattered lines | Interesting but solves correlation in distributed systems; sequential log lines are already correlated by timestamp in a single-process tool |
| structlog / loguru communities | Rich context binding, processor chains, ergonomic APIs | Migration cost (34 files, 133 calls, 12 tests) not justified when grep is our analysis tool |

## Architecture

Two fully independent knobs:

| Knob | Controls | Default | Where output goes |
|------|----------|---------|-------------------|
| `-v` / `--verbose` | Terminal verbosity | `WARNING` | stderr |
| `BRISTLENOSE_LOG_LEVEL` | Log file verbosity | `INFO` | `.bristlenose/bristlenose.log` |

Changing one does not affect the other. You can have a quiet terminal with a debug-level log file, or a noisy terminal with an info-level log file, or any combination.

### Log file details

- **Location**: `<output_dir>/.bristlenose/bristlenose.log` — alongside the per-project SQLite DB
- **Rotation**: `RotatingFileHandler`, 5 MB max per file, 2 backups (`.log.1`, `.log.2`)
- **Max disk**: ~15 MB ceiling (5 MB x 3 files), then oldest is deleted
- **Compression**: None — 15 MB is negligible for a local tool
- **Format**: `2026-02-21 14:32:15 | INFO    | bristlenose.server.autocode | Job started...`
- **Encoding**: UTF-8

### Where logging is configured

| Entry point | When `setup_logging()` is called |
|-------------|----------------------------------|
| `Pipeline.run()` | After `output_dir.mkdir()`, before manifest load |
| `Pipeline.run_transcription_only()` | After `output_dir.mkdir()` |
| `Pipeline.run_analysis_only()` | After `output_dir.mkdir()` |
| `Pipeline.run_render_only()` | Before intermediate JSON load |
| `create_app()` (serve mode) | After project_dir resolution, before FastAPI init |

All paths call `setup_logging()` from `bristlenose/logging.py`. The call is idempotent — second calls clear and rebuild handlers.

### Serve mode specifics

`bristlenose serve` now accepts `-v` / `--verbose`, which controls:
1. The bristlenose log terminal handler (DEBUG vs WARNING)
2. The uvicorn log level (`info` vs `warning`)

In `--dev` mode, the verbose flag is stashed in `_BRISTLENOSE_VERBOSE` env var so uvicorn's factory reload can recover it.

## PII policy for logs

Bristlenose processes interview transcripts containing real names, job titles, opinions about employers, health conditions, and other sensitive data. Logs can leak this in subtle ways — and logs leave their trust boundary when shared as crash reports or diagnostic bundles.

### Rules

1. **Never log transcript content.** No quote text, no segment text, no LLM prompt content, no LLM response content. Only structural metadata (field types, token counts, model name). The Tier 1 response shape logging logs field *types* (`{'assignments': 'list'}`) — never field *values*.

2. **Log identifiers, not names.** Use session IDs (`s1`), speaker codes (`p1`), quote DOM IDs (`q-p1-123`), not participant names, file paths containing names, or project names. Where a file path must be logged, prefer the output path (which uses session IDs) over the input path (which may contain names).

3. **Input filenames at DEBUG, not INFO.** Per-file discovery ("Found video: `interview_jane.mp4`") is DEBUG. Aggregates ("Found 6 supported files") are INFO. The default log level should not contain filenames that could identify participants.

4. **Project name: log the slug or project ID.** The importer uses the project ID, not the raw folder name. The slug is less identifying than "Sarah Jones Q1 Interviews" but still somewhat identifying — proportional for a local tool.

5. **Log file lives inside the project output.** Anyone with access to the log file already has access to the transcripts, quotes, and names it lives alongside. The log does not create new exposure within this trust boundary. PII paranoia should be proportional: the log is not more sensitive than the data beside it.

6. **Diagnostic export must strip PII.** When the desktop app exports a "Send diagnostic info" bundle, it should redact input file paths, project names, and DEBUG-level lines. This is a desktop app concern (future Phase F), not a logging infrastructure concern.

### Current PII exposure audit

| Risk | What's logged | Status |
|------|--------------|--------|
| **Safe** | File counts, durations, stage names, token counts, model names | Majority of 133 logger calls |
| **Fixed** | Per-file input filenames at INFO | Demoted to DEBUG in v0.13.5 |
| **Low** | Full output paths (contain home directory, session IDs) | Acceptable — session IDs, not names |
| **Low** | Speaker role maps (`{'Speaker A': RESEARCHER}`) | Labels, not person names |
| **Low** | Tag names from LLM resolution | Controlled vocabulary from codebook templates |

## Two systems: operational log vs event log

The codebase has two separate logging concepts that must stay separate:

**Operational log** (`bristlenose.log`) — this document:
- Purpose: debugging, diagnostics, crash reports
- Audience: developer, desktop app diagnostic bundle, occasionally the researcher
- Format: human-readable, line-oriented, rotating
- Retention: 15 MB ceiling, auto-rotated
- Content: "LLM call: model=claude-sonnet-4 input_tokens=1234 output_tokens=567"

**Event log** (`pipeline-events.jsonl`) — Phase 4 of `design-pipeline-resilience.md`:
- Purpose: provenance, audit trail, human/LLM merge, undo
- Audience: the tool itself (replay to rebuild state)
- Format: structured JSONL, append-only, never rotated or deleted
- Retention: permanent (grows with project history)
- Content: `{"event":"quote_extracted","id":"q001","model":"claude-sonnet-4"}`

These systems must not merge. The operational log is disposable. The event log is an audit trail.

## Key files

| File | Purpose |
|------|---------|
| `bristlenose/logging.py` | `setup_logging()`, `_parse_log_level()`, rotation config, PII policy reference |
| `bristlenose/pipeline.py` | `Pipeline._configure_logging()` — deferred setup |
| `bristlenose/server/app.py` | `create_app(verbose=...)` — serve mode setup |
| `bristlenose/cli.py` | `-v` flag on `run`, `transcribe`, `analyze`, `render`, `serve` |
| `tests/test_logging.py` | 12 tests covering handlers, levels, independence, rotation |

## Existing logger coverage

27 modules use `logging.getLogger(__name__)`:

- **Pipeline**: `pipeline.py`
- **LLM**: `llm/client.py`
- **Stages**: all 12 stage files (`ingest`, `extract_audio`, `parse_subtitles`, `parse_docx`, `transcribe`, `identify_speakers`, `merge_transcript`, `pii_removal`, `topic_segmentation`, `quote_extraction`, `quote_clustering`, `thematic_grouping`)
- **Server**: `app.py`, `autocode.py`, `importer.py`, `routes/autocode.py`
- **Other**: `doctor.py`, `ollama.py`, `people.py`, `timing.py`, `render/`, `render_output.py`, `utils/audio.py`, `utils/hardware.py`

## Instrumentation tiers

### Tier 1 — LLM diagnostics + PII hardening (implemented v0.13.5)

1. **LLM response shape logging** (DEBUG) — field *types* before `model_validate()`. Five providers × 1 line. Catches double-serialization, missing fields, unexpected nulls
2. **Token usage at INFO** — model + input/output tokens after each call. Five providers × 1 line. Visible in default log level
3. **AutoCode batch progress** (INFO) — job start (framework, quotes, batches, model), per-batch completion (progress, proposals), job finish (totals, error count)
4. **Model name at INFO** — promoted from DEBUG in all five `_analyze_*` methods
5. **Input filename demotion** — per-file "Found X file: filename" moved from INFO to DEBUG in `s01_ingest.py` (PII hardening)

### Tier 2 — pipeline diagnostics (backlog)

6. **Cache hit/miss decisions** — when `_is_stage_cached()` returns, log stage name + reason
7. **Importer sync stats** — already logged adequately (line 265). No change needed

### Tier 3 — observability (backlog, do when touching these files)

8. **Concurrency queue depth** — log semaphore config when created. DEBUG level
9. **PII entity breakdown** — per-type counts. DEBUG level. Low priority
10. **FFmpeg error detail** — command and return code on failure. ERROR level
11. **Keychain resolution** — which store, which keys found/missing. INFO level. *Python-side: still backlogged. Swift-side partial-ship: `ServeManager.overlayAPIKeys` logs `injected API key for provider=<name>` at `ServeManager.swift:382`. Equivalent coverage for the desktop deployment's credential path; Python-side CLI/serve still uninstrumented.*
12. **Manifest load/save** — schema version and stage summary. DEBUG level

### Future: desktop app support (gated on desktop work)

13. **Machine-readable progress markers** — `[BN:STAGE:8:START]` / `[BN:STAGE:8:DONE:12.3s]` on stdout for the SwiftUI process runner to parse
14. **`bristlenose diagnostic-bundle`** CLI command — collects PII-stripped log, Python version, platform, bristlenose version, installed providers, manifest summary
15. **Desktop app error panel** — last N stderr lines + "Send diagnostic info" button

## Multi-project / multi-user

**Already solved by filesystem layout.** Each project has its own `bristlenose-output/.bristlenose/bristlenose.log`. No tangling. No correlation IDs needed. When the desktop app runs multiple projects, each sidecar writes to its own log. When serve mode eventually supports multi-project, project IDs in messages will suffice.

## Non-goals (with rationale)

| Non-goal | Why |
|----------|-----|
| **Structured logging (JSON lines)** | The only "machine" parsing these logs is `grep`. Human-readable format is faster to scan in a text editor. Migration cost across 34 files is not justified |
| **structlog / loguru migration** | stdlib logging with two handlers is adequate. 34 files, 133 calls, 12 tests — migration cost > benefit |
| **Log aggregation / shipping** | Local-first tool. The diagnostic bundle (future Phase F) is the "shipping" mechanism — user-initiated, not automatic |
| **Correlation IDs** | Each project has its own log file. Session IDs in messages provide sufficient correlation within a single-process pipeline |
| **Per-module log levels** | stdlib supports this but exposing it to users adds complexity without proportional benefit. The two-knob system is sufficient |
| **Metrics / counters / histograms** | Prometheus-style metrics solve distributed-systems observability. For a local tool, token counts in the log file are greppable |
| **Per-request API middleware** | Uvicorn logs requests. Domain-level handler logging covers business operations. The gap between these is not worth filling for a single-user local server |
| **Compression** | 15 MB ceiling per project is negligible. gzip would add complexity for negligible gain |
| **Log viewer in serve mode** | The log file is a developer artifact. The desktop app may surface last few error lines, but that reads stderr, not the log file |

## References

- Phase 4a in `docs/design-pipeline-resilience.md` describes a structured event log (`pipeline-events.jsonl`) for provenance tracking. That's a separate system — immutable, append-only, machine-readable. The log file here is for human debugging, not data integrity
- The resilience design's event log and the logging system serve different purposes: events are facts about data ("quote q001 was extracted by claude-sonnet-4"), logs are operational diagnostics ("LLM call took 3.2s, 1847 output tokens, response had 25 assignments")
- Peter Bourgon, [_Logging v. Instrumentation_](https://peter.bourgon.org/blog/2016/02/07/logging-v-instrumentation.html) (2016) — log actionable information, use metrics for volume data
- Charity Majors, [_Observability is a Many-Splendored Thing_](https://charity.wtf/2020/03/03/observability-is-a-many-splendored-thing/) — observability ≠ three pillars
- The Twelve-Factor App, [_Logs_](https://12factor.net/logs) — treat logs as event streams
