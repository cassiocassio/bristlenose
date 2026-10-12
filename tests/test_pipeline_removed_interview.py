"""A removed interview leaves nothing behind — through the real ``Pipeline.run``.

Harness: ``test_pipeline_platform_transcripts``. Measured red 12 Oct 2026
(lifecycle handoff §1.2 P5).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from bristlenose.logging import release_log_file
from bristlenose.pipeline import prune_stale_session_files
from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline


def _two_then_one(d: Path, i: int):
    both = [audio_session(d, 1, "alpha"), audio_session(d, 2, "beta")]
    return both if i == 0 else both[:1]


def _artefacts(out: Path, sid: str) -> list[Path]:
    return [
        out / "transcripts-raw" / f"{sid}.txt",
        out / "transcripts-raw" / f"{sid}.md",
        out / "sessions" / f"transcript_{sid}.html",
        out / ".bristlenose" / "intermediate" / "speaker-info" / f"{sid}.json",
    ]


class TestRemovedInterview:
    def test_a_removed_interview_leaves_no_artefacts(self, tmp_path: Path) -> None:
        h = run_pipeline(tmp_path, _two_then_one, runs=2)
        out = h.output_dir
        assert all(p.exists() for p in _artefacts(out, "s1")), "control: s1 is still there"
        leftovers = sorted(str(p.relative_to(out)) for p in _artefacts(out, "s2") if p.exists())
        assert leftovers == []

    def test_a_removed_interview_does_not_come_back_through_serve(
        self, tmp_path: Path,
    ) -> None:
        """The user-visible symptom: the importer rebuilds a session from any
        transcript header it finds, so a stale ``s2.txt`` resurrected the
        deleted interview in the report (measured 12 Oct 2026)."""
        from bristlenose.server.db import create_session_factory, get_engine, init_db
        from bristlenose.server.importer import import_project
        from bristlenose.server.models import Session as SessionModel

        h = run_pipeline(tmp_path, _two_then_one, runs=2)
        project = tmp_path / "project"
        project.mkdir()
        # The run's log handler holds bristlenose.log open, and Windows will
        # not move a folder with an open file in it (WinError 32).
        release_log_file()
        shutil.move(str(h.output_dir), str(project / "bristlenose-output"))

        engine = get_engine("sqlite://")
        init_db(engine)
        db = create_session_factory(engine)()
        try:
            import_project(db, project)
            assert sorted(s.session_id for s in db.query(SessionModel)) == ["s1"]
        finally:
            db.close()




class TestPruneHelper:
    def test_removes_only_session_files_of_absent_sessions(self, tmp_path: Path) -> None:
        """``s1`` is a prefix of ``s12``; a README is not a session; the
        registry and the stage caches belong to their own writers."""
        files = [
            "transcripts-raw/s1.txt", "transcripts-raw/s2.txt", "transcripts-raw/s2.md",
            "transcripts-raw/s12.txt", "transcripts-raw/README.txt",
            "transcripts-cooked/s2.txt",
            "sessions/transcript_s1.html", "sessions/transcript_s2.html",
            "assets/thumbnails/s2.jpg", "assets/thumbnails/s2.jpg.src",
            ".bristlenose/intermediate/speaker-info/s2.json",
            ".bristlenose/intermediate/scene-colours/s2.json",
            ".bristlenose/temp/s2_extracted.wav",
            ".bristlenose/sessions.json",
            ".bristlenose/intermediate/session_segments.json",
        ]
        for rel in files:
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text("x", encoding="utf-8")

        removed = prune_stale_session_files(tmp_path, ["s1", "s12"])

        assert sorted(p.relative_to(tmp_path).as_posix() for p in removed) == [
            ".bristlenose/intermediate/scene-colours/s2.json",
            ".bristlenose/intermediate/speaker-info/s2.json",
            ".bristlenose/temp/s2_extracted.wav",
            "assets/thumbnails/s2.jpg", "assets/thumbnails/s2.jpg.src",
            "sessions/transcript_s2.html",
            "transcripts-cooked/s2.txt",
            "transcripts-raw/s2.md", "transcripts-raw/s2.txt",
        ]
        kept = sorted(
            p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()
        )
        assert kept == [
            ".bristlenose/intermediate/session_segments.json",
            ".bristlenose/sessions.json",
            "sessions/transcript_s1.html",
            "transcripts-raw/README.txt", "transcripts-raw/s1.txt", "transcripts-raw/s12.txt",
        ]

    def test_an_output_folder_with_no_session_dirs_is_fine(self, tmp_path: Path) -> None:
        assert prune_stale_session_files(tmp_path, ["s1"]) == []
