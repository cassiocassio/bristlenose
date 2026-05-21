"""Pipeline view — read-only surface for the mixture-of-models Bristlenose runs.

See `docs/design-cli-improvements.md` §"Captured design" for the parked design
space; v1 ships one CLI verb (`bristlenose pipeline`) + a matching read-only
Settings nav item in the React SPA.
"""

from bristlenose.pipeline_view.catalogue import STAGES, PipelineStageDef
from bristlenose.pipeline_view.host import HostFacts, probe_host
from bristlenose.pipeline_view.render import (
    PipelineView,
    StageSelection,
    build_pipeline_view,
)

__all__ = [
    "STAGES",
    "HostFacts",
    "PipelineStageDef",
    "PipelineView",
    "StageSelection",
    "build_pipeline_view",
    "probe_host",
]
