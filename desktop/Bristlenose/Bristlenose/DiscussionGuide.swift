import Foundation
import UniformTypeIdentifiers

/// The researcher's discussion guide, as the Mac app places it for the
/// pipeline's Discussion stage to find (`bristlenose/discussion/guide.py`).
enum DiscussionGuide {
    /// The reserved folder beside the recordings. Must equal `GUIDE_FOLDER` in
    /// `bristlenose/discussion/guide.py` — pinned by
    /// `tests/test_discussion_guide_parity.py`. Matched case-blind on read.
    static let folderName = "Discussion guide"

    /// The formats the stage reads: Word, Markdown, plain text.
    static let fileExtensions = ["docx", "md", "txt"]

    static var contentTypes: [UTType] {
        fileExtensions.compactMap { UTType(filenameExtension: $0) }
    }

    /// The project's guide folder, if there is one, whatever its case.
    static func existingFolder(in projectRoot: URL, fileManager: FileManager = .default) -> URL? {
        let entries = (try? fileManager.contentsOfDirectory(
            at: projectRoot, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
        return entries.first { $0.lastPathComponent.lowercased() == folderName.lowercased() }
    }

    enum InstallError: LocalizedError {
        /// The chosen guide is still in the cloud (dataless). Refused rather
        /// than fetched: a copy of a dataless file waits with no timeout, and
        /// this one runs on the main actor, so it would freeze the whole app
        /// (`desktop/CLAUDE.md`, the `copyItem` gotcha; R45 for the drop path).
        case notDownloaded

        /// English, for logs and bug reports; the alert reads `localeKey`.
        nonisolated var errorDescription: String? {
            "Your guide isn’t downloaded to this Mac yet."
        }

        nonisolated var localeKey: String { "desktop.discussion.guideNotDownloaded" }
    }

    /// Copy `source` into the project's guide folder, creating it if needed,
    /// and stamp it with the current time so the folder reads as changed after
    /// the last discussion record (`ProjectFolderWatcher.discussionWanted`).
    ///
    /// A file of the same name is replaced — that is what choosing a guide again
    /// means. Other files are left alone: the stage reads the newest and reports
    /// the rest, and deleting a researcher's file is not ours to do.
    ///
    /// A guide still in the cloud is refused before anything is touched, so a
    /// guide already in the project stays as it was. `isDataless` is injectable
    /// because no test can make a real cloud placeholder.
    @discardableResult
    static func install(
        _ source: URL,
        into projectRoot: URL,
        fileManager: FileManager = .default,
        isDataless: (URL) -> Bool = CopyMachinery.isDataless
    ) throws -> URL {
        if isDataless(source) { throw InstallError.notDownloaded }
        let folder = existingFolder(in: projectRoot, fileManager: fileManager)
            ?? projectRoot.appendingPathComponent(folderName, isDirectory: true)
        try fileManager.createDirectory(at: folder, withIntermediateDirectories: true)
        let destination = folder.appendingPathComponent(source.lastPathComponent)
        if fileManager.fileExists(atPath: destination.path) {
            let staged = folder.appendingPathComponent(".\(UUID().uuidString)-\(source.lastPathComponent)")
            try fileManager.copyItem(at: source, to: staged)
            _ = try fileManager.replaceItemAt(destination, withItemAt: staged)
        } else {
            try fileManager.copyItem(at: source, to: destination)
        }
        try fileManager.setAttributes([.modificationDate: Date()], ofItemAtPath: destination.path)
        return destination
    }
}
