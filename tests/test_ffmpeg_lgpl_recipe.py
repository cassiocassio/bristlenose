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
    # --check's licence half is the shipped-bundle gate itself, not a second copy of it.
    assert re.search(r'^[^#\n]*"\$SCRIPT_DIR/check-ffmpeg-licence\.sh" "\$bin"', fetch, flags=re.M)


def test_the_build_gates_the_ffmpeg_it_exported() -> None:
    """The licence gate reads the exported app's binaries, on a live line of build-all.sh."""
    text = (DESKTOP_SCRIPTS / "build-all.sh").read_text(encoding="utf-8").replace("\\\n", " ")
    call = re.search(r'^[^#\n]*"\$SCRIPT_DIR/check-ffmpeg-licence\.sh"[^\n]*', text, flags=re.M)
    assert call, "build-all.sh does not run check-ffmpeg-licence.sh"
    for name in ("ffmpeg", "ffprobe"):
        assert f'"$EXPORTED_APP/Contents/Resources/{name}"' in call.group(0), name
    assert "|| {" in call.group(0)  # a failure stops the build, not a warning


_VERSION = "8.1.3-bristlenose-lgpl-1"
_LGPL = "libavcodec license: LGPL version 2.1 or later\n"
_OURS = f"{_VERSION}\n--prefix=/x --enable-libass --enable-videotoolbox\n{_LGPL}"
# Bash scripts: nothing to run on Windows. An empty parameter list rather than a skip
# marker, as in test_gate_selftests.py (the skip-site ratchet counts markers).
_CHECK_CASES = [] if sys.platform == "win32" else [
    ("this recipe's build", _OURS, _OURS, 0),
    ("the GPL build shipped until 25 Nov 2026",
     "8.0.1-https://www.martin-riedl.de\n--prefix=/x --enable-gpl --enable-libx264\n", _OURS, 1),
    ("our version string, GPL flags", f"{_VERSION}\n--prefix=/x --enable-gpl\n", _OURS, 1),
    ("our version string, no licence strings", f"{_VERSION}\n--prefix=/x\n", _OURS, 1),
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


_GPL_8_0_1 = (  # the shape of the martin-riedl.de build shipped until 25 Nov 2026
    "%sconfiguration: --prefix=/Volumes/ffmpeg_arm64/out --enable-gpl --enable-libass"
    " --enable-libx264 --enable-libx265\n"
    "--prefix=/Volumes/ffmpeg_arm64/out --enable-gpl --enable-libass --enable-libx264"
    " --enable-libx265\n"
    "libavcodec license: GPL version 2 or later\n"
)
_LICENCE_CASES = [] if sys.platform == "win32" else [
    ("this recipe's build", _OURS, 0, "LGPL version 2.1 or later"),
    ("the GPL build", _GPL_8_0_1, 1, "configured with --enable-gpl --enable-libx264 --enable-libx265"),
    # Each reading alone refuses: flags that slipped past the licence string, and back.
    ("x264 without --enable-gpl", f"--prefix=/x --enable-libx264\n{_LGPL}", 1, "--enable-libx264"),
    ("quoted x265", f"--prefix=/x '--enable-libx265'\n{_LGPL}", 1, "--enable-libx265"),
    ("LGPL v3", "--prefix=/x --enable-version3\n"
     "libavcodec license: LGPL version 3 or later\n", 1, "--enable-version3"),
    ("GPL licence string, clean flags", "--prefix=/x\nlibavutil license: GPL version 2 or later\n",
     1, "GPL version 2 or later"),
    ("one GPL library among LGPL ones", f"--prefix=/x\n{_LGPL}"
     "libavfilter license: GPL version 3 or later\n", 1, "libavfilter"),
    # Unreadable is not clean.
    ("no configure line", _LGPL, 1, "no embedded configure line"),
    ("no licence strings", "--prefix=/x\n", 1, "no embedded licence strings"),
    ("a prefix that names a flag", f"--prefix=/opt/--enable-gplish\n{_LGPL}", 0, "LGPL"),
]


@pytest.mark.parametrize(("case", "text", "expected", "says"), _LICENCE_CASES)
def test_the_licence_gate(tmp_path: Path, case: str, text: str, expected: int, says: str) -> None:
    (tmp_path / "ffmpeg").write_text(text, encoding="utf-8")
    result = subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "check-ffmpeg-licence.sh"), str(tmp_path / "ffmpeg")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == expected, (case, result.stdout, result.stderr)
    assert says in result.stdout + result.stderr, case


@pytest.mark.parametrize("missing", [] if sys.platform == "win32" else ["ffprobe"])
def test_one_missing_binary_fails_the_whole_gate(tmp_path: Path, missing: str) -> None:
    (tmp_path / "ffmpeg").write_text(_OURS, encoding="utf-8")
    result = subprocess.run(
        ["bash", str(DESKTOP_SCRIPTS / "check-ffmpeg-licence.sh"),
         str(tmp_path / "ffmpeg"), str(tmp_path / missing)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 1 and f"{missing}: not found" in result.stderr
