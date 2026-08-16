import Foundation

// Which conference record belongs to which calendar event.
//
// Pure values and one pure function, so the decision that used to be `.first`
// on an unordered list can be tested without a tenant, a meeting link or a
// network. `desktop/CLAUDE.md` § Testing: the decision belongs in a testable
// helper, and this one had been sitting inside a networking function where
// nothing could reach it.
//
// **Why this exists at all.** A Meet *meeting code* is not a meeting — it is a
// room, and a researcher's personal room link is reused for every session they
// hold in it. The lookup nets every conference record on that code across a
// 15-hour window, so an event at 10:00 and another at 15:00 on the same link
// both see both records. Taking the first was a coin toss the API does not even
// promise to weight: `conferenceRecords.list` documents no ordering and accepts
// no `order_by`.
//
// The consequence was not a missing row. It was **the wrong video under the
// right participant's name** — a study analysing the 15:00 session as though it
// were the 10:00 one, with nothing anywhere to say so.

enum ConferenceRecordMatch {

    /// One conference record, reduced to the two fields that decide the match.
    struct Candidate: Equatable {
        /// `conferenceRecords/<id>` — the resource name, opaque and remote.
        let name: String
        let start: Date?
        let end: Date?

        init(name: String, start: Date?, end: Date? = nil) {
            self.name = name
            self.start = start
            self.end = end
        }
    }

    enum Outcome: Equatable {
        /// Nothing on this code in this window.
        case none
        /// The records that belong to this event — **all of them**, not one.
        case matched([String])
    }

    /// Selects every conference record that plausibly belongs to this event.
    ///
    /// **It selects rather than chooses, and that distinction is the bug this
    /// replaced.** A Meet code is a room, and one calendar event can hold
    /// several calls into that room: join, leave, rejoin, each producing its
    /// own conference record with its own recording. Observed live on
    /// 16 Aug 2026 — a "test" event booked for 15:00 with recordings at 13:12
    /// and 14:12, three conference records on one code, all of them that
    /// event's.
    ///
    /// Picking the single nearest record therefore hid real recordings: the
    /// window showed "Not recorded" over two files sitting in Drive, which is
    /// exactly the false negative this adapter exists to prevent. Worse, the
    /// outline had already been built to render a meeting with two recordings
    /// — the model was right and the selection threw the data away before it
    /// got there.
    ///
    /// What still bounds over-claiming is the **caller's window**, not this
    /// function: a recurring series reuses one code across every instance, and
    /// the −3h/+12h net around this instance is what keeps last Tuesday's
    /// record out. Widening that window widens what this sweeps up.
    static func select(
        from candidates: [Candidate],
        eventStart: Date,
        eventEnd: Date?
    ) -> Outcome {
        let usable = candidates.filter { !$0.name.isEmpty }
        guard !usable.isEmpty else { return .none }
        return .matched(usable.map(\.name))
    }

}
