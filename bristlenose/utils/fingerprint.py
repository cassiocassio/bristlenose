"""A recording's identity: its bytes, not its name or where it sits.

``docs/design-project-identity.md`` §5. A researcher renames
``Recording 2026-10-02 1433.mp4`` to ``p1 sarah.mp4``, moves it into a
"Round 2" folder, or copies the study to another disk; none of that changes
which interview it is, and none of it changes its bytes. A re-export or a trim
does change the bytes, and is a different recording.

``v1:`` + 32 hex of SHA-256 over the size and the hashes of the first and last
MiB (the whole file below 2 MiB). Two MiB read per recording whatever its
length, so a study of twenty hour-long videos fingerprints in well under a
second. Modification time and name are deliberately absent: Finder, cloud sync
and copy tools rewrite the first, and the researcher rewrites the second.

A cloud placeholder (``utils.fs.is_dataless``) has no fingerprint: reading it
would download it, and nothing here may start a download. Callers fall back to
the last fingerprint they knew for the file's place.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from bristlenose.utils.fs import is_dataless

VERSION = "v1"
_EDGE = 1 << 20  # one MiB from each end


def content_fingerprint(path: Path) -> str | None:
    """The file's content fingerprint, or ``None`` if its bytes are not here."""
    if is_dataless(path):
        return None
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size <= 2 * _EDGE:
                parts = [hashlib.sha256(fh.read()).digest()]
            else:
                head = fh.read(_EDGE)
                fh.seek(size - _EDGE)
                tail = fh.read(_EDGE)
                parts = [hashlib.sha256(head).digest(), hashlib.sha256(tail).digest()]
    except OSError:
        return None
    digest = hashlib.sha256(str(size).encode("ascii") + b"|" + b"".join(parts)).hexdigest()
    return f"{VERSION}:{digest[:32]}"


def is_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(f"{VERSION}:"):
        return False
    body = value[len(VERSION) + 1:]
    return len(body) == 32 and all(c in "0123456789abcdef" for c in body)
