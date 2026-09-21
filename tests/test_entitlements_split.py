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

    def test_the_override_path_is_absolute(self) -> None:
        """A relative path here cannot resolve, and not for the app target.

        A command-line build setting applies to EVERY target in the build, and
        Xcode resolves a relative ``CODE_SIGN_ENTITLEMENTS`` against each
        target's own ``$(SRCROOT)``. The Settings Swift package's SRCROOT is its
        checkout under ``DerivedData/SourcePackages``, where
        ``Bristlenose/BristlenoseDeveloperID.entitlements`` does not exist — so
        the archive died on ``Settings_Settings`` with "could not be opened",
        naming a target nobody had thought about, while the app target the
        override was written for was never the problem.

        Every test above passed throughout: they assert the override EXISTS in
        the invocation, which it did. Nothing asserted the archive could run.
        Caught on the 0.30.0 release, the first ``.dmg`` built since the split
        landed — the previous one was 31 Aug 2026, and the override arrived
        after it.
        """
        text = _BUILD_DMG.read_text(encoding="utf-8")
        line = next(
            ln for ln in text.splitlines()
            if "CODE_SIGN_ENTITLEMENTS=" in ln and not ln.lstrip().startswith("#")
        )
        value = line.split("CODE_SIGN_ENTITLEMENTS=", 1)[1].strip().rstrip("\\").strip().strip('"')
        assert value.startswith(("/", "$")), (
            f"CODE_SIGN_ENTITLEMENTS is {value!r} — a bare relative path. It "
            "resolves against each target's own SRCROOT, so the Settings "
            "package cannot find it and the archive fails before the app is "
            "ever signed. Use an absolute path."
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


_PKG_GATE = _DESKTOP / "scripts" / "check-pkg-shippable.sh"
_DMG_GATE = _DESKTOP / "scripts" / "check-dmg-shippable.sh"

# The <key> element, not the bare entitlement name. Both plists carry comments
# that MENTION the entitlement by name, so a substring grep answers "present"
# for the file that deliberately omits it — measured 12 Sep 2026 while adding
# these very probes. The tests above dodge it by parsing with plistlib; a shell
# gate cannot, so it must scope to the element.
_APP_GROUP_KEY = f"<key>{_APP_GROUP}</key>"


class TestTheArtefactGatesCheckTheSplitToo:
    """The source split is gated above; this gates the built artefacts.

    A `CODE_SIGN_ENTITLEMENTS` override is one line in one archive invocation.
    If it is ever dropped or mistyped, the source files still differ, every test
    above still passes, and the wrong entitlements reach a shipped image. Only a
    gate reading the signed artefact catches that.
    """

    def test_pkg_gate_requires_the_app_group(self) -> None:
        body = _PKG_GATE.read_text()
        assert _APP_GROUP_KEY in body, (
            "the MAS .pkg gate does not check for the app group — Background "
            "Assets would fail at runtime on a build that signed cleanly"
        )
        assert 'die "app group"' in body, (
            "the app-group check must DIE, not warn: a missing group is a "
            "silent capability loss, which is exactly what a warning becomes"
        )

    def test_dmg_gate_refuses_the_app_group(self) -> None:
        body = _DMG_GATE.read_text()
        assert _APP_GROUP_KEY in body, (
            "the Developer-ID .dmg gate does not read entitlements — until "
            "12 Sep 2026 it read none at all, so a mistyped override had "
            "nothing between it and a published image"
        )
        assert 'fail "app group"' in body, (
            "an app group on Developer-ID must FAIL the gate — Apple will not "
            "authorise one on that channel"
        )

    def test_neither_gate_matches_the_bare_entitlement_name(self) -> None:
        """The substring trap, pinned so it cannot be loosened back.

        `grep -q 'com.apple.security.application-groups'` matches the comment
        in `BristlenoseDeveloperID.entitlements` that explains why the key is
        absent — so the .dmg gate would report the group PRESENT on a correct
        file and fail every clean build.
        """
        for gate in (_PKG_GATE, _DMG_GATE):
            for line in gate.read_text().splitlines():
                if "grep" not in line or _APP_GROUP not in line:
                    continue
                assert _APP_GROUP_KEY in line, (
                    f"{gate.name} greps the bare entitlement name, which also "
                    f"matches the explanatory comments: {line.strip()!r}"
                )
