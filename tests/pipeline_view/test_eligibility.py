"""Eligibility predicate matrix.

The load-bearing test: every `Requirement.kind` value has at least one ok and
one not-ok case, plus boundary cases for the numeric kinds. Reasons are
asserted via substring match (`"Ollama" in reason`) so future agents don't
copy implementation-locking exemplars.
"""

from __future__ import annotations

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.catalogue import Requirement
from bristlenose.pipeline_view.eligibility import check_requirement
from bristlenose.pipeline_view.host import HostFacts


def _host(**overrides: object) -> HostFacts:
    defaults: dict[str, object] = {
        "os": "Darwin",
        "arch": "arm64",
        "os_version": "26.0",
        "memory_gb": 32.0,
        "keys_present": {"anthropic": True, "openai": False, "azure": False, "google": False},
        "installed_packages": {
            "mlx_whisper": True,
            "ctranslate2": False,
            "presidio_analyzer": False,
            "en_core_web_lg": False,
        },
        "ollama_running": False,
        "network_reachable": True,
        "apple_fm_status": "unknown",
    }
    defaults.update(overrides)
    return HostFacts(**defaults)  # type: ignore[arg-type]


def _settings(**overrides: object) -> BristlenoseSettings:
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "anthropic_api_key": "sk-test",
        "azure_endpoint": "",
        "azure_deployment": "",
        "pii_enabled": False,
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


# ── api_key ─────────────────────────────────────────────────────────────────

def test_api_key_present_passes() -> None:
    req = Requirement(kind="api_key", value="anthropic", reason_key="reasons.k")
    ok, reason, _action = check_requirement(req, _host(), _settings())
    assert ok and reason is None


def test_api_key_missing_fails_with_reason() -> None:
    req = Requirement(kind="api_key", value="openai", reason_key="reasons.no_openai")
    ok, reason, _action = check_requirement(req, _host(), _settings())
    assert not ok and "no_openai" in (reason or "")


# ── setting_present (truthy string fields like azure_endpoint) ──────────────

def test_setting_present_truthy_string_passes() -> None:
    req = Requirement(
        kind="setting_present",
        value="azure_endpoint",
        reason_key="reasons.endpoint",
    )
    ok, _, _ = check_requirement(req, _host(), _settings(azure_endpoint="https://x.openai.azure.com/"))
    assert ok


def test_setting_present_empty_string_fails() -> None:
    req = Requirement(
        kind="setting_present", value="azure_endpoint", reason_key="reasons.endpoint"
    )
    ok, reason, _action = check_requirement(req, _host(), _settings(azure_endpoint=""))
    assert not ok and "endpoint" in (reason or "")


# ── setting_enabled (bool) ──────────────────────────────────────────────────

def test_setting_enabled_true_passes() -> None:
    req = Requirement(
        kind="setting_enabled", value="pii_enabled", reason_key="reasons.pii"
    )
    ok, _, _ = check_requirement(req, _host(), _settings(pii_enabled=True))
    assert ok


def test_setting_enabled_false_fails() -> None:
    req = Requirement(
        kind="setting_enabled", value="pii_enabled", reason_key="reasons.pii"
    )
    ok, reason, _action = check_requirement(req, _host(), _settings(pii_enabled=False))
    assert not ok and "pii" in (reason or "")


# ── hardware (apple_silicon / cuda) ─────────────────────────────────────────

def test_hardware_apple_silicon_passes_on_arm_darwin() -> None:
    req = Requirement(
        kind="hardware", value="apple_silicon", reason_key="reasons.apple"
    )
    ok, _, _ = check_requirement(req, _host(os="Darwin", arch="arm64"), _settings())
    assert ok


def test_hardware_apple_silicon_fails_on_intel_mac() -> None:
    req = Requirement(
        kind="hardware", value="apple_silicon", reason_key="reasons.apple"
    )
    ok, reason, _action = check_requirement(req, _host(os="Darwin", arch="x86_64"), _settings())
    assert not ok and "apple" in (reason or "")


def test_hardware_apple_silicon_fails_on_linux() -> None:
    req = Requirement(
        kind="hardware", value="apple_silicon", reason_key="reasons.apple"
    )
    ok, _, _ = check_requirement(req, _host(os="Linux", arch="x86_64"), _settings())
    assert not ok


def test_hardware_cuda_unsupported_in_v1_5() -> None:
    """CUDA always fails — v1.5 doesn't probe it; explicit documented limit."""
    req = Requirement(kind="hardware", value="cuda", reason_key="reasons.cuda")
    ok, _, _ = check_requirement(req, _host(), _settings())
    assert not ok


# ── os ──────────────────────────────────────────────────────────────────────

def test_os_match_passes() -> None:
    req = Requirement(kind="os", value="Darwin", reason_key="reasons.os")
    ok, _, _ = check_requirement(req, _host(os="Darwin"), _settings())
    assert ok


def test_os_mismatch_fails() -> None:
    req = Requirement(kind="os", value="Darwin", reason_key="reasons.os")
    ok, _, _ = check_requirement(req, _host(os="Linux"), _settings())
    assert not ok


# ── min_ram_gb (boundary cases) ─────────────────────────────────────────────

def test_min_ram_at_boundary_passes() -> None:
    req = Requirement(kind="min_ram_gb", value=16, reason_key="reasons.ram")
    ok, _, _ = check_requirement(req, _host(memory_gb=16.0), _settings())
    assert ok


def test_min_ram_below_boundary_fails() -> None:
    req = Requirement(kind="min_ram_gb", value=16, reason_key="reasons.ram")
    ok, _, _ = check_requirement(req, _host(memory_gb=15.9), _settings())
    assert not ok


def test_min_ram_undetected_fails() -> None:
    req = Requirement(kind="min_ram_gb", value=16, reason_key="reasons.ram")
    ok, _, _ = check_requirement(req, _host(memory_gb=None), _settings())
    assert not ok


# ── ollama_running ──────────────────────────────────────────────────────────

def test_ollama_running_true_passes() -> None:
    req = Requirement(kind="ollama_running", value=True, reason_key="reasons.ollama")
    ok, _, _ = check_requirement(req, _host(ollama_running=True), _settings())
    assert ok


def test_ollama_running_false_fails() -> None:
    req = Requirement(kind="ollama_running", value=True, reason_key="reasons.ollama")
    ok, reason, _action = check_requirement(req, _host(ollama_running=False), _settings())
    assert not ok and "ollama" in (reason or "").lower()


# ── python_package (reads from host.installed_packages, not find_spec) ──────

def test_python_package_installed_passes() -> None:
    req = Requirement(
        kind="python_package", value="mlx_whisper", reason_key="reasons.mlx"
    )
    ok, _, _ = check_requirement(req, _host(), _settings())
    assert ok


def test_python_package_missing_fails() -> None:
    req = Requirement(
        kind="python_package", value="presidio_analyzer", reason_key="reasons.presidio"
    )
    ok, reason, _action = check_requirement(req, _host(), _settings())
    assert not ok and "presidio" in (reason or "")


def test_python_package_not_in_probe_set_treated_as_missing() -> None:
    """If a package isn't in installed_packages dict at all, treat as missing."""
    req = Requirement(
        kind="python_package", value="unknown_pkg", reason_key="reasons.unknown"
    )
    ok, _, _ = check_requirement(req, _host(), _settings())
    assert not ok


# ── min_os_version (boundary cases) ─────────────────────────────────────────

def test_min_os_version_at_boundary_passes() -> None:
    req = Requirement(kind="min_os_version", value=26.0, reason_key="reasons.osv")
    ok, _, _ = check_requirement(req, _host(os_version="26.0"), _settings())
    assert ok


def test_min_os_version_above_boundary_passes() -> None:
    req = Requirement(kind="min_os_version", value=26.0, reason_key="reasons.osv")
    ok, _, _ = check_requirement(req, _host(os_version="26.1"), _settings())
    assert ok


def test_min_os_version_below_boundary_fails() -> None:
    req = Requirement(kind="min_os_version", value=26.0, reason_key="reasons.osv")
    ok, _, _ = check_requirement(req, _host(os_version="25.4"), _settings())
    assert not ok


def test_min_os_version_none_fails() -> None:
    """Non-Darwin reports `os_version=None`; predicate must not crash."""
    req = Requirement(kind="min_os_version", value=26.0, reason_key="reasons.osv")
    ok, _, _ = check_requirement(req, _host(os_version=None), _settings())
    assert not ok


def test_min_os_version_malformed_string_fails_gracefully() -> None:
    req = Requirement(kind="min_os_version", value=26.0, reason_key="reasons.osv")
    ok, _, _ = check_requirement(req, _host(os_version="not-a-version"), _settings())
    assert not ok


# ── apple_fm_status ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "status,expected_ok",
    [("available", True), ("unavailable", False), ("unknown", False)],
)
def test_apple_fm_status_only_available_passes(status: str, expected_ok: bool) -> None:
    req = Requirement(
        kind="apple_fm_status", value="available", reason_key="reasons.fm"
    )
    ok, _, _ = check_requirement(req, _host(apple_fm_status=status), _settings())
    assert ok is expected_ok
