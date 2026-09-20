import Foundation
import Testing
@testable import Bristlenose

struct DetailFloorTests {
    @Test func reportPaneCarriesTheWebFigure() {
        #expect(DetailFloor.resolve(webMinWidth: 968, showingReport: true) == 968)
    }

    @Test func unreportedIsAbsentNotZero() {
        #expect(DetailFloor.resolve(webMinWidth: 0, showingReport: true) == nil)
    }

    @Test func nonReportPanesEnforceNothing() {
        #expect(DetailFloor.resolve(webMinWidth: 968, showingReport: false) == nil)
    }
}

struct SidebarAutoCollapseTests {
    typealias A = SidebarAutoCollapse

    @Test func collapsesWhenTheDetailBesideTheSidebarWouldBeBelowTheFloor() {
        // 1100 − 220 = 880 < 968
        #expect(A.decide(windowWidth: 1100, sidebarWidth: 220, minWidth: 968, sidebarVisible: true, autoCollapsed: false) == .collapse)
    }

    @Test func leavesAShowingSidebarThatFits() {
        // 1200 − 220 = 980 ≥ 968
        #expect(A.decide(windowWidth: 1200, sidebarWidth: 220, minWidth: 968, sidebarVisible: true, autoCollapsed: false) == .none)
    }

    @Test func expandsOnlyWhatItTook() {
        // Hidden by the researcher: never ours to give back.
        #expect(A.decide(windowWidth: 1400, sidebarWidth: 220, minWidth: 968, sidebarVisible: false, autoCollapsed: false) == .none)
        // Hidden by us, and it fits again.
        #expect(A.decide(windowWidth: 1400, sidebarWidth: 220, minWidth: 968, sidebarVisible: false, autoCollapsed: true) == .expand)
        // Hidden by us, still too narrow.
        #expect(A.decide(windowWidth: 1100, sidebarWidth: 220, minWidth: 968, sidebarVisible: false, autoCollapsed: true) == .none)
    }

    @Test func expandThresholdEqualsCollapseThresholdSoItCannotOscillate() {
        // At exactly floor + sidebar: a showing column stays, a taken one comes back —
        // and once back, the same width reads as "stays".
        let w: CGFloat = 968 + 220
        #expect(A.decide(windowWidth: w, sidebarWidth: 220, minWidth: 968, sidebarVisible: false, autoCollapsed: true) == .expand)
        #expect(A.decide(windowWidth: w, sidebarWidth: 220, minWidth: 968, sidebarVisible: true, autoCollapsed: false) == .none)
    }

    @Test func expandUsesTheWidthTheColumnHad() {
        // Dragged to 300: 1250 − 300 = 950 < 968, so it does not come back yet,
        // where an ideal of 220 would have said it did (1030 ≥ 968) and then
        // re-collapsed on arrival.
        #expect(A.decide(windowWidth: 1250, sidebarWidth: 300, minWidth: 968, sidebarVisible: false, autoCollapsed: true) == .none)
    }

    @Test func noFloorMeansNoAction() {
        #expect(A.decide(windowWidth: 700, sidebarWidth: 220, minWidth: nil, sidebarVisible: true, autoCollapsed: false) == .none)
        #expect(A.decide(windowWidth: 0, sidebarWidth: 220, minWidth: 968, sidebarVisible: true, autoCollapsed: false) == .none)
    }
}
