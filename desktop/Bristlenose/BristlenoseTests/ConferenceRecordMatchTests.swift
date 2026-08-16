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

    /// The failure this replaced, and it is the opposite of what it was
    /// written to prevent.
    ///
    /// One calendar event can hold several calls into the same room — join,
    /// leave, rejoin — each producing its own conference record with its own
    /// recording. Observed live 16 Aug 2026: a "test" event booked for 15:00
    /// with recordings at 13:12 and 14:12, three records on one code, all of
    /// them that event's. Choosing the single nearest reported "Not recorded"
    /// over two files sitting in Drive.
    @Test("Every record in the window belongs to the event, not just the nearest")
    func selectsAllRecordsForOneEvent() {
        let a = record("rec/A", from: at(13, 12), to: at(13, 14))
        let b = record("rec/B", from: at(14, 12), to: at(14, 14))
        let c = record("rec/C", from: at(15, 2), to: at(15, 6))

        let outcome = ConferenceRecordMatch.select(
            from: [a, b, c], eventStart: at(15), eventEnd: at(16, 30))
        #expect(outcome == .matched(["rec/A", "rec/B", "rec/C"]),
                "all three, so their recordings can be unioned")
    }

    @Test("No candidates is none")
    func noCandidates() {
        #expect(ConferenceRecordMatch.select(
            from: [], eventStart: at(10), eventEnd: at(11)) == .none)
    }

    /// A nameless record is unusable — there is no resource to fetch from — so
    /// it must not reach the caller, which would ask Google for
    /// `conferenceRecords//recordings`.
    @Test("A record with no name is dropped")
    func namelessRecordIsDropped() {
        let good = record("rec/A", from: at(10, 4), to: at(10, 55))
        let nameless = record("", from: at(10, 6), to: at(10, 50))
        #expect(ConferenceRecordMatch.select(
            from: [good, nameless], eventStart: at(10), eventEnd: at(11))
            == .matched(["rec/A"]))
    }

    /// The window is what bounds over-claiming, not this function — a recurring
    /// series reuses one code across every instance. Whatever the caller nets,
    /// this selects; widening the net widens the sweep, and that trade is
    /// documented where the net is set rather than here.
    @Test("Selection does not second-guess the caller's window")
    func selectsWhateverTheWindowNetted() {
        let far = record("rec/Far", from: at(3), to: at(4))
        #expect(ConferenceRecordMatch.select(
            from: [far], eventStart: at(15), eventEnd: at(16)) == .matched(["rec/Far"]))
    }
}
