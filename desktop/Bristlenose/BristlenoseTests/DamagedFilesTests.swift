import Foundation
import Testing
@testable import Bristlenose

/// A damaged file is named for what it is and never strands the researcher
/// (RE#17, owner rulings 22 Oct 2026, decisions #18 and #19).
///
/// A truncated manifest read as "Can't be read" (the folder-grant state, with
/// Locate…) and the row offered no way to run at all; a `projects.json` that
/// would not decode was set aside and the next launch was an empty Welcome
/// screen with nothing said.
@MainActor
@Suite("Damaged files")
struct DamagedFilesTests {

    // MARK: - Manifest: damaged, not unreadable

    private func project(manifest: Data?) throws -> (root: URL, manifest: URL) {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-damaged-\(UUID().uuidString)", isDirectory: true)
        let dot = root
            .appendingPathComponent("bristlenose-output", isDirectory: true)
            .appendingPathComponent(".bristlenose", isDirectory: true)
        try FileManager.default.createDirectory(at: dot, withIntermediateDirectories: true)
        let url = dot.appendingPathComponent("pipeline-manifest.json")
        if let manifest { try manifest.write(to: url) }
        return (root, url)
    }

    @Test(arguments: [
        "{\"schema_version\": 1, \"project_name\": \"x\", \"stag",  // truncated mid-write
        "",                                                          // zero bytes
        "{\"schema_version\": 1}",                                   // parses, no stages
    ])
    func aManifestThatWillNotParseIsDamaged(_ text: String) async throws {
        let p = try project(manifest: Data(text.utf8))
        defer { try? FileManager.default.removeItem(at: p.root) }

        let state = await PipelineRunner.parseManifest(at: p.manifest)

        #expect(state == .unreachable(reason: .damaged),
                "expected Project file damaged, got \(state)")
        // Not the folder-grant state: no Locate… for a folder that is fine.
        #expect(!state.needsFolderAccess)
    }

    // MARK: - Analyse is offered on a damaged project, Re-analyse is not

    private let data = UnanalysedState(
        newFiles: [], missingFiles: [], sessionCount: 14, totalDurationSeconds: nil,
        ingestableFileCount: 14
    )

    @Test func aDamagedProjectOffersAnalyse() {
        #expect(SidebarOutlineController.analyseIsOffered(
            hasPath: true, isAvailable: true,
            state: .unreachable(reason: .damaged), data: data))
    }

    @Test func aDamagedProjectDoesNotOfferReAnalyse() {
        // Re-analyse is `--clean`: it would discard the researcher's edits.
        #expect(!SidebarOutlineController.reAnalyseIsOffered(
            hasPath: true, isAvailable: true,
            state: .unreachable(reason: .damaged), data: data))
    }

    @Test func theOtherUnreachableStatesStillOfferNothing() {
        for reason in UnreachableReason.allCases where reason != .damaged {
            #expect(!SidebarOutlineController.analyseIsOffered(
                hasPath: true, isAvailable: true,
                state: .unreachable(reason: reason), data: data),
                "\(reason) must not offer Analyse")
        }
    }

    @Test func aDamagedProjectWhoseFolderIsGoneOffersNothing() {
        #expect(!SidebarOutlineController.analyseIsOffered(
            hasPath: true, isAvailable: false,
            state: .unreachable(reason: .damaged), data: data))
    }

    // MARK: - projects.json: set aside, and said

    private func index(with contents: Data, lockDirectory: Bool = false) throws -> (ProjectIndex, URL) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-index-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("projects.json")
        try contents.write(to: file)
        if lockDirectory {
            try FileManager.default.setAttributes([.posixPermissions: 0o555], ofItemAtPath: dir.path)
        }
        return (ProjectIndex(fileURL: file), dir)
    }

    private func cleanUp(_ dir: URL) {
        try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: dir.path)
        try? FileManager.default.removeItem(at: dir)
    }

    @Test func aDamagedListIsSaidOnce() throws {
        let (index, dir) = try index(with: Data("{\"version\":\"1.0\",\"projects\":[{\"id\"".utf8))
        defer { cleanUp(dir) }
        #expect(index.listWasSetAside)
        let names = try FileManager.default.contentsOfDirectory(atPath: dir.path)
        #expect(names.contains { $0.hasPrefix("projects.json.damaged-") }, "\(names)")
        // Said once: the first window claims it, a second restored window doesn't.
        #expect(index.claimListSetAsideNotice())
        #expect(!index.claimListSetAsideNotice())
    }

    @Test func aListThatCouldNotBeSetAsideIsSaidToo() throws {
        // The edge the owner accepted: saves are refused, the alert still shows.
        let (index, dir) = try index(with: Data("not json".utf8), lockDirectory: true)
        defer { cleanUp(dir) }
        #expect(index.listWasSetAside)
        // Proves the refused branch ran, not the ordinary set-aside.
        let names = try FileManager.default.contentsOfDirectory(atPath: dir.path)
        #expect(names == ["projects.json"], "\(names)")
    }

    @Test func aReadableListSaysNothing() throws {
        let (index, dir) = try index(with: Data("{\"version\":\"1.0\",\"folders\":[],\"projects\":[]}".utf8))
        defer { cleanUp(dir) }
        #expect(!index.listWasSetAside)
        #expect(!index.claimListSetAsideNotice())
    }
}
