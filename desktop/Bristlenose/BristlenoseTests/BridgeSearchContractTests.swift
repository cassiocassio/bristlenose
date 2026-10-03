import Foundation
import Testing

@testable import Bristlenose

/// The search bridge, native side, against the shared contract fixture
/// (`tests/fixtures/search-bridge-contract.json`, docs/design-search.md §7).
/// The SPA's `searchBridge.test.ts` asserts it builds every `wire` payload;
/// this suite asserts BridgeHandler decodes each one as it arrives, tolerates
/// kinds it does not know, and sends back exactly the payloads the SPA applies.
/// A field added on one side and not the other fails one of the two suites —
/// the wire-contract gotcha in root CLAUDE.md, closed for this channel.
@Suite("Search bridge contract")
@MainActor
struct BridgeSearchContractTests {

    nonisolated private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/search-bridge-contract.json")

    private func contract() throws -> [String: Any] {
        let data = try Data(contentsOf: Self.fixtureURL)
        return try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func webToNative() throws -> [String: Any] {
        try #require(try contract()["web_to_native"] as? [String: Any])
    }

    // MARK: web → native

    @Test func suggestionsDecodeAsTheSPASendsThem() throws {
        let cases = try #require(try webToNative()["search_suggestions"] as? [[String: Any]])
        let first = try #require(cases.first?["wire"] as? [String: Any])

        let bridge = BridgeHandler()
        bridge.handleMessage(first.merging(["type": "search-suggestions"]) { a, _ in a })

        let menu = bridge.searchSuggestions
        #expect(menu.query == "zo")
        #expect(menu.rows.map(\.id) == ["text", "person:p3", "person:p9", "tag:zoning"])
        #expect(menu.rows.map(\.kind) == [.text, .person, .person, .tag])
        #expect(menu.rows.map(\.count) == [4, 2, 1, 1])
        #expect(menu.rows[1].code == "p3")
        #expect(menu.rows[3].code == nil)
        #expect(menu.rows[2].typed.isEmpty)
    }

    /// The offsets are UTF-16, and the person's label opens with a ZWJ emoji
    /// and carries an accented letter: walking `Character`s would land the
    /// emphasis on "ë " instead of "Zo".
    @Test func typedOffsetsLandOnTheTypedLetters() throws {
        let cases = try #require(try webToNative()["search_suggestions"] as? [[String: Any]])
        let wire = try #require(cases.first?["wire"] as? [String: Any])
        let menu = SearchSuggestions(message: wire)

        let person = menu.rows[1]
        #expect(person.typedRanges.map { String(person.label[$0]) } == ["Zo"])
        let text = menu.rows[0]
        #expect(text.typedRanges.map { String(text.label[$0]) } == ["zo"])
    }

    @Test func anEmptyMenuClosesTheNativeOne() throws {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "search-suggestions", "query": "zo", "rows": [[
            "id": "text", "kind": "text", "label": "x", "typed": [], "count": 1,
        ]]])
        #expect(!bridge.searchSuggestions.rows.isEmpty)
        bridge.handleMessage(["type": "search-suggestions", "query": "", "rows": []])
        #expect(bridge.searchSuggestions == .empty)
    }

    @Test func tokensDecodeFromQuotesFilter() throws {
        let cases = try #require(try webToNative()["quotes_filter_tokens"] as? [[String: Any]])
        let wire = try #require(cases.first?["wire"])

        let bridge = BridgeHandler()
        bridge.handleMessage([
            "type": "quotes-filter", "searchQuery": "", "viewMode": "all", "tokens": wire,
        ])

        let tokens = bridge.quotesSearchTokens
        #expect(tokens.map(\.subject) == [
            .person(code: "p3"), .person(code: "p9"), .tag(name: "Zoning"),
        ])
        #expect(tokens[0].label == "Zoë O'Brien <Ng>")  // drawn as sent, unescaped
        #expect(tokens.map(\.styleKey) == ["p3", "p9", "zoning"])
        #expect(tokens[0].mode == "mentions")
        #expect(tokens[1].modes.map(\.enabled) == [true, false, true])
        #expect(tokens[2].modes.map(\.label) == [
            "Tagged “Zoning”", "Text contains “Zoning”", "Not tagged “Zoning”",
        ])
    }

    /// Before tokens existed, `quotes-filter` carried no `tokens` field. An
    /// older SPA (an export opened in a newer app) must still mean "none".
    @Test func aQuotesFilterWithoutTokensMeansNone() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "quotes-filter", "searchQuery": "kiosk", "viewMode": "all"])
        #expect(bridge.quotesSearchQuery == "kiosk")
        #expect(bridge.quotesSearchTokens.isEmpty)
    }

    @Test func unknownKindsAreDroppedNotFatal() throws {
        let tolerant = try #require(try webToNative()["swift_tolerates"] as? [String: Any])
        let menuWire = try #require(tolerant["search_suggestions"] as? [String: Any])

        let bridge = BridgeHandler()
        bridge.handleMessage(menuWire.merging(["type": "search-suggestions"]) { a, _ in a })
        #expect(bridge.searchSuggestions.rows.map(\.id) == ["tag:posture"])

        bridge.handleMessage([
            "type": "quotes-filter", "searchQuery": "", "viewMode": "all",
            "tokens": tolerant["tokens"] as Any,
        ])
        #expect(bridge.quotesSearchTokens.map(\.subject) == [.tag(name: "Posture")])
    }

    @Test func outOfRangeOffsetsAreDroppedNotTrusted() {
        let row = SearchSuggestionRow(wire: [
            "id": "tag:a", "kind": "tag", "label": "Ab", "count": 1,
            "typed": [[0, 1], [1, 9], [2, 1], [-1, 1], [0]],
        ])
        #expect(row?.typed == [0..<1])
    }

    @Test func resetClearsTheMenuAndTokens() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "search-suggestions", "query": "zo", "rows": [[
            "id": "text", "kind": "text", "label": "x", "typed": [], "count": 1,
        ]]])
        bridge.handleMessage(["type": "quotes-filter", "searchQuery": "", "viewMode": "all", "tokens": [[
            "kind": "tag", "subject": ["kind": "tag", "name": "Zoning"], "label": "Zoning",
            "mode": "tagged", "modes": [],
        ]]])
        bridge.reset()
        #expect(bridge.searchSuggestions == .empty)
        #expect(bridge.quotesSearchTokens.isEmpty)
    }

    // MARK: native → web

    /// Every native→web payload in the fixture is one our senders produce, so
    /// the SPA's half of the contract (which applies these payloads) is
    /// exercised by what this app actually sends.
    @Test func sendersBuildTheContractPayloads() throws {
        let nativeToWeb = try #require(try contract()["native_to_web"] as? [String: Any])
        let cases = try #require(nativeToWeb["cases"] as? [[String: Any]])
        var checked = 0
        for c in cases {
            let action = try #require(c["action"] as? String)
            let payload = try #require(c["payload"] as? [String: Any])
            let built: (String, [String: Any])
            switch action {
            case "applySearchSuggestion":
                built = SearchBridgeAction.applySuggestion(id: try #require(payload["id"] as? String))
            case "setSearchTokenMode", "removeSearchToken":
                // A subject this app cannot express (a future kind) is never
                // sent by it; the SPA's half pins that it ignores one.
                guard let subject = SearchSubject(wire: payload["subject"]) else { continue }
                built = action == "removeSearchToken"
                    ? SearchBridgeAction.removeToken(subject)
                    : SearchBridgeAction.setTokenMode(subject, mode: try #require(payload["mode"] as? String))
            default:
                Issue.record("unknown action \(action) in the contract")
                continue
            }
            #expect(built.0 == action)
            #expect(NSDictionary(dictionary: built.1).isEqual(to: payload), "\(c["name"] ?? action)")
            checked += 1
        }
        #expect(checked == cases.count - 1)  // all but the future-kind subject
    }
}
