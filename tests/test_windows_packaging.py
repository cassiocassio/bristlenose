"""The Windows installer build's own contracts (docs/design-winget.md).

packaging/windows/ is not a Python package (and must not shadow the `packaging`
library), so its lock script is loaded by path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "packaging" / "windows"


def _lock():
    spec = importlib.util.spec_from_file_location("bn_windows_lock", WIN / "lock.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_constraints_match_the_dependencies_they_were_compiled_from() -> None:
    """A dependency change without `python packaging/windows/lock.py` means the
    Windows build would install a set nothing compiled or tested."""
    lock = _lock()
    recorded = lock.recorded_digest((WIN / "constraints.txt").read_text(encoding="utf-8"))
    assert recorded == lock.inputs_digest(), (
        "pyproject.toml's dependencies changed: run `python packaging/windows/lock.py`"
    )


def test_the_digest_moves_when_a_dependency_does() -> None:
    lock = _lock()
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bumped = text.replace('"av<19"', '"av<20"', 1)
    assert bumped != text
    assert lock.inputs_digest(bumped) != lock.inputs_digest(text)


def test_the_build_installs_against_the_constraints() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert '"--constraint", $constraints' in build


def test_the_build_runs_the_smoke_tests() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert '"smoke.ps1") -App $app' in build


def test_the_smoke_tests_fixture_is_where_they_look() -> None:
    """smoke.ps1 transcribes this VTT and serves this project; moving either
    would fail only on a Windows build box, hours later."""
    smoke = (WIN / "smoke.ps1").read_text(encoding="utf-8")
    fixture = ROOT / "tests" / "fixtures" / "smoke-test" / "input"
    assert 'tests\\fixtures\\smoke-test\\input' in smoke
    assert '"Session 1.vtt"' in smoke and (fixture / "Session 1.vtt").is_file()
    assert (fixture / "bristlenose-output" / ".bristlenose" / "pipeline-events.jsonl").is_file()


def test_the_manifest_product_code_is_the_installers_app_id() -> None:
    """winget finds an installed copy by this code; if it drifts from the Inno
    AppId, `winget upgrade` installs a second copy beside the first."""
    import re

    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    app_id = re.search(r"^AppId=\{(\{[0-9A-F-]+\})$", iss, re.M)
    assert app_id
    installer = (WIN / "winget" / "Bristlenose.Bristlenose.installer.yaml").read_text(
        encoding="utf-8"
    )
    assert f"ProductCode: '{app_id.group(1)}_is1'" in installer


def test_the_manifest_templates_use_only_what_the_build_fills() -> None:
    import re

    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    filled = set(re.findall(r"^\s+([A-Z_0-9]+)\s+= ", build, re.M))
    for template in (WIN / "winget").glob("*.yaml"):
        used = set(re.findall(r"\$\{([A-Z_0-9]+)\}", template.read_text(encoding="utf-8")))
        assert used and used <= filled, (template.name, used - filled)


def test_the_build_packages_the_wheel_not_the_checkout() -> None:
    """Run from the repo root, a cwd or repo-root entry on sys.path makes the
    bundle carry the working tree instead of the released wheel (found on the
    acceptance box, 6 Oct 2026)."""
    spec = (WIN / "bristlenose-win.spec").read_text(encoding="utf-8")
    assert "pathex=[]" in spec and "PROJECT_ROOT" not in spec
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert '& $py -P -c "import bristlenose' in build
    assert 'Run $py @("-P", "-m", "PyInstaller"' in build


def test_the_installer_refuses_while_bristlenose_runs() -> None:
    """Restart Manager could not close a running serve for a non-admin user, and
    the aborted upgrade left bristlenose.exe without _internal. The check must be
    the file lock: a WMI query was refused to that user and failed open."""
    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    assert "fmOpenReadWrite or fmShareExclusive" in iss
    assert "SWbemLocator')" not in iss
    for hook in ("function PrepareToInstall", "function InitializeUninstall"):
        body = iss.split(hook, 1)[1].split("\nend;", 1)[0]
        assert "BristlenoseRunning()" in body, hook
