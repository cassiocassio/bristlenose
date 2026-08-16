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

    private func quotes(_ id: UUID) -> WindowRoster.Group {
        WindowRoster.Group(projectID: id, lens: "quotes")
    }

    // MARK: - Assignment

    @Test("the first window on a lens takes no suffix")
    func firstIsUnsuffixed() {
        let roster = freshRoster()
        let ordinal = roster.claim(windowID: UUID(), showing: quotes(study))
        #expect(ordinal == 1)
        #expect(WindowRoster.suffix(for: ordinal) == "")
    }

    @Test("a second window on the same lens is numbered")
    func secondIsNumbered() {
        let roster = freshRoster()
        _ = roster.claim(windowID: UUID(), showing: quotes(study))
        let second = roster.claim(windowID: UUID(), showing: quotes(study))
        #expect(second == 2)
        #expect(WindowRoster.suffix(for: second) == " 2")
    }

    @Test("different lenses of one study don't collide")
    func lensesAreSeparateGroups() {
        let roster = freshRoster()
        let onQuotes = roster.claim(windowID: UUID(), showing: quotes(study))
        let onCodebook = roster.claim(
            windowID: UUID(),
            showing: WindowRoster.Group(projectID: study, lens: "codebook"))
        // Their subtitles already differ (each carries its own lens count), so
        // there is nothing to disambiguate and neither takes a suffix.
        #expect(onQuotes == 1)
        #expect(onCodebook == 1)
    }

    @Test("different studies don't collide")
    func studiesAreSeparateGroups() {
        let roster = freshRoster()
        #expect(roster.claim(windowID: UUID(), showing: quotes(study)) == 1)
        #expect(roster.claim(windowID: UUID(), showing: quotes(other)) == 1)
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
        #expect(roster.claim(windowID: a, showing: quotes(study)) == 1)
        #expect(roster.claim(windowID: b, showing: quotes(study)) == 2)
        #expect(roster.claim(windowID: c, showing: quotes(study)) == 3)

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
        _ = roster.claim(windowID: a, showing: quotes(study))
        _ = roster.claim(windowID: b, showing: quotes(study))
        _ = roster.claim(windowID: c, showing: quotes(study))
        roster.release(windowID: b)

        #expect(roster.claim(windowID: UUID(), showing: quotes(study)) == 2,
                "lowest free, not next-highest — otherwise ordinals climb forever")
    }

    @Test("closing the FIRST window leaves the survivor on its number")
    func survivorKeepsItsNumber() {
        let roster = freshRoster()
        let a = UUID(), b = UUID()
        _ = roster.claim(windowID: a, showing: quotes(study))
        _ = roster.claim(windowID: b, showing: quotes(study))

        roster.release(windowID: a)

        // A single window reading "Study 2" looks odd, and is the accepted cost
        // of never renumbering. Pinned so it reads as a decision rather than as
        // the bug it resembles.
        #expect(roster.ordinal(for: b) == 2)
    }

    @Test("switching lens releases the old group's ordinal")
    func switchingLensMovesGroups() {
        let roster = freshRoster()
        let a = UUID(), b = UUID()
        _ = roster.claim(windowID: a, showing: quotes(study))
        #expect(roster.claim(windowID: b, showing: quotes(study)) == 2)

        // b moves to Codebook — it is no longer a duplicate of a, so it drops
        // its suffix, and its old number is free for the next Quotes window.
        #expect(roster.claim(
            windowID: b,
            showing: WindowRoster.Group(projectID: study, lens: "codebook")) == 1)
        #expect(roster.claim(windowID: UUID(), showing: quotes(study)) == 2)
    }

    // MARK: - Is anything open?

    @Test("the roster knows when there is nothing to come back to")
    func hasProjectWindow() {
        let roster = freshRoster()
        #expect(!roster.hasProjectWindow, "no windows — a Dock click should open one")

        let a = UUID()
        _ = roster.claim(windowID: a, showing: quotes(study))
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
}
