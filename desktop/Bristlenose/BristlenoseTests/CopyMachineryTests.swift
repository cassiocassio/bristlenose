import Foundation
import Testing

@testable import Bristlenose

/// Regression pins for `CopyMachinery`'s pure helpers. These functions sit at
/// an irreversible data boundary — a regression here either silently
/// overwrites a researcher's recording (`resolveDestinations`) or silently
/// flattens their folder organisation (`planItems`). Both are functions
/// the cohort QA can't reliably catch by eye.
///
/// Tests target the `nonisolated static` helpers; no actor isolation needed.
/// Temp dirs follow `EventLogReaderTests` style.
struct CopyMachineryTests {

    // MARK: - Helpers

    private func makeTempDir() -> URL {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("copy-machinery-tests-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func touch(_ url: URL) {
        try? Data().write(to: url, options: .atomic)
    }

    /// A real regular file with real content. `touch` writes zero bytes, and a
    /// zero-byte file is byte-identical to every other zero-byte file — so the
    /// identity tests below must not use it as a stand-in for "some recording".
    private func write(_ url: URL, _ content: String) {
        try? Data(content.utf8).write(to: url, options: .atomic)
    }

    /// A source that is a genuine regular file on disk, so `holdsSameContent`
    /// actually runs. `/dev/null` is a character device: `isPlainFile` refuses
    /// it, which would make an identity test pass for the wrong reason.
    private func source(_ dir: URL, _ name: String, _ content: String) -> URL {
        let url = dir.appendingPathComponent(name)
        write(url, content)
        return url
    }

    // MARK: - appendCount — Finder-style "name 2.ext" rename

    @Test("appendCount: simple extension")
    func appendCountSimpleExtension() {
        #expect(CopyMachinery.appendCount(to: "clip.mov", n: 2) == "clip 2.mov")
        #expect(CopyMachinery.appendCount(to: "clip.mov", n: 17) == "clip 17.mov")
    }

    @Test("appendCount: no extension")
    func appendCountNoExtension() {
        #expect(CopyMachinery.appendCount(to: "clip", n: 2) == "clip 2")
        #expect(CopyMachinery.appendCount(to: "README", n: 3) == "README 3")
    }

    @Test("appendCount: multi-dot — only last segment is extension")
    func appendCountMultiDot() {
        // Finder treats "name.tar" as the stem of "name.tar.gz".
        #expect(CopyMachinery.appendCount(to: "name.tar.gz", n: 3) == "name.tar 3.gz")
    }

    // MARK: - resolveDestinations — never overwrites, never duplicates

    @Test("resolveDestinations: no collision keeps original leaf")
    func resolveDestinations_noCollision() {
        let tmp = makeTempDir()
        let item = CopyMachinery.PlannedItem(
            source: URL(fileURLWithPath: "/dev/null"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved.count == 1)
        #expect(resolved[0].copiedDestination?.lastPathComponent == "clip.mov")
    }

    @Test("resolveDestinations: renames when leaf collides with DIFFERENT content")
    func resolveDestinations_onDiskCollision() {
        let tmp = makeTempDir()
        let src = makeTempDir()
        write(tmp.appendingPathComponent("clip.mov"), "participant one")

        let item = CopyMachinery.PlannedItem(
            source: source(src, "clip.mov", "participant two"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].copiedDestination?.lastPathComponent == "clip 2.mov")
    }

    @Test("resolveDestinations: triple collision walks 2 → 3 when all differ")
    func resolveDestinations_tripleCollision() {
        let tmp = makeTempDir()
        let src = makeTempDir()
        write(tmp.appendingPathComponent("clip.mov"), "participant one")
        write(tmp.appendingPathComponent("clip 2.mov"), "participant two")

        let item = CopyMachinery.PlannedItem(
            source: source(src, "clip.mov", "participant three"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].copiedDestination?.lastPathComponent == "clip 3.mov")
    }

    @Test("resolveDestinations: same size, different bytes still renames")
    func resolveDestinations_sameSizeDifferentBytes() {
        // The false-positive guard. Two AppleDouble sidecars on an ExFAT card
        // measure *exactly* 4096 bytes each, so equal length is ordinary and
        // must never be mistaken for equal content.
        let tmp = makeTempDir()
        let src = makeTempDir()
        write(tmp.appendingPathComponent("clip.mov"), "AAAAAAAA")

        let item = CopyMachinery.PlannedItem(
            source: source(src, "clip.mov", "BBBBBBBB"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].copiedDestination?.lastPathComponent == "clip 2.mov")
    }

    // MARK: - resolveDestinations — the re-drop this file exists for

    @Test("resolveDestinations: byte-identical file already held is skipped")
    func resolveDestinations_identicalContentSkips() {
        let tmp = makeTempDir()
        let src = makeTempDir()
        let existing = tmp.appendingPathComponent("clip.mov")
        write(existing, "the interview")

        let item = CopyMachinery.PlannedItem(
            source: source(src, "clip.mov", "the interview"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved.count == 1)
        #expect(resolved[0].isSkip)
        #expect(resolved[0].skippedExisting?.standardizedFileURL == existing.standardizedFileURL)
    }

    @Test("resolveDestinations: identity is checked along the WHOLE collision chain")
    func resolveDestinations_identicalFurtherAlongChain() {
        // The state the reported corpus is already in: one earlier re-drop left
        // `clip.mov` and `clip 2.mov` side by side. A third drop must recognise
        // the copy at position 2 rather than mint `clip 3.mov`.
        let tmp = makeTempDir()
        let src = makeTempDir()
        write(tmp.appendingPathComponent("clip.mov"), "someone else")
        let twin = tmp.appendingPathComponent("clip 2.mov")
        write(twin, "the interview")

        let item = CopyMachinery.PlannedItem(
            source: source(src, "clip.mov", "the interview"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].isSkip)
        #expect(resolved[0].skippedExisting?.lastPathComponent == "clip 2.mov")
    }

    @Test("resolveDestinations: a skip never names an existing file as a destination")
    func resolveDestinations_skipNeverTargetsTheExistingFile() {
        // The safety property behind the whole change. `copy` appends a
        // destination to `written` only after a successful `copyItem`, and
        // `rollback` DELETES everything in `written` — so if a resolution ever
        // named an already-held file as a destination, cancelling a drop would
        // delete the researcher's recording. Asserted structurally: no `.copy`
        // may point at a path that already exists on disk.
        let tmp = makeTempDir()
        let src = makeTempDir()
        write(tmp.appendingPathComponent("clip.mov"), "the interview")
        write(tmp.appendingPathComponent("other.mov"), "another one")

        let items = [
            CopyMachinery.PlannedItem(
                source: source(src, "clip.mov", "the interview"),
                relativeComponents: ["clip.mov"]
            ),
            CopyMachinery.PlannedItem(
                source: source(src, "other.mov", "changed since"),
                relativeComponents: ["other.mov"]
            ),
        ]
        let resolved = CopyMachinery.resolveDestinations(items: items, root: tmp)
        for resolution in resolved {
            if let destination = resolution.copiedDestination {
                #expect(!FileManager.default.fileExists(atPath: destination.path))
            }
        }
    }

    @Test("resolveDestinations: two empty files ARE identical, so the second is skipped")
    func resolveDestinations_zeroByteIsIdentity() {
        let tmp = makeTempDir()
        let src = makeTempDir()
        touch(tmp.appendingPathComponent("clip.mov"))
        let empty = src.appendingPathComponent("clip.mov")
        touch(empty)

        let item = CopyMachinery.PlannedItem(
            source: empty, relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].isSkip)
    }

    // MARK: - holdsSameContent — every uncertainty must answer "not identical"

    @Test("holdsSameContent: identical bytes")
    func holdsSameContent_identical() {
        let tmp = makeTempDir()
        write(tmp.appendingPathComponent("a"), "same")
        write(tmp.appendingPathComponent("b"), "same")
        #expect(CopyMachinery.holdsSameContent(
            as: tmp.appendingPathComponent("a"),
            candidate: tmp.appendingPathComponent("b")
        ))
    }

    @Test("holdsSameContent: TWO unreadable files are not identical")
    func holdsSameContent_bothUnreadableIsNotIdentity() {
        // The trap this guards: `(try? hash(a)) == (try? hash(b))` is
        // `nil == nil` -> true when BOTH files fail to open, which would
        // declare two recordings we cannot read the same and drop one.
        let tmp = makeTempDir()
        let a = tmp.appendingPathComponent("a")
        let b = tmp.appendingPathComponent("b")
        write(a, "AAAA")
        write(b, "BBBB")
        try? FileManager.default.setAttributes(
            [.posixPermissions: 0], ofItemAtPath: a.path)
        try? FileManager.default.setAttributes(
            [.posixPermissions: 0], ofItemAtPath: b.path)
        defer {
            try? FileManager.default.setAttributes(
                [.posixPermissions: 0o644], ofItemAtPath: a.path)
            try? FileManager.default.setAttributes(
                [.posixPermissions: 0o644], ofItemAtPath: b.path)
        }
        // Equal length, both unopenable. Only an explicit non-nil check saves us.
        #expect(!CopyMachinery.holdsSameContent(as: a, candidate: b))
    }

    @Test("holdsSameContent: a symlink is never an identity match")
    func holdsSameContent_symlinkIsNotIdentity() {
        // `copyItem` copies the link, not the bytes (measured), so the link's
        // content identity is not the question being asked.
        let tmp = makeTempDir()
        let real = tmp.appendingPathComponent("real")
        write(real, "the interview")
        let link = tmp.appendingPathComponent("link")
        try? FileManager.default.createSymbolicLink(at: link, withDestinationURL: real)
        #expect(!CopyMachinery.holdsSameContent(as: link, candidate: real))
        #expect(!CopyMachinery.holdsSameContent(as: real, candidate: link))
    }

    @Test("holdsSameContent: a directory at the leaf is never an identity match")
    func holdsSameContent_directoryIsNotIdentity() {
        let tmp = makeTempDir()
        let file = tmp.appendingPathComponent("a")
        write(file, "x")
        let dir = tmp.appendingPathComponent("d", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        #expect(!CopyMachinery.holdsSameContent(as: file, candidate: dir))
    }

    @Test("holdsSameContent: an absent file is never an identity match")
    func holdsSameContent_absentIsNotIdentity() {
        let tmp = makeTempDir()
        let file = tmp.appendingPathComponent("a")
        write(file, "x")
        #expect(!CopyMachinery.holdsSameContent(
            as: file, candidate: tmp.appendingPathComponent("nope")))
        #expect(!CopyMachinery.holdsSameContent(
            as: tmp.appendingPathComponent("nope"), candidate: file))
    }

    @Test("sha256: unreadable file yields nil, not a digest of nothing")
    func sha256_unreadableIsNil() {
        let tmp = makeTempDir()
        let a = tmp.appendingPathComponent("a")
        write(a, "content")
        #expect(CopyMachinery.sha256(of: a) != nil)
        try? FileManager.default.setAttributes(
            [.posixPermissions: 0], ofItemAtPath: a.path)
        defer {
            try? FileManager.default.setAttributes(
                [.posixPermissions: 0o644], ofItemAtPath: a.path)
        }
        #expect(CopyMachinery.sha256(of: a) == nil)
        #expect(CopyMachinery.sha256(of: tmp.appendingPathComponent("absent")) == nil)
    }

    @Test("resolveDestinations: within-batch collision — second item renamed")
    func resolveDestinations_withinBatchCollision() {
        let tmp = makeTempDir()
        let src1 = URL(fileURLWithPath: "/dev/null")
        let src2 = URL(fileURLWithPath: "/dev/zero")

        let items = [
            CopyMachinery.PlannedItem(source: src1, relativeComponents: ["clip.mov"]),
            CopyMachinery.PlannedItem(source: src2, relativeComponents: ["clip.mov"]),
        ]
        let resolved = CopyMachinery.resolveDestinations(items: items, root: tmp)
        #expect(resolved.count == 2)
        #expect(resolved[0].copiedDestination?.lastPathComponent == "clip.mov")
        // Deliberately a rename, not a skip: nothing is on disk yet when the
        // second item resolves, so within-batch duplicates are a known
        // remaining case rather than something this change addresses.
        #expect(resolved[1].copiedDestination?.lastPathComponent == "clip 2.mov")
    }

    @Test("resolveDestinations: nested relativeComponents land in subdir")
    func resolveDestinations_nestedPath() {
        let tmp = makeTempDir()
        let item = CopyMachinery.PlannedItem(
            source: URL(fileURLWithPath: "/dev/null"),
            relativeComponents: ["march-batch", "p1", "clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        let expected = tmp
            .appendingPathComponent("march-batch", isDirectory: true)
            .appendingPathComponent("p1", isDirectory: true)
            .appendingPathComponent("clip.mov")
        #expect(resolved[0].copiedDestination?.standardizedFileURL == expected.standardizedFileURL)
    }

    // MARK: - planItems — folder-name preservation

    @Test("planItems: loose file drop lands at root with no parent")
    func planItems_looseFile() {
        let tmp = makeTempDir()
        let file = tmp.appendingPathComponent("clip.mov")
        touch(file)

        let plan = CopyMachinery.planItems(urls: [file], acceptedExtensions: ["mov"])
        #expect(plan.count == 1)
        #expect(plan[0].relativeComponents == ["clip.mov"])
    }

    @Test("planItems: dropped folder's name is preserved as parent dir")
    func planItems_folderPreservesName() {
        let tmp = makeTempDir()
        let folder = tmp.appendingPathComponent("march-batch", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
        touch(folder.appendingPathComponent("clip.mov"))

        let plan = CopyMachinery.planItems(urls: [folder], acceptedExtensions: ["mov"])
        #expect(plan.count == 1)
        #expect(plan[0].relativeComponents == ["march-batch", "clip.mov"])
    }

    @Test("planItems: dropped folder with nested structure preserves both levels")
    func planItems_folderPreservesNestedStructure() {
        let tmp = makeTempDir()
        let folder = tmp.appendingPathComponent("march-batch", isDirectory: true)
        let subdir = folder.appendingPathComponent("p1", isDirectory: true)
        try? FileManager.default.createDirectory(at: subdir, withIntermediateDirectories: true)
        touch(subdir.appendingPathComponent("clip.mov"))

        let plan = CopyMachinery.planItems(urls: [folder], acceptedExtensions: ["mov"])
        #expect(plan.count == 1)
        #expect(plan[0].relativeComponents == ["march-batch", "p1", "clip.mov"])
    }

    @Test("planItems: files outside the extension allowlist are skipped")
    func planItems_filterByExtension() {
        let tmp = makeTempDir()
        let folder = tmp.appendingPathComponent("batch", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
        touch(folder.appendingPathComponent("clip.mov"))
        touch(folder.appendingPathComponent("notes.txt"))
        touch(folder.appendingPathComponent("cover.png"))

        let plan = CopyMachinery.planItems(urls: [folder], acceptedExtensions: ["mov"])
        let leaves = plan.map { $0.relativeComponents.last }
        #expect(leaves == ["clip.mov"])
    }

    @Test("planItems: empty folder yields zero items")
    func planItems_emptyFolder() {
        let tmp = makeTempDir()
        let folder = tmp.appendingPathComponent("empty", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)

        let plan = CopyMachinery.planItems(urls: [folder], acceptedExtensions: ["mov"])
        #expect(plan.isEmpty)
    }

    @Test("planItems: mixed drop (loose file + folder) preserves folder name on the folder branch only")
    func planItems_mixedDrop() {
        let tmp = makeTempDir()
        let loose = tmp.appendingPathComponent("standalone.mov")
        touch(loose)
        let folder = tmp.appendingPathComponent("batch", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
        touch(folder.appendingPathComponent("inner.mov"))

        let plan = CopyMachinery.planItems(urls: [loose, folder], acceptedExtensions: ["mov"])
        let pairs = plan.map { $0.relativeComponents }.sorted { $0.count < $1.count }
        #expect(pairs[0] == ["standalone.mov"])
        #expect(pairs[1] == ["batch", "inner.mov"])
    }

    // MARK: - sourcesShareVolume — sanity check on the comparison shape

    @Test("sourcesShareVolume: identical URLs share volume")
    func sourcesShareVolume_sameURL() {
        let tmp = makeTempDir()
        #expect(CopyMachinery.sourcesShareVolume(with: tmp, sources: [tmp]) == true)
    }

    @Test("sourcesShareVolume: same-volume siblings share volume")
    func sourcesShareVolume_sameVolumeSiblings() {
        let a = URL(fileURLWithPath: NSTemporaryDirectory())
        let b = URL(fileURLWithPath: NSHomeDirectory())
        // Both live on the boot volume on every macOS install we ship to.
        #expect(CopyMachinery.sourcesShareVolume(with: a, sources: [b]) == true)
    }
}

/// Test-local readers for `CopyMachinery.Resolution`. Kept out of the production
/// type so the shipping surface stays the two cases the copier actually
/// switches on.
extension CopyMachinery.Resolution {
    var copiedDestination: URL? {
        if case .copy(let item) = self { return item.destination }
        return nil
    }

    var skippedExisting: URL? {
        if case .skip(_, let existing) = self { return existing }
        return nil
    }

    var isSkip: Bool {
        if case .skip = self { return true }
        return false
    }
}
