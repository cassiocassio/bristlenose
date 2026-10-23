"""``transcripts-raw/`` carries a readme saying not to edit it (#120, 23 Oct 2026).

The folder is RAW: the transcripts as first transcribed, written again by every
run, while the edited transcripts live in the report. The readme says so where
a researcher opening the folder will see it. It is ``README.md``, never a
``.txt``: ``analyze`` and the serve importer read every ``*.txt`` there, and a
``README.txt`` would be one more transcript to them.

Real ``Pipeline`` methods over the stubbed stages of ``test_pipeline_command_caches``.
"""

from __future__ import annotations

from pathlib import Path

from bristlenose.pipeline import load_transcripts_from_dir, prune_stale_session_files
from bristlenose.server.importer import _parse_transcript_headers
from bristlenose.stages.s06_merge_transcript import RAW_README_NAME, write_raw_transcripts
from bristlenose.utils.markdown import RAW_TRANSCRIPTS_README
from tests.test_pipeline_command_caches import _drive
from tests.test_transcript_writing import _make_transcript


def _raw(tmp_path: Path) -> Path:
    return tmp_path / "output" / "transcripts-raw"


def test_a_run_writes_the_readme(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})

    readme = _raw(tmp_path) / "README.md"
    assert readme.read_text(encoding="utf-8") == RAW_TRANSCRIPTS_README
    assert RAW_README_NAME == "README.md"


def test_transcribe_writes_the_readme(tmp_path: Path) -> None:
    _drive(tmp_path, "transcribe", 1, {})

    assert (_raw(tmp_path) / "README.md").read_text(encoding="utf-8") == RAW_TRANSCRIPTS_README


def test_every_run_writes_it_again(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 1, {})
    readme = _raw(tmp_path) / "README.md"
    readme.write_text("my notes\n", encoding="utf-8")

    _drive(tmp_path, "run", 1, {})

    assert readme.read_text(encoding="utf-8") == RAW_TRANSCRIPTS_README


def test_analyze_reads_the_transcripts_and_not_the_readme(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    raw = _raw(tmp_path)
    assert (raw / RAW_README_NAME).is_file()
    skipped: list = []

    loaded = load_transcripts_from_dir(raw, skipped=skipped)

    assert sorted(t.session_id for t in loaded) == ["s1", "s2"]
    # Not refused by name either (R119 names an untimed .txt it cannot read).
    assert skipped == []

    log: dict = {}
    _drive(tmp_path, "analyze", 2, log)
    assert log["topics"] == [["s1", "s2"]], log


def test_the_importer_finds_two_sessions_not_three(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    assert (_raw(tmp_path) / RAW_README_NAME).is_file()

    assert sorted(_parse_transcript_headers(_raw(tmp_path))) == ["s1", "s2"]


def test_a_locked_readme_never_fails_the_run(tmp_path: Path, caplog) -> None:
    # Told not to edit these files, a researcher may lock the readme in Finder.
    raw = tmp_path / "transcripts-raw"
    raw.mkdir()
    readme = raw / RAW_README_NAME
    readme.write_text("locked\n", encoding="utf-8")
    readme.chmod(0o444)
    try:
        with caplog.at_level("WARNING", logger="bristlenose.stages.s06_merge_transcript"):
            paths = write_raw_transcripts([_make_transcript()], raw)
    finally:
        readme.chmod(0o644)

    assert [p.name for p in paths] == ["s1.txt"]
    assert (raw / "s1.txt").is_file()
    assert readme.read_text(encoding="utf-8") == "locked\n"
    assert "the transcripts are unaffected" in caplog.text


def test_the_stale_session_pruner_leaves_it(tmp_path: Path) -> None:
    # A removed interview's files go once a run succeeds; the readme is no one's.
    _drive(tmp_path, "run", 2, {})

    prune_stale_session_files(tmp_path / "output", keep=["s1"])

    assert (_raw(tmp_path) / RAW_README_NAME).is_file()
    assert not (_raw(tmp_path) / "s2.txt").exists()
