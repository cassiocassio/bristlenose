import Foundation
import Testing
@testable import Bristlenose

/// Which MCP token a project gets, with the Keychain replaced by a dictionary.
/// Never the real Keychain: a test that writes there wrote a developer's
/// items on 4 Sep 2026 (`desktop/CLAUDE.md`).
@Suite("MCP token keyed by study")
struct MCPTokenStoreResolveTests {

    final class Box { var items: [String: String] = [:]; var minted = 0 }

    private func resolve(_ box: Box, path: String, study: String?) -> String? {
        MCPTokenStore.resolve(
            path: path, studyID: study,
            read: { box.items[$0] },
            write: { box.items[$0] = $1; return true },
            mint: { box.minted += 1; return "token-\(box.minted)" }
        )
    }

    @Test func aStudyKeepsItsTokenAcrossAMove() {
        let box = Box()
        let study = "6f1c2b9e-1111-4000-8000-000000000001"
        let before = resolve(box, path: "/Studies/Talismanic", study: study)
        let after = resolve(box, path: "/Archive/2026/Talismanic", study: study)
        #expect(before != nil && before == after)
    }

    @Test func aCopyGetsItsOwnToken() {
        let box = Box()
        let original = resolve(box, path: "/Studies/Talismanic", study: "6f1c2b9e-1111-4000-8000-000000000001")
        let copy = resolve(box, path: "/Studies/Talismanic copy", study: "6f1c2b9e-1111-4000-8000-000000000002")
        #expect(original != copy)
    }

    @Test func theFirstStudyKeyCarriesThePathTokenAndLeavesItInPlace() {
        let box = Box()
        let path = "/Studies/Talismanic"
        let pathToken = resolve(box, path: path, study: nil)
        let studyToken = resolve(box, path: path, study: "6f1c2b9e-1111-4000-8000-000000000001")
        #expect(studyToken == pathToken, "the upgrade broke an agent config pasted before it")
        #expect(box.items[MCPTokenStore.accountKey(for: path)] == pathToken, "the old item was removed")
        #expect(box.minted == 1)
    }

    @Test func theTwoAccountsNeverCollide() {
        let id = "6f1c2b9e-1111-4000-8000-000000000001"
        #expect(MCPTokenStore.studyAccountKey(id) != MCPTokenStore.accountKey(for: id))
    }
}
