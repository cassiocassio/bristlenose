import Foundation
import Testing
@testable import Bristlenose

/// The page's word for what a right-click landed on, and the place a new window
/// opens at (docs/design-webview-context-menu.md §9). The page side is pinned by
/// `frontend/src/utils/contextPlace.test.ts`.
@Suite("Context place")
struct ContextPlaceTests {
    private static let moment: [String: Any] = [
        "click": "play", "verb": "show", "dest": "transcript",
        "path": "/report/sessions/s3#t-754", "media": ["key": "p2", "seconds": 754.5],
    ]

    @Test func readsARightClickOnATimecode() throws {
        let t = try #require(ContextTarget.from([
            "type": "context-target", "seq": 4, "place": Self.moment, "here": false, "card": NSNull(),
        ]))
        #expect(t.seq == 4)
        #expect(t.place?.click == .play)
        #expect(t.place?.media == ContextPlace.Media(key: "p2", seconds: 754.5))
        #expect(t.card == nil)
    }

    @Test func readsAQuoteCard() throws {
        let t = try #require(ContextTarget.from([
            "seq": 1, "place": NSNull(), "here": false,
            "card": ["domId": "q-s3-754", "starred": true, "place": Self.moment],
        ]))
        #expect(t.card?.domId == "q-s3-754")
        #expect(t.card?.starred == true)
    }

    /// A place this build doesn't know reads as no target at all, so the menu
    /// falls back to taking WebKit's risky items out and adding nothing.
    @Test func aPlaceThisBuildCannotReadIsNoTarget() {
        var place = Self.moment
        place["click"] = "teleport"
        #expect(ContextTarget.from(["seq": 1, "place": place, "here": false]) == nil)
    }

    @Test func aNewWindowPlaysOnlyWhenAskedAndThereIsARecording() throws {
        let data = try JSONSerialization.data(withJSONObject: Self.moment)
        let place = try JSONDecoder().decode(ContextPlace.self, from: data)
        #expect(WindowPlace(place: place, play: true).play?.seconds == 754.5)
        #expect(WindowPlace(place: place, play: false).play == nil)
    }

    @Test func aNewWindowLandsOnTheLensItsPathShows() {
        #expect(WindowPlace(path: "/report/sessions/s3#t-754", anchor: nil, play: nil).lens == .sessions)
        #expect(WindowPlace(path: "/report/quotes/#section-4", anchor: nil, play: nil).lens == .quotes)
    }

    @Test func theGoToPlacePayloadCarriesWhatTheReportNeeds() {
        let p = WindowPlace(path: "/report/sessions/s3#t-754", anchor: nil,
                            play: .init(key: "p2", seconds: 754.5)).payload
        #expect(p["path"] as? String == "/report/sessions/s3#t-754")
        #expect((p["play"] as? [String: Any])?["key"] as? String == "p2")
        #expect(p["anchor"] == nil)
    }

    @Test func aNewWindowRequestNeedsAPathToGoTo() {
        var place = Self.moment
        place["path"] = ""
        #expect(WindowPlace.from(message: ["place": place, "play": false]) == nil)
        #expect(WindowPlace.from(message: ["place": Self.moment, "play": true])?.play != nil)
    }
}

/// A seed carries its place to the new window, and a restored window comes back
/// without one.
@Suite("Window seed place")
struct WindowSeedPlaceTests {
    private let place = WindowPlace(path: "/report/sessions/s3#t-754", anchor: nil,
                                    play: .init(key: "p2", seconds: 754.5))

    @Test func aPlaceRoundTrips() throws {
        let seed = WindowSeed.fresh(project: UUID(), lens: "sessions", place: place)
        let back = try JSONDecoder().decode(WindowSeed.self, from: JSONEncoder().encode(seed))
        #expect(back == seed)
        #expect(back.place == place)
    }

    /// Restoration values written by builds before the place existed.
    @Test func aSeedFromBeforePlacesDecodesWithNone() throws {
        let id = UUID()
        let json = #"{"token":"\#(id.uuidString)","project":"\#(id.uuidString)","lens":"quotes"}"#
        let seed = try JSONDecoder().decode(WindowSeed.self, from: Data(json.utf8))
        #expect(seed.place == nil)
        #expect(seed.lens == "quotes")
    }

    @Test func aPlaceThisBuildCannotReadIsDroppedNotFatal() throws {
        let id = UUID()
        let json = #"{"token":"\#(id.uuidString)","project":"\#(id.uuidString)","place":{"nope":1}}"#
        let seed = try JSONDecoder().decode(WindowSeed.self, from: Data(json.utf8))
        #expect(seed.place == nil)
        #expect(seed.project == id)
    }

    @Test func consumingThePlaceKeepsTheWindowsIdentity() {
        let seed = WindowSeed.fresh(project: UUID(), lens: "sessions", place: place)
        let used = seed.withoutPlace
        #expect(used.place == nil)
        #expect(used.token == seed.token)
        #expect(used.project == seed.project)
        #expect(used.lens == seed.lens)
    }
}
