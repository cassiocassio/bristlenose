"""Python side of the scan-selection contract (decision #111, 21 Oct 2026).

`tests/fixtures/scan-selection-contract.json` lays out folders and says which
files `run` selects from each. This file asserts the table against
`iter_scanned_files` + `classify_file`, the functions `run` itself uses;
`desktop/Bristlenose/BristlenoseTests/ScanSelectionTests.swift` asserts the same
table against the Mac's port, `ScanSelection.scannedFiles`. Between them the
Mac's "files to analyse" count and `run` cannot drift apart without one suite
failing. Sibling of `test_shared_format_contract.py`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from bristlenose.models import classify_file
from bristlenose.stages import s01_ingest
from bristlenose.stages.s01_ingest import UnsuitableInputDirError, iter_scanned_files

CONTRACT = Path(__file__).resolve().parent / "fixtures" / "scan-selection-contract.json"


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _layouts() -> list[dict[str, Any]]:
    return _contract()["layouts"]


def _build(base: Path, layout: dict[str, Any]) -> Path:
    root = base / layout.get("root_name", "study")
    root.mkdir(parents=True)
    for rel in layout.get("dirs", []):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in layout.get("files", []):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    for rel in layout.get("outside", []):
        path = base / "outside" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    for link in layout.get("links", []):
        at = root / link["at"]
        at.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(link["to"], at)
    return root


def test_the_contract_states_run_s_depth() -> None:
    assert _contract()["max_depth"] == s01_ingest._MAX_SCAN_DEPTH


@pytest.mark.parametrize("layout", _layouts(), ids=lambda layout: layout["name"])
def test_run_selects_what_the_contract_says(
    layout: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if layout.get("posix_links") and sys.platform == "win32":
        pytest.skip("symlinks need privileges on Windows")
    root = _build(tmp_path, layout)
    home = layout.get("home")
    if home is not None:
        home_dir = (root / home).resolve()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

    try:
        scanned = list(iter_scanned_files(root))
    except UnsuitableInputDirError:
        scanned = []  # run refuses the folder; the Mac counts nothing in it

    selected = sorted(p.relative_to(root).as_posix() for p in scanned)
    readable = sorted(
        p.relative_to(root).as_posix() for p in scanned if classify_file(p) is not None
    )
    assert selected == sorted(layout["selected"])
    assert readable == sorted(layout["readable"])


@pytest.mark.skipif(sys.platform != "darwin", reason="the roots are macOS paths")
@pytest.mark.parametrize(
    "case", _contract()["refusals"], ids=lambda case: case["path"]
)
def test_run_refuses_the_roots_the_contract_names(case: dict[str, Any]) -> None:
    refused = s01_ingest._refuse_reason(Path(case["path"])) is not None
    assert refused is case["refused"]
