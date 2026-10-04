import AppKit
import Foundation
import Testing

@testable import Bristlenose

/// The person picker bridge, native side, against the shared contract fixture
/// (`tests/fixtures/person-picker-bridge-contract.json`). The SPA's
/// `personPickerBridge.test.ts` builds every `wire` and resolves every
/// `payload`; this suite decodes each `wire` as BridgeHandler receives it and
/// builds exactly the payloads the SPA resolves.
@Suite("Person picker bridge contract")
@MainActor
struct PersonPickerContractTests {

    nonisolated private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/person-picker-bridge-contract.json")

    private func contract() throws -> [String: Any] {
        let data = try Data(contentsOf: Self.fixtureURL)
        return try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func wires() throws -> [[String: Any]] {
        let cases = try #require(try contract()["web_to_native"] as? [[String: Any]])
        return try cases.map { try #require($0["wire"] as? [String: Any]) }
    }

    @Test func everyRequestDecodesAsTheSPASendsIt() throws {
        let requests = try wires().map { PersonPickerRequest(message: $0) }
        let moderator = try #require(requests[0])
        #expect(moderator.sessionId == "s1")
        #expect(moderator.slot == .init(code: "m1", role: .moderator, name: "Martin B Storey", confirmed: false))
        #expect(moderator.names == ["Kerri Ng", "Martin B Storey"])
        #expect(moderator.anchor == CGRect(x: 10, y: 21, width: 30, height: 18))
        #expect(moderator.labels.roles[.observer] == "Observer")
        #expect(moderator.labels.newPrompt == "New moderator")
        #expect(moderator.labels.thatsMe == "That’s Me ({{name}})")

        #expect(moderator.labels.proposed == "m1, proposed name Martin B Storey")

        let participant = try #require(requests[1])
        #expect(participant.slot.role == .participant)
        #expect(participant.labels.thatsMe == nil)
        #expect(participant.labels.proposed == nil)
        #expect(participant.labels.newPrompt == "New name for p3")
    }

    @Test func aRequestMissingWhatItNeedsIsDropped() throws {
        var wire = try wires()[0]
        wire["slot"] = ["role": "moderator"]   // no code
        #expect(PersonPickerRequest(message: wire) == nil)
    }

    @Test func picksAreSentAsTheSPAResolvesThem() throws {
        let cases = try #require(try contract()["native_to_web"] as? [[String: Any]])
        for c in cases {
            let native = try #require(c["native"] as? [String: String])
            let (action, payload) = PersonPickerAction.choose(
                sessionId: try #require(native["sessionId"]),
                code: try #require(native["code"]),
                name: try #require(native["name"]))
            #expect(action == "personPickerChoose")
            let expected = try #require(c["payload"] as? NSDictionary)
            #expect(NSDictionary(dictionary: payload) == expected)
        }
    }

    @Test func thatsMeAppearsOnlyWhereTheRoleHasItAndTheAccountHasAName() throws {
        let requests = try wires().compactMap { PersonPickerRequest(message: $0) }
        let mod = PersonPickerModel(request: requests[0], meName: "Martin Storey",
                                    onChoose: { _ in }, onClose: {})
        #expect(mod.rows.last == PersonPickerModel.meRow)
        #expect(mod.thatsMeLabel == "That’s Me (Martin Storey)")

        let nameless = PersonPickerModel(request: requests[0], meName: "  ",
                                         onChoose: { _ in }, onClose: {})
        #expect(!nameless.rows.contains(PersonPickerModel.meRow))

        let participant = PersonPickerModel(request: requests[1], meName: "Martin Storey",
                                            onChoose: { _ in }, onClose: {})
        #expect(!participant.rows.contains(PersonPickerModel.meRow))
    }

    /// A Mac menu is as wide as its widest item: a long That's Me name widens
    /// the picker instead of being cut off (the first render truncated it).
    @Test func thePickerIsAsWideAsItsWidestRow() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        let short = PersonPickerModel(request: request, meName: "Jo", onChoose: { _ in }, onClose: {})
        let long = PersonPickerModel(request: request, meName: "Maximiliana Alexandrova-Whitworth",
                                     onChoose: { _ in }, onClose: {})
        #expect(long.contentWidth > short.contentWidth)
        let font = long.metrics.nameFont
        let text = (long.thatsMeLabel! as NSString).size(withAttributes: [.font: font]).width
        #expect(long.contentWidth >= text + SpeakerBadgeView.width(for: "m1") + long.metrics.tickColumn)
        #expect(long.contentWidth <= 380)
    }

    /// The role labels are localised; a long set must widen the picker
    /// rather than squeeze the segments (Russian needs ~281 pt at Small).
    @Test func thePickerIsAtLeastAsWideAsItsRoleSegments() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        let l = request.labels
        let labels = PersonPickerRequest.Labels(
            roles: [.moderator: "Модератор", .participant: "Участник", .observer: "Наблюдатель"],
            roleGroup: l.roleGroup, newPrompt: l.newPrompt, thatsMe: l.thatsMe, menu: l.menu)
        let russian = PersonPickerRequest(sessionId: request.sessionId, slot: request.slot,
                                          names: request.names, anchor: request.anchor, labels: labels)
        let model = PersonPickerModel(request: russian, meName: "Jo", onChoose: { _ in }, onClose: {})
        #expect(model.segmentsWidth > 210)   // more than the floor leaves inside the padding
        #expect(model.contentWidth >= ceil(model.segmentsWidth) + 20)
    }

    /// The dotted ring and the grey name are visual; VoiceOver hears the
    /// proposed row as the SPA words it, and every other row as code and name.
    @Test func aProposedRowSaysSoToVoiceOver() throws {
        let requests = try wires().compactMap { PersonPickerRequest(message: $0) }
        let model = PersonPickerModel(request: requests[0], meName: "Jo", onChoose: { _ in }, onClose: {})
        #expect(model.accessibilityLabel(for: "Martin B Storey") == "m1, proposed name Martin B Storey")
        #expect(model.accessibilityLabel(for: "Kerri Ng") == "m1 Kerri Ng")
        let confirmed = PersonPickerModel(request: requests[1], onChoose: { _ in }, onClose: {})
        #expect(confirmed.accessibilityLabel(for: "Mary Adeyemi") == "p3 Mary Adeyemi")
    }

    @Test func theSelectionOpensOnTheAnswerAndAnUnknownSlotPreselectsNothing() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        let model = PersonPickerModel(request: request, onChoose: { _ in }, onClose: {})
        #expect(model.selection == "Martin B Storey")

        let unknown = PersonPickerRequest(
            sessionId: "s1", slot: .init(code: "m1", role: .moderator, name: "", confirmed: false),
            names: ["Kerri Ng"], anchor: .zero, labels: request.labels)
        #expect(PersonPickerModel(request: unknown, onChoose: { _ in }, onClose: {}).selection == nil)
    }

    @Test func choosingSendsTheNameAndCloses() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        var sent: [String] = []
        var closed = 0
        let model = PersonPickerModel(request: request, meName: "Martin Storey",
                                      onChoose: { sent.append($0) }, onClose: { closed += 1 })
        model.choose("Kerri Ng")
        model.choose(PersonPickerModel.meRow)
        model.choose(PersonPickerModel.newRow)   // the field row is typed into, not chosen
        model.draft = "  Mike Alvarez "
        model.submitDraft()
        #expect(sent == ["Kerri Ng", "Martin Storey", "Mike Alvarez"])
        #expect(closed == 3)
    }
}
