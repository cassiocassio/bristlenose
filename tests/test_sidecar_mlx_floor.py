"""The sidecar's MLX must be built for the app's floor, and the gate must say so.

30 Oct 2026: the shipped sidecar carried MLX's ``macosx_26_0`` wheels (minos 26.2) in an
app whose floor is macOS 15. On a clean macOS 15.7.7 guest ``import mlx_whisper`` aborted
in ``mlx::core::metal::Device::Device()`` and the Whisper probe, every Retry and ``run``
died with it. ``desktop/scripts/check-sidecar-mlx-floor.sh`` is the gate; these tests
drive it against synthetic bundles holding real Mach-O files, and pin that it is wired
in (a gate script with no caller is not a gate).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "desktop" / "scripts"
_GATE = _SCRIPTS / "check-sidecar-mlx-floor.sh"

needs_macho_tools = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("cc") is None or shutil.which("otool") is None,
    reason="builds real Mach-O files with cc and reads them with otool",
)


def _dylib(path: Path, minos: str) -> None:
    src = path.with_suffix(".c")
    src.write_text("int bn_probe(void) { return 0; }\n", encoding="utf-8")
    subprocess.run(
        ["cc", "-dynamiclib", f"-mmacosx-version-min={minos}", "-arch", "arm64",
         "-o", str(path), str(src)],
        check=True, capture_output=True,
    )
    src.unlink()


def _bundle(root: Path, *, tag: str, core_minos: str, lib_minos: str) -> Path:
    """A sidecar dir with the MLX files the gate reads, at the given tag and minos."""
    internal = root / "_internal"
    (internal / "mlx" / "lib").mkdir(parents=True)
    _dylib(internal / "mlx" / "core.cpython-312-darwin.so", core_minos)
    _dylib(internal / "mlx" / "lib" / "libmlx.dylib", lib_minos)
    for pkg, py in (("mlx", "cp312-cp312"), ("mlx_metal", "py3-none")):
        dist = internal / f"{pkg}-0.32.4.dist-info"
        dist.mkdir()
        (dist / "WHEEL").write_text(
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {py}-{tag}\n", encoding="utf-8"
        )
    return root


def _run(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(_GATE), str(bundle)], capture_output=True, text=True)


@needs_macho_tools
class TestGateBehaviour:
    def test_floor_build_passes(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="15.0")
        r = _run(b)
        assert r.returncode == 0, r.stderr
        assert "2 binaries read" in r.stdout

    def test_older_than_floor_passes(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_14_0_arm64", core_minos="14.0", lib_minos="14.0")
        assert _run(b).returncode == 0

    def test_host_built_wheels_fail_on_the_tag(self, tmp_path: Path) -> None:
        # The 0.43.0 shape: pip took the build host's newest wheel.
        b = _bundle(tmp_path, tag="macosx_26_0_arm64", core_minos="26.0", lib_minos="26.0")
        r = _run(b)
        assert r.returncode == 1
        assert "macosx_26_0_arm64" in r.stderr
        assert "floor is 15.0" in r.stderr

    def test_a_floor_tag_does_not_vouch_for_a_newer_binary(self, tmp_path: Path) -> None:
        # The receipt says 15 but the file the app loads says otherwise: the fact wins.
        b = _bundle(tmp_path, tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="26.2")
        r = _run(b)
        assert r.returncode == 1
        assert "libmlx.dylib has minos 26.2" in r.stderr

    def test_a_floor_binary_does_not_vouch_for_a_newer_tag(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_26_0_arm64", core_minos="15.0", lib_minos="15.0")
        assert _run(b).returncode == 1

    def test_missing_dist_info_fails_rather_than_passes(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="15.0")
        for d in (b / "_internal").glob("mlx*.dist-info"):
            shutil.rmtree(d)
        r = _run(b)
        assert r.returncode == 1
        assert "no dist-info/WHEEL" in r.stderr

    def test_missing_binaries_fail_rather_than_pass(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="15.0")
        (b / "_internal" / "mlx" / "lib" / "libmlx.dylib").unlink()
        assert _run(b).returncode == 1

    def test_a_stale_dist_info_does_not_hide_a_newer_one(self, tmp_path: Path) -> None:
        # Two mlx dist-infos: the lexicographically first is a leftover at the floor, the
        # second is what pip really chose. The verdict must not be the first one's.
        b = _bundle(tmp_path, tag="macosx_26_0_arm64", core_minos="15.0", lib_minos="15.0")
        # mlx-metal is fine, so the ONLY thing wrong is the real mlx dist-info the stale
        # one sorts in front of. Otherwise mlx-metal's tag fails the run by itself.
        (b / "_internal" / "mlx_metal-0.32.4.dist-info" / "WHEEL").write_text(
            "Tag: py3-none-macosx_15_0_arm64\n", encoding="utf-8"
        )
        stale = b / "_internal" / "mlx-0.30.0.dist-info"
        stale.mkdir()
        (stale / "WHEEL").write_text("Tag: cp312-cp312-macosx_15_0_arm64\n", encoding="utf-8")
        r = _run(b)
        assert r.returncode == 1
        assert "macosx_26_0_arm64" in r.stderr

    def test_an_unreadable_binary_says_so_and_fails(self, tmp_path: Path) -> None:
        b = _bundle(tmp_path, tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="15.0")
        lib = b / "_internal" / "mlx" / "lib" / "libmlx.dylib"
        lib.chmod(0o000)
        try:
            r = _run(b)
        finally:
            lib.chmod(0o644)
        assert r.returncode == 1
        assert "libmlx.dylib" in r.stderr  # a named failure, not a silent exit

    def test_not_a_bundle_is_a_usage_error(self, tmp_path: Path) -> None:
        assert _run(tmp_path).returncode == 2


class TestGateIsWired:
    """A gate script with no caller is not a gate (CLAUDE.md, Gate policy)."""

    @pytest.mark.parametrize(
        "script", ["build-sidecar.sh", "check-dmg-shippable.sh", "check-pkg-shippable.sh"]
    )
    def test_caller_invokes_the_gate(self, script: str) -> None:
        # A live, uncommented line: a comment or an echo naming the script is not a call.
        live = [
            ln for ln in (_SCRIPTS / script).read_text(encoding="utf-8").splitlines()
            if "check-sidecar-mlx-floor.sh" in ln and not ln.lstrip().startswith("#")
        ]
        assert live, f"{script} never runs check-sidecar-mlx-floor.sh"
        assert any(("if " in ln) or ("$(" in ln) for ln in live), (
            f"{script} runs the gate but does not branch on its exit status: {live}"
        )

    def test_gate_reads_the_floor_from_the_one_place_that_pins_it(self) -> None:
        body = _GATE.read_text(encoding="utf-8")
        assert "check-deployment-floors.sh" in body
        floors = (_SCRIPTS / "check-deployment-floors.sh").read_text(encoding="utf-8")
        assert 'EXPECT_APP="' in floors


class TestBuildPinsMlxToTheFloor:
    """build-sidecar.sh must put the floor wheels in, and notice when it hasn't."""

    def _body(self) -> str:
        return (_SCRIPTS / "build-sidecar.sh").read_text(encoding="utf-8")

    def test_pin_runs_straight_after_the_editable_install(self) -> None:
        body = self._body()
        install = body.index('install $cache_bypass -e "$ROOT[$SIDECAR_EXTRAS]"')
        pin = body.index("\n        _pin_mlx_to_floor\n")
        stamp = body.index('_deps_fingerprint > "$DEPS_STAMP"')
        assert install < pin < stamp, "the pin must land before the stamp and sentinel"

    def test_fingerprint_sees_the_wheel_tag_not_just_the_version(self) -> None:
        body = self._body()
        fp = body[body.index("_deps_fingerprint() {"):]
        fp = fp[: fp.index("\n}\n")]
        assert "_mlx_wheel_tags" in fp
        assert "MLX_FLOOR_PLATFORM" in fp

    def test_a_missing_floor_wheel_stops_the_build(self) -> None:
        body = self._body()
        fn = body[body.index("_pin_mlx_to_floor() {"):]
        fn = fn[: fn.index("\n}\n")]
        assert "--platform \"$MLX_FLOOR_PLATFORM\"" in fn
        assert "exit 1" in fn

    def test_floor_platform_matches_the_app_floor(self) -> None:
        floors = (_SCRIPTS / "check-deployment-floors.sh").read_text(encoding="utf-8")
        app = next(
            ln.split('"')[1] for ln in floors.splitlines() if ln.startswith('EXPECT_APP="')
        )
        major, minor = app.split(".")
        assert f'MLX_FLOOR_PLATFORM="macosx_{major}_{minor}_arm64"' in self._body()


@needs_macho_tools
def test_a_floor_written_without_a_minor_still_compares(tmp_path: Path) -> None:
    """`sort -V` ranks 15.0 above 15; the gate normalises both sides before comparing."""
    import re

    gate = tmp_path / "gate"
    gate.mkdir()
    body = _GATE.read_text(encoding="utf-8")
    shutil.copy(_SCRIPTS / "check-deployment-floors.sh", gate / "check-deployment-floors.sh")
    floors = gate / "check-deployment-floors.sh"
    floors.write_text(
        re.sub(r'^EXPECT_APP="[0-9.]+"', 'EXPECT_APP="15"',
               floors.read_text(encoding="utf-8"), flags=re.M),
        encoding="utf-8",
    )
    script = gate / "check-sidecar-mlx-floor.sh"
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    b = _bundle(tmp_path / "b", tag="macosx_15_0_arm64", core_minos="15.0", lib_minos="15.0")
    ok = subprocess.run([str(script), str(b)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    bad = _bundle(tmp_path / "c", tag="macosx_26_0_arm64", core_minos="26.0", lib_minos="26.0")
    assert subprocess.run([str(script), str(bad)], capture_output=True).returncode == 1
