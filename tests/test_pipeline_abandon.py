"""Tests for the pipeline abandon path — empty-data runs raise instead of
rendering a fake-empty report.

These tests cover the orchestrator-level mechanism in four layers:

1. ``_dominant_cause`` (pure helper) — picks the right Cause from a list of
   per-session failures.
2. ``run_lifecycle`` integration — when a ``PipelineAbandonedError`` escapes
   the context body, the events log gains a ``run_failed`` line whose
   ``summary`` matches the exception payload and whose ``cause`` is the
   one carried by the exception (not categorised from ``str(exc)``).
3. ``s05_transcribe`` outcome surfacing — every session-level failure
   becomes a ``StageFailure`` in the returned outcome.
4. ``Pipeline.run`` orchestration — when ``_gather_all_segments`` reports
   every session failed, the orchestrator raises ``PipelineAbandonedError``
   with a ``MISSING_BINARY`` cause before stage 6, so no fake-empty report
   is rendered (the bar repro from 7 May 2026).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    PipelineAbandonedError,
    PipelineSummary,
    RunFailedEvent,
    StageFailure,
    StageOutcome,
    read_events,
)
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.pipeline import Pipeline, _dominant_cause
from bristlenose.run_lifecycle import (
    _restore_signal_handlers,
    run_lifecycle,
)

# ---------------------------------------------------------------------------
# _dominant_cause
# ---------------------------------------------------------------------------


def test_dominant_cause_empty_falls_back_to_default() -> None:
    """No failures → synthesise a Cause from default_category + message."""
    cause = _dominant_cause(
        [],
        default_category=CauseCategoryEnum.WHISPER,
        message="all done",
    )
    assert cause.category == CauseCategoryEnum.WHISPER
    assert cause.message == "all done"


def test_dominant_cause_majority_wins() -> None:
    """Most common category among failures wins; message overridden."""
    failures = [
        StageFailure(session_id="s1", cause=Cause(
            category=CauseCategoryEnum.MISSING_BINARY, message="ffmpeg",
        )),
        StageFailure(session_id="s2", cause=Cause(
            category=CauseCategoryEnum.MISSING_BINARY, message="ffmpeg",
        )),
        StageFailure(session_id="s3", cause=Cause(
            category=CauseCategoryEnum.NETWORK, message="timeout",
        )),
    ]
    cause = _dominant_cause(
        failures,
        default_category=CauseCategoryEnum.UNKNOWN,
        message="all sessions failed",
    )
    assert cause.category == CauseCategoryEnum.MISSING_BINARY
    # The chosen Cause's stage/session_id is preserved; only message overridden.
    assert cause.message == "all sessions failed"


def test_dominant_cause_tie_prefers_non_retryable() -> None:
    """1 AUTH + 1 NETWORK → AUTH wins (priority order)."""
    failures = [
        StageFailure(session_id="s1", cause=Cause(
            category=CauseCategoryEnum.NETWORK, message="net",
        )),
        StageFailure(session_id="s2", cause=Cause(
            category=CauseCategoryEnum.AUTH, message="auth",
        )),
    ]
    cause = _dominant_cause(
        failures,
        default_category=CauseCategoryEnum.UNKNOWN,
        message="all failed",
    )
    assert cause.category == CauseCategoryEnum.AUTH


# ---------------------------------------------------------------------------
# run_lifecycle abandon path
# ---------------------------------------------------------------------------


def test_run_lifecycle_writes_summary_on_abandon(tmp_path: Path) -> None:
    """PipelineAbandonedError → run_failed with the exception's summary."""
    summary = PipelineSummary(
        transcripts=StageOutcome(
            attempted=3,
            succeeded=0,
            failed=[
                StageFailure(
                    session_id=f"s{i}",
                    cause=Cause(
                        category=CauseCategoryEnum.MISSING_BINARY,
                        message="[Errno 2] No such file: 'ffmpeg'",
                        stage="s05_transcribe",
                        session_id=f"s{i}",
                    ),
                )
                for i in range(1, 4)
            ],
        ),
    )
    abandon_cause = Cause(
        category=CauseCategoryEnum.MISSING_BINARY,
        message="All sessions failed to transcribe.",
    )

    try:
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise PipelineAbandonedError(cause=abandon_cause, summary=summary)
    except PipelineAbandonedError:
        pass
    finally:
        _restore_signal_handlers()

    events = read_events(tmp_path / ".bristlenose" / "pipeline-events.jsonl")
    failed_events = [e for e in events if isinstance(e, RunFailedEvent)]
    assert len(failed_events) == 1, events
    failed = failed_events[0]
    assert failed.cause is not None
    assert failed.cause.category == CauseCategoryEnum.MISSING_BINARY
    assert failed.cause.message == "All sessions failed to transcribe."
    assert failed.summary is not None
    assert failed.summary.transcripts is not None
    assert failed.summary.transcripts.attempted == 3
    assert failed.summary.transcripts.succeeded == 0
    assert len(failed.summary.transcripts.failed) == 3


def test_run_lifecycle_other_exceptions_still_categorised(tmp_path: Path) -> None:
    """Non-abandon exceptions: cause comes from categorise_exception, not exc."""
    try:
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise FileNotFoundError(2, "No such file or directory", "ffmpeg")
    except FileNotFoundError:
        pass
    finally:
        _restore_signal_handlers()

    events = read_events(tmp_path / ".bristlenose" / "pipeline-events.jsonl")
    failed = next(e for e in events if isinstance(e, RunFailedEvent))
    # categorise_exception now recognises bare-name FileNotFoundError.
    assert failed.cause is not None
    assert failed.cause.category == CauseCategoryEnum.MISSING_BINARY


# ---------------------------------------------------------------------------
# s05_transcribe outcome surfacing
# ---------------------------------------------------------------------------


class _StubSession:
    """Minimal stand-in for InputSession used by transcribe_sessions."""

    def __init__(self, sid: str, audio_path: Path) -> None:
        self.session_id = sid
        self.audio_path = audio_path
        self.has_existing_transcript = False


def test_transcribe_sessions_records_failures(monkeypatch, tmp_path: Path) -> None:
    """Every session-level failure becomes a StageFailure in the outcome."""
    from bristlenose.stages import s05_transcribe

    audio_files = [tmp_path / f"s{i}.wav" for i in range(1, 4)]
    for f in audio_files:
        f.write_bytes(b"fake")

    sessions = [_StubSession(f"s{i}", audio_files[i - 1]) for i in range(1, 4)]

    # Stub the backend factory so all 3 sessions raise FileNotFoundError —
    # mirrors the sandbox-without-ffmpeg case.
    def _fake_init_mlx(_settings):  # noqa: ARG001
        def _t(_path, _settings):  # noqa: ARG001
            raise FileNotFoundError(2, "No such file or directory", "ffmpeg")
        return _t

    monkeypatch.setattr(s05_transcribe, "_init_mlx_backend", _fake_init_mlx)
    monkeypatch.setattr(
        s05_transcribe,
        "_resolve_backend",
        lambda _c, _h: "mlx",  # noqa: ARG005
    )

    settings = type("S", (), {
        "whisper_backend": "mlx",
        "whisper_model": "tiny",
    })()

    results, outcome = s05_transcribe.transcribe_sessions(sessions, settings)

    assert outcome.attempted == 3
    assert outcome.succeeded == 0
    assert len(outcome.failed) == 3
    # Every failure carries the MISSING_BINARY category (categoriser saw a
    # bare-name FileNotFoundError).
    assert all(
        f.cause.category == CauseCategoryEnum.MISSING_BINARY
        for f in outcome.failed
    )
    # session_ids preserved on each failure.
    assert {f.session_id for f in outcome.failed} == {"s1", "s2", "s3"}
    # Results dict still has empty lists for failed sessions (existing contract).
    assert all(results[sid] == [] for sid in ["s1", "s2", "s3"])


# ---------------------------------------------------------------------------
# Pipeline.run orchestration — abandon fires before stage 6
# ---------------------------------------------------------------------------


def test_pipeline_run_abandons_when_all_transcribe_fail(tmp_path: Path) -> None:
    """Bar-repro regression: every session's transcription fails →
    Pipeline.run raises ``PipelineAbandonedError`` before stage 6, and
    no rendered report lands on disk.

    Rebuilds the 7 May 2026 bar scenario at orchestrator level: ingest
    discovers 3 sessions, extract-audio succeeds, but every transcription
    raises a bare-name ``FileNotFoundError`` for ``ffmpeg`` (the mlx-whisper
    sandbox path). The orchestrator must abandon before s06–s12, otherwise
    the user sees a fake-empty "Analysed" report with no diagnostic.
    """
    settings = MagicMock()
    settings.project_name = "test-bar"
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-sonnet-4-5-20250929"
    settings.skip_transcription = False
    settings.write_intermediate = True
    settings.llm_concurrency = 1
    settings.whisper_backend = "mlx"
    settings.whisper_model = "tiny"
    settings.color_scheme = "default"
    settings.pii_score_threshold = 0.5

    pipeline = Pipeline(settings, skip_confirm=True)

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    # Three plausible-looking video sessions (audio_path set so the
    # transcribe stage will attempt them).
    sessions: list[InputSession] = []
    for i in range(1, 4):
        video_path = input_dir / f"vid{i}.mov"
        video_path.write_bytes(b"fake-video")
        audio_path = input_dir / f"vid{i}.wav"
        audio_path.write_bytes(b"fake-audio")
        sess = InputSession(
            session_id=f"s{i}",
            session_number=i,
            participant_id=f"p{i}",
            participant_number=i,
            session_date=datetime.now(timezone.utc),
            files=[InputFile(
                path=video_path,
                file_type=FileType.VIDEO,
                created_at=datetime.now(timezone.utc),
                size_bytes=10,
                duration_seconds=60.0,
            )],
            audio_path=audio_path,
        )
        sessions.append(sess)

    # mlx-whisper-style failure: transcribe_sessions returns an all-failed
    # outcome. Patched directly (rather than via the backend factory) so
    # this test is robust to the underlying transcribe stack — the contract
    # under test is the orchestrator's reaction to an all-failed outcome,
    # not the backend wiring (which `test_transcribe_sessions_records_failures`
    # already covers).
    failures = [
        StageFailure(
            session_id=f"s{i}",
            cause=Cause(
                category=CauseCategoryEnum.MISSING_BINARY,
                message="[Errno 2] No such file: 'ffmpeg'",
                stage="s05_transcribe",
                session_id=f"s{i}",
            ),
        )
        for i in range(1, 4)
    ]

    def _fake_transcribe_sessions(needs, _settings, *, on_progress=None):
        return (
            {s.session_id: [] for s in needs},
            StageOutcome(
                attempted=len(needs), succeeded=0, failed=list(failures),
            ),
        )

    with (
        patch(
            "bristlenose.stages.s05_transcribe.transcribe_sessions",
            new=_fake_transcribe_sessions,
        ),
        patch(
            "bristlenose.stages.s01_ingest.ingest",
            return_value=sessions,
        ),
        # Audio is "already extracted" — extract_audio is a passthrough.
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_async_passthrough,
        ),
    ):
        with pytest.raises(PipelineAbandonedError) as exc_info:
            asyncio.run(pipeline.run(input_dir, output_dir))

    exc = exc_info.value
    assert exc.cause.category == CauseCategoryEnum.MISSING_BINARY, (
        f"expected MISSING_BINARY, got {exc.cause.category}"
    )
    assert exc.summary.transcripts is not None
    assert exc.summary.transcripts.attempted == 3
    assert exc.summary.transcripts.succeeded == 0
    assert len(exc.summary.transcripts.failed) == 3

    # No rendered report should exist on disk — abandon must fire before s12.
    report_html = output_dir / "bristlenose-test-bar-report.html"
    assert not report_html.exists(), (
        "abandon path rendered a report — the silent-skip bug is back"
    )


async def _async_passthrough(sessions, _temp_dir, **_kwargs):
    """Bypass for extract_audio_for_sessions (audio already on disk)."""
    return sessions
