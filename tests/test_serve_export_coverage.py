"""Coverage gate — the anti-drift backbone for the self-contained HTML export.

Every project-scoped GET *read* endpoint must be EITHER embedded in the export
(``EMBED_PATH_TEMPLATES``, produced by ``export_report``) OR an explicit
server-only opt-out (``SERVER_ONLY_PATH_TEMPLATES``).  This test reads the
server's OWN OpenAPI schema — the authoritative full read surface — and fails if
any GET read path is classified in neither set.  So a newly-added read endpoint
is offline-by-default, and dropping it from the export is a deliberate, reviewed
act rather than silent drift (the exact failure that let the export lag the API
surface for four months).

Unlike ``test_serve_export_api.py`` this needs NO frontend build — it is pure
schema introspection, so it runs (and has teeth) in CI where the frontend isn't
built.
"""

from __future__ import annotations

from pathlib import Path

from bristlenose.server.app import create_app
from bristlenose.server.routes.export import (
    EMBED_PATH_TEMPLATES,
    SERVER_ONLY_PATH_TEMPLATES,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_PREFIX = "/api/projects/{project_id}"


def _project_get_templates() -> set[str]:
    """Project-scoped GET path templates from the app's own (production) OpenAPI."""
    # dev=False → the shipped surface (dev-only playground/debug routes excluded).
    app = create_app(project_dir=_FIXTURE_DIR, dev=False, db_url="sqlite://")
    spec = app.openapi()
    return {
        path[len("/api") :]  # "/api/projects/{project_id}/x" → "/projects/{project_id}/x"
        for path, item in spec["paths"].items()
        if "get" in item and path.startswith(_PREFIX)
    }


def test_every_project_get_read_is_classified() -> None:
    """No project-scoped GET read escapes offline classification (the gate)."""
    surface = _project_get_templates()
    classified = EMBED_PATH_TEMPLATES | SERVER_ONLY_PATH_TEMPLATES
    unclassified = surface - classified
    assert not unclassified, (
        "New GET read endpoint(s) are unclassified for offline export:\n  "
        + "\n  ".join(sorted(unclassified))
        + "\n\nAdd each (in bristlenose/server/routes/export.py) to either:\n"
        "  • EMBED_PATH_TEMPLATES  — wire it into export_report so it ships offline, or\n"
        "  • SERVER_ONLY_PATH_TEMPLATES — a deliberate opt-out; also hide its UI\n"
        "    affordance offline via isExportMode()."
    )


def test_no_stale_classifications() -> None:
    """EMBED / SERVER_ONLY don't reference paths that no longer exist (rot guard)."""
    surface = _project_get_templates()
    stale = (EMBED_PATH_TEMPLATES | SERVER_ONLY_PATH_TEMPLATES) - surface
    assert not stale, (
        "Classified export path(s) no longer exist in the API surface:\n  "
        + "\n  ".join(sorted(stale))
        + "\n\nRemove them from EMBED_PATH_TEMPLATES / SERVER_ONLY_PATH_TEMPLATES "
        "in bristlenose/server/routes/export.py."
    )


def test_embed_and_server_only_are_disjoint() -> None:
    """A path can't be both embedded and opted-out."""
    overlap = EMBED_PATH_TEMPLATES & SERVER_ONLY_PATH_TEMPLATES
    assert not overlap, f"Paths classified as both EMBED and SERVER_ONLY: {sorted(overlap)}"
