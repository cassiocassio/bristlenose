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
    # Slice C: Whisper preflight checks settings.no_fetch — opt out so the
    # test reaches the real-failure path (transcribe stage), not the
    # preflight-abort path.
    settings.no_fetch = False

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
        # Preflights are globally bypassed via BRISTLENOSE_SKIP_PREFLIGHT=1
        # in tests/conftest.py — no need to patch each one individually.
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


# ---------------------------------------------------------------------------
# Stage emission honesty (A4 Fix 5) — fallback paths must NOT mask LLM
# failure. The stage returns fallback content for the renderer, but the
# StageOutcome records the LLM exception so the orchestrator can abandon.
# ---------------------------------------------------------------------------


def _make_pii_clean_transcript(participant_id: str):
    """Build a minimal PiiCleanTranscript for unit-testing stages."""
    from bristlenose.models import (
        PiiCleanTranscript,
        SpeakerRole,
        TranscriptSegment,
    )

    return PiiCleanTranscript(
        participant_id=participant_id,
        session_id=f"s-{participant_id}",
        source_file=f"{participant_id}.txt",
        session_date=datetime.now(timezone.utc),
        duration_seconds=60.0,
        segments=[
            TranscriptSegment(
                segment_index=0,
                start_time=0.0,
                end_time=10.0,
                text=f"Test from {participant_id}",
                speaker_role=SpeakerRole.PARTICIPANT,
            ),
        ],
    )


def _make_quote(participant_id: str, text: str, qtype=None):
    """Build a minimal ExtractedQuote for unit-testing stages 10/11."""
    from bristlenose.models import (
        EmotionalTone,
        ExtractedQuote,
        JourneyStage,
        QuoteIntent,
        QuoteType,
    )

    return ExtractedQuote(
        session_id=f"s-{participant_id}",
        participant_id=participant_id,
        start_timecode=0.0,
        end_timecode=5.0,
        text=text,
        verbatim_excerpt=text,
        topic_label="general",
        quote_type=qtype or QuoteType.SCREEN_SPECIFIC,
        researcher_context="",
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
        journey_stage=JourneyStage.OTHER,
    )


def test_s08_emits_stage_failure_when_llm_raises() -> None:
    """A failing LLM call at s08's call site must record per-session
    StageFailure entries on the outcome — not just silently return an
    empty SessionTopicMap. The orchestrator reads outcome.failed to fire
    the abandon predicate; if the stage hid the failures, abandon never
    fires and the cache poisons."""
    from unittest.mock import AsyncMock

    from bristlenose.stages.s08_topic_segmentation import segment_topics

    transcripts = [_make_pii_clean_transcript(f"p{i}") for i in range(1, 4)]
    mock_client = AsyncMock()
    mock_client.provider = "anthropic"
    mock_client.analyze = AsyncMock(
        side_effect=RuntimeError("Anthropic 429 rate limit"),
    )

    topic_maps, outcome = asyncio.run(
        segment_topics(transcripts, mock_client, concurrency=1),
    )

    # Stage still returned per-session SessionTopicMap objects (empty
    # boundaries) so downstream stages have structured input.
    assert len(topic_maps) == 3
    # The honest outcome: 3 attempts, 0 successes, 3 explicit failures.
    assert outcome.attempted == 3
    # Note: after _FAIL_THRESHOLD (3) consecutive failures the stage stops.
    # With concurrency=1 and 3 sessions, all 3 see the failure but only the
    # last is the threshold trigger — all 3 are recorded.
    assert outcome.succeeded == 0
    assert len(outcome.failed) == 3
    # cause.category is inferred from the substring matcher — QUOTA for "429".
    assert all(
        f.cause.category == CauseCategoryEnum.QUOTA for f in outcome.failed
    )
    # Privacy contract — no raw exception text in the persisted message.
    assert all("rate limit" not in (f.cause.message or "") for f in outcome.failed)
    # But the structured fields are populated for diagnostic context.
    assert all(f.cause.stage == "topic_segmentation" for f in outcome.failed)
    assert all(f.cause.provider == "anthropic" for f in outcome.failed)


def test_s10_emits_stage_failure_before_fallback_runs() -> None:
    """When cluster_by_screen's LLM call raises, the stage:
    1. Records the failure in outcome.failed BEFORE the fallback fires
    2. Returns the non-empty fallback clustering for downstream rendering
    3. Reports succeeded=0 so the orchestrator can abandon

    This is the Pass 3 lock: a degraded fallback report that LOOKS real is
    worse than honest abandon. The stage's emission must NOT be hidden by
    the fact that the function returns a non-empty list.
    """
    from unittest.mock import AsyncMock

    from bristlenose.stages.s10_quote_clustering import cluster_by_screen

    quotes = [_make_quote(f"p{i}", f"quote {i}") for i in range(1, 4)]
    mock_client = AsyncMock()
    mock_client.provider = "anthropic"
    mock_client.analyze = AsyncMock(side_effect=RuntimeError("500 Internal Server Error"))

    clusters, outcome = asyncio.run(cluster_by_screen(quotes, mock_client))

    # Fallback produced non-empty result (clusters by topic_label).
    assert len(clusters) > 0
    # But the honest outcome reports the LLM failure.
    assert outcome.attempted == 1
    assert outcome.succeeded == 0
    assert len(outcome.failed) == 1
    assert outcome.failed[0].cause.category == CauseCategoryEnum.API_SERVER
    assert outcome.failed[0].cause.stage == "cluster_and_group"
    assert outcome.failed[0].cause.provider == "anthropic"
    # Privacy: raw exception text not leaked.
    assert "500" not in (outcome.failed[0].cause.message or "")  # category, not message
    assert "Internal Server Error" not in (outcome.failed[0].cause.message or "")


def test_s11_emits_stage_failure_before_fallback_runs() -> None:
    """Same invariant for s11 group_by_theme: emit on the outcome BEFORE
    fallback runs. The abandon-check above the call site needs
    succeeded=0 on the rollup; if the outcome only sees successes
    (post-fallback), the predicate never fires."""
    from unittest.mock import AsyncMock

    from bristlenose.models import QuoteType
    from bristlenose.stages.s11_thematic_grouping import group_by_theme

    quotes = [
        _make_quote(f"p{i}", f"quote {i}", QuoteType.GENERAL_CONTEXT)
        for i in range(1, 4)
    ]
    mock_client = AsyncMock()
    mock_client.provider = "openai"
    mock_client.analyze = AsyncMock(side_effect=RuntimeError("invalid api key 401"))

    themes, outcome = asyncio.run(group_by_theme(quotes, mock_client))

    assert len(themes) > 0  # fallback produced non-empty result
    assert outcome.attempted == 1
    assert outcome.succeeded == 0
    assert len(outcome.failed) == 1
    assert outcome.failed[0].cause.category == CauseCategoryEnum.AUTH
    assert outcome.failed[0].cause.stage == "cluster_and_group"
    assert outcome.failed[0].cause.provider == "openai"


def test_run_analysis_only_abandons_at_s08_for_quota_failure(tmp_path: Path) -> None:
    """`bristlenose analyze` with a quota-exhausted key: every topic-seg call
    raises QUOTA. The pipeline must abandon at s08 (gating s09 entry) so no
    quote-extraction LLM calls fire. This is the Pass-3 acceptance criterion
    for the analyze path."""
    from unittest.mock import AsyncMock, patch

    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()
    # Two minimal .txt transcripts in the canonical format that
    # load_transcripts_from_dir() expects:
    #   `# Transcript: s1` header + `[MM:SS] [p1] text` lines.
    (transcripts_dir / "s1.txt").write_text(
        "# Transcript: s1\n"
        "# Source: s1.wav\n"
        "# Date: 2026-05-12\n"
        "# Duration: 00:00:10\n\n"
        "[00:00] [m1] Hello.\n"
        "[00:05] [p1] Hi there.\n",
        encoding="utf-8",
    )
    (transcripts_dir / "s2.txt").write_text(
        "# Transcript: s2\n"
        "# Source: s2.wav\n"
        "# Date: 2026-05-12\n"
        "# Duration: 00:00:10\n\n"
        "[00:00] [m1] Hello again.\n"
        "[00:05] [p2] Nice to meet you.\n",
        encoding="utf-8",
    )

    settings = MagicMock()
    settings.project_name = "test-quota-abandon"
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-sonnet-4-5-20250929"
    settings.anthropic_api_key = "sk-fake"
    settings.openai_api_key = None
    settings.google_api_key = None
    settings.azure_api_key = None
    settings.azure_endpoint = None
    settings.azure_deployment = None
    settings.write_intermediate = True
    settings.llm_concurrency = 1
    settings.min_quote_words = 3
    settings.color_scheme = "default"
    settings.pii_enabled = False

    pipeline = Pipeline(settings, skip_confirm=True)
    output_dir = tmp_path / "output"

    async def _failing_analyze(**_kw):
        raise RuntimeError("Anthropic 429 rate limit exceeded — credit exhausted")

    def _llm_init(_settings):
        client = AsyncMock()
        client.provider = "anthropic"
        client.tracker = MagicMock(input_tokens=0, output_tokens=0, calls=0)
        client.analyze = AsyncMock(side_effect=_failing_analyze)
        return client

    # `run_analysis_only` does `from bristlenose.llm.client import LLMClient`
    # inside the function body, so patch the source module.
    with patch("bristlenose.llm.client.LLMClient", side_effect=_llm_init):
        with pytest.raises(PipelineAbandonedError) as exc_info:
            asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))

    exc = exc_info.value
    assert exc.cause.category == CauseCategoryEnum.QUOTA, (
        f"expected QUOTA, got {exc.cause.category}"
    )
    # Summary captures s08 failures; s09/s10/s11 untouched. summary.quotes
    # is None because the abandon-check at s08 fires BEFORE the s09 outcome
    # rollup populates `self._summary.quotes` — the proxy for "s09 never
    # entered" is the absence of that field on the abandoned summary.
    assert exc.summary.topics is not None
    assert exc.summary.topics.attempted >= 2
    assert exc.summary.topics.succeeded == 0
    assert exc.summary.quotes is None
    assert exc.summary.themes is None
    # No report on disk — abandon before render.
    report_html = output_dir / "bristlenose-test-quota-abandon-report.html"
    assert not report_html.exists()
