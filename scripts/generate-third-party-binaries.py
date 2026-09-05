#!/usr/bin/env python3
"""Regenerate the auto-generated section of THIRD-PARTY-BINARIES.md.

Lists every Python package that ships in the desktop sidecar bundle, with
version + licence + origin URL. Run this manually before each release; the
file is committed to the repo so the result travels with the source.

How "what ships" is determined:
  - Run `pip-licenses` against the SIDECAR venv (`.venv-sidecar/`, the
    environment `desktop/scripts/build-sidecar.sh` builds the bundle from)
    to capture every installed package's licence + version + URL. Not
    `.venv`: that is the dev environment, it resolves separately, and on
    27 Aug 2026 it recorded starlette 1.3.1 against a bundle carrying 1.6.0
    and listed tokenizers, which the bundle does not contain. `--python`
    overrides the target; the tool itself still runs from `.venv`.
  - Filter out packages that the PyInstaller spec excludes (parsed
    from desktop/bristlenose-sidecar.spec) and packages in the
    [dev], [release], and PyInstaller-internal sets that obviously
    don't ship to users.
  - Emit Markdown between the BEGIN AUTO / END AUTO markers in the
    target file. Hand-written rows above the markers (FFmpeg, ffprobe,
    Python.framework) are preserved.

  This produces a slight over-estimate of what's bundled — PyInstaller
  may further strip transitive deps that nothing imports — but never
  under-estimates the CODE that ships. For procurement-readiness that's
  the safer error direction. One known exception, metadata only: a
  package the spec `excludes` can still leave its `*.dist-info` in
  `_internal/` (presidio_analyzer-2.2.364.dist-info was there on 5 Sep
  2026 with no package directory), so an SCA scanner reading dist-info
  will name it while this table, which follows the code, does not.

Prerequisites:
  - .venv with [release] extra installed: `pip install -e '.[dev,serve,apple,release]'`
    (pip-licenses lives here; it is never installed into the sidecar venv)
  - .venv-sidecar built: `desktop/scripts/build-sidecar.sh`

Usage:
  .venv/bin/python scripts/generate-third-party-binaries.py [--check] [--python PATH]

Exit codes:
  0  Wrote (or, with --check, would write) without changes.
  1  --check mode and the file would change. Re-run without --check.
  2  Environment error (missing target venv, missing pip-licenses, unparseable spec).
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
# The interpreter whose site-packages IS the bundle's input. build-sidecar.sh
# creates it with `python3.12 -m venv .venv-sidecar` and PyInstaller collects
# from it; .venv is a different resolve and must not be read as a proxy.
DEFAULT_TARGET_PYTHON = REPO_ROOT / ".venv-sidecar" / "bin" / "python"
BEGIN_WHEELS = "<!-- BEGIN AUTO: python-wheels -->"
END_WHEELS = "<!-- END AUTO: python-wheels -->"
BEGIN_FRAMEWORK = "<!-- BEGIN AUTO: framework-libs -->"
END_FRAMEWORK = "<!-- END AUTO: framework-libs -->"

# Override the Licence cell for packages whose pip metadata is unhelpful.
# pip-licenses returns whatever the wheel declared in its metadata, which
# for some packages is the full licence body (tiktoken) or an unversioned
# "GPL" string (pysrt). Keys are PEP 503-normalised distribution names.
LICENSE_OVERRIDES: dict[str, str] = {
    # tiktoken's wheel embeds the entire MIT licence text in the License
    # field; without an override it spans 22 lines and breaks the table.
    "tiktoken": "MIT",
    # pysrt declares "GNU General Public License (GPL)" without a version;
    # the upstream repo is GPL-3.0-or-later, which is AGPL-3.0 compatible.
    "pysrt": "GPL-3.0-or-later",
}

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
    # pytest-xdist and its transitive execnet arrived with the release suites
    # moving to Linux ("run the release suites on linux, and stop paying for
    # coverage 8 times"). Neither reaches the sidecar; without them here the
    # generator wanted to write a test-parallelisation library into a document
    # whose header says it lists what ships in `Bristlenose.app/Contents/
    # Resources/` and names procurement reviewers and CVE responders as its
    # readers. `build-all.sh` step 2b hard-fails on the resulting drift, so this
    # omission was a release blocker that would have surfaced mid-build.
    "pytest-xdist",
    "execnet",
    "pluggy",
    "iniconfig",
    "coverage",
    "ruff",
    "mypy",
    "mypy-extensions",
    "typing-inspection",
    "types-pyyaml",
    "types-requests",
    # pre-commit and its transitive tail. Declared in [dev] and used by the
    # gitleaks hook; none of it reaches the sidecar. Listed explicitly because
    # NEVER_SHIPPED matches names, not dependency trees — same reason
    # prettytable/wcwidth are named above.
    "pre-commit",
    "cfgv",
    "identify",
    "nodeenv",
    "virtualenv",
    "distlib",
    "platformdirs",
    "python-discovery",
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


def _pip_licenses_json(target_python: Path) -> list[dict]:
    """Run pip-licenses against the TARGET interpreter's site-packages.

    The tool comes from .venv (release extra); `--python` points it at the
    venv the bundle is built from, so the two never have to be the same
    environment and the sidecar venv stays free of dev tooling."""
    # .venv's copy first (the [release] extra pins pip-licenses>=5, which has
    # --python); PATH is the fallback, not the preference — a stranger's
    # pip-licenses may predate the one flag this script depends on.
    venv_tool = REPO_ROOT / ".venv" / "bin" / "pip-licenses"
    pip_licenses = str(venv_tool) if venv_tool.exists() else (shutil.which("pip-licenses") or str(venv_tool))
    if not Path(pip_licenses).exists():
        sys.stderr.write(
            "error: pip-licenses not on PATH and not in .venv/bin/\n"
            "       install with: .venv/bin/pip install -e '.[release]'\n"
        )
        sys.exit(2)
    proc = subprocess.run(
        [pip_licenses, "--python", str(target_python), "--format=json", "--with-urls"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def _clean_licence(raw: str) -> str:
    """Collapse whitespace, escape pipes, truncate. Defends against pip-licenses
    returning full licence bodies (tiktoken) or labels with newlines."""
    one_line = " ".join(raw.split()).replace("|", "/")
    return one_line if len(one_line) <= 80 else one_line[:77] + "..."


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
        override = LICENSE_OVERRIDES.get(_normalise(name))
        licence = override if override else _clean_licence(r["License"])
        url = r.get("URL") or ""
        if url in {"UNKNOWN", "None", ""}:
            url_cell = "—"
        else:
            url_cell = f"<{url}>"
        lines.append(f"| `{name}` | {version} | {licence} | {url_cell} |")
    return "\n".join(lines)


_PROBE_SRC = """
import json, sqlite3, ssl, sys, xml.parsers.expat, zlib
print(json.dumps({
    "python": sys.version.split()[0],
    "openssl": ssl.OPENSSL_VERSION.split()[1],
    "sqlite": sqlite3.sqlite_version,
    "zlib": zlib.ZLIB_VERSION,
    "expat": xml.parsers.expat.EXPAT_VERSION.removeprefix("expat_"),
}))
"""


def _probe_framework_libs(target_python: Path) -> str:
    """Query the TARGET Python for versions of bundled C libraries.

    Run as a subprocess under the sidecar interpreter, not in-process: the
    bundle's Python.framework is copied from the interpreter that created
    .venv-sidecar, so that is the one whose linked OpenSSL/SQLite ship. Each
    stdlib module that wraps a C library exposes the linked version as an
    attribute; libraries the stdlib doesn't expose are "tracks Python
    release" — they move with whichever interpreter created .venv-sidecar.
    """
    proc = subprocess.run(
        [str(target_python), "-c", _PROBE_SRC],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        sys.stderr.write(f"error: framework probe failed under {target_python}:\n{proc.stderr}\n")
        sys.exit(2)
    v = json.loads(proc.stdout)
    rows = [
        ("Python", v["python"], "The interpreter that created `.venv-sidecar` (Homebrew `python3.12` on the dev Mac today)"),
        ("OpenSSL", v["openssl"], "Linked into `_ssl` and `_hashlib`"),
        ("SQLite", v["sqlite"], "Linked into `_sqlite3`"),
        ("zlib", v["zlib"], "Linked into `zlib`"),
        ("expat", v["expat"], "Linked into `pyexpat`"),
    ]
    lines = [
        "| Library | Version | Where it lives in the bundle |",
        "|---|---|---|",
    ]
    lines += [f"| `{n}` | {v} | {w} |" for n, v, w in rows]
    return "\n".join(lines)


def _splice(existing: str, table: str, begin: str, end: str) -> str:
    """Replace content between begin/end markers. Validates that exactly one
    marker pair exists and that begin precedes end — defends against
    duplicated or reversed markers silently producing garbage."""
    if existing.count(begin) != 1 or existing.count(end) != 1:
        sys.stderr.write(
            f"error: marker pair must appear exactly once in {TARGET}\n"
            f"       found {existing.count(begin)}x BEGIN, {existing.count(end)}x END\n"
            f"       markers: '{begin}' / '{end}'\n"
        )
        sys.exit(2)
    if existing.index(begin) >= existing.index(end):
        sys.stderr.write(
            f"error: BEGIN marker must precede END marker in {TARGET}\n"
            f"       markers: '{begin}' / '{end}'\n"
        )
        sys.exit(2)
    pre, _, rest = existing.partition(begin)
    _, _, post = rest.partition(end)
    return f"{pre}{begin}\n{table}\n{end}{post}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 without writing if the file would change. CI-friendly.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=DEFAULT_TARGET_PYTHON,
        help=(
            "Interpreter whose site-packages to inventory. Default is the sidecar "
            "venv the bundle is built from; .venv is NOT a proxy for it."
        ),
    )
    args = parser.parse_args()

    # .absolute(), NOT .resolve(): a venv's bin/python is a symlink to the
    # base interpreter, and resolving it yields the base's site-packages —
    # one package, none of ours. Measured 5 Sep 2026 on the first run.
    target_python = args.python.absolute()
    if not target_python.is_file():
        sys.stderr.write(
            f"error: target interpreter not found: {target_python}\n"
            "       the inventory is read from the venv the bundle is built from —\n"
            "       run desktop/scripts/build-sidecar.sh first, or pass --python\n"
        )
        return 2

    excludes = _spec_excludes()
    raw = _pip_licenses_json(target_python)
    # The anchor, on the RAW records because _filtered_records drops the
    # project by name. bristlenose is installed in any venv this inventory can
    # describe, so its absence means the target is not a project venv: a bare
    # or half-built .venv-sidecar, a --python symlinked from outside the venv's
    # bin/ (lands on the base interpreter), or a plain wrong interpreter. The
    # `if not records` guard below is an existence check, not a floor — the
    # 5 Sep 2026 incident wrote ONE row through it and was caught by a human
    # reading stdout. Also the empty case: pip-licenses splits the target's
    # sys.path on whitespace, so a venv under a path containing a space (this
    # repo's documented worktree layout) yields zero records.
    if not any(_normalise(r["Name"]) == "bristlenose" for r in raw):
        sys.stderr.write(
            f"error: {target_python} does not carry the bristlenose distribution "
            f"({len(raw)} records) — not a project venv, refusing to inventory it.\n"
            "       Half-built .venv-sidecar? run desktop/scripts/build-sidecar.sh.\n"
            "       Path with whitespace? pip-licenses --python cannot read it; "
            "inventory from a space-free checkout.\n"
        )
        return 2
    records = _filtered_records(raw, excludes)
    if not records:
        sys.stderr.write("error: no packages survived filtering\n")
        return 2

    wheels_table = _format_rows(records)
    framework_table = _probe_framework_libs(target_python)

    existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    updated = _splice(existing, wheels_table, BEGIN_WHEELS, END_WHEELS)
    updated = _splice(updated, framework_table, BEGIN_FRAMEWORK, END_FRAMEWORK)

    if args.check:
        if existing != updated:
            sys.stderr.write(
                f"{TARGET.relative_to(REPO_ROOT)} is out of date — "
                "run scripts/generate-third-party-binaries.py to regenerate.\n"
                "       --check is meant to run on the canonical Mac sidecar build "
                "runner; per-platform venv differences (mlx, av, torch) may flag "
                "drift on other machines that isn't real drift.\n"
            )
            return 1
        return 0

    TARGET.write_text(updated, encoding="utf-8")
    print(
        f"wrote {len(records)} package rows + framework-libs table "
        f"to {TARGET.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    # Exit codes are the contract: 1 means "--check: the file would change",
    # which both shell callers answer with "regenerate". An uncaught exception
    # also exits 1 by Python's default, so a JSONDecodeError from a chatty
    # target interpreter or a KeyError from pip-licenses field drift used to
    # read as "stale" and prescribe a remedy that crashes identically. Every
    # failure that is not the --check verdict is 2.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — the exit code is the contract
        import traceback
        traceback.print_exc()
        sys.exit(2)
