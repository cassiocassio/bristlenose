"""Content hashing utilities for pipeline integrity verification.

Phase 2a: SHA-256 hashes of stage output files, stored in the manifest.
Phase 2c (future): file hashing, partial hashing for large media files,
input change detection.
"""

from __future__ import annotations

import hashlib


def hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()
