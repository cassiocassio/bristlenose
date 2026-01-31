# Pipeline Stages Context

## Transcript format conventions

- **Participant codes**: Segments use `[p1]`, `[p2]` etc. — never generic role labels like `[PARTICIPANT]`
- **Speaker labels**: Original Whisper labels (`Speaker A`, `Speaker B`) kept in parentheses in raw transcripts only
- **Timecodes**: `MM:SS` for segments under 1 hour, `HH:MM:SS` at or above 1 hour. Mixed formats in the same file is correct
- **Timecodes are floats internally**: All data structures store seconds as `float`. String formatting happens only at output. Never parse formatted timecodes back within the same session
- **`.txt` is canonical**: The parser (`_load_transcripts_from_dir`) reads only `.txt` files. `.md` files are human-readable companions, not parsed back
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
└── research_report.html      # Final HTML report with interactive features
```

## Duplicate timecode helpers

Both `models.py` and `utils/timecodes.py` define `format_timecode()` and `parse_timecode()`. They behave identically. Stage files import from one or the other — both are fine. The `utils/timecodes.py` version has a more sophisticated parser (SRT/VTT milliseconds support).
