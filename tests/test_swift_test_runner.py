"""Both native test processes must earn the runner's green receipt."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "mode,green",
    [("green", True), ("general_red", False), ("pool_red", False),
     ("general_crash", False), ("pool_crash", False),
     ("general_empty", False), ("pool_empty", False)],
)
def test_both_processes_required_for_receipt(tmp_path, mode, green):
    root = tmp_path / "repo"
    scripts = root / "desktop/scripts"
    scripts.mkdir(parents=True)
    (root / "desktop/Bristlenose").mkdir()
    (root / ".gitignore").write_text("desktop/build/\n")
    script = scripts / "test-swift.sh"
    shutil.copyfile(Path(__file__).resolve().parents[1] / "desktop/scripts/test-swift.sh", script)
    for args in [
        ["init", "--quiet"], ["add", "."],
        ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "commit", "--quiet", "-m", "fixture"],
    ]:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    binaries = tmp_path / "bin"
    binaries.mkdir()
    fake = binaries / "xcodebuild"
    fake.write_text(f"#!{sys.executable}\n" + '''
import os, sys
if "build-for-testing" in sys.argv:
    sys.exit(0)
leg = "pool" if "-only-testing:BristlenoseTests/PoolStarvationTimeoutTests" in sys.argv else "general"
with open(os.environ["CALLS"], "a") as log:
    log.write(leg + "\\n")
mode = os.environ["MODE"]
if mode == leg + "_crash":
    sys.exit(70)
if mode == leg + "_empty":
    sys.exit(0)
verdict = "failed" if mode == leg + "_red" else "passed"
print("Test case '" + leg + "/case()' " + verdict + " on 'Fixture' (0.01 seconds)")
sys.exit(65 if verdict == "failed" else 0)
''')
    fake.chmod(0o755)
    xcrun = binaries / "xcrun"
    xcrun.write_text("#!/bin/sh\nprintf '%s\\n' '{\"testFailures\":[]}'\n")
    xcrun.chmod(0o755)
    stamp = root / "desktop/build/swift-green.stamp"
    stamp.parent.mkdir()
    stamp.write_text("stale receipt must never survive a failed run")
    calls = tmp_path / "calls"
    result = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True,
        env={**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
             "MODE": mode, "CALLS": str(calls), "BN_LOG_DIR": str(tmp_path / "logs"),
             "BN_RELEASE_RUN": "fixture-run"},
    )
    assert calls.read_text().splitlines() == ["general", "pool"]
    assert (result.returncode == 0) is green, result.stdout + result.stderr
    assert stamp.exists() is green
    if green:
        assert stamp.read_text().startswith("run=fixture-run sha=")
