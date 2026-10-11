"""Which Ollama model names count as "installed" — Ollama's own rule.

Measured against a real Ollama (11 Oct 2026, /api/show): with only
``llama3.2:3b`` pulled, ``llama3.2`` and ``llama3.2:latest`` are 404 — a tag is
its own name even when the weights are identical, and a bare name means
``:latest``. Everything Bristlenose says about "installed" must agree, or
doctor passes a model the run then cannot load.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.ollama import DEFAULT_MODEL, ollama_has_model, validate_local_endpoint


@pytest.mark.parametrize(("name", "installed", "expected"), [
    ("llama3.2:3b", ["llama3.2:3b"], True),
    ("llama3.2", ["llama3.2:3b"], False),          # 404 on a real Ollama
    ("llama3.2:latest", ["llama3.2:3b"], False),   # 404 on a real Ollama
    ("gemma4", ["gemma4:latest"], True),           # 200 on a real Ollama
    ("gemma4:latest", ["gemma4:latest"], True),
    ("llama3.2:3b", ["llama3.2:1b"], False),
    ("llama3:8b", ["llama3.2:3b"], False),
    ("qwen2.5:7b", ["qwen2.5-coder:7b"], False),
])
def test_installed_means_what_ollama_means(name: str, installed: list[str], expected: bool) -> None:
    assert ollama_has_model(name, installed) is expected


def _tags(*names: str) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps({"models": [{"name": n} for n in names]}).encode()
    response.__enter__ = lambda self: self
    response.__exit__ = lambda *args: None
    return response


def test_doctor_does_not_pass_a_sibling_tag() -> None:
    """Was a prefix match on the part before the colon: llama3.2:1b passed
    for llama3.2:3b, and the run then failed with "model not pulled"."""
    with patch("urllib.request.urlopen", return_value=_tags("llama3.2:1b")):
        valid, err = validate_local_endpoint("http://localhost:11434/v1", "llama3.2:3b")
    assert valid is False
    assert "ollama pull llama3.2:3b" in err


def test_the_model_missing_fix_pulls_the_default_tag() -> None:
    """`ollama pull llama3.2` installs llama3.2:latest — not the llama3.2:3b
    the run asks for, so following the old advice left the run still failing."""
    from bristlenose.doctor_fixes import get_fix

    fix = get_fix("ollama_model_missing")
    assert f"ollama pull {DEFAULT_MODEL}" in fix
    assert "ollama pull llama3.2\n" not in fix


def test_setup_names_the_default_tag_when_a_download_fails(capsys: pytest.CaptureFixture[str]) -> None:
    from bristlenose.cli import _setup_local_provider
    from bristlenose.ollama import OllamaStatus

    status = OllamaStatus(is_running=True, has_suitable_model=False,
                          recommended_model=None, available_models=[], message="")
    with patch("bristlenose.ollama.check_ollama", return_value=status), \
            patch("rich.prompt.Confirm.ask", return_value=True), \
            patch("bristlenose.ollama.pull_model", return_value=False):
        assert _setup_local_provider() is None

    out = capsys.readouterr().out
    assert f"ollama pull {DEFAULT_MODEL}" in out
