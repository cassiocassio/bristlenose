"""The serve port has one source (``bristlenose/ports.py``); copies must agree.

Files that cannot import Python carry the number as text. This fails when one
of them drifts, which is how 8150 outlived the move to 8484 in five places.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bristlenose.ports import DEFAULT_SERVE_PORT

ROOT = Path(__file__).resolve().parent.parent


def test_serve_option_default_is_the_constant() -> None:
    from typer.main import get_command

    from bristlenose.cli import app

    serve = get_command(app).commands["serve"]  # type: ignore[attr-defined]
    port = next(p for p in serve.params if p.name == "port")
    assert port.default == DEFAULT_SERVE_PORT


def test_dev_url_fallback_is_the_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    from bristlenose.server import app as server_app

    monkeypatch.delenv("_BRISTLENOSE_PORT", raising=False)
    seen: list[str] = []
    monkeypatch.setattr(server_app.logger, "info", lambda msg, *a, **k: seen.append(str(msg % a)))
    server_app._print_dev_urls()
    assert any(f"localhost:{DEFAULT_SERVE_PORT}/report/" in line for line in seen)


MIRRORS = {
    "frontend/vite.config.ts": r'"/(?:api|report)": "http://localhost:(\d+)"',
    "e2e/playwright.config.ts": r"BN_E2E_PORT \?\? '(\d+)'",
    "frontend/src/components/SettingsModal.tsx": r'envVar: "_BRISTLENOSE_PORT", default: "(\d+)"',
    "experiments/icon-system/capture_icons.mjs": r"127\.0\.0\.1:(\d+)",
    "desktop/Bristlenose/Bristlenose.xcodeproj/xcshareddata/xcschemes/"
    "Bristlenose (External Server).xcscheme": r'value = "(\d+)"',
}


@pytest.mark.parametrize("path", sorted(MIRRORS))
def test_text_mirrors_carry_the_constant(path: str) -> None:
    text = (ROOT / path).read_text()
    found = {int(n) for n in re.findall(MIRRORS[path], text)}
    assert DEFAULT_SERVE_PORT in found, f"{path} does not mention {DEFAULT_SERVE_PORT}"
    if path.startswith(("frontend/vite", "e2e/")):
        assert found == {DEFAULT_SERVE_PORT}, f"{path} has a stale port: {found}"


def test_launch_json_serve_main_port() -> None:
    cfg = json.loads((ROOT / ".claude/launch.json").read_text())
    serve = next(c for c in cfg["configurations"] if c["name"] == "serve-main")
    assert serve["port"] == DEFAULT_SERVE_PORT
