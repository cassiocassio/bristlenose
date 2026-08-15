import Foundation

/// Parses a Teams recording filename into the title and the moment it started.
///
/// Real specimen, downloaded 15 Aug 2026:
///
///     Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4
///
/// Two things make this worth a type rather than a `split(separator: "-")`.
///
/// **The title can contain hyphens.** "Q3 Review - Design" is an ordinary
/// meeting name, and a left-to-right split mangles it. So this parses from the
/// *right*, where the structure is fixed, and treats everything before the
/// timestamp as the title.
///
/// **The timestamp is UTC and says so.** That `UTC` suffix is load-bearing: the
/// same specimen displayed as 16:20 in the Teams UI while the filename read
/// 14:20:07 — a two-hour offset from the client rendering local time. Parse it
/// as local and a 30-day window is wrong by the offset, silently dropping
/// meetings at each edge.
///
/// Why this matters at all: the title being *in the filename* is what lets the
/// import list be filtered on "Interview" using `Files.Read` alone, with no
/// calendar scope. See docs/design-cloud-import.md §6.
struct TeamsRecordingName: Equatable {
    /// The meeting title as Teams recorded it. Not sanitised — it is
    /// third-party-controlled text (§9), so it must go through `safe_filename`
    /// before becoming a path component and be wrapped before reaching a prompt.
    let title: String

    /// Recording start, in UTC. Note this is recording-start, not meeting-start:
    /// the gap between them is however late everyone joined, and is the
    /// tolerance the calendar join has to allow for.
    let startedAt: Date

    /// The fixed tail Teams appends. Held as a constant rather than inlined so
    /// the localisation question has somewhere to live: whether this suffix
    /// translates is **unverified** (it is the open half of Q5), and if it does,
    /// filename parsing becomes locale-dependent and title filtering moves
    /// behind the calendar scope instead of being free.
    static let suffix = "-Meeting Recording"

    private static let timestampPattern = /^(.+)-(\d{8})_(\d{6})UTC$/

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

        guard let date = Self.date(yyyymmdd: String(match.2), hhmmss: String(match.3)) else {
            return nil
        }

        self.title = rawTitle
        self.startedAt = date
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
