"""Check filled winget manifests against winget's own JSON schemas.

`winget validate` is the authority and build.ps1 runs it wherever winget is
installed. GitHub's Windows runner cannot install winget (Add-AppxPackage:
"does not have an appropriate application package for x64", 8 Oct 2026), so CI
validates here instead: each file against its schema (vendored from
microsoft/winget-cli, schemas/JSON/manifests/v<version>/), and the three files
against each other. This is the structural half of `winget validate`; it does
not download the installer or check its hash.

    python packaging/windows/validate_manifest.py <manifest dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMAS = Path(__file__).with_name("winget") / "schemas"
EXPECTED_TYPES = {"version", "installer", "defaultLocale"}


def _load(path: Path) -> dict:
    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    # winget reads dates as strings (ReleaseDate: 2026-10-08); PyYAML would
    # turn them into date objects, which a "type": "string" schema rejects.
    _Loader.yaml_implicit_resolvers = {
        k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name}: not a YAML mapping")
    return doc


def validate_dir(manifest_dir: Path) -> list[str]:
    """Return what is wrong with the manifests in ``manifest_dir``; empty if valid."""
    import jsonschema

    problems: list[str] = []
    files = sorted(manifest_dir.glob("*.yaml"))
    seen_types: set[str] = set()
    identity: set[tuple[str, str]] = set()
    for path in files:
        try:
            doc = _load(path)
        except Exception as exc:  # noqa: BLE001 - report every unreadable file
            problems.append(f"{path.name}: {exc}")
            continue
        mtype, mver = doc.get("ManifestType"), doc.get("ManifestVersion")
        schema_path = SCHEMAS / str(mver) / f"manifest.{mtype}.{mver}.json"
        if not schema_path.is_file():
            problems.append(f"{path.name}: no vendored schema for {mtype} {mver} ({schema_path})")
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for error in jsonschema.Draft7Validator(schema).iter_errors(doc):
            problems.append(f"{path.name}: {error.json_path}: {error.message}")
        seen_types.add(str(mtype))
        identity.add((str(doc.get("PackageIdentifier")), str(doc.get("PackageVersion"))))
    if seen_types != EXPECTED_TYPES:
        problems.append(f"expected one each of {sorted(EXPECTED_TYPES)}, found {sorted(seen_types)}")
    if len(identity) > 1:
        problems.append(f"the files disagree on PackageIdentifier/PackageVersion: {sorted(identity)}")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    problems = validate_dir(Path(argv[1]))
    for problem in problems:
        print(f"  x {problem}")
    print("Manifest schema validation " + ("failed." if problems else "passed."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
