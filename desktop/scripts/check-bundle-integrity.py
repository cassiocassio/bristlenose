#!/usr/bin/env python3
"""Fail if any Mach-O in the sidecar bundle has a hole in its executable code.

WHY THIS EXISTS
---------------
On 30 Aug 2026 the shipped sidecar crashed seconds into every transcription with
`EXC_BAD_INSTRUCTION (SIGILL)` in `llvm::InstCombinerImpl::visitOr`. The cause was
not code, entitlements, signing or the sandbox — it was a corrupt file.

PyInstaller shells out to `strip` for each collected binary and never checks its
exit status. That day strip died of SIGBUS inside `writeout_to_mem` partway
through rewriting `llvmlite/binding/libllvmlite.dylib`, having already created the
output. PyInstaller collected the result: a dylib of exactly the right size with
16,384 bytes of ZEROS at offset 0x02b20000, inside `__TEXT,__text`. On arm64 an
all-zero word is `udf #0` — permanently undefined — so the first JIT compilation
that executed into that page raised SIGILL.

Every gate in the build was green. `codesign -v --strict` passes on a corrupt
dylib, because it was signed *after* the damage. Size looks right. `otool -L` and
the install name are unchanged. The only evidence was a crash report, and the
failure log rendered the signal as though it were an exit code (`status=4`).

`strip` is off in the spec now, which removes that specific mechanism. This gate
is the general one: it asserts that no shipped executable code contains a run of
zeros big enough to be a hole, whatever put it there.

WHAT IT CHECKS
--------------
For every Mach-O in the bundle, scan the `__TEXT,__text` section — machine code
and nothing else — for a run of at least --min-run zero bytes (default 4096, one
page). Compiled arm64 code does not contain a page of zeros; padding lives in
other sections, which is why this looks only at `__text`.

Exit 0 clean, 1 on a hole, 2 on a usage/parse error.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
LC_SEGMENT_64 = 0x19

# One page. Below this, a legitimate alignment gap between functions could in
# principle trip the check; at or above it, nothing benign explains the run.
DEFAULT_MIN_RUN = 4096


def _text_sections(blob: bytes) -> list[tuple[int, int]]:
    """File-offset ranges of __TEXT,__text in a thin Mach-O. Empty if not one."""
    if len(blob) < 32:
        return []
    (magic,) = struct.unpack_from("<I", blob, 0)
    if magic == MH_CIGAM_64:  # big-endian 64-bit; we ship arm64 only
        return []
    if magic != MH_MAGIC_64:
        return []

    ncmds = struct.unpack_from("<I", blob, 16)[0]
    out: list[tuple[int, int]] = []
    off = 32
    for _ in range(ncmds):
        if off + 8 > len(blob):
            break
        cmd, cmdsize = struct.unpack_from("<II", blob, off)
        if cmdsize <= 0:
            break
        if cmd == LC_SEGMENT_64:
            segname = blob[off + 8 : off + 24].rstrip(b"\0").decode("ascii", "replace")
            nsects = struct.unpack_from("<I", blob, off + 64)[0]
            sec = off + 72
            for _ in range(nsects):
                if sec + 80 > len(blob):
                    break
                sectname = blob[sec : sec + 16].rstrip(b"\0").decode("ascii", "replace")
                size = struct.unpack_from("<Q", blob, sec + 40)[0]
                offset = struct.unpack_from("<I", blob, sec + 48)[0]
                if segname == "__TEXT" and sectname == "__text" and size:
                    out.append((offset, size))
                sec += 80
        off += cmdsize
    return out


def _longest_zero_run(blob: bytes, start: int, size: int, threshold: int) -> tuple[int, int] | None:
    """First zero run >= threshold within [start, start+size). None if clean."""
    end = min(start + size, len(blob))
    i = start
    while i < end:
        if blob[i]:
            i += 1
            continue
        run_start = i
        while i < end and not blob[i]:
            i += 1
        if i - run_start >= threshold:
            return run_start, i - run_start
    return None


def scan(path: Path, threshold: int) -> tuple[int, int] | None:
    """(offset, length) of the first hole in this file's code, or None."""
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    if len(blob) >= 4 and struct.unpack_from(">I", blob, 0)[0] in (FAT_MAGIC, FAT_CIGAM):
        # Universal binary. We build arm64-only, so this should not appear; say so
        # rather than silently passing a file we did not actually inspect.
        print(f"  ! universal binary, not inspected: {path}", file=sys.stderr)
        return None
    for offset, size in _text_sections(blob):
        hit = _longest_zero_run(blob, offset, size, threshold)
        if hit:
            return hit
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", type=Path, help="directory to walk (the sidecar bundle)")
    ap.add_argument("--min-run", type=int, default=DEFAULT_MIN_RUN,
                    help=f"zero-run length that counts as a hole (default {DEFAULT_MIN_RUN})")
    args = ap.parse_args()

    if not args.bundle.is_dir():
        print(f"error: not a directory: {args.bundle}", file=sys.stderr)
        return 2

    checked = 0
    bad: list[tuple[Path, int, int]] = []
    for p in sorted(args.bundle.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        try:
            with p.open("rb") as fh:
                head = fh.read(4)
        except OSError:
            continue
        if len(head) < 4:
            continue
        if struct.unpack("<I", head)[0] not in (MH_MAGIC_64, MH_CIGAM_64) and \
           struct.unpack(">I", head)[0] not in (FAT_MAGIC, FAT_CIGAM):
            continue
        checked += 1
        hit = scan(p, args.min_run)
        if hit:
            bad.append((p, hit[0], hit[1]))

    if not checked:
        print(f"error: no Mach-O files found under {args.bundle} — wrong path?", file=sys.stderr)
        return 2

    if bad:
        print(f"✗ bundle integrity: {len(bad)} of {checked} Mach-O files have a hole in __TEXT,__text")
        for p, off, length in bad:
            print(f"    {p}")
            print(f"      {length:,} zero bytes at offset 0x{off:08x} ({off:,})")
        print()
        print("  This is a CORRUPT BINARY, not a code defect. Executing into that")
        print("  region raises SIGILL. Rebuild the sidecar; if it recurs, check")
        print("  whether the build is stripping (it should not be — see the spec).")
        return 1

    print(f"✓ bundle integrity: {checked} Mach-O files, no holes in executable code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
