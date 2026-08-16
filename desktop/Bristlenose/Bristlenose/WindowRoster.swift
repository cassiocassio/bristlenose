import Foundation

/// Which project windows are open, and which of them are showing the same thing.
///
/// Two consumers, both of which need to know about windows *other than the front
/// one* — which is exactly what `focusedSceneValue` cannot tell you:
///
/// 1. **The ordinal suffix** (mockup E4). Nine windows on one study's Quotes lens
///    drew nine identical Window-menu rows. A window needs to know how many
///    siblings already show what it shows.
/// 2. **`applicationShouldHandleReopen`.** Clicking the Dock icon with no project
///    window open should open one. AppKit's `hasVisibleWindows` is the near
///    answer but counts Settings and the Import window too, so it says "yes,
///    there's a window" when there is nothing to come back to.
///
/// **Deliberately not a third thing.** It does not hold the windows themselves,
/// or track which was key most recently. That would be an approximation of
/// AppKit's `mainWindow` — "the window that is the focus of the user's
/// attention", which stays pointing at the document window while a panel is key
/// — and it was considered and declined (16 Aug 2026). With a panel frontmost
/// this app **dims** its window commands rather than acting on the window
/// behind, so there is no second window to resolve and nothing to hold.
@MainActor
final class WindowRoster {

    static let shared = WindowRoster()

    /// What makes two windows duplicates for titling: the same study on the
    /// same lens. Different lenses already read differently in the Window menu,
    /// because the subtitle carries the per-lens count.
    struct Group: Hashable {
        let projectID: UUID
        /// `Tab.rawValue`, or nil before the report has said which lens it is on.
        let lens: String?
    }

    /// Ordinals in use per group. Never compacted — see `claim`.
    private var taken: [Group: Set<Int>] = [:]
    /// Every live project window, and the ordinal it holds. The group is
    /// optional because a window showing the welcome screen still **counts** as
    /// a window — a Dock click must not open a second one — it just isn't in any
    /// duplicate group, since two "Welcome" windows aren't worth numbering.
    private var held: [UUID: (group: Group?, ordinal: Int)] = [:]

    private init() {}

    /// Is any project window open? (Settings and the Import window are not
    /// project windows and are deliberately not counted.)
    var hasProjectWindow: Bool { !held.isEmpty }

    /// Number of live project windows — for tests and diagnostics.
    var count: Int { held.count }

    /// What number `windowID` is currently holding, or 1 if it holds none.
    ///
    /// A read, deliberately separate from `claim`: claiming *releases first*
    /// (the window is telling the roster it now shows something else), so
    /// re-claiming is not a way to ask "what am I?". Each window keeps its own
    /// ordinal in `@State`; this exists so the never-renumber property can be
    /// observed from outside rather than inferred.
    func ordinal(for windowID: UUID) -> Int {
        held[windowID]?.ordinal ?? 1
    }

    /// Take an ordinal for `windowID` now showing `group`, releasing whatever it
    /// held before. `1` means "no suffix" — the first window on a study's lens
    /// is titled plainly, and only the second onwards is numbered.
    ///
    /// **Lowest free number, and nobody is ever renumbered** (decided 16 Aug
    /// 2026). Close the second of three and you are left with "Study" and
    /// "Study 3" — a gap, kept on purpose: renumbering would change a window's
    /// name while the researcher is looking at it, which is the same
    /// unlearnable-rule objection this design uses against a time-based
    /// restore. A window opened later fills the gap, so the numbers stay small.
    ///
    /// The honest consequence: close the *first* of two and the survivor stays
    /// "Study 2" on its own. Odd-looking, and still better than the alternative,
    /// which is a title that changes because something happened in a different
    /// window.
    @discardableResult
    func claim(windowID: UUID, showing group: Group?) -> Int {
        release(windowID: windowID)
        guard let group else {
            // Still a window, still counts for `hasProjectWindow` — just not a
            // member of any duplicate group.
            held[windowID] = (nil, 1)
            return 1
        }

        var used = taken[group] ?? []
        var ordinal = 1
        while used.contains(ordinal) { ordinal += 1 }
        used.insert(ordinal)
        taken[group] = used
        held[windowID] = (group, ordinal)
        return ordinal
    }

    /// Give back whatever `windowID` holds. Safe to call for a window that
    /// holds nothing.
    func release(windowID: UUID) {
        guard let (group, ordinal) = held.removeValue(forKey: windowID),
              let group else { return }
        taken[group]?.remove(ordinal)
        if taken[group]?.isEmpty == true { taken[group] = nil }
    }

    /// The suffix for an ordinal: nothing for the first, " 2" onwards.
    ///
    /// A plain space and digits, not "(2)" or "#2" — Terminal and Xcode both
    /// number this way, and parentheses are already spoken for here by the
    /// window subtitle, which AppKit renders as `Title (Subtitle)`.
    static func suffix(for ordinal: Int) -> String {
        ordinal > 1 ? " \(ordinal)" : ""
    }

    /// Test seam — drops every claim. Not called by the app.
    func resetForTesting() {
        taken.removeAll()
        held.removeAll()
    }
}
