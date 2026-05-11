"""ffmpeg preflight — detect, offer brew auto-install on macOS, print install table elsewhere.

Why this exists: pip-installed Bristlenose can't install system binaries.
A user who installs via `pip install bristlenose` on a fresh Linux box (or a
fresh Mac without brew-installed ffmpeg) currently hits `FileNotFoundError`
deep inside stage 2 (audio extraction) after ingest has already run. This
preflight surfaces the missing binary up-front with a fix instruction.

Channels already handled elsewhere:
- **Homebrew formula**: declares ``depends_on "ffmpeg"`` — handled.
- **Snap**: bundles ffmpeg inside the snap — handled.
- **Desktop**: ships ffmpeg in ``.app/Contents/Resources/`` (covered by
  ``bristlenose.utils.bundled_binary`` PATH-prepend, so ``shutil.which`` finds it).

This preflight only fires when ``shutil.which("ffmpeg")`` returns None,
which means none of the above provided it — i.e., a pip install on a system
where the user hasn't installed ffmpeg themselves.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from bristlenose.i18n import t
from bristlenose.preflight import PreflightAbortedError
from bristlenose.ui_kinds import MessageKind, cli_prefix

if TYPE_CHECKING:
    from rich.console import Console
    from rich.status import Status

logger = logging.getLogger(__name__)

# Back-compat alias — see preflight/whisper.py for the unification rationale.
FfmpegPreflightAbortedError = PreflightAbortedError


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _detect_distro() -> str:
    """Return a coarse distro label: ``macos`` / ``ubuntu`` / ``fedora`` / ``arch`` / ``other``."""
    if sys.platform == "darwin":
        return "macos"
    try:
        release = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return "other"
    fields = dict(
        line.split("=", 1)
        for line in release.splitlines()
        if "=" in line and not line.startswith("#")
    )
    distro_id = fields.get("ID", "").strip().strip('"').lower()
    like = fields.get("ID_LIKE", "").strip().strip('"').lower()
    if distro_id in {"ubuntu", "debian"} or "debian" in like:
        return "ubuntu"
    if distro_id in {"fedora", "rhel", "centos"} or "fedora" in like or "rhel" in like:
        return "fedora"
    if distro_id == "arch" or "arch" in like:
        return "arch"
    return "other"


def _brew_writable_prefix() -> str | None:
    """Return the writable ``brew --prefix`` path, or None if brew isn't usable.

    macOS only. ``None`` means we cannot offer the auto-install path — either
    brew isn't on PATH, or its prefix isn't writable by this process (e.g. a
    multi-user setup or an Apple Silicon machine where ``/opt/homebrew`` is
    root-owned).
    """
    if sys.platform != "darwin":
        return None
    if shutil.which("brew") is None:
        return None
    try:
        result = subprocess.run(
            ["brew", "--prefix"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    prefix = result.stdout.strip()
    if not prefix or not os.access(prefix, os.W_OK):
        return None
    return prefix


def _install_table(distro: str) -> str:
    """Return the multi-line install table with the matching distro row first.

    Padding is computed at print time (not baked into the locale strings) so
    label-width differences across translations (e.g. wider Korean glyphs,
    French "Ubuntu / Debian :" with the extra space) don't misalign the table.
    """
    rows = [
        ("macos", t("preflight.ffmpeg.label_macos"), t("preflight.ffmpeg.cmd_macos")),
        ("ubuntu", t("preflight.ffmpeg.label_ubuntu"), t("preflight.ffmpeg.cmd_ubuntu")),
        ("fedora", t("preflight.ffmpeg.label_fedora"), t("preflight.ffmpeg.cmd_fedora")),
        ("arch", t("preflight.ffmpeg.label_arch"), t("preflight.ffmpeg.cmd_arch")),
        ("other", t("preflight.ffmpeg.label_other"), t("preflight.ffmpeg.cmd_other")),
    ]
    # Put the matching row first; preserve relative order for the rest.
    rows.sort(key=lambda r: 0 if r[0] == distro else 1)
    width = max(len(label) for _, label, _ in rows)
    return "\n".join(
        f"    {label:<{width}}  {cmd}" for _, label, cmd in rows
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _print_missing_banner(console: Console, distro: str) -> None:

    console.print()
    console.print("  [bold]" + t("preflight.ffmpeg.banner_missing") + "[/bold]")
    console.print()
    console.print(_install_table(distro))
    console.print()


def _confirm_brew_install(console: Console) -> bool:
    """Ask the user whether to shell out to ``brew install ffmpeg``.

    Returns False (no auto-install) on non-TTY runs so scripts and CI don't
    block on the prompt.
    """
    if not sys.stdin.isatty():
        return False
    from rich.prompt import Confirm


    # Default to False so a hurried Enter doesn't trigger `brew install` —
    # the procurement story is "we never install system software without an
    # explicit yes." One extra keystroke for the happy path; cleaner defence.
    return Confirm.ask(
        "  " + t("preflight.ffmpeg.prompt_brew_install"), default=False,
    )


def _run_brew_install(
    console: Console, status: Status | None
) -> None:
    """Shell out to ``brew install ffmpeg``, letting brew print natively (Option B)."""
    if status is not None:
        status.stop()
    t0 = time.perf_counter()
    try:
        subprocess.run(["brew", "install", "ffmpeg"], check=True)
    finally:
        if status is not None:
            status.start()
    elapsed = time.perf_counter() - t0

    console.print(
        f"  {cli_prefix(MessageKind.SUCCESS)} "
        + t("preflight.ffmpeg.installed")
        + f" [{int(elapsed)}s]"
    )
    console.print()


def preflight_ffmpeg(
    *,
    console: Console,
    status: Status | None,
    allow_install: bool,
) -> None:
    """Run the ffmpeg preflight.

    Behaviour:
    - **Present**: silent, return immediately.
    - **Missing on macOS + brew available + writable prefix + ``allow_install``**:
      print the install table, prompt ``[Y/n]``, on Y shell out to brew, on N
      raise.
    - **Missing elsewhere (or auto-install declined / not offered)**: print
      the install table and raise :class:`FfmpegPreflightAbortedError`.

    Args:
        allow_install: Pass False when ``--no-fetch`` is set, or for the
            ``doctor`` command where we just report status without offering
            to mutate the system.
    """
    if shutil.which("ffmpeg"):
        return

    distro = _detect_distro()
    _print_missing_banner(console, distro)

    if (
        allow_install
        and distro == "macos"
        and _brew_writable_prefix() is not None
        and _confirm_brew_install(console)
    ):
        _run_brew_install(console, status)
        # Confirm post-install — brew may have failed silently (rare).
        if shutil.which("ffmpeg"):
            return
        # Fall through to the abort path with the install table still on screen.


    raise FfmpegPreflightAbortedError(t("preflight.ffmpeg.aborted"))


