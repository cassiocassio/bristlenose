#!/usr/bin/env python3
"""Bump version in all required files and create git tag.

Usage:
    ./scripts/bump-version.py patch   # 0.6.8 → 0.6.9
    ./scripts/bump-version.py minor   # 0.6.8 → 0.7.0
    ./scripts/bump-version.py major   # 0.6.8 → 1.0.0
    ./scripts/bump-version.py 0.7.0   # explicit version

    ./scripts/bump-version.py --build-only        # new build number, same version
    ./scripts/bump-version.py --build-only 2600   # ... or an explicit one

--build-only exists for re-uploading the SAME marketing version to App Store
Connect. ASC keys builds on (CFBundleShortVersionString, CFBundleVersion), so a
second upload of an unchanged version needs only a higher build number — which
is the 90-day TestFlight expiry refresh, and the retry after a rejected upload.

Before it existed, the only way to move the build number was a full version bump,
and re-running this script at an existing version rewrote __init__.py, the man
page and the pbxproj, THEN died on `git tag` (check=True) — leaving a dirty,
staged tree and still no new build number. --build-only touches the pbxproj
alone: no version files, no tag.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INIT_FILE = ROOT / "bristlenose" / "__init__.py"
MAN_FILE = ROOT / "bristlenose" / "data" / "bristlenose.1"
PBXPROJ_FILE = (
    ROOT / "desktop" / "Bristlenose" / "Bristlenose.xcodeproj" / "project.pbxproj"
)



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


def _sub_or_die(pattern: str, repl: str, text: str, *, path: Path, what: str) -> str:
    """``re.sub`` that refuses to no-op silently.

    Every updater below writes a file and then prints "Updated <path>". When a
    pattern stops matching — Xcode reformats the pbxproj, the ``__version__``
    style changes, someone edits the ``.TH`` line — ``re.sub`` returns the text
    unchanged, the write is a no-op, and that success line becomes a lie. The
    bump then half-lands: some version files move and others don't, which is
    exactly the mismatch ``check-release-ready.sh`` exists to catch, discovered
    much later and blamed on something else.

    Dying here is right even mid-run. A partial bump is a two-second
    ``git checkout``; a silent one ships.
    """
    new_text, n = re.subn(pattern, repl, text)
    if n == 0:
        sys.exit(
            f"error: {path.relative_to(ROOT)} — no match for {what}.\n"
            f"       The file's format has changed and bump-version.py needs updating.\n"
            f"       Check `git status`: files updated before this one have been written."
        )
    return new_text


def update_init(new_version: str) -> None:
    """Update __version__ in __init__.py."""
    text = INIT_FILE.read_text()
    new_text = _sub_or_die(
        r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        rf'\g<1>{new_version}\g<3>',
        text,
        path=INIT_FILE,
        what="the __version__ assignment",
    )
    INIT_FILE.write_text(new_text)
    print(f"  Updated {INIT_FILE.relative_to(ROOT)}")


def update_man_page(new_version: str) -> None:
    """Update .TH line in man page (version + date)."""
    from datetime import date

    today = date.today().isoformat()  # YYYY-MM-DD, mandoc-friendly
    text = MAN_FILE.read_text()
    # Match: .TH BRISTLENOSE 1 "2026-05-11" "bristlenose 0.6.8"
    new_text = _sub_or_die(
        r'(\.TH BRISTLENOSE 1 ")[^"]+(" "bristlenose )\d+\.\d+\.\d+(")',
        rf"\g<1>{today}\g<2>{new_version}\g<3>",
        text,
        path=MAN_FILE,
        what="the .TH header line (date + version)",
    )
    MAN_FILE.write_text(new_text)
    print(f"  Updated {MAN_FILE.relative_to(ROOT)}")


def get_build_number() -> int:
    """Get monotonically increasing build number from git commit count."""
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    return int(result.stdout.strip())


def get_current_build_number() -> int:
    """Read CURRENT_PROJECT_VERSION out of the pbxproj."""
    match = re.search(r"CURRENT_PROJECT_VERSION = (\d+);", PBXPROJ_FILE.read_text())
    if not match:
        sys.exit("Could not find CURRENT_PROJECT_VERSION in project.pbxproj")
    return int(match.group(1))


def update_pbxproj(new_version: str | None, build_number: int) -> None:
    """Update CURRENT_PROJECT_VERSION, and MARKETING_VERSION unless new_version is None."""
    text = PBXPROJ_FILE.read_text()
    text = _sub_or_die(
        r"CURRENT_PROJECT_VERSION = \d+;",
        f"CURRENT_PROJECT_VERSION = {build_number};",
        text,
        path=PBXPROJ_FILE,
        what="CURRENT_PROJECT_VERSION",
    )
    if new_version is not None:
        text = _sub_or_die(
            r"MARKETING_VERSION = [\d.]+;",
            f"MARKETING_VERSION = {new_version};",
            text,
            path=PBXPROJ_FILE,
            what="MARKETING_VERSION",
        )
    PBXPROJ_FILE.write_text(text)
    label = f"{new_version}, build {build_number}" if new_version else f"build {build_number}"
    print(f"  Updated {PBXPROJ_FILE.relative_to(ROOT)} ({label})")


def tag_exists(tag: str) -> bool:
    """Is this tag already present locally?"""
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.returncode == 0


def create_git_tag(new_version: str) -> None:
    """Create git tag (does not push)."""
    tag = f"v{new_version}"
    subprocess.run(["git", "tag", tag], check=True, cwd=ROOT)
    print(f"  Created tag {tag}")


def build_only(explicit: str | None) -> None:
    """Bump the build number alone — same marketing version, no tag."""
    current_build = get_current_build_number()
    version = get_current_version()

    if explicit is not None:
        if not explicit.isdigit():
            sys.exit(f"Invalid build number: {explicit} (expected a positive integer)")
        new_build = int(explicit)
        source = "explicit"
    else:
        new_build = get_build_number()
        source = "git commit count"

    # The guard that makes this useful rather than a silent no-op: the commit
    # count doesn't move unless you commit, so running this twice in a row would
    # otherwise re-write the same number and ASC would reject the upload again
    # with the identical error.
    if new_build <= current_build:
        sys.exit(
            f"Build number would not increase: {source} gives {new_build}, "
            f"pbxproj already has {current_build}.\n"
            f"App Store Connect requires a strictly higher build for the same version.\n"
            f"Either commit something, or pass one explicitly: "
            f"./scripts/bump-version.py --build-only {current_build + 1}"
        )

    print(f"Build {current_build} → {new_build}  (version {version} unchanged, {source})\n")

    update_pbxproj(None, new_build)
    subprocess.run(["git", "add", str(PBXPROJ_FILE)], check=True, cwd=ROOT)
    print("\n  Staged 1 file (no version files touched, no tag created)")

    print("\nDone. Remember to:")
    print(f"  1. Commit: git commit -m 'build {new_build} for a fresh {version} upload'")
    print("  2. Rebuild:  desktop/scripts/build-all.sh")
    print("  3. Gate:     desktop/scripts/check-pkg-shippable.sh <pkg>")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 1)

    if args[0] == "--build-only":
        if len(args) > 2:
            sys.exit("--build-only takes at most one argument (an explicit build number)")
        build_only(args[1] if len(args) == 2 else None)
        return

    if len(args) != 1:
        print(__doc__)
        sys.exit(1)

    bump_type = args[0]
    current = get_current_version()
    new_version = bump_version(current, bump_type)

    # Check the tag BEFORE writing anything. `git tag` runs last with check=True,
    # so an existing tag used to abort after __init__.py, the man page and the
    # pbxproj had all been rewritten and staged — a dirty tree, no new build
    # number, and a traceback instead of an explanation.
    tag = f"v{new_version}"
    if tag_exists(tag):
        sys.exit(
            f"Tag {tag} already exists — nothing has been modified.\n"
            f"To re-upload this version to App Store Connect you need a new BUILD "
            f"number, not a new version:\n"
            f"  ./scripts/bump-version.py --build-only"
        )

    print(f"Bumping {current} → {new_version}\n")

    updated_files = []

    update_init(new_version)
    updated_files.append(INIT_FILE)

    update_man_page(new_version)
    updated_files.append(MAN_FILE)

    build_number = get_build_number()
    update_pbxproj(new_version, build_number)
    updated_files.append(PBXPROJ_FILE)

    # Stage all modified files
    subprocess.run(
        ["git", "add"] + [str(f) for f in updated_files],
        check=True, cwd=ROOT,
    )
    print(f"\n  Staged {len(updated_files)} files")

    create_git_tag(new_version)

    print("\nDone. Remember to:")
    print("  1. Update README.md changelog")
    print("  2. Update CLAUDE.md 'Current status' version")
    print(f"  3. Commit: git commit -m 'bump to {new_version}'")
    print("  4. Push (after 9pm): git push origin main --tags")


if __name__ == "__main__":
    main()
