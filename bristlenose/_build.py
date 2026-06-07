"""Build provenance for the running bristlenose process.

Lets any run — and crucially any captured failure log — self-identify the
exact source the binary was built from, independent of what the most recent
Xcode/desktop build claims. The Swift host already bakes a git SHA into its
footer (`GeneratedBuildInfo.swift`); this is the sidecar's equivalent.

Resolution order:
  1. A generated ``bristlenose/_build_info.py`` baked at bundle time by
     ``desktop/scripts/build-sidecar.sh``. The bundled sidecar has no git repo
     at runtime (and runs sandboxed), so this is the only source that works in
     production.
  2. Live ``git rev-parse`` from the package's repo — the dev / source path,
     where no generated file exists.
  3. ``"unknown"`` — neither available (e.g. a release tarball install).
"""

from __future__ import annotations

from functools import lru_cache


def _from_generated() -> tuple[str, str] | None:
    try:
        from bristlenose._build_info import BUILD_DATE, GIT_SHA
    except ImportError:
        return None
    return GIT_SHA, BUILD_DATE


def _from_git() -> tuple[str, str] | None:
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        sha = result.stdout.strip()
        # Dirty flag: uncommitted changes mean the build differs from the SHA.
        # Without this, a rebuild from a working tree with uncommitted fixes
        # reports the same bare SHA as a build from clean HEAD — making the
        # banner useless for telling "did my rebuild take?" apart.
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if dirty.returncode == 0 and dirty.stdout.strip():
            sha += "-dirty"
    except (OSError, subprocess.SubprocessError):
        return None
    return sha, ""


@lru_cache(maxsize=1)
def build_sha() -> str:
    """Short git SHA the running process was built from, or ``"unknown"``.

    Dev runs append ``-dirty`` when the working tree has uncommitted changes.
    """
    for source in (_from_generated, _from_git):
        resolved = source()
        if resolved and resolved[0]:
            return resolved[0]
    return "unknown"


@lru_cache(maxsize=1)
def build_date() -> str:
    """ISO-8601 build timestamp (bundle builds only), else empty string."""
    resolved = _from_generated()
    return resolved[1] if resolved else ""


@lru_cache(maxsize=1)
def build_label() -> str:
    """Human banner string: SHA plus a build-time stamp when bundled.

    Bundled sidecar → ``"e93e079 @06-08T00:15Z"`` (the baked build minute, so
    two rebuilds of the same SHA are distinguishable). Dev → ``"e93e079-dirty"``.
    Empty string when provenance is unavailable (release tarball).
    """
    sha = build_sha()
    if sha == "unknown":
        return ""
    iso = build_date()
    if iso:
        # 2026-06-08T00:15:42Z -> 06-08T00:15Z  (compact, minute precision)
        stamp = iso[5:16].replace("T", "T") + "Z" if len(iso) >= 16 else iso
        return f"{sha} @{stamp}"
    return sha
