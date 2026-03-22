import Foundation

/// The five top-level navigation tabs in the toolbar segmented control.
///
/// Raw values match the keys expected by `window.switchToTab(tab)` in
/// `frontend/src/shims/navigation.ts`.
enum Tab: String, CaseIterable, Identifiable {
    case project, sessions, quotes, codebook, analysis

    var id: String { rawValue }

    var label: String {
        switch self {
        case .project:   "Project"
        case .sessions:  "Sessions"
        case .quotes:    "Quotes"
        case .codebook:  "Codebook"
        case .analysis:  "Analysis"
        }
    }

    var route: String {
        switch self {
        case .project:   "/report/"
        case .sessions:  "/report/sessions/"
        case .quotes:    "/report/quotes/"
        case .codebook:  "/report/codebook/"
        case .analysis:  "/report/analysis/"
        }
    }

    /// Derive the active tab from a React Router pathname.
    ///
    /// Uses longest-prefix-first ordering so `/report/sessions/abc123`
    /// correctly maps to `.sessions`. The project tab uses exact match
    /// to avoid swallowing all `/report/...` paths.
    static func from(path: String) -> Tab? {
        if path.hasPrefix("/report/analysis") { return .analysis }
        if path.hasPrefix("/report/codebook") { return .codebook }
        if path.hasPrefix("/report/quotes")   { return .quotes }
        if path.hasPrefix("/report/sessions") { return .sessions }
        if path == "/report/" || path == "/report" { return .project }
        return nil
    }
}
