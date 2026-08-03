import SwiftUI
import Testing
@testable import Bristlenose

/// Pins the two decisions behind View ▸ Hide/Show Projects, lifted out of
/// `ViewMenuContent` so they're testable without a window.
///
/// What's worth pinning here is the `.detailOnly`-is-the-only-hidden-case rule:
/// `NavigationSplitViewVisibility` has four cases and three of them show the
/// first column, so a naive `== .all` check would report the sidebar hidden in
/// `.doubleColumn`/`.automatic` and render the label backwards. The round-trip
/// test guards the toggle staying an involution — a menu item that doesn't
/// return to its starting state after two invocations is the classic regression.
@Suite struct SidebarToggleTests {

    // MARK: - isVisible

    @Test func isVisible_onlyDetailOnlyCountsAsHidden() {
        #expect(SidebarToggle.isVisible(.detailOnly) == false)
        #expect(SidebarToggle.isVisible(.all))
        #expect(SidebarToggle.isVisible(.doubleColumn))
        #expect(SidebarToggle.isVisible(.automatic))
    }

    // MARK: - next

    @Test func next_hiddenExpandsToAll() {
        #expect(SidebarToggle.next(.detailOnly) == .all)
    }

    @Test func next_anyVisibleStateCollapses() {
        #expect(SidebarToggle.next(.all) == .detailOnly)
        #expect(SidebarToggle.next(.doubleColumn) == .detailOnly)
        #expect(SidebarToggle.next(.automatic) == .detailOnly)
    }

    /// Two toggles from a visible state return to a visible state (and vice
    /// versa) — the property the user actually feels at the keyboard.
    @Test func next_roundTripsVisibility() {
        for start in [NavigationSplitViewVisibility.all, .detailOnly, .doubleColumn, .automatic] {
            let once = SidebarToggle.next(start)
            let twice = SidebarToggle.next(once)
            #expect(SidebarToggle.isVisible(twice) == SidebarToggle.isVisible(start))
        }
    }

    /// `next` and `isVisible` must agree: toggling always flips visibility.
    @Test func next_alwaysFlipsVisibility() {
        for start in [NavigationSplitViewVisibility.all, .detailOnly, .doubleColumn, .automatic] {
            #expect(SidebarToggle.isVisible(SidebarToggle.next(start)) != SidebarToggle.isVisible(start))
        }
    }
}

/// Pins View ▸ Hide/Show All Sidebars — the umbrella over the projects column
/// and the two web panels.
///
/// The rule worth pinning is that *any* one showing means the item reads
/// "Hide". The tempting alternative — all three showing — inverts the item in
/// exactly the mixed arrangements it exists to collapse: with only the tag
/// sidebar open it would offer "Show All Sidebars", and pressing it would open
/// two more rather than clear the one. The command-pairing test guards the
/// other half: web and native must move the same direction, because native
/// owns the verb and the web side is deliberately not allowed to re-derive it.
@Suite struct AllSidebarsTests {

    // MARK: - anyShowing

    @Test func anyShowing_isTrueWhenAnySingleOneIsUp() {
        #expect(AllSidebars.anyShowing(projects: true, leftPanel: false, rightPanel: false))
        #expect(AllSidebars.anyShowing(projects: false, leftPanel: true, rightPanel: false))
        #expect(AllSidebars.anyShowing(projects: false, leftPanel: false, rightPanel: true))
    }

    @Test func anyShowing_isFalseOnlyWhenEverythingIsDown() {
        #expect(AllSidebars.anyShowing(projects: false, leftPanel: false, rightPanel: false) == false)
    }

    // MARK: - webAction / nextVisibility

    /// The two halves of one press must agree. If the web ever received
    /// `showAllSidebars` while the column collapsed, the item would half-work
    /// in a way no single-surface test would catch.
    @Test func hidingSendsHideAndCollapsesTheColumn() {
        #expect(AllSidebars.webAction(hiding: true) == "hideAllSidebars")
        #expect(AllSidebars.nextVisibility(.all, hiding: true) == .detailOnly)
        #expect(AllSidebars.nextVisibility(.doubleColumn, hiding: true) == .detailOnly)
    }

    @Test func showingSendsShowAndExpandsTheColumn() {
        #expect(AllSidebars.webAction(hiding: false) == "showAllSidebars")
        #expect(AllSidebars.nextVisibility(.detailOnly, hiding: false) == .all)
    }

    /// Unlike `SidebarToggle.next`, this is idempotent per direction, not an
    /// involution — the direction comes from `anyShowing`, so a repeated Hide
    /// must not bounce the column back open.
    @Test func nextVisibility_isIdempotentPerDirection() {
        let hiddenOnce = AllSidebars.nextVisibility(.all, hiding: true)
        #expect(AllSidebars.nextVisibility(hiddenOnce, hiding: true) == .detailOnly)
        let shownOnce = AllSidebars.nextVisibility(.detailOnly, hiding: false)
        #expect(AllSidebars.nextVisibility(shownOnce, hiding: false) == .all)
    }

    /// The end-to-end loop the user feels: everything up → press → everything
    /// down → press → the column is back.
    @Test func roundTripReturnsTheColumn() {
        var visibility = NavigationSplitViewVisibility.all
        var hiding = AllSidebars.anyShowing(projects: SidebarToggle.isVisible(visibility),
                                            leftPanel: true, rightPanel: true)
        #expect(hiding)
        visibility = AllSidebars.nextVisibility(visibility, hiding: hiding)

        // Web panels are closed now too, so the mirror reports them false.
        hiding = AllSidebars.anyShowing(projects: SidebarToggle.isVisible(visibility),
                                        leftPanel: false, rightPanel: false)
        #expect(hiding == false)
        visibility = AllSidebars.nextVisibility(visibility, hiding: hiding)
        #expect(SidebarToggle.isVisible(visibility))
    }
}
