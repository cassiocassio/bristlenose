"""The raw transcript's speaker label is not part of what was said.

`[00:14] [p1] (Speaker B) Okay…` — the `.txt` writes each line's speaker label
after its code, and a platform transcript's label is the person's real name.
Until 7 Oct 2026 the importer kept it in the paragraph text, so the transcript
page drew "(Speaker B)" and "(Rachel Okafor)" in front of the words, and the
name reached everything that reads the text. Only a label the pipeline recorded
for the session is taken; anything else in brackets is the transcript's own.
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.server.importer import _session_speaker_labels, _without_speaker_label


def _info(out: Path, sid: str, infos: list[str], segment_labels: list[str]) -> None:
    d = out / ".bristlenose" / "intermediate" / "speaker-info"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.json").write_text(json.dumps({
        "speaker_infos": [{"speaker_label": x} for x in infos],
        "segments_with_roles": [{"speaker_label": x} for x in segment_labels],
    }))


def test_a_split_recordings_labels_and_a_platform_transcripts_names(tmp_path: Path) -> None:
    _info(tmp_path, "s1", ["Speaker A", "Speaker B"], [])
    _info(tmp_path, "s2", [], ["Rachel Okafor", "Yuki Tanaka"])
    assert _session_speaker_labels(tmp_path, "s1") == {"Speaker A", "Speaker B"}
    assert _session_speaker_labels(tmp_path, "s2") == {"Rachel Okafor", "Yuki Tanaka"}
    assert _session_speaker_labels(tmp_path, "s9") == set()


def test_only_the_sessions_own_label_is_taken() -> None:
    labels = {"Speaker B", "Rachel Okafor", "Robert (Bob) Smith"}
    assert _without_speaker_label("(Speaker B) um well I think", labels) == "um well I think"
    assert _without_speaker_label("(Rachel Okafor) Right, we are recording.", labels) == (
        "Right, we are recording."
    )
    assert _without_speaker_label("(Robert (Bob) Smith) Hi.", labels) == "Hi."
    # The transcript's own brackets stay.
    assert _without_speaker_label("(laughs) yeah", labels) == "(laughs) yeah"
    assert _without_speaker_label("(Speaker C) hello", labels) == "(Speaker C) hello"
    # Nothing known: nothing taken.
    assert _without_speaker_label("(Speaker B) um", set()) == "(Speaker B) um"
    # A line that is only a label keeps it rather than becoming empty.
    assert _without_speaker_label("(Speaker B)", labels) == "(Speaker B)"


def test_the_transcript_page_draws_no_label(tmp_path: Path) -> None:
    from tests.test_serve_moderator_identities import _TWO, _client, _project

    project = _project(tmp_path, _TWO)
    out = project / "bristlenose-output"
    raw = out / "transcripts-raw" / "s1.txt"
    text = raw.read_text(encoding="utf-8")
    labelled = text.replace("[p1] Thanks", "[p1] (Speaker B) Thanks")
    assert labelled != text
    raw.write_text(labelled, encoding="utf-8")
    _info(out, "s1", ["Speaker A", "Speaker B"], [])
    segs = _client(project).get("/api/projects/1/transcripts/s1").json()["segments"]
    assert segs[1]["text"].startswith("Thanks for having me")
