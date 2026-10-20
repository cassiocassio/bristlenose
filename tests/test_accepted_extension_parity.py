"""Mechanical parity between the Python and Swift accepted-extension sets.

Four surfaces decide whether a file is "one of ours", in two languages that
cannot share a constant. They drifted: `ProjectFolderWatcher` carried nine
extensions while drag-and-drop accepted seventeen, so a dropped `.mkv` was
accepted, copied and analysed — and then invisible to the watcher, meaning no
new-files count and no missing-file warning for the rest of its life. The two
sets were written in separate commits and nothing ever compared them.

This is the comparison. It parses the Swift literals rather than duplicating
them, so the test fails when the source drifts, not when someone forgets to
update a copy in the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.models import ALL_EXTENSIONS

REPO = Path(__file__).resolve().parents[1]
SWIFT = REPO / "desktop" / "Bristlenose" / "Bristlenose"

# Accepted by drag-and-drop but not by the pipeline: a dropped .txt is carried
# into the project folder as a companion note. Deliberate, and the only
# permitted difference between the Swift sets and ALL_EXTENSIONS.
COMPANION_EXTENSIONS = {"txt"}


def _swift_string_set(source: Path, symbol: str) -> set[str]:
    """Extract a `static let <symbol>: Set<String> = [ … ]` literal."""
    text = source.read_text(encoding="utf-8")
    match = re.search(
        rf"static let {re.escape(symbol)}\s*:\s*Set<String>\s*=\s*\[(.*?)\]",
        text,
        re.DOTALL,
    )
    assert match, f"{symbol} not found in {source.name} — was it renamed?"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


@pytest.fixture(scope="module")
def canonical() -> set[str]:
    return {ext.lstrip(".") for ext in ALL_EXTENSIONS}


def test_drag_drop_accepts_everything_the_pipeline_can_read(canonical: set[str]) -> None:
    accepted = _swift_string_set(SWIFT / "ContentView.swift", "acceptedExtensions")
    missing = canonical - accepted
    assert not missing, (
        f"drag-and-drop refuses {sorted(missing)}, which the pipeline can analyse"
    )
    assert accepted - canonical <= COMPANION_EXTENSIONS


def test_folder_watcher_sees_everything_drag_drop_accepts() -> None:
    """The defect this file exists for.

    A file the watcher cannot see gets no new-files count when it appears and no
    warning when it vanishes, even though it was ingested and analysed.
    """
    accepted = _swift_string_set(SWIFT / "ContentView.swift", "acceptedExtensions")
    watched = _swift_string_set(SWIFT / "ProjectFolderWatcher.swift", "eligibleExtensions")
    blind_spots = accepted - watched
    assert not blind_spots, (
        f"the folder watcher is blind to {sorted(blind_spots)} — these can be "
        "dropped, copied and analysed, but will never raise a new-files count "
        "or a missing-file warning"
    )


def test_cloud_import_scan_covers_the_media_it_may_encounter(canonical: set[str]) -> None:
    """`mediaExtensions` scans a destination folder, so it must cover real media.

    Narrower than the others by design — it carries no subtitle or document
    types, because it answers "is this a recording?" and not "would we ingest
    this?". Only the media half of the canonical set is asserted.
    """
    media = _swift_string_set(SWIFT / "CloudImportLocalMatch.swift", "mediaExtensions")
    canonical_media = canonical - {"srt", "vtt", "docx"} - COMPANION_EXTENSIONS
    missing = canonical_media - media
    assert not missing, (
        f"cloud-import destination scan cannot see {sorted(missing)}; a local file "
        "in one of these formats will never be matched to its remote row"
    )


_DOTTED = re.compile(r"(?<![\w.])\.([a-z0-9]+)\b")


def test_help_lists_exactly_what_the_pipeline_reads(canonical: set[str]) -> None:
    """`bristlenose help workflows` names the input formats in prose.

    It said `.txt (plain text)` was an accepted transcript while ingest declines
    every `.txt` ("Not a format Bristlenose reads"), so a researcher following
    the help got a run that analysed nothing (20 Oct 2026).
    """
    from typer.testing import CliRunner

    from bristlenose.cli import app

    result = CliRunner().invoke(app, ["help", "workflows"])
    assert result.exit_code == 0, result.output
    out = result.output
    block = out.split("Input files", 1)[1].split("Files sharing", 1)[0]
    assert set(_DOTTED.findall(block)) == canonical


def test_man_page_lists_exactly_what_the_pipeline_reads(canonical: set[str]) -> None:
    """The man page carries the same list, in its own `.nf` block."""
    man = (REPO / "bristlenose" / "data" / "bristlenose.1").read_text(encoding="utf-8")
    man = re.sub(r"\\f[BIRP]", "", man.replace("\\-", "-"))
    after = man.split("accepts any mix of audio, video, subtitle, and transcript files", 1)[1]
    block = after.split("\n.nf\n", 1)[1].split("\n.fi\n", 1)[0]
    assert set(_DOTTED.findall(block)) == canonical
