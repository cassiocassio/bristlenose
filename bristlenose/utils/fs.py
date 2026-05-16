"""Filesystem helpers — name-based filters for OS metadata files."""

from __future__ import annotations

from pathlib import Path


def is_os_metadata(path: Path) -> bool:
    """True for OS-created metadata files that scanners should skip.

    Most importantly, AppleDouble sidecars (``._<name>``) which macOS Finder
    creates when copying files to filesystems that can't store xattrs/resource
    forks natively (ExFAT, FAT32, SMB shares, some NFS exports). They share the
    same extension as the user file they shadow, so an extension-based scanner
    will happily try to decode `._foo.mp4` as a video or `._s1.txt` as a
    transcript — both fail (binary blob, not the format the extension claims).

    Also filters ``.DS_Store`` for symmetry with Finder.
    """
    name = path.name
    return name.startswith("._") or name == ".DS_Store"
