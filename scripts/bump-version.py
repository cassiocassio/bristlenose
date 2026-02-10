#!/usr/bin/env python3
"""Bump version in all required files and create git tag.

Usage:
    ./scripts/bump-version.py patch   # 0.6.8 → 0.6.9
    ./scripts/bump-version.py minor   # 0.6.8 → 0.7.0
    ./scripts/bump-version.py major   # 0.6.8 → 1.0.0
    ./scripts/bump-version.py 0.7.0   # explicit version
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INIT_FILE = ROOT / "bristlenose" / "__init__.py"
MAN_FILE = ROOT / "bristlenose" / "data" / "bristlenose.1"



def get_current_version() -> str:
    """Read current version from __init__.py."""
    text = INIT_FILE.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        sys.exit("Could not find __version__ in __init__.py")
    return match.group(1)


def bump_version(current: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    if bump_type in ("major", "minor", "patch"):
        parts = [int(p) for p in current.split(".")]
        if len(parts) != 3:
            sys.exit(f"Version {current} is not semver (x.y.z)")

        if bump_type == "major":
            parts = [parts[0] + 1, 0, 0]
        elif bump_type == "minor":
            parts = [parts[0], parts[1] + 1, 0]
        else:  # patch
            parts = [parts[0], parts[1], parts[2] + 1]

        return ".".join(str(p) for p in parts)
    else:
        # Assume explicit version
        if not re.match(r"^\d+\.\d+\.\d+$", bump_type):
            sys.exit(f"Invalid version: {bump_type} (expected x.y.z)")
        return bump_type


def update_init(new_version: str) -> None:
    """Update __version__ in __init__.py."""
    text = INIT_FILE.read_text()
    new_text = re.sub(
        r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        rf'\g<1>{new_version}\g<3>',
        text,
    )
    INIT_FILE.write_text(new_text)
    print(f"  Updated {INIT_FILE.relative_to(ROOT)}")


def update_man_page(new_version: str) -> None:
    """Update .TH line in man page."""
    text = MAN_FILE.read_text()
    # Match: .TH BRISTLENOSE 1 "January 2026" "bristlenose 0.6.8"
    new_text = re.sub(
        r'(\.TH BRISTLENOSE 1 "[^"]+" "bristlenose )\d+\.\d+\.\d+(")',
        rf"\g<1>{new_version}\g<2>",
        text,
    )
    MAN_FILE.write_text(new_text)
    print(f"  Updated {MAN_FILE.relative_to(ROOT)}")


def create_git_tag(new_version: str) -> None:
    """Create git tag (does not push)."""
    tag = f"v{new_version}"
    subprocess.run(["git", "tag", tag], check=True, cwd=ROOT)
    print(f"  Created tag {tag}")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    bump_type = sys.argv[1]
    current = get_current_version()
    new_version = bump_version(current, bump_type)

    print(f"Bumping {current} → {new_version}\n")

    update_init(new_version)
    update_man_page(new_version)
    create_git_tag(new_version)

    print("\nDone. Remember to:")
    print("  1. Update README.md changelog")
    print("  2. Update CLAUDE.md 'Current status' version")
    print(f"  3. Commit: git add -A && git commit -m 'bump to {new_version}'")
    print("  4. Push (after 9pm): git push origin main --tags")


if __name__ == "__main__":
    main()
