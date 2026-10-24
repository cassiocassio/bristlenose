"""A cluster/theme stage that lost one of its two calls is retried (R30 Q3).

Stage 10/11 makes two LLM calls, quote clustering and thematic grouping. When
one failed and the other succeeded, the run recorded the stage COMPLETE over
the failed half's fallback grouping, so every later run served the fallback
from cache until the quotes changed, and a plain Analyse never mended it. A
cache must not vouch for work that did not happen: the stage is now recorded
PARTIAL, the fallback stays on disk so the report renders, and the next run
makes both calls again (one stage record holds both halves, so it cannot
retry one alone). ``analyze`` records the stage the same way for the next run.

Real ``Pipeline`` and real manifest; every LLM stage stubbed (the harness of
``test_pipeline_command_caches``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.manifest import STAGE_CLUSTER_AND_GROUP, StageRecord, StageStatus, load_manifest
from tests.test_pipeline_command_caches import _drive, _intermediate


def _cluster_record(tmp_path: Path) -> StageRecord:
    manifest = load_manifest(tmp_path / "output")
    assert manifest is not None
    return manifest.stages[STAGE_CLUSTER_AND_GROUP]


@pytest.mark.parametrize("half", ["cluster", "group"])
def test_a_half_failed_cluster_stage_is_retried_on_the_next_run(
    tmp_path: Path, half: str,
) -> None:
    first: dict = {}
    result = _drive(tmp_path, "run", 2, first, cluster_fail=half)
    assert result is not None
    assert sorted(first["clustered"]) == ["cluster", "group"], first
    # The run says the call failed, and its fallback stays on disk.
    assert result.summary is not None and result.summary.themes is not None
    assert len(result.summary.themes.failed) == 1
    assert _intermediate(tmp_path, "screen_clusters.json").exists()
    assert _intermediate(tmp_path, "theme_groups.json").exists()
    # The manifest does not vouch for the fallback.
    record = _cluster_record(tmp_path)
    assert record.status == StageStatus.PARTIAL, record
    assert record.completed_at is None

    again: dict = {}
    result = _drive(tmp_path, "run", 2, again)
    # At HEAD: {} — the fallback was served from cache and nothing was called.
    assert sorted(again.get("clustered", [])) == ["cluster", "group"], again
    assert not {"topics", "quoted"} & set(again), again
    assert result is not None and result.summary is not None
    assert result.summary.themes is not None and not result.summary.themes.failed
    assert _cluster_record(tmp_path).status == StageStatus.COMPLETE

    third: dict = {}
    _drive(tmp_path, "run", 2, third)
    assert "clustered" not in third, third


def test_a_retry_that_fails_again_is_retried_again(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {}, cluster_fail="group")

    again: dict = {}
    result = _drive(tmp_path, "run", 2, again, cluster_fail="group")
    assert sorted(again.get("clustered", [])) == ["cluster", "group"], again
    assert result is not None and result.summary is not None
    assert result.summary.themes is not None and len(result.summary.themes.failed) == 1
    assert _cluster_record(tmp_path).status == StageStatus.PARTIAL


def test_a_clean_run_still_caches_the_stage(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    record = _cluster_record(tmp_path)
    assert record.status == StageStatus.COMPLETE
    assert record.completed_at is not None

    again: dict = {}
    _drive(tmp_path, "run", 2, again)
    assert "clustered" not in again, again


@pytest.mark.parametrize("half", ["cluster", "group"])
def test_a_run_after_a_half_failed_analyze_clusters_again(tmp_path: Path, half: str) -> None:
    _drive(tmp_path, "run", 2, {})
    _drive(tmp_path, "analyze", 2, {}, cluster_fail=half)
    assert _cluster_record(tmp_path).status == StageStatus.PARTIAL

    after: dict = {}
    _drive(tmp_path, "run", 2, after)
    # At HEAD: {} — analyze's fallback was vouched for, so the run served it.
    assert sorted(after.get("clustered", [])) == ["cluster", "group"], after
    # Only the stage that lost a call: analyze's topics and quotes are kept.
    assert not {"topics", "quoted"} & set(after), after
    assert _cluster_record(tmp_path).status == StageStatus.COMPLETE


def test_partial_over_a_complete_record_drops_its_completion() -> None:
    from bristlenose.manifest import create_manifest, mark_stage_complete, mark_stage_running

    manifest = create_manifest("p", "0")
    mark_stage_running(manifest, STAGE_CLUSTER_AND_GROUP)
    mark_stage_complete(manifest, STAGE_CLUSTER_AND_GROUP, content_hash="a")
    assert manifest.stages[STAGE_CLUSTER_AND_GROUP].completed_at is not None

    mark_stage_complete(manifest, STAGE_CLUSTER_AND_GROUP, content_hash="b", partial=True)
    record = manifest.stages[STAGE_CLUSTER_AND_GROUP]
    assert record.status == StageStatus.PARTIAL
    assert record.completed_at is None
