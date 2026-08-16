import Foundation
import Testing

@testable import Bristlenose

// The decision that used to be `.first` on a list the API documents no ordering
// for. Every test here is a shape that arises from one fact: **a Meet link is a
// room, not a meeting**, and a researcher's personal room is reused all day.

@Suite("Conference record match")
struct ConferenceRecordMatchTests {

    private let calendar = Calendar(identifier: .gregorian)

    private func at(_ hour: Int, _ minute: Int = 0) -> Date {
        calendar.date(from: DateComponents(
            year: 2026, month: 8, day: 13, hour: hour, minute: minute))!
    }

    private func record(
        _ name: String, from: Date, to: Date?
    ) -> ConferenceRecordMatch.Candidate {
        ConferenceRecordMatch.Candidate(name: name, start: from, end: to)
    }

    /// The failure this whole type exists for.
    ///
    /// Two sessions in one personal room, five hours apart. Both conference
    /// records fall inside each event's −3h/+12h net, so `.first` gave each
    /// event whichever record the API happened to return first — and the cost
    /// is not a missing row but the **wrong video under the right
    /// participant's name**, which analyses cleanly and reads as complete.
    @Test("Two calls in one room go to the right events, not to whichever came first")
    func personalRoomUsedTwiceInADay() {
        let morning = record("rec/A", from: at(10, 2), to: at(10, 54))
        let afternoon = record("rec/B", from: at(15, 4), to: at(15, 58))
        // Deliberately in the order that would break the old code: the
        // afternoon record first, so `.first` would hand it to the 10:00 event.
        let candidates = [afternoon, morning]

        #expect(ConferenceRecordMatch.pick(
            from: candidates, eventStart: at(10), eventEnd: at(11)) == .matched("rec/A"))
        #expect(ConferenceRecordMatch.pick(
            from: candidates, eventStart: at(15), eventEnd: at(16)) == .matched("rec/B"))
    }

    /// The join-early case that widened the lookback to three hours in the
    /// first place. The call starts before its own booking and still overlaps
    /// it heavily, so overlap picks it without any special-casing.
    @Test("A call joined early still matches its own booking")
    func joinedEarly() {
        let early = record("rec/A", from: at(14, 12), to: at(15, 50))
        let other = record("rec/B", from: at(9), to: at(9, 30))
        #expect(ConferenceRecordMatch.pick(
            from: [other, early], eventStart: at(15), eventEnd: at(16)) == .matched("rec/A"))
    }

    /// Back-to-back sessions on one link, too close to separate. **The refusal
    /// is the feature.** Every other refusal in the adapter costs a row the
    /// researcher can still fetch from Drive; guessing here costs them a
    /// silently mis-attributed interview.
    @Test("Two overlapping candidates are refused rather than guessed")
    func genuinelyAmbiguous() {
        // Both records straddle the booked hour by a similar amount — the shape
        // a start-time comparison cannot separate either.
        let a = record("rec/A", from: at(10, 5), to: at(10, 35))
        let b = record("rec/B", from: at(10, 20), to: at(10, 50))
        #expect(ConferenceRecordMatch.pick(
            from: [a, b], eventStart: at(10), eventEnd: at(11))
            == .ambiguous(candidates: 2))
    }

    /// A record still in progress has no `endTime`, so overlap can say nothing
    /// and the fallback has to. Half an hour apart is a real separation.
    @Test("With no end time, a clearly nearer start still decides it")
    func fallsBackToDistance() {
        let near = record("rec/A", from: at(10, 3), to: nil)
        let far = record("rec/B", from: at(13), to: nil)
        #expect(ConferenceRecordMatch.pick(
            from: [near, far], eventStart: at(10), eventEnd: at(11)) == .matched("rec/A"))
    }

    /// …and when the fallback can't separate them either, it refuses too.
    /// Two starts inside the same half hour are back-to-back sessions.
    @Test("With no end times and starts minutes apart, it refuses")
    func distanceTooCloseToCall() {
        let a = record("rec/A", from: at(10, 3), to: nil)
        let b = record("rec/B", from: at(10, 9), to: nil)
        #expect(ConferenceRecordMatch.pick(
            from: [a, b], eventStart: at(10), eventEnd: at(11))
            == .ambiguous(candidates: 2))
    }

    /// The overwhelmingly common case, and it must not pay for any of the
    /// above: one record, taken, no scoring at all.
    @Test("A single candidate is simply the match")
    func singleCandidate() {
        #expect(ConferenceRecordMatch.pick(
            from: [record("rec/A", from: at(10, 4), to: at(10, 55))],
            eventStart: at(10), eventEnd: at(11)) == .matched("rec/A"))
    }

    @Test("No candidates is none, not ambiguous")
    func noCandidates() {
        #expect(ConferenceRecordMatch.pick(
            from: [], eventStart: at(10), eventEnd: at(11)) == .none)
    }

    /// An event with no end — Google returns `date` instead of `dateTime` for
    /// all-day entries, and those are filtered upstream, but a malformed event
    /// must not crash the scorer or silently match on nothing.
    @Test("An event with no end falls back to distance rather than failing")
    func eventWithoutEnd() {
        let near = record("rec/A", from: at(10, 3), to: at(10, 55))
        let far = record("rec/B", from: at(16), to: at(16, 40))
        #expect(ConferenceRecordMatch.pick(
            from: [near, far], eventStart: at(10), eventEnd: nil) == .matched("rec/A"))
    }

    /// A nameless record is unusable — there is no resource to fetch from — and
    /// must not count towards ambiguity either, or one malformed entry would
    /// refuse an otherwise clear match.
    @Test("A record with no name is ignored, not counted")
    func namelessRecordIsIgnored() {
        let good = record("rec/A", from: at(10, 4), to: at(10, 55))
        let nameless = record("", from: at(10, 6), to: at(10, 50))
        #expect(ConferenceRecordMatch.pick(
            from: [good, nameless], eventStart: at(10), eventEnd: at(11)) == .matched("rec/A"))
    }
}
