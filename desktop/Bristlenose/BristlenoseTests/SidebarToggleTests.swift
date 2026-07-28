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
