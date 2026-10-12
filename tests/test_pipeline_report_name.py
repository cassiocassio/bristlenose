"""A renamed project leaves one report — through the real ``Pipeline.run``.

Harness: ``test_pipeline_platform_transcripts``. Measured red 12 Oct 2026
(lifecycle handoff §1.2 P8).
"""

from __future__ import annotations

from pathlib import Path

from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline


def _one(d: Path, _i: int):
    return [audio_session(d, 1, "bare")]


class TestProjectName:
    def test_a_renamed_project_leaves_one_report(self, tmp_path: Path) -> None:
        """Measured 12 Oct 2026: three ``*-report.html`` after two renames."""
        run_pipeline(tmp_path, _one, project_name="Talismanic")
        h = run_pipeline(tmp_path, _one, project_name="Talismanic study")
        reports = sorted(p.name for p in h.output_dir.glob("bristlenose-*-report.*"))
        assert reports == [
            "bristlenose-talismanic-study-report.html",
            "bristlenose-talismanic-study-report.md",
        ]


