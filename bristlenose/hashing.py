"""Content hashing utilities for pipeline integrity verification.

Phase 2a: SHA-256 hashes of stage output files, stored in the manifest.
Phase 2b: Verify stored hashes on load — detect corruption before trusting cache.
Phase 2c: Input change detection via file metadata hashing (size + mtime).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _canonical(path: Path) -> Path:
    """Best-effort resolved path.

    The hash must reflect file *identity*, not the spelling the caller passed.
    Without this, ``bristlenose run trial-runs/foo`` (relative) and
    ``run /abs/trial-runs/foo`` (absolute) produce different hashes for
    byte-identical inputs, so every stage re-runs (needless re-analysis + LLM
    spend).  ``resolve(strict=False)`` tolerates a missing leaf; ``OSError`` on
    an exotic/removed volume falls back to ``absolute()``.
    """
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def hash_file_metadata(paths: list[Path], *, relative_to: Path | None = None) -> str:
    """Hash file identity by (path, size, mtime_ns) — no content read.

    Uses the size+mtime fast path from the pipeline resilience design:
    if size or mtime changed, the file was modified.  Paths are resolved (so
    the hash is invariant to relative-vs-absolute spelling) and sorted for
    determinism.  Missing files include a ``MISSING`` sentinel so that file
    additions/deletions are detected.

    With ``relative_to`` (the project folder), the path part is the file's
    path *inside* that folder, so moving, renaming or copying the whole folder
    keeps every hash — the pipeline's transcription cache keys on this, and
    until 12 Oct 2026 the resolved absolute path was folded in, so a renamed
    study folder re-paid Whisper for every session in it. A file outside the
    folder contributes its name alone. Without ``relative_to`` the absolute
    form is used; the pipeline still computes that form to recognise a
    manifest written before the change.
    """
    root = _canonical(relative_to) if relative_to is not None else None
    parts: list[str] = []
    for p in sorted(_canonical(p) for p in paths):
        key = _path_key(p, root)
        if p.exists():
            st = p.stat()
            parts.append(f"{key}:{st.st_size}:{st.st_mtime_ns}")
        else:
            parts.append(f"{key}:MISSING")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _path_key(path: Path, root: Path | None) -> str:
    if root is None:
        return str(path)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


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
