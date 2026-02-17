import Foundation

struct FolderCheckResult {
    let fileCount: Int
    let hasExistingOutput: Bool
}

/// Checks a directory for files bristlenose can process.
///
/// Extension list mirrors `bristlenose/models.py` (AUDIO_EXTENSIONS,
/// VIDEO_EXTENSIONS, SUBTITLE_SRT_EXTENSIONS, SUBTITLE_VTT_EXTENSIONS,
/// DOCX_EXTENSIONS).
enum FolderValidator {

    private static let processableExtensions: Set<String> = [
        // Audio
        ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma", ".aac",
        // Video
        ".mp4", ".mov", ".avi", ".mkv", ".webm",
        // Subtitles
        ".srt", ".vtt",
        // Documents
        ".docx",
    ]

    static func check(folder: URL) -> FolderCheckResult {
        let fm = FileManager.default

        var fileCount = 0
        if let enumerator = fm.enumerator(
            at: folder,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        ) {
            for case let fileURL as URL in enumerator {
                let ext = fileURL.pathExtension.lowercased()
                if processableExtensions.contains(".\(ext)") {
                    fileCount += 1
                }
            }
        }

        let outputDir = folder.appendingPathComponent("bristlenose-output")
        var isDir: ObjCBool = false
        let hasExistingOutput = fm.fileExists(atPath: outputDir.path, isDirectory: &isDir)
            && isDir.boolValue

        return FolderCheckResult(
            fileCount: fileCount,
            hasExistingOutput: hasExistingOutput
        )
    }
}
