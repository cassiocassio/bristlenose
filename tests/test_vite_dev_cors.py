"""``serve --dev``'s Vite server keeps its loopback-only CORS default.

Local pen-test finding 1 (26 Nov 2026): ``server.cors: true`` made Vite answer every origin
with ``Access-Control-Allow-Origin: *``, on the ``/report`` and ``/api`` responses it proxies to
serve as well. Any website the developer had open could read ``/report/``, take the bearer token
from it, and read and write the study through ``localhost:5173``. Vite's default admits only
``localhost``/``127.0.0.1``/``[::1]`` origins, which is all the 8484 -> 5173 module loads need.

Text checks, like ``test_default_port.py``'s read of the same file: importing the config under
vitest would load the React plugin for nothing. A CLI flag overrides the config, so the argv
``serve --dev`` launches Vite with is checked too. Out of reach: a Vite someone already started
by hand on 5173, which ``serve --dev`` adopts as it finds it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VITE_CONFIG = _ROOT / "frontend" / "vite.config.ts"
_CLI = _ROOT / "bristlenose" / "cli.py"

_WHY = (
    "reopens pen-test finding 1: Vite would let other origins read /report/ (which carries the "
    "token) through its proxy. If a cross-origin need is real, admit loopback origins only, e.g. "
    r"cors: { origin: /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/ }, and update this test."
)


def _config_code() -> str:
    """vite.config.ts with // and /* */ comments removed, so prose cannot trip the checks."""
    text = _VITE_CONFIG.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Not the `//` of "http://…" in a string, or a `cors:` after a URL on the same line hides.
    return re.sub(r"(?m)(?<!:)//.*$", "", text)


def _key(name: str) -> str:
    """An object key, bare or quoted: `cors:`, `"cors":`, `'cors':`."""
    return rf"""(?<![\w$])['"]?{name}['"]?\s*:"""


def test_vite_config_sets_no_cors_key() -> None:
    assert not re.search(_key("cors"), _config_code()), "vite.config.ts sets `cors`: " + _WHY


def test_vite_config_adds_no_allow_origin_header() -> None:
    assert "access-control-allow-origin" not in _config_code().lower(), _WHY


def test_vite_config_does_not_widen_hosts() -> None:
    code = _config_code()
    assert not re.search(_key("allowedHosts"), code), (
        "allowedHosts reopens DNS rebinding against the dev server"
    )
    assert not re.search(_key("host"), code), (
        "a `host:` key (hmr's included) can put the dev server off loopback; if one is needed, "
        "allow loopback values here"
    )


def _vite_argvs() -> list[list[object]]:
    """Every literal ``["npx", "vite", ...]`` list in cli.py."""
    found: list[list[object]] = []
    for node in ast.walk(ast.parse(_CLI.read_text(encoding="utf-8"))):
        if isinstance(node, ast.List) and len(node.elts) >= 2:
            head = [e.value for e in node.elts[:2] if isinstance(e, ast.Constant)]
            if head == ["npx", "vite"]:
                found.append([e.value if isinstance(e, ast.Constant) else "?" for e in node.elts])
    return found


def test_serve_dev_launches_vite_without_cors_or_host_flags() -> None:
    argvs = _vite_argvs()
    assert argvs, "no ['npx', 'vite', ...] argv found in cli.py: this test has lost its subject"
    for argv in argvs:
        flags = [a for a in argv if isinstance(a, str) and a.startswith(("--cors", "--host"))]
        assert not flags, f"serve --dev launches Vite with {flags}: " + _WHY
