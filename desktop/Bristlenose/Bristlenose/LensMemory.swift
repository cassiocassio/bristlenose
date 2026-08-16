import Foundation

/// Which lens a window lands on when it opens a project.
///
/// ## The rule
///
/// **Where you left it, not the dashboard.** The app already holds this position
/// one level down: `SessionsRouteMemory` remembers which session you were
/// reading *inside* the Sessions lens, and its doc comment states the principle
/// — "the view the user left". This is the same rule one level up: project
/// instead of session, lens instead of route.
///
/// The reason is an **asymmetry, not a preference**. A wrong restore costs one
/// click: you wanted the overview, you click Project. A wrong reset can be
/// unrecoverable: you wanted the quote you were part-way through tagging, and
/// you are now hunting for a position among 312 you never consciously
/// memorised. One is a click, the other is a search.
///
/// Precedent: Finder stores view state per folder — view style, sort, scroll —
/// and restores it when you open that folder. A Bristlenose project *is* a
/// folder and the lens is the view style. That contract predates OS X.
///
/// ## What is deliberately not restored
///
/// **Search and filter.** A query restored days later shows 6 of 312 quotes with
/// no visible cause. Mail clears search between openings for the same reason.
///
/// **A never-opened project lands on the dashboard**, because it has no memory —
/// which is exactly the case the dashboard is right for. That falls out of the
/// data rather than needing a rule.
///
/// **No time heuristic.** "Restore only if closed recently" was considered and
/// rejected: an invisible clock deciding where you land is unlearnable, because
/// the researcher cannot see it and so cannot predict it. Either always or
/// never. (Same objection, and the same answer, as the conditional folder
/// disambiguator in the window-subtitle work.)
enum LensMemory {

    /// The lens to open on, given what was remembered.
    ///
    /// Returns nil for "no memory, land wherever the report loads by default",
    /// which is the Project dashboard. Also returns nil for a remembered value
    /// that no longer names a lens — a `Tab` case removed or renamed between
    /// versions. Silently landing on the dashboard beats both crashing and
    /// honouring a string nobody can interpret.
    static func restore(_ remembered: String?) -> Tab? {
        guard let remembered, let tab = Tab(rawValue: remembered) else { return nil }
        return tab
    }

    /// What to remember, given the lens the window is on now.
    ///
    /// Nil means "don't write" rather than "write nothing", so a window that
    /// hasn't yet reported a lens can't erase the memory it is about to restore
    /// from. That matters because the SPA's first `route-change` can arrive
    /// before, or instead of, a real navigation.
    static func remember(_ tab: Tab?) -> String? {
        tab?.rawValue
    }
}
