"""The Mac app's ffmpeg recipe stays LGPL-2.1, and its gate has a caller.

The app ships under Apple's EULA, which a GPL binary can't go out under; until
25 Nov 2026 it bundled a GPL build (x264, x265). ``build-ffmpeg-lgpl.sh`` gates
what it builds, but CI never runs it, so these read the recipe itself: a flag
added here would otherwise surface only on the owner's next build.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

DESKTOP_SCRIPTS = Path(__file__).resolve().parent.parent / "desktop" / "scripts"


def _ffmpeg_configure_flags() -> set[str]:
    text = (DESKTOP_SCRIPTS / "build-ffmpeg-lgpl.sh").read_text(encoding="utf-8")
    start = text.index('step "ffmpeg $FFMPEG_V"')
    block = text[start:text.index("make -j", start)].replace("\\\n", " ")
    return {tok.split("=")[0] for tok in shlex.split(block, comments=True) if tok.startswith("--")}


def test_the_recipe_has_no_gpl_nonfree_or_version3_flag() -> None:
    flags = _ffmpeg_configure_flags()
    assert "--disable-autodetect" in flags  # nothing from the build machine sneaks in
    forbidden = {f for f in flags if re.fullmatch(
        r"--enable-(gpl|nonfree|version3|libx26[45]|openssl|gnutls|libvidstab|frei0r)", f)}
    assert forbidden == set()


def test_the_recipe_keeps_what_the_app_uses() -> None:
    flags = _ffmpeg_configure_flags()
    # The burn (libass's subtitles filter, VideoToolbox's H.264) and AV1 decoding.
    assert {"--enable-libass", "--enable-videotoolbox", "--enable-libdav1d"} <= flags


def test_the_build_and_the_release_ask_for_the_pinned_recipe() -> None:
    """A gate with no caller is not a gate: both callers run ``--check`` on a live line."""
    root = DESKTOP_SCRIPTS.parent.parent
    for caller in ("desktop/scripts/ensure-sidecar.sh", "scripts/release.sh"):
        text = (root / caller).read_text(encoding="utf-8")
        assert re.search(r'^[^#\n]*fetch-ffmpeg\.sh" --check', text, flags=re.M), caller
    fetch = (DESKTOP_SCRIPTS / "fetch-ffmpeg.sh").read_text(encoding="utf-8")
    assert re.search(r'^[^#\n]*"\$SCRIPT_DIR/build-ffmpeg-lgpl\.sh" "\$tmp"', fetch, flags=re.M)


_VERSION = "8.1.3-bristlenose-lgpl-1"
_OURS = f"{_VERSION}\n--prefix=/x --enable-libass --enable-videotoolbox\n"
# Bash scripts: nothing to run on Windows. An empty parameter list rather than a skip
# marker, as in test_gate_selftests.py (the skip-site ratchet counts markers).
_CHECK_CASES = [] if sys.platform == "win32" else [
    ("this recipe's build", _OURS, _OURS, 0),
    ("the GPL build shipped until 25 Nov 2026",
     "8.0.1-https://www.martin-riedl.de\n--prefix=/x --enable-gpl --enable-libx264\n", _OURS, 1),
    ("our version string, GPL flags", f"{_VERSION}\n--prefix=/x --enable-gpl\n", _OURS, 1),
    ("an older BUILD_REV", "8.1.3-bristlenose-lgpl-0\n--prefix=/x\n", _OURS, 1),
    ("ffprobe missing", _OURS, None, 1),
]


@pytest.mark.parametrize(("case", "ffmpeg", "ffprobe", "expected"), _CHECK_CASES)
def test_check_tells_the_pinned_build_from_anything_else(
    tmp_path: Path, case: str, ffmpeg: str, ffprobe: str | None, expected: int,
) -> None:
    for name, text in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
        if text is not None:
            (tmp_path / name).write_text(text, encoding="utf-8")
            (tmp_path / name).chmod(0o755)
    assert _VERSION == subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "build-ffmpeg-lgpl.sh"), "--version"],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    result = subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "fetch-ffmpeg.sh"), "--check"],
        env={**os.environ, "FETCH_FFMPEG_RESOURCES_DIR": str(tmp_path)},
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == expected, (case, result.stderr)
