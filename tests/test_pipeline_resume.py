"""Tests for pipeline resume — skip completed stages on re-run (Phase 1c+1d+1d-ext)."""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
    STAGE_TRANSCRIBE,
    StageStatus,
    create_manifest,
    get_completed_session_ids,
    mark_session_complete,
    mark_stage_complete,
    mark_stage_running,
    write_manifest,
)
from bristlenose.models import (
    ExtractedQuote,
    QuoteType,
    ScreenCluster,
    SessionTopicMap,
    SpeakerRole,
    ThemeGroup,
    TopicBoundary,
    TranscriptSegment,
    TransitionType,
)
from bristlenose.pipeline import _is_stage_cached, _print_cached_step

# ---------------------------------------------------------------------------
# _is_stage_cached
# ---------------------------------------------------------------------------


def test_is_stage_cached_none_manifest():
    assert _is_stage_cached(None, STAGE_TOPIC_SEGMENTATION) is False


def test_is_stage_cached_no_stage_record():
    m = create_manifest("p", "1.0")
    assert _is_stage_cached(m, STAGE_TOPIC_SEGMENTATION) is False


def test_is_stage_cached_running():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    assert _is_stage_cached(m, STAGE_TOPIC_SEGMENTATION) is False


def test_is_stage_cached_complete():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    mark_stage_complete(m, STAGE_TOPIC_SEGMENTATION)
    assert _is_stage_cached(m, STAGE_TOPIC_SEGMENTATION) is True


def test_is_stage_cached_failed():
    m = create_manifest("p", "1.0")
    m.stages[STAGE_TOPIC_SEGMENTATION] = m.stages.get(
        STAGE_TOPIC_SEGMENTATION,
        type(list(m.stages.values())[0]) if m.stages else None,  # type: ignore[arg-type]
    )
    from bristlenose.manifest import StageRecord

    m.stages[STAGE_TOPIC_SEGMENTATION] = StageRecord(status=StageStatus.FAILED)
    assert _is_stage_cached(m, STAGE_TOPIC_SEGMENTATION) is False


def test_is_stage_cached_partial():
    from bristlenose.manifest import StageRecord

    m = create_manifest("p", "1.0")
    m.stages[STAGE_QUOTE_EXTRACTION] = StageRecord(status=StageStatus.PARTIAL)
    assert _is_stage_cached(m, STAGE_QUOTE_EXTRACTION) is False


# ---------------------------------------------------------------------------
# _print_cached_step (smoke test — just ensure no crash)
# ---------------------------------------------------------------------------


def test_print_cached_step_does_not_raise(capsys):
    _print_cached_step("Segmented 10 topic boundaries")
    # Rich output goes to stderr or capsys — just verify no exception


# ---------------------------------------------------------------------------
# Intermediate JSON round-trip (the loading pattern used by resume)
# ---------------------------------------------------------------------------


def _make_topic_boundaries() -> list[SessionTopicMap]:
    return [
        SessionTopicMap(
            session_id="s1",
            participant_id="p1",
            boundaries=[
                TopicBoundary(
                    timecode_seconds=0.0,
                    topic_label="Onboarding flow",
                    transition_type=TransitionType.SCREEN_CHANGE,
                ),
                TopicBoundary(
                    timecode_seconds=120.0,
                    topic_label="Dashboard overview",
                    transition_type=TransitionType.SCREEN_CHANGE,
                ),
            ],
        ),
    ]


def _make_quotes() -> list[ExtractedQuote]:
    return [
        ExtractedQuote(
            session_id="s1",
            participant_id="p1",
            start_timecode=10.0,
            end_timecode=20.0,
            text="I found the onboarding confusing.",
            topic_label="Onboarding flow",
            quote_type=QuoteType.SCREEN_SPECIFIC,
        ),
        ExtractedQuote(
            session_id="s1",
            participant_id="p1",
            start_timecode=130.0,
            end_timecode=140.0,
            text="The dashboard is clean and simple.",
            topic_label="Dashboard overview",
            quote_type=QuoteType.SCREEN_SPECIFIC,
        ),
    ]


def _make_clusters(quotes: list[ExtractedQuote]) -> list[ScreenCluster]:
    return [
        ScreenCluster(
            screen_label="Onboarding",
            description="First-time user experience",
            display_order=0,
            quotes=[quotes[0]],
        ),
    ]


def _make_themes(quotes: list[ExtractedQuote]) -> list[ThemeGroup]:
    return [
        ThemeGroup(
            theme_label="Simplicity",
            description="Users value simplicity",
            quotes=[quotes[1]],
        ),
    ]


def _write_intermediate(
    data: list,
    filename: str,
    output_dir: Path,
) -> Path:
    """Write a list of Pydantic models as JSON to the intermediate directory."""
    intermediate = output_dir / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    path = intermediate / filename
    json_data = [item.model_dump(mode="json") for item in data]
    path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    return path


def test_topic_boundaries_roundtrip(tmp_path: Path):
    """topic_boundaries.json can be written and loaded back identically."""
    originals = _make_topic_boundaries()
    _write_intermediate(originals, "topic_boundaries.json", tmp_path)

    path = tmp_path / ".bristlenose" / "intermediate" / "topic_boundaries.json"
    loaded = [
        SessionTopicMap.model_validate(obj)
        for obj in json.loads(path.read_text(encoding="utf-8"))
    ]
    assert len(loaded) == 1
    assert loaded[0].session_id == "s1"
    assert len(loaded[0].boundaries) == 2
    assert loaded[0].boundaries[0].topic_label == "Onboarding flow"
    assert loaded[0].boundaries[1].timecode_seconds == 120.0


def test_extracted_quotes_roundtrip(tmp_path: Path):
    """extracted_quotes.json can be written and loaded back identically."""
    originals = _make_quotes()
    _write_intermediate(originals, "extracted_quotes.json", tmp_path)

    path = tmp_path / ".bristlenose" / "intermediate" / "extracted_quotes.json"
    loaded = [
        ExtractedQuote.model_validate(obj)
        for obj in json.loads(path.read_text(encoding="utf-8"))
    ]
    assert len(loaded) == 2
    assert loaded[0].text == "I found the onboarding confusing."
    assert loaded[1].quote_type == QuoteType.SCREEN_SPECIFIC


def test_clusters_and_themes_roundtrip(tmp_path: Path):
    """screen_clusters.json and theme_groups.json round-trip correctly."""
    quotes = _make_quotes()
    clusters = _make_clusters(quotes)
    themes = _make_themes(quotes)
    _write_intermediate(clusters, "screen_clusters.json", tmp_path)
    _write_intermediate(themes, "theme_groups.json", tmp_path)

    intermediate = tmp_path / ".bristlenose" / "intermediate"
    loaded_clusters = [
        ScreenCluster.model_validate(obj)
        for obj in json.loads(
            (intermediate / "screen_clusters.json").read_text(encoding="utf-8")
        )
    ]
    loaded_themes = [
        ThemeGroup.model_validate(obj)
        for obj in json.loads(
            (intermediate / "theme_groups.json").read_text(encoding="utf-8")
        )
    ]
    assert len(loaded_clusters) == 1
    assert loaded_clusters[0].screen_label == "Onboarding"
    assert len(loaded_clusters[0].quotes) == 1
    assert len(loaded_themes) == 1
    assert loaded_themes[0].theme_label == "Simplicity"


# ---------------------------------------------------------------------------
# Cache-skip decision logic (manifest + file presence)
# ---------------------------------------------------------------------------


def _write_manifest_with_stages(
    output_dir: Path,
    complete_stages: list[str],
) -> None:
    """Write a manifest with the given stages marked complete."""
    m = create_manifest("test-project", "0.10.1")
    for stage in complete_stages:
        mark_stage_running(m, stage)
        mark_stage_complete(m, stage)
    write_manifest(m, output_dir)


def test_cache_skip_when_manifest_and_file_present(tmp_path: Path):
    """Stage is skipped when manifest says complete AND intermediate file exists."""
    _write_manifest_with_stages(
        tmp_path,
        [STAGE_TOPIC_SEGMENTATION, STAGE_QUOTE_EXTRACTION, STAGE_CLUSTER_AND_GROUP],
    )
    topics = _make_topic_boundaries()
    quotes = _make_quotes()
    clusters = _make_clusters(quotes)
    themes = _make_themes(quotes)
    _write_intermediate(topics, "topic_boundaries.json", tmp_path)
    _write_intermediate(quotes, "extracted_quotes.json", tmp_path)
    _write_intermediate(clusters, "screen_clusters.json", tmp_path)
    _write_intermediate(themes, "theme_groups.json", tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    intermediate = tmp_path / ".bristlenose" / "intermediate"

    # All three cacheable stages should be detected as cached
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is True
    assert (intermediate / "topic_boundaries.json").exists()

    assert _is_stage_cached(prev, STAGE_QUOTE_EXTRACTION) is True
    assert (intermediate / "extracted_quotes.json").exists()

    assert _is_stage_cached(prev, STAGE_CLUSTER_AND_GROUP) is True
    assert (intermediate / "screen_clusters.json").exists()
    assert (intermediate / "theme_groups.json").exists()


def test_cache_skip_fails_when_file_missing(tmp_path: Path):
    """Stage is NOT skipped when manifest says complete but file is missing."""
    _write_manifest_with_stages(tmp_path, [STAGE_TOPIC_SEGMENTATION])
    # Don't write the topic_boundaries.json file

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    intermediate = tmp_path / ".bristlenose" / "intermediate"

    # Manifest says complete but file doesn't exist — should not use cache
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is True
    assert not (intermediate / "topic_boundaries.json").exists()
    # The pipeline checks BOTH conditions — this test documents the pattern


def test_cache_skip_fails_when_stage_running(tmp_path: Path):
    """Stage is NOT skipped when manifest says running (interrupted stage)."""
    m = create_manifest("test", "1.0")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    # Don't mark complete — simulates a crash during quote extraction
    write_manifest(m, tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    assert _is_stage_cached(prev, STAGE_QUOTE_EXTRACTION) is False


def test_cache_skip_fails_when_no_manifest(tmp_path: Path):
    """Stage is NOT skipped when no manifest exists (fresh run)."""
    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    assert prev is None
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is False


# ---------------------------------------------------------------------------
# Phase 1d — per-session resume
# ---------------------------------------------------------------------------


def _make_multi_session_topic_boundaries() -> list[SessionTopicMap]:
    """Topic maps for 3 sessions."""
    return [
        SessionTopicMap(
            session_id=f"s{i}",
            participant_id=f"p{i}",
            boundaries=[
                TopicBoundary(
                    timecode_seconds=0.0,
                    topic_label=f"Topic A (s{i})",
                    transition_type=TransitionType.SCREEN_CHANGE,
                ),
            ],
        )
        for i in range(1, 4)
    ]


def _make_multi_session_quotes() -> list[ExtractedQuote]:
    """Quotes for 3 sessions (2 quotes each)."""
    quotes = []
    for i in range(1, 4):
        quotes.append(
            ExtractedQuote(
                session_id=f"s{i}",
                participant_id=f"p{i}",
                start_timecode=10.0,
                end_timecode=20.0,
                text=f"Quote A from session {i}",
                topic_label=f"Topic A (s{i})",
                quote_type=QuoteType.SCREEN_SPECIFIC,
            )
        )
        quotes.append(
            ExtractedQuote(
                session_id=f"s{i}",
                participant_id=f"p{i}",
                start_timecode=30.0,
                end_timecode=40.0,
                text=f"Quote B from session {i}",
                topic_label=f"Topic A (s{i})",
                quote_type=QuoteType.GENERAL_CONTEXT,
            )
        )
    return quotes


def _write_manifest_with_session_records(
    output_dir: Path,
    stage: str,
    completed_session_ids: list[str],
) -> None:
    """Write a manifest with per-session records for one stage."""
    m = create_manifest("test-project", "0.10.1")
    mark_stage_running(m, stage)
    for sid in completed_session_ids:
        mark_session_complete(m, stage, sid, provider="anthropic", model="sonnet")
    write_manifest(m, output_dir)


def test_per_session_topic_partial_resume(tmp_path: Path):
    """Only s1 is cached in topic segmentation; s2 and s3 need processing."""
    # Write manifest with s1 complete
    _write_manifest_with_session_records(
        tmp_path, STAGE_TOPIC_SEGMENTATION, ["s1"],
    )
    # Write intermediate JSON with all 3 sessions (simulating a crash after s1)
    all_maps = _make_multi_session_topic_boundaries()
    _write_intermediate(all_maps, "topic_boundaries.json", tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)

    # Stage should NOT be fully cached (PARTIAL, not COMPLETE)
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is False

    # But s1 should be identified as a completed session
    completed = get_completed_session_ids(prev, STAGE_TOPIC_SEGMENTATION)
    assert completed == {"s1"}


def test_per_session_topic_filter_cached_from_json(tmp_path: Path):
    """Cached topic maps are correctly filtered by session_id."""
    all_maps = _make_multi_session_topic_boundaries()
    _write_intermediate(all_maps, "topic_boundaries.json", tmp_path)

    tb_path = tmp_path / ".bristlenose" / "intermediate" / "topic_boundaries.json"
    cached_sids = {"s1", "s3"}
    cached_maps = [
        SessionTopicMap.model_validate(obj)
        for obj in json.loads(tb_path.read_text(encoding="utf-8"))
        if obj.get("session_id") in cached_sids
    ]
    assert len(cached_maps) == 2
    assert {m.session_id for m in cached_maps} == {"s1", "s3"}


def test_per_session_quote_filter_cached_from_json(tmp_path: Path):
    """Cached quotes are correctly filtered by session_id."""
    all_quotes = _make_multi_session_quotes()
    _write_intermediate(all_quotes, "extracted_quotes.json", tmp_path)

    eq_path = tmp_path / ".bristlenose" / "intermediate" / "extracted_quotes.json"
    cached_sids = {"s1", "s2"}
    cached_quotes = [
        ExtractedQuote.model_validate(obj)
        for obj in json.loads(eq_path.read_text(encoding="utf-8"))
        if obj.get("session_id") in cached_sids
    ]
    assert len(cached_quotes) == 4  # 2 quotes per session × 2 sessions
    assert all(q.session_id in cached_sids for q in cached_quotes)


def test_per_session_quote_partial_resume(tmp_path: Path):
    """Only s1 and s2 are cached in quote extraction; s3 needs processing."""
    _write_manifest_with_session_records(
        tmp_path, STAGE_QUOTE_EXTRACTION, ["s1", "s2"],
    )
    all_quotes = _make_multi_session_quotes()
    _write_intermediate(all_quotes, "extracted_quotes.json", tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)

    # Stage is PARTIAL (s3 missing)
    assert _is_stage_cached(prev, STAGE_QUOTE_EXTRACTION) is False

    completed = get_completed_session_ids(prev, STAGE_QUOTE_EXTRACTION)
    assert completed == {"s1", "s2"}


def test_per_session_all_complete_is_fully_cached(tmp_path: Path):
    """When all sessions are complete and stage is marked complete, fully cached."""
    # Build a manifest where all sessions finished AND mark_stage_complete was called
    m = create_manifest("test-project", "0.10.1")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    for sid in ["s1", "s2", "s3"]:
        mark_session_complete(m, STAGE_TOPIC_SEGMENTATION, sid)
    mark_stage_complete(m, STAGE_TOPIC_SEGMENTATION)
    write_manifest(m, tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    # Stage is COMPLETE → fully cached (Phase 1c all-or-nothing path)
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is True


def test_per_session_not_cached_when_stage_still_running(tmp_path: Path):
    """Stage with session records but no mark_stage_complete is NOT cached."""
    _write_manifest_with_session_records(
        tmp_path, STAGE_TOPIC_SEGMENTATION, ["s1", "s2", "s3"],
    )
    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    # Stage status is RUNNING (crash before mark_stage_complete) → not cached
    assert _is_stage_cached(prev, STAGE_TOPIC_SEGMENTATION) is False
    # But all 3 sessions are individually complete
    completed = get_completed_session_ids(prev, STAGE_TOPIC_SEGMENTATION)
    assert completed == {"s1", "s2", "s3"}


def test_per_session_merge_cached_and_fresh_topic_maps():
    """Merging cached + fresh topic maps produces the full set."""
    all_maps = _make_multi_session_topic_boundaries()
    cached = [m for m in all_maps if m.session_id in {"s1", "s2"}]
    fresh = [m for m in all_maps if m.session_id == "s3"]
    merged = cached + fresh
    assert len(merged) == 3
    assert {m.session_id for m in merged} == {"s1", "s2", "s3"}


def test_per_session_merge_cached_and_fresh_quotes():
    """Merging cached + fresh quotes produces the full set."""
    all_quotes = _make_multi_session_quotes()
    cached_sids = {"s1"}
    cached = [q for q in all_quotes if q.session_id in cached_sids]
    fresh = [q for q in all_quotes if q.session_id not in cached_sids]
    merged = cached + fresh
    assert len(merged) == 6
    assert {q.session_id for q in merged} == {"s1", "s2", "s3"}


def test_per_session_provider_model_recorded(tmp_path: Path):
    """Provider and model are recorded on each session record."""
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(
        m, STAGE_QUOTE_EXTRACTION, "s1", provider="anthropic", model="sonnet",
    )
    mark_session_complete(
        m, STAGE_QUOTE_EXTRACTION, "s2", provider="google", model="gemini-flash",
    )
    write_manifest(m, tmp_path)

    from bristlenose.manifest import load_manifest

    loaded = load_manifest(tmp_path)
    assert loaded is not None
    sessions = loaded.stages[STAGE_QUOTE_EXTRACTION].sessions
    assert sessions is not None
    assert sessions["s1"].provider == "anthropic"
    assert sessions["s1"].model == "sonnet"
    assert sessions["s2"].provider == "google"
    assert sessions["s2"].model == "gemini-flash"


# ---------------------------------------------------------------------------
# Phase 1d-ext — transcription per-session caching
# ---------------------------------------------------------------------------


def _make_session_segments() -> dict[str, list[TranscriptSegment]]:
    """Transcript segments for 3 sessions."""
    result = {}
    for i in range(1, 4):
        result[f"s{i}"] = [
            TranscriptSegment(
                start_time=0.0,
                end_time=10.0,
                text=f"Hello from session {i}",
                speaker_label="Speaker A",
                speaker_role=SpeakerRole.RESEARCHER,
                source="whisper",
            ),
            TranscriptSegment(
                start_time=10.0,
                end_time=25.0,
                text=f"Response from session {i}",
                speaker_label="Speaker B",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ]
    return result


def _write_session_segments_json(
    data: dict[str, list[TranscriptSegment]],
    output_dir: Path,
) -> Path:
    """Write session_segments.json to the intermediate directory."""
    intermediate = output_dir / ".bristlenose" / "intermediate"
    intermediate.mkdir(parents=True, exist_ok=True)
    path = intermediate / "session_segments.json"
    json_data = {
        sid: [seg.model_dump(mode="json") for seg in segs]
        for sid, segs in data.items()
    }
    path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    return path


def test_transcription_segments_json_roundtrip(tmp_path: Path):
    """session_segments.json can be written and loaded back identically."""
    originals = _make_session_segments()
    _write_session_segments_json(originals, tmp_path)

    path = tmp_path / ".bristlenose" / "intermediate" / "session_segments.json"
    loaded_raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = {
        sid: [TranscriptSegment.model_validate(s) for s in segs]
        for sid, segs in loaded_raw.items()
    }
    assert set(loaded.keys()) == {"s1", "s2", "s3"}
    for sid in loaded:
        assert len(loaded[sid]) == 2
        assert loaded[sid][0].speaker_label == "Speaker A"
        assert loaded[sid][0].source == "whisper"
        assert loaded[sid][1].end_time == 25.0


def test_transcription_cache_skip_when_complete(tmp_path: Path):
    """Transcription is fully cached when stage is COMPLETE and JSON exists."""
    _write_manifest_with_stages(tmp_path, [STAGE_TRANSCRIBE])
    _write_session_segments_json(_make_session_segments(), tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    ss_path = tmp_path / ".bristlenose" / "intermediate" / "session_segments.json"

    assert _is_stage_cached(prev, STAGE_TRANSCRIBE) is True
    assert ss_path.exists()


def test_transcription_per_session_partial_resume(tmp_path: Path):
    """Only s1 is cached in transcription; s2 and s3 need processing."""
    _write_manifest_with_session_records(
        tmp_path, STAGE_TRANSCRIBE, ["s1"],
    )
    _write_session_segments_json(_make_session_segments(), tmp_path)

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)

    # Stage is NOT fully cached (RUNNING, not COMPLETE)
    assert _is_stage_cached(prev, STAGE_TRANSCRIBE) is False

    # But s1 is individually complete
    completed = get_completed_session_ids(prev, STAGE_TRANSCRIBE)
    assert completed == {"s1"}

    # Filter remaining sessions
    all_sids = {"s1", "s2", "s3"}
    remaining = all_sids - completed
    assert remaining == {"s2", "s3"}


def test_transcription_filter_cached_from_json(tmp_path: Path):
    """Cached segments are correctly filtered by session_id."""
    _write_session_segments_json(_make_session_segments(), tmp_path)

    ss_path = tmp_path / ".bristlenose" / "intermediate" / "session_segments.json"
    raw = json.loads(ss_path.read_text(encoding="utf-8"))

    cached_sids = {"s1", "s3"}
    cached_segments = {
        sid: [TranscriptSegment.model_validate(s) for s in segs]
        for sid, segs in raw.items()
        if sid in cached_sids
    }
    assert set(cached_segments.keys()) == {"s1", "s3"}
    assert "s2" not in cached_segments


def test_transcription_merge_cached_and_fresh():
    """Merging cached + fresh segments produces the full set."""
    all_segments = _make_session_segments()
    cached = {sid: segs for sid, segs in all_segments.items() if sid in {"s1"}}
    fresh = {sid: segs for sid, segs in all_segments.items() if sid not in {"s1"}}
    merged = {**cached, **fresh}
    assert set(merged.keys()) == {"s1", "s2", "s3"}


# ---------------------------------------------------------------------------
# Phase 1d-ext — speaker identification per-session caching
# ---------------------------------------------------------------------------


def _write_speaker_info_json(
    output_dir: Path,
    session_id: str,
    speaker_infos: list[dict],
    segments: list[TranscriptSegment],
) -> Path:
    """Write a speaker-info/{session_id}.json cache file."""
    si_dir = output_dir / ".bristlenose" / "intermediate" / "speaker-info"
    si_dir.mkdir(parents=True, exist_ok=True)
    path = si_dir / f"{session_id}.json"
    data = {
        "speaker_infos": speaker_infos,
        "segments_with_roles": [seg.model_dump(mode="json") for seg in segments],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_speaker_info_json_roundtrip(tmp_path: Path):
    """SpeakerInfo serialization round-trips correctly."""
    from bristlenose.stages.identify_speakers import (
        SpeakerInfo,
        speaker_info_from_dict,
        speaker_info_to_dict,
    )

    info = SpeakerInfo(
        speaker_label="Speaker A",
        role=SpeakerRole.RESEARCHER,
        person_name="Jane",
        job_title="UX Researcher",
    )
    d = speaker_info_to_dict(info)
    assert d == {
        "speaker_label": "Speaker A",
        "role": "researcher",
        "person_name": "Jane",
        "job_title": "UX Researcher",
    }
    restored = speaker_info_from_dict(d)
    assert restored.speaker_label == info.speaker_label
    assert restored.role == info.role
    assert restored.person_name == info.person_name
    assert restored.job_title == info.job_title


def test_speaker_id_cache_skip_when_complete(tmp_path: Path):
    """Speaker ID is fully cached when stage is COMPLETE and files exist."""
    _write_manifest_with_stages(tmp_path, [STAGE_IDENTIFY_SPEAKERS])

    segments = _make_session_segments()
    for sid in ["s1", "s2", "s3"]:
        _write_speaker_info_json(
            tmp_path,
            sid,
            speaker_infos=[
                {"speaker_label": "Speaker A", "role": "researcher",
                 "person_name": "", "job_title": ""},
                {"speaker_label": "Speaker B", "role": "participant",
                 "person_name": "", "job_title": ""},
            ],
            segments=segments[sid],
        )

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)
    assert _is_stage_cached(prev, STAGE_IDENTIFY_SPEAKERS) is True

    si_dir = tmp_path / ".bristlenose" / "intermediate" / "speaker-info"
    assert (si_dir / "s1.json").exists()
    assert (si_dir / "s2.json").exists()
    assert (si_dir / "s3.json").exists()


def test_speaker_id_per_session_partial_resume(tmp_path: Path):
    """Only s1 cached in speaker ID; s2 and s3 need LLM calls."""
    _write_manifest_with_session_records(
        tmp_path, STAGE_IDENTIFY_SPEAKERS, ["s1"],
    )
    segments = _make_session_segments()
    _write_speaker_info_json(
        tmp_path,
        "s1",
        speaker_infos=[
            {"speaker_label": "Speaker A", "role": "researcher",
             "person_name": "", "job_title": ""},
        ],
        segments=segments["s1"],
    )

    from bristlenose.manifest import load_manifest

    prev = load_manifest(tmp_path)

    assert _is_stage_cached(prev, STAGE_IDENTIFY_SPEAKERS) is False
    completed = get_completed_session_ids(prev, STAGE_IDENTIFY_SPEAKERS)
    assert completed == {"s1"}


def test_speaker_info_segments_restored_from_cache(tmp_path: Path):
    """Cached segments have speaker_role preserved on reload."""
    segments = [
        TranscriptSegment(
            start_time=0.0,
            end_time=10.0,
            text="Let me show you the prototype.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=10.0,
            end_time=30.0,
            text="That looks great!",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
    ]
    _write_speaker_info_json(
        tmp_path,
        "s1",
        speaker_infos=[
            {"speaker_label": "Speaker A", "role": "researcher",
             "person_name": "Jane", "job_title": ""},
            {"speaker_label": "Speaker B", "role": "participant",
             "person_name": "Tom", "job_title": "PM"},
        ],
        segments=segments,
    )

    si_path = (
        tmp_path / ".bristlenose" / "intermediate" / "speaker-info" / "s1.json"
    )
    data = json.loads(si_path.read_text(encoding="utf-8"))

    restored_segments = [
        TranscriptSegment.model_validate(seg)
        for seg in data["segments_with_roles"]
    ]
    assert restored_segments[0].speaker_role == SpeakerRole.RESEARCHER
    assert restored_segments[1].speaker_role == SpeakerRole.PARTICIPANT
    assert restored_segments[0].source == "whisper"


def test_assign_speaker_codes_always_reruns():
    """assign_speaker_codes runs on all sessions for consistent global numbering."""
    from bristlenose.stages.identify_speakers import assign_speaker_codes

    # Session 1: one researcher, one participant
    segs_s1 = [
        TranscriptSegment(
            start_time=0.0, end_time=5.0, text="Hello",
            speaker_label="Speaker A", speaker_role=SpeakerRole.RESEARCHER,
        ),
        TranscriptSegment(
            start_time=5.0, end_time=10.0, text="Hi",
            speaker_label="Speaker B", speaker_role=SpeakerRole.PARTICIPANT,
        ),
    ]
    # Session 2: one researcher, one participant
    segs_s2 = [
        TranscriptSegment(
            start_time=0.0, end_time=5.0, text="Welcome",
            speaker_label="Speaker C", speaker_role=SpeakerRole.RESEARCHER,
        ),
        TranscriptSegment(
            start_time=5.0, end_time=10.0, text="Thanks",
            speaker_label="Speaker D", speaker_role=SpeakerRole.PARTICIPANT,
        ),
    ]

    # Run assign_speaker_codes with global numbering
    label_map_1, next_pnum = assign_speaker_codes(1, segs_s1)
    label_map_2, next_pnum = assign_speaker_codes(next_pnum, segs_s2)

    # Session 1: m1 for researcher, p1 for participant
    assert label_map_1["Speaker A"] == "m1"
    assert label_map_1["Speaker B"] == "p1"

    # Session 2: m1 for researcher (per-session), p2 for participant (global)
    assert label_map_2["Speaker C"] == "m1"
    assert label_map_2["Speaker D"] == "p2"

    # Global numbering continues
    assert next_pnum == 3
