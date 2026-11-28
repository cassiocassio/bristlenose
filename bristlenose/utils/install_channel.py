"""Which way this copy of Bristlenose was installed, and how to add to it.

An install hint has to name a command that works *here*: a pipx user told to
``pip install`` adds the package to some other Python and nothing changes.
pipx and uv keep each tool in its own environment, recognised by directory on
every platform; Homebrew keeps it under ``Cellar``.

And it must not take anything away. ``pipx install --force`` and ``uv tool
install --force`` rebuild the environment from what the command names, so a
hint that names one extra drops the other (a voice hint would remove any-llm,
and the other way round). Every hint names the extras already installed too.

Shared by every "this optional part isn't installed" hint (the voice pass,
any-llm).
"""

from __future__ import annotations

import importlib.util
import sys
from itertools import pairwise
from pathlib import Path


def install_channel() -> str:
    """``"pipx"``, ``"uv"``, ``"brew"`` or ``"pip"``, from this Python's prefix."""
    prefix = Path(sys.prefix)
    # Each tool's own marker in the environment it built: exact, and right
    # wherever UV_TOOL_DIR or PIPX_HOME has moved it (the paths below aren't).
    if (prefix / "uv-receipt.toml").is_file():
        return "uv"
    if (prefix / "pipx_metadata.json").is_file():
        return "pipx"
    # Backslashes folded so a Windows prefix splits the same on any OS (tests).
    parts = Path(sys.prefix.replace("\\", "/")).parts
    if "pipx" in parts:
        return "pipx"
    # uv tool venvs: ~/.local/share/uv/tools/<name>, or under %APPDATA% on Windows.
    if any(a == "uv" and b == "tools" for a, b in pairwise(parts)):
        return "uv"
    if "Cellar" in parts:
        return "brew"
    return "pip"


def installed_extras() -> list[str]:
    """The optional extras present in this install, by what each one imports."""
    present = []
    if _importable("kaldi_native_fbank"):
        present.append("voice")
    if _importable("any_llm"):
        present.append("any-llm")
    if _importable("mlx_whisper"):
        present.append("apple")
    if _importable("mcp"):
        present.append("mcp")
    return present


def pip_available() -> bool:
    """Whether this Python can run ``-m pip``.

    uv builds its environments without pip, so a ``uv tool install`` has none;
    pipx's do, through pipx's shared libraries. Anything that would shell out to
    ``python -m pip`` (``spacy download`` among them) asks this first.
    """
    return _importable("pip")


def _importable(name: str) -> bool:
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _spec(extra: str) -> str:
    extras = [extra, *(e for e in installed_extras() if e != extra)]
    return f"bristlenose[{','.join(extras)}]"


def uv_python_flag() -> str:
    """``--python X.Y``, the Python this tool runs on, for every uv rebuild we suggest.

    ``uv tool install --force`` picks an interpreter again unless told: on an
    Intel Mac a working 3.12 install was rebuilt on 3.14, which has no
    onnxruntime wheel there, and the rebuild failed (28 Nov 2026). Naming the
    running Python keeps whatever already works.
    """
    return f"--python {sys.version_info[0]}.{sys.version_info[1]}"


def add_extra_command(extra: str) -> str:
    """The command that adds ``bristlenose[extra]`` to this install, keeping the rest."""
    from bristlenose import __version__

    channel = install_channel()
    spec = _spec(extra)
    if channel == "pipx":
        return f'pipx install --force "{spec}"'
    if channel == "uv":
        return f'uv tool install --force "{spec}" {uv_python_flag()}'
    if channel == "brew":
        # The formula's own pip, pinned to the installed version: the formula
        # itself only installs what its post_install names.
        return f'$(brew --prefix bristlenose)/libexec/bin/pip install "{spec}=={__version__}"'
    return f'pip install "{spec}"'


def inject_command(requirement: str) -> str:
    """The command that adds one more package (``any-llm-sdk[cohere]==1.44.0``) here."""
    channel = install_channel()
    if channel == "pipx":
        return f'pipx inject bristlenose "{requirement}"'
    if channel == "uv":
        return (
            f'uv tool install --force "{_spec("any-llm")}" --with "{requirement}" '
            f"{uv_python_flag()}"
        )
    if channel == "brew":
        return f'$(brew --prefix bristlenose)/libexec/bin/pip install "{requirement}"'
    return f'pip install "{requirement}"'
