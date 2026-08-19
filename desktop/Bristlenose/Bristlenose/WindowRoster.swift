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
final class WindowRoster: ObservableObject {

    static let shared = WindowRoster()

    /// Each live window's ordinal. Published because a window's number can
    /// change after it was handed out — see `compact`.
    @Published private(set) var assignments: [UUID: Int] = [:]

    /// What makes two windows duplicates: **the same row in the Window menu**.
    ///
    /// AppKit renders each row as `Title (Subtitle)`, so two windows collide
    /// exactly when the project *and* the subtitle match — which is the only
    /// time a number is telling the reader anything.
    ///
    /// This was keyed on the **lens** until 17 Aug 2026, on the stated
    /// assumption that "different lenses already read differently, because the
    /// subtitle carries the per-lens count". That assumption is false, and the
    /// first six-window run showed it: `countSubtitle` returns the session count
    /// for Project, for Sessions *and* for a window with no lens yet, so three
    /// windows drew `IKEA with uxfriends (1 Session · 18m)` three times — each
    /// alone in its own lens group, each therefore unnumbered. Keying on the
    /// rendered subtitle makes the collision test the same thing the reader is
    /// looking at, rather than a proxy for it.
    ///
    /// The folder disambiguator is not part of the key: it is derived from the
    /// project, and the key is already project-scoped, so two windows on one
    /// study always share it.
    struct Group: Hashable {
        let projectID: UUID
        /// The resting per-lens subtitle — `countSubtitle`, deliberately not the
        /// live run narration. A run's stage and ETA change every second, and
        /// keying on them would reshuffle numbers throughout a run.
        let subtitle: String
    }

    /// Ordinals in use per group. Gaps are kept while the group has members —
 /// see `claim` — and collapse only when one window is left, see `compact`.
    private var taken: [Group: Set<Int>] = [:]
    /// Every live project window, and the ordinal it holds. The group is
    /// optional because a window showing the welcome screen still **counts** as
    /// a window — a Dock click must not open a second one — it just isn't in any
    /// duplicate group, since two "Welcome" windows aren't worth numbering.
    private var held: [UUID: (group: Group?, ordinal: Int)] = [:]

    /// Master or child, decided once per window and never recomputed.
    ///
    /// Masters get projects, children get lenses (`design-workspace.md` §"What a
    /// child window is"). A child has no project of its own — its title is read
    /// from what is being served — which is what makes it impossible for a child
    /// to name a study it isn't showing.
    private var roles: [UUID: Role] = [:]

    enum Role: Equatable {
        /// Carries the project list and picks the study.
        case master
        /// Carries the lens rail only, and inherits the served study.
        case child
    }

    private init() {}

    /// What kind of window this is — assigned on first ask, then fixed.
    ///
    /// **The rule is "am I the first project window", not "does a master
    /// exist".** Those differ in exactly one state and it is the one that was
    /// decided 18 Aug 2026: with the master closed and children still open, a
    /// new window is a **child**, because ⌥⌘N means one thing everywhere —
    /// another lens window on the study I am looking at — and gaining a special
    /// case there buys a project list nobody asked for at the cost of a rule
    /// that no longer fits in a sentence. (The cost of that is a mild dead end;
    /// see the design doc, where it is accepted knowingly.)
    ///
    /// **Self is excluded deliberately.** Two observers register a window —
    /// `.onAppear` and `.onChange(of: windowGroup, initial: true)` — and their
    /// order is not guaranteed, so if `claim` happens to land first the window
    /// would find itself in `held` and conclude it had company. Excluding the
    /// asker makes the answer independent of that race, the same reasoning
    /// `anyProjectShown(excluding:)` already carries.
    ///
    /// **Fixed once**, so a master does not become a child the moment a second
    /// window opens beside it.
    func role(for windowID: UUID) -> Role {
        if let existing = roles[windowID] { return existing }
        let hasCompany = held.keys.contains { $0 != windowID }
        let assigned: Role = hasCompany ? .child : .master
        roles[windowID] = assigned
        return assigned
    }

    /// Whether any live window carries the project list.
    ///
    /// Read by the ⌥⌘N gate's zero-windows case. Note this is **not** what
    /// decides the role — see `role(for:)`.
    var hasMaster: Bool { roles.values.contains(.master) }

    /// Is any project window open? (Settings and the Import window are not
    /// project windows and are deliberately not counted.)
    var hasProjectWindow: Bool { !held.isEmpty }

    /// Number of live project windows — for tests and diagnostics.
    var count: Int { held.count }

    /// Is any window **other than this one** showing a project?
    ///
    /// The question the serve lifecycle has to ask before it tears anything
    /// down. Selection is per window; the sidecar is not. A window that
    /// deselects — or that has just opened and hasn't restored its project yet
    /// — used to stop the serve on everyone's behalf, which killed the port
    /// every other window's web view was mounted against.
    ///
    /// Excludes the asking window deliberately, so the answer doesn't depend on
    /// whether that window's own roster entry has been updated yet. Two
    /// observers drive this (`selection` and `windowGroup`) and their order
    /// isn't guaranteed.
    func anyProjectShown(excluding windowID: UUID) -> Bool {
        held.contains { $0.key != windowID && $0.value.group != nil }
    }

    /// What number `windowID` is currently holding, or 1 if it holds none.
    ///
    /// A read, deliberately separate from `claim`: claiming *releases first*
    /// (the window is telling the roster it now shows something else), so
    /// re-claiming is not a way to ask "what am I?".
    func ordinal(for windowID: UUID) -> Int {
        held[windowID]?.ordinal ?? 1
    }

    /// Take an ordinal for `windowID` now showing `group`, releasing whatever it
    /// held before. `1` means "no suffix" — the first window on a study's lens
    /// is titled plainly, and only the second onwards is numbered.
    ///
    /// **Lowest free number, and a window with company is never renumbered**
    /// (decided 16 Aug 2026). Close the second of three and you are left with
    /// "Study" and "Study 3" — a gap, kept on purpose: renumbering would change
    /// a window's name while the researcher is looking at it, which is the same
    /// unlearnable-rule objection this design uses against a time-based restore.
    /// A window opened later fills the gap, so the numbers stay small.
    ///
    /// The one exception is a window left **alone** in its group, which gives
    /// its number up — see `compact` for the case that earned it.
    @discardableResult
    func claim(windowID: UUID, showing group: Group?) -> Int {
        releaseOrdinal(windowID: windowID)
        guard let group else {
            // Still a window, still counts for `hasProjectWindow` — just not a
            // member of any duplicate group.
            held[windowID] = (nil, 1)
            assignments[windowID] = 1
            return 1
        }

        var used = taken[group] ?? []
        var ordinal = 1
        while used.contains(ordinal) { ordinal += 1 }
        used.insert(ordinal)
        taken[group] = used
        held[windowID] = (group, ordinal)
        assignments[windowID] = ordinal
        return ordinal
    }

    /// Give back whatever `windowID` holds. Safe to call for a window that
    /// holds nothing.
    func release(windowID: UUID) {
        releaseOrdinal(windowID: windowID)
        // The role goes with the window. Deliberately *not* reassigned to a
        // survivor: promotion was rejected (design doc, §"What a child window
        // is") — it would exist only to paper over there being one serve, would
        // be deleted at Stage 3b, and would change a window's shape while the
        // researcher is looking at it because a *different* window closed.
        roles.removeValue(forKey: windowID)
    }

    /// Give back the ordinal, keeping the window on the roster.
    ///
    /// **Split out from `release` on 18 Aug 2026, and the split is load-bearing.**
    /// `release` was doing two unrelated jobs — "this window now shows something
    /// else, take its number back" (called by `claim`) and "this window is gone"
    /// (called by `.onDisappear`). Harmless while a number was all it held; the
    /// moment a *role* was added, every `claim` silently wiped it and the first
    /// window would lose its project list the first time it changed lens. Caught
    /// by `masterDoesNotBecomeChild`, which is why that test exists.
    private func releaseOrdinal(windowID: UUID) {
        assignments.removeValue(forKey: windowID)
        guard let (group, ordinal) = held.removeValue(forKey: windowID),
              let group else { return }
        taken[group]?.remove(ordinal)
        if taken[group]?.isEmpty == true { taken[group] = nil }
        compact(group)
    }

    /// A window left alone in its group gives up its number.
    ///
    /// **Why this is not the renumbering that was rejected.** The gap rule
    /// exists so a window's name doesn't change because of something that
    /// happened in a *different* window, and it is kept exactly where it was
    /// decided: close the middle of three and you still have "Study" and
    /// "Study 3", because 1 is still held and nothing moves.
    ///
    /// This covers a case the decision was never shown, and which turned out to
    /// be the common one. Every window passes *through* the Project lens as it
    /// opens, so pressing ⌥⌘N four times claims 1–4 there; move three of them
    /// to other lenses and the survivor keeps whatever it grabbed in transit.
    /// The first real run of multi-window drew a window titled
    /// **"IKEA with uxfriends 4"** sitting alone on Project, with no 1, 2 or 3
    /// anywhere — a number disambiguating nothing, which is the one thing an
    /// ordinal must never be.
    ///
    /// So: an ordinal is shown only while it is telling the reader something.
    /// Alone in the group, it isn't.
    private func compact(_ group: Group) {
        let members = held.filter { $0.value.group == group }
        guard members.count == 1, let (id, entry) = members.first, entry.ordinal != 1
        else { return }
        taken[group] = [1]
        held[id] = (group, 1)
        assignments[id] = 1
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
        assignments.removeAll()
        // Roles are sticky by design, so a suite that forgot this would leak a
        // master from one case into the next and every later window would come
        // back a child.
        roles.removeAll()
    }
}
