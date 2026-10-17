import AppKit
import Foundation
import Testing

@testable import Bristlenose

/// The transcript's timeline pulldown, native side (TimelineMenu.swift): the
/// request as BridgeHandler receives it, what is ticked, what a pick sends, and
/// where the menu goes.
@Suite("Timeline menu")
@MainActor
struct TimelineMenuTests {

    /// The shape `postTimelineMenu` sends (TimelineSplit.test.tsx pins the web side).
    private func wire(on: Bool = true, lanes: Int = 3) -> [String: Any] {
        [
            "type": "timeline-menu",
            "on": on,
            "lanes": lanes,
            "anchor": ["x": 600, "y": 12.5, "width": 110, "height": 24],
            "labels": [
                "journey": "User journey",
                "timeline": "Session timeline",
                "detail": "Timeline detail",
                "lanes": [
                    ["lanes": 2, "title": "Compact", "hint": "Sections · Moderator · Participant"],
                    ["lanes": 3, "title": "Standard", "hint": "+ Sentiment"],
                    ["lanes": 5, "title": "Full", "hint": "+ Themes"],
                ],
            ],
        ]
    }

    @Test func readsTheWire() throws {
        let r = try #require(TimelineMenuRequest(message: wire()))
        #expect(r.on)
        #expect(r.lanes == 3)
        #expect(r.anchor == CGRect(x: 600, y: 12.5, width: 110, height: 24))
        #expect(r.laneItems.map(\.lanes) == [2, 3, 5])
        #expect(r.laneItems[0].hint == "Sections · Moderator · Participant")
    }

    @Test func refusesAWireWithoutItsLabels() {
        var body = wire()
        body["labels"] = nil
        #expect(TimelineMenuRequest(message: body) == nil)
    }

    @Test func ticksTheStateShowingAndOnlyFlipsFromTheOtherRow() throws {
        let on = TimelineMenuEntry.entries(for: try #require(TimelineMenuRequest(message: wire(on: true))))
        #expect(on == [
            .item(title: "User journey", subtitle: nil, checked: false, pick: .toggle),
            .item(title: "Session timeline", subtitle: nil, checked: true, pick: .none),
            .separator,
            .header("Timeline detail"),
            .item(title: "Compact", subtitle: "Sections · Moderator · Participant", checked: false, pick: .lanes(2)),
            .item(title: "Standard", subtitle: "+ Sentiment", checked: true, pick: .lanes(3)),
            .item(title: "Full", subtitle: "+ Themes", checked: false, pick: .lanes(5)),
        ])
        let off = TimelineMenuEntry.entries(for: try #require(TimelineMenuRequest(message: wire(on: false))))
        #expect(off[0] == .item(title: "User journey", subtitle: nil, checked: true, pick: .none))
        #expect(off[1] == .item(title: "Session timeline", subtitle: nil, checked: false, pick: .toggle))
    }

    @Test func picksSendTheViewMenusOwnActions() {
        #expect(TimelineMenuEntry.Pick.none.action == nil)
        #expect(TimelineMenuEntry.Pick.toggle.action?.name == "toggleSessionTimeline")
        let lanes = TimelineMenuEntry.Pick.lanes(5).action
        #expect(lanes?.name == "setSessionTimelineLanes")
        #expect(lanes?.payload["lanes"] as? Int == 5)
    }

    @Test func theMenuHangsFromTheControlsRightEdgeBelowIt() {
        let anchor = NSRect(x: 600, y: 40, width: 110, height: 24)
        #expect(TimelineMenuEntry.origin(anchor: anchor, menuWidth: 240, flipped: true)
                == NSPoint(x: 470, y: 68))
        #expect(TimelineMenuEntry.origin(anchor: anchor, menuWidth: 240, flipped: false)
                == NSPoint(x: 470, y: 36))
    }
}
