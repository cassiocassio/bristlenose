"""Filesystem helpers — name-based filters, and cloud-materialisation support."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

from bristlenose.utils.text import count_noun

logger = logging.getLogger(__name__)

# BSD/macOS `st_flags` bit meaning "this file has no data extents — the bytes
# live in the cloud and the kernel will fault them in on read." Defined in
# <sys/stat.h> as SF_DATALESS. Not present on Linux, hence the getattr guard
# in `is_dataless` — the CLI is first-class there and st_flags doesn't exist.
SF_DATALESS = 0x40000000

# Outer bound on a materialisation wait. NOT a probe timeout — this exists only
# so a dead provider (client quit, offline, quota full) fails with an honest
# message instead of hanging the run forever. Deliberately generous: a 1.3 GB
# interview on a domestic uplink is minutes, and measured behaviour is that a
# fetch can sit at zero bytes for 90s+ before it starts moving.
MATERIALISE_TIMEOUT_SECONDS = 30 * 60


class CloudFetchTimeoutError(RuntimeError):
    """A dataless file did not materialise within `MATERIALISE_TIMEOUT_SECONDS`.

    Distinct from a probe failure on purpose: this means "the bytes never
    arrived", not "the file is corrupt". The two want opposite remedies from
    the researcher, so they must never share a message.
    """


def is_os_metadata(path: Path) -> bool:
    """True for OS-created metadata files that scanners should skip.

    Most importantly, AppleDouble sidecars (``._<name>``) which macOS Finder
    creates when copying files to filesystems that can't store xattrs/resource
    forks natively (ExFAT, FAT32, SMB shares, some NFS exports). They share the
    same extension as the user file they shadow, so an extension-based scanner
    will happily try to decode `._foo.mp4` as a video or `._s1.txt` as a
    transcript — both fail (binary blob, not the format the extension claims).

    Also filters ``.DS_Store`` for symmetry with Finder.
    """
    name = path.name
    return name.startswith("._") or name == ".DS_Store"


#: The per-run state directory, written inside every output dir.
STATE_DIR_NAME = ".bristlenose"

#: Files Bristlenose writes for itself. Exact names, because these are ours by
#: construction — a researcher's recording is never called `run.pid`.
_ARTEFACT_NAMES = frozenset(
    {
        "pipeline-events.jsonl",
        "llm-calls.jsonl",
        "pii_summary.txt",
        "run.pid",
        "bristlenose.log",
        "bristlenose.db",
        "manifest.json",
    }
)

#: SQLite's WAL companions — `bristlenose.db-wal`, `bristlenose.db-shm`.
_ARTEFACT_PREFIXES = ("bristlenose.db-",)


def is_bristlenose_artefact(path: Path) -> bool:
    """True for files and directories Bristlenose wrote for its own use.

    Sibling of :func:`is_os_metadata`, and the same argument: a scanner walking a
    user's folder must not report *our* detritus as *their* problem. `s01_ingest`
    already declines to descend into ``bristlenose-output``, which covers the
    default layout; this covers the rest — ``--output`` pointing at some other
    directory inside the input folder, or artefacts copied about by hand.

    The justification is the plain one and it is enough: this is noise the
    researcher did not create and cannot act on, and it crowds out the refusals
    that are genuinely theirs — four of nine files in one observed case.

    (An earlier draft of this docstring claimed ``pii_summary.txt`` would be
    *ingested as a transcript* because it is a ``.txt``. That is wrong and worth
    recording so nobody re-derives it: `classify_file` accepts audio, video,
    ``.srt``, ``.vtt`` and ``.docx`` — **not** ``.txt``. A loose
    ``pii_summary.txt`` is declined like any other unknown extension. It is
    still better not to name a re-identification key in a diagnostic the user
    may paste into a support thread, but that is a mild point, not the alarming
    one it was written as.)

    Matches by name rather than by location deliberately — the point is that
    these are ours wherever they turn up.
    """
    name = path.name
    if name == STATE_DIR_NAME:
        return True
    if name in _ARTEFACT_NAMES:
        return True
    return name.startswith(_ARTEFACT_PREFIXES)


def is_dataless(path: Path) -> bool:
    """True if `path` is a cloud placeholder with no bytes on disk.

    Covers every File Provider — iCloud Drive, OneDrive/SharePoint, Dropbox,
    Google Drive, Box — because "dataless" is a filesystem-level concept, not
    an iCloud one. Verified against a real Dropbox placeholder on 29 Jul 2026.

    Always False on Linux (no `st_flags`), which is correct: cloud clients
    there don't present dataless placeholders to POSIX.
    """
    try:
        st = os.stat(path)
    except OSError:
        return False
    return bool(getattr(st, "st_flags", 0) & SF_DATALESS)


def cloud_provider_for(path: Path) -> str | None:
    """Human-readable provider name for a cloud-backed path, else None.

    Structural rather than an allowlist: everything under
    `~/Library/CloudStorage/` *is* File Provider storage by definition, so any
    provider — including ones added later — resolves without a code change.
    The folder is named `<Provider>-<account>` (`GoogleDrive-a@b.com`,
    `OneDrive-Acme Corp`, `Box-Box`), and we want the family for a status line,
    not the account.
    """
    parts = path.resolve().parts if path.is_absolute() else Path(path).parts
    for i, part in enumerate(parts):
        if part == "Mobile Documents":
            return "iCloud Drive"
        if part == "CloudStorage" and i + 1 < len(parts):
            stem = parts[i + 1].split("-", 1)[0]
            return {
                "GoogleDrive": "Google Drive",
                "OneDrive": "OneDrive",
                "Dropbox": "Dropbox",
                "Box": "Box",
                "ProtonDrive": "Proton Drive",
            }.get(stem, stem or None)
    return None


def ensure_materialised(
    path: Path,
    timeout: float = MATERIALISE_TIMEOUT_SECONDS,
    on_wait: Callable[[Path, str | None], None] | None = None,
) -> bool:
    """Fault a cloud placeholder into local storage before anything reads it.

    Returns True if a fetch was actually waited on, False if the file was
    already resident (the overwhelmingly common case — one `stat`, no I/O).

    **The blocking read IS the trigger.** There is no Python API to request
    materialisation; opening the file and reading a byte is what makes the
    File Provider fetch it. So this doesn't avoid the blocking read — it moves
    it somewhere deliberate, off the 30s probe budget that was never meant to
    cover a download. See `docs/design-project-storage.md` §3 for the
    reproduction that motivated this.

    The read runs on a thread so the caller can bound it. No progress is
    reported because none is observable: providers stage the download and swap
    the file in atomically, so `st_blocks` reads 0 until it reads 100%.

    Raises `CloudFetchTimeoutError` if the bytes never arrive — deliberately NOT a
    probe error, because "still downloading" and "corrupt file" want opposite
    remedies from the researcher.
    """
    if not is_dataless(path):
        return False

    provider = cloud_provider_for(path)
    logger.info(
        "cloud_fetch_start | file=%s | provider=%s | size_bytes=%s",
        path.name, provider or "unknown", path.stat().st_size,
    )
    if on_wait is not None:
        on_wait(path, provider)

    def _touch() -> None:
        with open(path, "rb") as fh:
            fh.read(1)

    worker = threading.Thread(target=_touch, daemon=True, name="cloud-fetch")
    worker.start()
    worker.join(timeout)

    if worker.is_alive():
        # Daemon thread is abandoned deliberately — it's parked in a kernel
        # read we can't interrupt, and the process will exit around it.
        minutes = int(timeout // 60)
        waited = (
            count_noun(minutes, "minute") if minutes else count_noun(int(timeout), "second")
        )
        raise CloudFetchTimeoutError(
            f"{path.name} was still being fetched from "
            f"{provider or 'the cloud'} after {waited}"
        )

    logger.info("cloud_fetch_done | file=%s | provider=%s", path.name, provider or "unknown")
    return True
