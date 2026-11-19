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
        "MANIFEST_VERSION": "1.28.0",
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


def test_the_manifest_does_not_repeat_package_version_as_display_version() -> None:
    """winget-pkgs moderation bounces a DisplayVersion equal to PackageVersion
    (microsoft/winget-pkgs#449372, 4 Nov 2026). Inno's AppVersion is our version,
    so the field is only ever a duplicate."""
    installer = (WIN / "winget" / "Bristlenose.Bristlenose.installer.yaml").read_text(
        encoding="utf-8"
    )
    assert "DisplayVersion" not in installer.split("AppsAndFeaturesEntries:", 1)[1]


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


def test_a_silent_uninstall_refuses_without_a_dialog() -> None:
    """winget runs the uninstaller with /SILENT and no /SUPPRESSMSGBOXES; the
    "Bristlenose is running" box then waited for a click (Windows 11 VM, 9 Nov 2026)."""
    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    body = iss.split("function InitializeUninstall", 1)[1].split("\nend;", 1)[0]
    assert "if not UninstallSilent() then" in body
    assert body.index("if not UninstallSilent() then") < body.index("MsgBox(")


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


def test_hf_xet_is_bundled_with_its_metadata() -> None:
    """huggingface_hub imports hf_xet lazily and finds it through importlib.metadata,
    so the frozen build needs both; without them model downloads print "hf_xet is
    not installed" and fall back to plain HTTP (seen on Windows 10/11, 9 Oct 2026)."""
    spec = (WIN / "bristlenose-win.spec").read_text(encoding="utf-8")
    assert '"hf_xet",' in spec
    assert 'copy_metadata("hf-xet")' in spec
    assert "hf-xet==" in (WIN / "constraints.txt").read_text(encoding="utf-8")



def test_the_acceptance_script_names_the_installers_app_id() -> None:
    """winget-accept.ps1 finds the install by its Apps & Features key, which is
    bristlenose.iss's AppId plus Inno's _is1, the manifest's ProductCode."""
    import re

    iss = (WIN / "bristlenose.iss").read_text(encoding="utf-8")
    app_id = re.search(r"^AppId=\{(\{[0-9A-F-]+\})$", iss, re.M)
    assert app_id, "AppId line not found in bristlenose.iss"
    product_code = f"{app_id.group(1)}_is1"
    manifest = (WIN / "winget" / "Bristlenose.Bristlenose.installer.yaml").read_text(encoding="utf-8")
    assert f"ProductCode: '{product_code}'" in manifest
    script = (WIN / "winget-accept.ps1").read_text(encoding="utf-8")
    assert f'$AppId = "{product_code}"' in script


def test_the_windows_scripts_are_ascii() -> None:
    """Windows PowerShell 5.1 reads a .ps1 without a byte-order mark as the ANSI
    code page, so a UTF-8 dash or section sign turns into stray characters, and
    one of them is a quotation mark to the parser."""
    for script in WIN.glob("*.ps1"):
        text = script.read_bytes()
        assert text.isascii(), (script.name, [i for i, b in enumerate(text) if b > 127][:5])


def test_the_cpu_path_patterns_match_what_ctranslate2_prints(tmp_path: Path) -> None:
    """winget-accept.ps1 -CpuPaths fails a path unless CTranslate2 reports taking
    it. The patterns are checked here against a real CTranslate2 run on a
    two-token model built in place (no download), so a changed log line fails
    this test instead of every path on a Windows guest. Each path's patterns
    must match its own run and not the default run, or they prove nothing."""
    import os
    import platform
    import re
    import subprocess
    import sys

    import pytest

    np = pytest.importorskip("numpy")
    pytest.importorskip("ctranslate2")
    from ctranslate2 import specs

    if not sys.platform.startswith("linux") or platform.machine() not in ("x86_64", "AMD64"):
        pytest.skip("reads CTranslate2's x86-64 Linux build, which carries MKL")

    d, ff, vocab = 8, 16, 10
    rng = np.random.default_rng(0)

    def weights(*shape: int) -> object:
        return rng.random(shape, dtype=np.float32) - 0.5

    enc = specs.TransformerEncoderSpec(1, 1)
    enc.embeddings[0].weight = weights(vocab, d)
    layer = enc.layer[0]
    for norm in (layer.ffn.layer_norm, layer.self_attention.layer_norm, enc.layer_norm):
        norm.gamma = np.ones(d, np.float32)
        norm.beta = np.zeros(d, np.float32)
    layer.ffn.linear_0.weight = weights(ff, d)
    layer.ffn.linear_1.weight = weights(d, ff)
    layer.self_attention.linear[0].weight = weights(3 * d, d)
    layer.self_attention.linear[1].weight = weights(d, d)
    model = specs.TransformerEncoderModelSpec(enc)
    model.register_vocabulary([f"t{i}" for i in range(vocab)])
    model.validate()
    model.optimize(quantization=None)
    model_dir = tmp_path / "tiny"
    model_dir.mkdir()
    model.save(str(model_dir))

    script = (WIN / "winget-accept.ps1").read_text(encoding="utf-8")
    entries = re.findall(
        r'Name = "([\w-]+)"; Env = @\{([^}]*)\};\s*Expect = @\(([^)]*)\)', script,
    )
    assert {name for name, _, _ in entries} == {"intel-avx2", "non-mkl", "generic"}, entries

    probe = (
        "import sys, ctranslate2\n"
        "ctranslate2.Encoder(sys.argv[1], device='cpu').forward_batch([['t1', 't2']])\n"
    )

    def run(extra: dict[str, str]) -> str:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CT2_", "MKL_"))}
        env.update(extra, CT2_VERBOSE="1")
        done = subprocess.run(
            [sys.executable, "-c", probe, str(model_dir)],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
        )
        assert done.returncode == 0, done.stderr[-500:]
        return done.stdout + done.stderr

    default = run({})
    assert "Selected ISA:" in default, default[-500:]
    if "Use Intel MKL: true" not in default:
        # CTranslate2 uses MKL by default only on an Intel CPU. On AMD the default
        # run is already the non-MKL path, so "the patterns miss the default run"
        # cannot hold for it; an Intel machine is where this test means something.
        pytest.skip("not an Intel CPU: the default run is already the non-MKL path")
    for name, env_block, expect_block in entries:
        extra = dict(re.findall(r'(\w+) = "([^"]*)"', env_block))
        patterns = re.findall(r'"([^"]+)"', expect_block)
        output = run(extra)
        for pattern in patterns:
            assert re.search(pattern, output), (name, pattern, output[-600:])
        assert not all(re.search(p, default) for p in patterns), (
            f"{name}'s patterns also match the default run, so they prove nothing", patterns)
