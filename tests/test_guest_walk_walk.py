"""The guest walk must not pass falsely (docs/design-guest-walk.md).

`desktop/scripts/guest-walk/walk.sh` is driven here from the host side with a fake
`g.sh` (the guest shell), a fake `pull.sh` and a no-op `sleep`: no VM, no tart. The
failures that matter are a verdict that says COMPLETED over screens that were never
captured (lenses behind a sheet), a notify-sheet check that cannot tell "no sheet"
from "could not look", a preseed that is written and never read back, and a night
that silently walks the 30-day alpha app frozen into the base because the staged
app is missing (`staged-app-check.sh`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# walk.sh drives Tart guests from a Mac host; the fakes here are bash scripts,
# which Windows cannot execute (FileNotFoundError on windows-latest, 19 Nov 2026).
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake tools are shell scripts")

ROOT = Path(__file__).resolve().parents[1]
WALK_DIR = ROOT / "desktop" / "scripts" / "guest-walk"

FAKE_G = r"""#!/bin/bash
echo "$*" >> "$FAKE_DIR/calls"
case "$1" in
  */walker)
    case "$2" in
      tree)
        if [ "$4" = "New Project" ]; then
          [ -n "${FAKE_TREE_FAIL:-}" ] && { echo "no window matching" >&2; exit 1; }
          [ -f "$FAKE_DIR/sheet" ] && echo 'AXStaticText "Notify me when analysis finishes"'
        elif [ "$4" = "Bristlenose" ] && [ -n "${FAKE_CONSENT:-}" ]; then
          echo 'AXButton "Continue"'
        fi
        exit 0 ;;
      press)
        if [ "$5" = Continue ] && [ "$6" = "New Project" ] && [ -z "${FAKE_SHEET_STICKS:-}" ]; then
          rm -f "$FAKE_DIR/sheet"
        fi
        exit 0 ;;
      menu) [ "$4" = "View>${FAKE_LENS_FAIL:-none}" ] && exit 1; exit 0 ;;
      *) exit 0 ;;
    esac ;;
  sh)
    case "$3" in
      *"defaults write"*) [ -n "${FAKE_WRITE_FAIL:-}" ] && exit 1; exit 0 ;;
      *"defaults read"*) printf '%b' "${FAKE_PREF_READ:-2\n0\nlocal\n}"; exit 0 ;;
      *'run_(completed'*) echo '{"event":"run_completed","outcome":"ok"}'; exit 0 ;;
      *) exit 0 ;;
    esac ;;
  sw_vers) echo 27.0; exit 0 ;;
  defaults) echo 0.46.0; exit 0 ;;
  *) exit 0 ;;
esac
"""


def _walk(tmp_path: Path, **env: str) -> tuple[str, str]:
    """Run walk.sh once against the fakes; return (verdict, walk.log)."""
    bin_dir, here, fake = tmp_path / "bin", tmp_path / "here", tmp_path / "fake"
    for d in (bin_dir, here, fake):
        d.mkdir()
    shutil.copy(WALK_DIR / "walk.sh", here / "walk.sh")
    shutil.copy(WALK_DIR / "run_summary.py", here / "run_summary.py")
    (here / "g.sh").write_text(FAKE_G, encoding="utf-8")
    (here / "pull.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (bin_dir / "sleep").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    for f in (here / "g.sh", here / "pull.sh", bin_dir / "sleep"):
        f.chmod(0o755)
    if env.pop("SHEET", ""):
        (fake / "sheet").write_text("x", encoding="utf-8")
    out = tmp_path / "out"
    full = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "OUT": str(out),
        "SETTLE": "0",
        "FAKE_DIR": str(fake),
        **env,
    }
    subprocess.run(
        ["/bin/bash", str(here / "walk.sh"), "r1"],
        env=full, capture_output=True, text=True, timeout=60, check=False,
    )
    verdict = (out / "r1" / "verdict.txt").read_text(encoding="utf-8").strip()
    log = (out / "r1" / "walk.log").read_text(encoding="utf-8")
    return verdict, log


def test_a_clean_walk_completes(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path)
    assert verdict.startswith("COMPLETED ")


def test_a_skipped_lens_is_not_completed_and_is_named(tmp_path: Path) -> None:
    verdict, log = _walk(tmp_path, FAKE_LENS_FAIL="Quotes")
    assert not verdict.startswith("COMPLETED")
    assert verdict.startswith("INCOMPLETE ")
    assert "lenses not shown: Quotes" in verdict
    assert "lens Quotes: menu item not enabled" in log


def test_every_lens_skipped_names_them_all(tmp_path: Path) -> None:
    # A modal over everything disables the whole View menu: no lens is captured.
    # The fake can fail only one lens by name, so check the join on two runs' worth.
    verdict, _ = _walk(tmp_path, FAKE_LENS_FAIL="Discussion")
    assert verdict.endswith("lenses not shown: Discussion")


def test_a_notify_sheet_is_dismissed_and_checked_gone(tmp_path: Path) -> None:
    verdict, log = _walk(tmp_path, SHEET="1")
    assert verdict.startswith("COMPLETED ")
    assert "after-notify-sheet" in log


def test_a_notify_sheet_that_stays_halts(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path, SHEET="1", FAKE_SHEET_STICKS="1")
    assert verdict.startswith("HALTED")
    assert "notify sheet is still up" in verdict


def test_an_unreadable_window_is_not_read_as_no_sheet(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path, FAKE_TREE_FAIL="1")
    assert verdict.startswith("HALTED")
    assert "cannot read the New Project window" in verdict


def test_preseed_is_read_back(tmp_path: Path) -> None:
    verdict, log = _walk(tmp_path, PRESEED="1")
    assert verdict.startswith("COMPLETED ")
    assert "(read back)" in log


def test_a_preseed_that_did_not_stick_halts(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path, PRESEED="1", FAKE_PREF_READ="1\\n1\\nlocal\\n")
    assert verdict.startswith("HALTED")
    assert "PRESEED: read back" in verdict


def test_a_failed_preseed_write_halts(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path, PRESEED="1", FAKE_WRITE_FAIL="1")
    assert verdict.startswith("HALTED")
    assert "writing the first-launch preferences failed" in verdict


def test_preseed_with_a_consent_sheet_halts(tmp_path: Path) -> None:
    verdict, _ = _walk(tmp_path, PRESEED="1", FAKE_CONSENT="1")
    assert verdict.startswith("HALTED")
    assert "preseed did not take" in verdict


def test_the_sheet_text_is_the_english_locale_value() -> None:
    en = json.loads((ROOT / "bristlenose" / "locales" / "en" / "desktop.json").read_text(
        encoding="utf-8"))
    values: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, str):
            values.append(node)

    walk(en)
    text = next(
        line.split("'")[1]
        for line in (WALK_DIR / "walk.sh").read_text(encoding="utf-8").splitlines()
        if line.startswith("SHEET_TEXT=")
    )
    assert text in values


# --- staged-app-check.sh ---------------------------------------------------------


def _check(share: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(WALK_DIR / "staged-app-check.sh"), str(share)],
        env={**os.environ, **env}, capture_output=True, text=True, check=False,
    )


def test_a_staged_tar_installs(tmp_path: Path) -> None:
    (tmp_path / "app-0.46.0.tar").write_bytes(b"tar")
    (tmp_path / "app-current.tar").symlink_to("app-0.46.0.tar")
    assert _check(tmp_path).returncode == 0


@pytest.mark.parametrize("case", ["missing", "dangling", "empty"])
def test_a_missing_dangling_or_empty_tar_halts_with_a_reason(tmp_path: Path, case: str) -> None:
    if case == "dangling":
        (tmp_path / "app-current.tar").symlink_to("app-9.9.9.tar")
    elif case == "empty":
        (tmp_path / "app-current.tar").write_bytes(b"")
    r = _check(tmp_path)
    assert r.returncode == 3
    assert "app-current.tar" in r.stdout


def test_the_frozen_app_is_walked_only_on_opt_in(tmp_path: Path) -> None:
    r = _check(tmp_path, GW_FROZEN_APP="1")
    assert r.returncode == 4
    assert r.stdout == ""


def test_an_incomplete_walk_never_becomes_the_baseline() -> None:
    """BR-30: the baseline link is only moved by a COMPLETED verdict.

    guest-walk.sh needs a guest to run, so this pins the case line itself:
    an INCOMPLETE walk (lenses missing) must not become the reference."""
    src = (Path(__file__).resolve().parent.parent / "desktop/scripts/guest-walk/guest-walk.sh").read_text(
        encoding="utf-8"
    )
    lines = [ln for ln in src.splitlines() if '"$WALKS/baseline"' in ln and "ln -sfn" in ln]
    assert len(lines) == 1, lines
    assert "COMPLETED*" in lines[0] and "INCOMPLETE" not in lines[0], lines[0]
