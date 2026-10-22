"""Guard for ``docs/design-cloud-files.md``: the UI never narrates cloud storage.

Bristlenose reads cloud placeholders with a bound and fails as an ordinary
failure. It shows no wait label, no "In iCloud" state and no provider advice.
That rule was re-proposed five times before it was written down (22 Oct 2026),
so this test catches the sixth at the string, where any such surface has to
start: an English locale value, or a hard-coded Swift literal that escaped the
i18n gate.

Only ``en`` is scanned: the other 20 locales translate it, and
``scripts/check-locales.py`` already pins them to it.

``ALLOWED`` holds the strings the policy page lists as open owner questions
("As built on 22 Oct 2026"). Removing an entry once its string is reworded is
the point; adding one needs that page to say why.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "bristlenose" / "locales" / "en"
SWIFT = ROOT / "desktop" / "Bristlenose" / "Bristlenose"

# Naming a provider is allowed ("in iCloud Drive", "on Dropbox"); a status
# label is not. So the bare name is not a match, but the deleted "In iCloud"
# state label (capitalised, as a label reads) is.
NARRATION = re.compile(
    r"(?-i:\bIn iCloud\b(?! Drive))|Fetching from|Still fetching|still downloading"
    r"|Waiting for (iCloud|the cloud|Google Drive|OneDrive|Dropbox)"
    r"|Optimi[sz]e Mac Storage|Keep Downloaded|(download|open) (it|them) in Finder",
    re.IGNORECASE,
)

# key -> reason. Each is an open question in docs/design-cloud-files.md.
ALLOWED: dict[str, str] = {
    "desktop.chrome.copySourceNotDownloaded": "refusal is pattern A; the Finder advice is open",
    "desktop.discussion.guideNotDownloaded": "refusal is pattern A; the Finder advice is open",
    "common.screens.couldNotRead.cloudDownloading": "says 'still downloading'; only the bound fired",
}

# Swift literals that name a provider, by file. `cloudProviderLabel`'s return
# values feed Settings ▸ General and cloud import: naming is allowed, and these
# two are where the names come from. A new site is a new count here.
SWIFT_LITERAL = re.compile(r'"[^"\n]*(Waiting for iCloud|Fetching from|Still fetching|iCloud Drive)[^"\n]*"')
SWIFT_ALLOWED = {"ProjectIndex.swift": 2}


def _values(node: object, prefix: str):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _values(value, f"{prefix}.{key}")
    elif isinstance(node, str):
        yield prefix, node


def _en_values() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(EN.glob("*.json")):
        out.update(_values(json.loads(path.read_text(encoding="utf-8")), path.stem))
    return out


def test_no_english_string_narrates_cloud_storage() -> None:
    values = _en_values()
    assert len(values) > 1000, "the locale walk found almost nothing; the guard is blind"
    offenders = {
        key: value for key, value in values.items()
        if NARRATION.search(value) and key not in ALLOWED
    }
    assert not offenders, (
        "UI text narrates cloud storage, against docs/design-cloud-files.md: "
        f"{offenders}"
    )


def test_every_allowed_string_still_needs_its_exemption() -> None:
    values = _en_values()
    stale = [key for key in ALLOWED if not NARRATION.search(values.get(key, ""))]
    assert not stale, f"reworded or removed; drop them from ALLOWED: {stale}"


def _swift_literal_counts() -> dict[str, int]:
    files = sorted(SWIFT.rglob("*.swift"))
    assert len(files) > 100, "the Swift walk found almost nothing; the guard is blind"
    counts: dict[str, int] = {}
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("//"):
                continue
            if SWIFT_LITERAL.search(line):
                counts[path.name] = counts.get(path.name, 0) + 1
    return counts


def test_no_swift_literal_narrates_cloud_storage() -> None:
    counts = _swift_literal_counts()
    over = {f: n for f, n in counts.items() if n > SWIFT_ALLOWED.get(f, 0)}
    assert not over, (
        "a Swift literal names a cloud provider or narrates a fetch, against "
        f"docs/design-cloud-files.md: {over} (allowed: {SWIFT_ALLOWED})"
    )


def test_every_swift_allowance_is_still_used() -> None:
    counts = _swift_literal_counts()
    stale = {f: n for f, n in SWIFT_ALLOWED.items() if counts.get(f, 0) < n}
    assert not stale, f"fewer literals than allowed; lower SWIFT_ALLOWED: {stale} vs {counts}"
