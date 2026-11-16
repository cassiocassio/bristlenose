"""BR-16: a placeholder row for a session that produced no transcript says so.

Contract: docs/design-shared-formats.md, "people.yaml computed.status".
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bristlenose.models import PeopleFile
from bristlenose.people import (
    compute_participant_stats,
    load_people_file,
    merge_people,
    write_people_file,
)
from tests.test_people import _seg, _session, _transcript


def _written(tmp_path: Path, sessions, transcripts) -> dict:
    people = merge_people(None, compute_participant_stats(sessions, transcripts))
    write_people_file(people, tmp_path)
    return yaml.safe_load((tmp_path / "people.yaml").read_text(encoding="utf-8"))


def test_placeholder_row_is_marked_failed_and_working_rows_carry_no_key(tmp_path: Path) -> None:
    sessions = [_session("p1", 1), _session("p2", 2)]
    raw = _written(tmp_path, sessions, [_transcript("p1", [_seg("one two three")])])
    assert raw["participants"]["p2"]["computed"]["status"] == "failed"
    # the everyday row is byte-for-byte what it was: no key at all
    assert "status" not in raw["participants"]["p1"]["computed"]


def test_file_without_the_key_still_reads(tmp_path: Path) -> None:
    raw = _written(tmp_path, [_session("p1", 1)], [_transcript("p1", [_seg("one two")])])
    assert load_people_file(tmp_path) is not None
    assert "status" not in raw["participants"]["p1"]["computed"]


def test_an_older_reader_ignores_the_key(tmp_path: Path) -> None:
    """An older model has no `status` field; pydantic's default drops unknown keys."""
    from pydantic import BaseModel

    class OldComputed(BaseModel):
        participant_id: str
        source_file: str

    raw = _written(tmp_path, [_session("p1", 1)], [])
    comp = raw["participants"]["p1"]["computed"]
    assert comp["status"] == "failed"
    assert OldComputed.model_validate(comp).participant_id == "p1"
    assert isinstance(PeopleFile.model_validate(raw), PeopleFile)


def test_a_later_success_clears_the_mark_and_keeps_the_researchers_edits(tmp_path: Path) -> None:
    sessions = [_session("p1", 1)]
    first = merge_people(None, compute_participant_stats(sessions, []))
    first.participants["p1"].editable.full_name = "Ada Lovelace"
    write_people_file(first, tmp_path)

    existing = load_people_file(tmp_path)
    assert existing is not None and existing.participants["p1"].computed.status == "failed"
    second = merge_people(
        existing, compute_participant_stats(sessions, [_transcript("p1", [_seg("hello there")])])
    )
    assert second.participants["p1"].computed.status is None
    assert second.participants["p1"].editable.full_name == "Ada Lovelace"
