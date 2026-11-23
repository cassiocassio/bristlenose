import Combine
import Foundation
import Testing
@testable import Bristlenose

/// AutoCode landing plan Phase 5 (Mac): the row's line for an AutoCode run that stopped, failed or
/// finished partly, in the pipeline run's words (D13, D23); where it ranks against the pipeline's
/// lines; that it outlives the study's server and clears when the study is opened or the codebook
/// started again; the ring's Stop; and the busy hold that follows progress (D16, refined).

private func ended(_ outcome: AutoCodeEndedLine.Outcome, _ kind: String = "",
                   framework: String = "uxr", started: String = "2026-11-23T10:00:00",
                   processed: Int = 48, total: Int = 112) -> AutoCodeEndedLine {
    let status: String
    switch outcome {
    case .stopped: status = "cancelled"
    case .failed: status = "failed"
    case .partial: status = "completed"
    }
    return AutoCodeEndedLine(outcome: outcome, failureKind: kind, frameworkID: framework,
                             title: "Bristlenose UXR Codebook", processed: processed, total: total,
                             key: "\(framework)|\(started)|\(status)")
}

@Suite struct AutoCodeEndedParseTests {

    private func job(_ status: String, kind: String = "", completedAt: Any = NSNull(),
                     framework: String = "uxr") -> [String: Any] {
        ["framework_id": framework, "title": "Bristlenose UXR Codebook", "status": status,
         "completed_at": completedAt, "processed_quotes": 48, "total_quotes": 112,
         "failure_kind": kind, "started_at": "2026-11-23T10:00:00"]
    }

    @Test func eachEndingParsesToItsOutcome() {
        let lines = AutoCodeEndedLine.parseAll(["jobs": [
            job("cancelled", framework: "a"),
            job("failed", kind: "out_of_credit", framework: "b"),
            job("completed", kind: "rate_limited", completedAt: "2026-11-23T10:05:00", framework: "c"),
        ]])
        #expect(lines.map(\.outcome) == [.stopped, .failed, .partial])
        #expect(lines[1] == ended(.failed, "out_of_credit", framework: "b"))
        #expect(lines[0].key == "a|2026-11-23T10:00:00|cancelled")
    }

    /// A running job is the count's, a clean finish says nothing, and an applied codebook's
    /// stopped or failed catch-up is not a first apply's line.
    @Test func runningCleanAndCatchUpEndingsAreNotLines() {
        let applied = "2026-11-20T10:00:00"
        #expect(AutoCodeEndedLine.parseAll(["jobs": [
            job("running"), job("pending"), job("completed", completedAt: applied),
            job("failed", kind: "invalid_key", completedAt: applied),
            job("cancelled", completedAt: applied),
        ]]).isEmpty)
        #expect(AutoCodeEndedLine.parseAll([:]).isEmpty)
    }

    /// A restart is a new run: its key differs, so a line seen before is never taken for it.
    @Test func theKeyNamesTheRun() {
        var later = job("failed", kind: "network")
        later["started_at"] = "2026-11-24T09:00:00"
        let keys = AutoCodeEndedLine.parseAll(["jobs": [job("failed", kind: "network"), later]])
            .map(\.key)
        #expect(Set(keys).count == 2)
    }
}

@MainActor
@Suite struct AutoCodeEndedWordsTests {

    /// The shipped locales, never a fixture: a wrong key must fail here, not render raw and pass.
    private func english() throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        return i18n
    }

    private func row(_ line: AutoCodeEndedLine) throws -> String? {
        SidebarSubtitleText.text(for: .autocodeEnded(line), availability: .ready, progress: nil,
                                 i18n: try english())
    }

    /// D23, word for word, every one the pipeline run's own.
    @Test func theRowSaysD23sWords() throws {
        #expect(try row(ended(.stopped)) == "Stopped")
        #expect(try row(ended(.failed, "out_of_credit")) == "Out of credit")
        #expect(try row(ended(.failed, "invalid_key")) == "Provider key issue")
        #expect(try row(ended(.partial, "rate_limited")) == "Partial run")
    }

    /// The failures D23 does not name take their pipeline category's label (D13); one with no
    /// category reads "Run failed", as an unnamed run failure does.
    @Test func otherFailuresTakeTheirCategorysLabel() throws {
        #expect(try row(ended(.failed, "rate_limited")) == "Rate limited")
        #expect(try row(ended(.failed, "network")) == "Network error")
        #expect(try row(ended(.failed, "server_error")) == "Provider unavailable")
        #expect(try row(ended(.failed, "unknown")) == "Run failed")
        #expect(try row(ended(.failed, "")) == "Run failed")
    }

    /// D23's glyphs: none for a Stop, error for credit and key, warning for a partial run; a
    /// failure that waiting fixes is a warning, as the web chip says.
    @Test func theGlyphFollowsD23() {
        #expect(SubtitleVariant.autocodeEnded(ended(.stopped)).glyphKind == nil)
        #expect(SubtitleVariant.autocodeEnded(ended(.failed, "out_of_credit")).glyphKind == .error)
        #expect(SubtitleVariant.autocodeEnded(ended(.failed, "invalid_key")).glyphKind == .error)
        #expect(SubtitleVariant.autocodeEnded(ended(.partial, "rate_limited")).glyphKind == .warning)
        #expect(SubtitleVariant.autocodeEnded(ended(.failed, "rate_limited")).glyphKind == .warning)
        #expect(SubtitleVariant.autocodeEnded(ended(.failed, "")).glyphKind == .error)
    }

    /// The glyph opens the AutoCode popover, never the pipeline's Diagnostics (D38); a Stop has
    /// no glyph and so no door.
    @Test func theGlyphOpensTheAutoCodePopover() {
        #expect(SubtitleVariant.autocodeEnded(ended(.failed, "out_of_credit")).glyphAction
            == .autocodeFailure)
        #expect(SubtitleVariant.autocodeEnded(ended(.partial, "network")).glyphAction
            == .autocodeFailure)
        #expect(SubtitleVariant.autocodeEnded(ended(.stopped)).glyphAction == .none)
    }

    /// The popover's sentence is the web chip's long one; a partial run leads with its count.
    @Test func thePopoverSaysTheLongSentence() throws {
        let i18n = try english()
        #expect(SidebarSubtitleText.autocodeEndedSentence(ended(.failed, "out_of_credit"), i18n: i18n)
            == "Your AI provider account is out of credit.")
        #expect(SidebarSubtitleText.autocodeEndedSentence(ended(.failed, "invalid_key"), i18n: i18n)
            == "Your API key was rejected.")
        #expect(SidebarSubtitleText.autocodeEndedSentence(
            ended(.partial, "rate_limited", processed: 87, total: 112), i18n: i18n)
            == "Tagged 87 of 112 quotes. Some batches failed. Rate limited, so tagging stopped. Try again soon.")
        #expect(SidebarSubtitleText.autocodeEndedSentence(ended(.stopped), i18n: i18n) == nil)
    }

    @Test func copyIsAnEnglishForensicPayload() {
        let text = ProjectDiagnosticPopover.formatAutoCodePlaintext(
            ended(.failed, "out_of_credit"), projectName: "Talismanic")
        #expect(text == """
            Bristlenose — Talismanic
            AutoCode — Bristlenose UXR Codebook
            outcome: failed
            failure_kind: out_of_credit
            quotes: 48 of 112
            """)
    }
}

/// Where the line ranks. **Lead to confirm** (landing plan Phase 5): an active pipeline run
/// outranks AutoCode; an AutoCode failure outranks an idle row.
@MainActor
@Suite struct AutoCodeEndedRankingTests {

    private func resolve(
        pipelineState: PipelineState? = nil,
        addingCount: Int? = nil,
        preparingSignals: Bool = false,
        runUsage: RunUsageLine? = nil,
        screens: (done: Int, total: Int)? = nil,
        autocode: (done: Int, total: Int)? = nil,
        autocodeEnded: AutoCodeEndedLine?,
        reportCrash: ReportCrash? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0,
        databaseForked: Bool = false
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: pipelineState, isStopping: false,
            addingCount: addingCount, preparingSignals: preparingSignals, runUsage: runUsage,
            copy: nil, importBatch: nil, screens: screens, autocode: autocode,
            autocodeEnded: autocodeEnded, reportCrash: reportCrash, lastRunAt: nil,
            missingCount: missingCount, unanalysedCount: unanalysedCount,
            databaseForked: databaseForked)
    }

    private let credit = ended(.failed, "out_of_credit")
    private let partial = ended(.partial, "rate_limited")
    private let stop = ended(.stopped)

    @Test func itShowsOnAnIdleRow() {
        #expect(resolve(autocodeEnded: credit) == .autocodeEnded(credit))
        #expect(resolve(pipelineState: .ready(Date()), autocodeEnded: stop) == .autocodeEnded(stop))
        #expect(resolve(autocodeEnded: nil) == .placeholder)
    }

    /// Every pipeline state that has its own line keeps it; AutoCode's comes back when it clears.
    @Test func anActivePipelineRunOutranksIt() {
        #expect(resolve(pipelineState: .running, autocodeEnded: credit) == .running)
        #expect(resolve(pipelineState: .queued(position: 1), autocodeEnded: credit)
            == .queued(position: 1))
        #expect(resolve(pipelineState: .stopped(stagesComplete: []), autocodeEnded: credit) == .stopped())
    }

    /// A failure outranks the news-free and the warning and info lines: usage, the count of
    /// another codebook, Signals, screens, missing and unanalysed files.
    @Test func aFailureOrPartialRunOutranksTheQuietLines() {
        for line in [credit, partial] {
            #expect(resolve(runUsage: .tokens(1000), autocodeEnded: line) == .autocodeEnded(line))
            #expect(resolve(autocode: (1, 4), autocodeEnded: line) == .autocodeEnded(line))
            #expect(resolve(preparingSignals: true, autocodeEnded: line) == .autocodeEnded(line))
            #expect(resolve(screens: (1, 4), autocodeEnded: line) == .autocodeEnded(line))
            #expect(resolve(autocodeEnded: line, missingCount: 2) == .autocodeEnded(line))
            #expect(resolve(autocodeEnded: line, unanalysedCount: 2) == .autocodeEnded(line))
        }
    }

    /// It yields to the acts the researcher started, a forked database and the report crash.
    @Test func aFailureYieldsToTheirActsAndGraverNews() {
        let crash = ReportCrash(route: "/report/", message: "x", frames: [])
        #expect(resolve(addingCount: 2, autocodeEnded: credit) == .addingInterviews(count: 2))
        #expect(resolve(autocodeEnded: credit, databaseForked: true) == .deltaOnly(.databaseForked))
        #expect(resolve(autocodeEnded: credit, reportCrash: crash) == .reportError(crash))
    }

    /// "Stopped" is not news: it yields to a running count, Signals and any delta with a glyph,
    /// and takes the line from the screen read and the quiet unanalysed delta.
    @Test func aStopRanksAsAQuietActivity() {
        #expect(resolve(autocode: (1, 4), autocodeEnded: stop) == .codingQuotes(done: 1, total: 4))
        #expect(resolve(preparingSignals: true, autocodeEnded: stop) == .preparingSignals)
        #expect(resolve(autocodeEnded: stop, missingCount: 2) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(screens: (1, 4), autocodeEnded: stop) == .autocodeEnded(stop))
        #expect(resolve(autocodeEnded: stop, unanalysedCount: 2) == .autocodeEnded(stop))
    }
}

/// The line's memory: what survives the server, and what clears it.
@Suite struct AutoCodeLineMemoryTests {

    @Test func aGoodAnswerShowsTheGravestLine() {
        var m = AutoCodeLineMemory()
        m.observe([ended(.stopped, framework: "a"), ended(.partial, "network", framework: "b"),
                   ended(.failed, "invalid_key", framework: "c")])
        #expect(m.line?.frameworkID == "c")
        m.observe([ended(.stopped, framework: "a"), ended(.partial, "network", framework: "b")])
        #expect(m.line?.frameworkID == "b")
    }

    /// Opening the study clears a "Stopped" line, and the server listing the same run again does
    /// not bring it back.
    @Test func openingTheStudyClearsAStopForGood() {
        var m = AutoCodeLineMemory()
        let line = ended(.stopped)
        m.observe([line])
        m.acknowledge()
        #expect(m.line == nil)
        m.observe([line])
        #expect(m.line == nil, "a seen line came back")
    }

    /// A failure and a partial run clear when resolved, not when seen (Phase 5a review: failed
    /// runs stay visible and retryable). Opening the study clears a Stop beside them.
    @Test func aFailureOrPartialRunSurvivesBeingSeen() {
        var m = AutoCodeLineMemory()
        let credit = ended(.failed, "out_of_credit", framework: "a")
        let partial = ended(.partial, "network", framework: "b")
        let stop = ended(.stopped, framework: "c")
        m.observe([credit, partial, stop])
        m.acknowledge()
        #expect(m.line == credit)
        m.observe([partial, stop])            // the credit run was started again
        #expect(m.line == partial)
        m.observe([stop])                     // and the partial one resolved by a catch-up
        #expect(m.line == nil, "the seen Stop came back")
    }

    /// Starting the codebook again: the server no longer lists the run, so the line goes, and a
    /// new run that ends is a new line even though the old one was seen.
    @Test func startingTheCodebookAgainClearsItAndANewEndingShows() {
        var m = AutoCodeLineMemory()
        let first = ended(.stopped)
        m.observe([first])
        m.acknowledge()
        m.observe([])
        #expect(m.line == nil)
        #expect(m.isEmpty, "a seen key outlived its run")
        let second = ended(.stopped, started: "2026-11-24T09:00:00")
        m.observe([second])
        #expect(m.line == second)
    }

    /// A 404 drops what was listed but never what was seen, so a seen Stop cannot come back on
    /// the next good answer (Phase 5a review).
    @Test func anUnavailableListingKeepsWhatWasSeen() {
        var m = AutoCodeLineMemory()
        let stop = ended(.stopped)
        m.observe([stop, ended(.failed, "invalid_key", framework: "b")])
        m.acknowledge()
        m.listingUnavailable()
        #expect(m.line == nil)
        m.observe([stop])
        #expect(m.line == nil, "a 404 forgot what the researcher had seen")
    }

    /// Nothing but an answer, an open or a removal moves it: a reap is no answer.
    @Test func itIsAValueThatRoundTrips() throws {
        var m = AutoCodeLineMemory()
        m.observe([ended(.failed, "invalid_key"), ended(.stopped, framework: "b")])
        m.acknowledge()
        m.observe([ended(.failed, "invalid_key"), ended(.stopped, framework: "b"),
                   ended(.partial, "network", framework: "c")])
        let data = try JSONEncoder().encode(m)
        #expect(try JSONDecoder().decode(AutoCodeLineMemory.self, from: data) == m)
    }
}

@MainActor
@Suite struct AutoCodeEndedStoreTests {

    private func suite() -> UserDefaults {
        let name = "AutoCodeEndedStoreTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    /// The line outlives the app: a store made on the same defaults reads it back.
    @Test func theLinePersistsAcrossAQuit() {
        let d = suite()
        let id = UUID()
        let line = ended(.failed, "out_of_credit")
        ScreenReadingStore(defaults: d).noteAutoCodeEnded([line], for: id)
        #expect(ScreenReadingStore(defaults: d).autocodeEnded[id] == line)
    }

    @Test func openingAndRemovingClearItAndItsStorage() {
        let d = suite()
        let (a, b) = (UUID(), UUID())
        let store = ScreenReadingStore(defaults: d)
        store.noteAutoCodeEnded([ended(.stopped)], for: a)
        store.noteAutoCodeEnded([ended(.failed, "out_of_credit")], for: b)
        store.acknowledgeAutoCode(for: a)
        #expect(store.autocodeEnded[a] == nil)
        store.forgetAutoCode(for: b)
        #expect(store.autocodeEnded[b] == nil)
        let reread = ScreenReadingStore(defaults: d)
        #expect(reread.autocodeEnded.isEmpty)
        // a's seen key is kept while its run is listed, so it does not come back on the next answer
        reread.noteAutoCodeEnded([ended(.stopped)], for: a)
        #expect(reread.autocodeEnded[a] == nil)
    }

    @Test func anUnchangedAnswerPublishesNothing() {
        let store = ScreenReadingStore()
        let id = UUID()
        var publishes = 0
        let sub = store.objectWillChange.sink { publishes += 1 }
        store.noteAutoCodeEnded([ended(.stopped)], for: id)
        store.noteAutoCodeEnded([ended(.stopped)], for: id)
        #expect(publishes == 1)
        sub.cancel()
    }
}

/// The plumbing: a reap keeps the line, a removal does not, opening a study clears it, and a
/// manager with no running serve says nothing about ended runs.
@MainActor
@Suite struct AutoCodeEndedPlumbingTests {

    private func fleet(_ store: ScreenReadingStore) -> ServeFleet {
        ServeFleet(screenReading: store, makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 9_999)))
        })
    }

    @Test func aReapKeepsTheLineAndARemovalTakesIt() {
        let store = ScreenReadingStore()
        let f = fleet(store)
        let (a, b) = (UUID(), UUID())
        let line = ended(.failed, "out_of_credit")
        f.manager(for: a).onAutoCodeEnded?(.listed([line]))
        f.manager(for: b).onAutoCodeEnded?(.listed([line]))
        f.discard(a, forgettingAgentActivity: false)   // the reap's call
        f.discard(b)                                     // leaving the sidebar
        #expect(store.autocodeEnded[a] == line, "a failure seen before the reap was lost")
        #expect(store.autocodeEnded[b] == nil)
    }

    @Test func noRunningServeSaysNothingAboutEndedRuns() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 9)))  // idle: never started
        var ended: [AutoCodeEndedAnswer] = []
        m.onAutoCodeEnded = { ended.append($0) }
        await m.pollAutoCode()
        #expect(ended.isEmpty)
    }

    /// Opening is a study newly shown in a window, and it clears a "Stopped" line. One already
    /// on screen when its run stops keeps the line until it is next opened. A failure is not
    /// cleared by opening at all.
    @Test func openingTheStudyClearsAStop() {
        let store = ScreenReadingStore()
        let f = fleet(store)
        let (a, b, c) = (UUID(), UUID(), UUID())
        f.sweep(shownProjects: [b])
        store.noteAutoCodeEnded([ended(.stopped)], for: a)
        store.noteAutoCodeEnded([ended(.stopped)], for: b)
        store.noteAutoCodeEnded([ended(.failed, "out_of_credit")], for: c)
        f.sweep(shownProjects: [b])
        #expect(store.autocodeEnded[b] != nil, "a study already on screen lost its new line")
        f.sweep(shownProjects: [a, b, c])
        #expect(store.autocodeEnded[a] == nil, "opening the study did not clear its Stop")
        #expect(store.autocodeEnded[b] != nil)
        #expect(store.autocodeEnded[c] != nil, "opening the study cleared an unresolved failure")
    }

    @Test func theFleetWiresTheRingsStop() {
        let store = ScreenReadingStore()
        _ = fleet(store)
        #expect(store.onStopAutoCode != nil)
    }

    @Test func theStopIsTheCancelRouteWithTheBearer() throws {
        let request = try #require(ServeManager.autoCodeCancelRequest(
            state: .running(port: 5123), token: "tok", frameworkID: "uxr"))
        #expect(request.httpMethod == "POST")
        #expect(request.url?.absoluteString == "http://127.0.0.1:5123/api/projects/1/autocode/uxr/cancel")
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer tok")
        #expect(ServeManager.autoCodeCancelRequest(state: .running(port: 1), token: nil,
                                                    frameworkID: "uxr") == nil)
        #expect(ServeManager.autoCodeCancelRequest(state: .idle, token: "tok",
                                                    frameworkID: "uxr") == nil)
        #expect(ServeManager.autoCodeCancelRequest(state: .running(port: 1), token: "tok",
                                                    frameworkID: "a/b")?.url?.absoluteString
            == "http://127.0.0.1:1/api/projects/1/autocode/a%2Fb/cancel")
    }
}

/// D16, refined (review 11): a busy study's server is held while its progress moves; a run whose
/// counter stands still meets the ceiling.
@MainActor
@Suite struct BusyHoldFollowsProgressTests {

    @Test func stalledTimeRunsFromTheLaterOfTheHoldAndTheLastProgress() {
        let t0 = ContinuousClock.now
        let held = t0
        #expect(ServeReaping.stalledFor(heldSince: held, progressMovedAt: nil, now: t0 + .seconds(90))
            == .seconds(90))
        #expect(ServeReaping.stalledFor(heldSince: held, progressMovedAt: t0 + .seconds(80),
                                        now: t0 + .seconds(90)) == .seconds(10))
        // progress before the hold buys nothing
        #expect(ServeReaping.stalledFor(heldSince: held, progressMovedAt: t0 - .seconds(600),
                                        now: t0 + .seconds(90)) == .seconds(90))
    }

    @Test func theFirstReadingIsABaselineAndAChangeIsMovement() {
        let instance = ServeInstance()
        let t0 = ContinuousClock.now
        instance.noteBackgroundProgress(25, at: t0)
        #expect(instance.backgroundProgressMovedAt == nil)
        instance.noteBackgroundProgress(25, at: t0 + .seconds(20))
        #expect(instance.backgroundProgressMovedAt == nil)
        instance.noteBackgroundProgress(50, at: t0 + .seconds(40))
        #expect(instance.backgroundProgressMovedAt == t0 + .seconds(40))
        instance.resetBackgroundProgress()
        #expect(instance.backgroundProgress == nil && instance.backgroundProgressMovedAt == nil)
    }

    @Test func theProgressIsReadFromTheServersReply() {
        #expect(AgentActivity.parseBackgroundProgress(["busy": true, "progress": 75]) == 75)
        #expect(AgentActivity.parseBackgroundProgress(["busy": true]) == nil)
        #expect(AgentActivity.parseBackgroundProgress(["progress": true]) == nil)
        #expect(AgentActivity.parseBackgroundProgress(["progress": "75"]) == nil)
    }

    @Test func aPollFoldsTheProgressIn() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        m.instance.state = .running(port: 5000)
        m.instance.authToken = "tok"
        m.backgroundWorkReader = { _ in ["busy": true, "kinds": ["autocode"], "progress": 5] }
        await m.pollBackgroundWork()
        m.backgroundWorkReader = { _ in ["busy": true, "kinds": ["autocode"], "progress": 30] }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundProgress == 30)
        #expect(m.instance.backgroundProgressMovedAt != nil)
    }

    /// A run that keeps answering batches is held past the ceiling; one that stops moving is
    /// reaped once the ceiling passes from its last progress.
    @Test func aMovingRunIsHeldPastTheCeilingAndAStuckOneIsNot() async throws {
        let fleet = ServeFleet(screenReading: ScreenReadingStore())
        let id = UUID()
        let manager = fleet.manager(for: id)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)
        manager.instance.noteBackgroundProgress(0)
        let ceiling = Duration.milliseconds(150)

        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: ceiling)      // held
        try await Task.sleep(for: .milliseconds(250))                           // the ceiling is spent
        manager.instance.noteBackgroundProgress(25)                             // …but a batch answered
        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: ceiling)
        #expect(fleet.managers[id] != nil, "a run making progress was reaped")

        try await Task.sleep(for: .milliseconds(250))                           // no batch since
        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: ceiling)
        #expect(fleet.managers[id] == nil, "a stuck run kept its server past the ceiling")
    }

    @Test func aNewServeStartsWithNoProgress() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 1)))
        manager.instance.noteBackgroundProgress(5)
        manager.instance.noteBackgroundProgress(9)
        manager.start(projectPath: "/studies/a")
        #expect(manager.instance.backgroundProgress == nil)
        #expect(manager.instance.backgroundProgressMovedAt == nil)
    }
}
