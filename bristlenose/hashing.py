"""Content hashing utilities for pipeline integrity verification.

Phase 2a: SHA-256 hashes of stage output files, stored in the manifest.
Phase 2b: Verify stored hashes on load — detect corruption before trusting cache.
Phase 2c (future): file hashing, partial hashing for large media files,
input change detection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def verify_file_hash(path: Path, expected: str | None) -> bool:
    """Return True if *path*'s SHA-256 matches *expected*.

    Returns True when *expected* is ``None`` — backward compat with
    old manifests that predate content hashing (Phase 2a).
    Returns False when the file does not exist.
    """
    if expected is None:
        return True
    if not path.exists():
        return False
    return hash_bytes(path.read_bytes()) == expected
