"""`analyze` names a transcript it cannot read, rather than skipping it (R119).

`analyze` reads the pipeline's own transcript format: `[mm:ss] [p1] text` lines.
A plain-text transcript with no timecodes ("Interviewer: …") produced no
segments and was dropped without a word. Beside other transcripts the run went
ahead without it; alone, the run said "No transcript files found." about a
folder that held one. Reading untimed text is a feature, not this fix: the file
is refused by name, with the existing `unsupported_format` reason, in the same
files bucket `run` uses for a format it declines.

Drives the real CLI and the real `run_analysis_only`; the all-untimed folder
aborts before any LLM call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.refusals import UnusableReason

UNTIMED = "Interviewer: How did you find it?\nJane: Fine, mostly.\n"
TIMED = "# Transcript: s1\n\n[00:05] [m1] How did you find it?\n[00:09] [p1] Fine, mostly.\n"


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def test_the_loader_states_an_untimed_transcript_beside_a_timed_one(tmp_path: Path) -> None:
    (tmp_path / "jane.txt").write_text(UNTIMED, encoding="utf-8")
    (tmp_path / "s1.txt").write_text(TIMED, encoding="utf-8")
    skipped: list = []

    loaded = load_transcripts_from_dir(tmp_path, skipped=skipped)

    assert [t.session_id for t in loaded] == ["s1"]
    assert [(s.path.name, s.reason) for s in skipped] == [
        ("jane.txt", UnusableReason.UNSUPPORTED_FORMAT)
    ]


def test_analyze_names_the_untimed_transcript_and_records_it(runner, tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    (transcripts / "jane.txt").write_text(UNTIMED, encoding="utf-8")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["analyze", str(transcripts), "-o", str(out_dir)])

    assert result.exit_code == 1, result.output
    assert "jane.txt — Not a format Bristlenose reads." in result.output, result.output
    events = out_dir / ".bristlenose" / "pipeline-events.jsonl"
    terminus = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
    assert terminus["event"] == "run_failed", terminus
    ingest = terminus["summary"]["ingest"]
    assert ingest["succeeded"] == 0, ingest
    [refused] = ingest["failed"]
    assert refused["source_file"] == "jane.txt", refused
    assert refused["cause"]["category"] == "unusable_input", refused
    assert refused["cause"]["reason"] == "unsupported_format", refused
