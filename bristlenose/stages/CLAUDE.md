# Pipeline Stages Context

## Transcript format conventions

- **Participant codes**: Segments use `[p1]`, `[p2]` etc. — never generic role labels like `[PARTICIPANT]`
- **Speaker labels**: Original Whisper labels (`Speaker A`, `Speaker B`) kept in parentheses in raw transcripts only
- **Timecodes**: `MM:SS` for segments under 1 hour, `HH:MM:SS` at or above 1 hour. Mixed formats in the same file is correct
- **Timecodes are floats internally**: All data structures store seconds as `float`. String formatting happens only at output. Never parse formatted timecodes back within the same session
- **`.txt` is canonical**: The parser (`load_transcripts_from_dir`) reads only `.txt` files. `.md` files are human-readable companions, not parsed back
- **Legacy format support**: Parser also accepts old-format files with `[PARTICIPANT]`/`[RESEARCHER]` role labels

## Output directory structure

```
output/
├── raw_transcripts/          # Stage 6 output
│   ├── p1_raw.txt            # Plain text (canonical, machine-readable)
│   ├── p1_raw.md             # Markdown companion (human-readable)
│   ├── p2_raw.txt
│   └── p2_raw.md
├── cooked_transcripts/       # Stage 7 output (PII-redacted, only when --redact-pii)
│   ├── p1_cooked.txt
│   ├── p1_cooked.md
│   ├── p2_cooked.txt
│   └── p2_cooked.md
├── intermediate/             # JSON snapshots (if write_intermediate=True)
├── temp/                     # Extracted audio, working files
├── people.yaml               # Participant registry (computed stats + human-editable fields)
├── research_report.md        # Final markdown report
├── research_report.html      # Final HTML report with interactive features
├── transcript_p1.html        # Per-participant transcript page (one per participant)
├── transcript_p2.html
└── ...
```

## Stage 5b: Speaker identification

`identify_speakers.py` runs a two-pass speaker role assignment: heuristic first, then LLM refinement.

- **Heuristic pass** (`identify_speaker_roles_heuristic`): scores speakers by question ratio and researcher-phrase hits. Assigns `RESEARCHER`, `PARTICIPANT`, or `OBSERVER`. Fast, no LLM needed
- **LLM pass** (`identify_speaker_roles_llm`): sends first ~5 minutes to the LLM for refined role assignment. Also extracts `person_name` and `job_title` for each speaker when mentioned in the transcript
- **Return type**: `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` — a dataclass with `speaker_label`, `role`, `person_name`, `job_title`. Still mutates segments in place for role assignment (existing behaviour). Returns empty list on exception
- **`SpeakerInfo` import**: defined in `identify_speakers.py`. Other modules import it under `TYPE_CHECKING` to avoid circular imports (e.g. `people.py` uses `if TYPE_CHECKING: from bristlenose.stages.identify_speakers import SpeakerInfo`)
- **Structured output**: `SpeakerRoleItem` in `llm/structured.py` has `person_name` and `job_title` fields (both default `""` for backward compatibility with existing LLM responses)

## LLM concurrency in stages

Stages 8 and 9 accept a `concurrency: int = 1` kwarg, passed by the pipeline from `settings.llm_concurrency`. The pattern:

```python
semaphore = asyncio.Semaphore(concurrency)
async def _process(transcript):
    async with semaphore:
        return await _segment_single(transcript, llm_client)
return list(await asyncio.gather(*(_process(t) for t in transcripts)))
```

- **Default 1**: behaves identically to the old sequential loop (backward compatible, useful for tests)
- **Pipeline passes 3**: `concurrency=self.settings.llm_concurrency` in both `run()` and `run_analysis_only()`
- **Error isolation**: each `_process()` closure has its own try/except. A failed participant doesn't cancel siblings (asyncio.gather default behaviour — if one raises, others still complete since the exception is caught inside `_process`)
- **No cross-stage semaphore**: each stage creates its own semaphore. Stages still execute sequentially in the pipeline

## Duplicate timecode helpers

Both `models.py` and `utils/timecodes.py` define `format_timecode()` and `parse_timecode()`. They behave identically. Stage files import from one or the other — both are fine. The `utils/timecodes.py` version has a more sophisticated parser (SRT/VTT milliseconds support).
