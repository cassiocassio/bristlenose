"""The Mac app places the guide where the pipeline looks for it.

`DiscussionGuide.swift` copies a chosen guide into a folder by name, and the
Discussion stage finds it by name (`bristlenose/discussion/guide.py`). Two
spellings of one folder name, in two languages: the classic silent split, where
each side works and they never meet.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.discussion.guide import GUIDE_EXTENSIONS, GUIDE_FOLDER

_SWIFT = Path(__file__).parent.parent / "desktop/Bristlenose/Bristlenose/DiscussionGuide.swift"


def _swift() -> str:
    return _SWIFT.read_text(encoding="utf-8")


def test_the_folder_name_is_the_same_on_both_sides():
    m = re.search(r'static let folderName = "([^"]+)"', _swift())
    assert m and m.group(1) == GUIDE_FOLDER


def test_the_formats_are_the_same_on_both_sides():
    m = re.search(r"static let fileExtensions = \[([^\]]+)\]", _swift())
    assert m
    swift = {e.strip().strip('"') for e in m.group(1).split(",")}
    assert {"." + e for e in swift} == set(GUIDE_EXTENSIONS)
