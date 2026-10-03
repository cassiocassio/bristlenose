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


def guide_folder(project_dir: Path) -> Path:
    return project_dir / GUIDE_FOLDER


def is_guide_folder(path: Path) -> bool:
    """True for the reserved folder itself — ingest's skip test."""
    return path.name == GUIDE_FOLDER


def _candidates(folder: Path) -> list[Path]:
    out = []
    for p in folder.iterdir():
        if p.name.startswith(".") or p.name.startswith("~$"):  # dotfiles, Word lock files
            continue
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in GUIDE_EXTENSIONS:
            continue
        out.append(p)
    return out


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        import docx  # python-docx: lazy, as every heavy import here

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


def find_guide(project_dir: Path) -> Guide | None:
    """The guide in the reserved folder, or None. One guide: if several files are
    there, the most recently modified one is read and the rest are reported."""
    folder = guide_folder(project_dir)
    if not folder.is_dir():
        return None
    if folder.is_symlink():
        logger.warning("discussion guide folder is a symlink — refused: %s", folder.name)
        return None
    files = sorted(_candidates(folder), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    path, rest = files[0], files[1:]
    if path.stat().st_size > MAX_GUIDE_BYTES:
        logger.warning("discussion guide is over %d bytes — refused: %s", MAX_GUIDE_BYTES, path.name)
        return None
    raw = path.read_bytes()
    text = _read_text(path).strip()
    if not text:
        # Present but unreadable is a failure the stage records — never "no guide" (§9.A).
        return Guide(path, "", hashlib.sha256(raw).hexdigest(), [p.name for p in rest])
    return Guide(path, text, hashlib.sha256(raw).hexdigest(), [p.name for p in rest])
