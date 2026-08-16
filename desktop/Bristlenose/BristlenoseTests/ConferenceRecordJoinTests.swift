import Foundation
import Testing

@testable import Bristlenose

// The join that replaced walking the calendar. Every test here is a shape that
// arises from one of two facts: **a Meet link is a room, not a meeting** — so a
// researcher's personal room is reused all day — and **a call need not have been
// booked at all**, which is the case the old event-first listing could not see.

@Suite("Conference record join")
struct ConferenceRecordJoinTests {

    private let calendar = Calendar(identifier: .gregorian)

    private func at(_ hour: Int, _ minute: Int = 0) -> Date {
        calendar.date(from: DateComponents(
            year: 2026, month: 8, day: 13, hour: hour, minute: minute))!
    }

    private func record(
        _ name: String, code: String?, from: Date?, to: Date? = nil
    ) -> ConferenceRecordJoin.Record {
        ConferenceRecordJoin.Record(name: name, meetingCode: code, start: from, end: to)
    }

    private func event(
        _ id: String, code: String, from: Date, to: Date?
    ) -> ConferenceRecordJoin.Event {
        ConferenceRecordJoin.Event(id: id, meetingCode: code, start: from, end: to)
    }

    /// The reason for the whole inversion. A call started from the Meet home
    /// screen has no event to hang off, so an event-first listing produced no
    /// row for it — not a dimmed row, not a footer count, nothing. Two of five
    /// real recordings were invisible this way (16 Aug 2026).
    @Test("A call with no booking is unmatched, never dropped")
    func instantMeetingSurvives() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/instant", code: "osp-jwrt-wff", from: at(14, 21))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent.isEmpty)
        #expect(outcome.unmatched == ["rec/instant"], "it becomes its own row")
    }

    /// One booking, several calls into the room. Their recordings live on
    /// separate conference records, so choosing one discards real files — which
    /// is exactly what reported "Not recorded" over two videos in Drive.
    @Test("Every record inside the booking joins it, not just the nearest")
    func allRecordsOfOneBooking() {
        let outcome = ConferenceRecordJoin.join(
            records: [
                record("rec/A", code: "abc-defg-hij", from: at(15, 2), to: at(15, 6)),
                record("rec/B", code: "abc-defg-hij", from: at(15, 40), to: at(16)),
            ],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent == ["evt-1": ["rec/A", "rec/B"]])
        #expect(outcome.unmatched.isEmpty)
    }

    /// The case the ±window could only guess at. A daily standup reuses one code
    /// across every instance, and the code alone cannot say which Tuesday this
    /// is — but instances of one series never overlap, so the clock separates
    /// them without ever choosing between two *different* meetings.
    @Test("A recurring series is separated by time within its own room")
    func recurringInstancesSeparate() {
        let day2 = calendar.date(byAdding: .day, value: 1, to: at(9))!
        let outcome = ConferenceRecordJoin.join(
            records: [
                record("rec/mon", code: "std-upst-and", from: at(9, 1)),
                record("rec/tue", code: "std-upst-and", from: day2.addingTimeInterval(120)),
            ],
            events: [
                event("evt-mon", code: "std-upst-and", from: at(9), to: at(9, 30)),
                event("evt-tue", code: "std-upst-and",
                      from: day2, to: day2.addingTimeInterval(1800)),
            ])

        #expect(outcome.byEvent == ["evt-mon": ["rec/mon"], "evt-tue": ["rec/tue"]])
    }

    /// Two meetings running at once is ordinary — you accept both invitations and
    /// attend one, or hop between them. The code is what makes that safe: they
    /// are different rooms, so no time rule is ever consulted.
    @Test("Overlapping bookings are told apart by the code, not the clock")
    func overlappingBookingsUseTheKey() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/x", code: "second-room", from: at(11, 5))],
            events: [
                event("evt-a", code: "first-room", from: at(11), to: at(12)),
                event("evt-b", code: "second-room", from: at(11), to: at(12)),
            ])

        #expect(outcome.byEvent == ["evt-b": ["rec/x"]],
                "the overlapping first room is never even a candidate")
    }

    /// Measured live: a call joined at 2:12pm against a 3:00pm booking. Twenty
    /// minutes of extra tolerance separates this from a row reading "Not
    /// recorded" about a recording sitting in Drive.
    @Test("Joining early still joins — the measured 48 minutes clears")
    func earlyJoinIsStillTheMeeting() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/early", code: "abc-defg-hij", from: at(14, 12), to: at(14, 14))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent == ["evt-1": ["rec/early"]])
    }

    /// The other side of that tolerance, and the reason it is an hour rather
    /// than the fifteen the old window spanned. A mic check two hours before a
    /// session is not that session, and arriving as "Recording 1" of it is how a
    /// 30-second clip gets analysed under a participant's name.
    @Test("A call long before the booking stands alone")
    func farEarlierCallIsItsOwnMeeting() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/check", code: "abc-defg-hij", from: at(13, 12), to: at(13, 14))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent.isEmpty)
        #expect(outcome.unmatched == ["rec/check"],
                "still a row, still fetchable — just not filed under that title")
    }

    /// A record that begins after the booking ended is a new call placed later.
    /// A session that overran began before the end and overlaps anyway.
    @Test("A call starting after the booking ends is a different call")
    func laterCallIsNotTheBooking() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/after", code: "abc-defg-hij", from: at(16, 50))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.unmatched == ["rec/after"])
    }

    @Test("A session that overran its booking still belongs to it")
    func overrunStillJoins() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/long", code: "abc-defg-hij", from: at(16, 20), to: at(17, 15))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent == ["evt-1": ["rec/long"]])
    }

    /// `spaces.get` is the only thing that can supply the key. Without it there
    /// is nothing to match on, and inventing a match from the clock alone is the
    /// guess this join was built to remove.
    @Test("A record whose space could not be resolved is unmatched, not guessed")
    func unresolvedCodeIsNeverGuessed() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/unknown", code: nil, from: at(15, 5))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent.isEmpty)
        #expect(outcome.unmatched == ["rec/unknown"])
    }

    /// A clockless record in a room with one booking has nothing to be
    /// disambiguated against, so the code alone decides.
    @Test("A record with no start joins when its room holds exactly one booking")
    func clocklessRecordWithOneCandidate() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/noclock", code: "abc-defg-hij", from: nil)],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent == ["evt-1": ["rec/noclock"]])
    }

    @Test("A record with no start refuses to choose between two bookings")
    func clocklessRecordWithTwoCandidates() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("rec/noclock", code: "abc-defg-hij", from: nil)],
            events: [
                event("evt-1", code: "abc-defg-hij", from: at(10), to: at(11)),
                event("evt-2", code: "abc-defg-hij", from: at(15), to: at(16)),
            ])

        #expect(outcome.byEvent.isEmpty)
        #expect(outcome.unmatched == ["rec/noclock"])
    }

    /// A nameless record has no resource behind it — passing it on would have
    /// the caller ask Google for `conferenceRecords//recordings`.
    @Test("A record with no name is dropped entirely")
    func namelessRecordIsDropped() {
        let outcome = ConferenceRecordJoin.join(
            records: [record("", code: "abc-defg-hij", from: at(15, 5))],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16, 30))])

        #expect(outcome.byEvent.isEmpty)
        #expect(outcome.unmatched.isEmpty)
    }

    @Test("No records is not an error")
    func noRecords() {
        let outcome = ConferenceRecordJoin.join(
            records: [],
            events: [event("evt-1", code: "abc-defg-hij", from: at(15), to: at(16))])
        #expect(outcome == ConferenceRecordJoin.Result(byEvent: [:], unmatched: []))
    }

    /// An empty calendar is the state a researcher who declined the calendar
    /// scope is in — and every recording still has to reach them.
    @Test("With no calendar at all, every record is still a row")
    func noEventsMeansEveryRecordStandsAlone() {
        let outcome = ConferenceRecordJoin.join(
            records: [
                record("rec/A", code: "abc-defg-hij", from: at(15, 5)),
                record("rec/B", code: "osp-jwrt-wff", from: at(16, 5)),
            ],
            events: [])

        #expect(outcome.unmatched == ["rec/A", "rec/B"])
    }
}
