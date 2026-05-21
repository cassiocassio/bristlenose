"""Static catalogue of user-visible pipeline stages.

This is the "what Bristlenose runs" inventory the Pipeline view renders. Only
stages where the chosen backend is interesting to a researcher appear here —
deterministic ingest/audio/parse/merge/render stages are omitted (they don't
participate in the mixture-of-models story).

The Apple Foundation Models entry is a placeholder kind=`apple_fm` that the
renderer fills with `unknown` on the CLI; the desktop app's Pipeline view will
fill it once a Swift-side probe binary ships (deferred, see
`docs/design-cli-improvements.md` §Captured design).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

StageKind = Literal["transcription", "llm", "anonymisation", "apple_fm"]


class PipelineStageDef(BaseModel):
    """Static definition of a user-visible stage."""

    id: str  # stable identifier, used by `--stage` filter and React keys
    name: str  # display name, e.g. "Transcription"
    kind: StageKind
    notes: str  # one-line "why this backend" copy


STAGES: list[PipelineStageDef] = [
    PipelineStageDef(
        id="transcription",
        name="Transcription",
        kind="transcription",
        notes="Auto-detected from your hardware. Local, private, free.",
    ),
    PipelineStageDef(
        id="speaker_identification",
        name="Speaker identification",
        kind="llm",
        notes="Set by your provider choice.",
    ),
    PipelineStageDef(
        id="anonymisation",
        name="Anonymisation",
        kind="anonymisation",
        notes="Presidio runs locally when --redact-pii is enabled.",
    ),
    PipelineStageDef(
        id="topic_segmentation",
        name="Topic segmentation",
        kind="llm",
        notes="Set by your provider choice.",
    ),
    PipelineStageDef(
        id="quote_extraction",
        name="Quote extraction",
        kind="llm",
        notes="Set by your provider choice. Typically the largest LLM cost.",
    ),
    PipelineStageDef(
        id="quote_clustering",
        name="Quote clustering",
        kind="llm",
        notes="Set by your provider choice.",
    ),
    PipelineStageDef(
        id="thematic_grouping",
        name="Thematic grouping",
        kind="llm",
        notes="Set by your provider choice.",
    ),
    PipelineStageDef(
        id="apple_foundation_models",
        name="Apple Foundation Models",
        kind="apple_fm",
        notes=(
            "Availability not detected from CLI; see the desktop app's "
            "Pipeline view for status. A CLI probe is planned."
        ),
    ),
]


def find_stage(stage_id: str) -> PipelineStageDef | None:
    """Look up a stage definition by id; returns None if no match."""
    for stage in STAGES:
        if stage.id == stage_id:
            return stage
    return None
