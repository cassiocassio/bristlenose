"""Where the researcher's discussion guide lives, and how it is read.

Decision 0.3 (plan): a reserved subfolder beside the recordings — visible in
Finder and replaceable by hand, it survives Re-analyse (which stashes the output
folder, not the input), and ingest skips it. Decision 0.2: zero or one guide.
The folder name is PROVISIONAL (3 Oct 2026) and lives here only.

Hardened per the security review (§9.C/§9.E): a symlinked folder or file is
refused, only known extensions are read, the size is capped, and the guide's
text never passes through PII redaction — say so in the transparency copy.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

GUIDE_FOLDER = "Discussion guide"
GUIDE_EXTENSIONS = (".docx", ".md", ".txt")
MAX_GUIDE_BYTES = 2 * 1024 * 1024  # a guide is a few pages; anything larger is not one
NO_GUIDE_SHA = "none"  # the cache-key sentinel: present from the first release (§1.6)


@dataclass
class Guide:
    path: Path
    text: str
    sha: str
    ignored: list[str]  # other files in the folder, not read (zero or one guide)
    # Why a guide that is THERE was not used. Never "no guide" (§9.A): the
    # researcher put a file in the folder and the lens must say it went unread.
    # "" | "unreadable" | "too_large" | "symlink" | "unsupported_format" |
    # "folder_unreadable"
    problem: str = ""


def guide_folder(project_dir: Path) -> Path:
    return project_dir / GUIDE_FOLDER


def is_guide_folder(path: Path) -> bool:
    """True for the reserved folder itself — ingest's skip test. Case-blind,
    because the Mac's filesystem is: "Discussion Guide" is the same folder to
    ``find_guide``, and must not be ingested as a session."""
    return path.name.casefold() == GUIDE_FOLDER.casefold()


def _meta_sha(path: Path) -> str:
    """A cache key for a file that cannot be read: replacing it changes this."""
    try:
        st = path.lstat()
        key = f"{path.name}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        key = path.name
    return hashlib.sha256(key.encode()).hexdigest()


def _visible(folder: Path) -> list[Path]:
    # dotfiles and Word lock files are tool state, never the researcher's guide
    return [p for p in folder.iterdir() if not p.name.startswith((".", "~$"))]


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        import docx  # python-docx: lazy, as every heavy import here

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


def _locate(project_dir: Path) -> Path | None:
    try:
        return next((p for p in project_dir.iterdir() if is_guide_folder(p)), None)
    except OSError:
        return None


def guide_home(*candidates: Path) -> Path:
    """The first candidate that holds a guide folder, else the first candidate.

    For callers that are handed something other than the project folder —
    `bristlenose analyze` gets a transcripts folder, and its output lands
    either in the project folder or in `bristlenose-output/` inside it."""
    for c in candidates:
        if _locate(c) is not None:
            return c
    return candidates[0]


def find_guide(project_dir: Path) -> Guide | None:
    """The guide in the reserved folder, or None when there is no guide.

    Never raises: the stage is optional and a researcher's file must not end a
    run. A file that is there but cannot be used comes back with ``problem``
    set and ``text`` empty. One guide: if several files are there, the most
    recently modified one is read and the rest are reported."""
    folder = _locate(project_dir)
    if folder is None:
        return None
    try:
        return _find_in(folder)
    except OSError:  # a file vanished or locked between listing and reading
        return Guide(folder, "", _meta_sha(folder), [], "folder_unreadable")


def _find_in(folder: Path) -> Guide | None:
    if folder.is_symlink():
        logger.warning("discussion guide folder is a symlink — refused")
        return Guide(folder, "", _meta_sha(folder), [], "symlink")
    if not folder.is_dir():
        return None
    try:
        visible = _visible(folder)
        files = [p for p in visible if p.is_file()]
    except OSError:
        return Guide(folder, "", _meta_sha(folder), [], "folder_unreadable")
    usable = [p for p in files
              if not p.is_symlink() and p.suffix.lower() in GUIDE_EXTENSIONS]
    if not usable:
        if not files:
            return None  # an empty folder is no guide
        files.sort(key=lambda p: p.lstat().st_mtime, reverse=True)
        refused = "symlink" if any(p.is_symlink() for p in files) else "unsupported_format"
        return Guide(files[0], "", _meta_sha(files[0]), [p.name for p in files[1:]], refused)
    usable.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    path, rest = usable[0], [p.name for p in usable[1:]]
    if path.stat().st_size > MAX_GUIDE_BYTES:
        logger.warning("discussion guide is over %d bytes — refused", MAX_GUIDE_BYTES)
        return Guide(path, "", _meta_sha(path), rest, "too_large")
    try:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        text = _read_text(path).strip()
    except Exception as exc:  # noqa: BLE001 — a corrupt or locked document is the researcher's file, not our fault
        logger.warning("discussion guide could not be read: %s", type(exc).__name__)
        return Guide(path, "", _meta_sha(path), rest, "unreadable")
    if not text:
        return Guide(path, "", sha, rest, "unreadable")
    return Guide(path, text, sha, rest)
