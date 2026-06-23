import Testing
@testable import Bristlenose

/// Pins `LensItem.all` — the lens→Tab→icon mapping that the sidebar lens rail
/// introduces (spec §6.4, "the single silent-regression seam this change
/// introduces"). The lens→Tab *identity* is already covered by `TabTests`; this
/// suite tests what's genuinely new: the array's completeness, its sidebar order,
/// and the §5 icon assignments. A dropped row or a typo'd icon is a silent visual
/// regression these assertions catch.
@Suite struct LensItemTests {
    @Test func all_hasOneRowPerTab_inSidebarOrder() {
        #expect(LensItem.all.count == Tab.allCases.count)
        #expect(LensItem.all.map(\.tab) == [.project, .sessions, .quotes, .codebook, .analysis])
    }

    @Test func all_coversEveryTabExactlyOnce() {
        let tabs = LensItem.all.map(\.tab)
        for tab in Tab.allCases {
            #expect(tabs.filter { $0 == tab }.count == 1)
        }
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
