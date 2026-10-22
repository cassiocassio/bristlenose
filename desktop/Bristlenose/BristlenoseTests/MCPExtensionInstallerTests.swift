import Foundation
import Testing
@testable import Bristlenose

/// Install for Claude Desktop says when it opened nothing (decision #42,
/// 22 Oct 2026). `install()` used to return nothing, so the button whose
/// every route failed — no package built, nothing to open it — left the
/// researcher with no sign it had been pressed. The row now shows
/// `desktop.mcpAgents.installFailed` when `install()` answers false.
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
}
