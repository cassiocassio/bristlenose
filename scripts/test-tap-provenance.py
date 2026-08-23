#!/usr/bin/env python3
"""Test the Homebrew tap's PEP 740 provenance gate.

The tap formula's sha256 is fetched from PyPI alongside the sdist URL — that is
integrity in transit, not provenance. Anyone reaching PyPI got Homebrew for free,
automatically, on a channel with no notarisation and no Gatekeeper.

The gate in .github/workflows/homebrew-tap/update-formula.yml asserts the file
was attested by THIS repo's release workflow. This drives that decision with
synthetic documents, including the shapes that must fail closed.

Run:  python3 scripts/test-tap-provenance.py [--live]
      --live also checks the real published provenance for a known version.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

EXPECT_REPO = "cassiocassio/bristlenose"
EXPECT_WORKFLOW = "release.yml"
WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/homebrew-tap/update-formula.yml"

PASS = FAIL = 0


def ok(m: str) -> None:
    global PASS
    print(f"  \033[32m✓\033[0m {m}")
    PASS += 1


def bad(m: str) -> None:
    global FAIL
    print(f"  \033[31m✗\033[0m {m}", file=sys.stderr)
    FAIL += 1


def extract_verifier() -> str:
    """Run the SAME python the workflow runs — not a copy that can drift."""
    src = WORKFLOW.read_text()
    m = re.search(r"python3 - <<'VERIFY'\n(.*?)\n\s*VERIFY", src, re.S)
    if not m:
        sys.exit("could not extract the VERIFY heredoc from the workflow")
    return "\n".join(line[10:] if line.startswith(" " * 10) else line
                     for line in m.group(1).splitlines())


VERIFIER = extract_verifier()


def run(doc) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "provenance.json"
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        r = subprocess.run([sys.executable, "-c", VERIFIER], cwd=d,
                           capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr)


def bundle(repo=EXPECT_REPO, workflow=EXPECT_WORKFLOW, kind="GitHub", atts=1):
    return {"publisher": {"kind": kind, "repository": repo, "workflow": workflow},
            "attestations": [{"x": 1}] * atts}


CASES = [
    ("valid provenance accepted",        {"attestation_bundles": [bundle()]},                       0),
    ("wrong repository rejected",        {"attestation_bundles": [bundle(repo="evil/pkg")]},        1),
    ("wrong workflow rejected",          {"attestation_bundles": [bundle(workflow="evil.yml")]},    1),
    ("wrong publisher kind rejected",    {"attestation_bundles": [bundle(kind="GitLab")]},          1),
    ("empty attestations rejected",      {"attestation_bundles": [bundle(atts=0)]},                 1),
    ("no bundles rejected",              {"attestation_bundles": []},                               1),
    ("missing key rejected",             {},                                                        1),
    ("null bundles rejected",            {"attestation_bundles": None},                             1),
    ("malformed JSON rejected",          "{not json",                                               1),
    ("empty document rejected",          "",                                                        1),
    ("publisher absent rejected",        {"attestation_bundles": [{"attestations": [{}]}]},         1),
    ("good bundle among bad accepted",   {"attestation_bundles": [bundle(repo="evil/pkg"), bundle()]}, 0),
    ("case-mismatched repo rejected",    {"attestation_bundles": [bundle(repo="CassioCassio/Bristlenose")]}, 1),
]

print("\n\033[1mprovenance gate — synthetic documents\033[0m")
for name, doc, want in CASES:
    rc, out = run(doc)
    if (rc == 0) == (want == 0):
        ok(name)
    else:
        bad(f"{name}: expected exit {want}, got {rc} — {out.strip()[:90]}")

print("\n\033[1mthe gate is wired into the workflow\033[0m")
src = WORKFLOW.read_text()
checks = {
    "runs before the formula is written":
        src.index("Verify PyPI provenance") < src.index("name: Update formula"),
    "fails closed when provenance is unreachable":
        'if [ -z "$prov" ]; then' in src and "exit 1" in src,
    "steps.* values pass through env, not ${{ }} in run":
        "SDIST_URL: ${{ steps.pypi.outputs.url }}" in src
        and "${{ steps.pypi.outputs.url }}\\\"|" not in src,
    "version shape validated before sed":
        "refusing: unexpected version shape" in src,
    "sdist URL host pinned":
        "files.pythonhosted.org" in src,
}
for name, good in checks.items():
    ok(name) if good else bad(name)

if "--live" in sys.argv:
    print("\n\033[1mlive — the real published provenance\033[0m")
    import urllib.request
    v = "0.27.0"
    fn = f"bristlenose-{v}.tar.gz"
    url = f"https://pypi.org/integrity/bristlenose/{v}/{fn}/provenance"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            live = r.read().decode()
        rc, out = run(live)
        ok(f"real {v} provenance passes the gate") if rc == 0 else bad(f"real {v} REJECTED — {out.strip()[:120]}")
    except Exception as e:  # noqa: BLE001
        print(f"  \033[2m—\033[0m skipped (network): {e}")

print(f"\n\033[1m{PASS} passed, {FAIL} failed\033[0m\n")
sys.exit(1 if FAIL else 0)
