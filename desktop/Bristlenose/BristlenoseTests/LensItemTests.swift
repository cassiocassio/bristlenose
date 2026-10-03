import Foundation
import Testing
@testable import Bristlenose

/// Pins `LensItem.all` — the lens→Tab→icon mapping that the sidebar lens rail
/// introduces (spec §6.4, "the single silent-regression seam this change
/// introduces"). The lens→Tab *identity* is already covered by `TabTests`; this
/// suite tests what's genuinely new: the array's completeness, its sidebar order,
/// and the §5 icon assignments. A dropped row or a typo'd icon is a silent visual
/// regression these assertions catch.
@Suite struct LensItemTests {
    /// The rail, in order. Discussion is last, so the five older lenses keep
    /// ⌘1–⌘5 and it takes ⌘6. It was a flagged preview row until it shipped for
    /// beta on 3 Oct 2026; no flag remains, so no machine's defaults can hide it.
    @Test func all_hasOneRowPerTab_inSidebarOrder() {
        #expect(LensItem.all.map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .signals, .discussion,
        ])
    }

    /// Every tab has exactly one row.
    @Test func all_coversEveryTabExactlyOnce() {
        let tabs = LensItem.all.map(\.tab)
        for tab in Tab.allCases {
            #expect(tabs.filter { $0 == tab }.count == 1)
        }
    }

    /// The codebook route resolves, and a retired sibling does not resurrect.
    ///
    /// This guarded a prefix hazard: `/report/codebook-v2` has
    /// `/report/codebook` as a prefix, so the shorter test had to come second
    /// or it swallowed every v2 route silently. Both the route and the hazard
    /// retired with the v2 lens on 31 Aug 2026; the rule they taught is
    /// recorded in `Tab.from(path:)` for the next sibling that shares a prefix.
    @Test func from_resolvesTheCodebookRoute() {
        #expect(Tab.from(path: "/report/codebook/") == .codebook)
        #expect(Tab.from(path: "/report/codebook") == .codebook)
    }

    @Test func icons_matchSpecSection5() {
        let icons = Dictionary(uniqueKeysWithValues: LensItem.all.map { ($0.tab, $0.systemImage) })
        #expect(icons[.project] == "target")
        #expect(icons[.sessions] == "person.2")
        #expect(icons[.quotes] == "text.quote")
        #expect(icons[.codebook] == "tag")
        #expect(icons[.signals] == "square.grid.3x3")
        #expect(icons[.discussion] == "questionmark.bubble")
        #expect(LensItem.systemImage(for: .discussion) == "questionmark.bubble")
    }

    @Test func ids_areUnique() {
        let ids = LensItem.all.map(\.id)
        #expect(Set(ids).count == ids.count)
    }
}
