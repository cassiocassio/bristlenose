"""A recording's fingerprint: its bytes, never its name or mtime."""

from __future__ import annotations

import os
from pathlib import Path

from bristlenose.utils.fingerprint import content_fingerprint, is_fingerprint


def test_a_rename_or_copy_keeps_it_and_a_touch_does_not_move_it(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    a.write_bytes(b"interview bytes" * 1000)
    fp = content_fingerprint(a)
    assert fp is not None and is_fingerprint(fp)
    b = tmp_path / "sub" / "renamed.wav"
    b.parent.mkdir()
    a.rename(b)
    os.utime(b, (1, 1))
    assert content_fingerprint(b) == fp


def test_different_bytes_differ_at_the_head_the_tail_and_the_size(tmp_path: Path) -> None:
    big = 3 * (1 << 20)
    base = bytearray(b"x" * big)
    head, tail, longer = bytearray(base), bytearray(base), bytearray(base) + b"y"
    head[0] = ord("h")
    tail[-1] = ord("t")
    fps = set()
    for n, data in enumerate((base, head, tail, longer)):
        f = tmp_path / f"{n}.mov"
        f.write_bytes(bytes(data))
        fps.add(content_fingerprint(f))
    assert len(fps) == 4


def test_a_middle_edit_of_a_long_file_is_not_seen(tmp_path: Path) -> None:
    """By design: two MiB read per file. A trim or re-export changes an end."""
    big = 3 * (1 << 20)
    a, b = bytearray(b"x" * big), bytearray(b"x" * big)
    b[big // 2] = ord("m")
    (tmp_path / "a").write_bytes(bytes(a))
    (tmp_path / "b").write_bytes(bytes(b))
    assert content_fingerprint(tmp_path / "a") == content_fingerprint(tmp_path / "b")


def test_a_missing_file_has_none(tmp_path: Path) -> None:
    assert content_fingerprint(tmp_path / "gone.wav") is None
