import AppKit
import Testing

@testable import Bristlenose

// MARK: - Date mirror

/// The traps here are the ones a plan-review caught before implementation: both
/// obvious locale strategies are wrong, in opposite directions.
@Suite struct SessionsFinderDateTests {

    /// A fixed reference instant, built from components so the suite doesn't
    /// depend on the wall clock. Explicitly Gregorian: `Calendar.current` on a
    /// machine set to the Japanese or Buddhist calendar would read `year: 2026`
    /// in that calendar's numbering and land nowhere near the parsed Gregorian
    /// date — a spurious failure on a setting the code under test never reads
    /// (`parse` is fixed-format en_US_POSIX Gregorian).
    private func date(_ y: Int, _ m: Int, _ d: Int, _ hh: Int = 12, _ mm: Int = 0) -> Date {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone.current
        var c = DateComponents()
        c.year = y; c.month = m; c.day = d; c.hour = hh; c.minute = mm
        return cal.date(from: c)!
    }

    @Test("English renders day-month, not the US month-day order")
    func englishIsDayMonth() {
        // The bug this pins: passing the raw locale through gives Locale("en"),
        // which is US-ordered — "Feb 10, 2026" — silently breaking the exact
        // grid parity the mirror exists to provide.
        let out = SessionsFinderDate.format("2026-02-10T09:12:00",
                                            localeCode: "en",
                                            now: date(2026, 3, 1))
        #expect(out.contains("10 Feb"))
        #expect(!out.contains("Feb 10"))
    }

    @Test("Non-English locales are NOT forced into en_GB")
    func japaneseKeepsItsOwnOrder() {
        // The opposite bug: hardcoding en_GB renders "10 Feb 2026" in Japanese.
        let out = SessionsFinderDate.format("2026-02-10T09:12:00",
                                            localeCode: "ja",
                                            now: date(2026, 3, 1))
        #expect(!out.contains("Feb"))
        #expect(out.contains("2026"))
    }

    @Test("en, en-US and en-GB all resolve to en_GB")
    func englishVariantsCollapse() {
        for code in ["en", "en-US", "en-GB"] {
            #expect(SessionsFinderDate.resolvedLocale(code).identifier == "en_GB")
        }
        #expect(SessionsFinderDate.resolvedLocale("pt-BR").identifier != "en_GB")
    }

    @Test("Time is 24-hour — the Hm template, never jm")
    func timeIs24Hour() {
        // jm would give "9:12 AM" (en) or "오전 9:12" (ko). The web pins
        // hour12:false, so parity deliberately overrides the OS 12/24 setting.
        let out = SessionsFinderDate.format("2026-02-10T21:12:00",
                                            localeCode: "en",
                                            now: date(2026, 3, 1))
        #expect(out.contains("21"))
        #expect(!out.uppercased().contains("PM"))
    }

    @Test("DM1: the hour is PADDED even in locales whose own Hm pattern isn't")
    func hourIsPaddedInUnpaddedLocales() {
        // ICU's Hm pattern for es/ja/cs is "H:mm" (fi "H.mm") — a bare "9:07"
        // — while the web pins hour:"2-digit" and renders "09:07" everywhere.
        // Parity means matching the web's deliberate override of the locale.
        let now = date(2026, 3, 1)
        for code in ["es", "ja", "cs"] {
            let out = SessionsFinderDate.format("2026-02-10T09:07:00", localeCode: code, now: now)
            #expect(out.contains("09:07"), "\(code) rendered \(out)")
        }
        let fi = SessionsFinderDate.format("2026-02-10T09:07:00", localeCode: "fi", now: now)
        #expect(fi.contains("09.07"), "fi rendered \(fi)")
    }

    @Test("Today and Yesterday use the named form, not an elapsed interval")
    func namedDays() {
        // The trap: RelativeDateTimeFormatter.localizedString(for:relativeTo:) —
        // which ProjectRow.formatBareDate uses and an implementer will reach for
        // — returns "6 hours ago" here. The contract wants "Today".
        let now = date(2026, 2, 10, 18, 0)
        let today = SessionsFinderDate.format("2026-02-10T09:12:00", localeCode: "en", now: now)
        #expect(today.lowercased().hasPrefix("today"))
        #expect(!today.contains("ago"))

        let yesterday = SessionsFinderDate.format("2026-02-09T09:12:00", localeCode: "en", now: now)
        #expect(yesterday.lowercased().hasPrefix("yesterday"))
    }

    @Test("A nil date renders an em-dash, distinct from a midnight one")
    func nilIsEmDash() {
        #expect(SessionsFinderDate.format(nil, localeCode: "en") == SessionsFinderDate.emDash)

        // Transcript-only imports yield a real midnight, which must NOT collapse
        // into the same em-dash — they are different wrongnesses and the
        // fabricated one is the more plausible-looking of the two.
        let midnight = SessionsFinderDate.format("2026-02-11T00:00:00",
                                                 localeCode: "en",
                                                 now: date(2026, 3, 1))
        #expect(midnight != SessionsFinderDate.emDash)
        #expect(midnight.contains("00:00"))
    }

    @Test("Parses every shape the server actually emits")
    func parsesServerShapes() {
        // datetime.isoformat() omits microseconds when zero and emits six digits
        // when not. ISO8601DateFormatter alone rejects all of these (no timezone).
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00") != nil)
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00.123456") != nil)
        #expect(SessionsFinderDate.parse("2026-02-10") != nil)
        #expect(SessionsFinderDate.parse("not a date") == nil)
    }

    @Test("DM2: a time inside the DST spring-forward gap still parses")
    func dstGapParses() {
        // Europe/Madrid springs forward 2026-03-29 02:00→03:00, so 02:30 does
        // not exist as a wall-clock time. A non-lenient DateFormatter rejects
        // it → nil → the em-dash reserved for a genuinely ABSENT date, while
        // the web renders 03:30 for the same string. The lenient second pass
        // shifts forward, matching JS.
        let madrid = TimeZone(identifier: "Europe/Madrid")!
        #expect(SessionsFinderDate.parse("2026-03-29T02:30:00", timeZone: madrid) != nil)
        #expect(SessionsFinderDate.parse("2026-03-29T02:30:00.123456", timeZone: madrid) != nil)
        // The strict pass still owns normal strings.
        #expect(SessionsFinderDate.parse("2026-03-29T01:30:00", timeZone: madrid) != nil)
    }

    @Test("DM3: the aware-datetime fallback accepts fractional seconds")
    func awareFractionalSecondsParse() {
        // Aware datetime.isoformat() emits microseconds on essentially every
        // real timestamp. Without .withFractionalSeconds the last-resort
        // formatter rejects exactly the schema change it exists to absorb.
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00.123456+00:00") != nil)
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00.123456Z") != nil)
        // Second-precision aware strings keep working via the default options.
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00Z") != nil)
        #expect(SessionsFinderDate.parse("2026-02-10T09:12:00+01:00") != nil)
    }
}

// MARK: - Row spec

@Suite struct SessionsPopoverSpecTests {

    private func session(_ n: Int, participants: [(String, String?)]) -> SessionsPopoverSpec.Session {
        SessionsPopoverSpec.Session(
            sessionID: "s\(n)",
            number: n,
            isoDate: "2026-02-10T09:12:00",
            durationSeconds: 1591,
            participants: participants.map { SessionsPopoverSpec.Participant(code: $0.0, name: $0.1) }
        )
    }

    @Test("Row height is a function of participant count, not a binary")
    func heightIsParameterisedOverN() {
        // The finding this pins: framing height as "1-up vs stacked" yields a
        // two-case test that passes on a three-case bug. Every extra
        // participant must add a line.
        let h1 = SessionsPopoverSpec.rowHeight(participantCount: 1)
        let h2 = SessionsPopoverSpec.rowHeight(participantCount: 2)
        let h3 = SessionsPopoverSpec.rowHeight(participantCount: 3)
        let h4 = SessionsPopoverSpec.rowHeight(participantCount: 4)

        #expect(h1 < h2)
        #expect(h2 < h3)
        #expect(h3 < h4)
        // Uniform growth past the first stacked row.
        #expect(abs((h3 - h2) - (h4 - h3)) < 0.01)
        // TEST.3: pin the increment's IDENTITY, not just monotonicity — a
        // mutation to `base + n * 0.5` grows monotonically, and the off-by-one
        // `base + (n-1) * lines` would clip the last participant's name line.
        // Both pass the relative assertions above; neither passes these.
        #expect(abs((h3 - h2) - SessionsPopoverSpec.nameLineHeight) < 0.01)
        #expect(abs(h2 - (h1 + 2 * SessionsPopoverSpec.nameLineHeight)) < 0.01)
        // A zero-participant session must not be shorter than a one-up row.
        #expect(SessionsPopoverSpec.rowHeight(participantCount: 0) == h1)
    }

    @Test("Only 2+ participants stack")
    func stackingThreshold() {
        #expect(!SessionsPopoverSpec.isStacked(participantCount: 0))
        #expect(!SessionsPopoverSpec.isStacked(participantCount: 1))
        #expect(SessionsPopoverSpec.isStacked(participantCount: 2))
    }

    @Test("Type-select leads with the name so typing a person's name matches")
    func typeSelectLeadsWithName() {
        // AppKit's DEFAULT matcher is anchored-prefix. If the title led, typing
        // "beth" would match nothing — and type-select was a stated reason for
        // using a real table. The localised title is passed in, never hardcoded.
        let s = session(6, participants: [("p6", "Beth"), ("p7", nil)])
        let str = SessionsPopoverSpec.typeSelectString(
            for: s, title: "Interview 6", placeholder: "Participant")
        #expect(str.hasPrefix("Beth"))
        #expect(str.contains("p6"))
        #expect(str.contains("Interview 6"))
        #expect(!str.contains("Session"))   // English never leaks past the title param
    }

    @Test("SPEC-1: token matching reaches codes and the title, not just the leading name")
    func typeSelectTokenMatching() {
        // The default anchored-prefix matcher only reaches "beth". The
        // wrapper's nextTypeSelectMatchFromRow uses this helper so "p6" and
        // "session 6" land too — the promise the comment used to make falsely.
        let candidate = "Beth p6 Participant p7 Session 6"
        #expect(SessionsPopoverSpec.typeSelectMatches(search: "beth", candidate: candidate))
        #expect(SessionsPopoverSpec.typeSelectMatches(search: "p6", candidate: candidate))
        #expect(SessionsPopoverSpec.typeSelectMatches(search: "p7", candidate: candidate))
        #expect(SessionsPopoverSpec.typeSelectMatches(search: "session 6", candidate: candidate))
        #expect(SessionsPopoverSpec.typeSelectMatches(search: "SESSION", candidate: candidate))
        #expect(!SessionsPopoverSpec.typeSelectMatches(search: "eth", candidate: candidate))
        #expect(!SessionsPopoverSpec.typeSelectMatches(search: "", candidate: candidate))
    }

    @Test("Unnamed speakers fall back to the placeholder, including empty strings")
    func unnamedFallback() {
        // The API returns "" rather than null for a speaker the pipeline never
        // named, so an `if let` on the raw value is not enough.
        let s = session(6, participants: [("p6", ""), ("p7", nil)])
        #expect(s.participants.allSatisfy { $0.name == nil })
        let str = SessionsPopoverSpec.typeSelectString(
            for: s, title: "Session 6", placeholder: "Participant")
        #expect(str.hasPrefix("Participant"))
    }

    @Test("Accessibility label speaks each code immediately before its own name")
    func accessibilityPairsCodeWithName() {
        // Adjacency here is the ONLY thing conveying the badge↔name pairing
        // non-visually — a grid's natural reading order is often column-major
        // ("p6 p7 p8 Session 6 Beth …"), which destroys it.
        let s = session(6, participants: [("p6", "Beth"), ("p7", nil), ("p8", nil)])
        let label = SessionsPopoverSpec.accessibilityLabel(
            for: s, title: "Interview 6", placeholder: "Participant",
            duration: "19m", date: "11 Feb 2026, 09:00")

        #expect(label.contains("p6 Beth"))
        #expect(label.contains("p7 Participant"))
        // SPEC-2: the spoken title is the LOCALISED one — a German VoiceOver
        // user hears "Interview 6", the words on screen, never English.
        #expect(label.hasPrefix("Interview 6"))
        // Commas pause; a middot is read as nothing at all.
        #expect(!label.contains("\u{00B7}"))
    }

    @Test("A missing date is omitted from the spoken label rather than read as a dash")
    func accessibilityOmitsEmDash() {
        let s = session(1, participants: [("p1", "Yuki")])
        let label = SessionsPopoverSpec.accessibilityLabel(
            for: s, title: "Session 1", placeholder: "Participant",
            duration: "26m", date: SessionsFinderDate.emDash)
        #expect(!label.contains(SessionsFinderDate.emDash))
        #expect(label.contains("26m"))
    }
}

// MARK: - Fetch identity

/// The invariant behind the highest-severity plan-review finding: a parked
/// sidecar stays alive and authorised, so a stale (port, token) pair returns
/// HTTP 200 with the *previous project's* participant names.
@Suite struct SessionsFetchIdentityTests {

    @Test("A response is published only when its port is still the serving port")
    func portMustStillMatch() {
        #expect(SessionsFetchIdentity.shouldPublish(responseFrom: 51234, currentPort: 51234))
        // The bug: a project switch overtook the fetch. The old sidecar answered
        // 200 because it is parked, not stopped.
        #expect(!SessionsFetchIdentity.shouldPublish(responseFrom: 51234, currentPort: 51999))
    }

    @Test("Nothing is published when no serve is running")
    func noServeMeansNoPublish() {
        #expect(!SessionsFetchIdentity.shouldPublish(responseFrom: 51234, currentPort: nil))
    }
}

// MARK: - Load state

@Suite struct SessionsLoadStateTests {

    @Test("An empty list is a distinct state from a failure")
    func emptyIsNotFailure() {
        // A 200 carrying zero sessions is a correct answer — it is what a
        // just-imported project looks like. Collapsing it into the failure
        // state teaches the researcher to distrust an accurate screen.
        #expect(SessionsLoadState.empty != SessionsLoadState.unreachable)
        #expect(SessionsLoadState.empty != SessionsLoadState.loading)
    }

    @Test("No identity yields unreachable without sending a request")
    func nilIdentityIsUnreachable() async {
        // Sending with no Authorization header 401s with the identical body a
        // wrong-token request produces, destroying the one diagnostic signal.
        let state = await SessionsAPI.load { nil }
        #expect(state == .unreachable)
    }

    @Test("The model keeps its previous state when a fetch is superseded")
    func modelKeepsStateOnSupersededFetch() async {
        // A nil from load means "overtaken by a project switch" — the model
        // must keep what it was showing, not flash to unreachable off an old
        // fetch's failure.
        let model = await SessionsPopoverModel()
        let flipper = await PortFlipper()
        await model.refresh { flipper.next() }
        #expect(await model.state == .loading)   // unchanged: the nil was discarded

        // A genuine no-identity refresh, by contrast, publishes unreachable.
        await model.refresh { nil }
        #expect(await model.state == .unreachable)
    }

    @Test("API2/rule 3: a fetch overtaken by a project switch is discarded, not published")
    func supersededFetchIsDiscarded() async {
        // The provider answers port 1 at request-build time and port 2 after
        // the await — the parked-sidecar switch scenario. The result must be
        // nil (keep previous state), NOT .unreachable: an old fetch's
        // connection-refused must not mark the NEW project unreachable, any
        // more than its 200 may show the old project's names.
        let flipper = await PortFlipper()
        let state = await SessionsAPI.load { flipper.next() }
        #expect(state == nil)
        #expect(await flipper.calls >= 2)   // read at build time AND re-read after the await
    }
}

/// Serves port 1 to the first provider read and port 2 to every later one —
/// the minimal model of a project switch overtaking an in-flight fetch.
@MainActor
private final class PortFlipper {
    private(set) var calls = 0
    func next() -> (port: Int, token: String)? {
        calls += 1
        return (port: calls == 1 ? 1 : 2, token: "t")
    }
}

// MARK: - Route memory

@Suite struct SessionsRouteMemoryTests {

    @Test("Parses the three route shapes and rejects everything else")
    func parsing() {
        typealias R = SessionsRouteMemory
        #expect(R.sessionsRoute(fromPath: "/report/sessions/") == .index)
        #expect(R.sessionsRoute(fromPath: "/report/sessions") == .index)
        #expect(R.sessionsRoute(fromPath: "/report/sessions/s3") == .session("s3"))
        #expect(R.sessionsRoute(fromPath: "/report/sessions/s12?x=1#t-40") == .session("s12"))
        #expect(R.sessionsRoute(fromPath: "/report/quotes/") == nil)
        #expect(R.sessionsRoute(fromPath: "/report/") == nil)
        // The server serves transcript_*.html under the same prefix — a
        // non-session filename must never become a restore target.
        #expect(R.sessionsRoute(fromPath: "/report/sessions/transcript_s1.html") == nil)
        #expect(R.sessionsRoute(fromPath: "/report/sessions/s3/extra") == nil)
        #expect(R.sessionsRoute(fromPath: "/report/sessionsfoo") == nil)
        #expect(R.sessionsRoute(fromPath: "/report/sessions/sX") == nil)
    }

    @Test("Remembers the last transcript; visiting the grid resets to index")
    func observeAndReset() {
        var m = SessionsRouteMemory()
        #expect(m.restoreSessionID == nil)
        m.observe(path: "/report/sessions/s3")
        #expect(m.restoreSessionID == "s3")
        // Other lenses leave the memory alone — leaving Sessions and coming
        // back is exactly the restore case.
        m.observe(path: "/report/quotes/")
        #expect(m.restoreSessionID == "s3")
        // The grid resets it: "the view the user left" is now the index.
        m.observe(path: "/report/sessions/")
        #expect(m.restoreSessionID == nil)
        m.observe(path: "/report/sessions/s7")
        m.clear()   // run completion / project switch
        #expect(m.restoreSessionID == nil)
    }
}

// MARK: - Table outcome

/// The OUTCOME tests the review demanded (Finding 40, accepted): a pure
/// `rowHeight(participantCount:)` test passes whether or not the delegate is
/// ever consulted — under any `rowSizeStyle` other than `.custom` the height
/// delegate is silently never called and every row reports the same pinned
/// height. `rect(ofRow:)` differing between a single and a stacked row is the
/// one assertion that fails on that real bug.
@MainActor
@Suite struct SessionsPopoverTableTests {

    private func row(_ n: Int, participants: [(String, String?)]) -> SessionsPopoverRow {
        let session = SessionsPopoverSpec.Session(
            sessionID: "s\(n)",
            number: n,
            isoDate: "2026-02-10T09:12:00",
            durationSeconds: 1591,
            participants: participants.map { SessionsPopoverSpec.Participant(code: $0.0, name: $0.1) }
        )
        return SessionsPopoverRow(
            session: session,
            title: "Session \(n)",
            subtitle: "26m · 10 Feb 2026, 09:12",
            placeholder: "Participant",
            typeSelect: SessionsPopoverSpec.typeSelectString(
                for: session, title: "Session \(n)", placeholder: "Participant"),
            accessibility: SessionsPopoverSpec.accessibilityLabel(
                for: session, title: "Session \(n)", placeholder: "Participant",
                duration: "26m", date: "10 Feb 2026, 09:12")
        )
    }

    private func makeTable(rows: [SessionsPopoverRow])
        -> (NSTableView, SessionsPopoverList.Coordinator) {
        let table = SessionsPopoverTableView(frame: NSRect(x: 0, y: 0, width: 308, height: 600))
        configureSourceListTable(table)
        let coordinator = SessionsPopoverList.Coordinator(
            rows: rows, onCommit: { _ in }, onCancel: {})
        coordinator.table = table
        table.dataSource = coordinator
        table.delegate = coordinator
        table.reloadData()
        table.layoutSubtreeIfNeeded()
        return (table, coordinator)
    }

    @Test("configureSourceListTable postconditions — each silently inert when wrong")
    func configurationPostconditions() {
        let table = NSTableView()
        configureSourceListTable(table)
        #expect(table.rowSizeStyle == .custom)          // else heightOfRow is never called
        #expect(table.style == .sourceList)
        #expect(table.selectionHighlightStyle == .sourceList)  // else no capsule
        #expect(table.headerView == nil)
        #expect(table.tableColumns.count == 1)
        #expect(!table.allowsMultipleSelection)
    }

    @Test("rect(ofRow:) heights differ between single and stacked rows")
    func laidOutHeightsFollowParticipantCount() {
        let (table, _) = makeTable(rows: [
            row(1, participants: [("p1", "Yuki")]),
            row(2, participants: [("p2", "Beth"), ("p3", nil), ("p4", nil)]),
        ])
        let single = table.rect(ofRow: 0).height
        let stacked = table.rect(ofRow: 1).height
        // The load-bearing assertion: under any non-.custom rowSizeStyle both
        // rows report the same pinned height and this fails.
        #expect(single != stacked)
        #expect(abs(single - SessionsPopoverSpec.rowHeight(participantCount: 1)) < 0.5)
        #expect(abs(stacked - SessionsPopoverSpec.rowHeight(participantCount: 3)) < 0.5)
    }

    @Test("The row view inherits the shared source-list row view, so the two surfaces cannot drift")
    func sharedRowView() {
        let (table, coordinator) = makeTable(rows: [row(1, participants: [("p1", "Yuki")])])
        let rowView = coordinator.tableView(table, rowViewForRow: 0)
        // The hover subclass (menu-role pointer tracking) IS-A the shared row
        // view — the capsule pin is inherited, not duplicated. The sidebar
        // keeps the hover-free base class.
        #expect(rowView is SessionsPopoverHoverRowView)
        #expect(rowView is SourceListSelectionRowView)
        #expect(rowView?.isEmphasized == false)
        rowView?.isEmphasized = true                    // the pin: writes are ignored
        #expect(rowView?.isEmphasized == false)
    }

    @Test("The badge reports a text baseline so the grid can align it to the name")
    func badgeReportsBaseline() {
        // A plain NSView reports no baseline, and NSGridView's .firstBaseline
        // alignment then falls back to edge placement — the chip sat visibly
        // below the text beside it (QA screenshot, 14 Aug 2026). The offset
        // must be the label's own baseline plus the chip's vertical inset —
        // i.e. strictly greater than the bare label's, and within the chip.
        let badge = SpeakerBadgeView(code: "p1")
        let bare = NSTextField(labelWithString: "p1")
        bare.font = SpeakerBadgeView.font
        #expect(badge.firstBaselineOffsetFromTop > bare.firstBaselineOffsetFromTop)
        #expect(badge.firstBaselineOffsetFromTop < badge.intrinsicContentSize.height)
    }

    @Test("Token type-select finds codes on non-leading rows, wrapping the search")
    func nextTypeSelectMatch() {
        let (table, coordinator) = makeTable(rows: [
            row(1, participants: [("p1", "Yuki")]),
            row(6, participants: [("p6", "Beth"), ("p7", nil)]),
        ])
        // "p6" is unreachable by the default anchored-prefix matcher (row 1's
        // string starts "Beth"); the token matcher must find row 1.
        let match = coordinator.tableView(table, nextTypeSelectMatchFromRow: 0, toRow: 0, for: "p6")
        #expect(match == 1)
        let miss = coordinator.tableView(table, nextTypeSelectMatchFromRow: 0, toRow: 0, for: "zzz")
        #expect(miss == -1)
    }

    @Test("Selection change alone never commits — navigation is click/Return only")
    func selectionDoesNotCommit() {
        var committed = 0
        let table = SessionsPopoverTableView(frame: NSRect(x: 0, y: 0, width: 308, height: 600))
        configureSourceListTable(table)
        let coordinator = SessionsPopoverList.Coordinator(
            rows: [row(1, participants: [("p1", "Yuki")]),
                   row(2, participants: [("p2", "Priya")])],
            onCommit: { _ in committed += 1 }, onCancel: {})
        coordinator.table = table
        table.dataSource = coordinator
        table.delegate = coordinator
        table.reloadData()
        // Arrowing = selection movement. The chooser contract: no commit.
        table.selectRowIndexes(IndexSet(integer: 0), byExtendingSelection: false)
        table.selectRowIndexes(IndexSet(integer: 1), byExtendingSelection: false)
        #expect(committed == 0)
        // Return commits the selected row.
        coordinator.commitSelectedRow()
        #expect(committed == 1)
    }
}
