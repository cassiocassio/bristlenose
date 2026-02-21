# QA: Phase 1d-ext — Per-session caching for transcription and speaker ID

## What changed

Stages 3-5 (transcription) and 5b (speaker identification) now cache per-session results to intermediate JSON, so a resumed pipeline skips Whisper and LLM calls for sessions that already completed.

**Measured impact**: On a 4-session project (M2 Max), transcription was 52% of resume time (56s) and speaker ID was 7% + ~$0.02 LLM cost. Both are now zero on resume.

## Files changed

| File | Change |
|------|--------|
| `bristlenose/pipeline.py` | Transcription caching (session_segments.json), speaker ID caching (speaker-info/*.json), moved `intermediate` dir earlier |
| `bristlenose/stages/identify_speakers.py` | Added `speaker_info_to_dict()` / `speaker_info_from_dict()` |
| `tests/test_pipeline_resume.py` | 10 new tests for 1d-ext |

## Automated test coverage

33 tests in `test_pipeline_resume.py` (23 existing + 10 new), all passing:

- `test_transcription_segments_json_roundtrip` — session_segments.json write/load fidelity
- `test_transcription_cache_skip_when_complete` — full cache skip path
- `test_transcription_per_session_partial_resume` — partial resume (1 of 3 cached)
- `test_transcription_filter_cached_from_json` — JSON filtering by session_id
- `test_transcription_merge_cached_and_fresh` — dict merge correctness
- `test_speaker_info_json_roundtrip` — SpeakerInfo serialize/deserialize
- `test_speaker_id_cache_skip_when_complete` — full speaker ID cache skip
- `test_speaker_id_per_session_partial_resume` — partial speaker ID resume
- `test_speaker_info_segments_restored_from_cache` — speaker_role preserved on reload
- `test_assign_speaker_codes_always_reruns` — global p1/p2 numbering consistency

## Human QA checklist

These checks require running a real pipeline with audio files, which unit tests can't cover:

### 1. Full run → resume (transcription caching)

```bash
bristlenose run <project-with-audio>/
# Wait for transcription to complete, then Ctrl+C during speaker ID or later
bristlenose run <project-with-audio>/
```

**Verify**:
- [ ] Second run prints `✓ Transcribed N sessions (M segments)  (cached)` — no Whisper invocation
- [ ] `.bristlenose/intermediate/session_segments.json` exists and contains all sessions
- [ ] Pipeline manifest shows `transcribe` stage with session records
- [ ] Downstream stages (speaker ID, merge, analysis) produce identical output

### 2. Full run → resume (speaker ID caching)

```bash
bristlenose run <project-with-audio>/
# Wait for speaker ID to complete, then Ctrl+C during topic segmentation
bristlenose run <project-with-audio>/
```

**Verify**:
- [ ] Second run prints `✓ Identified speakers  (cached)` — no LLM call for speaker ID
- [ ] `.bristlenose/intermediate/speaker-info/s1.json` etc. exist
- [ ] Speaker codes (p1, p2, m1) are identical between runs
- [ ] People file names/roles match between runs

### 3. Partial transcription resume

```bash
bristlenose run <project-with-4+-sessions>/
# Ctrl+C after 2 of 4 sessions transcribe (watch the progress counter)
bristlenose run <project-with-4+-sessions>/
```

**Verify**:
- [ ] Second run prints `✓ Transcribed 4 sessions (M segments, 2 new sessions)  Xs`
- [ ] Only 2 sessions go through Whisper, not all 4
- [ ] session_segments.json contains all 4 sessions after the second run

### 4. Clean run still works

```bash
bristlenose run --clean <project>/
```

**Verify**:
- [ ] Everything runs from scratch (no caching)
- [ ] No leftover intermediate files from previous run

### 5. VTT/SRT-only project (no Whisper)

```bash
bristlenose run <project-with-vtt-files>/
# Ctrl+C after transcription, re-run
```

**Verify**:
- [ ] Parsing results are cached just like Whisper results
- [ ] Second run shows `(cached)` for transcription
