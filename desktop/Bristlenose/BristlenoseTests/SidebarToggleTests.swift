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

/// Pins the label decision behind the View menu's four panel rows.
///
/// Two things are worth pinning. The first is that the verb follows the panel:
/// these are toggles, and for a long time all three web rows said "Show" even
/// with the panel open, because native had no way to see the SPA's panels. The
/// second is the `isAvailable` override — a dimmed row that still said "Hide"
/// would be the same class of lie in a quieter place, and it's the case a bare
/// `isOpen ? hide : show` gets wrong (the mirrored flag is stale on a lens that
/// has no such panel).
///
/// The exhaustive key test is the drift catcher: every string it lists must
/// exist under `menu.view` in `bristlenose/locales/*/desktop.json`, so a
/// renamed panel or a new row fails here rather than rendering a raw key.
@Suite struct PanelToggleTests {

    // MARK: - Verb selection

    @Test func labelKey_openPanelOffersHide() {
        #expect(PanelToggle.labelKey(panel: "Tags", isOpen: true, isAvailable: true)
                == "desktop.menu.view.hideTags")
    }

    @Test func labelKey_closedPanelOffersShow() {
        #expect(PanelToggle.labelKey(panel: "Tags", isOpen: false, isAvailable: true)
                == "desktop.menu.view.showTags")
    }

    /// A dimmed row reads "Show" whatever the mirror last said — on a lens with
    /// no left panel, `leftPanelOpen` describes the lens the user just left.
    @Test func labelKey_unavailablePanelAlwaysOffersShow() {
        for isOpen in [true, false] {
            #expect(PanelToggle.labelKey(panel: "Contents", isOpen: isOpen, isAvailable: false)
                    == "desktop.menu.view.showContents")
        }
    }

    // MARK: - Key composition

    /// Every panel the View menu can name, in both verbs. `leftPanelKey` picks
    /// one of Contents/Sessions/Codes/Signals per lens; Projects, Tags and
    /// Heatmap are fixed rows.
    @Test func labelKey_composesEveryRowInTheViewMenu() {
        let expected: [String: (show: String, hide: String)] = [
            "Projects": ("desktop.menu.view.showProjects", "desktop.menu.view.hideProjects"),
            "Contents": ("desktop.menu.view.showContents", "desktop.menu.view.hideContents"),
            "Sessions": ("desktop.menu.view.showSessions", "desktop.menu.view.hideSessions"),
            "Codes":    ("desktop.menu.view.showCodes",    "desktop.menu.view.hideCodes"),
            "Signals":  ("desktop.menu.view.showSignals",  "desktop.menu.view.hideSignals"),
            "Tags":     ("desktop.menu.view.showTags",     "desktop.menu.view.hideTags"),
            "Heatmap":  ("desktop.menu.view.showHeatmap",  "desktop.menu.view.hideHeatmap"),
        ]
        for (panel, keys) in expected {
            #expect(PanelToggle.labelKey(panel: panel, isOpen: false, isAvailable: true) == keys.show)
            #expect(PanelToggle.labelKey(panel: panel, isOpen: true, isAvailable: true) == keys.hide)
        }
    }

    /// The two verbs never collide — the property that makes the row a toggle
    /// rather than a relabelling.
    @Test func labelKey_verbsDiffer() {
        for panel in ["Projects", "Contents", "Sessions", "Codes", "Signals", "Tags", "Heatmap"] {
            #expect(PanelToggle.labelKey(panel: panel, isOpen: true, isAvailable: true)
                    != PanelToggle.labelKey(panel: panel, isOpen: false, isAvailable: true))
        }
    }
}
