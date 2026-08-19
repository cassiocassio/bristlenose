import Foundation
import Testing

@testable import Bristlenose

/// Ordinal assignment for duplicate window titles (mockup E4).
///
/// The rule under test is **never renumber a window that is already open** —
/// decided 16 Aug 2026, and the reason the roster hands out lowest-free rather
/// than recomputing positions. Its consequences are counter-intuitive enough
/// (gaps; a lone window that keeps a "2") that they are pinned individually:
/// each of these would look like a bug to someone who hadn't read the decision,
/// and the fix they'd reach for is exactly the renumbering being avoided.
@MainActor
@Suite("Window roster ordinals")
struct WindowRosterTests {

    private func freshRoster() -> WindowRoster {
        let roster = WindowRoster.shared
        roster.resetForTesting()
        return roster
    }

    private let study = UUID()
    private let other = UUID()

    /// Windows whose Window-menu rows read the same — the collision the ordinal
    /// exists to break. Keyed on the rendered subtitle, not the lens.
    private func row(_ id: UUID, _ subtitle: String = "20 Quotes") -> WindowRoster.Group {
        WindowRoster.Group(projectID: id, subtitle: subtitle)
    }

    // MARK: - Assignment

    @Test("the first window on a lens takes no suffix")
    func firstIsUnsuffixed() {
        let roster = freshRoster()
        let ordinal = roster.claim(windowID: UUID(), showing: row(study))
        #expect(ordinal == 1)
        #expect(WindowRoster.suffix(for: ordinal) == "")
    }

    @Test("a second window on the same lens is numbered")
    func secondIsNumbered() {
        let roster = freshRoster()
        _ = roster.claim(windowID: UUID(), showing: row(study))
        let second = roster.claim(windowID: UUID(), showing: row(study))
        #expect(second == 2)
        #expect(WindowRoster.suffix(for: second) == " 2")
    }

    @Test("windows whose rows differ don't collide")
    func differentSubtitlesAreSeparateGroups() {
        let roster = freshRoster()
        let onQuotes = roster.claim(windowID: UUID(), showing: row(study))
        let onCodebook = roster.claim(
            windowID: UUID(), showing: row(study, "4 Codebooks · 60 Tags"))
        // Different rows in the menu, so there is nothing to disambiguate and
        // neither takes a suffix.
        #expect(onQuotes == 1)
        #expect(onCodebook == 1)
    }

    @Test("different studies don't collide")
    func studiesAreSeparateGroups() {
        let roster = freshRoster()
        #expect(roster.claim(windowID: UUID(), showing: row(study)) == 1)
        #expect(roster.claim(windowID: UUID(), showing: row(other)) == 1)
    }

    @Test("the welcome screen isn't numbered")
    func noProjectMeansNoOrdinal() {
        let roster = freshRoster()
        #expect(roster.claim(windowID: UUID(), showing: nil) == 1)
        #expect(roster.claim(windowID: UUID(), showing: nil) == 1)
    }

    // MARK: - Never renumber

    @Test("closing the middle window leaves a gap")
    func gapIsKept() {
        let roster = freshRoster()
        let a = UUID(), b = UUID(), c = UUID()
        #expect(roster.claim(windowID: a, showing: row(study)) == 1)
        #expect(roster.claim(windowID: b, showing: row(study)) == 2)
        #expect(roster.claim(windowID: c, showing: row(study)) == 3)

        roster.release(windowID: b)

        // "Study" and "Study 3". c is NOT renumbered to 2 — a window's name must
        // not change because something happened in a different window.
        #expect(roster.ordinal(for: a) == 1)
        #expect(roster.ordinal(for: c) == 3)
    }

    @Test("a new window fills the gap, so the numbers stay small")
    func gapIsRefilled() {
        let roster = freshRoster()
        let a = UUID(), b = UUID(), c = UUID()
        _ = roster.claim(windowID: a, showing: row(study))
        _ = roster.claim(windowID: b, showing: row(study))
        _ = roster.claim(windowID: c, showing: row(study))
        roster.release(windowID: b)

        #expect(roster.claim(windowID: UUID(), showing: row(study)) == 2,
                "lowest free, not next-highest — otherwise ordinals climb forever")
    }

    @Test("a window left alone gives its number up")
    func lastOneStandingIsUnnumbered() {
        let roster = freshRoster()
        let a = UUID(), b = UUID()
        _ = roster.claim(windowID: a, showing: row(study))
        _ = roster.claim(windowID: b, showing: row(study))

        roster.release(windowID: a)

        // An ordinal exists to disambiguate. Alone, it disambiguates nothing,
        // and "Study 2" with no "Study" anywhere is just wrong.
        #expect(roster.ordinal(for: b) == 1)
    }

    @Test("a number grabbed in transit doesn't outlive the reason for it")
    func transitOrdinalIsGivenUp() {
        // The case the first real multi-window run drew: every window passes
        // through the Project lens as it opens, so ⌥⌘N four times claims 1–4
        // there. Move three of them to other lenses and the survivor was left
        // titled "IKEA with uxfriends 4" — alone on Project, with no 1, 2 or 3
        // anywhere.
        let roster = freshRoster()
        let windows = (0..<4).map { _ in UUID() }
        let project = row(study, "1 Session · 18m")
        for w in windows { _ = roster.claim(windowID: w, showing: project) }
        #expect(roster.ordinal(for: windows[3]) == 4)

        for (i, subtitle) in ["20 Quotes", "6 Signals", "4 Codebooks · 60 Tags"].enumerated() {
            _ = roster.claim(windowID: windows[i], showing: row(study, subtitle))
        }

        #expect(roster.ordinal(for: windows[3]) == 1, "alone on Project — no suffix")
    }

    @Test("the gap survives while the group still has members")
    func compactionDoesNotEatTheGap() {
        // The rule the gap decision was actually about, unchanged: 1 is still
        // held, so nothing moves and the third window keeps its 3.
        let roster = freshRoster()
        let a = UUID(), b = UUID(), c = UUID()
        _ = roster.claim(windowID: a, showing: row(study))
        _ = roster.claim(windowID: b, showing: row(study))
        _ = roster.claim(windowID: c, showing: row(study))

        roster.release(windowID: b)

        #expect(roster.ordinal(for: a) == 1)
        #expect(roster.ordinal(for: c) == 3)
    }

    // MARK: - Whose serve is it?

    @Test("a window opening with no project doesn't look like the last one")
    func anotherWindowStillShowsAProject() {
        // The question that decides whether the shared sidecar is torn down. A
        // new window starts with no selection, and used to stop the serve on
        // everyone's behalf — which reset every other window to the dashboard.
        let roster = freshRoster()
        let visible = UUID(), opening = UUID()
        _ = roster.claim(windowID: visible, showing: row(study))
        _ = roster.claim(windowID: opening, showing: nil)

        #expect(roster.anyProjectShown(excluding: opening))
        #expect(!roster.anyProjectShown(excluding: visible),
                "the only project window may stop the serve")
    }

    @Test("nobody showing a project means the serve is nobody's")
    func noProjectAnywhere() {
        let roster = freshRoster()
        let a = UUID()
        _ = roster.claim(windowID: a, showing: nil)
        #expect(!roster.anyProjectShown(excluding: UUID()))
    }

    @Test("switching lens releases the old group's ordinal")
    func switchingLensMovesGroups() {
        let roster = freshRoster()
        let a = UUID(), b = UUID()
        _ = roster.claim(windowID: a, showing: row(study))
        #expect(roster.claim(windowID: b, showing: row(study)) == 2)

        // b moves to Codebook — it is no longer a duplicate of a, so it drops
        // its suffix, and its old number is free for the next Quotes window.
        #expect(roster.claim(
            windowID: b,
            showing: row(study, "4 Codebooks · 60 Tags")) == 1)
        #expect(roster.claim(windowID: UUID(), showing: row(study)) == 2)
    }

    // MARK: - Is anything open?

    @Test("the roster knows when there is nothing to come back to")
    func hasProjectWindow() {
        let roster = freshRoster()
        #expect(!roster.hasProjectWindow, "no windows — a Dock click should open one")

        let a = UUID()
        _ = roster.claim(windowID: a, showing: row(study))
        #expect(roster.hasProjectWindow)

        // The welcome screen still counts: it IS a project window, just an
        // unselected one, and clicking the Dock shouldn't open a second.
        let b = UUID()
        _ = roster.claim(windowID: b, showing: nil)
        #expect(roster.count == 2)

        roster.release(windowID: a)
        roster.release(windowID: b)
        #expect(!roster.hasProjectWindow)
    }

    @Test("Project and Sessions collide, because they draw the same row")
    func sameSubtitleDifferentLensStillCollides() {
        // The bug the first six-window run drew. `countSubtitle` returns the
        // session count for Project, for Sessions AND for a window with no lens
        // yet — so three windows read `IKEA with uxfriends (1 Session · 18m)`.
        // Keyed on the lens they were three separate groups, each unnumbered,
        // and the menu showed the same row three times.
        let roster = freshRoster()
        let onProject = UUID(), onSessions = UUID(), onTranscript = UUID()
        let sameRow = "1 Session · 18m"

        #expect(roster.claim(windowID: onProject, showing: row(study, sameRow)) == 1)
        #expect(roster.claim(windowID: onSessions, showing: row(study, sameRow)) == 2)
        #expect(roster.claim(windowID: onTranscript, showing: row(study, sameRow)) == 3)
    }
}


// MARK: - Master and child

// Masters get projects, children get lenses. The role is what makes a child
// unable to name a study it isn't showing: it has no project of its own, so
// there is no second source to drift from the serve.
//
// Every case here is a state the researcher can reach by ordinary use, and two
// of them (the order race, and the master closing) are the ones that would
// otherwise be found by a cohort tester.
@MainActor
@Suite("Window roles", .serialized)
struct WindowRoleTests {

    private func fresh() -> WindowRoster {
        let r = WindowRoster.shared
        r.resetForTesting()
        return r
    }

    @Test("The first project window is the master")
    func firstWindowIsMaster() {
        let r = fresh()
        #expect(r.role(for: UUID()) == .master)
    }

    @Test("A window opened alongside one is a child")
    func secondWindowIsChild() {
        let r = fresh()
        let first = UUID()
        _ = r.role(for: first)
        r.claim(windowID: first, showing: nil)
        #expect(r.role(for: UUID()) == .child)
    }

    @Test("The role is fixed — a master stays a master when company arrives")
    func masterDoesNotBecomeChild() {
        // The whole point of caching it. Recomputed, a master would flip to
        // child the instant a second window opened beside it, and the project
        // list would vanish from the window the researcher was working in.
        let r = fresh()
        let master = UUID()
        #expect(r.role(for: master) == .master)
        r.claim(windowID: master, showing: nil)

        let child = UUID()
        #expect(r.role(for: child) == .child)
        r.claim(windowID: child, showing: nil)

        #expect(r.role(for: master) == .master, "asking again must not re-decide")
    }

    @Test("Restoring five windows at once yields one master, not five")
    func batchRestoreDoesNotMintFiveMasters() {
        // **The bug this method was rewritten for, seen on screen 18 Aug 2026:
        // five restored windows, five project lists.** At relaunch macOS brings
        // every window back at once, so several `.onAppear` blocks run before
        // the first `claim` — and while the company test read `held` (which only
        // `claim` writes) each of them saw an empty roster and took master.
        //
        // The batch is the shape that matters: no interleaved claims at all.
        let r = fresh()
        let windows = (0..<5).map { _ in UUID() }
        let roles = windows.map { r.role(for: $0) }

        #expect(roles.filter { $0 == .master }.count == 1,
                "exactly one window carries the project list")
        #expect(roles.first == .master, "and it is the first one back")
        #expect(roles.dropFirst().allSatisfy { $0 == .child })
    }

    @Test("Asking is enough — a window never claimed still counts as company")
    func askingRegisters() {
        // The property the fix turns on: `role(for:)` writes its own answer, so
        // it does not depend on a second observer having run.
        let r = fresh()
        _ = r.role(for: UUID())
        #expect(r.role(for: UUID()) == .child)
    }

    @Test("Claiming before asking does not make the first window a child")
    func roleSurvivesTheObserverRace() {
        // Two observers register a window — .onAppear and .onChange(initial:) —
        // and their order is not guaranteed. If claim lands first the window is
        // already in `held`, so a rule that asked "is anyone here" without
        // excluding the asker would call the very first window a child and ship
        // an app whose only window has no project list.
        let r = fresh()
        let only = UUID()
        r.claim(windowID: only, showing: nil)
        #expect(r.role(for: only) == .master)
    }

    @Test("With the master closed, a new window is still a child")
    func childrenOnlyYieldsAnotherChild() {
        // Decided 18 Aug 2026, and it is the one case where "am I first" and
        // "does a master exist" disagree. ⌥⌘N means one thing everywhere —
        // another lens window on the study I am looking at — and the cost (no
        // route back to a project list without closing everything) is accepted
        // knowingly rather than patched with a special case.
        let r = fresh()
        let master = UUID(), child = UUID()
        _ = r.role(for: master); r.claim(windowID: master, showing: nil)
        _ = r.role(for: child);  r.claim(windowID: child, showing: nil)

        r.release(windowID: master)
        #expect(r.hasMaster == false, "the role goes with the window — no promotion")
        #expect(r.role(for: UUID()) == .child)
    }

    @Test("A surviving child is not promoted")
    func noPromotion() {
        // Promotion would make a window change shape because a *different*
        // window closed, and it would be deleted at Stage 3b. Pinned so nobody
        // adds it back as a convenience.
        let r = fresh()
        let master = UUID(), child = UUID()
        _ = r.role(for: master); r.claim(windowID: master, showing: nil)
        _ = r.role(for: child);  r.claim(windowID: child, showing: nil)

        r.release(windowID: master)
        #expect(r.role(for: child) == .child)
    }

    @Test("Close everything and the next window is a master again")
    func emptyRosterRestoresAMaster() {
        // The documented way back from the orphan state: close every window,
        // then ⌥⌘N.
        let r = fresh()
        let a = UUID(), b = UUID()
        _ = r.role(for: a); r.claim(windowID: a, showing: nil)
        _ = r.role(for: b); r.claim(windowID: b, showing: nil)
        r.release(windowID: a); r.release(windowID: b)

        #expect(r.hasProjectWindow == false)
        #expect(r.role(for: UUID()) == .master)
    }
}


// MARK: - Which study a window is about

// The decision that closes constraint 5. A master picks its study; a child
// inherits the served one and has no selection to disagree with.
@MainActor
@Suite("Window project resolution")
struct WindowProjectResolutionTests {

    private func project(_ name: String, _ path: String) -> Project {
        Project(id: UUID(), name: name, path: path)
    }

    @Test("A master shows what it selected")
    func masterFollowsSelection() {
        let a = project("IKEA Study", "/s/a")
        let resolved = WindowProjectResolution.project(
            role: .master, selected: a, servedPath: "/s/a", projects: [a])
        #expect(resolved?.path == "/s/a")
    }

    @Test("A master mid-switch still names what the researcher clicked")
    func masterLeadsTheServe() {
        // Deliberate, and the reason the guard lives at the mount site instead
        // of here: after clicking B the title should say B immediately, with the
        // pane showing a boot state. A title that lagged back to A would be
        // lying about the click that just happened.
        let a = project("IKEA Study", "/s/a")
        let b = project("Nokia Diary", "/s/b")
        let resolved = WindowProjectResolution.project(
            role: .master, selected: b, servedPath: "/s/a", projects: [a, b])
        #expect(resolved?.path == "/s/b")
    }

    @Test("A child shows the served study, whatever anyone selected")
    func childFollowsTheServe() {
        // The whole point. Even handed a selection — which a child never has —
        // it takes the serve, so no argument between the two is representable.
        let a = project("IKEA Study", "/s/a")
        let b = project("Nokia Diary", "/s/b")
        let resolved = WindowProjectResolution.project(
            role: .child, selected: a, servedPath: "/s/b", projects: [a, b])
        #expect(resolved?.path == "/s/b",
                "a child must never be able to name a study it isn't showing")
    }

    @Test("A child with nothing served shows nothing")
    func childWithNoServe() {
        let a = project("IKEA Study", "/s/a")
        #expect(WindowProjectResolution.project(
            role: .child, selected: a, servedPath: nil, projects: [a]) == nil)
    }

    @Test("A child whose served path is not in the index shows nothing")
    func childWithUnknownServe() {
        // Fails to the welcome title rather than to a stale name. A window that
        // kept naming the last study it knew about is exactly the drift the
        // child shape exists to prevent.
        let a = project("IKEA Study", "/s/a")
        #expect(WindowProjectResolution.project(
            role: .child, selected: a, servedPath: "/s/gone", projects: [a]) == nil)
    }

    @Test("A master with no selection shows nothing, even while a serve runs")
    func masterOnWelcomeKeepsItsWelcome() {
        // A master that has gone back to the welcome screen while children keep
        // the serve up must not silently re-adopt the served study — it said
        // Welcome because the researcher deselected.
        let a = project("IKEA Study", "/s/a")
        #expect(WindowProjectResolution.project(
            role: .master, selected: nil, servedPath: "/s/a", projects: [a]) == nil)
    }
}
