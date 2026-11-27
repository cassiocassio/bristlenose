"""`analyze` never puts the raw transcript's speaker label in a prompt as speech.

The raw `.txt` writer puts each line's label after its code,
`[00:55] [p1] (Speaker A) Um, it's a good one.`, and `load_transcripts_from_dir`
(what `analyze` reads) kept it as part of the words. Every `analyze` prompt then
read "(Speaker A) Um, it's a good one", and on 27 Nov 2026 a local model
(gemma4:e4b, no grammar) copied it into 58 of 105 quotes' `verbatim_excerpt`,
which serve uses to find the quote in a transcript the importer had already
stripped. A platform transcript's label is the person's real name.

Only a label the pipeline recorded for the session is taken, the importer's own
rule (`bristlenose.speaker_labels`), so a transcript's "(laughs)" stays.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.models import INAUDIBLE_TOKEN
from bristlenose.pipeline import load_transcripts_from_dir
from tests.test_importer_speaker_labels import _info

TRANSCRIPT = (
    "# Transcript: s1\n\n"
    "[00:00] [m1] (Speaker B) Tell me about an object you love.\n\n"
    "[00:55] [p1] (Speaker A) Um, it's a good one. A crock pot.\n\n"
    "[01:13] [p1] (laughs) Not so tech.\n\n"
    "[01:20] [p1] (Robert (Bob) Smith) " + INAUDIBLE_TOKEN + "\n"
)


def _project(tmp_path: Path, labels: list[str]) -> Path:
    out = tmp_path / "bristlenose-output"
    raw = out / "transcripts-raw"
    raw.mkdir(parents=True)
    (raw / "s1.txt").write_text(TRANSCRIPT, encoding="utf-8")
    if labels:
        _info(out, "s1", labels, [])
    return raw


def test_a_recorded_label_leaves_the_words_and_is_kept_as_the_label(tmp_path: Path) -> None:
    raw = _project(tmp_path, ["Speaker A", "Speaker B", "Robert (Bob) Smith"])
    [t] = load_transcripts_from_dir(raw, labels_from=raw.parent)
    assert [(s.speaker_label, s.text, s.inaudible) for s in t.segments] == [
        ("Speaker B", "Tell me about an object you love.", False),
        ("Speaker A", "Um, it's a good one. A crock pot.", False),
        # Not a label the session has: the transcript's own words.
        (None, "(laughs) Not so tech.", False),
        # A label holding brackets hid the token from the inaudible check.
        ("Robert (Bob) Smith", "", True),
    ]
    assert "(Speaker" not in t.full_text()


def test_with_no_record_nothing_is_taken(tmp_path: Path) -> None:
    raw = _project(tmp_path, [])
    [t] = load_transcripts_from_dir(raw, labels_from=raw.parent)
    assert t.segments[1].text == "(Speaker A) Um, it's a good one. A crock pot."
    assert t.segments[1].speaker_label is None


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


def test_analyze_reads_the_record_beside_the_transcripts(
    runner, tmp_path: Path, monkeypatch,
) -> None:
    # The caller, not only the helper: what analyze itself loads for its prompts.
    raw = _project(tmp_path, ["Speaker A", "Speaker B"])
    loaded: list = []

    def spy(*args, **kwargs):  # type: ignore[no-untyped-def]
        loaded.extend(load_transcripts_from_dir(*args, **kwargs))
        return []  # stop before any LLM call

    monkeypatch.setattr("bristlenose.pipeline.load_transcripts_from_dir", spy)
    runner.invoke(app, ["analyze", str(raw), "--llm", "claude"])
    assert loaded, "analyze did not load the transcripts"
    assert all("(Speaker" not in t.full_text() for t in loaded)
