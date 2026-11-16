import Combine
import Foundation
import Testing
@testable import Bristlenose

/// A first AutoCode apply as one more activity on the sidebar status line ("AutoCode · 25 of 101"),
/// the screens line's sibling: when it parses, where it ranks, what it says, and that the store
/// publishes only on change.

@Suite struct AutoCodeProgressParseTests {

    private func job(status: String = "running", completedAt: Any = NSNull(),
                     processed: Int = 25, total: Int = 101) -> [String: Any] {
        ["framework_id": "uxr", "title": "Bristlenose UXR Codebook", "status": status,
         "completed_at": completedAt, "processed_quotes": processed, "total_quotes": total]
    }

    private func body(_ jobs: [[String: Any]]) -> [String: Any] { ["jobs": jobs] }

    @Test func aRunningFirstApplyParses() {
        let p = AutoCodeProgress.parse(body([job()]))
        #expect(p?.done == 25)
        #expect(p?.total == 101)
    }

    /// The warm-up: started, no batch answered. It shows "0 of M", not nothing.
    @Test func theWarmUpShowsZeroOfM() {
        #expect(AutoCodeProgress.parse(body([job(status: "pending", processed: 0)]))?.done == 0)
    }

    /// A catch-up writes its counts once, at the end, so a line for it would sit at "101 of 101"
    /// for the whole pass. Only a job with no `completed_at` is a first apply.
    @Test func aCatchUpPassHasNoRowLine() {
        #expect(AutoCodeProgress.parse(body([job(completedAt: "2026-10-20T10:00:00")])) == nil)
    }

    @Test func nothingLeftToDoOrNothingToDoShowsNothing() {
        #expect(AutoCodeProgress.parse(body([job(processed: 101)])) == nil)
        #expect(AutoCodeProgress.parse(body([job(processed: 0, total: 0)])) == nil)
        #expect(AutoCodeProgress.parse(body([])) == nil)
        #expect(AutoCodeProgress.parse([:]) == nil)
    }

    /// The route lists only pending and running, but the rule does not rely on it.
    @Test func aFinishedJobShowsNothing() {
        for status in ["completed", "failed", "cancelled"] {
            #expect(AutoCodeProgress.parse(body([job(status: status)])) == nil, "\(status)")
        }
    }

    /// Several codebooks at once: the first first-apply that has something left, never a sum.
    @Test func theFirstQualifyingJobWins() {
        let jobs = [job(completedAt: "2026-10-20T10:00:00"), job(processed: 10, total: 50),
                    job(processed: 1, total: 9)]
        let p = AutoCodeProgress.parse(body(jobs))
        #expect(p?.done == 10)
        #expect(p?.total == 50)
    }
}

@MainActor
@Suite struct AutoCodeSubtitleTests {

    private func resolve(
        pipelineState: PipelineState? = nil,
        addingCount: Int? = nil,
        preparingSignals: Bool = false,
        screens: (done: Int, total: Int)? = nil,
        autocode: (done: Int, total: Int)? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0,
        databaseForked: Bool = false
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: pipelineState, isStopping: false,
            addingCount: addingCount, preparingSignals: preparingSignals, copy: nil,
            importBatch: nil, screens: screens, autocode: autocode, lastRunAt: nil,
            missingCount: missingCount, unanalysedCount: unanalysedCount,
            databaseForked: databaseForked)
    }

    private let coding = (done: 25, total: 101)
    private let reading = (done: 3, total: 10)

    @Test func itShowsOnAnOtherwiseQuietRow() {
        #expect(resolve(autocode: coding) == .codingQuotes(done: 25, total: 101))
    }

    /// Work on the quotes the run just made outranks the screen read it follows.
    @Test func itOutranksScreenReading() {
        #expect(resolve(screens: reading, autocode: coding) == .codingQuotes(done: 25, total: 101))
        #expect(resolve(screens: reading) == .readingScreens(done: 3, total: 10))
    }

    /// The apply holds the Signals build open for its whole length, so with no report yet the
    /// window reads "lens withheld" for minutes: the count must not hide behind "Picking up
    /// Signals…". When the count reaches its total the line goes and Signals takes over.
    @Test func itOutranksTheSignalsLineAndHandsOverWhenDone() {
        #expect(resolve(preparingSignals: true, autocode: coding)
            == .codingQuotes(done: 25, total: 101))
        #expect(resolve(preparingSignals: true) == .preparingSignals)
    }

    /// A run and the researcher's own acts keep the line over it.
    @Test func aRunAndTheirOwnActsOutrankIt() {
        #expect(resolve(pipelineState: .running, autocode: coding) == .running)
        #expect(resolve(addingCount: 2, autocode: coding) == .addingInterviews(count: 2))
    }

    /// A read can run for hours and a codebook for minutes, but the row must not hide a forked
    /// database or missing files behind either; the quiet delta yields.
    @Test func itYieldsToDistressDeltasAndOutranksTheQuietOne() {
        #expect(resolve(autocode: coding, unanalysedCount: 5) == .codingQuotes(done: 25, total: 101))
        #expect(resolve(autocode: coding, missingCount: 2) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(autocode: coding, databaseForked: true) == .deltaOnly(.databaseForked))
    }

    /// Progress, not news: no glyph and no door; and work, so it shimmers.
    @Test func itCarriesNoGlyphAndShimmers() {
        let v = SubtitleVariant.codingQuotes(done: 0, total: 4)
        #expect(v.glyphKind == nil)
        #expect(v.glyphAction == .none)
        #expect(SidebarOutlineController.shimmers(v, animationOn: true, reduceMotion: false))
        #expect(!SidebarOutlineController.shimmers(v, animationOn: false, reduceMotion: false))
        #expect(!SidebarOutlineController.shimmers(v, animationOn: true, reduceMotion: true))
    }
}

@MainActor
@Suite struct AutoCodeTextTests {

    /// The shipped locales, never a fixture: a wrong or missing key in `en/desktop.json` must
    /// fail here, not render a raw key and pass.
    private func english() throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        return i18n
    }

    @Test func theRowReadsAutoCodeNofM() throws {
        let text = SidebarSubtitleText.text(
            for: .codingQuotes(done: 25, total: 101), availability: .ready,
            progress: nil, i18n: try english())
        #expect(text == "AutoCode · 25 of 101")
    }

    /// A count in the thousands truncates on the row in a long locale, so hover says it whole.
    @Test func theTooltipSaysTheWholeLine() throws {
        let tip = SidebarSubtitleText.tooltip(
            for: .codingQuotes(done: 1012, total: 2500), data: nil, progress: nil,
            i18n: try english())
        #expect(tip == "AutoCode · 1012 of 2500")
    }
}

@MainActor
@Suite struct AutoCodeStoreTests {

    @Test func anUnchangedTickPublishesNothing() {
        let store = ScreenReadingStore()
        let id = UUID()
        var publishes = 0
        let sub = store.objectWillChange.sink { publishes += 1 }
        store.setAutoCode(AutoCodeProgress(done: 1, total: 4), for: id)
        store.setAutoCode(AutoCodeProgress(done: 1, total: 4), for: id)
        #expect(publishes == 1)
        store.setAutoCode(nil, for: id)
        store.setAutoCode(nil, for: id)
        #expect(publishes == 2)
        #expect(store.autocode[id] == nil)
        sub.cancel()
    }
}

/// The plumbing the pure tests above do not reach: a manager's poll clears the row when there is
/// no serve, a fleet routes a manager's progress to its own project, and a discarded project keeps
/// no row. Deleting any of the three would leave every other test here green.
@MainActor
@Suite struct AutoCodePlumbingTests {

    private static let a = UUID()
    private static let b = UUID()

    private func fleet(_ store: ScreenReadingStore) -> ServeFleet {
        ServeFleet(screenReading: store, makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 9_999)))
        })
    }

    @Test func noRunningServeClearsTheRow() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 9)))  // idle: never started
        var calls: [AutoCodeProgress?] = []
        m.onAutoCodeProgress = { calls.append($0) }

        await m.pollAutoCode()

        #expect(calls.count == 1)
        #expect(calls.first.map { $0 == nil } == true, "a leftover row survived the serve stopping")
    }

    @Test func aManagersProgressLandsUnderItsOwnProjectAndGoesWithIt() {
        let store = ScreenReadingStore()
        let fleet = fleet(store)
        let p = AutoCodeProgress(done: 25, total: 101)
        _ = fleet.manager(for: Self.b)
        fleet.manager(for: Self.a).onAutoCodeProgress?(p)
        #expect(store.autocode[Self.a] == p)
        #expect(store.autocode[Self.b] == nil)

        fleet.discard(Self.a)
        #expect(store.autocode[Self.a] == nil, "a discarded project kept its row")
    }
}
