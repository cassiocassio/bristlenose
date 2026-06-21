import Foundation
import os

/// Copies dropped URLs into a project folder. Plan §11 "Just Copy" — files
/// physically land alongside existing source media; researcher's originals
/// stay where they were (Photos-app model).
///
/// One in-flight copy at a time. The target project's sidebar row observes
/// `inFlight` (matched by `projectID`) and shows the determinate ring +
/// hover-cancel + "Copying · N%" subtitle; cancellation (ring hover-× or the
/// row's "Cancel copy" context-menu item) triggers a full rollback of any
/// partial destination files.
///
/// Same-volume copies on APFS use `clonefile(2)` automatically (via
/// `FileManager.copyItem`) — instant and zero bytes. Cross-volume copies
/// run sequentially with per-file progress; disk-space is prechecked.
@MainActor
final class CopyMachinery: ObservableObject {

    /// Visible state for the toolbar pill.
    struct InFlight: Equatable {
        let projectID: UUID
        let projectName: String
        var phase: Phase
        /// 0…1 fraction of bytes copied. Same-volume copies stay near 0
        /// briefly then jump to 1 because clonefile is instant.
        var progress: Double
        var totalBytes: Int64
    }

    enum Phase: Equatable { case copying, cancelling }

    /// Domain errors. Carries enough state to render a localised alert
    /// without forcing the call-site to format byte counts itself.
    enum CopyError: Error {
        case insufficientDiskSpace(needed: Int64, available: Int64)
        case noItemsAfterFiltering
        case underlying(String)
    }

    @Published private(set) var inFlight: InFlight?

    private var currentTask: Task<[URL], Error>?
    private let logger = Logger(subsystem: "app.bristlenose", category: "copy")

    /// Cancel the in-flight copy (if any). Rollback runs inside the task's
    /// catch block — the pill flips to "Cancelling…" while it completes.
    func cancel() {
        guard inFlight != nil else { return }
        inFlight?.phase = .cancelling
        currentTask?.cancel()
    }

    /// Plan + execute one copy. Returns the destination URLs of every
    /// successfully-copied file (suitable for `addFiles`).
    func copy(
        urls: [URL],
        into projectFolder: URL,
        projectID: UUID,
        projectName: String,
        acceptedExtensions: Set<String>
    ) async throws -> [URL] {
        guard inFlight == nil else {
            throw CopyError.underlying("Another copy is already in flight.")
        }

        // Planning + precheck — all on main; cheap.
        let items = Self.planItems(urls: urls, acceptedExtensions: acceptedExtensions)
        guard !items.isEmpty else {
            throw CopyError.noItemsAfterFiltering
        }
        let sameVolume = Self.sourcesShareVolume(
            with: projectFolder, sources: items.map(\.source)
        )
        let totalBytes = items.reduce(Int64(0)) { acc, item in
            acc + (Self.fileSize(of: item.source) ?? 0)
        }
        if !sameVolume,
           let available = Self.availableBytes(at: projectFolder),
           available < totalBytes {
            throw CopyError.insufficientDiskSpace(needed: totalBytes, available: available)
        }
        let resolved = Self.resolveDestinations(items: items, root: projectFolder)

        inFlight = InFlight(
            projectID: projectID,
            projectName: projectName,
            phase: .copying,
            progress: 0.0,
            totalBytes: totalBytes
        )

        // Heavy lift on a detached task — FileManager.copyItem is sync.
        let machineryLogger = self.logger
        let task = Task.detached { [weak self] () throws -> [URL] in
            var written: [URL] = []
            let totalBytesD = max(Double(totalBytes), 1.0)
            var copiedBytes: Int64 = 0
            do {
                for item in resolved {
                    try Task.checkCancellation()
                    try FileManager.default.createDirectory(
                        at: item.destination.deletingLastPathComponent(),
                        withIntermediateDirectories: true
                    )
                    // copyItem on APFS same-volume uses clonefile(2): O(1).
                    // Cross-volume: synchronous copy, no cancellation mid-file
                    // — Cancel takes effect at the next file boundary.
                    try FileManager.default.copyItem(at: item.source, to: item.destination)
                    written.append(item.destination)
                    copiedBytes += CopyMachinery.fileSize(of: item.source) ?? 0
                    let progress = Double(copiedBytes) / totalBytesD
                    await MainActor.run { [weak self] in
                        self?.inFlight?.progress = progress
                    }
                }
                return written
            } catch is CancellationError {
                await CopyMachinery.rollback(written: written, logger: machineryLogger)
                throw CancellationError()
            } catch {
                await CopyMachinery.rollback(written: written, logger: machineryLogger)
                throw CopyError.underlying(error.localizedDescription)
            }
        }
        self.currentTask = task
        defer {
            self.inFlight = nil
            self.currentTask = nil
        }
        return try await task.value
    }

    // MARK: - Pure helpers (testable)

    /// One source file and its relative-to-root destination subpath.
    struct PlannedItem: Equatable {
        let source: URL
        /// Relative path components under the destination root (e.g.
        /// `["folder", "subdir", "clip.mp4"]` for a folder drop preserving
        /// structure). Folder leaf is included so two folders dropped
        /// together with identical internal layouts don't collide.
        let relativeComponents: [String]
    }

    /// One source + final destination URL after collision resolution.
    struct ResolvedItem: Equatable {
        let source: URL
        let destination: URL
    }

    /// Expand top-level URLs into a flat list of items. Walks folders
    /// (`FileManager.enumerator`) and preserves their subdirectory shape;
    /// filters non-folder files by `acceptedExtensions`.
    ///
    /// The dropped folder's own name is preserved as a parent directory in
    /// the destination — researchers organise interviews into folders on
    /// purpose (batch, participant, location) and the pipeline's recursive
    /// scan finds files at any depth, so preserving that structure costs
    /// nothing and respects user intent. Matches Photos / Mail / Finder.
    /// Inter-folder name collisions are resolved by `resolveDestinations`
    /// via Finder-style "name 2.ext" renames.
    nonisolated static func planItems(urls: [URL], acceptedExtensions: Set<String>) -> [PlannedItem] {
        var out: [PlannedItem] = []
        for url in urls {
            if url.hasDirectoryPath {
                let rootName = url.lastPathComponent
                let baseLen = url.standardizedFileURL.pathComponents.count
                let fm = FileManager.default
                guard let walker = fm.enumerator(
                    at: url,
                    includingPropertiesForKeys: [.isRegularFileKey],
                    options: [.skipsHiddenFiles, .skipsPackageDescendants]
                ) else { continue }
                for case let child as URL in walker {
                    let isRegular = (try? child.resourceValues(
                        forKeys: [.isRegularFileKey]
                    ).isRegularFile) ?? false
                    guard isRegular else { continue }
                    let ext = child.pathExtension.lowercased()
                    guard acceptedExtensions.contains(ext) else { continue }
                    let allComponents = child.standardizedFileURL.pathComponents
                    let suffix = Array(allComponents.dropFirst(baseLen))
                    out.append(PlannedItem(
                        source: child,
                        relativeComponents: [rootName] + suffix
                    ))
                }
            } else {
                let ext = url.pathExtension.lowercased()
                if acceptedExtensions.contains(ext) {
                    out.append(PlannedItem(
                        source: url,
                        relativeComponents: [url.lastPathComponent]
                    ))
                }
            }
        }
        return out
    }

    /// Resolve every planned destination, applying Finder-style collision
    /// rename (`clip.mp4` → `clip 2.mp4` → `clip 3.mp4`, …) so we never
    /// overwrite. Within-batch collisions also work — `inUse` tracks paths
    /// already assigned to earlier items in this same call.
    nonisolated static func resolveDestinations(
        items: [PlannedItem],
        root: URL
    ) -> [ResolvedItem] {
        var inUse: Set<String> = []
        let fm = FileManager.default
        var out: [ResolvedItem] = []
        for item in items {
            let parentComponents = Array(item.relativeComponents.dropLast())
            let leaf = item.relativeComponents.last ?? "item"
            var parent = root
            for component in parentComponents {
                parent = parent.appendingPathComponent(component, isDirectory: true)
            }
            var candidateLeaf = leaf
            var n = 2
            while inUse.contains(parent.appendingPathComponent(candidateLeaf).path)
                || fm.fileExists(atPath: parent.appendingPathComponent(candidateLeaf).path) {
                candidateLeaf = Self.appendCount(to: leaf, n: n)
                n += 1
            }
            let dest = parent.appendingPathComponent(candidateLeaf)
            inUse.insert(dest.path)
            out.append(ResolvedItem(source: item.source, destination: dest))
        }
        return out
    }

    /// Finder-style rename: `name.mp4` → `name 2.mp4`; `name` → `name 2`.
    nonisolated static func appendCount(to name: String, n: Int) -> String {
        let url = URL(fileURLWithPath: name)
        let ext = url.pathExtension
        let stem = url.deletingPathExtension().lastPathComponent
        return ext.isEmpty ? "\(stem) \(n)" : "\(stem) \(n).\(ext)"
    }

    /// True iff every source lives on the same volume as `destination`.
    /// Uses `URLResourceKey.volumeIdentifierKey` — works regardless of
    /// filesystem type (APFS, HFS+, exFAT, network mounts).
    nonisolated static func sourcesShareVolume(with destination: URL, sources: [URL]) -> Bool {
        guard let destID = Self.volumeIdentifier(of: destination) else { return false }
        for src in sources {
            guard let srcID = Self.volumeIdentifier(of: src),
                  (srcID as? NSObject)?.isEqual(destID) == true else {
                return false
            }
        }
        return true
    }

    /// Raw `volumeIdentifier` from URL resource values. Typed as `Any` —
    /// callers compare with `isEqual:`. Apple's documented type is a generic
    /// "NSCopying & NSObjectProtocol & NSSecureCoding"; in practice it's an
    /// opaque NSObject (do not introspect).
    nonisolated static func volumeIdentifier(of url: URL) -> Any? {
        let values = try? url.resourceValues(forKeys: [.volumeIdentifierKey])
        return values?.volumeIdentifier
    }

    nonisolated static func fileSize(of url: URL) -> Int64? {
        let values = try? url.resourceValues(forKeys: [.fileSizeKey])
        return values?.fileSize.map(Int64.init)
    }

    nonisolated static func availableBytes(at url: URL) -> Int64? {
        let values = try? url.resourceValues(
            forKeys: [.volumeAvailableCapacityForImportantUsageKey]
        )
        return values?.volumeAvailableCapacityForImportantUsage
    }

    /// Delete every successfully-written destination, best-effort. Logs
    /// failures but never throws — the caller is already in an error path.
    nonisolated static func rollback(written: [URL], logger: Logger) async {
        for url in written {
            do {
                try FileManager.default.removeItem(at: url)
            } catch {
                logger.error("rollback: failed to remove \(url.path, privacy: .public): \(error.localizedDescription, privacy: .public)")
            }
        }
    }
}
