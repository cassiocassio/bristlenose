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
    /// The shipping rail, in order. Discussion is last, so the five older
    /// lenses keep ⌘1–⌘5 and it takes ⌘6.
    ///
    /// Read through `lenses(screens:)`, never `all`: `all` follows the machine's
    /// own Diagnostics preference, so a developer who has Diagnostics on would
    /// see this go red for a correct rail (the trap the Discussion preview's
    /// tests named while it rode a flag).
    @Test func shippingRail_hasOneRowPerLens_inSidebarOrder() {
        #expect(LensItem.lenses(screens: false).map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .signals, .discussion,
        ])
    }

    /// Diagnostics adds exactly one row, Screens, last — so every shipping lens
    /// keeps its number and Screens takes ⌘7.
    @Test func diagnostics_appendsScreensLast() {
        #expect(LensItem.lenses(screens: true).map(\.tab) == [
            .project, .sessions, .quotes, .codebook, .signals, .discussion, .screens,
        ])
        #expect(LensItem.lenses(screens: true).firstIndex { $0.tab == .screens } == 6)
    }

    /// `all` is the preference's rail: off by default, Screens with it on. The
    /// key is the Diagnostics preference itself, not a flag of its own, so the
    /// lens cannot be on while the menu that explains it is hidden.
    ///
    /// `rail(_:)` takes the domain so both states are read from a throwaway
    /// suite; `all` is then pinned to be `rail` of the app's own domain. The
    /// app's preference itself is never written — the test host is the real
    /// app, and a suite run must not switch a researcher's Diagnostics.
    @Test func all_followsTheDiagnosticsPreference() throws {
        let suite = "LensItemTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        #expect(LensItem.rail(defaults).contains { $0.tab == .screens } == false)
        defaults.set(true, forKey: DiagnosticsPreference.key)
        #expect(LensItem.rail(defaults).contains { $0.tab == .screens })
        #expect(LensItem.all.map(\.tab) == LensItem.rail(.standard).map(\.tab))
        #expect(LensItem.all.map(\.tab)
            == LensItem.lenses(screens: DiagnosticsPreference.isEnabled()).map(\.tab))
    }

    /// Every shipping tab has exactly one row; with Diagnostics on, every tab.
    @Test func rails_coverEveryTabExactlyOnce() {
        let shipping = LensItem.lenses(screens: false).map(\.tab)
        for tab in Tab.allCases where tab != .screens {
            #expect(shipping.filter { $0 == tab }.count == 1)
        }
        #expect(!shipping.contains(.screens))
        let diagnostic = LensItem.lenses(screens: true).map(\.tab)
        for tab in Tab.allCases {
            #expect(diagnostic.filter { $0 == tab }.count == 1)
        }
    }

    /// The icon resolves whatever the preference says — a remembered Screens
    /// lens must not draw a placeholder circle with Diagnostics off.
    @Test func screensIcon_resolvesWithDiagnosticsOff() {
        #expect(LensItem.systemImage(for: .screens) == "macwindow.on.rectangle")
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
        let icons = Dictionary(uniqueKeysWithValues: LensItem.lenses(screens: true).map { ($0.tab, $0.systemImage) })
        #expect(icons[.project] == "target")
        #expect(icons[.sessions] == "person.2")
        #expect(icons[.quotes] == "text.quote")
        #expect(icons[.codebook] == "tag")
        #expect(icons[.signals] == "square.grid.3x3")
        #expect(icons[.discussion] == "questionmark.bubble")
        #expect(LensItem.systemImage(for: .discussion) == "questionmark.bubble")
        #expect(icons[.screens] == "macwindow.on.rectangle")
    }

    @Test func ids_areUnique() {
        let ids = LensItem.lenses(screens: true).map(\.id)
        #expect(Set(ids).count == ids.count)
    }
}
