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

    /// A ready the boot nets fabricate (didFinish's, the uncover ceiling's, a
    /// status page's) has no report to go to: the place waits for the real one
    /// instead of being spent on nothing.
    @Test func aPlaceWaitsForTheReportItself() {
        #expect(WindowSeed.placeArrival(hasPlace: true, document: .loading, lensIntentReplayed: false) == .wait)
        #expect(WindowSeed.placeArrival(hasPlace: true, document: .statusPage(.inProgress),
                                        lensIntentReplayed: false) == .wait)
        #expect(WindowSeed.placeArrival(hasPlace: true, document: .spa, lensIntentReplayed: false) == .go)
    }

    /// A lens clicked during boot wins, and the place is forgotten rather than
    /// left to send a restored window to the link later.
    @Test func aLensClickedDuringBootForgetsThePlace() {
        #expect(WindowSeed.placeArrival(hasPlace: true, document: .spa, lensIntentReplayed: true) == .forget)
        #expect(WindowSeed.placeArrival(hasPlace: false, document: .spa, lensIntentReplayed: true) == .none)
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

/// The page's right-click wire, decoded as the app receives it, against the
/// shared fixture `tests/fixtures/context-target-contract.json`. The SPA's
/// `contextPlace.test.ts` builds every `wire` from its builder; the decode here
/// is strict, so a value only one side knows would turn every target into none.
@Suite("Context target contract")
struct ContextPlaceContractTests {
    private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/context-target-contract.json")

    private func contract() throws -> [String: Any] {
        let data = try Data(contentsOf: Self.fixtureURL)
        return try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    @Test func everyPlaceThePageBuildsDecodes() throws {
        let cases = try #require(try contract()["places"] as? [[String: Any]])
        #expect(cases.count >= 7)
        for c in cases {
            let wire = try #require(c["wire"] as? [String: Any])
            let data = try JSONSerialization.data(withJSONObject: wire)
            let place = try JSONDecoder().decode(ContextPlace.self, from: data)
            #expect(place.path == wire["path"] as? String, "\(c["build"] ?? "?")")
            #expect(place.click.rawValue == wire["click"] as? String)
            #expect(place.verb.rawValue == wire["verb"] as? String)
            #expect(place.dest.rawValue == wire["dest"] as? String)
            #expect(place.anchor == wire["anchor"] as? String)
        }
    }

    @Test func everyTargetThePageReadsDecodes() throws {
        let cases = try #require(try contract()["targets"] as? [[String: Any]])
        for c in cases {
            let wire = try #require(c["wire"] as? [String: Any])
            let target = try #require(ContextTarget.from(wire), "\(c["what"] ?? "?")")
            #expect(target.seq == wire["seq"] as? Int)
            #expect((target.place != nil) == !(wire["place"] is NSNull))
            #expect((target.card != nil) == !(wire["card"] is NSNull))
        }
    }
}
