"""The Developer-ID .dmg lane reuses what the release already verified.

Two things build-dmg.sh used to redo that build-all.sh had just done at the same
commit in the same release run, both measured from the ledgers (0.28.0–0.35.0):

* the sidecar's dependency resolve — every build-dmg log from 0.31.4 on says
  ``[V] REBUILD — forced`` while build-all's kept the venv, so the .dmg could
  ship a closure resolved minutes after the one preflight checked;
* the Swift suite — two of the seven non-operator build-dmg stops (incidents 36
  and 41) were in this second run of a suite build-all had just passed.

These read the arguments and environment that ARRIVE, by running the real lines
against stubs, rather than asserting a string is in the file — the archive
invocation's own test in test_entitlements_split.py explains why.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_BASH = shutil.which("bash") or "bash"
_ROOT = Path(__file__).resolve().parent.parent
_BUILD_DMG = _ROOT / "desktop" / "scripts" / "build-dmg.sh"


def _line(prefix: str) -> str:
    lines = [ln for ln in _BUILD_DMG.read_text(encoding="utf-8").splitlines() if ln.strip().startswith(prefix)]
    assert len(lines) == 1, f"expected exactly one line starting {prefix!r}, found {lines}"
    return lines[0].strip()


def test_the_dmg_lane_reuses_the_release_resolve(tmp_path: Path) -> None:
    """build-dmg's ensure-sidecar call carries --keep-venv, as build-all's does."""
    stub = tmp_path / "ensure-sidecar.sh"
    stub.write_text('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\n')
    stub.chmod(0o755)
    line = _line('_BRISTLENOSE_RELEASE=1 "$SCRIPT_DIR/ensure-sidecar.sh"')
    out = subprocess.run([_BASH, "-c", f'SCRIPT_DIR="{tmp_path}"\n{line}'], capture_output=True, text=True,
                         timeout=30).stdout.split()
    assert "--force" in out and "--keep-venv" in out, (
        f"build-dmg's sidecar build must reuse the release's resolve (--keep-venv). Arguments: {out}")


def test_both_lanes_pass_the_same_sidecar_flags() -> None:
    """A lane that drops the flag reopens incident 23 on that lane alone."""
    all_ = (_ROOT / "desktop" / "scripts" / "build-all.sh").read_text(encoding="utf-8")
    assert '"$SCRIPT_DIR/ensure-sidecar.sh" --force --keep-venv' in all_, "build-all.sh changed its sidecar call"
    assert _line('_BRISTLENOSE_RELEASE=1 "$SCRIPT_DIR/ensure-sidecar.sh"').endswith("--force --keep-venv")
