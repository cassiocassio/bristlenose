"""Static promises of the Windows one-line installer, scripts/windows/install.ps1.

The script itself runs end to end on windows-latest (install-test.yml,
`windows-install-ps1`); these checks run on every OS, because each one is a
property a reader can break without a Windows machine to notice.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows" / "install.ps1"


def _code_lines() -> list[str]:
    """Script lines with comments removed (no block comments are used)."""
    out = []
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return out


def test_script_is_plain_ascii() -> None:
    # PowerShell 5.1's `irm` decodes a response with no charset as Latin-1, so
    # any non-ASCII byte arrives garbled in the user's terminal.
    data = SCRIPT.read_bytes()
    bad = [i for i, b in enumerate(data) if b > 127]
    assert not bad, f"non-ASCII byte at offset {bad[0]}"


def test_exit_only_when_run_as_a_file() -> None:
    # Under `irm | iex` the script runs in the user's own session, where `exit`
    # closes their terminal mid-message. The one exit is guarded.
    def statements(line: str) -> str:
        line = re.sub(r"'[^']*'|\"[^\"]*\"", "''", line)  # drop string contents
        return line.split("#", 1)[0]

    exits = [
        ln.strip()
        for ln in _code_lines()
        if re.search(r"(?<![\w-])exit(?![\w-])", statements(ln), re.I)
    ]
    assert exits == ["if ($PSCommandPath) { exit 1 }"], exits


def test_never_asks_for_admin_or_changes_policy() -> None:
    code = "\n".join(_code_lines())
    assert "RunAs" not in code
    assert "Set-ExecutionPolicy" not in code
    assert "Start-Process" not in code


def test_never_touches_a_provider_api_host() -> None:
    # A Windows-native fetch from one of these hosts installs its root
    # certificate as a side effect, which would hide the TLS fix in doctor
    # (docs/design-windows-port.md, item 9). The installer has no reason to.
    text = SCRIPT.read_text(encoding="utf-8")
    for host in ("api.anthropic.com", "api.openai.com", "generativelanguage.googleapis.com"):
        assert host not in text


def test_winget_always_names_the_winget_source() -> None:
    # Plain `winget install FFmpeg` fails on the msstore source; the exact id on
    # the winget source works (measured on Server 2025).
    calls = [ln for ln in _code_lines() if re.search(r"&\s*winget\s+install\b", ln)]
    assert calls, "no winget install call found"
    for call in calls:
        assert "--source winget" in call and " -e " in call, call


def test_fallback_ffmpeg_is_pinned_and_hashed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    url = re.search(r"\$FfmpegZipUrl = '([^']+)'", text)
    sha = re.search(r"\$FfmpegZipSha256 = '([^']+)'", text)
    assert url and sha
    m = re.fullmatch(
        r"https://github\.com/GyanD/codexffmpeg/releases/download/"
        r"(\d+(?:\.\d+)*)/ffmpeg-(\d+(?:\.\d+)*)-essentials_build\.zip",
        url.group(1),
    )
    assert m, f"not a pinned release asset: {url.group(1)}"
    assert m.group(1) == m.group(2), "tag and filename versions differ"
    assert re.fullmatch(r"[0-9a-f]{64}", sha.group(1)), "SHA-256 must be 64 lowercase hex"
    assert "Get-FileHash" in text


def test_python_version_matches_install_guide() -> None:
    # The manual route in INSTALL.md and the one-liner must install the same
    # Python, or the voice extra works on one route and not the other.
    text = SCRIPT.read_text(encoding="utf-8")
    script_py = re.search(r"\$PythonVersion = '([\d.]+)'", text)
    assert script_py
    guide = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    guide_py = re.search(r"uv tool install --python ([\d.]+) bristlenose", guide)
    assert guide_py, "INSTALL.md no longer gives the uv command"
    assert script_py.group(1) == guide_py.group(1)


def test_uv_comes_from_astrals_installer() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "$UvInstallerUrl = 'https://astral.sh/uv/install.ps1'" in text


def test_a_failure_after_install_does_not_say_not_installed() -> None:
    # Once uv has put Bristlenose in place, a later failure (PATH, doctor)
    # reads "Bristlenose is installed, but <message>": the messages after that
    # point are the second half of the sentence, and "not installed" is only
    # said before it. A redirected 0.33.0 doctor crash once printed "not
    # installed" over a working install (found on Server 2025, 5 Oct 2026).
    text = SCRIPT.read_text(encoding="utf-8")
    mark = text.index("$installed = $true")
    assert text.index("& uv tool install --python") < mark < text.index("uv tool dir --bin")
    after = text[mark : text.index("} catch {", mark)]
    messages = re.findall(r"Exit-Install\s+\(?\s*[\"'](.)", after)
    assert messages, "no Exit-Install after the install step"
    assert all(first.islower() for first in messages), messages
    catch = text[text.index("} catch {", mark) :]
    assert catch.index("if ($installed)") < catch.index("Bristlenose was not installed.")
