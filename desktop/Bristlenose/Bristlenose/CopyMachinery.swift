import CryptoKit
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

    /// Domain errors. `LocalizedError`, so every case renders a sentence
    /// wherever it is caught: `error.localizedDescription` resolves through
    /// `errorDescription` instead of Foundation's enum-index fallback
    /// ("…CopyError error 1."), and both catch sites in ContentView read the
    /// same words for the same failure. Pinned by CopyErrorSurfacingTests;
    /// the divergence this closed is in docs/design-copy-error-surfacing.md.
    enum CopyError: LocalizedError {
        /// Still carries the counts so the disk-space alert can format them.
        case insufficientDiskSpace(needed: Int64, available: Int64)
        case noItemsAfterFiltering
        case alreadyInFlight
        /// The error a file operation threw, carried whole so a caller can
        /// discriminate by domain and code. The sentence is the error's own.
        case underlying(Error)

        nonisolated var errorDescription: String? {
            switch self {
            case .insufficientDiskSpace(let needed, let available):
                let f = ByteCountFormatter()
                f.countStyle = .file
                return "Not enough free space: needs \(f.string(fromByteCount: needed)), "
                    + "\(f.string(fromByteCount: available)) available."
            case .noItemsAfterFiltering:
                return "None of the dropped items is a file Bristlenose can import."
            case .alreadyInFlight:
                return "Another copy is already in flight."
            case .underlying(let error):
                return error.localizedDescription
            }
        }

        /// The row's version: a key, not a sentence.
        ///
        /// `errorDescription` above stays English because `LocalizedError`
        /// descriptions reach logs and bug reports, and because
        /// `CopyErrorSurfacingTests` pins the contract that every case renders
        /// *a sentence* rather than an enum-index fallback — a contract about
        /// the diagnostic path, which this does not touch.
        ///
        /// `nil` for `.underlying`: that one carries a system error whose
        /// `localizedDescription` macOS has already localised. Translating it
        /// again would be replacing Apple's wording with ours.
        ///
        /// `insufficientDiskSpace` reuses `chrome.copyDiskSpaceTitle`, which
        /// already exists in 21 locales for the alert on the same condition —
        /// the house rule is to look for an already-translated twin before
        /// writing anything new.
        nonisolated var localeKey: String? {
            switch self {
            case .insufficientDiskSpace: return "desktop.chrome.copyDiskSpaceTitle"
            case .noItemsAfterFiltering: return "desktop.chrome.copyNoImportableItems"
            case .alreadyInFlight:       return "desktop.chrome.copyAlreadyInFlight"
            case .underlying:            return nil
            }
        }
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
            throw CopyError.alreadyInFlight
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
        inFlight = InFlight(
            projectID: projectID,
            projectName: projectName,
            phase: .copying,
            progress: 0.0,
            totalBytes: totalBytes
        )

        // Heavy lift on a detached task — FileManager.copyItem is sync, and
        // planning now hashes file contents to recognise a re-drop, which must
        // not run on the main thread.
        let machineryLogger = self.logger
        let task = Task.detached { [weak self] () throws -> [URL] in
            var written: [URL] = []
            let totalBytesD = max(Double(totalBytes), 1.0)
            var copiedBytes: Int64 = 0
            var skipped = 0
            let resolved = Self.resolveDestinations(items: items, root: projectFolder)
            do {
                for resolution in resolved {
                    try Task.checkCancellation()
                    switch resolution {
                    case .skip(let source, _):
                        // Already in the project, byte for byte. Nothing is
                        // written, so `written` never learns this path — which
                        // is what keeps `rollback` away from the researcher's
                        // existing recording if the copy is cancelled.
                        skipped += 1
                        copiedBytes += CopyMachinery.fileSize(of: source) ?? 0
                    case .copy(let item):
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
                    }
                    let progress = Double(copiedBytes) / totalBytesD
                    await MainActor.run { [weak self] in
                        self?.inFlight?.progress = progress
                    }
                }
                if skipped > 0 {
                    // Counts only. A basename can name a participant, so it is
                    // never logged — the same rule the folder watcher carries.
                    machineryLogger.info(
                        "copy: \(skipped, privacy: .public) already present, byte-identical; not copied"
                    )
                }
                return written
            } catch is CancellationError {
                await CopyMachinery.rollback(written: written, logger: machineryLogger)
                throw CancellationError()
            } catch {
                await CopyMachinery.rollback(written: written, logger: machineryLogger)
                throw CopyError.underlying(error)
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

    /// What to do with one planned item.
    ///
    /// `.skip` exists because the collision rename had exactly one verdict —
    /// rename — and so answered "is there something at this name?" when the
    /// question a re-drop asks is "do I already hold this content?". The
    /// duplicate it produced was free on disk (same-volume `copyItem` clones)
    /// and expensive downstream: the transcription cache keys on
    /// path + size + mtime, so a renamed copy is a guaranteed miss, and one
    /// re-dropped folder measured $0.6170 across 15 LLM calls against $0.0907
    /// clean. Two copies of one interview also become two participants, whose
    /// identical quotes then cluster together — so the report reads as
    /// corroboration rather than as a mistake.
    enum Resolution: Equatable {
        case copy(ResolvedItem)
        /// `existing` is the file already in the project that answered for
        /// this source. Carried so a caller can say which file it recognised.
        case skip(source: URL, existing: URL)
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
    ///
    /// A file the project already holds **byte for byte** resolves to `.skip`
    /// instead. Nothing is deleted, moved or overwritten to achieve that — the
    /// never-overwrite guarantee above is unchanged, and a skip simply writes
    /// nothing. Identity is proven, never guessed: see `holdsSameContent`.
    nonisolated static func resolveDestinations(
        items: [PlannedItem],
        root: URL
    ) -> [Resolution] {
        var inUse: Set<String> = []
        let fm = FileManager.default
        var out: [Resolution] = []
        for item in items {
            let parentComponents = Array(item.relativeComponents.dropLast())
            let leaf = item.relativeComponents.last ?? "item"
            var parent = root
            for component in parentComponents {
                parent = parent.appendingPathComponent(component, isDirectory: true)
            }
            var candidateLeaf = leaf
            var n = 2
            var alreadyHeld: URL?
            while true {
                let candidate = parent.appendingPathComponent(candidateLeaf)
                // A path claimed by an earlier item in this same batch is not
                // on disk yet, so it can answer the collision question but not
                // the identity one.
                let claimed = inUse.contains(candidate.path)
                guard claimed || fm.fileExists(atPath: candidate.path) else { break }
                // Every *existing* file in the chain is an identity candidate,
                // not just the first. A folder that has already been re-dropped
                // holds `clip.mov` AND `clip 2.mov`, and the next drop has to
                // recognise either one rather than minting `clip 3.mov`.
                if !claimed, Self.holdsSameContent(as: item.source, candidate: candidate) {
                    alreadyHeld = candidate
                    break
                }
                candidateLeaf = Self.appendCount(to: leaf, n: n)
                n += 1
            }
            if let alreadyHeld {
                out.append(.skip(source: item.source, existing: alreadyHeld))
                continue
            }
            let dest = parent.appendingPathComponent(candidateLeaf)
            inUse.insert(dest.path)
            out.append(.copy(ResolvedItem(source: item.source, destination: dest)))
        }
        return out
    }

    /// Whether `candidate` — a file the project already holds — is byte for
    /// byte the same content as `source`.
    ///
    /// **Exact, never heuristic.** The cost of a false positive is a distinct
    /// interview silently not imported, so every uncertainty answers `false`
    /// and the caller falls back to the rename. Cheaper signals were measured
    /// and rejected:
    ///
    /// - **size alone** — two distinct AppleDouble sidecars on an ExFAT card
    ///   measure *exactly* 4096 bytes. Size collisions are ordinary.
    /// - **mtime** — a cross-volume copy truncates nanoseconds to ExFAT's 10 ms
    ///   (measured 1790431020.6103103 → 1790431020.6100001), so equality is not
    ///   portable; and two unrelated files can share one anyway.
    /// - **duration** — reading a container header faults a cloud placeholder
    ///   in, so answering "do I have this?" would download it; and it cannot
    ///   separate two half-hour interviews. This is why `CloudImportLocalMatch`,
    ///   which matches on duration, is not reused for identity here — only its
    ///   `isMaterialised` measurement is.
    /// - **inode / `fileResourceIdentifierKey`** — proves *same file*
    ///   (a hard link), not same content. A clone gets a fresh one, so it
    ///   cannot see the duplicate this exists to stop.
    ///
    /// The full digest is affordable because the equal-length gate below almost
    /// never fires on a genuine new drop: 465 MB hashes in 0.22 s uncached
    /// (CryptoKit, ~2 GB/s), so the common case costs one extra `stat`.
    nonisolated static func holdsSameContent(as source: URL, candidate: URL) -> Bool {
        // Cancelling mid-hash answers "not identical", which renames; the copy
        // loop then throws and rolls back. Fail-safe direction.
        if Task.isCancelled { return false }

        // Both sides must be ordinary files. A symbolic link reports
        // `isRegularFile == false` (measured), which is the answer we want:
        // `copyItem` would copy the link rather than the bytes, so the link's
        // content identity is not the question being asked.
        guard Self.isPlainFile(source), Self.isPlainFile(candidate) else { return false }

        // Never fault in a placeholder to answer "do I already have this?".
        // A dataless file reports its full logical size over zero allocated
        // blocks (measured: 397975112 bytes, 0 blocks), so the size gate below
        // would match and prove nothing.
        guard CloudImportLocalMatch.isMaterialised(source),
              CloudImportLocalMatch.isMaterialised(candidate) else { return false }

        // Cheap gate: a different length is a definite answer for one `stat`.
        guard let sourceStamp = Self.stamp(of: source),
              let candidateStamp = Self.stamp(of: candidate),
              sourceStamp.size == candidateStamp.size else { return false }

        // Both digests must exist AND agree. Spelled out rather than compared
        // as optionals on purpose: `(try? a) == (try? b)` is `nil == nil` when
        // *both* files are unreadable, which would declare two files we cannot
        // read identical and silently drop one.
        guard let sourceDigest = Self.sha256(of: source),
              let candidateDigest = Self.sha256(of: candidate),
              sourceDigest == candidateDigest else { return false }

        // The digests describe the files as they were a moment ago. A recording
        // still being written — or a cloud client still syncing into the folder
        // — can have grown since, and skipping then loses the longer file. Both
        // stamps must be unchanged for the skip to stand.
        guard Self.stamp(of: source) == sourceStamp,
              Self.stamp(of: candidate) == candidateStamp else { return false }

        return true
    }

    /// Size + mtime, read together, for the before/after comparison in
    /// `holdsSameContent`. `nil` when the file cannot be measured at all.
    private struct Stamp: Equatable {
        let size: Int64
        let modified: Date?
    }

    nonisolated private static func stamp(of url: URL) -> Stamp? {
        guard let values = try? url.resourceValues(
            forKeys: [.fileSizeKey, .contentModificationDateKey]
        ), let size = values.fileSize else { return nil }
        return Stamp(size: Int64(size), modified: values.contentModificationDate)
    }

    /// A regular file and not a symbolic link. Both keys are checked because
    /// `resourceValues` on a symlink URL describes the *link* (measured:
    /// `isRegularFile == false`, `isSymbolicLink == true`), while
    /// `fileExists(atPath:)` follows it — an asymmetry worth not relying on.
    nonisolated private static func isPlainFile(_ url: URL) -> Bool {
        guard let values = try? url.resourceValues(
            forKeys: [.isRegularFileKey, .isSymbolicLinkKey]
        ) else { return false }
        return values.isRegularFile == true && values.isSymbolicLink != true
    }

    /// Streaming SHA-256 over a 1 MiB buffer.
    ///
    /// `nil` on *any* read failure, so an unreadable file can never compare
    /// equal to anything — including another unreadable file. Checks
    /// cancellation per chunk so a large re-drop stays stoppable.
    nonisolated static func sha256(of url: URL) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            if Task.isCancelled { return nil }
            let chunk: Data?
            do {
                chunk = try handle.read(upToCount: 1 << 20)
            } catch {
                return nil
            }
            guard let chunk, !chunk.isEmpty else { break }
            hasher.update(data: chunk)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
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
