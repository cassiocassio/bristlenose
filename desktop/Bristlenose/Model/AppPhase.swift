import Foundation

/// The four states of the launcher UI.
enum AppPhase {
    case ready
    case selected(folder: URL, fileCount: Int, hasExistingOutput: Bool)
    case running(folder: URL, mode: RunMode)
    case done(folder: URL, reportPath: String?, lines: [String])
}

enum RunMode: String {
    case analyse = "analyse"
    case rerender = "rerender"
}
