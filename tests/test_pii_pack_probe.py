"""The release preflight's PII-pack row, exercised as shell rather than grepped.

The `en_core_web_lg` pack is **self-hosted**. The CLI acquirer's `spacy
download` is PyPI's problem, but the `.dmg` and TestFlight acquirers fetch our
own URL, so nothing else in the release chain would notice a CDN that had gone
stale or an artefact that had been replaced. This is the only thing that looks.

These tests extract the real block out of `check-release-ready.sh` and run it
under bash with a stubbed `curl`, so they fail if the logic changes — not
merely if the wording does. A text-level assertion would pass against a probe
that had been silently inverted.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_PREFLIGHT = _ROOT / "scripts" / "check-release-ready.sh"
_CONF = _ROOT / "scripts" / "project.conf"

_BLOCK_OPENER = 'if [ -n "${PII_PACK_URL:-}" ]'


def _extract_block() -> str:
    """Lift the probe out of the preflight by matching its `if`/`fi` depth."""
    lines = _PREFLIGHT.read_text().splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(_BLOCK_OPENER)]
    assert len(starts) == 1, (
        f"expected exactly one PII-pack probe in {_PREFLIGHT.name}, found "
        f"{len(starts)} — the release preflight is the only thing watching a "
        f"self-hosted artefact"
    )
    start = starts[0]
    depth = 0
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if re.match(r"^if\b", stripped):
            depth += 1
        if stripped == "fi":
            depth -= 1
            if depth == 0:
                return "\n".join(lines[start : i + 1])
    raise AssertionError("probe block never closes — unbalanced if/fi")


def _run(url: str, pin: str, http_code: str, body: str) -> str:
    """Run the real block with ok/warn/bad and curl stubbed. Returns 'LEVEL|evidence'."""
    harness = f"""
set +e
PII_PACK_URL={url!r}
PII_PACK_SHA256={pin!r}
ok()   {{ echo "OK|$2"; }}
warn() {{ echo "WARN|$2"; }}
bad()  {{ echo "BAD|$2"; }}
FAKE_CODE={http_code!r}
FAKE_BODY={body!r}
curl() {{
  for a in "$@"; do [ "$a" = "-w" ] && {{ printf '%s' "$FAKE_CODE"; return 0; }}; done
  printf '%s' "$FAKE_BODY"
}}
{_extract_block()}
"""
    out = subprocess.run(
        ["bash", "-c", harness], capture_output=True, text=True, timeout=30
    )
    return (out.stdout + out.stderr).strip()


def _sha(body: str) -> str:
    out = subprocess.run(
        ["shasum", "-a", "256"], input=body, capture_output=True, text=True
    )
    return out.stdout.split()[0]


class TestTheConfigCarriesTheKnobs:
    def test_both_keys_exist_so_the_probe_can_arm(self) -> None:
        """Empty is fine; absent is not — an absent key can never be filled in."""
        conf = _CONF.read_text()
        for key in ("PII_PACK_URL", "PII_PACK_SHA256"):
            assert re.search(rf"^{key}=", conf, re.M), (
                f"{key} is not in project.conf, so the preflight row can never "
                f"arm — see 'a gate script with no caller is not a gate'"
            )


class TestTheProbeIsTriState:
    """*No data* is a third state, not a failure (REPORT-STYLE.md Part 2)."""

    def test_unset_is_silent_rather_than_a_standing_warning(self) -> None:
        """The pack is genuinely not hosted yet.

        A warning on every unrelated release is how a gate teaches people to
        scroll past it — the failure mode `docs/testing/gaps.md` exists for.
        """
        assert _run("", "", "200", "anything") == ""

    def test_unreachable_is_bad(self) -> None:
        got = _run("https://example.invalid/pack", _sha("x"), "404", "")
        assert got.startswith("BAD|"), got
        assert "404" in got

    def test_reachable_but_unpinned_warns(self) -> None:
        """Its own hazard, not a lesser version of reachable.

        Without a pin a replaced artefact is undetectable, and this one is
        unpacked onto the user's machine and loaded by the detector.
        """
        got = _run("https://example.invalid/pack", "", "200", "the-real-pack")
        assert got.startswith("WARN|"), got

    def test_matching_sha_passes(self) -> None:
        body = "the-real-pack"
        got = _run("https://example.invalid/pack", _sha(body), "200", body)
        assert got.startswith("OK|"), got

    def test_a_swapped_artefact_at_the_same_url_is_bad(self) -> None:
        """The whole reason the row exists — the URL is fine, the bytes are not."""
        got = _run(
            "https://example.invalid/pack", _sha("the-real-pack"), "200", "a-swapped-pack"
        )
        assert got.startswith("BAD|"), got
        assert "MISMATCH" in got


class TestSeveritiesAreNotQuietlyDowngraded:
    @pytest.mark.parametrize("needle", ['bad "PII pack"', 'warn "PII pack"', 'ok "PII pack"'])
    def test_all_three_severities_are_used(self, needle: str) -> None:
        assert needle in _PREFLIGHT.read_text(), (
            f"{needle} is gone — a probe that can only pass or only warn is not "
            f"tri-state, whatever its comment says"
        )
