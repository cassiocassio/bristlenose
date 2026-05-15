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

    // MARK: - resolveDestinations — never overwrites existing files

    @Test("resolveDestinations: no collision keeps original leaf")
    func resolveDestinations_noCollision() {
        let tmp = makeTempDir()
        let item = CopyMachinery.PlannedItem(
            source: URL(fileURLWithPath: "/dev/null"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved.count == 1)
        #expect(resolved[0].destination.lastPathComponent == "clip.mov")
    }

    @Test("resolveDestinations: renames when leaf collides with existing disk file")
    func resolveDestinations_onDiskCollision() {
        let tmp = makeTempDir()
        touch(tmp.appendingPathComponent("clip.mov"))

        let item = CopyMachinery.PlannedItem(
            source: URL(fileURLWithPath: "/dev/null"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].destination.lastPathComponent == "clip 2.mov")
    }

    @Test("resolveDestinations: triple disk collision walks 2 → 3")
    func resolveDestinations_tripleCollision() {
        let tmp = makeTempDir()
        touch(tmp.appendingPathComponent("clip.mov"))
        touch(tmp.appendingPathComponent("clip 2.mov"))

        let item = CopyMachinery.PlannedItem(
            source: URL(fileURLWithPath: "/dev/null"),
            relativeComponents: ["clip.mov"]
        )
        let resolved = CopyMachinery.resolveDestinations(items: [item], root: tmp)
        #expect(resolved[0].destination.lastPathComponent == "clip 3.mov")
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
        #expect(resolved[0].destination.lastPathComponent == "clip.mov")
        #expect(resolved[1].destination.lastPathComponent == "clip 2.mov")
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
        #expect(resolved[0].destination.standardizedFileURL == expected.standardizedFileURL)
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
