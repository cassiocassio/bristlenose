#!/usr/bin/env python3
"""App Store §2.5.2 static-string gate for the PyInstaller sidecar.

App Store Connect runs an automated static scan that rejects any binary
CONTAINING the literal ``itms-services`` — "the app uses the itms-services
URL scheme to install an app" — even when the code is never executed. CPython
ships that literal in ``Lib/urllib/parse.py`` (the known-URL-scheme lists);
Homebrew's python@3.12 is not built with ``--with-app-store-compliance``, so
the literal freezes into the sidecar's ``urllib.parse``. The spec
(``desktop/bristlenose-sidecar.spec``) strips it at freeze time; this gate is
the independent backstop that verifies the *assembled* bundle is clean.

The literal lives marshalled inside the module's code object, and the PYZ is
zlib-compressed, so ``strings``/``grep`` on the bundle returns a FALSE
NEGATIVE. This scanner therefore:

  1. Extracts the PYZ from the sidecar executable (PyInstaller CArchive),
     decompresses every frozen module, and recursively scans its code-object
     constants (including strings nested inside tuple/list constants — where
     module-level scheme lists actually live).
  2. Byte-scans the on-disk bundle files for good measure (catches any
     uncompressed occurrence in a .so / data file).

Exit codes: 0 clean · 1 needle found (prints the carriers) · 2 usage / can't
locate the PYZ.

Usage:
    check-sidecar-appstore-strings.py <sidecar-exe | sidecar-dir | .app | .xcarchive>
"""

from __future__ import annotations

import marshal
import os
import sys
from pathlib import Path

# The App-Store-rejected literals. Keep in sync with the spec's strip patch.
NEEDLES = ("itms-services",)


def _find_sidecar_exe(target: Path) -> Path | None:
    """Resolve a sidecar executable from any of the accepted inputs."""
    if target.is_file():
        return target

    candidates: list[Path] = []
    if target.is_dir():
        name = target.name
        # PyInstaller --onedir: <dir>/<dir-name> is the executable.
        candidates.append(target / "bristlenose-sidecar")
        if name.endswith(".app"):
            candidates.append(
                target / "Contents" / "Resources" / "bristlenose-sidecar" / "bristlenose-sidecar"
            )
        if name.endswith(".xcarchive"):
            apps = list((target / "Products" / "Applications").glob("*.app"))
            for app in apps:
                candidates.append(
                    app / "Contents" / "Resources" / "bristlenose-sidecar" / "bristlenose-sidecar"
                )
    for c in candidates:
        if c.is_file():
            return c
    return None


def _iter_strings(obj):
    """Recurse into code objects AND container constants (tuple/list/set)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, (tuple, list, set, frozenset)):
        for c in obj:
            yield from _iter_strings(c)
    elif hasattr(obj, "co_consts"):
        for c in obj.co_consts:
            yield from _iter_strings(c)


def _scan_pyz(exe: Path) -> list[tuple[str, str]]:
    """Return [(module, needle)] for every frozen module carrying a needle."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    car = CArchiveReader(str(exe))
    pyz_name = next((n for n in car.toc if n.lower().endswith(".pyz")), None)
    if pyz_name is None:
        raise SystemExit(f"error: no PYZ archive found inside {exe}")

    data = car.extract(pyz_name)
    if isinstance(data, tuple):
        data = data[1]

    # Write to a system temp file — never into the (possibly read-only /
    # signature-sensitive) bundle directory.
    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".pyz", prefix="appstore-gate-")
    workpyz = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        zar = ZlibArchiveReader(str(workpyz))
        hits: list[tuple[str, str]] = []
        for name in list(zar.toc):
            try:
                entry = zar.extract(name)
                code = entry[1] if isinstance(entry, tuple) else entry
                if isinstance(code, (bytes, bytearray)):
                    code = marshal.loads(code)
                if not hasattr(code, "co_consts"):
                    continue
                found = {s for s in _iter_strings(code) for n in NEEDLES if n in s}
                for n in NEEDLES:
                    if any(n in s for s in found):
                        hits.append((name, n))
            except Exception:
                # Package markers / namespace entries have no code object.
                continue
        return hits
    finally:
        workpyz.unlink(missing_ok=True)


def _scan_ondisk(root: Path) -> list[tuple[str, str]]:
    """Raw byte-scan of on-disk bundle files (uncompressed occurrences)."""
    hits: list[tuple[str, str]] = []
    needles_b = [(n, n.encode()) for n in NEEDLES]
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = Path(dirpath) / f
            try:
                blob = p.read_bytes()
            except OSError:
                continue
            for n, nb in needles_b:
                if nb in blob:
                    hits.append((str(p.relative_to(root)), n))
    return hits


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {os.path.basename(argv[0])} <sidecar|app|xcarchive>", file=sys.stderr)
        return 2

    target = Path(argv[1]).resolve()
    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 2

    exe = _find_sidecar_exe(target)
    if exe is None:
        print(f"error: could not locate a sidecar executable under {target}", file=sys.stderr)
        return 2

    bundle_root = exe.parent  # the --onedir directory

    pyz_hits = _scan_pyz(exe)
    disk_hits = _scan_ondisk(bundle_root)

    if pyz_hits or disk_hits:
        print("FAIL: App-Store-noncompliant URL-scheme literal found in the sidecar.", file=sys.stderr)
        print("App Store Connect's static scan (§2.5.2) rejects binaries containing", file=sys.stderr)
        print("'itms-services' even when the code never runs (CPython gh-120522).", file=sys.stderr)
        print("", file=sys.stderr)
        for mod, needle in pyz_hits:
            print(f"  PYZ frozen module: {mod}  ->  {needle!r}", file=sys.stderr)
        for path, needle in disk_hits:
            print(f"  on-disk file:      {path}  ->  {needle!r}", file=sys.stderr)
        print("", file=sys.stderr)
        print("The spec strip (desktop/bristlenose-sidecar.spec ::", file=sys.stderr)
        print("_strip_app_store_noncompliant_strings) should have removed this at", file=sys.stderr)
        print("freeze time — if it didn't, PyInstaller internals likely shifted.", file=sys.stderr)
        print("Rebuild the sidecar (desktop/scripts/build-sidecar.sh) after fixing.", file=sys.stderr)
        return 1

    print(f"clean: no App-Store-noncompliant URL-scheme literals in {exe.name} (PYZ + on-disk)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
