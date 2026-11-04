"""Importing the CLI or the server must not pull in ``inflect``.

``inflect`` took ~0.84 s to import (``python -X importtime``, 4 Nov 2026) and
sat on every command's import path via ``bristlenose.utils.text``, so a
``serve`` start and a ``--help`` both paid it for a plural they never made.
``count_noun`` now builds the engine on first plural. A subprocess is the
only honest probe: ``sys.modules`` in the test process is already polluted.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from bristlenose.utils.text import count_noun


@pytest.mark.parametrize("module", ["bristlenose.cli", "bristlenose.server.app"])
def test_import_does_not_load_inflect(module: str) -> None:
    code = (
        f"import {module}, sys; "
        "sys.exit(1 if 'inflect' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"importing {module} loaded inflect again (~0.84 s on every command): "
        f"{result.stderr[-300:]}"
    )


def test_count_noun_still_pluralises_lazily() -> None:
    assert count_noun(1, "child") == "1 child"
    assert count_noun(2, "child") == "2 children"
    assert count_noun(0, "person") == "0 people"
    assert count_noun(3, "topic boundary") == "3 topic boundaries"
    assert count_noun(2, "x", plural="xen") == "2 xen"
