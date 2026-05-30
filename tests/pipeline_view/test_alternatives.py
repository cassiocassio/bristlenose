"""Integration tests for the v1.5 alternatives surface.

Three scenarios cover the host shapes the alpha cohort runs on. Each asserts
the user-visible result (which backends ✓/✗ for which stages) rather than
locking implementation. The chosen-backend-sorts-first invariant and the
LLM-dedup-into-summary invariant are silent-regression surfaces, asserted
explicitly.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view import host as host_module
from bristlenose.pipeline_view.render import build_pipeline_view


@pytest.fixture(autouse=True)
def _clear_installed_packages_cache() -> None:
    """`_probe_installed_packages` is lru_cached per process — clear per test."""
    host_module._probe_installed_packages.cache_clear()
    yield
    host_module._probe_installed_packages.cache_clear()


def _settings(**overrides: object) -> BristlenoseSettings:
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-20250514",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "azure_api_key": "",
        "google_api_key": "",
        "whisper_backend": "auto",
        "whisper_model": "large-v3-turbo",
        "pii_enabled": False,
        "local_model": "llama3.2:3b",
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


def _patched_host(
    *,
    os_: str = "Darwin",
    arch: str = "arm64",
    os_version: str | None = "26.0",
    memory_gb: float | None = 32.0,
    ollama_running: bool = False,
    network_reachable: bool = True,
    installed_packages: dict[str, bool] | None = None,
):
    """Stack patches so `probe_host()` returns a deterministic shape."""
    packages = installed_packages or {
        "mlx_whisper": True,
        "ctranslate2": True,
        "presidio_analyzer": False,
        "en_core_web_lg": False,
    }
    return [
        patch("bristlenose.pipeline_view.host.platform.system", return_value=os_),
        patch("bristlenose.pipeline_view.host.platform.machine", return_value=arch),
        patch(
            "bristlenose.pipeline_view.host._detect_os_version",
            return_value=os_version,
        ),
        patch(
            "bristlenose.pipeline_view.host._detect_memory_gb",
            return_value=memory_gb,
        ),
        patch(
            "bristlenose.pipeline_view.host._probe_ollama_running",
            return_value=ollama_running,
        ),
        patch(
            "bristlenose.pipeline_view.host._probe_network_reachable",
            return_value=network_reachable,
        ),
        patch(
            "bristlenose.pipeline_view.host._probe_installed_packages",
            return_value=packages,
        ),
    ]


def _run_with_patches(patches, fn):
    """Apply a list of context managers and execute fn() inside."""
    if not patches:
        return fn()
    with patches[0]:
        return _run_with_patches(patches[1:], fn)


def test_apple_silicon_32gb_anthropic_only_key() -> None:
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    by_id = {a.id: a for a in view.llm_summary}
    assert by_id["claude"].available is True
    assert by_id["openai"].available is False and "openai" in (by_id["openai"].reason or "")
    assert by_id["azure"].available is False
    assert by_id["google"].available is False
    assert by_id["local"].available is False and "ollama" in (by_id["local"].reason or "")
    # Apple FM always ✗ on CLI — same reason key as the standalone row.
    assert by_id["apple_fm"].available is False
    assert "apple_fm_check_desktop" in (by_id["apple_fm"].reason or "")

    # Chosen-first sort invariant.
    assert view.llm_summary[0].id == "claude"


def test_all_keys_plus_ollama_running() -> None:
    settings = _settings(
        anthropic_api_key="a",
        openai_api_key="b",
        azure_api_key="c",
        azure_endpoint="https://x.openai.azure.com/",
        azure_deployment="gpt-4o",
        google_api_key="d",
    )
    patches = _patched_host(ollama_running=True)
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    by_id = {a.id: a for a in view.llm_summary}
    for provider in ("claude", "openai", "azure", "google", "local"):
        assert by_id[provider].available is True, (
            f"{provider} should be ✓ with all keys + ollama"
        )
    # Apple FM still ✗ on CLI — status is "unknown" regardless of OS/hardware.
    assert by_id["apple_fm"].available is False


def test_linux_cpu_no_keys() -> None:
    """faster-whisper available; MLX unavailable; every LLM alternative ✗."""
    settings = _settings()
    patches = _patched_host(
        os_="Linux",
        arch="x86_64",
        os_version=None,
        memory_gb=16.0,
        installed_packages={
            "mlx_whisper": False,
            "ctranslate2": True,
            "presidio_analyzer": False,
            "en_core_web_lg": False,
        },
    )
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    # Transcription has its own per-stage alternatives.
    transcription = next(s for s in view.catalogue if s.id == "transcription")
    by_id = {a.id: a for a in transcription.alternatives}
    assert by_id["faster-whisper"].available is True
    assert by_id["mlx"].available is False
    assert "apple_silicon" in (by_id["mlx"].reason or "")
    # Available sorts before unavailable.
    assert transcription.alternatives[0].available is True

    # LLM summary: all ✗.
    assert all(not a.available for a in view.llm_summary)


def test_llm_stages_alternatives_field_is_empty_after_dedup() -> None:
    """v1.5 dedup: per-stage LLM rows render `alternatives=[]`; summary card owns it."""
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    llm_stages = [s for s in view.catalogue if s.kind == "llm"]
    assert llm_stages, "expected at least one LLM stage in the catalogue"
    for stage in llm_stages:
        assert stage.alternatives == [], (
            f"LLM stage {stage.id} should have no per-stage alternatives "
            f"(host-wide summary owns this); got {stage.alternatives}"
        )


def test_chosen_backend_appears_first_when_available() -> None:
    """Sort invariant: chosen-id is index 0 if present and available."""
    settings = _settings(anthropic_api_key="sk-test", llm_provider="anthropic")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    assert view.llm_summary[0].id == "claude"
    assert view.llm_summary[0].available is True


def test_reason_is_none_when_available() -> None:
    """Silent invariant: available=True implies reason=None (no `title=null` leak)."""
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    for entry in view.llm_summary:
        if entry.available:
            assert entry.reason is None, (
                f"{entry.id} is available but carries a reason {entry.reason!r}"
            )


def test_anonymisation_per_stage_alternatives_keep_pii_toggle_separate() -> None:
    """Presidio is three Requirements: package + spaCy model + pii_enabled."""
    settings = _settings(pii_enabled=False)
    patches = _patched_host(
        installed_packages={
            "mlx_whisper": True,
            "ctranslate2": False,
            "presidio_analyzer": True,
            "en_core_web_lg": True,
        }
    )
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    anon = next(s for s in view.catalogue if s.id == "anonymisation")
    # Package + model are present, but pii_enabled is False — option ✗ with
    # the pii_disabled reason, not the install-missing reason.
    presidio = anon.alternatives[0]
    assert presidio.available is False
    assert "pii_disabled" in (presidio.reason or "")
