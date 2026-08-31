import Foundation

/// The five top-level navigation tabs in the toolbar segmented control.
///
/// Raw values match the keys expected by `window.switchToTab(tab)` in
/// `frontend/src/shims/navigation.ts`.
enum Tab: String, CaseIterable, Identifiable {
    case project, sessions, quotes, codebook, analysis

    var id: String { rawValue }

    /// English fallback label — used when I18n is not available.
    var label: String {
        switch self {
        case .project:   "Project"
        case .sessions:  "Sessions"
        case .quotes:    "Quotes"
        case .codebook:  "Codebooks"
        case .analysis:  "Analysis"
        }
    }

    /// Translated label from shared locale files.
    /// Uses `_short` variant if available (e.g. "Códigos" instead of "Libro de códigos").
    @MainActor func localizedLabel(_ i18n: I18n) -> String {
        let shortKey = "common.nav.\(rawValue)Short"
        let shortValue = i18n.t(shortKey)
        // If _short key resolved (didn't return raw key), use it
        if shortValue != shortKey { return shortValue }
        // Otherwise use the full label
        let fullKey = "common.nav.\(rawValue)"
        let fullValue = i18n.t(fullKey)
        return fullValue != fullKey ? fullValue : label
    }

    /// Full translated label (no `_short` preference) — for surfaces with room,
    /// e.g. the sidebar lens rail ("Codebook", not the toolbar Picker's "Codes").
    /// Shares the English `label` fallback so the i18n resolution lives in one
    /// place rather than being re-implemented per call site.
    @MainActor func fullLocalizedLabel(_ i18n: I18n) -> String {
        let key = "common.nav.\(rawValue)"
        let value = i18n.t(key)
        return value != key ? value : label
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

    /// Does this lens have a web left panel — the content navigator?
    ///
    /// One list, because there were four: the toolbar button's gate, its label,
    /// its tooltip, and the View menu's Show/Hide item. Adding a lens once
    /// reached three of them and missed the gate, so it had a panel, a menu
    /// item that toggled it and a ⌘⌥L that worked — and no toolbar button,
    /// which on the Mac is the only affordance embedded mode leaves (the SPA's
    /// own rails are gone there). A four-way enumeration of the same fact is a
    /// three-way disagreement waiting to happen.
    var hasLeftPanel: Bool {
        switch self {
        case .quotes, .codebook, .analysis: true
        case .project, .sessions: false
        }
    }

    /// Derive the active tab from a React Router pathname.
    ///
    /// Uses longest-prefix-first ordering so `/report/sessions/abc123`
    /// correctly maps to `.sessions`. The project tab uses exact match
    /// to avoid swallowing all `/report/...` paths.
    static func from(path: String) -> Tab? {
        if path.hasPrefix("/report/analysis") { return .analysis }
        // The v2 route is gone (v2 became the only Codebook lens, 31 Aug 2026),
        // and with it the longest-prefix hazard this arm guarded:
        // "/report/codebook-v2" had "/report/codebook" as a prefix, so the
        // shorter test would have swallowed it silently. Kept as a note because
        // the rule outlives the case — any future sibling route sharing a
        // prefix must be tested BEFORE the shorter one.
        if path.hasPrefix("/report/codebook") { return .codebook }
        if path.hasPrefix("/report/quotes")   { return .quotes }
        if path.hasPrefix("/report/sessions") { return .sessions }
        if path == "/report/" || path == "/report" { return .project }
        return nil
    }
}
