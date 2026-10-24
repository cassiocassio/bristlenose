import Testing
import Foundation
@testable import Bristlenose

/// R50: a study added without a usable security-scoped bookmark looked fine,
/// then read "Can't be read" at the next launch.
///
/// `Project.availability` answers `.ready` from `fileExists`, which needs no
/// grant, and a row with no bookmark gets no lease. The add holds the grant
/// (a drop, an Open or Save panel), so the row works for the rest of that
/// session; the next launch has nothing to reopen the folder with.
///
/// The reachable way to mint nothing with a grant held is a path whose last
/// component is a symlink: `bookmarkData(.withSecurityScope)` refuses the
/// link and accepts the folder it names. The add now retries at the resolved
/// spelling and stores that spelling. This host can always read its container,
/// so the one-session grant itself is checked by hand, not here.
@MainActor
@Suite("R50 — a study's bookmark survives the add")
struct BookmarkMintTests {

    private func folder() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-r50-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// A study folder and a link to it, in a fresh folder.
    private func studyAndLink() throws -> (root: URL, study: URL, link: URL) {
        let root = try folder()
        let study = root.appendingPathComponent("Study")
        try FileManager.default.createDirectory(at: study, withIntermediateDirectories: true)
        let link = root.appendingPathComponent("Study link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: study)
        return (root, study, link)
    }

    private struct Refused: Error {}

    /// The same folder, allowing for `/private`. An unsandboxed host (CI builds
    /// the tests unsigned) has its temporary folder under `/var`, a bookmark
    /// resolves that to `/private/var`, and `resolvingSymlinksInPath` writes it
    /// without the prefix. A link's spelling is still told from the folder's.
    private func samePlace(_ a: String, _ b: String) -> Bool {
        a == b || a == "/private" + b || "/private" + a == b
    }

    /// The measured fact the fix stands on, in this sandboxed host: the link
    /// spelling mints nothing and the folder it names mints a bookmark.
    @Test func aLinkMintsNothingAndItsFolderMints() throws {
        let (root, _, link) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }

        #expect(throws: (any Error).self) {
            try URL(fileURLWithPath: link.path).bookmarkData(options: .withSecurityScope)
        }
        #expect(throws: Never.self) {
            try URL(fileURLWithPath: link.path).resolvingSymlinksInPath()
                .bookmarkData(options: .withSecurityScope)
        }
    }

    /// The bug, end to end at the model: a study added at a symlinked folder
    /// is `.ready` now and must still have a bookmark — and so a lease — when
    /// the index is loaded again, as it is at the next launch. The row names
    /// the folder from the add on, so nothing respells it later.
    @Test func aSymlinkedStudyCanBeReopenedNextLaunch() throws {
        let (root, study, link) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("projects.json")

        let added: Project
        do {
            let index = ProjectIndex(fileURL: file, watcherCap: 0)
            added = index.addProject(name: "Study", path: link.path)
            #expect(added.availability == .ready, "add time")
            #expect(added.bookmarkData != nil, "the add stored no bookmark")
            #expect(added.path == study.path, "the row keeps the link's spelling")
        }

        let nextLaunch = ProjectIndex(fileURL: file, watcherCap: 0)
        nextLaunch.refreshAvailability()
        let row = try #require(nextLaunch.projects.first { $0.id == added.id })
        #expect(row.availability == .ready)
        #expect(row.bookmarkData != nil, "next launch has nothing to reopen the folder with")
        #expect(nextLaunch.leaseURL(projectID: row.id) != nil, "next launch holds no lease")
        #expect(samePlace(row.path, study.path), "the row does not name the folder")
    }

    /// The same at a Locate or a drop onto an existing row: the row names the
    /// folder, with a bookmark.
    @Test func aRowLocatedAtALinkNamesTheFolder() throws {
        let (root, study, link) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }
        let first = root.appendingPathComponent("First")
        try FileManager.default.createDirectory(at: first, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"), watcherCap: 0)
        let added = index.addProject(name: "Study", path: first.path)
        index.relocateProject(id: added.id, newPath: link.path)
        let row = try #require(index.projects.first { $0.id == added.id })
        #expect(row.bookmarkData != nil, "the relocation stored no bookmark")
        #expect(row.path == study.path, "the row keeps the link's spelling")
    }

    // ── The decision, with the maker injected ───────────────────────────────

    @Test func theFirstSpellingIsKeptWhenItMints() {
        var asked: [String] = []
        let minted = ProjectIndex.mintBookmark(for: "/Users/r/Study") { url in
            asked.append(url.path)
            return Data([1])
        }
        #expect(minted == .init(data: Data([1]), path: "/Users/r/Study"))
        #expect(asked == ["/Users/r/Study"])
    }

    @Test func aRefusedLinkIsMintedAtTheFolderItNames() throws {
        let (root, study, link) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }

        var asked: [String] = []
        let minted = ProjectIndex.mintBookmark(for: link.path) { url in
            asked.append(url.path)
            guard url.path != link.path else { throw Refused() }
            return Data(url.path.utf8)
        }
        #expect(asked == [link.path, study.path])
        #expect(minted == .init(data: Data(study.path.utf8), path: study.path))
    }

    /// A link anywhere in the path, not only the last component.
    @Test func aLinkedAncestorIsResolvedToo() throws {
        let (root, study, _) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }
        let inner = study.appendingPathComponent("Round 2")
        try FileManager.default.createDirectory(at: inner, withIntermediateDirectories: true)
        let viaLink = root.appendingPathComponent("Study link/Round 2").path

        let minted = ProjectIndex.mintBookmark(for: viaLink) { url in
            guard url.path != viaLink else { throw Refused() }
            return Data()
        }
        #expect(minted?.path == inner.path)
    }

    /// `/private/tmp` resolves to `/tmp`: a refused `/private` spelling is
    /// asked again at the short one. Harmless, and stated so it is not a
    /// surprise.
    @Test func aRefusedPrivateSpellingIsAskedAgainAtTheShortOne() throws {
        let respelled = URL(fileURLWithPath: "/private/tmp").resolvingSymlinksInPath().path
        try #require(respelled != "/private/tmp")
        var asked: [String] = []
        let minted = ProjectIndex.mintBookmark(for: "/private/tmp") { url in
            asked.append(url.path)
            guard url.path != "/private/tmp" else { throw Refused() }
            return Data()
        }
        #expect(asked == ["/private/tmp", respelled])
        #expect(minted?.path == respelled)
    }

    /// No other spelling: one refusal is the answer, not a reason to ask
    /// again for the same path.
    @Test func aRefusedPlainFolderIsAskedOnce() throws {
        let root = try folder()
        defer { try? FileManager.default.removeItem(at: root) }
        var asked = 0
        let minted = ProjectIndex.mintBookmark(for: root.resolvingSymlinksInPath().path) { _ in
            asked += 1
            throw Refused()
        }
        #expect(minted == nil)
        #expect(asked == 1)
    }

    @Test func aLinkWhoseFolderIsRefusedTooMintsNothing() throws {
        let (root, _, link) = try studyAndLink()
        defer { try? FileManager.default.removeItem(at: root) }
        var asked = 0
        let minted = ProjectIndex.mintBookmark(for: link.path) { _ in
            asked += 1
            throw Refused()
        }
        #expect(minted == nil)
        #expect(asked == 2)
    }

    @Test func anEmptyPathAsksNothing() {
        var asked = 0
        let minted = ProjectIndex.mintBookmark(for: "") { _ in asked += 1; return Data() }
        #expect(minted == nil)
        #expect(asked == 0)
    }

    // ── A failed re-mint keeps a bookmark that still names the folder ───────

    /// A study whose folder was renamed, with a working bookmark minted at the
    /// old name, and an index whose next mint is refused.
    private func renamedStudy() throws -> (root: URL, index: ProjectIndex, id: UUID, old: Data, moved: URL) {
        let root = try folder()
        let original = root.appendingPathComponent("Study")
        try FileManager.default.createDirectory(at: original, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"), watcherCap: 0)
        let added = index.addProject(name: "Study", path: original.path)
        let old = try #require(added.bookmarkData, "precondition: the first mint works")
        let moved = root.appendingPathComponent("Study renamed")
        try FileManager.default.moveItem(at: original, to: moved)
        index.makeBookmark = { _ in throw Refused() }
        return (root, index, added.id, old, moved)
    }

    @Test func aLaunchThatFollowsTheFolderKeepsTheBookmarkThatResolved() throws {
        let (root, index, id, old, moved) = try renamedStudy()
        defer { try? FileManager.default.removeItem(at: root) }
        index.refreshAvailability()
        let row = try #require(index.projects.first { $0.id == id })
        #expect(samePlace(row.path, moved.path), "precondition: the bookmark followed the rename")
        #expect(row.bookmarkData == old, "a refused re-mint dropped a working bookmark")
    }

    @Test func aWatcherMoveKeepsTheBookmarkWhenTheReMintFails() throws {
        let (root, index, id, old, moved) = try renamedStudy()
        defer { try? FileManager.default.removeItem(at: root) }
        index.projectFolderDidMove(id: id, to: moved)
        let row = try #require(index.projects.first { $0.id == id })
        #expect(row.path == moved.path)
        #expect(row.bookmarkData == old, "a refused re-mint dropped a bookmark that follows the folder")
    }

    /// Locate points the row at another folder, which the old bookmark does
    /// not name: nil is the honest answer there.
    @Test func aLocateWhoseMintFailsKeepsNoBookmark() throws {
        let (root, index, id, _, _) = try renamedStudy()
        defer { try? FileManager.default.removeItem(at: root) }
        let elsewhere = root.appendingPathComponent("Another study")
        try FileManager.default.createDirectory(at: elsewhere, withIntermediateDirectories: true)
        index.relocateProject(id: id, newPath: elsewhere.path)
        let row = try #require(index.projects.first { $0.id == id })
        #expect(row.path == elsewhere.path)
        #expect(row.bookmarkData == nil, "a Locate kept a bookmark to the old folder")
    }
}
