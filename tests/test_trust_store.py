"""The CA bundle every HTTPS call trusts (certifi) carries no root we know is bad,
and the Windows installer's pin is at least pyproject's floor."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path

import certifi
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from packaging.requirements import Requirement
from packaging.version import Version

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]

# SHA-256 of the root's SubjectPublicKeyInfo (DER), so a re-issued certificate
# over the same key is still caught. The next incident adds a line.
DENYLIST = {
    # emSign ECC Root CA - G3 (eMudhra): intermediate keys compromised, removed
    # from Mozilla NSS and certifi 2026.10.19. Hashed from certifi 2026.7.22, 23 Oct 2026.
    "8d417db2dd8bf5e3084d1e3f196d583849d81bdd4c00c70b9d39369e96b8c782": "emSign ECC Root CA - G3",
}


def _spki_hashes(pem: Path) -> set[str]:
    with warnings.catch_warnings():
        # some long-standing roots carry a non-positive serial; not our concern here
        warnings.simplefilter("ignore")
        certs = x509.load_pem_x509_certificates(pem.read_bytes())
    return {
        hashlib.sha256(
            c.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        ).hexdigest()
        for c in certs
    }


def test_the_installed_ca_bundle_trusts_no_denylisted_root() -> None:
    found = _spki_hashes(Path(certifi.where())) & DENYLIST.keys()
    assert not found, (
        f"certifi {certifi.__version__} still trusts {[DENYLIST[h] for h in found]}: "
        "upgrade certifi"
    )


def test_the_windows_pin_meets_the_certifi_floor() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    req = next(Requirement(d) for d in project["dependencies"] if d.startswith("certifi"))
    floor = next(Version(s.version) for s in req.specifier if s.operator == ">=")
    constraints = (ROOT / "packaging" / "windows" / "constraints.txt").read_text(encoding="utf-8")
    pin = next(
        Version(ln.split("==", 1)[1]) for ln in constraints.splitlines() if ln.startswith("certifi==")
    )
    assert pin >= floor, f"Windows pins certifi {pin}, below the floor {floor}: run lock.py"
