"""Every Miro failure a researcher reads names a reason, and every reason resolves.

Register item 46. Nine `MiroError` sites raise English sentences; the server
returned them as `detail` and both clients rendered that raw, so a German,
Japanese or Ukrainian researcher read *"No quotes match the current selection"*
inside an otherwise-translated sheet. `api.ts` is explicit that `detail` is
"English prose. Do not display it to a researcher" — and the panel displayed it,
because until now there was nothing else to show.

The fix is not translation, it is a **discriminator**: a client cannot
pattern-match an English sentence, and every attempt to do so breaks the day
somebody rewords it. Same shape as `Cause.reason` and `CloudFetchFailure`, and
deliberately the same *name* the SPA already documents for the job rather than a
parallel sibling that means the same thing.

**Six of the nine deliberately have no reason.** They carry an HTTP status and
Miro's own response text — wire diagnostics that go to a log, not to a
researcher, and are correctly English. This file asserts that split holds:
reasons resolve, and the diagnostics stay bare.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXPORT = REPO / "bristlenose" / "server" / "miro_export.py"
ROUTE = REPO / "bristlenose" / "server" / "routes" / "miro.py"
SWIFT = REPO / "desktop" / "Bristlenose" / "Bristlenose" / "MiroAPI.swift"
PANEL = REPO / "frontend" / "src" / "components" / "MiroExportPanel.tsx"
LOCALES = REPO / "bristlenose" / "locales"


def _reasons() -> set[str]:
    """Every reason the server can actually emit, read from the raise sites."""
    return set(re.findall(r'reason="(\w+)"', EXPORT.read_text(encoding="utf-8")))


def _en_miro() -> dict:
    return json.loads((LOCALES / "en" / "common.json").read_text(encoding="utf-8"))["miro"]


def test_the_server_emits_at_least_the_three_researcher_facing_reasons() -> None:
    """Derived from the source, not a hand-written list — a new one enrols itself."""
    assert _reasons() >= {"no_quotes_selected", "no_board_id", "board_incomplete"}


@pytest.mark.parametrize("client", ["swift", "spa"])
def test_every_reason_has_a_key_in_both_clients(client: str) -> None:
    """A reason no client maps renders English, which is the defect this closes."""
    body = (SWIFT if client == "swift" else PANEL).read_text(encoding="utf-8")
    # Anchor past the TYPE annotation: `[String: String]` carries brackets of
    # its own, and a regex that stops at the first one captures "String: String"
    # and reports every reason missing — a confident false positive, which is
    # the failure mode this whole file is about.
    pattern = (
        r"errorKeys[^=]*=\s*\[(.*?)\n    \]" if client == "swift"
        else r"EXPORT_ERROR_KEYS[^=]*=\s*\{(.*?)\n\};"
    )
    table = re.search(pattern, body, re.S)
    assert table, f"{client}: could not find the reason→key table — did it get renamed?"
    mapped = set(re.findall(r'"?(\w+)"?\s*:', table.group(1)))

    missing = sorted(_reasons() - mapped)
    assert not missing, (
        f"{client} has no key for {missing}. The researcher gets the server's "
        "English `detail` instead — which is exactly what register item 46 is."
    )


def test_every_mapped_key_exists_in_english() -> None:
    """A key that resolves to itself renders a dotted path in the sheet."""
    keys = set(re.findall(r'"common\.miro\.(\w+)"', SWIFT.read_text(encoding="utf-8")))
    keys |= set(re.findall(r'"miro\.(err\w+)"', PANEL.read_text(encoding="utf-8")))
    en = _en_miro()
    missing = sorted(k for k in keys if k not in en)
    assert not missing, f"named by a client, absent from en/common.json: {missing}"


def test_every_locale_carries_the_error_sentences() -> None:
    """`check-locales.py` would catch this too; here it is next to its reason."""
    wanted = {k for k in _en_miro() if k.startswith("err")}
    assert wanted, "no err* keys in en — did the block get renamed?"
    for d in sorted(p for p in LOCALES.iterdir() if p.is_dir()):
        data = json.loads((d / "common.json").read_text(encoding="utf-8")) \
            if (d / "common.json").exists() else None
        if data is None:
            continue  # zh-Hant-HK ships a file only where it overrides something
        missing = sorted(wanted - set(data.get("miro", {})))
        assert not missing, f"{d.name}: {missing}"


def test_the_wire_diagnostics_stay_bare() -> None:
    """The six status-plus-response-text raises must NOT acquire a reason.

    They are correctly English: they name an HTTP status and Miro's own words,
    which is what a bug report needs and what no researcher should be shown. A
    reason on one of them would mean somebody localised a diagnostic — the
    opposite failure to the one this file exists for, and the harder one to
    notice, because it looks like thoroughness.
    """
    client = (REPO / "bristlenose" / "miro_client.py").read_text(encoding="utf-8")
    raises = re.findall(r"raise MiroError\((.*?)\)\s*(?:from|$|\n)", client, re.S)
    assert len(raises) >= 5, f"expected the wire diagnostics, found {len(raises)}"
    tagged = [r for r in raises if "reason=" in r]
    assert not tagged, (
        "a wire diagnostic in miro_client.py grew a reason. Those carry an HTTP "
        "status and Miro's response text; they belong in a log, not in a "
        f"researcher's sheet: {tagged}"
    )


def test_the_route_sends_the_reason() -> None:
    """The discriminator is useless if the route drops it on the way out."""
    body = ROUTE.read_text(encoding="utf-8")
    assert '"reason": exc.reason' in body, (
        "the export route no longer forwards `reason`, so every client falls "
        "back to English `detail` and the rest of this file passes anyway."
    )
