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
    """Synthetic edit, not a real pin: a test keyed to one pin's text breaks the
    day that pin is lifted, for a reason that has nothing to do with the digest."""
    lock = _lock()
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bumped = text.replace("dependencies = [", 'dependencies = [\n    "not-a-real-package>=1",', 1)
    assert bumped != text
    assert lock.inputs_digest(bumped) != lock.inputs_digest(text)


def test_the_build_installs_against_the_constraints() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert '"--constraint", $constraints' in build


def test_the_build_runs_the_smoke_tests_and_heeds_them() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    call = build.index('"smoke.ps1") -App $app')
    assert 'if ($LASTEXITCODE -ne 0) { throw "smoke tests failed" }' in build[call:call + 200]
    # and an installer build cannot skip them
    assert "if ($SkipSmoke -and $Installer) { throw" in build


def test_the_build_refuses_an_installed_set_the_constraints_do_not_pin() -> None:
    """--constraint pins only what it names; a PyPI wheel from a newer
    pyproject could pull in an unpinned dependency at today's version."""
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    freeze = build.index("& uv pip freeze --python $py")
    assert build.index('"--constraint", $constraints') < freeze
    assert 'if ($drift.Count -gt 0) {' in build[freeze:]


def test_a_manifest_build_must_validate() -> None:
    build = (WIN / "build.ps1").read_text(encoding="utf-8")
    assert 'Run winget @("validate", "--manifest", $manifestDir)' in build
    assert '(Join-Path $PSScriptRoot "validate_manifest.py"), $manifestDir)' in build
    # jsonschema is not in the build venv: the validator gets its own environment
    assert '"--with", "jsonschema"' in build
    assert "if ($Manifest -and -not $ValidateWithSchema -and -not (Get-Command winget" in build


def _validator():
    spec = importlib.util.spec_from_file_location(
        "bn_windows_validate", WIN / "validate_manifest.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _filled_manifests(out: Path, overrides: dict[str, dict[str, str]] | None = None) -> Path:
    """The templates as build.ps1 fills them; ``overrides`` maps a template's
    file name to values that replace the defaults in that file only."""
    defaults = {
        "VERSION": "1.2.3",
        "MANIFEST_VERSION": "1.12.0",
        "INSTALLER_URL": "https://github.com/cassiocassio/bristlenose/releases/download/v1.2.3/bristlenose-1.2.3-setup-x64.exe",
        "INSTALLER_SHA256": "A" * 64,
        "RELEASE_DATE": "2026-10-08",
    }
    out.mkdir(parents=True)
    for template in (WIN / "winget").glob("*.yaml"):
        values = {**defaults, **(overrides or {}).get(template.name, {})}
        text = template.read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace("${" + key + "}", value)
        (out / template.name).write_text(text, encoding="utf-8")
    return out


def test_the_filled_templates_pass_winget_schemas(tmp_path: Path) -> None:
    """What CI runs instead of `winget validate`, since its runner cannot
    install winget: the templates, filled, must satisfy winget's own schemas."""
    assert _validator().validate_dir(_filled_manifests(tmp_path / "m")) == []


def test_the_schema_check_rejects_a_bad_manifest(tmp_path: Path) -> None:
    validator = _validator()
    bad_hash = _filled_manifests(tmp_path / "a", {
        "Bristlenose.Bristlenose.installer.yaml": {"INSTALLER_SHA256": "not-a-sha"},
    })
    assert any("InstallerSha256" in p for p in validator.validate_dir(bad_hash))
    mismatch = _filled_manifests(tmp_path / "b", {
        "Bristlenose.Bristlenose.yaml": {"VERSION": "9.9.9"},
    })
    assert any("disagree" in p for p in validator.validate_dir(mismatch))


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
    # Share-all: a running image still refuses the write open, and a reader
    # that shares (Defender, Explorer's preview) no longer reads as "running".
    assert "TFileStream.Create(Exe, fmOpenReadWrite or fmShareDenyNone)" in iss
    assert "SWbemLocator')" not in iss
    for hook in ("function PrepareToInstall", "function InitializeUninstall"):
        body = iss.split(hook, 1)[1].split("\nend;", 1)[0]
        assert "BristlenoseRunning()" in body, hook


def test_uninstall_never_deletes_the_install_folder_wholesale() -> None:
    """winget passes --location through as /DIR=, so {app} can be a folder of
    the user's; "filesandordirs {app}" would delete everything in it."""
    import re

    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    section = iss.split("[UninstallDelete]", 1)[1].split("\n[", 1)[0]
    entries = [ln for ln in section.splitlines() if ln.startswith("Type:")]
    assert entries, "no [UninstallDelete] entries"
    for line in entries:
        kind, name = re.match(r'Type: (\w+); Name: "([^"]+)"', line).groups()
        assert not (kind == "filesandordirs" and name == "{app}"), line
    assert 'Type: dirifempty; Name: "{app}"' in section


def test_winget_reads_the_refusal_as_package_in_use() -> None:
    """Silent mode shows no message: without this mapping a user sees only
    "Installer failed with exit code: 7"."""
    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" in iss  # the refusal that exits 7
    installer = (WIN / "winget" / "Bristlenose.Bristlenose.installer.yaml").read_text(
        encoding="utf-8"
    )
    assert "- InstallerReturnCode: 7\n  ReturnResponse: packageInUse" in installer
