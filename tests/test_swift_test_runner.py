"""Both native test processes must earn the runner's green receipt."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# shutil.which follows PATH. A bare "bash" on Windows is resolved by
# CreateProcess, which tries System32 first and so finds WSL's bash.exe, which
# runs nothing (the fake was never called; 0.44.0 strict CI).
_BASH = shutil.which("bash") or "bash"

# The fakes are #!/bin/sh wrappers that exec this interpreter on a sibling .py:
# a #!<python> shebang is a Windows path there, and /bin/sh is what Git Bash
# runs stubs with (test_dmg_lane.py). The paths travel as env values, which
# MSYS passes through untouched, so python.exe reads them as it was given them.
_FAKE_XCODEBUILD = '''
import os, sys
if "build-for-testing" in sys.argv:
    sys.exit(0)
def flag(prefix, suite):
    return any(a.startswith(prefix) and a.endswith(suite) for a in sys.argv)
pool_suite = "PoolStarvationTimeoutTests"
leg = "pool" if flag("-only-testing:", pool_suite) else "general"
with open(os.environ["CALLS"], "a") as log:
    log.write(leg + "\\n")
skips_pool = flag("-skip-testing:", pool_suite)
with open(os.environ["CALLS"] + ".skips", "a") as log:
    log.write(leg + " skips_pool=" + str(skips_pool) + "\\n")
mode = os.environ["MODE"]
if mode == leg + "_crash":
    sys.exit(70)
if mode == leg + "_empty":
    sys.exit(0)
verdict = "failed" if mode == leg + "_red" else "passed"
print("Test case '" + leg + "/case()' " + verdict + " on 'Fixture' (0.01 seconds)")
sys.exit(65 if verdict == "failed" else 0)
'''


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
    fake_py = binaries / "xcodebuild.py"
    fake_py.write_text(_FAKE_XCODEBUILD)
    fake = binaries / "xcodebuild"
    fake.write_text('#!/bin/sh\nexec "$FAKE_PYTHON" "$FAKE_XCODEBUILD" "$@"\n')
    fake.chmod(0o755)
    xcrun = binaries / "xcrun"
    xcrun.write_text("#!/bin/sh\nprintf '%s\\n' '{\"testFailures\":[]}'\n")
    xcrun.chmod(0o755)
    stamp = root / "desktop/build/swift-green.stamp"
    stamp.parent.mkdir()
    stamp.write_text("stale receipt must never survive a failed run")
    calls = tmp_path / "calls"
    result = subprocess.run(
        [_BASH, str(script)], capture_output=True, text=True,
        env={**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
             "MODE": mode, "CALLS": str(calls), "BN_LOG_DIR": str(tmp_path / "logs"),
             "BN_RELEASE_RUN": "fixture-run",
             "FAKE_PYTHON": sys.executable, "FAKE_XCODEBUILD": str(fake_py)},
    )
    assert calls.exists(), f"the fake xcodebuild never ran:\n{result.stdout}{result.stderr}"
    assert calls.read_text().splitlines() == ["general", "pool"]
    # The general process must leave the pool suite to its own process: dropping
    # the skip flag would run it twice and bring back the contention the split
    # exists to remove, with every other assertion here still green.
    assert (tmp_path / "calls.skips").read_text().splitlines() == [
        "general skips_pool=True", "pool skips_pool=False",
    ]
    assert (result.returncode == 0) is green, result.stdout + result.stderr
    assert stamp.exists() is green
    if green:
        assert stamp.read_text().startswith("run=fixture-run sha=")
