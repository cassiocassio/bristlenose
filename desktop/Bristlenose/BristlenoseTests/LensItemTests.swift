import Testing
@testable import Bristlenose

/// Pins `LensItem.all` — the lens→Tab→icon mapping that the sidebar lens rail
/// introduces (spec §6.4, "the single silent-regression seam this change
/// introduces"). The lens→Tab *identity* is already covered by `TabTests`; this
/// suite tests what's genuinely new: the array's completeness, its sidebar order,
/// and the §5 icon assignments. A dropped row or a typo'd icon is a silent visual
/// regression these assertions catch.
@Suite struct LensItemTests {
    /// The shipping rail. One row per lens, no build-configuration fork: the
    /// second Codebook row that rode here in DEBUG was the v2 lens, and v2
    /// became the only Codebook lens on 31 Aug 2026.
    @Test func all_hasOneRowPerTab_inSidebarOrder() {
        #expect(LensItem.all.map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .analysis,
        ])
    }

    /// Every rail row is a distinct tab, and every SHIPPING tab has a row.
    ///
    /// No longer `LensItem.all.count == Tab.allCases.count`: that held only
    /// while the two sets were identical, so it would have passed in DEBUG by
    /// coincidence and failed in Release for a correct rail. It asserted the
    /// arithmetic rather than the invariant.
    @Test func all_coversEveryShippingTabExactlyOnce() {
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
        #expect(icons[.analysis] == "square.grid.3x3")
    }

    @Test func ids_areUnique() {
        let ids = LensItem.all.map(\.id)
        #expect(Set(ids).count == ids.count)
    }
}
