import Foundation

/// Parses a Teams recording filename into the title and, when the filename
/// says so, the moment it started.
///
/// Two real specimens, both captured 15 Aug 2026:
///
///     Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4   (personal)
///     Meeting with Martin Storey-20260815_200732-Meeting Recording.mp4      (business)
///
/// Three things make this worth a type rather than a `split(separator: "-")`.
///
/// **The title can contain hyphens.** "Q3 Review - Design" is an ordinary
/// meeting name, and a left-to-right split mangles it. So this parses from the
/// *right*, where the structure is fixed, and treats everything before the
/// timestamp as the title.
///
/// **The `UTC` marker is optional, and its absence is not cosmetic.** A
/// business tenant omits it, and what it writes instead is **local time, with
/// nothing saying whose**. Measured on the business specimen above: the filename
/// reads 20:07:32, the mp4's own `creation_time` reads `2026-08-15T18:07:38Z`,
/// and the recording machine was on `Europe/Madrid` (UTC+2) — so the two agree
/// exactly, and the filename is simply the wall clock in front of whoever hit
/// record.
///
/// That is unresolvable rather than merely undeclared. The importing machine is
/// not necessarily the recording one: a researcher in London opening a
/// colleague's Madrid recording has no way to know the digits were written two
/// hours ahead of their own clock, and neither has this parser.
///
/// So an unmarked timestamp cannot be resolved to a moment by *any* regex.
/// `startedAtUTC` is nil in that case, deliberately, and the caller must take
/// the moment from a source that carries a zone — `driveItem.createdDateTime`
/// over Graph, or `format.tags.creation_time` from the file itself. Returning
/// a plausible-looking wrong Date here is how a 30-day window silently drops
/// meetings at each edge.
///
/// Why this matters at all: the title being *in the filename* is what lets the
/// import list be filtered on "Interview" using `Files.Read` alone, with no
/// calendar scope. See docs/design-cloud-import.md §6. The **title** is what
/// this type exists to recover; the timestamp is a bonus that only sometimes
/// arrives.
struct TeamsRecordingName: Equatable {
    /// The meeting title as Teams recorded it. Not sanitised — it is
    /// third-party-controlled text (§9), so it must go through `safe_filename`
    /// before becoming a path component and be wrapped before reaching a prompt.
    let title: String

    /// Recording start in UTC — **only when the filename carried the `UTC`
    /// marker.** Nil on a business-tenant filename, where the digits are the
    /// recorder's local wall clock and carry no zone (see the type note).
    /// Callers must fall back to a zone-carrying source rather than treating nil
    /// as "no date".
    ///
    /// Note this is recording-start, not meeting-start: the gap between them is
    /// however late everyone joined, and is the tolerance the calendar join has
    /// to allow for.
    let startedAtUTC: Date?

    /// The timestamp exactly as the filename wrote it, zone unresolved.
    ///
    /// Kept because it is still useful for *disambiguation* — two recordings of
    /// the same weekly meeting differ here even when neither can be placed on a
    /// clock — and because it is the only date-ish thing a transcript sibling
    /// can be matched against. Never render it as a time.
    let timestampDigits: String

    /// The fixed tail Teams appends. Held as a constant rather than inlined so
    /// the localisation question has somewhere to live: whether this suffix
    /// translates is **unverified** (it is the open half of Q5), and if it does,
    /// filename parsing becomes locale-dependent and title filtering moves
    /// behind the calendar scope instead of being free.
    static let suffix = "-Meeting Recording"

    /// `UTC` is optional because a business tenant omits it. Capturing it
    /// rather than merely tolerating it is the point: its presence is the only
    /// evidence that the digits mean anything on a clock.
    private static let timestampPattern = /^(.+)-(\d{8})_(\d{6})(UTC)?$/

    /// Returns `nil` rather than throwing: a file that does not match is simply
    /// not a Teams recording, which is an ordinary condition in a folder listing
    /// and not an error worth surfacing.
    init?(filename: String) {
        var stem = filename
        for ext in [".mp4", ".m4a"] where stem.hasSuffix(ext) {
            stem.removeLast(ext.count)
            break
        }
        guard stem.hasSuffix(Self.suffix) else { return nil }
        stem.removeLast(Self.suffix.count)

        guard let match = stem.wholeMatch(of: Self.timestampPattern) else { return nil }

        let rawTitle = String(match.1)
        guard !rawTitle.isEmpty else { return nil }

        let yyyymmdd = String(match.2), hhmmss = String(match.3)

        // A date is only computed when the filename declared its zone. Without
        // the marker the digits are somebody's local wall clock and we do not
        // know whose, so there is no honest Date to return — see the type note.
        let isZoneQualified = match.4 != nil
        let resolved = isZoneQualified ? Self.date(yyyymmdd: yyyymmdd, hhmmss: hhmmss) : nil
        if isZoneQualified, resolved == nil { return nil }   // marked UTC but not a real date

        self.title = rawTitle
        self.timestampDigits = "\(yyyymmdd)_\(hhmmss)"
        self.startedAtUTC = resolved
    }

    private static func date(yyyymmdd: String, hhmmss: String) -> Date? {
        func number(_ s: Substring) -> Int? { Int(s) }
        let d = Array(yyyymmdd), t = Array(hhmmss)
        guard d.count == 8, t.count == 6 else { return nil }

        var components = DateComponents()
        components.year = number(yyyymmdd.prefix(4))
        components.month = number(yyyymmdd.dropFirst(4).prefix(2))
        components.day = number(yyyymmdd.dropFirst(6))
        components.hour = number(hhmmss.prefix(2))
        components.minute = number(hhmmss.dropFirst(2).prefix(2))
        components.second = number(hhmmss.dropFirst(4))

        // UTC, explicitly and always. The suffix in the filename says so, and
        // this is the single line that keeps the window boundary honest.
        var calendar = Calendar(identifier: .gregorian)
        guard let utc = TimeZone(identifier: "UTC") else { return nil }
        calendar.timeZone = utc
        return calendar.date(from: components)
    }
}

extension TeamsRecordingName {
    /// Whether the title matches a filter, using the same case- and
    /// diacritic-insensitive comparison the list field should use. Kept beside
    /// the parser so the filter and the parse cannot drift apart.
    func matches(filter: String) -> Bool {
        guard !filter.isEmpty else { return true }
        return title.range(of: filter, options: [.caseInsensitive, .diacriticInsensitive]) != nil
    }
}
