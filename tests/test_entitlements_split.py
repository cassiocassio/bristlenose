"""The two Release entitlements files, and why they differ by exactly one group.

Both channels build the `Release` configuration, so they would share one
entitlements file if `build-dmg.sh` did not override `CODE_SIGN_ENTITLEMENTS`.
The Mac App Store build needs the `group.app.bristlenose` app group for
Background Assets; the Developer-ID `.dmg` must NOT carry it — its profile does
not authorise it, and the `.dmg` does not need one because it acquires the PII
model by plain HTTPS.

Both carry the Team-ID-prefixed group `$(TeamIdentifierPrefix)app.bristlenose`,
which holds the MCP handshake for the sandboxed native proxy
(docs/design-mcp-native-proxy.md §6).

The realistic regression is not someone deliberately undoing this. It is someone
editing one file and not the other, or dropping the override line while tidying
the archive invocation — after which the `.dmg` silently carries a group it
cannot use, and nothing fails until an archive refuses to sign.
"""

from __future__ import annotations

import plistlib
import re
import shutil
import subprocess
from pathlib import Path

# shutil.which follows PATH. A bare "bash" on Windows is resolved by
# CreateProcess, which tries System32 first and so finds WSL's bash.exe.
_BASH = shutil.which("bash") or "bash"

_DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
_MAS = _DESKTOP / "Bristlenose" / "Bristlenose" / "Bristlenose.entitlements"
_DEBUG = _DESKTOP / "Bristlenose" / "Bristlenose" / "BristlenoseDebug.entitlements"
_DEV_ID = _DESKTOP / "Bristlenose" / "Bristlenose" / "BristlenoseDeveloperID.entitlements"
_BUILD_DMG = _DESKTOP / "scripts" / "build-dmg.sh"

_APP_GROUP = "com.apple.security.application-groups"
_BA_GROUP = "group.app.bristlenose"
_TEAM_GROUP = "$(TeamIdentifierPrefix)app.bristlenose"

# Zoom's HTTPS sign-in callback. `webcredentials`, never `applinks`: an
# applinks-only entry makes ASWebAuthenticationSession hang after consent.
_ASSOCIATED_DOMAINS = "com.apple.developer.associated-domains"
_WEBCREDENTIALS = ["webcredentials:bristlenose.app"]


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
        assert groups == [_BA_GROUP, _TEAM_GROUP], (
            "Background Assets deposits packs into the App Group container; "
            "without this the archive signs and BA then fails at runtime."
        )

    def test_developer_id_carries_only_the_team_group(self) -> None:
        groups = _load(_DEV_ID).get(_APP_GROUP)
        assert groups == [_TEAM_GROUP], (
            "the .dmg must not carry the Background Assets group (its profile "
            "does not authorise it, and it fetches the model over plain HTTPS), "
            "but it needs the team group for the MCP handshake."
        )

    def test_every_build_carries_the_zoom_callback_domain(self) -> None:
        """Zoom's sign-in returns over HTTPS, which needs this exact entry.

        Debug matters as much as the store build: it is what a Zoom sign-in is
        tested on, and without the entitlement the consent page completes and
        nothing comes back, with no error anywhere. The .dmg carries it too
        since 18 Oct 2026, so Zoom import works where Teams and Meet do.
        """
        for p in (_MAS, _DEBUG, _DEV_ID):
            assert _load(p).get(_ASSOCIATED_DOMAINS) == _WEBCREDENTIALS, (
                f"{p.name} must carry {_WEBCREDENTIALS} — webcredentials, not "
                "applinks, or the Zoom sign-in hangs after consent"
            )

    def test_they_differ_by_exactly_the_store_only_entitlements(self) -> None:
        """Anything else diverging is drift, not design."""
        mas, dev = _load(_MAS), _load(_DEV_ID)
        assert set(mas) == set(dev)
        assert set(mas[_APP_GROUP]) - set(dev[_APP_GROUP]) == {_BA_GROUP}
        assert set(dev[_APP_GROUP]) - set(mas[_APP_GROUP]) == set()
        for key in set(dev) - {_APP_GROUP}:
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

    def test_the_invocation_is_not_truncated(self) -> None:
        """Run the block with a stub and read the arguments that arrive.

        Asserting a flag is *in the file* cannot tell you it reaches the
        command. A ``#`` comment between two backslash-continued lines ends the
        command there: everything below it is parsed as new commands, and
        ``bash -n`` passes because the result is valid, merely truncated. That
        happened while fixing the relative-path bug above — xcodebuild ran with
        no entitlements override and no ``archive`` verb, printed BUILD
        SUCCEEDED, and the next line failed as
        ``-allowProvisioningUpdates: command not found``.

        The dangerous version of that truncation is the quiet one: cut after
        ``archive`` instead of before it and the archive is produced with the
        project's own MAS entitlements — app group and all — on the Developer-ID
        channel Apple will not authorise it for. No error, wrong artefact.
        """
        import re
        import subprocess

        src = _BUILD_DMG.read_text(encoding="utf-8").splitlines()
        i = next(n for n, ln in enumerate(src) if ln.strip() == "xcodebuild \\")
        j = next(n for n in range(i, len(src)) if 'xcodebuild archive failed' in src[n])
        block = "\n".join(src[i:j + 1])
        block = block.replace('> "$ARCHIVE_LOG" 2>&1 \\\n', "")
        block = re.sub(r'\|\| \{ echo "xcodebuild archive failed.*', "", block, flags=re.S)
        script = (
            'xcodebuild() { printf "%s\\n" "$@"; }\n'
            "PROJECT_DIR=/PD; ARCHIVE_PATH=/AP; TEAM_ID=TID; ARCHIVE_LOG=/dev/null\n"
            + block
        )
        out = subprocess.run(
            [_BASH, "-c", script], capture_output=True, text=True, timeout=30
        ).stdout.splitlines()

        assert "archive" in out, (
            "the `archive` verb never reaches xcodebuild — the invocation is "
            f"truncated. Arguments that arrived: {out}"
        )
        ent = [a for a in out if a.startswith("CODE_SIGN_ENTITLEMENTS=")]
        assert len(ent) == 1, f"entitlements override did not arrive: {out}"
        assert ent[0].endswith("BristlenoseDeveloperID.entitlements"), ent[0]
        assert "-allowProvisioningUpdates" in out, out

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
    """Reading the working tree is not enough for these files.

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
        assert d.get(_APP_GROUP) == [_BA_GROUP, _TEAM_GROUP], (
            "the app group is missing from the COMMITTED file — a fresh clone "
            "would build without it. Check `git ls-files -v | grep '^S'`."
        )

    def test_the_committed_files_carry_the_zoom_callback_domain(self) -> None:
        """The entitlement was exactly the skip-worktree edit that went missing
        on 12 Sep 2026 while every working-tree test passed."""
        for rel in ("desktop/Bristlenose/Bristlenose/Bristlenose.entitlements",
                    "desktop/Bristlenose/Bristlenose/BristlenoseDebug.entitlements",
                    "desktop/Bristlenose/Bristlenose/BristlenoseDeveloperID.entitlements"):
            assert self._from_head(rel).get(_ASSOCIATED_DOMAINS) == _WEBCREDENTIALS, (
                f"{rel} at HEAD has no {_ASSOCIATED_DOMAINS} — a fresh clone "
                "would build a Zoom sign-in that never returns"
            )

    def test_no_entitlements_file_is_skip_worktree(self) -> None:
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
        assert hidden == [], (
            f"skip-worktree entitlements: {hidden} — edits to them will not "
            "commit and this suite will pass against a tree nobody else has."
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
        body = _PKG_GATE.read_text(encoding="utf-8")
        assert _APP_GROUP_KEY in body, (
            "the MAS .pkg gate does not check for the app group — Background "
            "Assets would fail at runtime on a build that signed cleanly"
        )
        assert 'die "app group"' in body, (
            "the app-group check must DIE, not warn: a missing group is a "
            "silent capability loss, which is exactly what a warning becomes"
        )

    def test_dmg_gate_refuses_the_app_group(self) -> None:
        body = _DMG_GATE.read_text(encoding="utf-8")
        assert _APP_GROUP_KEY in body, (
            "the Developer-ID .dmg gate does not read entitlements — until "
            "12 Sep 2026 it read none at all, so a mistyped override had "
            "nothing between it and a published image"
        )
        assert 'fail "app group"' in body, (
            "the wrong app group on Developer-ID must FAIL the gate — the "
            "Background Assets group is App-Store-only, and the team group the "
            "MCP helper reads must be there"
        )

    def test_neither_gate_matches_the_bare_entitlement_name(self) -> None:
        """The substring trap, pinned so it cannot be loosened back.

        `grep -q 'com.apple.security.application-groups'` matches the comment
        in `BristlenoseDeveloperID.entitlements` that explains why the key is
        absent — so the .dmg gate would report the group PRESENT on a correct
        file and fail every clean build.
        """
        for gate in (_PKG_GATE, _DMG_GATE):
            for line in gate.read_text(encoding="utf-8").splitlines():
                if "grep" not in line or _APP_GROUP not in line:
                    continue
                assert _APP_GROUP_KEY in line, (
                    f"{gate.name} greps the bare entitlement name, which also "
                    f"matches the explanatory comments: {line.strip()!r}"
                )


_PBXPROJ = _DESKTOP / "Bristlenose" / "Bristlenose.xcodeproj" / "project.pbxproj"


class TestTheSandboxRefusesPrinting:
    """No shipping build carries `com.apple.security.print`: printing is post-v1.

    R69 (21 Oct 2026) turned it on so File ▸ Print would open the print panel.
    The owner withdrew printing for v1 on 23 Oct 2026, because what prints is
    not a deliverable: Quotes cards below the fold print blank
    (`content-visibility`), the app chrome prints, real names print whatever
    the Anonymise setting says, and nothing on the page says what it is
    (`docs/design-printing.md`). File ▸ Print and Page Setup are gone from the
    menus, so the entitlement would be a capability with no affordance — and
    one App Review asks about.

    The host's sandbox entitlements are generated from `ENABLE_*` build
    settings, not from the `.entitlements` files above, so a capability toggle
    in Xcode puts it back with no diff in those files. These assertions are
    what notices. When printing is designed, invert them in the same commit.
    """

    def test_no_sandboxed_configuration_may_print(self) -> None:
        text = _PBXPROJ.read_text(encoding="utf-8")
        blocks = re.findall(r"buildSettings = \{(.*?)\n\t\t\t\};", text, re.DOTALL)
        app = [b for b in blocks if "PRODUCT_BUNDLE_IDENTIFIER = app.bristlenose;" in b]
        assert len(app) == 2, (
            "expected the app target's Debug and Release configurations; "
            f"found {len(app)} — the parse no longer sees them"
        )
        for block in app:
            assert "ENABLE_APP_SANDBOX = YES;" in block
            # Pin the explicit NO rather than the absence of YES: a missing row
            # is Xcode's default today, and a default is not a decision.
            assert "ENABLE_RESOURCE_ACCESS_PRINTING = NO;" in block, (
                "a configuration grants com.apple.security.print — printing is "
                "post-v1, and File ▸ Print is not in the menus to use it"
            )

    def test_no_entitlements_file_grants_print(self) -> None:
        for path in (_MAS, _DEV_ID, _DEBUG):
            assert "<key>com.apple.security.print</key>" not in path.read_text(
                encoding="utf-8"
            ), f"{path.name} grants com.apple.security.print — printing is post-v1"

    def test_both_artefact_gates_refuse_print_on_the_signed_app(self) -> None:
        """The pbxproj is the setting; the gates read what was actually signed."""
        for gate, verdict in ((_PKG_GATE, 'die "host print"'), (_DMG_GATE, 'fail "print"')):
            body = gate.read_text(encoding="utf-8")
            assert "<key>com.apple.security.print</key>" in body, (
                f"{gate.name} does not check the print entitlement on the artefact"
            )
            assert verdict in body, f"{gate.name} must refuse an artefact that may print"
            assert '"print" "present"' not in body and '"host print" "present"' not in body, (
                f"{gate.name} still passes an artefact because it may print"
            )
            # The refusal must be the branch the grep takes, not merely present:
            # a swapped if/else keeps every string above and passes an artefact
            # that may print. The pkg gate also has a fixture suite; the dmg gate
            # has only this.
            assert re.search(
                r"if grep -q '<key>com\.apple\.security\.print</key>'[^\n]*\n\s*"
                + re.escape(verdict),
                body,
            ), f"{gate.name}: the print grep's then-branch is not `{verdict}`"


class TestTheSpeechHelperShipsAndIsGated:
    """Apple-first transcription graduated on 22 Oct 2026: the sidecar launches
    `bristlenose-speech` on a first run, so every build must embed it and every
    shippable gate must require it and run its one check. While it was parked
    the gates did the opposite (a copy in a release archive was a leak), and a
    gate left in that shape would now fail every correct release."""

    def test_every_configuration_embeds_the_helper(self) -> None:
        text = _PBXPROJ.read_text(encoding="utf-8")
        assert "speech-helper/build-helper.sh" in text
        assert "BRISTLENOSE_BUNDLE_SPEECH_HELPER" not in text, (
            "the Debug-only override is back: a release archive would ship "
            "without the helper, and a first run would wait for Whisper"
        )
        assert "Helpers/bristlenose-speech" not in text, (
            "the phase still removes the helper from some configuration"
        )

    def test_both_shippable_gates_require_and_check_it(self) -> None:
        for gate in (_PKG_GATE, _DMG_GATE):
            body = gate.read_text(encoding="utf-8")
            assert "check-speech-helper.sh" in body, f"{gate.name} does not check the helper"
            assert "absent (parked)" not in body, f"{gate.name} still treats the helper as parked"
