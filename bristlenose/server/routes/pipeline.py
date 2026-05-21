"""GET /api/pipeline — read-only mixture-of-models view for the SPA Settings tab.

Mounted under `/api/` so `BearerTokenMiddleware` applies. Returns the same
`PipelineView` JSON the CLI emits via `bristlenose pipeline --json`, so the
shared contract fixture round-trips both surfaces.
"""

from __future__ import annotations

from fastapi import APIRouter

from bristlenose.config import load_settings
from bristlenose.pipeline_view.render import PipelineView, build_pipeline_view

router = APIRouter(prefix="/api")


@router.get("/pipeline", response_model=PipelineView)
def get_pipeline() -> PipelineView:
    """Return the current mixture-of-models view for this host."""
    settings = load_settings()
    return build_pipeline_view(settings)
