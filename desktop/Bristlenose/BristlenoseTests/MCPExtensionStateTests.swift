import Foundation
import Testing

@testable import Bristlenose

/// The pane's one job is to be right about builds, so every claim it makes has
/// to be derived. These pin what may be said, not how it is worded — the key
/// chosen, never the rendered string (a bare `I18n()` returns the raw key, so
/// a text assertion here would silently be an assertion about the identifier).
@Suite("MCPExtensionState")
struct MCPExtensionStateTests {

    // MARK: - Nothing is knowable

    @Test("nothing has called yet is unknown, not up-to-date")
    func nilRunningIsUnknown() {
        #expect(MCPExtensionState.compare(bundled: "0.26.0+abc1234", running: nil) == .unknown)
    }

    @Test("no bundled extension is unknown, not a mismatch")
    func nilBundledIsUnknown() {
        #expect(MCPExtensionState.compare(bundled: nil, running: "0.26.0+abc1234") == .unknown)
    }

    @Test("empty strings do not masquerade as versions")
    func emptyIsUnknown() {
        #expect(MCPExtensionState.compare(bundled: "", running: "0.26.0+abc") == .unknown)
        #expect(MCPExtensionState.compare(bundled: "0.26.0+abc", running: "") == .unknown)
    }

    // MARK: - The comparison

    @Test("identical stamps match, and say nothing")
    func identicalMatches() {
        let s = MCPExtensionState.compare(bundled: "0.26.0+abc1234", running: "0.26.0+abc1234")
        #expect(s == .matching)
        #expect(s.footnoteKey == nil)
        #expect(s.buttonKey == "desktop.mcpAgents.install")
    }

    @Test("same release, different hash is 'different' and never 'older'")
    func sameReleaseDifferentHash() {
        // Content hashes have no ordering. This is the case that cost six
        // reinstall cycles, and the case where a confident direction would be
        // the app guessing.
        let s = MCPExtensionState.compare(bundled: "0.26.0+aaaaaaa", running: "0.26.0+bbbbbbb")
        #expect(s == .differentBuild(installed: "0.26.0 (bbbbbbb)"))
        #expect(s.footnoteKey == "desktop.mcpAgents.installedDifferentBuild")
        #expect(s.buttonKey == "desktop.mcpAgents.reinstall")
    }

    @Test("an older installed release orders, and offers Update")
    func olderRelease() {
        let s = MCPExtensionState.compare(bundled: "0.26.0+aaaaaaa", running: "0.25.3+bbbbbbb")
        #expect(s == .olderRelease(installed: "0.25.3 (bbbbbbb)"))
        #expect(s.footnoteKey == "desktop.mcpAgents.installedOlder")
        #expect(s.buttonKey == "desktop.mcpAgents.update")
    }

    @Test("a newer installed release is not reported as older")
    func newerRelease() {
        // Downgrade the app, or pack-install-then-checkout-an-older-branch.
        // Rare, but "older" is the common direction, not a safe default.
        let s = MCPExtensionState.compare(bundled: "0.25.3+aaaaaaa", running: "0.26.0+bbbbbbb")
        #expect(s == .newerRelease(installed: "0.26.0 (bbbbbbb)"))
        #expect(s.footnoteKey == "desktop.mcpAgents.installedNewer")
    }

    @Test("a missing hash on either side degrades to silence, not a false alarm")
    func sameReleaseWithoutHashIsUnknown() {
        // The stamp file is absent (older bundle), so bundled is release-only.
        // Two same-release stamps we cannot actually compare must not be
        // announced as a difference.
        #expect(MCPExtensionState.compare(bundled: "0.26.0", running: "0.26.0+bbbbbbb") == .unknown)
        #expect(MCPExtensionState.compare(bundled: "0.26.0+aaaaaaa", running: "0.26.0") == .unknown)
    }

    @Test("a release difference is still reported without hashes")
    func releaseDifferenceSurvivesMissingHash() {
        #expect(MCPExtensionState.compare(bundled: "0.26.0", running: "0.25.3")
                == .olderRelease(installed: "0.25.3"))
    }

    // MARK: - Ordering

    @Test("releases order numerically, not lexicographically")
    func numericOrdering() {
        // The bug this forbids: "0.9.0" > "0.26.0" as strings, which would
        // invert the single directional claim this type is allowed to make.
        #expect(MCPExtensionState.compareReleases("0.9.0", "0.26.0") == .orderedAscending)
        #expect(MCPExtensionState.compareReleases("0.26.0", "0.9.0") == .orderedDescending)
        #expect(MCPExtensionState.compareReleases("0.26.0", "0.26.0") == .orderedSame)
    }

    @Test("differing component counts compare as if zero-padded")
    func shortReleases() {
        #expect(MCPExtensionState.compareReleases("1.0", "1.0.0") == .orderedSame)
        #expect(MCPExtensionState.compareReleases("1.0", "1.0.1") == .orderedAscending)
    }

    @Test("a non-numeric release is incomparable, so no direction is claimed")
    func nonNumericIsIncomparable() {
        #expect(MCPExtensionState.compareReleases("0.26.0-rc1", "0.26.0") == .orderedSame)
        let s = MCPExtensionState.compare(bundled: "0.26.0+aaaaaaa", running: "beta+bbbbbbb")
        #expect(s == .differentBuild(installed: "beta (bbbbbbb)"))
    }

    // MARK: - Rendering

    @Test("the wire form renders in Apple's version-and-build convention")
    func displayForm() {
        // `0.26.0+854270a` is package-manifest syntax; every first-party About
        // panel writes `Version 26.3 (17C52)`.
        #expect(MCPExtensionState.display("0.26.0+854270a") == "0.26.0 (854270a)")
    }

    @Test("a stamp with no hash renders unchanged rather than gaining empty parens")
    func displayWithoutHash() {
        #expect(MCPExtensionState.display("0.26.0") == "0.26.0")
        #expect(MCPExtensionState.display("0.26.0+") == "0.26.0+")
    }

    @Test("identity mirrors display, and is absent when nothing is bundled")
    func identity() {
        #expect(MCPExtensionState.identity(bundled: "0.26.0+854270a") == "0.26.0 (854270a)")
        #expect(MCPExtensionState.identity(bundled: nil) == nil)
        #expect(MCPExtensionState.identity(bundled: "") == nil)
    }

    // MARK: - The states carry no version where they claim none

    @Test("only the differing states name an installed version")
    func installedDisplayIsScoped() {
        #expect(MCPExtensionState.unknown.installedDisplay == nil)
        #expect(MCPExtensionState.matching.installedDisplay == nil)
        #expect(MCPExtensionState.olderRelease(installed: "0.25.3").installedDisplay == "0.25.3")
    }
}
