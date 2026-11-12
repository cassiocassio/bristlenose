"""The Python half of the contract the Mac's `FreshRunProbe` is held to.

The Mac restores a Re-analyse that was running at Quit or a crash as a plain Analyse once
the fresh run holds a session (owner, 12 Nov 2026). It cannot call Python, so it
re-implements `holds_an_analysed_session` and the set-aside folder's name; this
fixture, read here and by `FreshRunProbeTests.swift`, is what keeps the two together.
"""

import json
from pathlib import Path

import pytest

from bristlenose.utils.output_backup import backup_path_for, holds_an_analysed_session

_FIXTURE = Path(__file__).parent / "fixtures" / "fresh-run-probe-contract.json"
_CONTRACT = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_the_set_aside_folder_is_named_as_the_mac_expects(tmp_path: Path) -> None:
    output = tmp_path / _CONTRACT["outputDirName"]
    assert backup_path_for(output).name == _CONTRACT["setAsideDirName"]
    assert backup_path_for(output).parent == tmp_path


@pytest.mark.parametrize("case", _CONTRACT["cases"], ids=lambda c: c["name"])
def test_holds_an_analysed_session_matches_the_contract(case: dict, tmp_path: Path) -> None:
    dot = tmp_path / ".bristlenose"
    (dot / "intermediate").mkdir(parents=True)
    if case["manifest"] is not None:
        (dot / "pipeline-manifest.json").write_text(json.dumps(case["manifest"]), encoding="utf-8")
    if case["quotes"] is not None:
        (dot / "intermediate" / "extracted_quotes.json").write_text(
            json.dumps(case["quotes"]), encoding="utf-8"
        )
    assert holds_an_analysed_session(tmp_path) is case["holds"]
