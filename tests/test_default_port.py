"""The serve port has one source (``bristlenose/ports.py``); copies must agree.

Files that cannot import Python carry the number as text. This fails when one
of them drifts, which is how 8150 outlived the move to 8484 in five places.
"""

from __future__ import annotations

import json
import re
import subprocess
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


def test_port_scan_starts_at_the_constant() -> None:
    import inspect

    from bristlenose.cli import _find_open_port

    start = inspect.signature(_find_open_port).parameters["start"].default
    assert start == DEFAULT_SERVE_PORT


def test_the_retired_default_is_gone_from_the_package() -> None:
    # 8150 was the default until 3 Nov 2026. A Python source still saying it is a
    # fallback that was never moved (the sweep below looks only for the new value).
    old = re.compile(r"\b8150\b")
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in (ROOT / "bristlenose").rglob("*.py")
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if old.search(line)]
    assert not hits, f"the retired default 8150 is still in: {hits}"


def test_dev_url_fallback_is_the_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    from bristlenose.server import app as server_app

    monkeypatch.delenv("_BRISTLENOSE_PORT", raising=False)
    seen: list[str] = []
    monkeypatch.setattr(server_app.logger, "info", lambda msg, *a, **k: seen.append(str(msg % a)))
    server_app._print_dev_urls()
    assert any(f"localhost:{DEFAULT_SERVE_PORT}/report/" in line for line in seen)


MIRRORS = {
    "frontend/vite.config.ts": r'"/[a-z]+": "http://localhost:(\d+)"',
    "e2e/playwright.config.ts": r"BN_E2E_PORT \?\? '(\d+)'",
    "frontend/src/components/SettingsModal.tsx": r'envVar: "_BRISTLENOSE_PORT", default: "(\d+)"',
    "experiments/icon-system/capture_icons.mjs": r"127\.0\.0\.1:(\d+)",
    "desktop/scripts/perf/profile-resize.sh": r"BRISTLENOSE_DEV_EXTERNAL_PORT:-(\d+)",
    "bristlenose/data/bristlenose.1": r"Port to serve on\. Default: \\fB(\d+)\\fR",
    "desktop/Bristlenose/Bristlenose.xcodeproj/xcshareddata/xcschemes/"
    "Bristlenose (External Server).xcscheme":
        r'key = "BRISTLENOSE_DEV_EXTERNAL_PORT"\s+value = "(\d+)"',
}


@pytest.mark.parametrize("path", sorted(MIRRORS))
def test_text_mirrors_carry_the_constant(path: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    found = {int(n) for n in re.findall(MIRRORS[path], text)}
    assert found, f"{path}: the pattern matched nothing, so it pins nothing"
    assert found == {DEFAULT_SERVE_PORT}, f"{path} carries {found}, not {DEFAULT_SERVE_PORT}"


def test_launch_json_serve_main_port() -> None:
    cfg = json.loads((ROOT / ".claude/launch.json").read_text(encoding="utf-8"))
    serve = next(c for c in cfg["configurations"] if c["name"] == "serve-main")
    assert serve["port"] == DEFAULT_SERVE_PORT


# ── the stray-literal sweep ──────────────────────────────────────────────
# MIRRORS only knows the copies someone listed. This finds the one nobody did.
# Code files only: prose (docs, changelog, TODO) is not a copy a program reads.
# The old value is not swept across the repo — 8150 is an arbitrary fixture port
# in the Swift tests and still in desktop/scripts/reset-sandbox-state.sh. The
# package itself is checked for it above.

SWEPT_SUFFIXES = (".py", ".ts", ".tsx", ".mjs", ".swift", ".sh", ".ps1",
                  ".yaml", ".yml", ".json", ".xcscheme", ".1", ".toml", ".plist",
                  ".html", ".js", ".cjs", ".mts", ".cfg", ".entitlements")
UNSWEPT_PREFIXES = ("docs/", "trial-runs/", "experiments/", ".claude/", "tests/",
                    "desktop/Bristlenose/Resources/", "desktop/build/", "frontend/trial-runs/")
# Copies that sit in a comment, so nothing reads them: they explain the port, not set it.
COMMENT_ONLY = {
    "snap/snapcraft.yaml",
    "packaging/windows/smoke.ps1",
    "desktop/scripts/reset-app-state.sh",
    "bristlenose/server/middleware.py",  # docstring examples of a rebinding Host
    "e2e/tests/lens-datum.spec.ts",
    "e2e/tests/lenses-load-clean.spec.ts",
}


def test_no_unlisted_copy_of_the_port() -> None:
    try:
        listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    known = set(MIRRORS) | COMMENT_ONLY | {"bristlenose/ports.py"}
    pattern = re.compile(rf"\b{DEFAULT_SERVE_PORT}\b")
    strays = []
    for rel in listed:
        if rel in known or not rel.endswith(SWEPT_SUFFIXES) or rel.startswith(UNSWEPT_PREFIXES):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                strays.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not strays, (
        f"{DEFAULT_SERVE_PORT} appears in code that no test pins. Import it from "
        "bristlenose/ports.py, or add the file to MIRRORS (or COMMENT_ONLY):\n"
        + "\n".join(strays)
    )
