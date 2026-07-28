"""System-health (doctor) endpoint.

Runs the local, non-network subset of ``bristlenose/doctor.py`` in-process and
returns the ``DoctorReport`` as JSON. Consumed by the desktop app's native
Health window (Diagnostics ▸ Check Health), which renders the checks as a
native list keyed off the same ``MessageKind`` vocabulary the CLI uses.

Auth: unlike ``/api/health`` this endpoint is **NOT** auth-exempt. It exposes
environment detail (bundle paths, which dependencies/keys are present), so it
stays behind the bearer token like every other ``/api/*`` route. The desktop
Health window already holds ``authToken`` (from ``ServeManager``) and sends it
as a bearer.

Network-bearing checks (API-key validation, endpoint reachability, the Ollama
probe) are intentionally deferred — ``run_local_checks`` omits them so the
request doesn't block on a remote round-trip. A future async pass can surface
them separately.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from bristlenose import doctor as doctor_mod
from bristlenose.config import load_settings
from bristlenose.doctor_fixes import get_fix

router = APIRouter(prefix="/api")


def _load_settings_for(request: Request) -> object:
    """Load settings, honouring a test override on ``app.state``."""
    override = getattr(request.app.state, "settings", None)
    if override is not None:
        return override
    return load_settings()


@router.get("/doctor")
def doctor(request: Request) -> dict[str, object]:
    """Return the local health checks as structured JSON."""
    settings = _load_settings_for(request)
    report = doctor_mod.run_local_checks(settings)  # type: ignore[arg-type]
    return {
        "checks": [
            {
                "status": result.status.value,
                "label": result.label,
                "detail": result.detail,
                "fix_key": result.fix_key,
                # Resolve the fix_key slug to its human-readable, install-aware
                # instruction here (single source of truth), so the native
                # Health window renders a string and never a bare slug. Empty
                # when the check has no remedy.
                "fix": get_fix(result.fix_key) if result.fix_key else "",
            }
            for result in report.results
        ],
    }
