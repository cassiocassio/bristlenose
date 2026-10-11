"""Installing Ollama with the official script: a failed download is a failure."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from bristlenose import ollama


class _Runs:
    """Stands in for subprocess.run and records each command."""

    def __init__(self, curl_code: int, curl_out: bytes, sh_code: int = 0) -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self.curl_code, self.curl_out, self.sh_code = curl_code, curl_out, sh_code

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((cmd, kwargs))
        if cmd[0] == "curl":
            return subprocess.CompletedProcess(cmd, self.curl_code, self.curl_out, b"")
        return subprocess.CompletedProcess(cmd, self.sh_code, b"", b"")


def test_a_failed_download_is_not_reported_as_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """`curl … | sh` without pipefail exits with sh's status: an empty script
    runs cleanly, so a failed download used to read as a successful install."""
    runs = _Runs(curl_code=22, curl_out=b"")
    monkeypatch.setattr(ollama.subprocess, "run", runs)

    assert ollama.install_ollama("curl") is False
    assert [c[0][0] for c in runs.calls] == ["curl"]  # nothing was run


def test_the_downloaded_script_is_what_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = _Runs(curl_code=0, curl_out=b"#!/bin/sh\necho installing\n")
    monkeypatch.setattr(ollama.subprocess, "run", runs)

    assert ollama.install_ollama("curl") is True
    (curl, _), (sh, sh_kwargs) = runs.calls
    assert "https://ollama.com/install.sh" in curl
    assert sh == ["sh"] and sh_kwargs["input"] == b"#!/bin/sh\necho installing\n"


def test_a_failing_script_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama.subprocess, "run",
                        _Runs(curl_code=0, curl_out=b"exit 1\n", sh_code=1))
    assert ollama.install_ollama("curl") is False
