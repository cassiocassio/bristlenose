import Foundation

// Which conference record belongs to which calendar event.
//
// Pure values and one pure function, so the join that decides what the window
// shows can be tested without a tenant, a meeting link or a network.
//
// **This replaces a search with a lookup, and that is the whole change.** The
// adapter used to walk the *calendar*: for each event, ask Meet for conference
// records on that event's meeting code within a ±window, then decide which of
// them was this one. Two costs came out of that shape, and only the second was
// obvious.
//
// The obvious one: a call with no calendar event behind it — Meet's own "instant
// meeting", started from the home screen — has no event to walk from, so it
// produced no row at all. Not a dimmed row, not a footer count: nothing. On the
// tenant this was built against, two of five real recordings were invisible
// (16 Aug 2026).
//
// The subtle one: the ±window was doing work the meeting code should have done.
// A code is exact — `spaces.get` returns the real one for every conference
// record — so once the records are listed on time alone and their codes
// resolved, the join is an equality on a key both sides genuinely share. The
// remaining use of time is to pick *which instance* of a recurring series a
// record belongs to, and instances of one series cannot overlap each other, so
// the dangerous case (two different meetings running at once, the researcher
// hopping between them) cannot arise inside it.
//
// The incentive also flips, which is why the tolerance below is an hour rather
// than the fifteen the old window spanned. Before the inversion an unmatched
// record was *invisible*, so generosity was the safe direction. Now an unmatched
// record gets its own row — real time, real size, fetchable — so a tight join is
// the safe direction: the failure it produces is a recording filed under its
// meeting code instead of a title, not a recording filed under the wrong title.

enum ConferenceRecordJoin {

    /// One conference record, reduced to the fields that decide the join.
    struct Record: Equatable {
        /// `conferenceRecords/<id>` — the resource name, opaque and remote.
        let name: String
        /// The room's code, from `spaces.get`. Nil when the space could not be
        /// resolved, and then this record can never be joined — the key is the
        /// only thing that could have matched it.
        let meetingCode: String?
        /// When the *call* began. Not when anyone pressed record.
        let start: Date?
        let end: Date?

        init(name: String, meetingCode: String?, start: Date?, end: Date? = nil) {
            self.name = name
            self.meetingCode = meetingCode
            self.start = start
            self.end = end
        }
    }

    /// One calendar event that has a Meet call attached.
    struct Event: Equatable {
        /// The caller's own key. Never interpreted here.
        let id: String
        /// `conferenceData.conferenceId`, which for `hangoutsMeet` is the
        /// meeting code and matches `space.meetingCode` exactly.
        let meetingCode: String
        let start: Date
        let end: Date?
    }

    struct Result: Equatable {
        /// Event key → the records held in that event's room during its span, in
        /// the order the caller supplied them.
        ///
        /// A list, not a single record, because one booking routinely holds
        /// several calls: join, leave, rejoin, each producing its own record
        /// with its own recording. Taking one and calling it the answer reported
        /// "Not recorded" over two files sitting in Drive (16 Aug 2026).
        let byEvent: [String: [String]]
        /// Records that belong to no event in the window — an instant meeting, a
        /// call in a room whose booking is on another calendar, or a record
        /// whose space could not be resolved. Each still becomes a row.
        let unmatched: [String]
    }

    /// How early a call may begin before its booking and still be that booking's.
    ///
    /// **An hour, sized against a measurement rather than a feeling.** People
    /// open the room before the meeting: a call joined at 2:12pm against a 3:00pm
    /// event was observed live on 16 Aug 2026, which is 48 minutes. An hour
    /// clears it with room to spare and stops well short of the two-hour-plus
    /// gaps that separate a mic check from the session it precedes — a 30-second
    /// clip recorded while testing the microphone must not arrive as "P05
    /// Interview — Recording 1", which is the shape that gets a wrong file
    /// analysed under a participant's name.
    static let earlyJoinTolerance: TimeInterval = 60 * 60

    /// Assumed length of an event whose end the calendar didn't give us. Only
    /// reachable for a malformed event — Google always serves `end` for a timed
    /// one — and an hour is the length such an event would have been booked for.
    private static let assumedMeetingLength: TimeInterval = 60 * 60

    /// Joins conference records to calendar events on the meeting code.
    ///
    /// Every record lands somewhere: matched to exactly one event, or in
    /// `unmatched`. Nothing is dropped, because a dropped record is a recording
    /// that exists and has no row, which is the failure this whole adapter is
    /// written against.
    static func join(records: [Record], events: [Event]) -> Result {
        var byCode: [String: [Event]] = [:]
        for event in events {
            byCode[event.meetingCode, default: []].append(event)
        }

        var byEvent: [String: [String]] = [:]
        var unmatched: [String] = []

        for record in records {
            // A nameless record is unusable — there is no resource to fetch
            // from — and passing it on would have the caller ask Google for
            // `conferenceRecords//recordings`.
            guard !record.name.isEmpty else { continue }
            guard let code = record.meetingCode,
                  let candidates = byCode[code],
                  let event = bestEvent(for: record, among: candidates)
            else {
                unmatched.append(record.name)
                continue
            }
            byEvent[event.id, default: []].append(record.name)
        }

        return Result(byEvent: byEvent, unmatched: unmatched)
    }

    /// Which instance of a room's bookings this call belongs to.
    ///
    /// Only ever called with events that already share the record's meeting
    /// code, so this is disambiguation *within one room* — where bookings do not
    /// overlap — and never a choice between two different meetings.
    private static func bestEvent(for record: Record, among events: [Event]) -> Event? {
        guard let recordStart = record.start else {
            // No clock on the record. With one booking in the room there is
            // nothing to disambiguate; with several, any pick is a coin toss and
            // the row is better off standing alone under its own code.
            return events.count == 1 ? events[0] : nil
        }
        let recordEnd = record.end ?? recordStart

        var best: (event: Event, distance: TimeInterval)?
        for event in events {
            let eventEnd = event.end ?? event.start.addingTimeInterval(assumedMeetingLength)
            let opensAt = event.start.addingTimeInterval(-earlyJoinTolerance)
            // Interval overlap against the booking, widened only at the front.
            // Nothing at the back: a record that *begins* after the booking ends
            // is a new call placed later, not the same session running long —
            // a session that overran began before the end and overlaps anyway.
            guard recordStart <= eventEnd, recordEnd >= opensAt else { continue }
            let distance = abs(recordStart.timeIntervalSince(event.start))
            if best == nil || distance < best!.distance {
                best = (event, distance)
            }
        }
        return best?.event
    }
}
