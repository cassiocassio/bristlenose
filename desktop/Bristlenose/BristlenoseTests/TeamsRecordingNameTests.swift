import Foundation
import Testing

@testable import Bristlenose

@Suite("Teams recording filename")
struct TeamsRecordingNameTests {

    // Two real specimens, both captured 15 Aug 2026 from live tenants. Every
    // other case in this suite is a variation on one of them.
    //
    // The difference between them is the whole subject of this file: a personal
    // tenant marks the timestamp `UTC`, a business tenant does not — and the
    // business one is the tier that ships.

    /// Personal OneDrive. Timestamp declares its zone.
    private static let personalSpecimen =
        "Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4"

    /// Business tenant (`bristlenose.onmicrosoft.com`), recorded and downloaded
    /// 15 Aug 2026. **No `UTC` marker.**
    private static let businessSpecimen =
        "Meeting with Martin Storey-20260815_200732-Meeting Recording.mp4"

    private func utc(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int, _ s: Int) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar.date(from: DateComponents(
            year: y, month: mo, day: d, hour: h, minute: mi, second: s))!
    }

    // MARK: The two tiers

    @Test("Parses the personal specimen, timestamp and all")
    func parsesPersonalSpecimen() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.personalSpecimen))
        #expect(parsed.title == "Meeting with Martin Storey")
        #expect(parsed.startedAtUTC == utc(2026, 7, 19, 14, 20, 07))
    }

    /// The regression this suite was rewritten for. Before 15 Aug 2026 this
    /// filename was **rejected**, by a test that asserted the rejection on the
    /// reasoning that Teams would never emit it. Teams emits it on every
    /// business tenant, so every business recording was dropped from the
    /// listing — and because a dropped row leaves `outcome` untouched, the
    /// import window reported a folder full of recordings as empty.
    @Test("Parses the business specimen, which carries no UTC marker")
    func parsesBusinessSpecimen() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.businessSpecimen))
        #expect(parsed.title == "Meeting with Martin Storey")
        #expect(parsed.timestampDigits == "20260815_200732")
    }

    /// Measured, not assumed. The business specimen's filename reads 20:07:32;
    /// the mp4's own `format.tags.creation_time` reads `2026-08-15T18:07:38Z`;
    /// the machine was in London on BST (UTC+1). The filename is therefore
    /// UTC+2 — a server-side zone, set on the tenant or the mailbox, invisible
    /// from the filename and not the user's own.
    ///
    /// So there is no correct way to turn those digits into an instant, and
    /// returning a plausible-looking wrong `Date` is worse than returning none:
    /// it shifts the 30-day window by the offset and drops meetings at each
    /// edge without a single error.
    @Test("An unmarked timestamp yields no date rather than a guessed one")
    func unmarkedTimestampHasNoResolvedDate() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.businessSpecimen))
        #expect(parsed.startedAtUTC == nil,
                "unknowable zone — the caller must use driveItem.createdDateTime")
    }

    /// An absolute instant, not a wall-clock reading — so this holds identically
    /// on a machine in London, Madrid or Tokyo. 2026-07-19T14:20:07Z.
    @Test("A marked timestamp is UTC regardless of the machine's timezone")
    func markedTimestampIsAlwaysUTC() throws {
        let parsed = try #require(TeamsRecordingName(filename: Self.personalSpecimen))
        #expect(parsed.startedAtUTC?.timeIntervalSince1970 == 1_784_470_807)
    }

    @Test("Both tiers yield the same title for the same meeting")
    func titleIsTierIndependent() throws {
        let personal = try #require(TeamsRecordingName(filename: Self.personalSpecimen))
        let business = try #require(TeamsRecordingName(filename: Self.businessSpecimen))
        #expect(personal.title == business.title,
                "§6 needs the title from the filename; it must not depend on tier")
    }

    // MARK: Title recovery

    /// A left-to-right `split(separator: "-")` mangles this, and "Q3 Review -
    /// Design" is an entirely ordinary meeting name. Checked on both tiers,
    /// because the business form has one fewer landmark to parse from.
    @Test("A hyphen in the title survives, on both tiers")
    func hyphenatedTitle() throws {
        let marked = try #require(TeamsRecordingName(
            filename: "Q3 Review - Design-20260719_142007UTC-Meeting Recording.mp4"))
        #expect(marked.title == "Q3 Review - Design")

        let unmarked = try #require(TeamsRecordingName(
            filename: "Q3 Review - Design-20260815_200732-Meeting Recording.mp4"))
        #expect(unmarked.title == "Q3 Review - Design")
    }

    @Test("Titles with unicode and punctuation survive")
    func unicodeTitle() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "P07 Interview — ward handover 🏥-20260812_150000UTC-Meeting Recording.mp4"))
        #expect(parsed.title == "P07 Interview — ward handover 🏥")
    }

    @Test("The .m4a audio-only variant parses the same way")
    func audioOnlyExtension() throws {
        let parsed = try #require(TeamsRecordingName(
            filename: "Meeting with Martin Storey-20260815_200732-Meeting Recording.m4a"))
        #expect(parsed.title == "Meeting with Martin Storey")
    }

    // MARK: Rejection

    @Test("A non-recording file is not a parse failure, just not a recording")
    func rejectsUnrelatedFiles() {
        #expect(TeamsRecordingName(filename: "Sdfasdf asdf as.docx") == nil)
        #expect(TeamsRecordingName(filename: "holiday.mp4") == nil)
        #expect(TeamsRecordingName(filename: "-20260719_142007UTC-Meeting Recording.mp4") == nil,
                "an empty title is not a valid recording name")
        // The transcript sibling. Teams names it with the bare title and no
        // timestamp at all, so it is correctly not a recording — but note that
        // leaves title as the only thing pairing it to its video.
        #expect(TeamsRecordingName(filename: "Meeting with Martin Storey.vtt") == nil)
    }

    @Test("A malformed timestamp is rejected rather than guessed at")
    func rejectsMalformedTimestamp() {
        #expect(TeamsRecordingName(filename: "Call-2026719_142007UTC-Meeting Recording.mp4") == nil)
        #expect(TeamsRecordingName(filename: "Call-20260719_1420UTC-Meeting Recording.mp4") == nil)
        #expect(TeamsRecordingName(filename: "Call-20260719_142007XYZ-Meeting Recording.mp4") == nil,
                "an unrecognised zone marker is a format change, not one to absorb")
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
