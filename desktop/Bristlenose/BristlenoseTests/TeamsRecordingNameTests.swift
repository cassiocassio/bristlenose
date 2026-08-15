import Foundation
import Testing

@testable import Bristlenose

@Suite("Teams recording filename")
struct TeamsRecordingNameTests {

    /// The real specimen, downloaded 15 Aug 2026. Everything else in this suite
    /// is a variation on it.
    private static let realSpecimen =
        "Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4"

    private func utc(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int, _ s: Int) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar.date(from: DateComponents(
            year: y, month: mo, day: d, hour: h, minute: mi, second: s))!
    }

    @Test("Parses the real downloaded filename")
    func parsesRealSpecimen() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.realSpecimen))
        #expect(parsed.title == "Meeting with Martin Storey")
        #expect(parsed.startedAt == utc(2026, 7, 19, 14, 20, 07))
    }

    /// The bug this type exists to prevent. The same recording displayed as
    /// 16:20 in the Teams UI while the filename read 14:20:07 — the client was
    /// rendering local time in a UTC+2 zone. Parsed as local, a 30-day window
    /// shifts by the offset and silently drops meetings at each edge.
    @Test("The timestamp is UTC regardless of the machine's timezone")
    func timestampIsAlwaysUTC() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.realSpecimen))
        // An absolute instant, not a wall-clock reading — so this assertion
        // holds identically on a machine in London, Madrid or Tokyo.
        // 2026-07-19T14:20:07Z.
        #expect(parsed.startedAt.timeIntervalSince1970 == 1_784_470_807)
    }

    /// A left-to-right `split(separator: "-")` mangles this, and "Q3 Review -
    /// Design" is an entirely ordinary meeting name.
    @Test("A hyphen in the title survives")
    func hyphenatedTitle() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "Q3 Review - Design-20260719_142007UTC-Meeting Recording.mp4"))
        #expect(parsed.title == "Q3 Review - Design")
    }

    @Test("Titles with unicode and punctuation survive")
    func unicodeTitle() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "P07 Interview — ward handover 🏥-20260812_150000UTC-Meeting Recording.mp4"))
        #expect(parsed.title == "P07 Interview — ward handover 🏥")
    }

    @Test("A non-recording file is not a parse failure, just not a recording")
    func rejectsUnrelatedFiles() {
        #expect(TeamsRecordingName(filename: "Sdfasdf asdf as.docx") == nil)
        #expect(TeamsRecordingName(filename: "holiday.mp4") == nil)
        #expect(TeamsRecordingName(filename: "-20260719_142007UTC-Meeting Recording.mp4") == nil,
                "an empty title is not a valid recording name")
    }

    @Test("A malformed timestamp is rejected rather than guessed at")
    func rejectsMalformedTimestamp() {
        #expect(TeamsRecordingName(filename: "Call-2026719_142007UTC-Meeting Recording.mp4") == nil)
        #expect(TeamsRecordingName(filename: "Call-20260719_1420UTC-Meeting Recording.mp4") == nil)
        // No UTC marker: this is the shape the plan assumed before the real
        // specimen was seen. Rejecting it is deliberate — if Teams ever emits
        // it, that is a format change worth noticing, not silently absorbing.
        #expect(TeamsRecordingName(filename: "Call-20260719_142007-Meeting Recording.mp4") == nil)
    }

    // MARK: Filtering — the reason the title being in the filename matters

    @Test("Filtering is case- and diacritic-insensitive")
    func filtering() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "P07 Interview — ward handover-20260812_150000UTC-Meeting Recording.mp4"))
        #expect(parsed.matches(filter: "interview"))
        #expect(parsed.matches(filter: "INTERVIEW"))
        #expect(parsed.matches(filter: ""), "an empty filter matches everything")
        #expect(!parsed.matches(filter: "diary study"))
    }

    /// The caveat the UI has to state rather than hide: title filtering rides on
    /// meeting-naming discipline.
    @Test("A badly-named meeting does not match, and that is the documented limit")
    func namingDisciplineCaveat() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "Chat with Sarah-20260812_150000UTC-Meeting Recording.mp4"))
        #expect(!parsed.matches(filter: "Interview"))
    }
}
