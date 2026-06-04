"""Integration tests for the v2 per-model alternatives surface.

Three host scenarios cover the shapes the alpha cohort runs on. Each asserts
the user-visible result (which provider/model cells ✓/✗ for which stages)
rather than locking implementation.

v2 changes from v1.5/v1.9:
  - `view.llm_summary` is gone. Eligibility + quality resolve at (provider,
    model) grain; each LLM stage carries its own flat `alternatives` list.
  - Rows expose `provider_id` / `model_id` (was `id`) and `reason_key` (was
    `reason`).
  - No global quality sort — rows stay in catalogue declaration order;
    collapse-when-uniform is a render-layer concern.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view import host as host_module
from bristlenose.pipeline_view.render import ModelAvailability, build_pipeline_view


@pytest.fixture(autouse=True)
def _clear_installed_packages_cache() -> None:
    """`_probe_*` helpers are lru_cached per process — clear per test."""
    host_module._probe_installed_packages.cache_clear()
    host_module._probe_ollama_models.cache_clear()
    yield
    host_module._probe_installed_packages.cache_clear()
    host_module._probe_ollama_models.cache_clear()


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
    ollama_models: list[str] | None = None,
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
            "bristlenose.pipeline_view.host._probe_ollama_models",
            return_value=ollama_models or [],
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


def _provider_rows(
    rows: list[ModelAvailability],
) -> dict[str, list[ModelAvailability]]:
    """Group a stage's flat alternatives by provider_id, preserving order."""
    grouped: dict[str, list[ModelAvailability]] = {}
    for row in rows:
        grouped.setdefault(row.provider_id, []).append(row)
    return grouped


def _any_available(rows: list[ModelAvailability]) -> bool:
    return any(r.available for r in rows)


def test_apple_silicon_32gb_anthropic_only_key() -> None:
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    quote = next(s for s in view.catalogue if s.id == "quote_extraction")
    by_provider = _provider_rows(quote.alternatives)

    # Claude both models available (key present).
    assert _any_available(by_provider["claude"])
    assert all(r.available for r in by_provider["claude"])
    # Every other provider unavailable, each with the right fixable reason.
    assert not _any_available(by_provider["openai"])
    assert "no_openai_key" in (by_provider["openai"][0].reason_key or "")
    assert not _any_available(by_provider["azure"])
    assert not _any_available(by_provider["google"])
    assert not _any_available(by_provider["local"])
    assert "ollama_not_running" in (by_provider["local"][0].reason_key or "")
    # Apple FM always ✗ on CLI — structural, action_key None.
    assert not _any_available(by_provider["apple_fm"])
    assert "apple_fm_check_desktop" in (by_provider["apple_fm"][0].reason_key or "")
    assert by_provider["apple_fm"][0].action_key is None

    # Declaration order: Claude is the first provider in the catalogue.
    assert quote.alternatives[0].provider_id == "claude"


def test_all_keys_plus_ollama_running() -> None:
    settings = _settings(
        anthropic_api_key="a",
        openai_api_key="b",
        azure_api_key="c",
        azure_endpoint="https://x.openai.azure.com/",
        azure_deployment="gpt-4o",
        google_api_key="d",
    )
    patches = _patched_host(ollama_running=True, ollama_models=["llama3.2:3b"])
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    quote = next(s for s in view.catalogue if s.id == "quote_extraction")
    by_provider = _provider_rows(quote.alternatives)
    for provider in ("claude", "openai", "azure", "google", "local"):
        assert _any_available(by_provider[provider]), (
            f"{provider} should have an available row with all keys + ollama"
        )
    # Azure renders as a synthesised deployment row when fully configured.
    azure_row = by_provider["azure"][0]
    assert azure_row.synthesised is True
    assert azure_row.model_id == "gpt-4o"
    # Apple FM still ✗ on CLI — status is "unknown" regardless of OS/hardware.
    assert not _any_available(by_provider["apple_fm"])


def test_linux_cpu_no_keys() -> None:
    """faster-whisper available; MLX unavailable; every LLM cell ✗."""
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

    transcription = next(s for s in view.catalogue if s.id == "transcription")
    by_provider = _provider_rows(transcription.alternatives)
    assert by_provider["faster-whisper"][0].available is True
    assert by_provider["mlx"][0].available is False
    assert "requires_apple_silicon" in (by_provider["mlx"][0].reason_key or "")

    # Every LLM cell across every LLM stage is ✗.
    for stage in (s for s in view.catalogue if s.kind == "llm"):
        assert not _any_available(stage.alternatives), (
            f"{stage.id} should have no available cell with no keys"
        )


def test_llm_stages_carry_per_model_alternatives() -> None:
    """v2 inverts v1.5 dedup: each LLM stage owns its per-(provider, model) rows."""
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    llm_stages = [s for s in view.catalogue if s.kind == "llm"]
    assert llm_stages, "expected at least one LLM stage in the catalogue"
    for stage in llm_stages:
        assert stage.alternatives, (
            f"LLM stage {stage.id} should carry per-model alternatives in v2; "
            f"got {stage.alternatives}"
        )
        # Claude is catalogued with two models. Pin the count (the per-model
        # grain invariant), not the exact ids — those churn on model bumps and
        # are covered by test_models.py's declaration invariants.
        claude_rows = [r for r in stage.alternatives if r.provider_id == "claude"]
        assert len(claude_rows) == 2


def test_declaration_order_no_quality_sort() -> None:
    """v2 drops the v1.9 quality sort — providers stay in declaration order."""
    settings = _settings(
        llm_provider="local",
        anthropic_api_key="a",
        openai_api_key="b",
        google_api_key="d",
    )
    patches = _patched_host(ollama_running=True, ollama_models=["llama3.2:3b"])
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    quote = next(s for s in view.catalogue if s.id == "quote_extraction")
    # First appearance of each provider, in row order.
    seen: list[str] = []
    for row in quote.alternatives:
        if row.provider_id not in seen:
            seen.append(row.provider_id)
    assert seen == ["claude", "openai", "azure", "google", "local", "apple_fm"]


def test_reason_key_is_none_when_available() -> None:
    """Silent invariant: available=True implies reason_key/action_key None."""
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    for stage in view.catalogue:
        for row in stage.alternatives:
            if row.available:
                assert row.reason_key is None, (
                    f"{stage.id}/{row.provider_id}/{row.model_id} is available "
                    f"but carries reason_key {row.reason_key!r}"
                )
                assert row.action_key is None


def test_quality_fields_populate_from_catalogue() -> None:
    """Every catalogued row carries quality / quality_source + default/recommended."""
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    quote = next(s for s in view.catalogue if s.id == "quote_extraction")
    by_model = {r.model_id: r for r in quote.alternatives}

    sonnet = by_model["claude-sonnet-4-20250514"]
    assert sonnet.quality is not None
    assert sonnet.quality_source is not None
    assert sonnet.default is True  # BN's default model
    assert sonnet.recommended is True

    opus = by_model["claude-opus-4-20250514"]
    # First time recommended != default: Opus 4 is endorsed but not the default.
    assert opus.recommended is True
    assert opus.default is False

    # Apple FM stays unrated until a probe ships → quality None.
    apple = next(r for r in quote.alternatives if r.provider_id == "apple_fm")
    assert apple.quality is None
    assert apple.quality_source is None
    assert apple.default is False
    assert apple.recommended is False


def test_local_quality_splits_structural_vs_synthesis() -> None:
    """The v2 split that deleted llm_summary: Local is good for structural
    stages (speaker/topic), marginal for synthesis stages (quote/cluster/theme).
    """
    settings = _settings(llm_provider="local")
    patches = _patched_host(ollama_running=True, ollama_models=["llama3.2:3b"])
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    def _local_quality(stage_id: str) -> str | None:
        stage = next(s for s in view.catalogue if s.id == stage_id)
        row = next(
            r
            for r in stage.alternatives
            if r.provider_id == "local" and r.model_id == "llama3.2:3b"
        )
        return row.quality

    assert _local_quality("speaker_identification") == "good"
    assert _local_quality("topic_segmentation") == "good"
    assert _local_quality("quote_extraction") == "marginal"
    assert _local_quality("quote_clustering") == "marginal"
    assert _local_quality("thematic_grouping") == "marginal"


def test_pulled_ollama_models_synthesise_rows() -> None:
    """User-pulled Ollama models BN hasn't catalogued appear as synthesised rows."""
    settings = _settings(llm_provider="local")
    patches = _patched_host(
        ollama_running=True,
        ollama_models=["llama3.2:3b", "mistral:7b", "qwen2.5:14b"],
    )
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    quote = next(s for s in view.catalogue if s.id == "quote_extraction")
    local_rows = [r for r in quote.alternatives if r.provider_id == "local"]
    synthesised = [r for r in local_rows if r.synthesised]
    assert {r.model_id for r in synthesised} == {"mistral:7b", "qwen2.5:14b"}
    for row in synthesised:
        assert row.quality is None  # uncatalogued → untested


def test_transcription_quality_carries_note_keys() -> None:
    settings = _settings(anthropic_api_key="sk-test")
    patches = _patched_host()
    view = _run_with_patches(patches, lambda: build_pipeline_view(settings))

    transcription = next(s for s in view.catalogue if s.id == "transcription")
    by_provider = _provider_rows(transcription.alternatives)
    for opt_id in ("mlx", "faster-whisper"):
        row = by_provider[opt_id][0]
        assert row.quality is not None
        assert row.quality_note is not None
        assert row.quality_note.startswith("pipeline.quality.")


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
    assert "pii_disabled" in (presidio.reason_key or "")
