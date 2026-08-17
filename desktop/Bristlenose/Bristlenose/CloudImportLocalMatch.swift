import AVFoundation
import Foundation

// Whether a listed recording is already sitting in the destination project.
//
// Design: docs/design-cloud-import.md, changelog 17 Aug 2026, item 1.
//
// MARK: PII — filenames may name participants. Never log them.
//
// **The route this answers is a manual one.** The researcher downloads by
// hand, renames, drops the file in the folder and processes it — and only
// opens this window days later. Those files never came through the importer,
// so there is no row id to have recorded and no key we could have minted at
// import time. A folder scan is the whole answer here, not a fallback to one.
//
// It earns its place on what a duplicate does downstream rather than on the
// wasted transfer. Two copies of one interview become two participants, whose
// identical quotes then cluster *together* — so the report does not read as a
// mistake, it reads as corroboration. That is the failure this prevents.
//
// **Duration is the only key available.** The filename is gone by
// construction (renaming is step two of the routine), and Google writes no
// `creation_time` into its MP4s at all — measured over the five recordings
// this feature has fetched, every Meet file carries `encoder=Google` and
// nothing else, while the Teams file beside them has one. So the
// date-plus-duration pair collapses to duration alone on the platform it was
// designed for.
//
// **It degrades in a knowable order, and the last cell is stated rather than
// answered.** A hand-*trimmed* recording matches nothing, because its length
// is no longer the meeting's. Closing that cell would take audio
// fingerprinting — IP-protection technology, and a whole subsystem for one
// case — so trimming is out of scope by decision, not by omission.

/// One media file found in the destination folder.
struct LocalRecording: Equatable, Sendable {
    /// Diagnostics and tests only. **Never rendered and never logged** — a
    /// basename here may identify a participant, the same rule the folder
    /// watcher carries.
    let name: String

    /// Media length in seconds, read from the container.
    let duration: TimeInterval
}

enum CloudImportLocalMatch {

    // MARK: - The decision

    /// Which rows the destination folder already holds.
    ///
    /// Pure, so the matching rule can be argued about without a folder, a
    /// tenant, or a signed-in account.
    ///
    /// **One file may satisfy at most one row.** Without that, a single
    /// downloaded interview lying within tolerance of two listed rows marks
    /// *both* as held — and `.imported` offers no tick, so the second row
    /// becomes unfetchable with no override. The failure directions are not
    /// symmetric: missing a match costs a duplicate the researcher can delete,
    /// while inventing one silently withholds a recording. So ties resolve to
    /// the closest pair, and every row that loses a contest stays fetchable.
    ///
    /// - Parameter platform: supplies the tolerance, which is **per row** —
    ///   see `CloudPlatform.durationTolerance(forListed:)`. The two quantities
    ///   being compared are not the same measurement, and how far apart they
    ///   may drift scales with the recording.
    static func alreadyPresent(
        rows: [CloudImportRow],
        local: [LocalRecording],
        platform: CloudPlatform
    ) -> Set<String> {
        guard !local.isEmpty else { return [] }

        // Only a row that claims nothing locally, and that has a recording
        // behind it at all. `hasRecording` rather than `video.isAvailable`:
        // a recording the tenant won't serve us is one the researcher can
        // still have downloaded from the web UI by hand, and that is exactly
        // the population this check is for.
        let candidates = rows.compactMap { row -> (id: String, length: TimeInterval)? in
            guard row.localState == .notImported, row.hasRecording,
                  let length = row.duration, length > 0 else { return nil }
            return (row.id, length)
        }
        guard !candidates.isEmpty else { return [] }

        var pairs: [(rowID: String, file: Int, delta: TimeInterval)] = []
        for candidate in candidates {
            // Per row, not per platform: a 35-minute interview and a
            // 20-second test recording listed side by side need very
            // different windows, and the flat one was 75% of the short one.
            let tolerance = platform.durationTolerance(forListed: candidate.length)
            for (index, file) in local.enumerated() where file.duration > 0 {
                let delta = abs(file.duration - candidate.length)
                if delta <= tolerance {
                    pairs.append((candidate.id, index, delta))
                }
            }
        }

        // Closest first, then by row id and file index so a tie resolves the
        // same way twice. Two Meet siblings of one call routinely carry an
        // identical duration, and an arbitrary winner there would move between
        // renders of the same list.
        pairs.sort { lhs, rhs in
            if lhs.delta != rhs.delta { return lhs.delta < rhs.delta }
            if lhs.rowID != rhs.rowID { return lhs.rowID < rhs.rowID }
            return lhs.file < rhs.file
        }

        var claimedRows: Set<String> = []
        var claimedFiles: Set<Int> = []
        for pair in pairs where !claimedRows.contains(pair.rowID)
            && !claimedFiles.contains(pair.file) {
            claimedRows.insert(pair.rowID)
            claimedFiles.insert(pair.file)
        }
        return claimedRows
    }

    // MARK: - The scan

    /// Extensions worth opening for a duration.
    ///
    /// A media-only subset of `ProjectFolderWatcher.eligibleExtensions`: a
    /// `.vtt` or `.docx` beside the recordings is a transcript, which has no
    /// length to compare and would cost an `AVAsset` open to learn that.
    static let mediaExtensions: Set<String> = [
        "mp4", "m4v", "mov", "webm", "mkv", "avi",
        "m4a", "mp3", "wav", "aac", "flac",
    ]

    /// Read every top-level recording in `folder` and measure it.
    ///
    /// Top level only, matching `ProjectFolderWatcher` — the routine this
    /// serves drops files *in* the project folder, and the pipeline ingests
    /// from there, so a nested copy is not a session either scanner counts.
    ///
    /// `folder` must already carry its security-scoped lease. Under App
    /// Sandbox a raw path into a user-chosen folder has no grant behind it and
    /// enumerates as empty — which would read as "nothing here" rather than as
    /// a refusal, and quietly turn this whole check off.
    ///
    /// Never throws: a folder we cannot read yields no matches, which leaves
    /// every row fetchable. That is the safe direction.
    static func scan(folder: URL) async -> [LocalRecording] {
        let files = mediaFiles(in: folder)
        guard !files.isEmpty else { return [] }

        let found = await withTaskGroup(of: LocalRecording?.self) { group in
            for url in files {
                group.addTask { await probe(url) }
            }
            var measured: [LocalRecording] = []
            for await recording in group {
                if let recording { measured.append(recording) }
            }
            return measured
        }
        // A task group completes out of order. Sorting restores a stable input
        // for the tie-break above, which is otherwise decided by whichever
        // header happened to be read first.
        return found.sorted { $0.name < $1.name }
    }

    private static func mediaFiles(in folder: URL) -> [URL] {
        guard let contents = try? FileManager.default.contentsOfDirectory(
            at: folder,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        ) else { return [] }

        return contents.filter { url in
            let name = url.lastPathComponent
            // Derived media, not sources — an exported clip is cut *from* one
            // of these recordings. Top-level-only already excludes it; kept
            // explicit so this reads identically to the watcher's filter.
            if name == "bristlenose-output" { return false }
            // Belt and braces over `.skipsHiddenFiles`, and the AppleDouble
            // guard: a `._interview.mp4` on an ExFAT card is binary metadata
            // wearing a video extension.
            if name.hasPrefix(".") { return false }
            if !mediaExtensions.contains(url.pathExtension.lowercased()) { return false }
            return (try? url.resourceValues(forKeys: [.isRegularFileKey]))?
                .isRegularFile == true
        }
    }

    /// Measure one file, or decline to.
    private static func probe(_ url: URL) async -> LocalRecording? {
        // **Never open a placeholder.** Reading a container header faults the
        // file in, and a dataless source is the case where `FileManager`'s
        // equivalent blocks indefinitely with no error and no cancellation —
        // here that would wedge the scan behind a file the researcher never
        // asked us to download. A file we cannot measure is one we cannot
        // claim, so declining leaves its row fetchable.
        guard isMaterialised(url) else { return nil }

        let asset = AVURLAsset(url: url)
        guard let time = try? await asset.load(.duration), time.isNumeric else { return nil }
        let seconds = CMTimeGetSeconds(time)
        guard seconds.isFinite, seconds > 0 else { return nil }
        return LocalRecording(name: url.lastPathComponent, duration: seconds)
    }

    /// Whether the bytes are actually here.
    ///
    /// Two signals, because one provider's placeholder is invisible to the
    /// other's flag. `ubiquitousItemDownloadingStatus` is what iCloud Drive
    /// and every NSFileProvider extension publish; allocated-size-zero over a
    /// non-zero logical size is what the file *is*, and catches a provider
    /// that publishes no status at all.
    private static func isMaterialised(_ url: URL) -> Bool {
        if ProjectFolderWatcher.isCloudEvicted(url) { return false }
        let values = try? url.resourceValues(
            forKeys: [.fileSizeKey, .totalFileAllocatedSizeKey])
        if let logical = values?.fileSize, logical > 0,
           let allocated = values?.totalFileAllocatedSize, allocated == 0 {
            return false
        }
        return true
    }
}
