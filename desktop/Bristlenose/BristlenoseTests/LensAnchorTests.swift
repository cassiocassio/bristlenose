import Foundation
import Testing

@testable import Bristlenose

/// How a remembered position is applied, which differs by lens.
///
/// The case worth pinning hardest is **Sessions**: its position is a route, not
/// a scroll offset, so restoring it means navigating. Everything else on the
/// lens list scrolls, and getting Sessions wrong would look like the anchor
/// silently doing nothing rather than like a bug.
@Suite("Lens anchor")
struct LensAnchorTests {

    @Test("Quotes and Codebook scroll to a heading")
    func scrollingLenses() {
        #expect(LensAnchor.action(lens: .quotes, anchor: "theme-billing")
                == .scroll("theme-billing"))
        #expect(LensAnchor.action(lens: .codebook, anchor: "codebook-fw-nielsen")
                == .scroll("codebook-fw-nielsen"))
    }

    @Test("Sessions navigates instead of scrolling")
    func sessionsNavigates() {
        // A transcript is a route. Scrolling to an element called "s3" would
        // find nothing and quietly leave the reader on the grid.
        #expect(LensAnchor.action(lens: .sessions, anchor: "s3") == .session("s3"))
    }

    @Test("Analysis and Project land at the top")
    func lensesWithoutPositions() {
        // Decided 16 Aug 2026. Passing an anchor anyway — a stale one from
        // another lens — must still land at the top rather than be honoured.
        #expect(LensAnchor.action(lens: .analysis, anchor: "theme-billing") == .top)
        #expect(LensAnchor.action(lens: .project, anchor: "theme-billing") == .top)
    }

    @Test("nothing remembered means the top")
    func noAnchorMeansTop() {
        #expect(LensAnchor.action(lens: .quotes, anchor: nil) == .top)
        #expect(LensAnchor.action(lens: .quotes, anchor: "") == .top)
        #expect(LensAnchor.action(lens: nil, anchor: "theme-billing") == .top)
    }

    @Test("only the lenses that can restore a position record one")
    func remembersPosition() {
        // The gate on *writing*. Without it, switching to Analysis would leave
        // the Quotes anchor on disk, and the next open would try to apply it.
        #expect(LensAnchor.remembersPosition(.quotes))
        #expect(LensAnchor.remembersPosition(.codebook))
        #expect(LensAnchor.remembersPosition(.sessions))
        #expect(!LensAnchor.remembersPosition(.analysis))
        #expect(!LensAnchor.remembersPosition(.project))
        #expect(!LensAnchor.remembersPosition(nil))
    }

    @Test("every lens that records a position can also apply one")
    func recordAndApplyAgree() {
        // The two halves are separate switches over the same list, and a lens
        // added to one but not the other would store a position it then ignores
        // — silent, and only visible as "restore doesn't work on that lens".
        for tab in Tab.allCases {
            let applies = LensAnchor.action(lens: tab, anchor: "x") != .top
            #expect(applies == LensAnchor.remembersPosition(tab), "\(tab) disagrees")
        }
    }
}
