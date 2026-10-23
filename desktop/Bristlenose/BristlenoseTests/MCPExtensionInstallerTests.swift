import Foundation
import Testing
@testable import Bristlenose

/// Install for Claude Desktop says when it opened nothing (decision #42,
/// 22 Oct 2026). `install()` used to return nothing, so the button whose
/// every route failed — no package built, nothing to open it — left the
/// researcher with no sign it had been pressed. The row now shows
/// `desktop.mcpAgents.installFailed` when `installOutcome()` is `.nothing`,
/// and the Node extension's notes when it fell back to the Node extension (R42).
///
/// Whatever this bundle carries (the native helper, the Node `.mcpb`, both or
/// neither), "succeeded" must mean "something was opened": the opener is the
/// one fact these tests control. The container is a temp folder, so nothing
/// lands in the real Application Support.
@MainActor
@Suite struct MCPExtensionInstallerTests {

    private func tempContainer() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-mcp-install-\(UUID().uuidString)")
    }

    @Test func anInstallThatOpensNothingSaysSo() {
        let container = tempContainer()
        defer { try? FileManager.default.removeItem(at: container) }
        var asked: [URL] = []
        let opened = MCPExtensionInstaller.install(container: container) { url in
            asked.append(url)
            return false
        }
        #expect(opened == false, "an install nothing opened reported success (asked to open \(asked.count))")
    }

    @Test func anInstallThatOpensSomethingSucceeds() {
        let container = tempContainer()
        defer { try? FileManager.default.removeItem(at: container) }
        var asked: [URL] = []
        let opened = MCPExtensionInstaller.install(container: container) { url in
            asked.append(url)
            return true
        }
        // True exactly when the opener was asked: a bundle with nothing to
        // install has nothing to open, and says so.
        #expect(opened == !asked.isEmpty)
        if MCPExtensionInstaller.bundledExtensionExists {
            #expect(opened, "the bundled Node extension was there to open")
        }
    }

    @Test func noContainerOpensNothingAndSaysSo() {
        var asked = 0
        let opened = MCPExtensionInstaller.install(container: nil) { _ in
            asked += 1
            return true
        }
        #expect(opened == false)
        #expect(asked == 0)
    }

    // MARK: - Which extension Claude received (R42)

    /// A readable file standing in for the signed helper: the package only
    /// zips its bytes.
    private func fakeFile(in dir: URL, named name: String) -> URL {
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent(name)
        FileManager.default.createFile(atPath: url.path, contents: Data("stand-in".utf8))
        return url
    }

    @Test func aNativeInstallThatOpensSaysNative() {
        let container = tempContainer()
        let parts = tempContainer()
        defer {
            try? FileManager.default.removeItem(at: container)
            try? FileManager.default.removeItem(at: parts)
        }
        var asked: [URL] = []
        let outcome = MCPExtensionInstaller.installOutcome(
            container: container,
            open: { asked.append($0); return true },
            helper: fakeFile(in: parts, named: "bristlenose-mcp"),
            bundled: fakeFile(in: parts, named: "Bristlenose.mcpb"))
        #expect(outcome == .native)
        let dest = container.appendingPathComponent(MCPExtensionInstaller.filename)
        #expect(asked == [dest])
        // The package is a zip built around the helper, not a copy of either file.
        #expect((try? Data(contentsOf: dest))?.prefix(2) == Data("PK".utf8))
    }

    /// The silent half of R42: the native package fails, the Node extension
    /// opens in its place, and the row has to know it was the Node one.
    @Test func aNativeFailureThatFallsBackSaysNodeExtension() {
        let container = tempContainer()
        let parts = tempContainer()
        defer {
            try? FileManager.default.removeItem(at: container)
            try? FileManager.default.removeItem(at: parts)
        }
        let outcome = MCPExtensionInstaller.installOutcome(
            container: container,
            open: { _ in true },
            helper: parts.appendingPathComponent("no-such-helper"),
            bundled: fakeFile(in: parts, named: "Bristlenose.mcpb"))
        #expect(outcome == .nodeExtension)
    }

    /// A native package from an earlier Install sits at the same path and is
    /// always newer than the bundled Node copy. The fall-back must replace it,
    /// or it re-opens last time's native package and calls it the Node one.
    @Test func aFallBackReplacesAnEarlierNativePackage() {
        let container = tempContainer()
        let parts = tempContainer()
        defer {
            try? FileManager.default.removeItem(at: container)
            try? FileManager.default.removeItem(at: parts)
        }
        let node = fakeFile(in: parts, named: "Bristlenose.mcpb")
        try? FileManager.default.createDirectory(at: container, withIntermediateDirectories: true)
        let dest = container.appendingPathComponent(MCPExtensionInstaller.filename)
        FileManager.default.createFile(atPath: dest.path, contents: Data("an earlier native package".utf8))

        var opened: Data?
        let outcome = MCPExtensionInstaller.installOutcome(
            container: container,
            open: { opened = try? Data(contentsOf: $0); return true },
            helper: parts.appendingPathComponent("no-such-helper"),
            bundled: node)
        #expect(outcome == .nodeExtension)
        #expect(opened == (try? Data(contentsOf: node)))
    }

    /// No Node extension in the bundle: nothing to fall back to, and nothing
    /// is asked to open a file that isn't there.
    @Test func aNativeFailureWithNoNodeExtensionOpensNothing() {
        let container = tempContainer()
        let parts = tempContainer()
        defer {
            try? FileManager.default.removeItem(at: container)
            try? FileManager.default.removeItem(at: parts)
        }
        var asked = 0
        let outcome = MCPExtensionInstaller.installOutcome(
            container: container,
            open: { _ in asked += 1; return true },
            helper: parts.appendingPathComponent("no-such-helper"),
            bundled: parts.appendingPathComponent("Bristlenose.mcpb"))
        #expect(outcome == .nothing)
        #expect(asked == 0)
    }

    @Test func aNodeOnlyBuildThatOpensNothingSaysNothing() {
        let container = tempContainer()
        let parts = tempContainer()
        defer {
            try? FileManager.default.removeItem(at: container)
            try? FileManager.default.removeItem(at: parts)
        }
        let outcome = MCPExtensionInstaller.installOutcome(
            container: container,
            open: { _ in false },
            helper: nil,
            bundled: fakeFile(in: parts, named: "Bristlenose.mcpb"))
        #expect(outcome == .nothing)
    }

    @Test(arguments: [
        (false, nil, true),
        (true, nil, false),
        (true, MCPExtensionInstaller.Outcome.native, false),
        (true, MCPExtensionInstaller.Outcome.nodeExtension, true),
        (false, MCPExtensionInstaller.Outcome.native, true),
    ] as [(Bool, MCPExtensionInstaller.Outcome?, Bool)])
    func theNodeNotesFollowWhatClaudeReceived(
        usesNativeHelper: Bool, lastOpened: MCPExtensionInstaller.Outcome?, expected: Bool
    ) {
        #expect(MCPExtensionInstaller.nodeNotesApply(
            usesNativeHelper: usesNativeHelper, lastOpened: lastOpened) == expected)
    }
}
