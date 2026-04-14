# Architecture & Infrastructure Improvements

_14 Mar 2026_

Suggested architectural, platform, and infrastructure improvements for Bristlenose, informed by the codebase, design docs, TODO, and roadmap.

---

## Architecture Improvements

### 1. Pipeline — Incremental Re-runs

The biggest pain point: adding 2 interviews to a 6-session project re-clusters everything and re-spends LLM credits. File hashing for source change detection (Phase 2 in `design-pipeline-resilience.md`) would enable selective re-processing. The dedup key `(project_id, session_id, participant_id, start_timecode)` is already designed — it needs implementation.

### 2. Pipeline — Stage Overlap (Pipelining)

Stages 8→9 run sequentially per-participant, but participant B's segmentation could overlap with participant A's quote extraction. This is Issue #32 in the performance audit — a producer/consumer pattern between stages would cut wall-clock time significantly for multi-participant projects.

### 3. LLM Response Caching

Hash `(transcript_chunk + prompt_template + model_id)` → skip API calls on unchanged re-runs. This is Issue #34, distinct from stage caching — it operates at the LLM call level, saving credits even when the pipeline "thinks" it needs to re-run a stage.

### 4. Multi-Project Support

Project ID is hardcoded to 1 in serve mode. A project registry (home screen, SQLite row per project, switching) would unlock the "research hub" use case. This is prerequisite for the desktop app feeling like a real app vs. a CLI wrapper.

### 5. Event Sourcing for Edits

Currently no provenance tracking — who changed what, when. An append-only event log for researcher edits (tag, star, hide, rename, reorder) would enable undo/redo, conflict resolution for incremental re-runs, and audit trails.

---

## Platform / Infrastructure Improvements

### 6. CI Gaps — Windows + Multi-Python

CI only runs on `ubuntu-latest` with Python 3.10. Missing:

- **Windows** (design doc exists, `pyproject.toml` is Windows-ready, needs pytest on Windows runner)
- **Python 3.10–3.13 matrix** (3.10 EOL is Oct 2026 — need to test the floor before bumping)
- **macOS CI** (desktop app CI is separate; main pipeline should also test macOS)

### 7. Observability — Logging Tier 1

The two-knob logging system is built but barely instrumented. 20 lines of code (per `design-logging.md`) would add:

- LLM response shape logging (catches double-serialization bugs)
- Token usage at INFO level
- AutoCode batch progress
- Cache hit/miss decisions

This is the highest ROI infrastructure change available.

### 8. Temp File Cleanup

Extracted WAV files (~115 MB/hr/participant) are never deleted (Issue #33). For a 6-session project that's potentially ~4 GB of orphaned temp files. A cleanup hook at pipeline completion (or a `bristlenose clean` command) would help.

### 9. Bundle Size Tracking

No budget or tracking for JS bundle size. With the desktop app .dmg targeting 365–435 MB, and React islands growing, a CI check that fails on bundle regression would prevent creep.

### 10. Playwright E2E Layers 4–5

Layers 1–3 (console, links, network) are done. Layer 4 (structural smoke — do sections render, do counts match data?) and Layer 5 (write actions — star, hide, edit, tag) would close the biggest testing gap. The `data-testid` convention is already in place.

---

## Packaging & Distribution

### 11. Desktop App (.dmg)

Design doc is complete (`docs/design-desktop-app.md`), SwiftUI scaffold designed, PyInstaller sidecar planned. Open blockers: signed static FFmpeg for arm64, PyInstaller + ctranslate2 bundling, App Store sandbox compatibility. This is the #1 adoption barrier for non-technical researchers.

### 12. Snap Store Publication

Snap builds but isn't published — needs classic confinement forum approval. Once approved, auto-publish from CI on tagged releases.

### 13. Windows Distribution (winget)

Planned but not implemented. The Python package works on Windows; packaging as an MSI/MSIX for winget would reach enterprise Windows shops doing UX research.

---

## Performance

### 14. Cache `system_profiler` (Issue #30) ✅

**Done (Mar 2026).** `detect_hardware()` caches static hardware properties (chip_name, gpu_cores, memory_gb) to `~/.config/bristlenose/.hardware-cache.json` with 24h TTL. Dynamic properties (mlx_available, cuda_available) are always re-checked. Saves ~2–4s on macOS startup.

### 15. Word Timestamp Pruning (Issue #35)

After transcript merge, ~80K per-word timestamp objects are carried through the rest of the pipeline but never used again. Dropping them after merge saves memory and serialization time.

### 16. Mid-Run Provider Switching

If Claude credits run out mid-pipeline, there's no way to switch to ChatGPT without restarting. A provider fallback chain (or interactive prompt on failure) would save the $3.50+ already spent on completed stages.

---

## Suggested Priority Order

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Logging Tier 1 (#7) | ~2 hrs | High — debuggability |
| 2 | Temp file cleanup (#8) | ~3 hrs | High — disk space |
| 3 | Cache system_profiler (#14) | ~1 hr | Medium — startup UX |
| 4 | Source change detection (#1) | ~15 hrs | Very high — LLM cost |
| 5 | Windows + multi-Python CI (#6) | ~8 hrs | High — reliability |
| 6 | LLM response cache (#3) | ~10 hrs | High — LLM cost |
| 7 | Playwright E2E 4–5 (#10) | ~15 hrs | High — test coverage |
| 8 | Stage pipelining (#2) | ~20 hrs | Medium — speed |
| 9 | Desktop app (#11) | ~40+ hrs | Very high — adoption |
| 10 | Multi-project (#4) | ~30 hrs | High — serve mode UX |

The first three items are quick wins that immediately improve developer experience and user experience. Items 4–7 address the two biggest structural gaps: LLM cost on re-runs and CI coverage. Items 8–10 are the larger architectural bets.
