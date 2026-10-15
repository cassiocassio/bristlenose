import Combine
import Foundation
import Testing
@testable import Bristlenose

/// The Screens lens's reading progress as one more activity on the sidebar
/// status line: where it sits in the precedence chain, when it shows at all,
/// and what it says.
@Suite struct ScreenReadingSubtitleTests {

    private func resolve(
        pipelineState: PipelineState? = nil,
        addingCount: Int? = nil,
        copy: CopyDisplay? = nil,
        importBatch: (done: Int, total: Int)? = nil,
        screens: (done: Int, total: Int)? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0,
        databaseForked: Bool = false
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: pipelineState, isStopping: false,
            addingCount: addingCount, copy: copy, importBatch: importBatch,
            screens: screens, lastRunAt: nil,
            missingCount: missingCount, unanalysedCount: unanalysedCount,
            databaseForked: databaseForked)
    }

    private let reading = (done: 3, total: 10)

    @Test func screensShowOnAnOtherwiseQuietRow() {
        #expect(resolve(screens: reading) == .readingScreens(done: 3, total: 10))
    }

    /// The owner's order: adding › batch › copying › (distress deltas) › screens › quiet delta.
    @Test func everyGestureTheResearcherStartedOutranksScreens() {
        #expect(resolve(addingCount: 2, screens: reading) == .addingInterviews(count: 2))
        #expect(resolve(importBatch: (done: 1, total: 4), screens: reading)
            == .importingBatch(done: 1, total: 4))
        #expect(resolve(copy: .copying(fraction: 0.5), screens: reading)
            == .copying(fraction: 0.5))
        #expect(resolve(copy: .cancelling, screens: reading) == .copyCancelling)
    }

    /// A quiet delta (more material than the report has read) yields to the
    /// read; a distress delta does not — a read can run for hours, and the row
    /// must not hide a forked database or missing files for that long.
    @Test func screensOutrankOnlyTheQuietDelta() {
        #expect(resolve(screens: reading, unanalysedCount: 5) == .readingScreens(done: 3, total: 10))
        #expect(resolve(screens: reading, missingCount: 2) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(screens: reading, databaseForked: true) == .deltaOnly(.databaseForked))
        #expect(resolve(screens: reading, missingCount: 2, unanalysedCount: 5)
            == .deltaOnly(.missing(count: 2)))
    }

    /// It yields to a run without asking — the run is returned before the idle
    /// tier is reached.
    @Test func aRunOutranksScreens() {
        #expect(resolve(pipelineState: .running, screens: reading) == .running)
        #expect(resolve(pipelineState: .queued(position: 1), screens: reading) == .queued(position: 1))
    }

    /// Progress, not news: no glyph and no door, like the cloud batch.
    @Test func screensCarryNoGlyph() {
        let v = SubtitleVariant.readingScreens(done: 0, total: 4)
        #expect(v.glyphKind == nil)
        #expect(v.glyphAction == .none)
    }
}

/// When the row appears is the server's answer, parsed — pure, so it is tested
/// without one.
@Suite struct ScreenReadingParseTests {

    private func body(enabled: Bool = true, running: Bool = true, done: Int = 2,
                      total: Int = 9, rate: Any = NSNull()) -> [String: Any] {
        ["enabled": enabled, "unavailable": NSNull(), "running": running,
         "done": done, "total": total, "seconds_done": 120.0,
         "seconds_total": 600.0, "rate": rate]
    }

    @Test func aRunningJobParses() {
        let p = ScreenReadingProgress.parse(body())
        #expect(p?.done == 2)
        #expect(p?.total == 9)
        #expect(p?.rate == nil)
    }

    @Test func theRowIsHiddenWhenNotRunningDisabledOrDone() {
        #expect(ScreenReadingProgress.parse(body(running: false)) == nil)
        #expect(ScreenReadingProgress.parse(body(enabled: false)) == nil)
        #expect(ScreenReadingProgress.parse(body(done: 9, total: 9)) == nil)
        #expect(ScreenReadingProgress.parse(body(done: 0, total: 0)) == nil)
    }

    /// The warm-up: running, nothing read yet. It shows "0 of M", not nothing.
    @Test func theWarmUpShowsZeroOfM() {
        #expect(ScreenReadingProgress.parse(body(done: 0, total: 9))?.done == 0)
    }

    /// An ETA exists only once the server has measured a rate — never from a
    /// constant.
    @Test func noRateMeansNoETA() {
        #expect(ScreenReadingProgress.parse(body())?.etaSeconds == nil)
        #expect(ScreenReadingProgress.parse(body(rate: 0.0))?.etaSeconds == nil)
        // 480 s of recording left at 2 s/s → 240 s.
        #expect(ScreenReadingProgress.parse(body(rate: 2.0))?.etaSeconds == 240)
    }
}

/// Whether a project has a Screens lens at all — the rail row, ⌘7 and the View
/// menu row follow it. The server decides (`screens_available`); the Mac reads
/// `available` and never re-derives it.
@Suite struct ScreenReadingAvailabilityTests {

    private func body(available: Any?, hasScreens: Bool = false, running: Bool = false,
                      done: Int = 0, total: Int = 0) -> [String: Any] {
        var json: [String: Any] = [
            "enabled": true, "unavailable": NSNull(), "running": running,
            "done": done, "total": total, "seconds_done": 0.0,
            "seconds_total": 0.0, "rate": NSNull(), "has_screens": hasScreens]
        if let available { json["available"] = available }
        return json
    }

    @Test func theServersYesIsAYes() {
        #expect(ScreenReadingProgress.isAvailable(body(available: true)))
    }

    /// Screens found, or a read still to come, but the server said no: no lens.
    @Test func theCountsNeverOverruleTheServer() {
        #expect(!ScreenReadingProgress.isAvailable(body(available: false, hasScreens: true)))
        #expect(!ScreenReadingProgress.isAvailable(body(available: false, running: true, total: 3)))
    }

    /// An older serve without the field, or a null, is not a yes.
    @Test func absentIsNotAYes() {
        #expect(!ScreenReadingProgress.isAvailable(body(available: nil, hasScreens: true)))
        #expect(!ScreenReadingProgress.isAvailable(body(available: NSNull(), hasScreens: true)))
    }
}

/// What the row and its tooltip say. Configured on a throwaway locale folder
/// with the real English values, and pinned to `en` — a bare `I18n()` returns
/// raw keys, and an unpinned one follows the app's own language.
@MainActor
@Suite struct ScreenReadingTextTests {

    private func english() throws -> I18n {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("screens-i18n-\(UUID().uuidString)")
        let en = dir.appendingPathComponent("en")
        try FileManager.default.createDirectory(at: en, withIntermediateDirectories: true)
        let desktop: [String: Any] = ["chrome": ["pipeline": [
            "screens": "Screens · {{done}} of {{total}}",
            "etaMinutes": "~{{count}} min left",
            "etaUnderMinute": "<1 min left",
        ]]]
        try JSONSerialization.data(withJSONObject: desktop)
            .write(to: en.appendingPathComponent("desktop.json"))
        let i18n = I18n()
        i18n.configure(localesDirectory: dir)
        i18n.setLocale("en")
        return i18n
    }

    private func progress(done: Int, total: Int, rate: Double?) -> ScreenReadingProgress {
        ScreenReadingProgress(done: done, total: total, secondsDone: 0,
                              secondsTotal: 600, rate: rate)
    }

    @Test func theRowReadsScreensNofM() throws {
        let i18n = try english()
        let text = SidebarSubtitleText.text(
            for: .readingScreens(done: 3, total: 10), availability: .ready,
            progress: nil, i18n: i18n)
        #expect(text == "Screens · 3 of 10")
    }

    /// The warm-up reads "0 of M", and says nothing about time — on the row
    /// or in the tooltip.
    @Test func theWarmUpSaysNothingAboutTime() throws {
        let i18n = try english()
        let variant = SubtitleVariant.readingScreens(done: 0, total: 10)
        #expect(SidebarSubtitleText.text(for: variant, availability: .ready,
                                         progress: nil, i18n: i18n) == "Screens · 0 of 10")
        #expect(SidebarSubtitleText.screensTooltip(
            variant, progress: progress(done: 0, total: 10, rate: nil), i18n: i18n)
            == "Screens · 0 of 10")
    }

    /// Once a rate is measured, the time left goes in the tooltip — and only
    /// there: the row keeps its count.
    @Test func aMeasuredRateAddsTimeToTheTooltipOnly() throws {
        let i18n = try english()
        let variant = SubtitleVariant.readingScreens(done: 3, total: 10)
        // 600 s left at 2 s/s → 300 s → "~5 min left".
        let tip = SidebarSubtitleText.tooltip(
            for: variant, data: nil, progress: nil,
            screens: progress(done: 3, total: 10, rate: 2), i18n: i18n)
        #expect(tip == "Screens · 3 of 10 · ~5 min left")
        #expect(SidebarSubtitleText.text(for: variant, availability: .ready,
                                         progress: nil, i18n: i18n) == "Screens · 3 of 10")
    }
}

/// The store publishes only on change — the property that keeps a poll tick
/// from republishing anything a window can see.
@MainActor
@Suite struct ScreenReadingStoreTests {

    @Test func anUnchangedTickPublishesNothing() {
        let store = ScreenReadingStore()
        let id = UUID()
        let value = ScreenReadingProgress(done: 1, total: 4, secondsDone: 10,
                                          secondsTotal: 40, rate: nil)
        var publishes = 0
        let sub = store.objectWillChange.sink { publishes += 1 }
        defer { sub.cancel() }

        store.set(value, for: id)
        store.set(value, for: id)
        store.set(nil, for: id)
        store.set(nil, for: id)

        #expect(publishes == 2)
        #expect(store.progress[id] == nil)
    }

    /// Availability publishes only on change too — it is polled every tick and
    /// changes almost never.
    @Test func availabilityPublishesOnlyOnChange() {
        let store = ScreenReadingStore()
        let a = UUID(), b = UUID()
        var publishes = 0
        let sub = store.objectWillChange.sink { publishes += 1 }
        defer { sub.cancel() }

        store.setAvailable(true, for: a)
        store.setAvailable(true, for: a)
        store.setAvailable(false, for: b)
        store.setAvailable(false, for: a)
        store.setAvailable(false, for: a)

        #expect(publishes == 2)
        #expect(store.available.isEmpty)
    }
}

/// The poll's clearing guards — the part that decides the row goes away. Both
/// return before any request, so no server is needed; the request half is the
/// server's contract and is pinned by `parse` above.
@MainActor
@Suite struct ScreenReadingPollTests {

    private func manager() -> ServeManager {
        ServeManager(resolvedMode: .success(.external(port: 9)))
    }

    @Test func preferenceOffClearsTheRowAndTheLensWithoutAsking() async throws {
        let suite = "ScreenReadingPollTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(false, forKey: ScreenTextPreference.key)
        // Diagnostics on must not keep it alive: the lens left that switch.
        defaults.set(true, forKey: DiagnosticsPreference.key)

        let m = manager()
        m.instance.state = .running(port: 9)
        m.authToken = "token"
        var calls: [ScreenReadingProgress?] = []
        var availability: [Bool] = []
        m.onScreensProgress = { calls.append($0) }
        m.onScreensAvailability = { availability.append($0) }

        await m.pollScreens(defaults: defaults)

        #expect(calls.count == 1)
        #expect(calls.first.map { $0 == nil } == true, "a leftover row survived Read shared screens off")
        #expect(availability == [false], "the Screens lens survived Read shared screens off")
    }

    /// A serve between spawns — any preference restart — clears the row but
    /// says nothing about the lens, so a window on Screens is not moved off it.
    @Test func noRunningServeClearsTheRowButKeepsTheLens() async throws {
        let suite = "ScreenReadingPollTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }

        let m = manager()   // idle: never started; preference at its default (on)
        var calls: [ScreenReadingProgress?] = []
        var availability: [Bool] = []
        m.onScreensProgress = { calls.append($0) }
        m.onScreensAvailability = { availability.append($0) }

        await m.pollScreens(defaults: defaults)

        #expect(calls.count == 1)
        #expect(calls.first.map { $0 == nil } == true)
        #expect(availability.isEmpty, "a restart moved the lens off the rail")
    }
}
