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
        /// One record is clearly this event's.
        case matched(String)
        /// Two or more are equally plausible, and picking would be a guess.
        ///
        /// **Deliberately not "take the nearest anyway".** Every other refusal
        /// in this adapter costs the researcher a row they could have had; this
        /// one, guessed wrong, costs them a *correct-looking* import of someone
        /// else's session under this participant's name. A row they can chase
        /// is recoverable. A quietly mis-attributed interview is not — it
        /// analyses cleanly and reads as complete, which is the failure this
        /// whole feature is written against.
        case ambiguous(candidates: Int)
    }

    /// Picks the record for an event, or declines to.
    ///
    /// **Overlap first, distance second.** A conference record spans real time
    /// and so does a calendar event, so the strongest available evidence is how
    /// much of the booked hour the call actually occupied — far stronger than
    /// comparing start times, because people join early and run late in both
    /// directions at once. Two calls in one room cannot overlap each other, so
    /// overlap separates them cleanly where "nearest start" can still tie.
    ///
    /// Distance between start times is the fallback for when overlap cannot
    /// speak: a record still in progress with no `endTime`, an event with no
    /// end, or a call that finished before its own booking began.
    ///
    /// - Parameter tolerance: how much better the winner must be before the
    ///   choice counts as evidence rather than noise. Applied as a ratio on
    ///   overlap and as an absolute margin on distance — see the constants.
    static func pick(
        from candidates: [Candidate],
        eventStart: Date,
        eventEnd: Date?
    ) -> Outcome {
        let usable = candidates.filter { !$0.name.isEmpty }
        guard !usable.isEmpty else { return .none }
        guard usable.count > 1 else { return .matched(usable[0].name) }

        // --- Overlap, when both intervals are known ---------------------------
        if let eventEnd, eventEnd > eventStart {
            let scored = usable
                .map { (candidate: $0, overlap: overlap($0, eventStart, eventEnd)) }
                .sorted { $0.overlap > $1.overlap }
            let best = scored[0], runnerUp = scored[1]
            if best.overlap > 0 {
                // A clear winner is one that occupied the booking and the
                // others essentially did not. The ratio, rather than a fixed
                // number of seconds, because the same 90-second margin means
                // something different against a 5-minute call and an hour-long
                // one.
                if runnerUp.overlap == 0 || best.overlap >= runnerUp.overlap * overlapRatio {
                    return .matched(best.candidate.name)
                }
                return .ambiguous(candidates: usable.count)
            }
            // Nothing overlapped the booking at all — everything ran outside
            // it. Fall through to distance rather than refusing: a call that
            // started an hour early and finished before the scheduled start is
            // unusual but not ambiguous.
        }

        // --- Distance between start times -------------------------------------
        let timed = usable.compactMap { candidate -> (Candidate, TimeInterval)? in
            guard let start = candidate.start else { return nil }
            return (candidate, abs(start.timeIntervalSince(eventStart)))
        }
        // A record with no start time at all cannot be placed. If that is all
        // there is, there is nothing to choose between.
        guard !timed.isEmpty else { return .ambiguous(candidates: usable.count) }
        guard timed.count > 1 else { return .matched(timed[0].0.name) }

        let sorted = timed.sorted { $0.1 < $1.1 }
        let best = sorted[0], runnerUp = sorted[1]
        // An absolute margin here, not a ratio: near the event both distances
        // are small and their ratio is wild (two minutes versus one is a
        // factor of two and means nothing), while half an hour apart is a real
        // separation whatever the absolute values.
        if runnerUp.1 - best.1 >= distanceMargin {
            return .matched(best.0.name)
        }
        return .ambiguous(candidates: usable.count)
    }

    /// The winner must have occupied at least three times as much of the
    /// booking as its nearest rival. Two genuinely different sessions in one
    /// room are usually 100:0 on this measure; the ratio exists to catch the
    /// case where a stray record clips the edge of the booking.
    static let overlapRatio: Double = 3

    /// Half an hour. Two calls on one link closer together than this are
    /// back-to-back sessions whose recordings a start time cannot separate —
    /// the same bound `TeamsSource.matchEvent` uses, for the same reason.
    static let distanceMargin: TimeInterval = 30 * 60

    private static func overlap(_ candidate: Candidate, _ from: Date, _ to: Date) -> TimeInterval {
        guard let start = candidate.start, let end = candidate.end, end > start else { return 0 }
        let lower = max(start, from)
        let upper = min(end, to)
        return max(0, upper.timeIntervalSince(lower))
    }
}
