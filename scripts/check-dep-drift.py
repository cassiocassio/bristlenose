#!/usr/bin/env python3
"""Name the packages whose resolved version has drifted from the inventory.

WHY THIS EXISTS

release-log 0.27.0 tricky thing #5: `openai>=1.50` resolved to 3.0.0 during a
release. Every constructor survived, so it was a non-event — but

    "the discovery moment was '10pm, mid-release', which is the wrong moment
     for it."

That is the complaint, and it is about TIMING, not about wanting an upper bound.
The project's written policy is floor-only (pyproject.toml), and pinning without
a renovation bot ships known-vulnerable transitives for months, so capping is a
separate judgement the maintainer owns.

What this does instead is make the preflight say WHICH packages moved and WHETHER
any of them is a major, at the free first step rather than at 10pm. Same data
`generate-third-party-binaries.py --check` already computes; that one answers a
yes/no ("is the file stale?"), which is exactly the answer that does not help
you decide anything.

Which environment is "installed": the SIDECAR venv (`.venv-sidecar/`), the one
the bundle is built from — not the interpreter running this script. `.venv`
resolves separately and has recorded versions the bundle never carried.
`--python` overrides the target.

Exit codes:
  0  no drift, or only minor/patch drift (named, not silent)
  1  at least one MAJOR version change since the committed inventory
  2  could not run — no inventory, target venv missing, or metadata unreadable
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
from importlib import metadata

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TARGET_PYTHON = REPO_ROOT / ".venv-sidecar" / "bin" / "python"

BEGIN = "<!-- BEGIN AUTO: python-wheels -->"
END = "<!-- END AUTO: python-wheels -->"
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|")


def parse_inventory(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    try:
        body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    except IndexError:
        sys.exit("::error::inventory markers not found")
    out: dict[str, str] = {}
    for line in body.splitlines():
        m = ROW.match(line.strip())
        if m and m.group(2) not in ("Version", "---"):
            out[m.group(1).lower().replace("_", "-")] = m.group(2).strip()
    return out


def bump_kind(old: str, new: str) -> str:
    """major / minor / patch / other — lenient, because versions are not all PEP 440."""
    def parts(v: str) -> list[int]:
        got = []
        for chunk in re.split(r"[.\-+]", v):
            if chunk.isdigit():
                got.append(int(chunk))
            else:
                break
        return got or [0]

    a, b = parts(old), parts(new)
    if a == b:
        # Numerically identical but textually different — 1.2.3 vs 1.2.3.post1,
        # or an rc/dev suffix. parts() stops at the first non-digit, so these
        # collapse. Report them: the resolved set DID change, and a gate that
        # silently drops a change it saw is the same defect as one that reports
        # success while seeing nothing.
        return "same" if old == new else "patch"
    if a[0] != b[0]:
        return "major"
    if len(a) > 1 and len(b) > 1 and a[1] != b[1]:
        return "minor"
    return "patch"


def _site_packages(target_python: pathlib.Path) -> pathlib.Path | None:
    """Ask the target interpreter where its distributions live."""
    proc = subprocess.run(
        [str(target_python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return pathlib.Path(proc.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="name resolved-version drift from the inventory")
    parser.add_argument(
        "--python",
        type=pathlib.Path,
        default=DEFAULT_TARGET_PYTHON,
        help="interpreter whose site-packages count as 'installed' (default: the sidecar venv)",
    )
    args = parser.parse_args()

    inv_path = REPO_ROOT / "THIRD-PARTY-BINARIES.md"
    if not inv_path.exists():
        print("::error::no THIRD-PARTY-BINARIES.md to compare against")
        return 2
    inventory = parse_inventory(inv_path)
    if not inventory:
        print("::error::inventory parsed to zero rows — refusing to report 'no drift'")
        return 2

    # .absolute(), NOT .resolve(): resolving a venv's python follows the
    # symlink to the base interpreter and its (empty) site-packages.
    target_python = args.python.absolute()
    if not target_python.is_file():
        print(f"::error::target interpreter not found: {target_python} — build the sidecar or pass --python")
        return 2
    site = _site_packages(target_python)
    if site is None or not site.is_dir():
        print(f"::error::could not locate site-packages under {target_python}")
        return 2

    installed: dict[str, str] = {}
    for dist in metadata.distributions(path=[str(site)]):
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name:
            installed[name] = dist.version

    majors, minors, gone = [], [], []
    for name, old in sorted(inventory.items()):
        new = installed.get(name)
        if new is None:
            gone.append(name)
            continue
        kind = bump_kind(old, new)
        if kind == "major":
            majors.append((name, old, new))
        elif kind in ("minor", "patch"):
            minors.append((name, old, new, kind))

    if not majors and not minors and not gone:
        print(f"{len(inventory)} packages, none drifted")
        return 0

    for name, old, new in majors:
        print(f"MAJOR  {name}  {old} -> {new}")
    for name, old, new, kind in minors:
        print(f"{kind:<6} {name}  {old} -> {new}")
    for name in gone:
        print(f"absent {name}  (in inventory, not installed)")

    if majors:
        print(f"::error::{len(majors)} major version change(s) since the inventory")
        return 1
    print(f"{len(minors) + len(gone)} non-major change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
