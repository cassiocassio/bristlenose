"""A session a stage FAILED on must never be recorded as complete.

The manifest's per-session records are not bookkeeping — they are the work
list for the next run. ``get_completed_session_ids`` reads them back and drops
those sessions, so a failed session written as COMPLETE is never retried, and
the per-session rollup goes on counting it as a success. The honest
"9 of 10, one failed" record is overwritten by a clean 10/10 on the very next
run, and the loss stops being visible anywhere.

WHY THIS FILE EXISTS. The rule lived inline at two call sites sixty lines
apart: s08 had it (with the reasoning in a comment), s09 did not, and nothing
compared them. Measured on the FOSSDA run of 30 Apr 2026 — s3's quote
extraction timed out (3 x 600s), recorded a StageFailure, and was written to
the manifest as ``quote_extraction -> s3: complete`` in the same breath.

The whole-stage guards from 1e1ec118 ("stage-cache honesty") do NOT cover this
and cannot: when a single session of a batch fails, the intermediate JSON is
non-empty and ``succeeded == 0`` is false, so both pass. Nor does
``assert_sessions_accounted`` — the arithmetic is honest (10 == 9 + 1) while
the manifest says otherwise. Two records disagree, and the one driving resume
is the wrong one. Nothing mechanical was watching, which is what this file is.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.events import Cause, CauseCategoryEnum, StageFailure, StageOutcome
from bristlenose.manifest import (
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
    create_manifest,
    get_completed_session_ids,
    load_manifest,
    mark_stage_running,
)
from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.pipeline import Pipeline, _mark_sessions_complete_except_failed


def _failure(sid: str, stage: str) -> StageFailure:
    return StageFailure(
        session_id=sid,
        cause=Cause(
            category=CauseCategoryEnum.API_REQUEST,
            message="Timeout",
            stage=stage,
            session_id=sid,
        ),
    )


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------


class TestMarkSessionsCompleteExceptFailed:
    """Unit-level: the shared rule both per-session LLM stages route through."""

    def _manifest(self):
        m = create_manifest("test", "0.0.0")
        mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
        return m

    def test_a_failed_session_is_not_marked_complete(self) -> None:
        m = self._manifest()
        outcome = StageOutcome(
            attempted=3, succeeded=2,
            failed=[_failure("s2", "quote_extraction")],
        )

        skipped = _mark_sessions_complete_except_failed(
            m, STAGE_QUOTE_EXTRACTION, ["s1", "s2", "s3"], outcome,
        )

        assert skipped == {"s2"}
        # Both directions matter. Asserting only that s2 is absent would pass
        # on a loop that marks nothing at all.
        assert get_completed_session_ids(m, STAGE_QUOTE_EXTRACTION) == {"s1", "s3"}

    def test_a_clean_run_marks_every_session(self) -> None:
        m = self._manifest()
        outcome = StageOutcome(attempted=3, succeeded=3)

        skipped = _mark_sessions_complete_except_failed(
            m, STAGE_QUOTE_EXTRACTION, ["s1", "s2", "s3"], outcome,
        )

        assert skipped == set()
        assert get_completed_session_ids(m, STAGE_QUOTE_EXTRACTION) == {
            "s1", "s2", "s3",
        }

    def test_a_failure_with_no_session_id_excludes_nothing(self) -> None:
        """``StageFailure.session_id`` is optional. A stage-level failure that
        names no session must not silently swallow a session's completion —
        ``None`` is not a session id, and a set holding it would match none."""
        m = self._manifest()
        outcome = StageOutcome(
            attempted=2, succeeded=2,
            failed=[StageFailure(cause=Cause(
                category=CauseCategoryEnum.UNKNOWN,
                message="stage-level",
                stage="quote_extraction",
            ))],
        )

        skipped = _mark_sessions_complete_except_failed(
            m, STAGE_QUOTE_EXTRACTION, ["s1", "s2"], outcome,
        )

        assert skipped == set()
        assert get_completed_session_ids(m, STAGE_QUOTE_EXTRACTION) == {"s1", "s2"}


# ---------------------------------------------------------------------------
# The wiring — the half a unit test cannot see
# ---------------------------------------------------------------------------
#
# A rule nothing calls is the failure mode this bug already demonstrated once.
# These drive the real `Pipeline.run` call sites and read the manifest off
# disk, so they fail if either stage stops routing through the rule.


def _sessions(input_dir: Path, n: int) -> list[InputSession]:
    out = []
    for i in range(1, n + 1):
        media = input_dir / f"rec{i}.wav"
        media.write_bytes(b"fake")
        out.append(InputSession(
            session_id=f"s{i}",
            session_number=i,
            participant_id=f"p{i}",
            participant_number=i,
            session_date=datetime.now(timezone.utc),
            files=[InputFile(
                path=media,
                file_type=FileType.AUDIO,
                created_at=datetime.now(timezone.utc),
                size_bytes=4,
                duration_seconds=60.0,
            )],
            audio_path=media,
        ))
    return out


def _segment(i: int) -> TranscriptSegment:
    return TranscriptSegment(
        segment_index=0,
        start_time=0.0,
        end_time=30.0,
        text=f"I could not find the checkout button, session {i}.",
        speaker_role=SpeakerRole.PARTICIPANT,
        speaker_code=f"p{i}",
    )


def _run_pipeline_with_one_failing_session(
    tmp_path: Path,
    *,
    failing_stage: str,
    failing_sid: str = "s2",
    n: int = 3,
) -> Path:
    """Drive the real ``Pipeline.run`` where exactly one session fails at
    ``failing_stage`` ('s08' or 's09'). Returns the output dir.

    Seams are the stage functions, matching test_pipeline_abandon.py's choice
    to patch the stage rather than the backend: the contract under test is the
    orchestrator's per-session manifest marking, not the LLM wiring.
    """
    from bristlenose.models import PiiCleanTranscript, SessionTopicMap

    settings = MagicMock()
    settings.project_name = "guard-test"
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-sonnet-4-6"
    settings.skip_transcription = False
    settings.write_intermediate = True
    settings.llm_concurrency = 1
    settings.min_quote_words = 3
    settings.color_scheme = "default"
    settings.pii_score_threshold = 0.5
    settings.pii_llm_pass = False
    settings.pii_custom_names = None
    settings.no_fetch = False

    pipeline = Pipeline(settings)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    sessions = _sessions(input_dir, n)
    sids = [s.session_id for s in sessions]

    async def _fake_gather(_self, _sessions, **_kw):
        segs = {s.session_id: [_segment(i)] for i, s in enumerate(_sessions, 1)}
        return segs, StageOutcome(attempted=len(_sessions), succeeded=len(_sessions))

    async def _passthrough(sess, _tmp, **_kw):
        return sess

    def _fake_remove_pii(transcripts, *_a, **_kw):
        # s07's real contract: FullTranscript in, PiiCleanTranscript out.
        clean = [
            PiiCleanTranscript(**t.model_dump(), pii_entities_found=0)
            for t in transcripts
        ]
        return clean, []

    async def _fake_segment_topics(transcripts, *_a, **_kw):
        maps = [
            SessionTopicMap(session_id=t.session_id,
                            participant_id=t.participant_id,
                            boundaries=[])
            for t in transcripts
        ]
        if failing_stage == "s08":
            return maps, StageOutcome(
                attempted=len(maps), succeeded=len(maps) - 1,
                failed=[_failure(failing_sid, "topic_segmentation")],
            )
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _fake_extract_quotes(transcripts, *_a, **_kw):
        assert all(isinstance(t, PiiCleanTranscript) for t in transcripts)
        if failing_stage == "s09":
            return [], StageOutcome(
                attempted=len(transcripts), succeeded=len(transcripts) - 1,
                failed=[_failure(failing_sid, "quote_extraction")],
            )
        return [], StageOutcome(
            attempted=len(transcripts), succeeded=len(transcripts),
        )

    async def _fake_cluster(quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    async def _fake_group(quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch(
            "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
            new=_passthrough,
        ),
        patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
        patch("bristlenose.stages.s07_pii_removal.remove_pii", new=_fake_remove_pii),
        patch(
            "bristlenose.stages.s08_topic_segmentation.segment_topics",
            new=_fake_segment_topics,
        ),
        patch(
            "bristlenose.stages.s09_quote_extraction.extract_quotes",
            new=_fake_extract_quotes,
        ),
        patch(
            "bristlenose.stages.s10_quote_clustering.cluster_by_screen",
            new=_fake_cluster,
        ),
        patch(
            "bristlenose.stages.s11_thematic_grouping.group_by_theme",
            new=_fake_group,
        ),
        patch("bristlenose.llm.client.LLMClient", MagicMock()),
    ):
        asyncio.run(pipeline.run(input_dir, output_dir))

    assert sids  # sanity: the fixture built sessions at all
    return output_dir


@pytest.mark.parametrize(
    ("failing_stage", "stage_key"),
    [("s09", STAGE_QUOTE_EXTRACTION), ("s08", STAGE_TOPIC_SEGMENTATION)],
)
def test_failed_session_is_absent_from_the_manifest(
    tmp_path: Path, failing_stage: str, stage_key: str,
) -> None:
    """The orchestrator must not cache a session the stage failed on.

    s09 is the case that shipped broken; s08 is its twin, which had the guard
    and no test — deleting one would have been silent.
    """
    output_dir = _run_pipeline_with_one_failing_session(
        tmp_path, failing_stage=failing_stage,
    )

    manifest = load_manifest(output_dir)
    assert manifest is not None
    completed = get_completed_session_ids(manifest, stage_key)

    assert "s2" not in completed, (
        f"{failing_stage} recorded a FAILED session as complete — it will "
        "never be retried, and the next run will count it as a success"
    )
    # The other two must still be cached, or the guard has simply stopped
    # the stage caching anything and resume is broken in the other direction.
    assert completed == {"s1", "s3"}


def test_a_clean_run_still_caches_every_session(tmp_path: Path) -> None:
    """The guard must not cost a clean run its cache."""
    output_dir = _run_pipeline_with_one_failing_session(
        tmp_path, failing_stage="none",
    )

    manifest = load_manifest(output_dir)
    assert manifest is not None
    for stage_key in (STAGE_TOPIC_SEGMENTATION, STAGE_QUOTE_EXTRACTION):
        assert get_completed_session_ids(manifest, stage_key) == {"s1", "s2", "s3"}
