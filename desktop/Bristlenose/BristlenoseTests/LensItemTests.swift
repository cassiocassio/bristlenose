import Testing
@testable import Bristlenose

/// Pins `LensItem.all` — the lens→Tab→icon mapping that the sidebar lens rail
/// introduces (spec §6.4, "the single silent-regression seam this change
/// introduces"). The lens→Tab *identity* is already covered by `TabTests`; this
/// suite tests what's genuinely new: the array's completeness, its sidebar order,
/// and the §5 icon assignments. A dropped row or a typo'd icon is a silent visual
/// regression these assertions catch.
@Suite struct LensItemTests {
    /// The shipping rail. Codebook v2 sits between Codebook and Analysis in
    /// DEBUG only (`docs/design-codebook-v2.md` D29) — a second Codebook row is
    /// nonsense to a researcher until the flag defaults on at phase 6.
    @Test func all_hasOneRowPerTab_inSidebarOrder() {
        #if DEBUG
        #expect(LensItem.all.map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .codebookV2, .analysis,
        ])
        #else
        #expect(LensItem.all.map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .analysis,
        ])
        #expect(!LensItem.all.contains { $0.tab == .codebookV2 })
        #endif
    }

    /// Every rail row is a distinct tab, and every SHIPPING tab has a row.
    ///
    /// No longer `LensItem.all.count == Tab.allCases.count`: that held only
    /// while the two sets were identical, so it would have passed in DEBUG by
    /// coincidence and failed in Release for a correct rail. It asserted the
    /// arithmetic rather than the invariant.
    @Test func all_coversEveryShippingTabExactlyOnce() {
        let tabs = LensItem.all.map(\.tab)
        for tab in Tab.allCases where tab != .codebookV2 {
            #expect(tabs.filter { $0 == tab }.count == 1)
        }
    }

    /// A route that is a prefix of another must not swallow it.
    ///
    /// `/report/codebook-v2` has `/report/codebook` as a prefix, so
    /// `Tab.from(path:)` has to test the longer one first. Getting this wrong
    /// is silent: every v2 route reports as the shipped lens, the rail
    /// highlights the wrong row, and nothing errors.
    @Test func from_prefersTheLongerCodebookPrefix() {
        #expect(Tab.from(path: "/report/codebook-v2/") == .codebookV2)
        #expect(Tab.from(path: "/report/codebook-v2") == .codebookV2)
        #expect(Tab.from(path: "/report/codebook/") == .codebook)
        #expect(Tab.from(path: "/report/codebook") == .codebook)
    }

    @Test func icons_matchSpecSection5() {
        let icons = Dictionary(uniqueKeysWithValues: LensItem.all.map { ($0.tab, $0.systemImage) })
        #expect(icons[.project] == "target")
        #expect(icons[.sessions] == "person.2")
        #expect(icons[.quotes] == "text.quote")
        #expect(icons[.codebook] == "tag")
        #if DEBUG
        #expect(icons[.codebookV2] == "tag.square")
        #endif
        #expect(icons[.analysis] == "square.grid.3x3")
    }

    @Test func ids_areUnique() {
        let ids = LensItem.all.map(\.id)
        #expect(Set(ids).count == ids.count)
    }
}
