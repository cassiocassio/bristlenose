"""Tests for bristlenose.hashing — content hash utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path

from bristlenose.hashing import hash_bytes, hash_file_metadata


def test_hash_bytes_known_vector():
    """SHA-256 of 'hello' matches the known digest."""
    expected = hashlib.sha256(b"hello").hexdigest()
    assert hash_bytes(b"hello") == expected


def test_hash_bytes_empty():
    expected = hashlib.sha256(b"").hexdigest()
    assert hash_bytes(b"") == expected


def test_hash_bytes_deterministic():
    a = hash_bytes(b"bristlenose")
    b = hash_bytes(b"bristlenose")
    assert a == b


def test_hash_bytes_different_inputs():
    assert hash_bytes(b"a") != hash_bytes(b"b")


def test_hash_bytes_returns_hex_string():
    result = hash_bytes(b"test")
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest is 64 chars
    assert all(c in "0123456789abcdef" for c in result)


# ── hash_file_metadata (Phase 2c) ───────────────────────────────


def test_hash_file_metadata_deterministic(tmp_path: Path):
    f = tmp_path / "interview.mov"
    f.write_bytes(b"video data")
    a = hash_file_metadata([f])
    b = hash_file_metadata([f])
    assert a == b


def test_hash_file_metadata_detects_content_change(tmp_path: Path):
    f = tmp_path / "interview.mov"
    f.write_bytes(b"original video")
    h1 = hash_file_metadata([f])
    # Simulate trimming the video — different size
    f.write_bytes(b"trimmed")
    h2 = hash_file_metadata([f])
    assert h1 != h2


def test_hash_file_metadata_missing_file(tmp_path: Path):
    gone = tmp_path / "deleted.mov"
    h = hash_file_metadata([gone])
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_file_metadata_order_independent(tmp_path: Path):
    a = tmp_path / "a.mov"
    b = tmp_path / "b.mov"
    a.write_bytes(b"aaa")
    b.write_bytes(b"bbb")
    assert hash_file_metadata([a, b]) == hash_file_metadata([b, a])


def test_hash_file_metadata_detects_new_file(tmp_path: Path):
    f1 = tmp_path / "a.mov"
    f1.write_bytes(b"aaa")
    h1 = hash_file_metadata([f1])
    f2 = tmp_path / "b.mov"
    f2.write_bytes(b"bbb")
    h2 = hash_file_metadata([f1, f2])
    assert h1 != h2
