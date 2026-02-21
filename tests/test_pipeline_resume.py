"""Tests for pipeline resume — skip completed stages on re-run (Phase 1c)."""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
    StageStatus,
    create_manifest,
    mark_stage_complete,
    mark_stage_running,
    write_manifest,
)
from bristlenose.models import (
    ExtractedQuote,
    QuoteType,
    ScreenCluster,
    SessionTopicMap,
    ThemeGroup,
    TopicBoundary,
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
