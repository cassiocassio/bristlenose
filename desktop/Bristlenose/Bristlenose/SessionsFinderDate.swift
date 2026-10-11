import Foundation

/// Swift mirror of `formatFinderDate` in `frontend/src/utils/format.ts:20`.
///
/// The sessions popover's subtitle is at **exact parity with the Sessions grid's
/// Start column**, so this reproduces the TS contract rather than inventing a
/// native one. Four things about it are load-bearing and each was got wrong in
/// an earlier draft of the design:
///
/// 1. **`en*` maps to `en_GB`, everything else passes through.** Hardcoding
///    `en_GB` renders `10 Feb 2026` in Japanese, where the locale wants
///    `2026年2月10日` — wrong in 19 locales. But passing the raw locale renders
///    `Feb 10, 2026` in *English*, breaking the very grid parity this exists for
///    (`Locale("en")` is US-ordered). The TS does `locale.startsWith("en") ?
///    "en-GB" : locale`; so do we.
/// 2. **Time uses the `Hm` template, not `jm`.** `jm` is locale-preferred and
///    yields `9:12 AM` / `오전 9:12`; the web pins `hour12: false`. This
///    therefore *deliberately overrides* the user's 12/24-hour system setting,
///    because matching the other surface matters more here than matching the OS.
/// 3. **Today/Yesterday come from `DateComponents`, not from a time interval.**
///    `RelativeDateTimeFormatter.localizedString(for:relativeTo:)` — which is
///    what `ProjectRow.formatBareDate`'s `relative()` uses, and what an
///    implementer will reach for — returns "6 hours ago" for a session recorded
///    this morning. The contract wants "Today". `localizedString(from:
///    DateComponents(day: 0))` is the call that yields the named form, and it
///    comes from Apple's own CLDR data, so it needs no glossary check in any
///    future locale.
/// 4. **`nil` renders an em-dash**, matching `format.ts:22`. A genuinely absent
///    date must stay distinguishable from the midnight that a date-only
///    transcript header produces (see the KNOWN-WRONG note below).
///
/// The value is `sessions.session_date`, the session's START as resolved by
/// `bristlenose/utils/session_start.py` (11 Oct 2026): Bristlenose's own
/// cloud-import stamp, a Teams/Zoom/Screen Recording filename, the recorder's
/// own container time, or — last — the file's creation time. Until then it was
/// the file's creation time, which for most recorders is the session's END.
/// The server sends it UTC-marked (`+00:00`), so it renders on this Mac's clock.
/// Still owed (`docs/design-timezones.md` § 5.10): a transcript-only import
/// with a date-only header carries a fabricated local midnight, and a session
/// whose signals disagree has no marker here — both render plausibly. Parity
/// with the web is deliberate so one fix lands on both surfaces at once.
///
/// There is also a third, Python implementation (`bristlenose/utils/markdown.py`
/// `format_finder_date`) which renders `Today at 16:59` — a different separator.
/// This popover adopts the **TypeScript** contract. No cross-language fixture:
/// these are independent local renderings, not a wire format, so a mismatch is
/// cosmetic (unlike the Swift/Python `start_time` token, which is parsed).
enum SessionsFinderDate {

    /// Format an ISO date string the way the Sessions grid does.
    /// - Parameters:
    ///   - iso: `datetime.isoformat()` output from the server, or nil.
    ///   - localeCode: the app's locale (`I18n.locale`), e.g. `"en"`, `"ja"`.
    ///   - now: injected for testability — callers omit it.
    /// - Returns: `"Today, 09:12"`, `"10 Feb 2026, 09:12"`, or `"—"`.
    static func format(_ iso: String?, localeCode: String, now: Date = Date()) -> String {
        guard let iso, let date = parse(iso) else { return emDash }

        let locale = resolvedLocale(localeCode)
        let time = timeString(date, locale: locale)

        let calendar = calendar(for: locale)
        if let named = namedDay(for: date, now: now, calendar: calendar, locale: locale) {
            return "\(named), \(time)"
        }
        return "\(absoluteDate(date, locale: locale)), \(time)"
    }

    static let emDash = "\u{2014}"

    // MARK: - Locale

    /// `en`, `en-US`, `en-GB` → `en_GB` (day-month order, matching the web).
    /// Everything else passes through untouched — hyphenated codes such as
    /// `pt-BR` and `zh-Hant-HK` canonicalise through `Locale(identifier:)`
    /// unchanged.
    static func resolvedLocale(_ localeCode: String) -> Locale {
        localeCode.hasPrefix("en") || localeCode.isEmpty
            ? Locale(identifier: "en_GB")
            : Locale(identifier: localeCode)
    }

    private static func calendar(for locale: Locale) -> Calendar {
        var cal = Calendar.current
        cal.locale = locale
        return cal
    }

    // MARK: - Parsing

    /// Since 11 Oct 2026 the server sends an AWARE UTC string (`+00:00`), which
    /// the naive passes below reject and the ISO 8601 fallback reads — measured:
    /// neither the strict nor the lenient formatter accepts a trailing offset.
    /// The naive passes stay for older servers and the export of an older
    /// project, which sent `datetime.isoformat()` with no zone; JavaScript's
    /// `new Date(...)` reads that as **local** time, so we do too.
    ///
    /// `timeZone` is injectable for tests only (the DST case below is
    /// timezone-specific); production callers omit it.
    static func parse(_ iso: String, timeZone: TimeZone = .current) -> Date? {
        // Strict pass — the shapes the server actually emits.
        for format in naiveFormats {
            if let date = formatter(format, timeZone: timeZone).date(from: iso) {
                return date
            }
        }

        // DM2: a wall-clock time inside the DST spring-forward gap does not
        // exist, and a non-lenient DateFormatter rejects it — while JS's
        // `new Date("2026-03-29T02:30:00")` shifts it forward to 03:30. A
        // lenient SECOND pass matches JS for the gap without loosening the
        // strict pass for normal strings. Accepted divergence: a lenient
        // formatter also rolls out-of-range components (month 13 → January)
        // where JS rejects — the server never emits those, the gap is real.
        for format in naiveFormats {
            let df = formatter(format, timeZone: timeZone)
            df.isLenient = true
            if let date = df.date(from: iso) { return date }
        }

        // Timezone-bearing strings — what the server sends since 11 Oct 2026.
        // DM3: the default-options formatter REJECTS fractional seconds, and
        // aware `datetime.isoformat()` emits microseconds on essentially every
        // real timestamp — so without the `.withFractionalSeconds` attempt this
        // fallback would fail for exactly the schema change it exists to absorb.
        if let date = ISO8601DateFormatter().date(from: iso) { return date }
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fractional.date(from: iso)
    }

    private static let naiveFormats = [
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss.SSS",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd'T'HH:mm",
        "yyyy-MM-dd",
    ]

    private static func formatter(_ format: String, timeZone: TimeZone) -> DateFormatter {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")   // fixed-format parsing
        df.timeZone = timeZone
        df.dateFormat = format
        return df
    }

    // MARK: - Components

    /// "Today" / "Yesterday" in the locale's own words, capitalised — or nil
    /// when the date is neither. Uses `DateComponents`, not a time interval;
    /// see the type doc.
    private static func namedDay(for date: Date,
                                 now: Date,
                                 calendar: Calendar,
                                 locale: Locale) -> String? {
        let day: Int
        if calendar.isDate(date, inSameDayAs: now) {
            day = 0
        } else if let yesterday = calendar.date(byAdding: .day, value: -1, to: now),
                  calendar.isDate(date, inSameDayAs: yesterday) {
            day = -1
        } else {
            return nil
        }

        let rdf = RelativeDateTimeFormatter()
        rdf.locale = locale
        rdf.dateTimeStyle = .named
        rdf.unitsStyle = .full
        let word = rdf.localizedString(from: DateComponents(day: day))
        return capitalisingFirst(word, locale: locale)
    }

    /// The TS does `word[0].toUpperCase() + word.slice(1)` — first character
    /// only, never a title-case pass (which would give "Yesterday Evening"-style
    /// mangling in locales whose word is multi-token).
    private static func capitalisingFirst(_ s: String, locale: Locale) -> String {
        guard let first = s.first else { return s }
        return String(first).uppercased(with: locale) + s.dropFirst()
    }

    /// `d MMM yyyy` reordered for the locale — `10 Feb 2026`, `2026年2月10日`.
    private static func absoluteDate(_ date: Date, locale: Locale) -> String {
        let df = DateFormatter()
        df.locale = locale
        df.setLocalizedDateFormatFromTemplate("d MMM yyyy")
        return df.string(from: date)
    }

    /// 24-hour, locale-correct separator. `Hm`, never `jm` — see the type doc.
    ///
    /// DM1: ICU's localised `Hm` pattern is UNPADDED (`H:mm` → "9:07") in
    /// es/ja/cs and `H.mm` in fi — that is those locales' own CLDR convention.
    /// The web deliberately overrides it (`hour: "2-digit"` in `format.ts:32`)
    /// so times align in a tabular column, and parity obliges the same override
    /// here. A padded `HHmm` *skeleton* does not work — ICU still returns
    /// `H:mm` for those locales — so the lone `H` field is widened by hand,
    /// preserving the locale's own separator.
    private static func timeString(_ date: Date, locale: Locale) -> String {
        let df = DateFormatter()
        df.locale = locale
        df.setLocalizedDateFormatFromTemplate("Hm")
        if let pattern = df.dateFormat, !pattern.contains("HH"),
           let lone = pattern.range(of: "H") {
            df.dateFormat = pattern.replacingCharacters(in: lone, with: "HH")
        }
        return df.string(from: date)
    }
}
