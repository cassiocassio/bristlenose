"""Which way this copy of Bristlenose was installed, and how to add to it.

An install hint has to name a command that works *here*: a pipx user told to
``pip install`` adds the package to some other Python and nothing changes.
pipx and uv keep each tool in its own environment, recognised by directory on
every platform; Homebrew keeps it under ``Cellar``.

Shared by every "this optional part isn't installed" hint (the voice pass,
any-llm).
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path


def install_channel() -> str:
    """``"pipx"``, ``"uv"``, ``"brew"`` or ``"pip"``, from this Python's prefix."""
    parts = Path(sys.prefix).parts
    if "pipx" in parts:
        return "pipx"
    # uv tool venvs: ~/.local/share/uv/tools/<name>, or under %APPDATA% on Windows.
    if any(a == "uv" and b == "tools" for a, b in pairwise(parts)):
        return "uv"
    if "Cellar" in parts:
        return "brew"
    return "pip"


def add_extra_command(extra: str) -> str:
    """The command that adds ``bristlenose[extra]`` to this install."""
    channel = install_channel()
    if channel == "pipx":
        return f'pipx install --force "bristlenose[{extra}]"'
    if channel == "uv":
        return f'uv tool install --force "bristlenose[{extra}]"'
    if channel == "brew":
        return "brew reinstall bristlenose"
    return f'pip install "bristlenose[{extra}]"'


def inject_command(requirement: str) -> str:
    """The command that adds one more package (``any-llm-sdk[cohere]``) here."""
    channel = install_channel()
    if channel == "pipx":
        return f'pipx inject bristlenose "{requirement}"'
    if channel == "uv":
        return f'uv tool install --force "bristlenose" --with "{requirement}"'
    if channel == "brew":
        return f'$(brew --prefix bristlenose)/libexec/bin/pip install "{requirement}"'
    return f'pip install "{requirement}"'
