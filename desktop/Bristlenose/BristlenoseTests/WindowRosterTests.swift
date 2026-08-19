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

// MARK: - Keeping a peer window in step with the serve

// The whole mechanism of the peer model, and the seam where this class of bug
// has already shipped twice in three days — `9f4183af` ("stop one window's
// selection from resetting all the others") and `29f70e33` ("one window's
// empty-sidebar click was deselecting all of them"). Third occurrence of a named
// pattern, so it gets a helper and a suite rather than a comment.
@MainActor
@Suite("Selection follows the served study")
struct SelectionSyncTests {

    private func project(_ name: String, _ path: String) -> Project {
        Project(id: UUID(), name: name, path: path)
    }

    @Test("A window on another study is moved to the served one")
    func followsTheServe() {
        let a = project("IKEA", "/s/a"), b = project("Nokia", "/s/b")
        #expect(SelectionSync.resolve(current: [.project(a.id)], served: b)
                == [.project(b.id)])
    }

    @Test("A window parked on Welcome stays there")
    func deselectIsLocal() {
        // Rule 1, and the reason it exists: propagating an empty selection is
        // the 17 Aug bug where one click on empty sidebar space sent every
        // window to Welcome and stopped the serve.
        let b = project("Nokia", "/s/b")
        #expect(SelectionSync.resolve(current: [], served: b) == nil)
    }

    @Test("A window already on the served study is left alone")
    func noRedundantWrite() {
        // Rule 2, and it is what breaks the feedback path rather than merely
        // tidying it: selection drives switchProject, so rewriting an
        // already-correct selection would re-enter the serve lifecycle in every
        // window on every publish.
        let a = project("IKEA", "/s/a")
        #expect(SelectionSync.resolve(current: [.project(a.id)], served: a) == nil)
    }

    @Test("Nothing served changes nothing")
    func nilServeIsNotAnInstruction() {
        // Rule 3. `stop()` used to leave `currentProjectPath` populated, and a
        // brand-new or volume-ejected study is deliberately unserved while
        // still being the thing its window is about.
        let a = project("IKEA", "/s/a")
        #expect(SelectionSync.resolve(current: [.project(a.id)], served: nil) == nil)
    }

    @Test("A multi-selection survives a sibling's click")
    func multiSelectIsNotDisturbed() {
        // Falls out of rule 1 rather than needing its own branch: three studies
        // being dragged into a folder is "not empty", so the drag is not yanked
        // out from under the researcher by a click in another window.
        let a = project("IKEA", "/s/a"), b = project("Nokia", "/s/b")
        let multi: Set<SidebarSelection> = [.project(a.id), .project(b.id)]
        #expect(SelectionSync.resolve(current: multi, served: b) == [.project(b.id)])
    }
}
