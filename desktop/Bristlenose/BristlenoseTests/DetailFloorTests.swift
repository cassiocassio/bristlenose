import Foundation
import Testing
@testable import Bristlenose

struct DetailFloorTests {
    @Test func reportPaneDeclaresTheWebFigure() {
        #expect(DetailFloor.resolve(webMinWidth: 968, showingReport: true) == 968)
    }

    @Test func unreportedIsAbsentNotZero() {
        #expect(DetailFloor.resolve(webMinWidth: 0, showingReport: true) == nil)
    }

    @Test func nonReportPanesDeclareNothing() {
        #expect(DetailFloor.resolve(webMinWidth: 968, showingReport: false) == nil)
    }
}
