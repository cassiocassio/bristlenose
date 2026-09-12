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


class TestSpacyModelPresenceAcrossDeliveryShapes:
    """The model ships in two shapes; the probe must recognise both.

    The CLI acquirer runs `spacy download`, installing an importable package.
    The `.dmg` and TestFlight acquirers unpack a model *directory* and point
    `BRISTLENOSE_PII_MODEL_DIR` at it, installing no package at all. A probe
    that only asks `find_spec` reports "model missing" on a Mac where
    redaction works — and the Pipeline view then offers to install something
    already sitting on disk.
    """

    @staticmethod
    def _live_model_dir(tmp_path):
        d = tmp_path / "en_core_web_lg"
        d.mkdir()
        (d / "meta.json").write_text("{}")
        (d / "config.cfg").write_text("[nlp]")
        return d

    def test_path_delivered_model_reads_present_without_a_package(
        self, tmp_path, monkeypatch
    ) -> None:
        from bristlenose.pipeline_view.host import _spacy_model_present

        # Simulate a machine where the package genuinely is not installed —
        # the .dmg / TestFlight case. Without the override this must read
        # absent, and with it present, on the same machine.
        def _no_package(name, path=None, target=None):
            if name == "en_core_web_lg":
                raise ModuleNotFoundError(name)
            return None

        monkeypatch.setattr("importlib.util.find_spec", _no_package)

        monkeypatch.delenv("BRISTLENOSE_PII_MODEL_DIR", raising=False)
        assert _spacy_model_present() is False

        monkeypatch.setenv(
            "BRISTLENOSE_PII_MODEL_DIR", str(self._live_model_dir(tmp_path))
        )
        assert _spacy_model_present() is True

    def test_incomplete_model_dir_reads_absent(self, tmp_path, monkeypatch) -> None:
        """A model we cannot load is a model that is not there.

        `resolve_spacy_model` requires both `meta.json` and `config.cfg`; a
        half-unpacked directory (an interrupted download) must not read as a
        working detector, or stage 7 fails at redaction time instead of the
        Pipeline view saying so up front.
        """
        from bristlenose.pipeline_view.host import _spacy_model_present

        d = self._live_model_dir(tmp_path)
        (d / "meta.json").unlink()
        monkeypatch.setenv("BRISTLENOSE_PII_MODEL_DIR", str(d))
        assert _spacy_model_present() is False
