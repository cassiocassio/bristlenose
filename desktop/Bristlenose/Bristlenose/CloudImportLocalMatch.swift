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

/// What one look at the destination folder found.
///
/// **The whole per-project record, and there is deliberately no other one.**
/// The plan called for a persisted artefact — what we fetched, what never
/// arrived, what was in flight when the app quit — with a schema, a migration
/// story and a privacy question, since it would name meetings and platforms.
/// It is not needed, because `CloudDownloader` was built so the folder answers
/// all three: verification happens while the bytes are still outside the
/// destination name and the final rename is atomic, so *"what you can see on
/// disk is true"* (its own words). A record would be a second, staler copy of
/// something already trustworthy, and the one that can disagree.
struct LocalScan: Equatable, Sendable {
    /// Files that opened and measured. The duration match runs on these.
    var recordings: [LocalRecording] = []

    /// Files that are present, materialised, in a format we can judge — and
    /// will not open.
    ///
    /// **Judgeable is the load-bearing word.** `mediaExtensions` includes
    /// `mkv`, `webm` and `avi`, none of which AVFoundation can open *at all*,
    /// so "did not open" is not evidence of damage for a researcher's own
    /// files — it is evidence of a container Apple never shipped support for.
    /// Only formats we ourselves write are listed here. See `judgeableExtensions`.
    var unreadable: [String] = []

    /// Leftover `.part` files: a download that was interrupted, almost always
    /// by the app quitting mid-batch.
    ///
    /// This is the *only* on-disk trace an in-flight quit can leave, and that
    /// is by construction rather than by luck: the transfer streams to the
    /// system temp directory, is verified there, and only then moves to `.part`
    /// and atomically renames. So a killed app leaves either nothing or an
    /// obviously-unfinished sibling — never a plausible-looking recording under
    /// the real name.
    var interrupted: [String] = []
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

    // MARK: - Goodness

    /// Rows whose file is present and will not open.
    ///
    /// **Matched by name, not by duration — and the inversion is deliberate.**
    /// Everywhere else this type matches on duration precisely *because*
    /// filenames diverge: ours are machine-local, the vendor's are
    /// account-local, and a researcher renames things. None of that applies
    /// here. A damaged file has no readable duration to match on, and the only
    /// files we are willing to call damaged are ones **we wrote ourselves**,
    /// under a name `CloudDownloadNaming` computed from the row in front of us.
    /// So the name is exact by construction, and a researcher's own broken
    /// download of the same meeting is correctly left alone.
    ///
    /// Compared on the stem, so Zoom's audio-only `.m4a` rendition matches the
    /// same row as an `.mp4` would — the extension is decided at fetch time
    /// from the file Zoom offers, and is not knowable from the row.
    static func damaged(rows: [CloudImportRow], scan: LocalScan) -> Set<String> {
        guard !scan.unreadable.isEmpty else { return [] }
        let broken = Set(scan.unreadable.map { ($0 as NSString).deletingPathExtension })

        var damaged: Set<String> = []
        for row in rows {
            let expected = CloudDownloadNaming.filename(
                title: row.title, startsAt: row.startsAt,
                fileExtension: "mp4", part: row.siblingOrdinal)
            if broken.contains((expected as NSString).deletingPathExtension) {
                damaged.insert(row.id)
            }
        }
        return damaged
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
        await inspect(folder: folder).recordings
    }

    /// Formats a failed open is real evidence about.
    ///
    /// **The list is "what we write", not "what we accept".** `mediaExtensions`
    /// is the wider set the duration match reads, and it includes `mkv`,
    /// `webm` and `avi` — containers AVFoundation cannot open at all. A
    /// researcher's own `.mkv` therefore fails to probe on a perfectly healthy
    /// file, and calling that damaged would accuse their material of being
    /// broken because Apple never shipped a demuxer for it.
    ///
    /// Every cloud download lands as `.mp4`, or `.m4a` for Zoom's audio-only
    /// rendition. Both are natively supported, so for these — and only these —
    /// "materialised and will not open" means the file is bad.
    static let judgeableExtensions: Set<String> = ["mp4", "m4a", "mov", "m4v"]

    /// One look at the destination folder: what opened, what did not, and what
    /// was left half-written.
    ///
    /// The same single pass the duration match already paid for — the probe was
    /// always distinguishing these cases and throwing two of them away.
    static func inspect(folder: URL) async -> LocalScan {
        var result = LocalScan(interrupted: partFiles(in: folder))

        let files = mediaFiles(in: folder)
        guard !files.isEmpty else { return result }

        let probed = await withTaskGroup(of: (URL, LocalRecording?).self) { group in
            for url in files {
                group.addTask { (url, await probe(url)) }
            }
            var out: [(URL, LocalRecording?)] = []
            for await pair in group { out.append(pair) }
            return out
        }

        for (url, recording) in probed {
            if let recording {
                result.recordings.append(recording)
            } else if judgeableExtensions.contains(url.pathExtension.lowercased()),
                      isMaterialised(url) {
                // Materialised, ours, and it will not open. Not a placeholder
                // (that is `isMaterialised`'s job) and not an unsupported
                // container (that is `judgeableExtensions`'), so what is left is
                // a file that has actually gone bad since it landed —
                // truncated by a sync, corrupted on disk, or half-copied by
                // something that is not us.
                result.unreadable.append(url.lastPathComponent)
            }
        }

        // A task group completes out of order. Sorting restores a stable input
        // for the tie-break above, which is otherwise decided by whichever
        // header happened to be read first.
        result.recordings.sort { $0.name < $1.name }
        result.unreadable.sort()
        return result
    }

    /// Interrupted downloads, by the final name they were heading for.
    ///
    /// Returned as `foo.mp4`, not `foo.mp4.part`, because the caller's question
    /// is always "what happened to this recording" and the `.part` suffix is
    /// our own plumbing.
    private static func partFiles(in folder: URL) -> [String] {
        guard let contents = try? FileManager.default.contentsOfDirectory(
            at: folder,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        ) else { return [] }

        return contents
            .filter { $0.pathExtension.lowercased() == "part" }
            .map { $0.deletingPathExtension().lastPathComponent }
            .sorted()
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
