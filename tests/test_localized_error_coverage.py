"""Coverage gate — every `LocalizedError` in the app target is classified.

`LocalizedError.errorDescription` is the highest-risk site in this codebase for
a sentence filed as data. On 21 Sep 2026 **all six** conformers held hardcoded
English, 6 for 6, no false positives — and every one of them renders: the OAuth
three reach the cloud-import window through `CloudImportStore`'s `.failed`
phase, `CopyError` becomes a toast in the main window, `MiroAPI.APIError` shows
in the Miro sheet, `CloudDownloadError` drew the import row.

The protocol's name is the promise. This gate does not force it to be kept — it
forces the answer to be *written down*, which is what nothing did. A new
conformer is unclassified and fails, so English-by-omission stops being
possible; making it English on purpose is a reviewed edit to `ENGLISH_PENDING`
below, with a reason, exactly as adding a route to `SERVER_ONLY_PATH_TEMPLATES`
is in `test_serve_export_coverage.py` — the pattern this copies.

**Why a declared set and not a scan for string literals.** A scan cannot tell a
sentence from a diagnostic, and `errorDescription` is legitimately English in
one case already: `CloudDownloadError` keeps its English description *for the
log* and exposes `fetchFailure` for the row. One type, two readers, two answers.
A gate that could not express that would have to be wrong about it.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "desktop" / "Bristlenose" / "Bristlenose"

# Conformers whose user-facing text reaches the UI through a discriminator the
# view resolves. English may still appear in `errorDescription` for the log.
LOCALISED: dict[str, str] = {
    "APIError": (
        "MiroAPI's. localeKey is set only when the sentence is ours; nil means "
        "`message` is the SERVER's own detail (an invalid-token reason, a "
        "partial-board recovery URL on a 502), which is already the most "
        "specific thing anyone has and is passed through untranslated. "
        "MiroSheet.text(for:) resolves it and falls back to the sheet's own "
        "connectError / exportError as before. 21 Sep 2026."
    ),
    "CopyError": (
        "errorDescription stays English for the log and for `.underlying`, whose "
        "system error macOS has already localised — translating that again would "
        "replace Apple's wording with ours. `localeKey` carries the three cases "
        "we author; both drop sites resolve it through ContentView.copyToastText. "
        "insufficientDiskSpace reuses chrome.copyDiskSpaceTitle, which already "
        "existed in 21 locales for the alert on the same condition. 21 Sep 2026."
    ),
    "CloudDownloadError": (
        "errorDescription stays English for the log (LocalizedError reaches bug "
        "reports, where a run analysed in German must not read as German "
        "forever); `fetchFailure` carries the verdict as a CloudFetchFailure "
        "case and CloudImportOutlineView resolves it. 21 Sep 2026."
    ),
}

# English on purpose, for a reason that is a property of the surface rather than
# a stage of the project (docs/design-i18n.md §"Which surfaces are targets").
# These are not debt and do not count against the ratchet.
ENGLISH_BY_DECISION: dict[str, str] = {
    "SidecarResolveError": (
        "Developer surface. Every case is about _BRISTLENOSE_DEV_* env vars or a "
        "broken bundle — 'Both dev env vars are set, pick one', 'Dev sidecar path "
        "is not a usable executable'. A researcher cannot reach these without "
        "setting a dev env var first. Found by this gate on 21 Sep 2026, having "
        "been missed by a hand audit that grepped ': LocalizedError' and so "
        "skipped ': Error, Equatable, LocalizedError'."
    ),
}

# Conformers still rendering English, each with what it costs and where it is
# tracked. This set may only SHRINK — moving an entry to LOCALISED is the work;
# adding one is a decision that needs a reason a reader can weigh.
ENGLISH_PENDING: dict[str, str] = {
    "ZoomOAuthError": "~10 sign-in sentences → cloud-import window via CloudImportStore:413.",
    "MicrosoftOAuthError": "~9 sentences, incl. the two longest on the surface (admin approval, Conditional Access).",
    "GoogleOAuthError": "~6 sentences → same window, same path.",
}

# The ratchet. Lower it when an entry moves; raising it needs a commit that says
# why, per docs/testing/soft-gates.json's policy.
MAX_ENGLISH_PENDING = 3


def _conformers() -> dict[str, Path]:
    found: dict[str, Path] = {}
    pattern = re.compile(
        r"^\s*(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
        r"(?:final\s+)?(?:enum|struct|class)\s+(\w+)\s*:[^{\n]*\bLocalizedError\b",
        re.MULTILINE,
    )
    for swift in sorted(_APP.rglob("*.swift")):
        for m in pattern.finditer(swift.read_text(encoding="utf-8")):
            found[m.group(1)] = swift
    return found


def test_every_localizederror_is_classified() -> None:
    found = set(_conformers())
    classified = set(LOCALISED) | set(ENGLISH_PENDING) | set(ENGLISH_BY_DECISION)
    unclassified = sorted(found - classified)
    assert not unclassified, (
        f"{unclassified} conform to LocalizedError and are in neither set. "
        f"errorDescription renders — decide which it is and say why. If it is "
        f"localised, carry a discriminator the view resolves (CloudDownloadError "
        f"is the worked example); if it is English, add it to ENGLISH_PENDING "
        f"with what that costs and raise MAX_ENGLISH_PENDING deliberately."
    )


def test_no_stale_classifications() -> None:
    """A classification naming a type that no longer exists is a stale claim."""
    found = set(_conformers())
    stale = sorted(
        (set(LOCALISED) | set(ENGLISH_PENDING) | set(ENGLISH_BY_DECISION)) - found
    )
    assert not stale, (
        f"{stale} are classified here but no longer conform to LocalizedError. "
        f"If the type was deleted, delete its row; if it was renamed, rename it."
    )


def test_sets_are_disjoint() -> None:
    sets = {
        "LOCALISED": set(LOCALISED),
        "ENGLISH_PENDING": set(ENGLISH_PENDING),
        "ENGLISH_BY_DECISION": set(ENGLISH_BY_DECISION),
    }
    for a, b in (("LOCALISED", "ENGLISH_PENDING"),
                 ("LOCALISED", "ENGLISH_BY_DECISION"),
                 ("ENGLISH_PENDING", "ENGLISH_BY_DECISION")):
        overlap = sorted(sets[a] & sets[b])
        assert not overlap, f"{overlap} classified as both {a} and {b}"


def test_english_pending_does_not_grow() -> None:
    assert len(ENGLISH_PENDING) <= MAX_ENGLISH_PENDING, (
        f"{len(ENGLISH_PENDING)} conformers render English, ceiling is "
        f"{MAX_ENGLISH_PENDING}. A ceiling that rises quietly is how 238 mypy "
        f"errors happened — raise it in a commit that says why."
    )


def test_every_pending_entry_says_what_it_costs() -> None:
    rows = {**ENGLISH_PENDING, **ENGLISH_BY_DECISION}
    thin = sorted(k for k, v in rows.items() if len(v) < 30)
    assert not thin, (
        f"{thin} have no reason worth reading. 'Deliberate' is only as good as "
        f"the fact it rests on, and nothing re-checks that fact once written — "
        f"name the surface and the cost."
    )
