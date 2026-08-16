import Foundation
import Testing

@testable import Bristlenose

// The import grid's tree, which is where every judgement about what nests under
// what is made. The view below it renders; it decides nothing.
//
// Scope, deliberately: these test the *outcomes* a researcher would notice — a
// half-session that goes missing, a footer that overstates, a triangle on a
// meeting that never needed one — rather than the shape of the enum. The
// mechanical grouping is exercised by all of them at once, which is what makes
// them worth having.

@Suite("Cloud import outline")
struct CloudImportOutlineTests {

    private let calendar = Calendar(identifier: .gregorian)

    /// A fixed instant, so day labels don't drift with the wall clock. 16 Aug
    /// 2026 is a Sunday.
    private var now: Date {
        calendar.date(from: DateComponents(year: 2026, month: 8, day: 16, hour: 18))!
    }

    private func moment(daysAgo: Int, hour: Int, minute: Int = 0) -> Date {
        let day = calendar.date(byAdding: .day, value: -daysAgo, to: now)!
        return calendar.date(bySettingHour: hour, minute: minute, second: 0, of: day)!
    }

    private func row(
        id: String,
        title: String = "P05 Interview",
        scheduled: Date,
        booked: TimeInterval? = 3600,
        recorded: Date?,
        ran: TimeInterval? = nil,
        meeting: String? = nil,
        ordinal: Int? = nil,
        local: ImportRowState = .notImported,
        video: ArtifactAvailability = .available
    ) -> CloudImportRow {
        CloudImportRow(
            id: id,
            title: title,
            startsAt: recorded ?? scheduled,
            duration: ran,
            sizeBytes: nil,
            expiresAt: nil,
            attendees: [],
            localState: local,
            video: video,
            roster: .available,
            transcript: .available,
            organiser: nil,
            scheduledAt: scheduled,
            scheduledDuration: booked,
            recordedAt: recorded,
            meetingID: meeting,
            siblingOrdinal: ordinal
        )
    }

    private func build(_ rows: [CloudImportRow]) -> CloudImportOutline.Result {
        CloudImportOutline.build(rows: rows, now: now, calendar: calendar)
    }

    // MARK: - The reason this is an outline

    /// The failure the whole grid exists to make visible.
    ///
    /// A researcher stops and restarts recording mid-interview and the call
    /// produces two files. The adapter used to take `.first` and drop the
    /// second in silence — and a half-session analyses perfectly cleanly, so
    /// nothing downstream would ever say that forty minutes never arrived.
    /// Both halves must be present, separately tickable, and counted.
    @Test("Two recordings of one call nest under it, and both can be fetched")
    func oneMeetingTwoRecordings() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let result = build([
            row(id: "file-a", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(120), ran: 1_924, meeting: "mtg-p05"),
            row(id: "file-b", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(2_460), ran: 2_299, meeting: "mtg-p05"),
        ])

        #expect(result.days.count == 1)
        let entries = result.days[0].children
        #expect(entries.count == 1, "one call, not two rows at meeting level")

        guard case .meeting(let meeting) = entries[0].kind else {
            Issue.record("a call with two recordings draws a meeting row")
            return
        }
        #expect(meeting.recordingCount == 2)
        #expect(entries[0].children.count == 2)
        #expect(entries[0].children.compactMap(\.row?.id) == ["file-a", "file-b"],
                "chronological within the call — Recording 1 is the one that happened first")

        // The footer's job: say two, not one.
        #expect(result.meetings == 1)
        #expect(result.recordings == 2)
        #expect(result.fetchable == 2)
    }

    /// The 90% case, and the one that must NOT grow a triangle. Making someone
    /// expand a disclosure to read a single recording's time would be the
    /// hierarchy taxing the common case to serve the rare one.
    @Test("One recording of one call is a single flat row")
    func oneMeetingOneRecording() {
        let scheduled = moment(daysAgo: 3, hour: 9, minute: 30)
        let result = build([
            row(id: "file-a", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(240), ran: 3_131, meeting: "mtg-p04"),
        ])

        let entries = result.days[0].children
        #expect(entries.count == 1)
        #expect(entries[0].children.isEmpty, "nothing to expand")
        guard case .recording(let recording) = entries[0].kind else {
            Issue.record("a lone recording is a recording row, not a meeting row")
            return
        }
        #expect(recording.ordinal == nil, "no ordinal means: this row IS the meeting")
        #expect(!recording.isChild)
        // Both clocks live on the one row — the point of not nesting it.
        #expect(recording.row.scheduledAt == scheduled)
        #expect(recording.row.recordedAt == scheduled.addingTimeInterval(240))
    }

    /// A meeting nobody recorded is still a row. "You didn't record that one"
    /// and "that meeting isn't here" are different answers, and only one of
    /// them is true — the false negative this feature is written against.
    @Test("A meeting with no recording is listed, and counts as zero recordings")
    func unrecordedMeetingStillAppears() {
        let result = build([
            row(id: "evt-sync", title: "Weekly sync",
                scheduled: moment(daysAgo: 5, hour: 10), recorded: nil, video: .notRecorded),
        ])

        #expect(result.days[0].children.count == 1)
        #expect(result.meetings == 1)
        #expect(result.recordings == 0)
        #expect(result.fetchable == 0)
    }

    // MARK: - Order

    /// Newest day first, because the researcher opened this to find last week.
    /// Chronological inside the day, because that is how a schedule reads and
    /// how two interviews that share a Wednesday relate to each other.
    @Test("Days descend; rows within a day ascend")
    func ordering() {
        let result = build([
            row(id: "c", title: "Late",   scheduled: moment(daysAgo: 3, hour: 16), recorded: moment(daysAgo: 3, hour: 16)),
            row(id: "a", title: "Early",  scheduled: moment(daysAgo: 3, hour: 9),  recorded: moment(daysAgo: 3, hour: 9)),
            row(id: "z", title: "Older",  scheduled: moment(daysAgo: 9, hour: 11), recorded: moment(daysAgo: 9, hour: 11)),
            row(id: "n", title: "Newer",  scheduled: moment(daysAgo: 1, hour: 14), recorded: moment(daysAgo: 1, hour: 14)),
        ])

        #expect(result.days.count == 3)
        // Compared as dates rather than as labels: the label's *wording* is
        // `dayLabels`' business, and asserting a formatted string here would
        // pin this test to the machine's locale for no gain.
        #expect(result.days.compactMap { node -> Date? in
            guard case .day(let day) = node.kind else { return nil }
            return day.start
        } == [
            calendar.startOfDay(for: moment(daysAgo: 1, hour: 12)),
            calendar.startOfDay(for: moment(daysAgo: 3, hour: 12)),
            calendar.startOfDay(for: moment(daysAgo: 9, hour: 12)),
        ])

        // Within the dense day: 09:00 before 16:00.
        #expect(result.days[1].children.compactMap(\.row?.title) == ["Early", "Late"])
    }

    /// A recording that ran past midnight must not be torn off its meeting into
    /// the next day's group. The call belongs to the day it was booked for.
    /// A call booked at 23:30 whose second half records after midnight must not
    /// be torn in two by the day grouping — the meeting row under one header
    /// and one of its children under the next.
    ///
    /// Two rows, deliberately: with one row this took the single-recording
    /// branch and never built a meeting node at all, so it pinned something
    /// milder than its own name claimed.
    @Test("A meeting that records past midnight stays whole, under its booked day")
    func lateNightMeetingStaysWithItsDay() {
        let scheduled = moment(daysAgo: 2, hour: 23, minute: 30)
        let result = build([
            row(id: "file-a", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(600), meeting: "mtg-late"),
            row(id: "file-b", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(3_600), meeting: "mtg-late"),
        ])

        #expect(result.days.count == 1, "one day, not one either side of midnight")
        guard case .day(let day) = result.days[0].kind else {
            Issue.record("expected a day header")
            return
        }
        #expect(day.start == calendar.startOfDay(for: scheduled))
        #expect(result.days[0].children.count == 1)
        #expect(result.days[0].children[0].children.count == 2, "both halves under one meeting")
    }

    /// Ordinals come from the adapter, not from position — because siblings can
    /// share an exact `startsAt` (the platform omitted the recording's own
    /// start), which makes their sorted order arbitrary rather than merely
    /// unspecified. The same ordinal also disambiguates the destination
    /// filename, so a swap is not cosmetic.
    @Test("The adapter's ordinal wins over array position")
    func adapterOrdinalWins() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let result = build([
            row(id: "file-a", scheduled: scheduled, recorded: scheduled,
                meeting: "mtg", ordinal: 2),
            row(id: "file-b", scheduled: scheduled, recorded: scheduled,
                meeting: "mtg", ordinal: 1),
        ])
        let children = result.days[0].children[0].children
        let ordinals = children.map { node -> Int? in
            guard case .recording(let r) = node.kind else { return nil }
            return r.ordinal
        }
        #expect(Set(ordinals.compactMap { $0 }) == [1, 2],
                "each sibling keeps the number the adapter gave it")
    }

    // MARK: - Day labels

    @Test("Today and Yesterday are named; older days carry their weekday")
    func dayLabels() {
        func label(_ date: Date) -> String {
            CloudImportOutline.dayLabel(for: date, now: now, calendar: calendar)
        }
        #expect(label(moment(daysAgo: 0, hour: 9)) == "Today")
        #expect(label(moment(daysAgo: 1, hour: 9)) == "Yesterday")

        // 13 Aug 2026 is a Thursday. Asserted by content rather than as one
        // string, because the system formatter orders weekday, day and month
        // per locale — "Thu 13 Aug" here, "Thu, Aug 13" on a US Mac — and
        // pinning the order would test the machine rather than the code. What
        // must be true either way: all three parts are present.
        //
        // The weekday is there because a study runs across a week or two and
        // "the Thursday one" is how a researcher holds that.
        let older = label(moment(daysAgo: 3, hour: 9))
        #expect(older.contains("Thu"))
        #expect(older.contains("13"))
        #expect(older.contains("Aug"))
    }

    /// Finder and Mail's rule. Eleven months of the year the year is noise;
    /// across the New Year it is the only thing that disambiguates.
    @Test("The year appears only when it differs from this one")
    func yearOnlyWhenDifferent() {
        let thisYear = CloudImportOutline.dayLabel(
            for: moment(daysAgo: 30, hour: 9), now: now, calendar: calendar)
        let lastYear = CloudImportOutline.dayLabel(
            for: moment(daysAgo: 300, hour: 9), now: now, calendar: calendar)
        #expect(!thisYear.contains("2026"))
        #expect(lastYear.contains("2025"))
    }

    // MARK: - What the footer may claim

    /// The permissions link's whole contract. It appears when a recording the
    /// researcher can *see* is one they cannot *fetch* — and its absence when
    /// they can fetch everything is the reassurance, so a link that is always
    /// on is worse than none.
    @Test("Fetch everything you can see and there is no permissions link")
    func noLinkWhenNothingIsWithheld() {
        let result = build([
            row(id: "a", scheduled: moment(daysAgo: 1, hour: 9), recorded: moment(daysAgo: 1, hour: 9)),
            row(id: "b", scheduled: moment(daysAgo: 2, hour: 9), recorded: moment(daysAgo: 2, hour: 9)),
        ])
        #expect(result.fetchable == 2)
        #expect(!result.withholding)
    }

    /// The case that made `fetchable < recordings` the wrong arithmetic, and
    /// the one a returning researcher hits every single time.
    ///
    /// All three of these are *local* facts — the file is already here, it is
    /// an iCloud placeholder, the drive is unplugged — and each makes a row
    /// unfetchable while plainly having a recording. Counting them as withheld
    /// showed a remote-permissions link to someone whose only crime was
    /// succeeding last week, which is exactly how a link that means something
    /// becomes a link nobody reads.
    @Test("A file you already have is not a permissions problem")
    func localStatesAreNotWithholding() {
        let result = build([
            row(id: "a", scheduled: moment(daysAgo: 1, hour: 9),
                recorded: moment(daysAgo: 1, hour: 9), local: .imported),
            row(id: "b", scheduled: moment(daysAgo: 2, hour: 9),
                recorded: moment(daysAgo: 2, hour: 9),
                local: .notDownloaded(provider: "Dropbox")),
            row(id: "c", scheduled: moment(daysAgo: 3, hour: 9),
                recorded: moment(daysAgo: 3, hour: 9),
                local: .driveNotConnected(volume: "T7")),
        ])
        #expect(result.recordings == 3)
        #expect(result.fetchable == 0, "none of them can be ticked…")
        #expect(!result.withholding, "…and none of them is a permissions question")
    }

    /// The most permission-shaped state in the feature, and the one the old
    /// arithmetic could never fire for: we were not allowed to look, so we see
    /// no recording, so `fetchable < recordings` was 0 < 0.
    @Test("A declined scope is withholding even though we cannot see the file")
    func declinedScopeIsWithholding() {
        let result = build([
            row(id: "a", scheduled: moment(daysAgo: 1, hour: 9), recorded: moment(daysAgo: 1, hour: 9)),
            row(id: "b", scheduled: moment(daysAgo: 2, hour: 10), recorded: nil,
                video: .needsScope("drive.readonly")),
        ])
        #expect(result.withholding)
    }

    /// The case the mockup calls out by name: an ordinary month of un-recorded
    /// standups must never raise a permissions question, because nothing was
    /// withheld — there was simply nothing to withhold.
    @Test("A meeting nobody recorded never triggers the permissions link")
    func unrecordedMeetingsAreNotWithholding() {
        let result = build([
            row(id: "a", scheduled: moment(daysAgo: 1, hour: 9), recorded: moment(daysAgo: 1, hour: 9)),
            row(id: "sync1", scheduled: moment(daysAgo: 2, hour: 10), recorded: nil, video: .notRecorded),
            row(id: "sync2", scheduled: moment(daysAgo: 3, hour: 10), recorded: nil, video: .notRecorded),
        ])
        #expect(result.meetings == 3)
        #expect(result.recordings == 1)
        #expect(!result.withholding, "two un-recorded standups are not a permissions problem")
    }

    @Test("A recording we can see and cannot fetch does trigger it")
    func withheldRecordingIsWithholding() {
        let visible = moment(daysAgo: 1, hour: 9)
        let result = build([
            row(id: "a", scheduled: visible, recorded: visible),
            // Listed, with a real recording behind it, and unfetchable — the
            // Teams shape where the tenant blocks download.
            row(id: "b", scheduled: moment(daysAgo: 2, hour: 9),
                recorded: moment(daysAgo: 2, hour: 9), video: .unsupported),
        ])
        #expect(result.recordings == 2)
        #expect(result.fetchable == 1)
        #expect(result.withholding)
    }

    // MARK: - The meeting header's checkbox

    /// The parent exists for the case the outline was built for — one interview
    /// that arrived as two files — where wanting both is the ordinary intent.
    @Test("A meeting header summarises its recordings: off, mixed, on")
    func parentTickSummarises() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let a = row(id: "file-a", scheduled: scheduled, recorded: scheduled, meeting: "mtg")
        let b = row(id: "file-b", scheduled: scheduled,
                    recorded: scheduled.addingTimeInterval(2_400), meeting: "mtg")

        #expect(CloudImportOutline.parentTick(for: [a, b], ticked: []).draw == .off)
        #expect(CloudImportOutline.parentTick(for: [a, b], ticked: ["file-a"]).draw == .mixed)
        #expect(CloudImportOutline.parentTick(for: [a, b], ticked: ["file-a", "file-b"]).draw == .on)
    }

    /// The parent must never contradict the boxes directly beneath it. A file
    /// already on disk draws ticked — because it is here, not because it was
    /// chosen — so a meeting whose halves are both imported reads *on*, and
    /// says so while doing nothing when clicked.
    @Test("A fully-imported meeting reads on, and is disabled")
    func parentTickFollowsWhatChildrenDraw() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let held = [
            row(id: "file-a", scheduled: scheduled, recorded: scheduled,
                meeting: "mtg", local: .imported),
            row(id: "file-b", scheduled: scheduled, recorded: scheduled,
                meeting: "mtg", local: .driveNotConnected(volume: "T7")),
        ]
        let tick = CloudImportOutline.parentTick(for: held, ticked: [])
        #expect(tick.draw == .on, "both boxes below are drawn ticked")
        #expect(!tick.isEnabled, "and neither can be acted on")
    }

    /// One imported half and one fetchable half is the awkward shape, and the
    /// answer follows from the same rule: one box drawn, one not, so mixed —
    /// and clicking is still worth offering, because one child can move.
    @Test("A half-held meeting is mixed and still actionable")
    func parentTickWithOneHeldChild() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let mixed = [
            row(id: "file-a", scheduled: scheduled, recorded: scheduled,
                meeting: "mtg", local: .imported),
            row(id: "file-b", scheduled: scheduled, recorded: scheduled, meeting: "mtg"),
        ]
        let tick = CloudImportOutline.parentTick(for: mixed, ticked: [])
        #expect(tick.draw == .mixed)
        #expect(tick.isEnabled)
        // Tick the one that can move and the parent completes.
        #expect(CloudImportOutline.parentTick(for: mixed, ticked: ["file-b"]).draw == .on)
    }

    /// Nothing to tick, no tick offered — the same rule the leaf rows follow.
    /// A control that cannot act is worse than no control.
    @Test("A meeting whose recordings are all unfetchable offers no header tick")
    func parentTickAbsentWhenNothingIsTickable() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let none = [
            row(id: "file-a", scheduled: scheduled, recorded: nil,
                meeting: "mtg", video: .notOrganiser(organiser: "A. Bianchi")),
            row(id: "file-b", scheduled: scheduled, recorded: nil,
                meeting: "mtg", video: .notOrganiser(organiser: "A. Bianchi")),
        ]
        #expect(CloudImportOutline.parentTick(for: none, ticked: []) == .none)
    }

    // MARK: - Identity

    /// The contract that keeps the outline usable, and the one that would fail
    /// silently: the tree is rebuilt on every keystroke and every progress
    /// tick, and `NSOutlineView` matches its retained items against the new
    /// ones with `isEqual:`. Default `NSObject` identity would make every
    /// rebuild all-new objects — collapsing every expansion and dropping the
    /// selection on each keypress, which reads as the outline fighting the
    /// user rather than as an identity bug.
    @Test("A rebuilt tree produces nodes equal to the ones it replaces")
    func nodesSurviveARebuild() {
        let scheduled = moment(daysAgo: 3, hour: 11)
        let rows = [
            row(id: "file-a", scheduled: scheduled, recorded: scheduled, meeting: "mtg"),
            row(id: "file-b", scheduled: scheduled,
                recorded: scheduled.addingTimeInterval(2_400), meeting: "mtg"),
        ]

        let first = build(rows)
        let second = build(rows)

        #expect(first.days[0] == second.days[0])
        #expect(first.days[0].hash == second.days[0].hash)
        #expect(first.days[0].children[0] == second.days[0].children[0])
        #expect(first.days[0].children[0].children[1]
                == second.days[0].children[0].children[1])
        // Equal, but genuinely rebuilt — otherwise this proves nothing.
        #expect(first.days[0] !== second.days[0])
    }

    /// Rows with no meeting id are each their own call, never swept into one
    /// bucket together. Two unrelated ad-hoc recordings sharing a "no meeting"
    /// key would render as one meeting with two children — which on Meet means
    /// claiming they are two halves of the same session.
    @Test("Rows with no meeting are separate meetings, not one shared group")
    func nilMeetingIDsDoNotMerge() {
        let result = build([
            row(id: "a", title: "One", scheduled: moment(daysAgo: 1, hour: 9),
                recorded: moment(daysAgo: 1, hour: 9), meeting: nil),
            row(id: "b", title: "Two", scheduled: moment(daysAgo: 1, hour: 14),
                recorded: moment(daysAgo: 1, hour: 14), meeting: nil),
        ])
        #expect(result.days[0].children.count == 2)
        #expect(result.days[0].children.allSatisfy { $0.children.isEmpty })
        #expect(result.meetings == 2)
    }

    @Test("An empty list is an empty outline, not a day with nothing in it")
    func emptyIsEmpty() {
        #expect(build([]) == .empty)
    }
}
