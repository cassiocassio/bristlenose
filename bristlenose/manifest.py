"""Pipeline manifest — records which stages have completed.

The manifest lives at `<output_dir>/.bristlenose/pipeline-manifest.json`.
It is written after each stage completes so that interrupted runs can
resume from the last completed stage.

On startup, ``run()`` loads an existing manifest and skips stages marked
complete — loading cached intermediate JSON from disk instead of
re-computing.  Stages 1–7 always re-run (fast, no intermediate JSON).
Stages 8–11 are skippable when ``write_intermediate`` was True on the
original run.  Stage 12 (render) always re-runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class StageStatus(str, Enum):
    """Status of a single pipeline stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"  # some sessions done, some not
    FAILED = "failed"


class StageRecord(BaseModel):
    """Record for one pipeline stage."""

    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class PipelineManifest(BaseModel):
    """Top-level manifest model.

    Persisted to ``pipeline-manifest.json`` in the ``.bristlenose/``
    directory of the output folder.
    """

    schema_version: int = 1
    project_name: str
    pipeline_version: str
    created_at: str
    updated_at: str
    stages: dict[str, StageRecord] = {}
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Stage name constants — keep in sync with pipeline.py
# ---------------------------------------------------------------------------

STAGE_INGEST = "ingest"
STAGE_EXTRACT_AUDIO = "extract_audio"
STAGE_TRANSCRIBE = "transcribe"
STAGE_IDENTIFY_SPEAKERS = "identify_speakers"
STAGE_MERGE_TRANSCRIPT = "merge_transcript"
STAGE_PII_REMOVAL = "pii_removal"
STAGE_TOPIC_SEGMENTATION = "topic_segmentation"
STAGE_QUOTE_EXTRACTION = "quote_extraction"
STAGE_CLUSTER_AND_GROUP = "cluster_and_group"
STAGE_RENDER = "render"

# Ordered list for the full `run()` pipeline.
STAGE_ORDER = [
    STAGE_INGEST,
    STAGE_EXTRACT_AUDIO,
    STAGE_TRANSCRIBE,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_MERGE_TRANSCRIPT,
    STAGE_PII_REMOVAL,
    STAGE_TOPIC_SEGMENTATION,
    STAGE_QUOTE_EXTRACTION,
    STAGE_CLUSTER_AND_GROUP,
    STAGE_RENDER,
]


# ---------------------------------------------------------------------------
# Manifest file name (relative to .bristlenose/)
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "pipeline-manifest.json"


# ---------------------------------------------------------------------------
# Read / write helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _manifest_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / MANIFEST_FILENAME


def create_manifest(project_name: str, pipeline_version: str) -> PipelineManifest:
    """Create a fresh manifest with all stages pending."""
    now = _now_iso()
    return PipelineManifest(
        project_name=project_name,
        pipeline_version=pipeline_version,
        created_at=now,
        updated_at=now,
    )


def load_manifest(output_dir: Path) -> PipelineManifest | None:
    """Load the manifest from disk, or return None if it doesn't exist."""
    path = _manifest_path(output_dir)
    if not path.exists():
        return None
    return PipelineManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_manifest(manifest: PipelineManifest, output_dir: Path) -> None:
    """Write the manifest to disk (atomic: write tmp then rename)."""
    path = _manifest_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    tmp.rename(path)


def mark_stage_running(manifest: PipelineManifest, stage: str) -> None:
    """Mark a stage as running and update the manifest timestamp."""
    manifest.stages[stage] = StageRecord(
        status=StageStatus.RUNNING,
        started_at=_now_iso(),
    )
    manifest.updated_at = _now_iso()


def mark_stage_complete(manifest: PipelineManifest, stage: str) -> None:
    """Mark a stage as complete and update the manifest timestamp."""
    record = manifest.stages.get(stage, StageRecord())
    record.status = StageStatus.COMPLETE
    record.completed_at = _now_iso()
    manifest.stages[stage] = record
    manifest.updated_at = _now_iso()
