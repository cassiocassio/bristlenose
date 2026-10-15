#!/usr/bin/env python3
"""Live check that the Whisper download sizes the banner quotes are still true.

``_DOWNLOAD_MB`` in ``bristlenose/preflight/whisper.py`` is hardcoded on
purpose: asking the Hub for a size before the banner is a network round-trip on
a path that must not stall (``docs/design-cli-just-works.md``, "Estimating size
before download"). The cost is that a re-uploaded model, or a repo that grows a
second weights file, makes the banner's "~1.6 GB" quietly wrong. Nothing asked
until 15 Oct 2026, while the design doc said a quarterly drift audit would.

This asks the same question the table was built from, the Hub API's file list
(``/api/models/<repo>?blobs=true``), summed in decimal megabytes, because
``snapshot_download`` fetches every file in the repo.

    .venv/bin/python scripts/check-whisper-sizes.py

Exit 0 = every repo within a megabyte of the table. Exit 1 = drift or a repo
gone (the message names the new number to paste). Exit 2 = the Hub could not be
asked. Not a CI gate — it needs the network. Run it at the quarterly dependency
review, beside ``check-providers-live.py``.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TOLERANCE_MB = 1  # the table rounds to whole megabytes


@dataclass
class Drift:
    repo: str
    table_mb: int
    hub_mb: int | None  # None: the repo is gone

    def describe(self) -> str:
        if self.hub_mb is None:
            return f"{self.repo}: not on the Hub any more (table says {self.table_mb} MB)"
        return f"{self.repo}: table {self.table_mb} MB, Hub {self.hub_mb} MB — set it to {self.hub_mb}"


def compare(table: dict[str, int], hub: dict[str, int | None]) -> list[Drift]:
    """Every repo whose Hub size differs from the table by more than rounding."""
    drifts = []
    for repo, table_mb in sorted(table.items()):
        hub_mb = hub.get(repo)
        if hub_mb is None or abs(hub_mb - table_mb) > TOLERANCE_MB:
            drifts.append(Drift(repo, table_mb, hub_mb))
    return drifts


def hub_size_mb(repo: str) -> int | None:
    """The repo's total size in decimal MB, or None when the Hub says it is gone."""
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 404):  # the Hub answers 401 for a repo that does not exist
            return None
        raise
    return round(sum(s.get("size") or 0 for s in data.get("siblings", [])) / 1e6)


def main() -> int:
    from bristlenose.preflight.whisper import _DOWNLOAD_MB

    hub: dict[str, int | None] = {}
    for repo in sorted(_DOWNLOAD_MB):
        try:
            hub[repo] = hub_size_mb(repo)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"could not ask the Hub about {repo}: {exc}", file=sys.stderr)
            return 2
    drifts = compare(_DOWNLOAD_MB, hub)
    for drift in drifts:
        print(drift.describe())
    print(f"{len(_DOWNLOAD_MB) - len(drifts)} of {len(_DOWNLOAD_MB)} repos match the table")
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
