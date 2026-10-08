# Transcript readability experiments (6 Oct 2026)

The scripts behind `docs/design-transcript-readability.md` and
`docs/mockups/transcript-readability-versions.html`. Throwaway research code, kept so
the measurements and the mockup can be redone.

Everything ran in a scratch directory, never inside a project folder. To rerun, make a
working directory holding copies of:

- `db/<project>/bristlenose.db` (plus `-wal`/`-shm` if present) and
  `db/<project>/session_segments.json`, copied from a project's
  `bristlenose-output/.bristlenose/` (the database) and its `intermediate/` folder.
  The scripts name the projects `IKEA_with_uxfriends`, `fossda-opensource`,
  `project-ikea`, `Fishkeeping`, `Rockclimbing` and `ja`.
- `s1.wav` and `ja.wav`, copied from a project's `.bristlenose/temp/s1_extracted.wav`.

Run from that directory with the repo venv (`.venv/bin/python`). No paid calls; the
Whisper runs are local mlx-whisper.

| Script | What it does | Doc section |
|---|---|---|
| `style.py` | Lower-case "i", unpunctuated runs, words per sentence in raw Whisper output | §1.1 |
| `stats.py` | Paragraph length distribution per project database | §1.3 |
| `join.py` | Re-runs the importer's time-based word join | §1.4 |
| `make_carry.py` | Writes `carry_transcribe.py`: mlx-whisper's `transcribe.py` with the prompt carried to every window. Run it first | §2.3 |
| `exp.py`, `exp2.py`, `exp3.py` | Whisper settings on the 1:00–6:00 excerpt | §2.3 |
| `exp4.py <current\|G\|H\|J>` | The same on the full file; writes `full_<cfg>_<time>.json` | §2.3 |
| `exp5.py`, `exp6.py` | Japanese: no prompt, Japanese prompt, English prompt | §5 |
| `sim.py` | Candidate paragraph rules on raw segments | §3.2 |
| `gen_data.py`, `gen_html.py` | Build the comparison mockup from the runs above | mockup |

`gen_html.py` copies the shipped CSS out of
`docs/mockups/transcript-paragraph-capitalisation.html`, which was generated from the
tree; regenerate that file first if the theme has moved.
