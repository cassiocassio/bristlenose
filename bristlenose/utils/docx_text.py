"""The text of a Word document, tables included, in reading order.

``Document.paragraphs`` is only the body's own paragraphs: anything inside a
table — a transcript laid out as time | speaker | text, a discussion guide
laid out as question | probe — is not in it, and a reader built on it drops
that text without a word.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def block_texts(container: Any) -> Iterator[str]:
    """Yield each paragraph's text, body order, descending into tables.

    A table is read row by row, cell by cell, each cell's own content in
    order (nested tables included). A cell merged across columns appears once
    per row, not once per column it spans.
    """
    from docx.table import Table

    for block in container.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                seen: set[int] = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:  # a merged cell, repeated per column
                        continue
                    seen.add(id(cell._tc))
                    yield from block_texts(cell)
        else:
            yield block.text
