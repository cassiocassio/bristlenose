"""Host probe for the Pipeline view.

Loopback-only by contract: reads OS metadata, the user's already-loaded
settings, and the local Ollama port. Must NOT import telemetry, network, or
anything that emits off-host. Apple FM availability returns `unknown` on CLI;
the desktop app's Pipeline view fills it.

The host-specific payload is excluded from the support-bundle export
enumeration (see `bristlenose/server/admin.py` / support-bundle scaffolding
when that lands).
"""

from __future__ import annotations

import platform
import socket
from typing import Literal

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings

AppleFmStatus = Literal["unknown", "available", "unavailable"]


class HostFacts(BaseModel):
    """Loopback-only snapshot of the machine running this CLI.

    Never include re-identifying fields (hostname, MAC, install path, etc.).
    Everything here is either OS-class metadata or yes/no presence flags.
    """

    os: str  # "Darwin", "Linux", "Windows"
    arch: str  # "arm64", "x86_64"
    memory_gb: float | None  # rounded; None when undetected
    keys_present: dict[str, bool]  # provider name → has API key set
    ollama_running: bool
    network_reachable: bool  # OS route-table check only, no HEAD probe
    apple_fm_status: AppleFmStatus  # always "unknown" on CLI in v1


def _detect_memory_gb() -> float | None:
    """Return total system memory in GB via the existing hardware probe."""
    try:
        from bristlenose.utils.hardware import _get_system_memory_gb

        mem = _get_system_memory_gb()
        return round(mem, 1) if mem is not None else None
    except Exception:
        return None


def _probe_ollama_running() -> bool:
    """Cheap TCP-only probe — does someone hold the Ollama port?

    We don't import or call `check_ollama()` from `bristlenose/ollama.py`: that
    helper opens an HTTP connection to enumerate models, which is more work
    than the Pipeline view needs and risks shipping model names into a render
    that should be pure host facts. The route-table sense is enough.
    """
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.3):
            return True
    except OSError:
        return False


def _probe_network_reachable() -> bool:
    """OS route-table check only — no HEAD probe, no DNS lookup of a real host.

    We resolve a known-stable IP (`1.1.1.1` Cloudflare) via UDP, which doesn't
    send packets but does ask the kernel "is there a route to this address?"
    Returns False inside an air-gapped environment.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.3)
            sock.connect(("1.1.1.1", 80))
            return True
    except OSError:
        return False


def _probe_keys_present(settings: BristlenoseSettings) -> dict[str, bool]:
    """Return which provider API keys are set on the loaded settings."""
    return {
        "anthropic": bool(settings.anthropic_api_key),
        "openai": bool(settings.openai_api_key),
        "azure": bool(settings.azure_api_key),
        "google": bool(settings.google_api_key),
    }


def probe_host(settings: BristlenoseSettings) -> HostFacts:
    """Probe the local machine for Pipeline-view host facts.

    All probes are best-effort. Failures default to the safe value (False /
    None / "unknown"). Never raises.
    """
    return HostFacts(
        os=platform.system(),
        arch=platform.machine(),
        memory_gb=_detect_memory_gb(),
        keys_present=_probe_keys_present(settings),
        ollama_running=_probe_ollama_running(),
        network_reachable=_probe_network_reachable(),
        apple_fm_status="unknown",
    )
