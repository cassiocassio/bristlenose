import Foundation
import Testing

@testable import Bristlenose

/// The register's whole claim is "this is what is exposed", so every row and
/// every headline number has to be derived from the same predicate the
/// handshake uses. These pin the derivation, not the rendering.
@Suite("AgentProjectRegister")
struct AgentProjectRegisterTests {

    private func candidate(_ name: String,
                           id: UUID = UUID(),
                           access: Bool = true,
                           sessions: Int? = 1,
                           lastAsked: Date? = nil) -> AgentProjectRegister.Candidate {
        .init(id: id, name: name, icon: nil, access: access,
              sessions: sessions, lastAsked: lastAsked)
    }

    // MARK: - Membership

    @Test("a project with access off is absent, not listed and unticked")
    func accessOffIsAbsent() {
        // The scope decision: the register is what you have shared or might be
        // sharing. An off project is neither.
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("off", access: false)], shown: [], receipts: [])
        #expect(rows.isEmpty)
    }

    @Test("unticking keeps the row for the session, as a receipt")
    func receiptSurvivesTheClick() {
        let id = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("revoked", id: id, access: false)],
            shown: [], receipts: [id])
        #expect(rows.count == 1)
        #expect(rows[0].access == false)
        #expect(rows[0].isReceipt)
    }

    @Test("a receipt is gone once the pane forgets it")
    func receiptIsSessionScoped() {
        let id = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("revoked", id: id, access: false)],
            shown: [], receipts: [])
        #expect(rows.isEmpty)
    }

    @Test("a ticked row is never a receipt, even while the pane remembers it")
    func retickClearsTheDimming() {
        // Re-ticking within the session is the undo, so the row has to stop
        // looking like a log line the moment access comes back — even though
        // the receipt set still names it.
        let id = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("restored", id: id, access: true)],
            shown: [], receipts: [id])
        #expect(rows.count == 1)
        #expect(!rows[0].isReceipt)
    }

    // MARK: - Grouping

    @Test("the group is the window half of the exposure rule, not serve liveness")
    func groupFollowsTheRoster() {
        let open = UUID(), closed = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("b-open", id: open), candidate("a-closed", id: closed)],
            shown: [open], receipts: [])
        #expect(rows.first { $0.id == open }?.group == .windowOpen)
        #expect(rows.first { $0.id == closed }?.group == .availableWhenOpened)
    }

    @Test("window-open rows sort above available ones regardless of name")
    func groupBeatsName() {
        // "zulu" is open and "alpha" is not: the grouping is the explanation,
        // so it has to win the sort or the header would sit above the wrong set.
        let open = UUID(), closed = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("alpha", id: closed), candidate("zulu", id: open)],
            shown: [open], receipts: [])
        #expect(rows.map(\.name) == ["zulu", "alpha"])
    }

    @Test("within a group, names sort naturally")
    func naturalOrdering() {
        // localizedStandardCompare, so "Study 2" precedes "Study 10" — the
        // Finder's ordering, which is the one a researcher has been trained on.
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("Study 10"), candidate("Study 2"), candidate("Study 1")],
            shown: [], receipts: [])
        #expect(rows.map(\.name) == ["Study 1", "Study 2", "Study 10"])
    }

    @Test("colliding names order deterministically rather than by array chance")
    func collidingNamesAreStable() {
        // Two studies both called "interviews" is the routine case, not the
        // exotic one, and a pair that swaps under the pointer reads as a bug.
        let a = UUID(uuidString: "00000000-0000-0000-0000-0000000000AA")!
        let b = UUID(uuidString: "00000000-0000-0000-0000-0000000000BB")!
        let forwards = AgentProjectRegister.rows(
            candidates: [candidate("interviews", id: b), candidate("interviews", id: a)],
            shown: [], receipts: [])
        let backwards = AgentProjectRegister.rows(
            candidates: [candidate("interviews", id: a), candidate("interviews", id: b)],
            shown: [], receipts: [])
        #expect(forwards.map(\.id) == backwards.map(\.id))
        #expect(forwards.first?.id == a)
    }

    // MARK: - The headline

    @Test("readable prints the gate set, not a second opinion of it")
    func readableIsTheGate() {
        // The whole point of taking `gate`: the headline is the set
        // `syncHandshake` pushes to every serve, so it cannot disagree with
        // what the gate closes on. A row can be window-open and ticked and
        // still be outside the gate — a failed sidecar is the live case.
        let open = UUID(), failed = UUID(), closed = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("open", id: open, sessions: 3),
                         candidate("failed", id: failed, sessions: 7),
                         candidate("closed", id: closed, sessions: 42)],
            shown: [open, failed], receipts: [])
        let r = AgentProjectRegister.readable(rows, gate: [open])
        #expect(r.projects == 1)
        #expect(r.sessions == 3)
        #expect(r.unknown == 0)
    }

    @Test("a revoked row stops counting as readable immediately")
    func receiptIsNotReadable() {
        // The receipt is still on screen; it must not still be in the headline,
        // or the one number the pane exists to be right about is wrong. The
        // gate is re-derived on the same act, so it drops the id too.
        let id = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("revoked", id: id, access: false, sessions: 9)],
            shown: [id], receipts: [id])
        #expect(rows.count == 1)
        #expect(AgentProjectRegister.readable(rows, gate: []).projects == 0)
        #expect(AgentProjectRegister.readable(rows, gate: []).sessions == 0)
    }

    @Test("an unknown session count is counted as unknown, not summed as zero")
    func unknownSessionsDoNotInvent() {
        // The sum is honest and the caller is TOLD it is partial, so it can
        // drop the clause instead of printing a confident "4 sessions" for a
        // set whose second member has never been scanned.
        let a = UUID(), b = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("known", id: a, sessions: 4),
                         candidate("unknown", id: b, sessions: nil)],
            shown: [a, b], receipts: [])
        let r = AgentProjectRegister.readable(rows, gate: [a, b])
        #expect(r.projects == 2)
        #expect(r.sessions == 4)
        #expect(r.unknown == 1)
    }

    @Test("nothing shared reads as zero, not as an absent number")
    func emptyRegister() {
        let r = AgentProjectRegister.readable([], gate: [])
        #expect(r.projects == 0)
        #expect(r.sessions == 0)
        #expect(r.unknown == 0)
    }

    // MARK: - What VoiceOver hears

    @Test("the row label joins with commas, because a middot announces as nothing")
    func labelJoinsWithCommas() {
        // Straight from SessionsPopoverSpec: VoiceOver pauses on a comma and
        // reads nothing at all for `·`, so the spoken separator is not the
        // visible one.
        let label = AgentProjectRegister.accessibilityLabel(
            name: "Acme Study", group: "Active",
            sessions: "3 sessions", lastAsked: "Last asked 12 min ago")
        #expect(label == "Acme Study, Active, 3 sessions, Last asked 12 min ago")
    }

    @Test("an absent session count is dropped, not announced as a pause")
    func labelDropsUnknownSessions() {
        let label = AgentProjectRegister.accessibilityLabel(
            name: "Acme Study", group: "Active", sessions: nil, lastAsked: "Never")
        #expect(label == "Acme Study, Active, Never")
    }

    @Test("an empty part is dropped rather than doubling a separator")
    func labelDropsEmptyParts() {
        let label = AgentProjectRegister.accessibilityLabel(
            name: "Acme Study", group: "", sessions: "", lastAsked: "Never")
        #expect(label == "Acme Study, Never")
    }
}
