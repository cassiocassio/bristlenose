"""The Windows installer build's own contracts (docs/design-winget.md).

packaging/windows/ is not a Python package (and must not shadow the `packaging`
library), so its lock script is loaded by path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "packaging" / "windows"


def _lock():
    spec = importlib.util.spec_from_file_location("bn_windows_lock", WIN / "lock.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_constraints_match_the_dependencies_they_were_compiled_from() -> None:
    """A dependency change without `python packaging/windows/lock.py` means the
    Windows build would install a set nothing compiled or tested."""
    lock = _lock()
    recorded = lock.recorded_digest((WIN / "constraints.txt").read_text(encoding="utf-8"))
    assert recorded == lock.inputs_digest(), (
        "pyproject.toml's dependencies changed: run `python packaging/windows/lock.py`"
    )


def test_the_digest_moves_when_a_dependency_does() -> None:
    lock = _lock()
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bumped = text.replace('"av<19"', '"av<20"', 1)
    assert bumped != text
    assert lock.inputs_digest(bumped) != lock.inputs_digest(text)


def test_the_build_installs_against_the_constraints() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert '"--constraint", $constraints' in build
