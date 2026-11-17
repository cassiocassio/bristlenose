"""Pins for the Background Assets extension target (the Background Assets plan, section on the release lanes).

The extension is a second signed process in the store build, and several things about it are
invisible until upload or a release night: the Developer-ID lane signing it with the app's
entitlements, a floor above the app's that a template silently resets, a version that drifts from
the host's, an Info.plist that leaks keys into the other channel. Each pin reads the project file
or the extension's own files, the only places these facts are written down.

It is dark on purpose today: the target exists and builds, but the app does not depend on it or
embed it, and ``BA_WHISPER`` is defined nowhere. ``TestTheExtensionIsStillDark`` pins that, and is
the test to edit, deliberately, in the commit that embeds it.
"""

from __future__ import annotations

import plistlib
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DESKTOP = _ROOT / "desktop"
_EXT = _DESKTOP / "BAExtension"
_PBXPROJ = _DESKTOP / "Bristlenose" / "Bristlenose.xcodeproj" / "project.pbxproj"
_EXPORT = _DESKTOP / "Bristlenose" / "ExportOptions.plist"
_BUILD_ALL = _DESKTOP / "scripts" / "build-all.sh"

_EXT_ID = "app.bristlenose.BAExtension"
#: The extension's product (BAExtension.appex) file reference. An embed phase names the product
#: as a PBXBuildFile; nothing else does, whatever Xcode calls the phase or its comment.
_PRODUCT_REF = "BA0000000000000000000005"
_EMBED_BUILD_FILE = re.compile(r"isa = PBXBuildFile; fileRef = " + _PRODUCT_REF + r"[ ;]")
#: Team-prefixed, so it needs no portal registration; the host holds it in both store and .dmg files.
_BA_GROUP = "$(TeamIdentifierPrefix)app.bristlenose"


def _load(path: Path) -> dict:
    with path.open("rb") as fh:
        return plistlib.load(fh)


def _text() -> str:
    return _PBXPROJ.read_text(encoding="utf-8")


def _ext_configs() -> list[str]:
    """The two XCBuildConfiguration bodies of the BAExtension target."""
    text = _text()
    # The target's configuration list names its two configs; take the blocks that set its id.
    return re.findall(
        r"buildSettings = \{([^}]*PRODUCT_BUNDLE_IDENTIFIER = " + re.escape(_EXT_ID) + r";[^}]*)\};",
        text,
    )


class TestTheExtensionFiles:
    def test_the_entitlements_are_an_extension_s_not_a_helper_s(self) -> None:
        ents = _load(_EXT / "BAExtension.entitlements")
        assert ents["com.apple.security.app-sandbox"] is True
        assert "com.apple.security.inherit" not in ents, (
            "an extension is launched by the system, not spawned by the app: inherit makes launchd refuse it"
        )
        assert ents["com.apple.security.application-groups"] == [_BA_GROUP], (
            "the extension shares the host's BAAppGroupID and nothing else"
        )
        # Without these two the profile is not embedded and the system refuses the connection
        # ("lacks a string team identifier": measured on the toy, 16 Nov 2026).
        assert ents["com.apple.application-identifier"] == "$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)"
        assert ents["com.apple.developer.team-identifier"] == "$(DEVELOPMENT_TEAM)"
        assert "com.apple.security.get-task-allow" not in ents

    def test_the_host_group_is_one_the_store_entitlements_hold(self) -> None:
        host = _load(_DESKTOP / "Bristlenose" / "Bristlenose" / "Bristlenose.entitlements")
        assert _BA_GROUP in host["com.apple.security.application-groups"]

    def test_the_info_plist_is_the_downloader_extension_point_and_nothing_else(self) -> None:
        info = _load(_EXT / "Info.plist")
        # The ExtensionKit form (Xcode 27.2's Background Download template; measured to work, and
        # the NSExtension form is not what Apple's template produces): no NSExtension dict.
        assert "NSExtension" not in info
        assert info["EXAppExtensionAttributes"] == {
            "EXExtensionPointIdentifier": "com.apple.background-asset-downloader-extension"
        }, "no principal class: StoreDownloaderExtension is the whole extension"
        assert info["CFBundlePackageType"] == "XPC!"
        # Apple's upload refuses an extension with no display name (ITMS-90360,
        # found 17 Nov by the first real delivery).
        assert info["CFBundleDisplayName"].strip()
        # Version, build and floor come from build settings, so there is one place to bump them.
        assert info["CFBundleShortVersionString"] == "$(MARKETING_VERSION)"
        assert info["CFBundleVersion"] == "$(CURRENT_PROJECT_VERSION)"
        assert info["LSMinimumSystemVersion"] == "$(MACOSX_DEPLOYMENT_TARGET)"
        # The OAuth client IDs live in the app's plist only; copying them here is a second place
        # to forget (and ships Teams/Zoom identifiers in a process that never signs anyone in).
        assert not [k for k in info if "OAuth" in k or k.startswith("BA")], sorted(info)

    def test_the_privacy_manifest_is_empty_and_valid(self) -> None:
        manifest = _load(_EXT / "PrivacyInfo.xcprivacy")
        assert manifest["NSPrivacyTracking"] is False
        assert manifest["NSPrivacyCollectedDataTypes"] == []
        assert manifest["NSPrivacyAccessedAPITypes"] == []

    def test_the_target_is_an_extensionkit_extension(self) -> None:
        text = _text()
        assert 'productType = "com.apple.product-type.extensionkit-extension";' in text
        assert "com.apple.product-type.app-extension" not in text
        assert 'explicitFileType = "wrapper.extensionkit-extension"' in text

    def test_the_source_is_the_one_line_extension(self) -> None:
        src = (_EXT / "BAExtension.swift").read_text(encoding="utf-8")
        assert "StoreDownloaderExtension" in src, "Apple-hosted packs use the Store downloader"
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("//"))
        assert "ManagedDownloaderExtension" not in code, "self-hosted is the other class"
        assert "@main" in src
        assert "import ExtensionFoundation" in src


class TestTheTargetInTheProject:
    def test_both_configurations_exist_with_the_right_identity_and_floor(self) -> None:
        configs = _ext_configs()
        assert len(configs) == 2, "Debug and Release of the BAExtension target"
        for body in configs:
            assert "MACOSX_DEPLOYMENT_TARGET = 26.0;" in body, (
                "a template defaults to the SDK (27.2), which would not load on macOS 26"
            )
            assert "CODE_SIGN_ENTITLEMENTS = ../BAExtension/BAExtension.entitlements;" in body
            assert "INFOPLIST_FILE = ../BAExtension/Info.plist;" in body
            assert "CODE_SIGN_STYLE = Manual;" in body, (
                "automatic signing in an IDE build would register the App ID by itself"
            )

    def test_its_version_moves_with_the_apps(self) -> None:
        """bump-version.py rewrites every CURRENT_PROJECT_VERSION and MARKETING_VERSION, so the
        extension follows the host: a different number is an ITMS version-mismatch upload error."""
        text = _text()
        assert len(set(re.findall(r"CURRENT_PROJECT_VERSION = (\d+);", text))) == 1
        assert len(set(re.findall(r"MARKETING_VERSION = ([\d.]+);", text))) == 1
        for body in _ext_configs():
            assert re.search(r"CURRENT_PROJECT_VERSION = \d+;", body)
            assert re.search(r"MARKETING_VERSION = [\d.]+;", body)

    def test_no_other_target_names_the_extension_s_entitlements(self) -> None:
        text = _text()
        assert text.count("../BAExtension/BAExtension.entitlements") == 2  # its two configs only


class TestTheEmbedIsGatedAndOnlyTheStoreSchemeBuildsIt:
    """The extension reaches an app only through the store lane.

    Xcode must embed and sign it (a hand-copied, re-signed extension was measured never to start), so
    the app has a real Copy Files phase ("Embed ExtensionKit Extensions", into Contents/Extensions).
    That phase is switched off by default through EXCLUDED_SOURCE_FILE_NAMES, which `build-all.sh`
    lifts with BN_EMBED_BA=YES; and there is no target dependency, so only the "Bristlenose Store"
    scheme builds the extension (measured: the plain scheme neither builds nor embeds it).
    """

    _SCHEMES = _DESKTOP / "Bristlenose" / "Bristlenose.xcodeproj" / "xcshareddata" / "xcschemes"

    def test_the_app_embeds_it_through_xcode_but_never_depends_on_it(self) -> None:
        text = _text()
        assert _EMBED_BUILD_FILE.search(text), "the embed is a real Xcode phase, so Xcode signs it"
        assert 'dstPath = "$(EXTENSIONS_FOLDER_PATH)";' in text and "dstSubfolderSpec = 16;" in text
        assert "remoteInfo = BAExtension;" not in text, "a target dependency would make every app build sign it"

    def test_the_embed_is_off_unless_the_store_lane_turns_it_on(self) -> None:
        text = _text()
        # Two app configurations (Debug, Release) each exclude the product unless BN_EMBED_BA=YES.
        assert text.count('EXCLUDED_SOURCE_FILE_NAMES = "$(BN_BA_EXCLUDE_$(BN_EMBED_BA))";') == 2
        assert text.count("BN_EMBED_BA = NO;") == 2
        assert text.count("BN_BA_EXCLUDE_NO = BAExtension.appex;") == 2
        assert text.count('BN_BA_EXCLUDE_YES = "";') == 2

    def test_the_host_keys_script_is_wired_and_gated(self) -> None:
        text = _text()
        assert "Background Assets Host Keys" in text and "embed-ba-extension.sh" in text
        script = (_DESKTOP / "scripts" / "embed-ba-extension.sh").read_text(encoding="utf-8")
        # Gated first, refuses in a .dmg build, checks the extension really is embedded, and adds
        # exactly the three host keys (the team-prefixed group needs a team).
        assert script.index('BN_EMBED_BA:-NO') < script.index("Extensions/BAExtension.appex")
        assert "DEVELOPER_ID_BETA" in script
        for key in ("BAAppGroupID", "BAHasManagedAssetPacks", "BAUsesAppleHosting"):
            assert key in script
        assert "${DEVELOPMENT_TEAM:?" in script and ".app.bristlenose" in script
        assert "ditto" not in script, "copying by hand is the thing that was measured not to work"

    def test_only_the_store_scheme_builds_the_extension(self) -> None:
        for scheme in self._SCHEMES.glob("*.xcscheme"):
            has = "BAExtension" in scheme.read_text(encoding="utf-8")
            assert has == (scheme.name == "Bristlenose Store.xcscheme"), scheme.name

    def test_the_store_scheme_builds_the_extension_first_and_one_at_a_time(self) -> None:
        """The embed script needs the extension's product to exist. With no target dependency, only
        sequential building in the listed order guarantees that (parallel builds raced)."""
        text = (self._SCHEMES / "Bristlenose Store.xcscheme").read_text(encoding="utf-8")
        assert 'parallelizeBuildables = "NO"' in text
        assert text.index("BAExtension.appex") < text.index("Bristlenose.app"), "extension listed first"

    def test_the_store_lane_archives_that_scheme_with_the_flag(self) -> None:
        text = _BUILD_ALL.read_text(encoding="utf-8")
        assert '-scheme "Bristlenose Store"' in text and "BN_EMBED_BA=YES" in text
        dmg = (_DESKTOP / "scripts" / "build-dmg.sh").read_text(encoding="utf-8")
        assert "Bristlenose Store" not in dmg and "BN_EMBED_BA" not in dmg, "the .dmg lane never embeds"

    def test_the_store_archive_can_define_the_flag_but_only_on_request(self) -> None:
        """17 Nov: an evidence build can turn the adapter on (BN_BA_WHISPER=1), the default stays dark,
        and the .dmg lane has no way to."""
        text = _BUILD_ALL.read_text(encoding="utf-8")
        assert 'BN_BA_WHISPER:-0}" = "1"' in text, "off unless asked"
        assert "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) BA_WHISPER" in text
        assert text.count("BA_WHISPER'") == 1, "defined once, in the store archive's argument list"
        dmg = (_DESKTOP / "scripts" / "build-dmg.sh").read_text(encoding="utf-8")
        assert "BA_WHISPER" not in dmg

    def test_the_compile_flag_is_defined_nowhere_in_the_project(self) -> None:
        """Owner, 16 Nov 2026: BA_WHISPER stays undefined until a TestFlight build has shown the
        pack arrive. Then a one-line change in the store configuration turns the adapter on."""
        assert "BA_WHISPER" not in _text()


class TestTheLaneIsReadyForTheEmbed:
    """Dormant while the extension is not embedded; they bite the moment it is."""

    def _embedded(self) -> bool:
        return "BAExtension" in (
            self._SCHEMES_STORE.read_text(encoding="utf-8") if self._SCHEMES_STORE.is_file() else ""
        )

    _SCHEMES_STORE = (
        _DESKTOP / "Bristlenose" / "Bristlenose.xcodeproj" / "xcshareddata" / "xcschemes"
        / "Bristlenose Store.xcscheme"
    )

    def test_export_options_map_the_extension_s_profile_once_it_is_embedded(self) -> None:
        # Read as text: ExportOptions.plist carries a long XML comment that plistlib rejects.
        text = _EXPORT.read_text(encoding="utf-8")
        profiles = dict(re.findall(
            r"<key>(app\.bristlenose[\w.]*)</key>\s*<string>([^<]+)</string>", text))
        # The host's mapping must be intact whether or not the extension is embedded.
        assert "app.bristlenose" in profiles
        if not self._embedded():
            return
        assert _EXT_ID in profiles, "the store export would sign the extension with no profile"
        assert profiles[_EXT_ID] != profiles["app.bristlenose"], "its own profile, not the host's"

    def test_build_all_knows_the_extension_profile(self) -> None:
        text = _BUILD_ALL.read_text(encoding="utf-8")
        assert "EXT_PROFILE_PATH" in text and "project_embeds_extension" in text
        assert _EXT_ID in text
        # The detector must look at the scheme the store lane archives, or the guards never switch on.
        assert "Bristlenose Store.xcscheme" in text
        # ...and the extension's product must really be the extension's in the project.
        assert re.search(_PRODUCT_REF + r" /\* BAExtension.appex \*/ = \{isa = PBXFileReference", _text())

    def test_the_dmg_lane_never_passes_a_command_line_entitlements_file(self) -> None:
        build_dmg = (_DESKTOP / "scripts" / "build-dmg.sh").read_text(encoding="utf-8")
        live = [ln for ln in build_dmg.splitlines() if not ln.lstrip().startswith("#")]
        assert not [ln for ln in live if "CODE_SIGN_ENTITLEMENTS=" in ln], (
            "a command-line CODE_SIGN_ENTITLEMENTS reaches the extension target too"
        )
