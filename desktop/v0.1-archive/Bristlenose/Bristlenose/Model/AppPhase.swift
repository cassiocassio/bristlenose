import Foundation

/// The five states of the launcher UI.
enum AppPhase: Equatable {
    case ready
    case selected(folder: URL, fileCount: Int, hasExistingOutput: Bool)
    case running(folder: URL, mode: RunMode)
    case serving(folder: URL, reportURL: String, lines: [String])
    case done(folder: URL, reportPath: String?, lines: [String])
}

enum RunMode: String {
    case analyse = "analyse"
    case rerender = "rerender"
}
