"""A Word lock file is never a session (R120).

While a .docx is open, Word writes an owner file beside it: `~$` and the
name's tail, a few hundred bytes recording who has it open. It wears the
document's extension, so discovery took it for a second transcript and made a
session of it. Office's `~$` owner files are OS-like detritus, filtered with
the AppleDouble sidecars by `is_os_metadata`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.stages.s01_ingest import discover_files
from bristlenose.utils.fs import is_os_metadata


@pytest.mark.parametrize("name", ["~$terview 1.docx", "~$notes.xlsx", "~$deck.pptx"])
def test_an_office_owner_file_is_metadata(name: str) -> None:
    assert is_os_metadata(Path(name))


@pytest.mark.parametrize("name", ["Interview 1.docx", "$5 study.docx", "a~$b.docx"])
def test_a_document_is_not(name: str) -> None:
    assert not is_os_metadata(Path(name))


def test_a_word_lock_file_beside_its_document_is_not_discovered(tmp_path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Ana Souza   0:00\nShall we start?")
    doc.save(str(tmp_path / "Interview 1.docx"))
    # What Word writes while the document is open: the owner's name, padded.
    (tmp_path / "~$terview 1.docx").write_bytes(b"\x09Ana Souza" + b"\x00" * 153)
    assert [f.path.name for f in discover_files(tmp_path)] == ["Interview 1.docx"]
