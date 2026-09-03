#!/usr/bin/env python3
"""Compute the CPython "Goldilocks band" the shipped dependency set actually supports.

Run at the quarterly tooling review (docs/design-platform-policy.md § Quarterly
tooling review) to answer "are we inside the band?" by measurement rather than
by argument.

What gates a CPython version is the set of dependencies carrying **compiled**
extensions -- pure-Python packages install anywhere and never constrain us. So
this script does not carry a hardcoded package list (which would rot, and has:
"numba and llvmlite lag the newest CPython" was repeated for months after it
stopped being true). It finds the compiled distributions empirically, by looking
for extension modules in an installed environment, then asks PyPI which CPython
versions each one's *current* release ships wheels for.

Run it against the venv that SHIPS, not the dev venv:

    .venv-sidecar/bin/python scripts/check-python-band.py

This is a reporting tool for a human at review time, NOT a CI gate. If you ever
wire it into a workflow, it needs a disposition in docs/testing/soft-gates.json
first -- see CLAUDE.md § "Gate policy -- no gate goes soft by default".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import distributions
from pathlib import Path

PYPI = "https://pypi.org/pypi/{name}/json"
CANDIDATES = [(3, minor) for minor in range(9, 20)]
# cp<major><minor>-<abi>-<platform>; abi is cp3XX, cp3XXt (free-threaded) or abi3.
WHEEL_TAG = re.compile(r"-cp(\d)(\d+)-(cp\d+t?|abi3)-")
PY3_NONE = re.compile(r"-(?:py3|py2\.py3)-none-")
TIMEOUT = 30


def compiled_distributions(paths: list[str] | None) -> dict[str, str]:
    """Map distribution name -> installed version, for dists shipping extensions."""
    found: dict[str, str] = {}
    kwargs = {"path": paths} if paths else {}
    for dist in distributions(**kwargs):  # type: ignore[arg-type]
        name = dist.metadata["Name"]
        if not name:
            continue
        files = dist.files or []
        for f in files:
            suffix = Path(str(f)).suffix
            if suffix in {".so", ".pyd", ".dylib"}:
                found[name] = dist.version
                break
    return found


def supported_versions(name: str, version: str | None) -> tuple[set[tuple[int, int]], str | None]:
    """CPython versions this package ships wheels for.

    `version` is the release to inspect -- normally the INSTALLED one, because
    the actionable question is "if we moved the interpreter today, would the set
    we actually ship still install?". Pass None for the newest release (the
    ecosystem view), which differs wherever a package is deliberately held.

    Returns (versions, error). A non-None error means we could not look, or
    could not parse -- reported as UNKNOWN and excluded from the band, never
    folded into a pass. An empty result with no error is itself a parse failure:
    every wheel has some tag, so zero versions means the tags were a shape this
    function does not understand.
    """
    try:
        with urllib.request.urlopen(PYPI.format(name=name), timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return set(), f"{type(exc).__name__}: {exc}"

    release = version if version in data["releases"] else data["info"]["version"]
    files = data["releases"].get(release, [])
    wheels = [f.get("filename", "") for f in files if f.get("filename", "").endswith(".whl")]
    if not wheels:
        return set(), f"no wheels published for {release} (sdist only)"

    versions: set[tuple[int, int]] = set()
    for filename in wheels:
        m = WHEEL_TAG.search(filename)
        if m:
            base = (int(m.group(1)), int(m.group(2)))
            if m.group(3) == "abi3":
                # abi3 is forward-compatible: built for `base`, runs on >= base.
                versions.update(v for v in CANDIDATES if v >= base)
            else:
                versions.add(base)
        elif PY3_NONE.search(filename):
            # `py3-none-<platform>`: no Python ABI dependency, so any CPython 3.
            # Platform-specific binary payloads use this (e.g. mlx-metal ships
            # `py3-none-macosx_*`). Missing this shape zeroed the band on first run.
            versions.update(CANDIDATES)
    if not versions:
        return set(), f"could not parse any wheel tag from {len(wheels)} wheel(s) of {release}"
    return versions, None


def ship_target(root: Path) -> tuple[int, int] | None:
    """The interpreter we build and ship against, from .tool-versions."""
    tv = root / ".tool-versions"
    if not tv.exists():
        return None
    for line in tv.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "python":
            bits = parts[1].split(".")
            if len(bits) >= 2:
                return (int(bits[0]), int(bits[1]))
    return None


def fmt(v: tuple[int, int]) -> str:
    return f"{v[0]}.{v[1]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venv", type=Path, help="scan this venv instead of the running interpreter")
    ap.add_argument("--latest", action="store_true",
                    help="inspect each package's newest release (the ecosystem band) rather than "
                         "the installed one (what we actually ship)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if the ship target is outside the band")
    args = ap.parse_args()

    paths = None
    if args.venv:
        globbed = sorted(args.venv.glob("lib/python*/site-packages"))
        if not globbed:
            print(f"error: no site-packages under {args.venv}", file=sys.stderr)
            return 2
        paths = [str(p) for p in globbed]

    compiled = compiled_distributions(paths)
    if not compiled:
        # An empty result is a tool failure, not an all-clear.
        print("error: found no compiled distributions -- wrong venv, or nothing installed.", file=sys.stderr)
        print("       Run against the shipped venv: .venv-sidecar/bin/python scripts/check-python-band.py", file=sys.stderr)
        return 2

    names = sorted(compiled)
    wanted = [None if args.latest else compiled[n] for n in names]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(names, pool.map(supported_versions, names, wanted)))

    unknown = {n: err for n, (_, err) in results.items() if err}
    known = {n: vers for n, (vers, err) in results.items() if not err}

    shown = [v for v in CANDIDATES if any(v in vers for vers in known.values())]
    width = max((len(n) for n in names), default=10)
    header = f"{'package':<{width}}  {'installed':<12} " + "  ".join(f"{fmt(v):>5}" for v in shown)
    print(header)
    print("-" * len(header))
    for n in names:
        vers, err = results[n]
        if err:
            print(f"{n:<{width}}  {compiled[n]:<12} " + "  ".join(f"{'?':>5}" for _ in shown))
            continue
        print(f"{n:<{width}}  {compiled[n]:<12} " + "  ".join(f"{('yes' if v in vers else '--'):>5}" for v in shown))

    band = [v for v in shown if all(v in vers for vers in known.values())]
    print()
    print(f"Inspecting the {'newest' if args.latest else 'INSTALLED'} release of each package.")
    print()
    if unknown:
        print(f"UNKNOWN: could not determine support for {len(unknown)} package(s) -- excluded from "
              f"the band, which is therefore provisional, not a pass:")
        for n, err in sorted(unknown.items()):
            print(f"  {n}: {err}")
        print()

    if not band:
        print("BAND: empty -- no single CPython supports every compiled dependency.")
        return 1

    print(f"BAND: {fmt(band[0])} - {fmt(band[-1])}  "
          f"(every compiled dependency ships wheels for these at its current release)")
    # Explain only the versions that inform a decision: those below the band
    # (what moving down would cost) and the first one above it (what the next
    # move upward is waiting on). Versions further ahead are unreleased and
    # their long "missing" lists are noise that makes the report unreadable.
    ceiling = (band[-1][0], band[-1][1] + 1)
    for v in shown:
        if v in band or v > ceiling:
            continue
        missing = sorted(n for n, vers in known.items() if v not in vers)
        label = "not yet" if v > band[-1] else "outside"
        print(f"  {fmt(v):>5}: {label} -- no wheel for {', '.join(missing)}")

    root = Path(__file__).resolve().parent.parent
    target = ship_target(root)
    if target is None:
        print("\nship target: could not read `python` from .tool-versions")
        return 0

    inside = target in band
    print(f"\nship target (.tool-versions): {fmt(target)} -- {'INSIDE the band' if inside else 'OUTSIDE the band'}")
    if not inside:
        print("  The interpreter we build and ship against cannot install the current release")
        print("  of every compiled dependency. That is the condition this script exists to catch.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
