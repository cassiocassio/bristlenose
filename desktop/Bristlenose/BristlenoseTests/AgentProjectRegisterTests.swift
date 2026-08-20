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

    @Test("readable counts only what a window is holding with access on")
    func readableIsBothHalves() {
        let open = UUID(), closed = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("open", id: open, sessions: 3),
                         candidate("closed", id: closed, sessions: 42)],
            shown: [open], receipts: [])
        let r = AgentProjectRegister.readable(rows)
        #expect(r.projects == 1)
        #expect(r.sessions == 3)
    }

    @Test("a revoked row stops counting as readable immediately")
    func receiptIsNotReadable() {
        // The receipt is still on screen; it must not still be in the headline,
        // or the one number the pane exists to be right about is wrong.
        let id = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("revoked", id: id, access: false, sessions: 9)],
            shown: [id], receipts: [id])
        #expect(rows.count == 1)
        #expect(AgentProjectRegister.readable(rows).projects == 0)
        #expect(AgentProjectRegister.readable(rows).sessions == 0)
    }

    @Test("an unknown session count contributes nothing rather than a guess")
    func unknownSessionsDoNotInvent() {
        let a = UUID(), b = UUID()
        let rows = AgentProjectRegister.rows(
            candidates: [candidate("known", id: a, sessions: 4),
                         candidate("unknown", id: b, sessions: nil)],
            shown: [a, b], receipts: [])
        let r = AgentProjectRegister.readable(rows)
        #expect(r.projects == 2)
        #expect(r.sessions == 4)
    }

    @Test("nothing shared reads as zero, not as an absent number")
    func emptyRegister() {
        let r = AgentProjectRegister.readable([])
        #expect(r.projects == 0)
        #expect(r.sessions == 0)
    }
}
