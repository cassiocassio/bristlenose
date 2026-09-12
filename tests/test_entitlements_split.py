"""The two Release entitlements files, and why they differ by exactly one key.

Both channels build the `Release` configuration, so they would share one
entitlements file if `build-dmg.sh` did not override `CODE_SIGN_ENTITLEMENTS`.
The Mac App Store build needs `com.apple.security.application-groups` for
Background Assets; the Developer-ID `.dmg` must NOT carry it — Apple will not
authorise an app group on that channel, and the `.dmg` does not need one because
it acquires the PII model by plain HTTPS.

The realistic regression is not someone deliberately undoing this. It is someone
editing one file and not the other, or dropping the override line while tidying
the archive invocation — after which the `.dmg` silently carries a group it
cannot use, and nothing fails until an archive refuses to sign.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

_DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
_MAS = _DESKTOP / "Bristlenose" / "Bristlenose" / "Bristlenose.entitlements"
_DEV_ID = _DESKTOP / "Bristlenose" / "Bristlenose" / "BristlenoseDeveloperID.entitlements"
_BUILD_DMG = _DESKTOP / "scripts" / "build-dmg.sh"

_APP_GROUP = "com.apple.security.application-groups"


def _load(path: Path) -> dict:
    with path.open("rb") as fh:
        return plistlib.load(fh)


class TestTheSplitExists:
    def test_both_files_are_present_and_valid(self) -> None:
        for p in (_MAS, _DEV_ID):
            assert p.is_file(), f"{p.name} is missing — the split is the whole point"
            assert isinstance(_load(p), dict)

    def test_mas_carries_the_app_group(self) -> None:
        groups = _load(_MAS).get(_APP_GROUP)
        assert groups == ["group.app.bristlenose"], (
            "Background Assets deposits packs into the App Group container; "
            "without this the archive signs and BA then fails at runtime."
        )

    def test_developer_id_does_not(self) -> None:
        assert _APP_GROUP not in _load(_DEV_ID), (
            "Apple will not authorise an app group on Developer ID, and the "
            ".dmg does not need one — it fetches the model over plain HTTPS."
        )

    def test_they_differ_by_exactly_that_one_key(self) -> None:
        """Anything else diverging is drift, not design."""
        mas, dev = _load(_MAS), _load(_DEV_ID)
        assert set(mas) - set(dev) == {_APP_GROUP}
        assert set(dev) - set(mas) == set()
        for key in set(dev):
            assert mas[key] == dev[key], f"{key} drifted between the two files"


class TestTheBuildActuallySelectsIt:
    def test_build_dmg_overrides_the_entitlements(self) -> None:
        """Without this line the split is inert and the .dmg gets the group."""
        text = _BUILD_DMG.read_text(encoding="utf-8")
        assert "CODE_SIGN_ENTITLEMENTS=" in text, (
            "build-dmg.sh must override CODE_SIGN_ENTITLEMENTS — both channels "
            "build Release, so otherwise the .dmg uses the App Store file."
        )
        assert _DEV_ID.name in text, (
            f"the override must point at {_DEV_ID.name}"
        )

    def test_the_override_sits_in_the_archive_invocation(self) -> None:
        """A build setting only applies to the xcodebuild call it is attached to."""
        text = _BUILD_DMG.read_text(encoding="utf-8")
        # Split on the standalone `archive` verb, not the first "archive"
        # substring — `-archivePath` comes earlier and would cut the block
        # short, which is how this test failed the first time it ran.
        body = text.split("xcodebuild", 1)[1]
        archive = body.split("\n    archive", 1)[0]
        assert "CODE_SIGN_ENTITLEMENTS=" in archive, (
            "the override drifted out of the archive invocation and is now inert"
        )


class TestTheEntitlementsAreActuallyCommitted:
    """Reading the working tree is not enough for these two files.

    `Bristlenose.entitlements` was `skip-worktree` — set to keep a parked local
    `associated-domains` edit out of commits — so `git status` reported clean
    while the app-group addition sat uncommitted. Every test above would have
    passed locally and a fresh clone would have built a Mac App Store binary
    with no app group and no error. That is the `c837f8b5` failure class: a file
    that exists on one disk and nowhere else.

    These read git, not the filesystem, so an uncommitted edit cannot satisfy
    them.
    """

    @staticmethod
    def _from_head(relpath: str) -> dict:
        out = subprocess.run(
            ["git", "show", f"HEAD:{relpath}"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, check=True,
        )
        return plistlib.loads(out.stdout)

    def test_the_committed_mas_file_carries_the_app_group(self) -> None:
        d = self._from_head("desktop/Bristlenose/Bristlenose/Bristlenose.entitlements")
        assert d.get(_APP_GROUP) == ["group.app.bristlenose"], (
            "the app group is missing from the COMMITTED file — a fresh clone "
            "would build without it. Check `git ls-files -v | grep '^S'`."
        )

    def test_neither_file_is_skip_worktree(self) -> None:
        """The flag makes any future edit to these invisible to git status."""
        out = subprocess.run(
            ["git", "ls-files", "-v", "--", "desktop/Bristlenose/Bristlenose/"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, check=True,
        ).stdout
        hidden = [
            line.split(" ", 1)[1]
            for line in out.splitlines()
            if line.startswith("S") and line.endswith(".entitlements")
        ]
        assert "desktop/Bristlenose/Bristlenose/Bristlenose.entitlements" not in hidden, (
            "Bristlenose.entitlements is skip-worktree again — edits to it will "
            "not commit and this suite will pass against a tree nobody else has."
        )
