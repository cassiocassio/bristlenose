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
        #expect(moderator.slot == .init(code: "m1", role: .moderator, name: "Martin B Storey",
                                        confirmed: false, person: "id-martin"))
        #expect(moderator.labels.notThisPerson == "Not {{name}}")
        #expect(moderator.names == ["Kerri Ng", "Martin B Storey"])
        #expect(moderator.codes == ["m2", "m1"])
        #expect(moderator.newCode == "m3")
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
        #expect(participant.codes == ["p3"])
        #expect(participant.newCode == "p3")
        #expect(participant.others.isEmpty)
        #expect(participant.openRoles == [.participant])

        // A recode (§J7 R1): the observers, the speaker first under the next code.
        #expect(moderator.others.isEmpty, "an SPA that sends no roles leaves the segments off")
        let recode = try #require(requests[2])
        #expect(recode.openRoles == [.moderator, .observer])
        #expect(recode.others[.observer]
            == .init(names: ["Martin B Storey", "Ana Ruiz"], codes: ["o2", "o1"], newCode: "o3"))
        #expect(recode.newPrompt(for: .observer) == "New observer")
        #expect(recode.newPrompt(for: .moderator) == "New moderator")
    }

    /// Switching the segment to Observer shows the observers; a pick there is
    /// a recode, carrying the role, and nothing under it is the current answer.
    @Test func anotherRolesSegmentBrowsesItAndAPickThereRecodes() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }[2])
        var sent: [PersonPickerPick] = []
        let model = PersonPickerModel(request: request, meName: "Jo Bloggs",
                                      onChoose: { sent.append($0) }, onClose: {})
        #expect(model.names == ["Kerri Ng", "Martin B Storey"])
        #expect(model.isAnswer("Martin B Storey") && model.canClear && model.canRename("Martin B Storey"))

        model.browse(.participant)   // not open: nothing changes
        #expect(model.browsing == .moderator)

        model.browse(.observer)
        #expect(model.recoding)
        #expect(model.names == ["Martin B Storey", "Ana Ruiz"])
        #expect(model.code(for: "Martin B Storey") == "o2")
        #expect(model.newCode == "o3" && model.newPrompt == "New observer")
        #expect(model.selection == "Martin B Storey")
        #expect(!model.isAnswer("Martin B Storey") && !model.canClear && !model.canRename("Martin B Storey"))

        model.choose("Martin B Storey")   // not a rename here: the same person, recoded
        model.draft = "Mike Alvarez"
        model.submitDraft()
        #expect(sent == [
            PersonPickerPick(name: "Martin B Storey", kind: .name, role: .observer),
            PersonPickerPick(name: "Mike Alvarez", kind: .new, role: .observer),
        ])

        model.browse(.moderator)
        #expect(!model.recoding && model.isAnswer("Martin B Storey"))
    }

    /// The popover is sized for every role at once, so a segment never
    /// resizes it under the pointer.
    @Test func browsingARoleNeverResizesThePicker() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }[2])
        let model = PersonPickerModel(request: request, meName: "Jo", onChoose: { _ in }, onClose: {})
        let before = model.contentWidth
        model.browse(.observer)
        #expect(model.contentWidth == before)
        #expect(request.allCodes.contains("o3"))
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
            let kind = try #require(native["kind"].flatMap(PersonPickerPick.Kind.init(rawValue:)))
            let (action, payload) = PersonPickerAction.choose(
                sessionId: try #require(native["sessionId"]),
                code: try #require(native["code"]),
                pick: PersonPickerPick(name: try #require(native["name"]), kind: kind,
                                       role: native["role"].flatMap(PersonPickerRequest.Role.init(rawValue:))))
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
        #expect(model.accessibilityLabel(for: "Kerri Ng") == "m2 Kerri Ng")
        let confirmed = PersonPickerModel(request: requests[1], onChoose: { _ in }, onClose: {})
        #expect(confirmed.accessibilityLabel(for: "Mary Adeyemi") == "p3 Mary Adeyemi")
    }

    /// The badge's rect counts from the web viewport, which starts below the
    /// toolbar; the popover must point at the badge, not a toolbar's height above.
    @Test func thePopoverPointsAtTheBadgeBelowTheToolbar() {
        let badge = CGRect(x: 100, y: 200, width: 30, height: 18)
        let flipped = PersonPickerPresenter.viewRect(for: badge, zoom: 1, viewportTop: 52,
                                                     boundsHeight: 800, flipped: true)
        #expect(flipped == NSRect(x: 100, y: 252, width: 30, height: 18))
        let unflipped = PersonPickerPresenter.viewRect(for: badge, zoom: 1, viewportTop: 52,
                                                       boundsHeight: 800, flipped: false)
        #expect(unflipped == NSRect(x: 100, y: 800 - 52 - 218, width: 30, height: 18))
        let zoomed = PersonPickerPresenter.viewRect(for: badge, zoom: 2, viewportTop: 52,
                                                    boundsHeight: 800, flipped: true)
        #expect(zoomed == NSRect(x: 200, y: 452, width: 60, height: 36))
    }

    /// An unknown speaker has nothing to confirm, so the cursor starts in the
    /// new-person field (design-people.md §J8.10).
    @Test func theSelectionOpensOnTheAnswerAndAnUnknownSlotOpensInTheField() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        let model = PersonPickerModel(request: request, onChoose: { _ in }, onClose: {})
        #expect(model.selection == "Martin B Storey")

        let unknown = PersonPickerRequest(
            sessionId: "s1", slot: .init(code: "m1", role: .moderator, name: "", confirmed: false),
            names: ["Kerri Ng"], anchor: .zero, labels: request.labels)
        #expect(PersonPickerModel(request: unknown, onChoose: { _ in }, onClose: {}).selection
            == PersonPickerModel.newRow)
    }

    /// A picked row, That's Me and a typed name each say which they are, so
    /// the SPA never reads a typed name as a pick.
    /// Rename in place (design-people.md §J8.8): the current, confirmed row
    /// becomes a field; a proposed one is still confirmed by choosing it.
    @Test func theCurrentConfirmedRowRenamesInPlace() throws {
        let wire = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        let confirmed = PersonPickerRequest(
            sessionId: "s1",
            slot: .init(code: "m1", role: .moderator, name: "Martin B Storey", confirmed: true, person: "id-martin"),
            names: wire.names, codes: wire.codes, newCode: wire.newCode, anchor: .zero, labels: wire.labels)
        var sent: [PersonPickerPick] = []
        var closed = 0
        let model = PersonPickerModel(request: confirmed, onChoose: { sent.append($0) }, onClose: { closed += 1 })
        #expect(model.canRename("Martin B Storey"))
        #expect(!model.canRename("Kerri Ng"))

        model.choose("Martin B Storey")
        #expect(model.renaming)
        #expect(model.renameDraft == "Martin B Storey")
        #expect(sent.isEmpty && closed == 0)

        model.submitRename()   // unchanged: back to the list, nothing sent
        #expect(!model.renaming)
        #expect(sent.isEmpty && closed == 0)

        model.choose("Martin B Storey")
        model.renameDraft = " Martyn B Storey "
        model.submitRename()
        #expect(sent == [PersonPickerPick(name: "Martyn B Storey", kind: .rename)])
        #expect(closed == 1)

        // A proposed answer is not renamed: choosing it is the yes.
        let proposed = PersonPickerModel(request: wire, onChoose: { _ in }, onClose: {})
        #expect(!proposed.canRename("Martin B Storey"))
    }

    /// The ✕ refuses the current answer: only for a moderator or observer the
    /// slot points at, and its reply names nobody (design-people.md §J8.8).
    @Test func theCrossClearsOnlyAKnownModeratorOrObserver() throws {
        let requests = try wires().compactMap { PersonPickerRequest(message: $0) }
        var sent: [PersonPickerPick] = []
        var closed = 0
        let moderator = PersonPickerModel(request: requests[0], onChoose: { sent.append($0) },
                                          onClose: { closed += 1 })
        #expect(moderator.canClear)
        moderator.clearCurrent()
        #expect(sent == [PersonPickerPick(name: "", kind: .clear)])
        #expect(closed == 1)

        let participant = PersonPickerModel(request: requests[1], onChoose: { sent.append($0) },
                                            onClose: { closed += 1 })
        #expect(!participant.canClear)
        participant.clearCurrent()
        #expect(sent.count == 1, "a participant has nothing to clear")

        let (_, payload) = PersonPickerAction.choose(
            sessionId: "s1", code: "m1", pick: PersonPickerPick(name: "", kind: .clear))
        #expect(NSDictionary(dictionary: payload)
            == NSDictionary(dictionary: ["sessionId": "s1", "code": "m1", "choice": ["kind": "clear"]]))
    }

    @Test func choosingSendsTheNameAndItsKindAndCloses() throws {
        let request = try #require(try wires().compactMap { PersonPickerRequest(message: $0) }.first)
        var sent: [PersonPickerPick] = []
        var closed = 0
        let model = PersonPickerModel(request: request, meName: "Martin Storey",
                                      onChoose: { sent.append($0) }, onClose: { closed += 1 })
        model.choose("Kerri Ng")
        model.choose(PersonPickerModel.meRow)
        model.choose(PersonPickerModel.newRow)   // the field row is typed into, not chosen
        model.draft = "  Mike Alvarez "
        model.submitDraft()
        #expect(sent == [
            PersonPickerPick(name: "Kerri Ng", kind: .name),
            PersonPickerPick(name: "Martin Storey", kind: .me),
            PersonPickerPick(name: "Mike Alvarez", kind: .new),
        ])
        #expect(closed == 3)
    }
}
