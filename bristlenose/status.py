"""Project status — reads pipeline manifest and validates cached artifacts.

Pure logic module: reads the manifest, checks intermediate file existence,
and returns a data structure for the CLI to print.  No I/O beyond file
existence checks and manifest JSON parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bristlenose.manifest import (
    PipelineManifest,
    StageStatus,
    _derive_stage_status,
    load_manifest,
)

# ---------------------------------------------------------------------------
# Intermediate file names — keep in sync with pipeline.py / render_output.py
# ---------------------------------------------------------------------------

_INTERMEDIATE_FILES: dict[str, str] = {
    "topic_segmentation": "topic_boundaries.json",
    "quote_extraction": "extracted_quotes.json",
    "cluster_and_group": "screen_clusters.json",
}

# theme_groups.json is written by the same cluster_and_group stage
_THEME_GROUPS_FILE = "theme_groups.json"


# ---------------------------------------------------------------------------
# Display names for stages
# ---------------------------------------------------------------------------

_STAGE_DISPLAY: dict[str, str] = {
    "ingest": "Ingest",
    "extract_audio": "Extract audio",
    "transcribe": "Transcribe",
    "identify_speakers": "Speakers",
    "merge_transcript": "Merge",
    "pii_removal": "PII removal",
    "topic_segmentation": "Topics",
    "quote_extraction": "Quotes",
    "cluster_and_group": "Clusters & themes",
    "render": "Report",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class StageStatusInfo:
    """Status of one pipeline stage for display."""

    name: str  # display name, e.g. "Transcribe"
    stage_key: str  # manifest key, e.g. "transcribe"
    status: StageStatus
    detail: str = ""  # e.g. "10 sessions", "87 boundaries"
    session_total: int | None = None
    session_complete: int | None = None
    file_exists: bool = True  # intermediate file validated
    file_missing_warning: str = ""  # set if file_exists is False


@dataclass
class ProjectStatus:
    """Full project status for display."""

    project_name: str
    pipeline_version: str
    last_run: str  # ISO timestamp from manifest.updated_at
    stages: list[StageStatusInfo] = field(default_factory=list)
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Stage ordering for display (subset of STAGE_ORDER — skip trivial stages)
# ---------------------------------------------------------------------------

_DISPLAY_STAGES = [
    "ingest",
    "transcribe",
    "identify_speakers",
    "topic_segmentation",
    "quote_extraction",
    "cluster_and_group",
    "render",
]


def _count_json_array(path: Path) -> int | None:
    """Count top-level array entries without full deserialization.

    Returns None if the file doesn't exist or isn't a JSON array.
    """
    if not path.exists():
        return None
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _build_stage_info(
    stage_key: str,
    manifest: PipelineManifest,
    intermediate_dir: Path,
    output_dir: Path,
) -> StageStatusInfo:
    """Build status info for one stage."""
    display_name = _STAGE_DISPLAY.get(stage_key, stage_key)
    record = manifest.stages.get(stage_key)

    if record is None:
        return StageStatusInfo(
            name=display_name,
            stage_key=stage_key,
            status=StageStatus.PENDING,
        )

    # Derive effective status from session records if available
    effective_status = _derive_stage_status(record)

    info = StageStatusInfo(
        name=display_name,
        stage_key=stage_key,
        status=effective_status,
    )

    # Per-session detail
    if record.sessions:
        total = len(record.sessions)
        complete = sum(
            1 for s in record.sessions.values() if s.status == StageStatus.COMPLETE
        )
        info.session_total = total
        info.session_complete = complete
        if effective_status == StageStatus.COMPLETE:
            info.detail = f"{total} sessions"
        elif complete > 0:
            incomplete = total - complete
            info.detail = f"{complete}/{total} sessions ({incomplete} incomplete)"
        else:
            info.detail = f"{total} sessions pending"

    # Stage-specific detail enrichment
    if effective_status == StageStatus.COMPLETE:
        if stage_key == "topic_segmentation":
            count = _count_json_array(intermediate_dir / "topic_boundaries.json")
            if count is not None:
                info.detail = f"{count} boundaries"
        elif stage_key == "quote_extraction":
            count = _count_json_array(intermediate_dir / "extracted_quotes.json")
            if count is not None:
                session_part = f" ({info.session_total} sessions)" if info.session_total else ""
                info.detail = f"{count} quotes{session_part}"
        elif stage_key == "cluster_and_group":
            clusters = _count_json_array(intermediate_dir / "screen_clusters.json")
            themes = _count_json_array(intermediate_dir / "theme_groups.json")
            parts = []
            if clusters is not None:
                parts.append(f"{clusters} screens")
            if themes is not None:
                parts.append(f"{themes} themes")
            if parts:
                info.detail = " · ".join(parts)
        elif stage_key == "render":
            # Check if report HTML exists
            report_files = list(output_dir.glob("bristlenose-*-report.html"))
            if report_files:
                info.detail = report_files[0].name
            else:
                info.detail = "complete"
        elif stage_key == "ingest" and not info.detail:
            # Ingest doesn't have session records — derive from other stages
            for other_key in ("transcribe", "identify_speakers", "topic_segmentation",
                              "quote_extraction"):
                other = manifest.stages.get(other_key)
                if other and other.sessions:
                    info.detail = f"{len(other.sessions)} sessions"
                    break
            if not info.detail:
                info.detail = "complete"

    # Validate intermediate file existence for completed stages
    if effective_status == StageStatus.COMPLETE and stage_key in _INTERMEDIATE_FILES:
        expected = intermediate_dir / _INTERMEDIATE_FILES[stage_key]
        if not expected.exists():
            info.file_exists = False
            info.file_missing_warning = (
                f"marked complete but {_INTERMEDIATE_FILES[stage_key]} missing "
                f"— will re-run on next pipeline run"
            )

    return info


def get_project_status(output_dir: Path) -> ProjectStatus | None:
    """Read manifest and validate file existence.

    *output_dir* is the pipeline output directory (the one containing
    ``.bristlenose/``).  Returns ``None`` if no manifest exists.
    """
    manifest = load_manifest(output_dir)
    if manifest is None:
        return None

    intermediate_dir = output_dir / ".bristlenose" / "intermediate"

    stages = [
        _build_stage_info(stage_key, manifest, intermediate_dir, output_dir)
        for stage_key in _DISPLAY_STAGES
    ]

    return ProjectStatus(
        project_name=manifest.project_name,
        pipeline_version=manifest.pipeline_version,
        last_run=manifest.updated_at,
        stages=stages,
        total_cost_usd=manifest.total_cost_usd,
    )


def format_resume_summary(status: ProjectStatus) -> str:
    """One-line summary for the pre-run resume message.

    Returns a human-readable string like:
      "Resuming: 7/10 sessions have quotes, 3 remaining."
      "Resuming: all 10 stages complete — will re-render."
    """
    # Find the first incomplete stage
    for info in status.stages:
        if info.status in (StageStatus.PARTIAL, StageStatus.RUNNING):
            if info.session_total and info.session_complete is not None:
                remaining = info.session_total - info.session_complete
                return (
                    f"Resuming: {info.session_complete}/{info.session_total} "
                    f"sessions have {info.name.lower()}, {remaining} remaining."
                )
            return f"Resuming from {info.name.lower()}."

        if info.status == StageStatus.PENDING:
            return f"Resuming from {info.name.lower()}."

    return "Resuming: all stages complete — will re-render."
