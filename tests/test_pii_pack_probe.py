"""The release preflight's PII-pack row, exercised as shell rather than grepped.

The `en_core_web_lg` pack is **self-hosted**. The CLI acquirer's `spacy
download` is PyPI's problem, but the `.dmg` and TestFlight acquirers fetch our
own URL, so nothing else in the release chain would notice a CDN that had gone
stale or an artefact that had been replaced. This is the only thing that looks.

The row does a HEAD and reads a `.sha256` sidecar. It must never pull the body:
the first version did, on every armed preflight, and under `--max-time` a slow
connection produced a partial-file hash that read as a tampered artefact.

These tests extract the real block out of `check-release-ready.sh` and run it
under bash with a stubbed `curl`, so they fail if the logic changes — not
merely if the wording does.
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

_SHA = "a" * 64
_OTHER = "b" * 64


def _extract_block() -> str:
    lines = _PREFLIGHT.read_text().splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(_BLOCK_OPENER)]
    assert len(starts) == 1, f"expected one PII-pack probe, found {len(starts)}"
    depth = 0
    for i in range(starts[0], len(lines)):
        stripped = lines[i].strip()
        if re.match(r"^if\b", stripped):
            depth += 1
        if stripped == "fi":
            depth -= 1
            if depth == 0:
                return "\n".join(lines[starts[0] : i + 1])
    raise AssertionError("probe block never closes")


def _run(url: str, pin: str, head_code: str, served_sha: str, length: str = "425000000") -> str:
    """Run the real block with ok/warn/bad and curl stubbed. Returns 'LEVEL|evidence'.

    The stub answers a HEAD (`-I`) with a status line + Content-Length, answers
    `<url>.sha256` with `served_sha`, and TRIPS on any request for the body —
    which is the regression this test exists to hold shut.
    """
    harness = f"""
set +e
PII_PACK_URL={url!r}
PII_PACK_SHA256={pin!r}
ok()   {{ echo "OK|$2"; }}
warn() {{ echo "WARN|$2"; }}
bad()  {{ echo "BAD|$2"; }}
curl() {{
  local head=0 target=""
  for a in "$@"; do
    case "$a" in -sIL|-I) head=1;; http*) target="$a";; esac
  done
  if [ "$head" = 1 ]; then
    printf 'HTTP/2 {head_code}\\r\\ncontent-length: {length}\\r\\n'
  elif [[ "$target" == *.sha256 ]]; then
    # An empty served_sha models the sidecar being ABSENT: a real 404 with
    # `curl -s` (no -f) prints the error page to stdout, not nothing.
    if [ -n {served_sha!r} ]; then printf '%s  pack.tar.gz\\n' {served_sha!r};
    else printf '<!DOCTYPE html><title>404 Not Found</title>\\n'; fi
  else
    echo "BODY-PULLED|the probe requested the pack body" >&2
    exit 99
  fi
}}
{_extract_block()}
"""
    out = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=30)
    return (out.stdout + out.stderr).strip()


class TestTheConfigCarriesTheKnobs:
    def test_both_keys_exist_so_the_probe_can_arm(self) -> None:
        conf = _CONF.read_text()
        for key in ("PII_PACK_URL", "PII_PACK_SHA256"):
            assert re.search(rf"^{key}=", conf, re.M), f"{key} missing from project.conf"


class TestTheProbeIsTriState:
    def test_unset_is_silent_rather_than_a_standing_warning(self) -> None:
        assert _run("", "", "200", _SHA) == ""

    def test_unreachable_is_bad(self) -> None:
        got = _run("https://example.invalid/pack", _SHA, "404", _SHA)
        assert got.startswith("BAD|") and "404" in got, got

    def test_reachable_but_unpinned_warns(self) -> None:
        got = _run("https://example.invalid/pack", "", "200", _SHA)
        assert got.startswith("WARN|"), got

    def test_matching_sidecar_passes_and_reports_the_size(self) -> None:
        got = _run("https://example.invalid/pack", _SHA, "200", _SHA)
        assert got.startswith("OK|"), got
        assert "425000000" in got

    def test_a_replaced_artefact_with_a_stale_pin_is_bad(self) -> None:
        got = _run("https://example.invalid/pack", _SHA, "200", _OTHER)
        assert got.startswith("BAD|") and "MISMATCH" in got, got

    def test_a_missing_sidecar_is_bad_not_a_download(self) -> None:
        got = _run("https://example.invalid/pack", _SHA, "200", "")
        assert got.startswith("BAD|") and ".sha256" in got, got

    def test_pin_case_is_normalised(self) -> None:
        got = _run("https://example.invalid/pack", _SHA.upper(), "200", _SHA)
        assert got.startswith("OK|"), got


class TestTheBodyIsNeverPulled:
    """The regression that motivated the rewrite, held shut by the stub."""

    @pytest.mark.parametrize("pin,served", [(_SHA, _SHA), (_SHA, _OTHER), ("", _SHA), (_SHA, "")])
    def test_no_state_requests_the_body(self, pin: str, served: str) -> None:
        got = _run("https://example.invalid/pack", pin, "200", served)
        assert "BODY-PULLED" not in got, got
