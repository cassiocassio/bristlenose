#!/usr/bin/env python3
"""Regenerate the auto-generated section of THIRD-PARTY-BINARIES.md.

Lists every Python package that ships in the desktop sidecar bundle, with
version + licence + origin URL. Run this manually before each release; the
file is committed to the repo so the result travels with the source.

How "what ships" is determined:
  - Run `pip-licenses` against the venv to capture every installed
    package's licence + version + URL.
  - Filter out packages that the PyInstaller spec excludes (parsed
    from desktop/bristlenose-sidecar.spec) and packages in the
    [dev], [release], and PyInstaller-internal sets that obviously
    don't ship to users.
  - Emit Markdown between the BEGIN AUTO / END AUTO markers in the
    target file. Hand-written rows above the markers (FFmpeg, ffprobe,
    Python.framework) are preserved.

  This produces a slight over-estimate of what's bundled — PyInstaller
  may further strip transitive deps that nothing imports — but never
  under-estimates. For procurement-readiness that's the safer error
  direction.

Prerequisites:
  - .venv with [release] extra installed: `pip install -e '.[dev,serve,apple,release]'`

Usage:
  .venv/bin/python scripts/generate-third-party-binaries.py [--check]

Exit codes:
  0  Wrote (or, with --check, would write) without changes.
  1  --check mode and the file would change. Re-run without --check.
  2  Environment error (missing venv, missing pip-licenses, unparseable spec).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "desktop" / "bristlenose-sidecar.spec"
TARGET = REPO_ROOT / "THIRD-PARTY-BINARIES.md"
BEGIN = "<!-- BEGIN AUTO: python-wheels -->"
END = "<!-- END AUTO: python-wheels -->"

# Hard-coded "obviously not shipped" set on top of the spec excludes.
# These are dev/build tooling that's in the venv but never in the bundle.
NEVER_SHIPPED = {
    # Build / packaging
    "pip",
    "pip-licenses",
    "setuptools",
    "wheel",
    "hatchling",
    "hatch",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "macholib",
    "modulegraph",
    "prettytable",  # pip-licenses transitive
    "wcwidth",  # prettytable transitive
    # Dev / test
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "pytest-mock",
    "pluggy",
    "iniconfig",
    "coverage",
    "ruff",
    "mypy",
    "mypy-extensions",
    "typing-inspection",
    "types-pyyaml",
    "types-requests",
    # Already excluded in spec but transitive tail may sneak in
    "presidio-analyzer",
    "presidio-anonymizer",
    "spacy",
    "ctranslate2",
    "faster-whisper",
}


def _spec_excludes() -> set[str]:
    """Parse the PyInstaller spec's excludes=[...] into a set of distribution names."""
    if not SPEC.is_file():
        sys.stderr.write(f"error: spec not found at {SPEC}\n")
        sys.exit(2)
    tree = ast.parse(SPEC.read_text(encoding="utf-8"), filename=str(SPEC))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Analysis"
        ):
            for kw in node.keywords:
                if kw.arg == "excludes" and isinstance(kw.value, ast.List):
                    return {
                        elt.value
                        for elt in kw.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    }
    sys.stderr.write(f"error: no Analysis(excludes=[...]) in {SPEC}\n")
    sys.exit(2)


def _normalise(name: str) -> str:
    """PEP 503 normalisation — case-fold, collapse runs of [-_.] to single hyphen."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pip_licenses_json() -> list[dict]:
    """Run pip-licenses against the venv, return all installed packages."""
    pip_licenses = shutil.which("pip-licenses") or str(
        REPO_ROOT / ".venv" / "bin" / "pip-licenses"
    )
    if not Path(pip_licenses).exists():
        sys.stderr.write(
            "error: pip-licenses not on PATH and not in .venv/bin/\n"
            "       install with: .venv/bin/pip install -e '.[release]'\n"
        )
        sys.exit(2)
    proc = subprocess.run(
        [pip_licenses, "--format=json", "--with-urls"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(
            f"error: pip-licenses failed (exit {proc.returncode}):\n{proc.stderr}\n"
        )
        sys.exit(2)
    return json.loads(proc.stdout)


def _filtered_records(records: list[dict], excludes: set[str]) -> list[dict]:
    """Drop spec-excluded + never-shipped + bristlenose-itself packages."""
    drop = {_normalise(n) for n in (excludes | NEVER_SHIPPED | {"bristlenose"})}
    return [r for r in records if _normalise(r["Name"]) not in drop]


def _format_rows(records: list[dict]) -> str:
    # Sort by name for determinism across machines / Python versions.
    sorted_records = sorted(records, key=lambda r: r["Name"].lower())
    lines = [
        "| Package | Version | Licence | URL |",
        "|---|---|---|---|",
    ]
    for r in sorted_records:
        name = r["Name"]
        version = r["Version"]
        licence = r["License"].replace("|", "/")
        url = r.get("URL") or ""
        if url in {"UNKNOWN", "None", ""}:
            url_cell = "—"
        else:
            url_cell = f"<{url}>"
        lines.append(f"| `{name}` | {version} | {licence} | {url_cell} |")
    return "\n".join(lines)


def _splice(existing: str, table: str) -> str:
    if BEGIN not in existing or END not in existing:
        sys.stderr.write(
            f"error: marker block missing in {TARGET}\n"
            f"       expected '{BEGIN}' and '{END}'\n"
        )
        sys.exit(2)
    pre, _, rest = existing.partition(BEGIN)
    _, _, post = rest.partition(END)
    return f"{pre}{BEGIN}\n{table}\n{END}{post}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 without writing if the file would change. CI-friendly.",
    )
    args = parser.parse_args()

    excludes = _spec_excludes()
    records = _filtered_records(_pip_licenses_json(), excludes)
    if not records:
        sys.stderr.write("error: no packages survived filtering\n")
        return 2

    table = _format_rows(records)

    existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    updated = _splice(existing, table)

    if args.check:
        if existing != updated:
            sys.stderr.write(
                f"{TARGET.relative_to(REPO_ROOT)} is out of date — "
                "run scripts/generate-third-party-binaries.py to regenerate\n"
            )
            return 1
        return 0

    TARGET.write_text(updated, encoding="utf-8")
    print(f"wrote {len(records)} package rows to {TARGET.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
