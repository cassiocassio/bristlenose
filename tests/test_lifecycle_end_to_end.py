"""A study's life, end to end: the real ``run`` and the real server, in the
order the Mac app drives them. The rig is ``tests/lifecycle_rig.py``.

Each test is one sequence a researcher actually performs. The move, rename,
re-filing and copy sequences were strict xfails until identity stopped being a
path on 15 Oct 2026 (``docs/design-project-identity.md``, phase 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bristlenose import study_marker
from tests.lifecycle_rig import new_study
from tests.test_serve_project_root import fast_watcher as fast_watcher  # noqa: F401


def test_first_analysis_with_the_server_started_first(tmp_path: Path, fast_watcher) -> None:
    """The app starts the server, then the first run: the report fills in."""
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        study.sessions(client, expect=2)
        study.assert_healthy()
    assert sorted(study.transcribed[0]) == ["Interview 1.wav", "Interview 2.wav"]



def test_an_added_interview_keeps_curation_and_transcribes_only_itself(
    tmp_path: Path, fast_watcher,
) -> None:
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        star = study.quote_ids(client)[0]
        study.star(client, star)
        study.add_recording("Interview 3.wav")
        study.run()
        study.sessions(client, expect=3)
        study.assert_healthy()
        assert star in study.starred(client), "adding an interview lost a star"
    assert study.transcribed[1] == ["Interview 3.wav"]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Re-analyse under a live server moves the output folder the server holds open; "
    "Windows refuses the move, so the run reuses the folder and curation stays (the same "
    "limit test_lifecycle_scenarios skips for reanalyse-succeeds-live-serve)",
)
def test_re_analyse_is_a_deliberate_reset_and_the_report_comes_back(
    tmp_path: Path, fast_watcher,
) -> None:
    """Re-analyse under a live server: the analysis is rebuilt, curation is
    reset by design (``design-analysis-lifecycle.md`` §1), the report fills."""
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        study.star(client, study.quote_ids(client)[0])
        before = study_marker.read(study.folder / "bristlenose-output")
        study.run(clean=True)
        study.sessions(client, expect=2)
        study.assert_healthy()
        assert study.starred(client) == set()
    assert before is not None
    assert study_marker.read(study.folder / "bristlenose-output") == before, (
        "a Re-analyse gave the study a new identity"
    )


def test_re_analyse_keeps_where_a_copy_came_from(tmp_path: Path) -> None:
    """A copy the app re-minted records ``copied_from``; resetting its analysis
    must not erase that, or its sidebar row stops saying it is a copy the next
    time the marker is read (found by review, 15 Oct 2026)."""
    import uuid

    study = new_study(tmp_path, "Interview 1.wav")
    study.run()
    out = study.folder / "bristlenose-output"
    original = str(uuid.uuid4())
    study_marker.write(out, str(uuid.uuid4()), minted_by="app", copied_from=original)
    copy_id = study_marker.read(out)
    study.run(clean=True)
    assert study_marker.read(out) == copy_id
    assert study_marker.copied_from(out) == original, "a Re-analyse forgot the copy's original"


def test_a_folder_moved_while_closed_is_not_transcribed_again(
    tmp_path: Path, fast_watcher,
) -> None:
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    study.run()
    minted = study_marker.read(study.folder / "bristlenose-output")
    assert minted is not None, "a run with no server open minted no study marker"
    study.move_to(tmp_path / "Archive" / "2026" / "Talismanic")
    study.run()
    assert study.transcribed[1] == [], "a moved study paid for transcription again"
    assert study_marker.read(study.folder / "bristlenose-output") == minted


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows CI still finds bristlenose.db open after the in-process server stops, so it "
    "refuses the move; a real CLI process lets go when it exits. The holder is not yet found "
    "(TODO.md, 16 Oct 2026)",
)
def test_a_folder_moved_while_closed_keeps_its_curation(tmp_path: Path, fast_watcher) -> None:
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        star = study.quote_ids(client)[0]
        study.star(client, star)
    study.move_to(tmp_path / "Archive" / "2026" / "Talismanic")
    with study.serve() as client:
        study.run()
        study.sessions(client, expect=2)
        study.assert_healthy()
        assert star in study.starred(client), "the move orphaned the researcher's star"


def test_a_renamed_interview_keeps_its_curation_and_is_not_transcribed_again(
    tmp_path: Path, fast_watcher,
) -> None:
    """``Recording 2026-10-02.wav`` renamed to ``p1 sarah.wav`` (row 31)."""
    study = new_study(tmp_path, "Recording 2026-10-02 1433.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        stars = study.quote_ids(client)
        for q in stars:
            study.star(client, q)
        (study.folder / "Recording 2026-10-02 1433.wav").rename(study.folder / "p1 sarah.wav")
        study.run()
        sessions = study.sessions(client, expect=2)
        study.assert_healthy()
        assert set(stars) <= study.starred(client), "a renamed interview lost its stars"
        files = {f["filename"] for s in sessions for f in s.get("source_files", [])}
        assert "p1 sarah.wav" in files, f"the report still points at the old name: {files}"
        assert "Recording 2026-10-02 1433.wav" not in files, f"a stale row survived: {files}"
    assert study.transcribed[1] == [], "a renamed interview was transcribed again"


def test_a_copy_is_an_independent_duplicate(tmp_path: Path, fast_watcher) -> None:
    """``design-project-identity.md`` §9: the copy opens with the curation it
    was copied with, and from then on the two are unrelated."""
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        first, second = study.quote_ids(client)[:2]
        study.star(client, first)
    copy = study.copy_to(tmp_path / "Studies" / "Talismanic copy")
    with copy.serve() as client:
        copy.sessions(client, expect=2)
        copy.assert_healthy()
        assert first in copy.starred(client), "the copy lost the curation it carries"
        copy.star(client, second)
    with study.serve() as client:
        study.sessions(client, expect=2)
        study.assert_healthy()
        assert study.starred(client) == {first}, "the copy's star reached the original"


def test_interviews_filed_into_a_subfolder_keep_everything(tmp_path: Path, fast_watcher) -> None:
    """A researcher tidies Round 1 into its own folder before Round 2 arrives."""
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        stars = study.quote_ids(client)[:2]
        for q in stars:
            study.star(client, q)
        (study.folder / "Round 1").mkdir()
        for name in ("Interview 1.wav", "Interview 2.wav"):
            (study.folder / name).rename(study.folder / "Round 1" / name)
        study.add_recording("Interview 3.wav")
        study.run()
        sessions = study.sessions(client, expect=3)
        study.assert_healthy()
        assert set(stars) <= study.starred(client), "filing interviews into a folder lost stars"
        paths = {f["path"] for s in sessions for f in s.get("source_files", [])}
        assert any("Round 1" in p for p in paths), f"the report still points at the old place: {paths}"
    assert study.transcribed[1] == ["Interview 3.wav"]


def test_re_analyse_after_a_rename_keeps_when_the_interview_happened(
    tmp_path: Path, fast_watcher,
) -> None:
    """Zoom names a recording with its own clock; the researcher renames it,
    then re-analyses. The new name carries no date, so the re-run alone could
    only read the file's save time. The start crosses the reset by content."""
    study = new_study(tmp_path, "GMT20261002-133312_Recording.wav", "Interview 2.wav")
    with study.serve() as client:
        study.run()
        before = {s["session_id"]: s["session_date"] for s in study.sessions(client, expect=2)}
        (study.folder / "GMT20261002-133312_Recording.wav").rename(study.folder / "p1 sarah.wav")
        study.run(clean=True)
        after = {s["session_id"]: s["session_date"] for s in study.sessions(client, expect=2)}
    assert before["s1"].startswith("2026-10-02T13:33:12"), before
    assert after["s1"] == before["s1"], "a Re-analyse after a rename lost the interview's date"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Re-analyse under a live server moves the output folder the server holds open; "
    "Windows refuses the move (as for test_re_analyse_is_a_deliberate_reset…)",
)
def test_a_partial_re_analyse_replaces_the_report_and_analyse_finishes_it(
    tmp_path: Path, fast_watcher,
) -> None:
    """Ruled 23 Oct 2026, through the real pipeline: a Re-analyse with a session
    failed is still a fresh start, so it replaces the report (its star goes,
    as the Re-analyse sheet said). The ordinary Analyse then finishes it,
    transcribing only the session that failed, and curation made on the fresh
    report survives it. No plain run replaces a report."""
    from bristlenose.events import CauseCategoryEnum
    from bristlenose.utils import output_backup

    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav", "Interview 3.wav")
    out = study.folder / "bristlenose-output"
    with study.serve() as client:
        study.run()
        old_star = study.quote_ids(client)[0]
        study.star(client, old_star)

        study.run(clean=True, fail={"Interview 3.wav": CauseCategoryEnum.NETWORK})
        assert "Your previous report is still here" not in study.last_output
        study.sessions(client, expect=2)
        assert old_star not in study.starred(client), "a fresh start kept the old curation"
        new_star = study.quote_ids(client)[-1]
        study.star(client, new_star)

        study.run()
        assert study.transcribed[2] == ["Interview 3.wav"], (
            "Analyse paid again for sessions the fresh start had finished"
        )
        study.sessions(client, expect=3)
        assert new_star in study.starred(client), "Analyse lost curation on the fresh report"
        study.assert_healthy()
    assert not output_backup.failed_path_for(out).exists()
    assert not output_backup.backup_path_for(out).exists()
