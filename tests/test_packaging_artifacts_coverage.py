"""Source→package coverage gate for build-generated runtime assets.

`bristlenose/server/static/` and `bristlenose/server/static-export/` are both
*generated* by `npm run build` and both **gitignored**, so hatchling only ships
them because `[tool.hatch.build] artifacts` re-includes them by name. Miss one
and there is no error anywhere: the tree is fine, the suite is green, the wheel
builds, and the gap surfaces only on an installed copy, as a runtime 500 in
front of a user.

That is not hypothetical. `static-export/` was absent from `artifacts` and
therefore from every sdist and wheel ever published, so **Export HTML returned a
500 on every pip / pipx / Homebrew / Snap install** — `routes/export.py` raises
"Export build not found or incomplete" when `app.js`/`app.css` are missing. Only
the macOS app worked, because `desktop/bristlenose-sidecar.spec` lists the
directory separately and correctly. Found 27 Aug 2026.

Note what could *not* have caught it. `tests/test_serve_export_coverage.py` is
the anti-drift gate for exports, and it classifies **routes**, not assets. Every
other test runs against `pip install -e .`, where these directories exist at
their source paths whether or not they are packaged — so asserting the directory
exists proves precisely nothing about the artefact a user downloads. The only
question with teeth is the one below: *is this path declared for packaging?*

Sibling gate, same shape, different packager: `desktop/scripts/check-bundle-manifest.sh`
(source→PyInstaller-spec coverage).
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Gitignored paths under bristlenose/ that are deliberately NOT shipped, with
#: the reason. Anything gitignored and absent from both this map and the
#: `artifacts` list fails the test below — so a new generated asset directory
#: forces a decision here rather than shipping a hole.
NOT_SHIPPED: dict[str, str] = {
    "bristlenose/_build_info.py": (
        "generated per-build provenance stamp, written at build time by the "
        "packaging scripts; imported via try/except in bristlenose/_build.py "
        "and absent by design in a source checkout"
    ),
}


def _gitignored_bristlenose_paths() -> list[str]:
    """Every .gitignore entry naming a path inside the bristlenose/ package."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        # Skip comments, blanks, and negations (re-inclusions, not exclusions).
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        # Only entries anchored inside the importable package matter here.
        # ".bristlenose/" is a per-run output dir, not part of the package.
        if line.startswith("bristlenose/"):
            out.append(line.rstrip("/"))
    return out


def _artifact_globs() -> list[str]:
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    return data["tool"]["hatch"]["build"]["artifacts"]


def _is_covered(path: str, globs: list[str]) -> bool:
    """True if *path* (a directory or file) is matched by an artifacts glob.

    A directory is covered by a `dir/**` glob; hatchling's `**` matches the
    directory's contents, so compare against a representative child too.
    """
    probe = (path, f"{path}/x", f"{path}/x/y")
    return any(fnmatch(p, g) for g in globs for p in probe)


def test_generated_asset_dirs_are_declared_for_packaging() -> None:
    """Every gitignored path in the package is shipped, or explicitly is not.

    The failure this pins is silent by construction: nothing in a source
    checkout behaves differently when an artifacts entry is missing.
    """
    globs = _artifact_globs()
    undeclared = [
        p
        for p in _gitignored_bristlenose_paths()
        if p not in NOT_SHIPPED and not _is_covered(p, globs)
    ]
    assert not undeclared, (
        "gitignored path(s) under bristlenose/ are neither in "
        "[tool.hatch.build] artifacts nor recorded in NOT_SHIPPED:\n  "
        + "\n  ".join(undeclared)
        + "\n\nA generated directory that is gitignored and undeclared ships in "
        "NO sdist or wheel, with no build error — it fails at runtime on the "
        "user's machine. Add it to artifacts, or add it to NOT_SHIPPED with a "
        "reason."
    )


@pytest.mark.parametrize(
    ("asset_dir", "reader"),
    [
        ("bristlenose/server/static", "server/app.py::_mount_prod_report (the React SPA)"),
        (
            "bristlenose/server/static-export",
            "server/routes/export.py::_build_export_html (the single-file export build)",
        ),
    ],
)
def test_server_runtime_asset_dirs_are_packaged(asset_dir: str, reader: str) -> None:
    """Name the two directories explicitly, so the reason survives a refactor.

    The parametrised names are the point: a future edit that drops one from
    `artifacts` fails against the code path that reads it, not against a
    generic glob assertion.
    """
    assert _is_covered(asset_dir, _artifact_globs()), (
        f"{asset_dir}/ is not covered by [tool.hatch.build] artifacts, so it "
        f"ships in no wheel or sdist — but {reader} reads it at runtime."
    )
