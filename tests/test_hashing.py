"""Tests for bristlenose.hashing — content hash utilities."""

from __future__ import annotations

import hashlib

from bristlenose.hashing import hash_bytes


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
