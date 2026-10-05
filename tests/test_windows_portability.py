"""Windows portability, tested from any platform.

The run path once named ``os.O_NOFOLLOW`` directly. Windows has no such
attribute, so the first event write of every run raised ``AttributeError``
there. These tests remove the attribute the way Windows lacks it and drive real
call sites, and a source gate stops a sixth site from naming it again.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import bristlenose

_PKG = Path(bristlenose.__file__).parent


@pytest.fixture
def no_nofollow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``os`` module as Windows has it: no ``O_NOFOLLOW``."""
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)


def test_no_module_names_o_nofollow_directly() -> None:
    """Only ``open_private`` may reach for the flag, and only via ``getattr``."""
    offenders = [
        f"{path.relative_to(_PKG)}:{n}"
        for path in _PKG.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bos\.O_NOFOLLOW\b", line)
    ]
    assert offenders == [], f"use utils.fs.open_private instead: {offenders}"


def test_pid_file_writes_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.run_lifecycle import _read_pid_file, _write_pid_file

    _write_pid_file(tmp_path, "run-1", "start")
    assert _read_pid_file(tmp_path) == {
        "pid": os.getpid(), "start_time": "start", "run_id": "run-1",
    }


def test_shoal_feed_writes_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.shoal_feed import _write

    path = tmp_path / ".bristlenose" / "feed.jsonl"
    _write(path, line='{"a": 1}')
    _write(path, line='{"b": 2}')
    # Bytes, not text: a text-mode open on Windows would write \r\n here.
    assert path.read_bytes() == b'{"a": 1}\n{"b": 2}\n'


def test_backup_append_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.utils.output_backup import _append_onto

    src, dest = tmp_path / "src.jsonl", tmp_path / "dest.jsonl"
    src.write_bytes(b"two\n")
    dest.write_bytes(b"one\n")
    assert _append_onto(src, dest)
    assert dest.read_bytes() == b"one\ntwo\n"


def test_open_private_is_owner_only(tmp_path: Path) -> None:
    from bristlenose.utils.fs import open_private

    path = tmp_path / "f"
    os.close(open_private(path, os.O_WRONLY | os.O_CREAT))
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name != "posix", reason="symlink refusal is POSIX-only")
def test_open_private_still_refuses_a_symlink(tmp_path: Path) -> None:
    from bristlenose.utils.fs import open_private

    target = tmp_path / "elsewhere"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        open_private(link, os.O_WRONLY | os.O_APPEND)


def test_manifest_rewrites_over_itself(tmp_path: Path) -> None:
    """Every stage rewrites the manifest; the second write must not fail.

    It was ``tmp.rename(path)``, which overwrites on POSIX and raises
    FileExistsError on Windows, so a Windows run died at its second stage. The
    first Windows CI run found it (5 Oct 2026); ``transcribe`` writes no
    manifest, so the smoke run could not.
    """
    from bristlenose.manifest import PipelineManifest, load_manifest, write_manifest

    def manifest(updated: str) -> PipelineManifest:
        return PipelineManifest(
            project_name="p", pipeline_version="0", created_at="t0", updated_at=updated,
        )

    write_manifest(manifest("t1"), tmp_path)
    write_manifest(manifest("t2"), tmp_path)
    loaded = load_manifest(tmp_path)
    assert loaded is not None and loaded.updated_at == "t2"


def test_start_time_tracks_a_live_process() -> None:
    """A live run reads as live, and a finished one as gone — on every platform.

    ``_ps_start_time`` reads libproc on macOS, ``ps`` on Linux and
    ``GetProcessTimes`` on Windows, so the windows-latest CI job is where the
    Windows reader meets a real process. Without one, every live run read as
    dead there, and a second run on the same folder was not refused. No skip:
    each platform proves its own reader.
    """
    from bristlenose.run_lifecycle import _is_alive_owned, _ps_start_time

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        first = _ps_start_time(child.pid)
        assert first, "no start time for a running process"
        assert _ps_start_time(child.pid) == first, "start time is not stable"
        assert _is_alive_owned({"pid": child.pid, "start_time": first})
        assert not _is_alive_owned({"pid": child.pid, "start_time": "0.0"})
    finally:
        child.kill()
        child.wait()
    # On Windows, Popen still holds a handle, so OpenProcess succeeds; the
    # exit-code check is what has to say "gone".
    assert _ps_start_time(child.pid) is None
    assert _ps_start_time(os.getpid()), "this process has no start time"


class TestWindowsFixText:
    """Doctor advice a Windows user can actually type."""

    @pytest.fixture(autouse=True)
    def _windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import platform
        import sys

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(platform, "system", lambda: "Windows")

    def test_ffmpeg_offers_winget(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        text = get_fix("ffmpeg_missing", "pip")
        assert "winget install --id Gyan.FFmpeg -e --source winget" in text
        assert "new terminal" in text

    def test_azure_and_proxy_use_setx_not_export(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        for key in ("api_key_missing_azure", "network_unreachable"):
            text = get_fix(key, "pip")
            assert "setx " in text, key
            assert "export " not in text, key

    def test_key_hint_names_the_real_file(self) -> None:
        from bristlenose.credentials import user_config_env_path
        from bristlenose.doctor_fixes import _credential_store_hint

        assert str(user_config_env_path()) in _credential_store_hint()


@pytest.fixture
def cp1252_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text-mode subprocess output decoded the way Windows decodes it.

    ``subprocess`` with ``text=True`` and no ``encoding`` decodes with the
    locale encoding, which is cp1252 on a Western Windows install, while
    ffmpeg and ffprobe write UTF-8 there.
    """
    import locale

    # 3.11+ asks _text_encoding, which answers utf-8 whenever UTF-8 mode is
    # on — and a C locale turns it on, so patching locale alone proves nothing
    # on a CI shell. 3.10 asks locale directly.
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp1252", raising=False)
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "cp1252")


def test_a_kanji_filename_probes_under_a_windows_codepage(
    cp1252_locale: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ffprobe echoes the filename in its JSON; 会 and 録 do not decode as cp1252.

    Decoded with the locale encoding, ``subprocess.run`` raised
    ``UnicodeDecodeError`` out of ``probe_media`` — the ingest probe — for a
    recording named in Japanese or Chinese. The real call runs, with ffprobe's
    bytes supplied by a Python child, so the decoding under test is the one
    ``probe_media`` asks for.
    """
    import json

    import bristlenose.utils.audio as audio

    name = "会議の録音.wav"
    payload = json.dumps(
        {"format": {"filename": name, "duration": "12.5"}, "streams": []}, ensure_ascii=False,
    ).encode("utf-8")
    real_run = subprocess.run

    def ffprobe(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        child = [sys.executable, "-c", f"import sys; sys.stdout.buffer.write({payload!r})"]
        return real_run(child, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(audio.subprocess, "run", ffprobe)
    (tmp_path / name).write_bytes(b"")
    duration, _ = audio.probe_media(tmp_path / name)
    assert duration == 12.5


def test_every_text_subprocess_names_its_encoding() -> None:
    """``text=True`` alone decodes with the locale codepage, cp1252 on Windows."""
    import ast

    offenders = []
    for path in _PKG.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {k.arg: k.value for k in node.keywords}
            text = any(
                isinstance(kwargs.get(k), ast.Constant) and kwargs[k].value is True  # type: ignore[union-attr]
                for k in ("text", "universal_newlines")
            )
            if text and "encoding" not in kwargs:
                offenders.append(f"{path.relative_to(_PKG)}:{node.lineno}")
    assert offenders == [], f"add encoding='utf-8' to: {offenders}"


def test_llm_log_trims_without_fchmod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows has no ``os.fchmod``; the trim at each run's end called it.

    The log grows across runs, so a project's first runs were fine and every
    run after it passed 1,000 calls raised at the terminus, after the report
    was written. That the rewrite stays owner-only is
    test_llm_telemetry's test_trim_to_cap_rewrite_is_owner_only.
    """
    from bristlenose.llm.telemetry import trim_to_cap

    monkeypatch.delattr(os, "fchmod", raising=False)
    path = tmp_path / "llm-calls.jsonl"
    path.write_bytes(b"".join(b"%d\n" % i for i in range(5)))
    assert trim_to_cap(path, cap=2) == 2
    assert path.read_bytes() == b"3\n4\n"
    assert [p.name for p in tmp_path.iterdir()] == ["llm-calls.jsonl"]


def test_every_text_file_read_and_write_names_its_encoding() -> None:
    """``open``/``read_text``/``write_text`` default to the locale codepage too.

    On Windows that is cp1252: a transcript, a quote or a participant name
    outside it raises on write and mis-reads on load. Binary modes are exempt.
    """
    import ast

    offenders = []
    for path in _PKG.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in ("read_text", "write_text"):
                offenders.append(f"{path.relative_to(_PKG)}:{node.lineno}")
            elif name == "open" and not (
                isinstance(func, ast.Attribute) and getattr(func.value, "id", "") in ("os", "webbrowser")
            ):
                mode_at = 0 if isinstance(func, ast.Attribute) else 1
                mode = next((k.value for k in node.keywords if k.arg == "mode"), None)
                if mode is None and len(node.args) > mode_at:
                    mode = node.args[mode_at]
                text = mode is None or (isinstance(mode, ast.Constant) and "b" not in str(mode.value))
                if text and (node.args or isinstance(func, ast.Attribute)):
                    offenders.append(f"{path.relative_to(_PKG)}:{node.lineno}")
    assert offenders == [], f"add encoding='utf-8' to: {offenders}"


def test_redirected_output_in_a_codepage_prints_rather_than_crashes(tmp_path: Path) -> None:
    """``bristlenose doctor > out.txt`` on Windows: stdout is cp1252, which has no ``✓``.

    Found on a Windows 11 VM (5 Oct 2026): every command that printed a tick
    raised UnicodeEncodeError before any output when redirected or piped; then,
    replaced with ``?``, a saved log could not tell a pass from a fail. The
    child's stdout is forced to cp1252, which reproduces it on any OS, and
    ``pipeline`` is a real command that prints ticks, crosses and dots without a
    project. Its own "untested" marker is a literal ``?``, so the count of ``?``
    must match a UTF-8 run of the same command: no symbol may collapse into one.
    """
    def run(encoding: str) -> subprocess.CompletedProcess[bytes]:
        env = {**os.environ, "PYTHONIOENCODING": encoding, "HOME": str(tmp_path),
               "USERPROFILE": str(tmp_path), "NO_COLOR": "1"}
        env.pop("PYTHONUTF8", None)
        return subprocess.run(
            [sys.executable, "-m", "bristlenose", "pipeline"],
            capture_output=True, env=env, timeout=120,
        )

    narrow, wide = run("cp1252"), run("utf-8")
    assert narrow.returncode == 0, narrow.stderr.decode("cp1252", "replace")[-600:]
    assert b"UnicodeEncodeError" not in narrow.stderr
    text = narrow.stdout.decode("cp1252")
    assert "+" in text, "the pass glyph did not become +"
    assert text.count("?") == wide.stdout.decode("utf-8").count("?"), text



def test_a_config_file_key_store_is_not_called_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows has no Keychain or Secret Service; the key goes to a plain .env.

    First-run guidance said "stores it securely (config file)" there, a claim
    the store does not earn. The Keychain wording is unchanged.
    """
    import io

    from rich.console import Console

    import bristlenose.cli as cli

    for label, secure in (("config file", False), ("Keychain", True)):
        buf = io.StringIO()
        monkeypatch.setattr(cli, "console", Console(file=buf, width=200, color_system=None))
        monkeypatch.setattr("bristlenose.credentials.get_credential_store_label", lambda: label)
        cli._print_provider_guidance()
        assert (f"stores it securely ({label})" in buf.getvalue()) is secure, label
        assert f"stores it ({label})" in buf.getvalue() or secure, label


@pytest.mark.parametrize(("platform", "shown"), [("win32", False), ("darwin", True), ("linux", True)])
def test_doctor_shows_the_homebrew_row_only_where_homebrew_exists(
    monkeypatch: pytest.MonkeyPatch, platform: str, shown: bool,
) -> None:
    """A Windows doctor printed "Homebrew  not a Homebrew formula install"."""
    import bristlenose.doctor as doctor

    for name in [n for n in dir(doctor) if n.startswith("check_")]:
        monkeypatch.setattr(
            doctor, name,
            lambda *a, _n=name, **k: doctor.CheckResult(status=doctor.CheckStatus.OK, label=_n),
        )
    monkeypatch.setattr(sys, "platform", platform)
    labels = [r.label for r in doctor.run_all(settings=None).results]  # type: ignore[arg-type]
    assert ("check_brew_tap_trust" in labels) is shown


def test_urllib_trust_survives_an_empty_system_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh Windows store lacks Google Trust Services until curl or a browser
    fetches it; api.anthropic.com and api.openai.com chain to it.

    Measured on a new Windows Server 2025 box (5 Oct 2026): doctor called the
    network down and ``configure`` could not validate a key, because urllib read
    the store as it stood. The store is emptied here, the way that box had it.
    """
    import ssl

    from bristlenose.utils.tls import https_context

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", lambda self, purpose=None: None)
    monkeypatch.setattr(ssl.SSLContext, "set_default_verify_paths", lambda self: None)
    assert ssl.create_default_context().get_ca_certs() == [], "the store was not emptied"
    subjects = [
        dict(part[0] for part in cert["subject"]).get("organizationName", "")
        for cert in https_context().get_ca_certs()
    ]
    assert "Google Trust Services LLC" in subjects


def test_every_urlopen_brings_its_own_trust() -> None:
    """Every https ``urlopen`` passes ``context=https_context()``.

    Ollama's two calls are plain http to localhost and need no trust.
    """
    import ast

    offenders = []
    for path in _PKG.rglob("*.py"):
        if path.name == "ollama.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "urlopen"
                and not any(k.arg == "context" for k in node.keywords)
            ):
                offenders.append(f"{path.relative_to(_PKG)}:{node.lineno}")
    assert offenders == [], f"pass context=https_context() to: {offenders}"


def test_a_saved_key_path_reads_whole_on_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`configure` printed "Saved to ~/.config\\bristlenose\\.env" on Windows:
    a `~` cmd.exe cannot expand, glued to backslashes."""
    import bristlenose.cli as cli

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = tmp_path / ".config" / "bristlenose" / ".env"
    monkeypatch.setattr(sys, "platform", "win32")
    assert cli._display_config_path(path) == str(path)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cli._display_config_path(path) == "~/.config/bristlenose/.env"
