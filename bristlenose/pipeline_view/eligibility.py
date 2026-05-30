"""Resolve `BackendOption` eligibility against `HostFacts` + `BristlenoseSettings`.

Pure functions — no I/O. The host probe owns runtime I/O (find_spec,
platform.mac_ver, socket); this module reads from the already-populated
`HostFacts`. Two consequences:

1. `check_requirement(kind="python_package")` reads `host.installed_packages`
   — it never calls `importlib.util.find_spec` directly. Otherwise the
   ~150 predicate checks per `/api/pipeline` render would each cost a
   `find_spec` call (~0.5ms) ≈ 75 ms wasted.
2. Tests can fully mock eligibility by constructing a synthetic `HostFacts`
   — no need to patch stdlib.
"""

from __future__ import annotations

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.catalogue import (
    BackendOption,
    Requirement,
    requirements_for,
)
from bristlenose.pipeline_view.host import HostFacts


def check_requirement(
    req: Requirement,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> tuple[bool, str | None]:
    """Return `(ok, explain_failure_key)`. Key is None on success."""
    value = req.value
    if req.kind == "api_key":
        ok = bool(host.keys_present.get(str(value), False))
    elif req.kind == "setting_present":
        ok = bool(getattr(settings, str(value), None))
    elif req.kind == "setting_enabled":
        ok = bool(getattr(settings, str(value), False))
    elif req.kind == "hardware":
        ok = _matches_hardware(host, str(value))
    elif req.kind == "os":
        ok = host.os == str(value)
    elif req.kind == "min_ram_gb":
        ok = host.memory_gb is not None and host.memory_gb >= float(value)
    elif req.kind == "ollama_running":
        ok = host.ollama_running is True
    elif req.kind == "python_package":
        ok = host.installed_packages.get(str(value), False)
    elif req.kind == "min_os_version":
        ok = _meets_min_os_version(host.os_version, float(value))
    elif req.kind == "apple_fm_status":
        ok = host.apple_fm_status == str(value)
    else:  # pragma: no cover — closed enum, mypy guards exhaustiveness
        ok = False
    return (True, None) if ok else (False, req.explain_failure)


def _matches_hardware(host: HostFacts, required: str) -> bool:
    """Map host (os, arch) to AcceleratorType-style strings."""
    if required == "apple_silicon":
        return host.os == "Darwin" and host.arch == "arm64"
    if required == "cuda":
        # v1.5 doesn't probe CUDA presence — out of scope for the alpha cohort.
        # If/when we do, this is the single spot to update.
        return False
    return False


def _meets_min_os_version(os_version: str | None, minimum: float) -> bool:
    """Compare a macOS version string ("26.0" / "26.1") against a minimum."""
    if not os_version:
        return False
    try:
        major_minor = ".".join(os_version.split(".")[:2])
        return float(major_minor) >= minimum
    except (ValueError, IndexError):
        return False


def evaluate_backend(
    stage_id: str,
    option: BackendOption,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> tuple[bool, str | None]:
    """Aggregate all requirements for a (stage, option) cell.

    Returns `(available, first_failing_reason_key)`. Determinism: the first
    failing requirement in declaration order wins. None when all pass.
    """
    for req in requirements_for(stage_id, option.id):
        ok, reason = check_requirement(req, host, settings)
        if not ok:
            return False, reason
    return True, None
