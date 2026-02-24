"""Tests for the session-count safety guard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bristlenose.pipeline import _MAX_SESSIONS_NO_CONFIRM, Pipeline


def _make_pipeline(skip_confirm: bool = False) -> Pipeline:
    """Create a Pipeline with minimal mocked settings."""
    settings = MagicMock()
    settings.project_name = "test"
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-sonnet-4-5-20250929"
    return Pipeline(settings, skip_confirm=skip_confirm)


class TestThresholdConstant:
    def test_value(self) -> None:
        assert _MAX_SESSIONS_NO_CONFIRM == 16


class TestConfirmLargeSessionCount:
    """Tests for Pipeline._confirm_large_session_count."""

    def test_returns_true_when_user_confirms(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline()
        with patch("rich.prompt.Confirm.ask", return_value=True) as mock_ask:
            assert pipeline._confirm_large_session_count(20, tmp_path) is True
            mock_ask.assert_called_once()

    def test_returns_false_when_user_declines(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline()
        with patch("rich.prompt.Confirm.ask", return_value=False) as mock_ask:
            assert pipeline._confirm_large_session_count(20, tmp_path) is False
            mock_ask.assert_called_once()

    def test_prints_session_count(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline()
        with (
            patch("rich.prompt.Confirm.ask", return_value=True),
            patch("bristlenose.pipeline.console") as mock_console,
        ):
            pipeline._confirm_large_session_count(42, tmp_path)
            printed = mock_console.print.call_args[0][0]
            assert "42" in printed


class TestSessionGuardIntegration:
    """Test that the guard fires (or doesn't) based on session count."""

    def _fake_sessions(self, n: int) -> list[MagicMock]:
        sessions = []
        for i in range(n):
            s = MagicMock()
            s.files = [MagicMock(file_type=MagicMock(value="video"))]
            sessions.append(s)
        return sessions

    def test_no_prompt_at_threshold(self, tmp_path: Path) -> None:
        """Exactly 16 sessions should not trigger the prompt."""
        pipeline = _make_pipeline()
        sessions = self._fake_sessions(16)
        with (
            patch("bristlenose.stages.ingest.ingest", return_value=sessions),
            patch.object(pipeline, "_confirm_large_session_count") as mock_confirm,
            patch("bristlenose.pipeline.console"),
            patch("bristlenose.pipeline._print_step"),
            patch("bristlenose.pipeline.mark_stage_running"),
            patch("bristlenose.pipeline.mark_stage_complete"),
            patch("bristlenose.pipeline.write_manifest"),
            patch("bristlenose.pipeline.create_manifest"),
            patch("bristlenose.pipeline.load_manifest", return_value=None),
        ):
            try:
                import asyncio
                asyncio.run(pipeline.run(tmp_path, tmp_path / "out"))
            except Exception:
                pass
            mock_confirm.assert_not_called()

    def test_prompt_above_threshold_user_confirms(self, tmp_path: Path) -> None:
        """17 sessions should trigger the prompt; confirming lets it continue."""
        pipeline = _make_pipeline()
        sessions = self._fake_sessions(17)
        with (
            patch("bristlenose.stages.ingest.ingest", return_value=sessions),
            patch.object(
                pipeline, "_confirm_large_session_count", return_value=True
            ) as mock_confirm,
            patch("bristlenose.pipeline.console"),
            patch("bristlenose.pipeline._print_step"),
            patch("bristlenose.pipeline.mark_stage_running"),
            patch("bristlenose.pipeline.mark_stage_complete"),
            patch("bristlenose.pipeline.write_manifest"),
            patch("bristlenose.pipeline.create_manifest"),
            patch("bristlenose.pipeline.load_manifest", return_value=None),
        ):
            try:
                import asyncio
                asyncio.run(pipeline.run(tmp_path, tmp_path / "out"))
            except Exception:
                pass
            mock_confirm.assert_called_once_with(17, tmp_path)

    def test_prompt_above_threshold_user_declines(self, tmp_path: Path) -> None:
        """17 sessions, user declines — returns empty result."""
        pipeline = _make_pipeline()
        sessions = self._fake_sessions(17)
        with (
            patch("bristlenose.stages.ingest.ingest", return_value=sessions),
            patch.object(
                pipeline, "_confirm_large_session_count", return_value=False
            ),
            patch("bristlenose.pipeline.console"),
            patch("bristlenose.pipeline._print_step"),
            patch("bristlenose.pipeline.mark_stage_running"),
            patch("bristlenose.pipeline.write_manifest"),
            patch("bristlenose.pipeline.create_manifest"),
            patch("bristlenose.pipeline.load_manifest", return_value=None),
        ):
            import asyncio
            result = asyncio.run(pipeline.run(tmp_path, tmp_path / "out"))
            assert result.screen_clusters == []
            assert result.theme_groups == []

    def test_skip_confirm_bypasses_prompt(self, tmp_path: Path) -> None:
        """--yes flag skips the prompt entirely."""
        pipeline = _make_pipeline(skip_confirm=True)
        sessions = self._fake_sessions(20)
        with (
            patch("bristlenose.stages.ingest.ingest", return_value=sessions),
            patch.object(pipeline, "_confirm_large_session_count") as mock_confirm,
            patch("bristlenose.pipeline.console"),
            patch("bristlenose.pipeline._print_step"),
            patch("bristlenose.pipeline.mark_stage_running"),
            patch("bristlenose.pipeline.mark_stage_complete"),
            patch("bristlenose.pipeline.write_manifest"),
            patch("bristlenose.pipeline.create_manifest"),
            patch("bristlenose.pipeline.load_manifest", return_value=None),
        ):
            try:
                import asyncio
                asyncio.run(pipeline.run(tmp_path, tmp_path / "out"))
            except Exception:
                pass
            mock_confirm.assert_not_called()
