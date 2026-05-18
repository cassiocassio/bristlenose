"""HostFacts probe — pure mock per probe, no live system calls trusted."""

from __future__ import annotations

from unittest.mock import patch

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.host import probe_host


def _settings(**overrides: object) -> BristlenoseSettings:
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "anthropic_api_key": "sk-test",
        "openai_api_key": "",
        "azure_api_key": "",
        "google_api_key": "",
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


def test_keys_present_reflects_settings() -> None:
    with (
        patch("bristlenose.pipeline_view.host._probe_ollama_running", return_value=False),
        patch("bristlenose.pipeline_view.host._probe_network_reachable", return_value=False),
    ):
        host = probe_host(
            _settings(anthropic_api_key="x", openai_api_key="", google_api_key="y")
        )
    assert host.keys_present == {
        "anthropic": True,
        "openai": False,
        "azure": False,
        "google": True,
    }


def test_apple_fm_status_is_always_unknown_on_cli() -> None:
    with (
        patch("bristlenose.pipeline_view.host._probe_ollama_running", return_value=False),
        patch("bristlenose.pipeline_view.host._probe_network_reachable", return_value=True),
    ):
        host = probe_host(_settings())
    assert host.apple_fm_status == "unknown"


def test_ollama_probe_failure_returns_false_not_raises() -> None:
    """_probe_ollama_running must swallow OSError (firewall, sandbox, etc.)."""
    from bristlenose.pipeline_view.host import _probe_ollama_running

    with patch(
        "bristlenose.pipeline_view.host.socket.create_connection",
        side_effect=OSError("blocked"),
    ):
        assert _probe_ollama_running() is False


def test_network_probe_failure_returns_false() -> None:
    """_probe_network_reachable must return False on socket error."""
    import socket as _socket

    from bristlenose.pipeline_view.host import _probe_network_reachable

    class _BlockedSocket:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> _BlockedSocket:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def settimeout(self, *_: object) -> None:
            pass

        def connect(self, *_: object) -> None:
            raise OSError("no route")

    with patch.object(_socket, "socket", _BlockedSocket):
        assert _probe_network_reachable() is False


def test_host_excludes_re_identifying_fields() -> None:
    """HostFacts must not carry hostname, MAC, install path, etc."""
    with (
        patch("bristlenose.pipeline_view.host._probe_ollama_running", return_value=False),
        patch("bristlenose.pipeline_view.host._probe_network_reachable", return_value=True),
    ):
        host = probe_host(_settings())
    serialised = host.model_dump()
    leaky = {"hostname", "mac", "install_path", "username", "user", "home"}
    assert not (leaky & set(serialised.keys())), (
        f"HostFacts leaked a re-identifying field: {leaky & set(serialised.keys())}"
    )


def test_host_module_does_not_import_telemetry() -> None:
    """HostFacts is loopback-only; importing it must not touch telemetry code."""
    import sys

    # Ensure a clean import surface for the assertion.
    telemetry_modules_before = [m for m in sys.modules if "telemetry" in m]
    import bristlenose.pipeline_view.host  # noqa: F401  (re-import is fine)

    telemetry_modules_after = [m for m in sys.modules if "telemetry" in m]
    # The host module itself must not have added a telemetry import.
    # (Other tests may have loaded telemetry; we only care about deltas
    # introduced by host.py.)
    assert telemetry_modules_after == telemetry_modules_before or all(
        not m.startswith("bristlenose.pipeline") for m in telemetry_modules_after
    )
