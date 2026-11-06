import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// The run-finished banner (docs/design-run-banner.md). Its purpose, from the
/// owner: "do I need to look at this?" Each test pins a way the banner could say
/// something untrue, or say something at the wrong moment.

// MARK: - Fixtures

private func cause(_ category: CauseCategory, session: String? = "s1") -> SessionFailure {
    SessionFailure(sessionId: session, sourceFile: session == nil ? "participant-name.mp4" : nil,
                   cause: Cause(category: category))
}

private func stage(_ attempted: Int, _ succeeded: Int, failed: [SessionFailure] = []) -> StageOutcome {
    StageOutcome(attempted: attempted, succeeded: succeeded, durationMs: nil, failed: failed)
}

private func summary(
    sessions: Int = 8, analysed: Int = 8,
    transcriptFailures: [SessionFailure] = [], quoteFailures: [SessionFailure] = [],
    ingestFailures: [SessionFailure] = [], leftOut: [String: Int]? = nil
) -> PipelineSummary {
    PipelineSummary(
        ingest: ingestFailures.isEmpty ? nil : stage(sessions, sessions, failed: ingestFailures),
        transcripts: stage(sessions, sessions - transcriptFailures.count, failed: transcriptFailures),
        quotes: stage(sessions, analysed, failed: quoteFailures),
        quotesLeftOut: leftOut)
}

private func terminus(
    started: String? = "2026-11-06T09:00:00.000000Z", ended: String? = "2026-11-06T09:38:00.500000Z",
    runId: String = "run-1", summary: PipelineSummary? = nil
) throws -> EventLogReader.Event {
    var json: [String: Any] = ["schema_version": 5, "ts": "x", "event": "run_completed",
                               "run_id": runId, "kind": "run", "started_at": started ?? ""]
    if let ended { json["ended_at"] = ended }
    if let summary {
        json["summary"] = try JSONSerialization.jsonObject(with: JSONEncoder().encode(summary))
    }
    return try JSONDecoder().decode(
        EventLogReader.Event.self, from: JSONSerialization.data(withJSONObject: json))
}

// MARK: - The decision

@Suite struct RunBannerPlanTests {

    @Test func aCleanRunFinishesWithItsSessionCountAndDuration() throws {
        let plan = try #require(RunBanner.plan(
            for: .ready(Date()), terminus: terminus(summary: summary()), stopRequested: false))
        #expect(plan.kind == .finished)
        #expect(plan.sessionCount == 8)
        #expect(plan.durationSeconds == 38 * 60 + 0.5)
    }

    @Test func aRunTheResearcherStoppedSaysNothingEvenIfItExitedCleanly() throws {
        #expect(RunBanner.plan(for: .ready(Date()), terminus: nil, stopRequested: true) == nil)
        #expect(RunBanner.plan(
            for: .failed(.passthrough("x"), category: .network), terminus: nil, stopRequested: true) == nil)
    }

    // The three ways `.completedPartial` is reached without a failed session.

    @Test func quotesLeftOutAloneIsFinishedNotFinishedWithFailures() throws {
        let s = summary(leftOut: ["s2": 3])
        let plan = try #require(RunBanner.plan(
            for: .completedPartial(summary: s), terminus: nil, stopRequested: false))
        #expect(plan.kind == .finished)
    }

    @Test func sessionsWaitingForWhisperAreFinishedBecauseTheAppFinishesThemItself() throws {
        let s = summary(transcriptFailures: [cause(.deferred, session: "s3")])
        let plan = try #require(RunBanner.plan(
            for: .completedPartial(summary: s), terminus: nil, stopRequested: false))
        #expect(plan.kind == .finished)
    }

    @Test func filesRefusedAtIngestAreNotSessionsThatFailed() throws {
        let s = summary(ingestFailures: [cause(.unusableInput, session: nil)])
        let plan = try #require(RunBanner.plan(
            for: .completedPartial(summary: s), terminus: nil, stopRequested: false))
        #expect(plan.kind == .finished)
    }

    @Test func aSessionThatFailedIsFinishedWithFailuresAndCarriesTheAnalysedCount() throws {
        let s = summary(analysed: 6, quoteFailures: [cause(.network, session: "s3"), cause(.network, session: "s7")])
        let plan = try #require(RunBanner.plan(
            for: .completedPartial(summary: s), terminus: nil, stopRequested: false))
        #expect(plan.kind == .finishedWithFailures)
        #expect(plan.analysed == SessionsAnalysed(done: 6, total: 8))
    }

    // A run that did not finish.

    @Test func aFailedRunWithASummaryNamesItsReasonAndHowFarItGot() throws {
        let s = summary(analysed: 5, quoteFailures: [cause(.outOfCredit, session: "s6")])
        let plan = try #require(RunBanner.plan(
            for: .failedWithDiagnostic(summary: s), terminus: nil, stopRequested: false))
        #expect(plan.kind == .didntFinish)
        #expect(plan.reason == .outOfCredit)
        #expect(plan.analysed == SessionsAnalysed(done: 5, total: 8))
    }

    @Test func aFailedRunWithNoSummaryStatesNoCounts() throws {
        let plan = try #require(RunBanner.plan(
            for: .failed(.passthrough("x"), category: .network), terminus: nil, stopRequested: false))
        #expect(plan.kind == .didntFinish)
        #expect(plan.analysed == nil)
        #expect(plan.reason == .network)
    }

    @Test func aReasonThatSaysNothingIsLeftOut() throws {
        for category: PipelineFailureCategory in [.unknown, .userSignal, .providerNotSetUp, .outputExists] {
            let plan = try #require(RunBanner.plan(
                for: .failed(.passthrough("x"), category: category), terminus: nil, stopRequested: false))
            #expect(plan.reason == nil, "\(category) must not be named")
        }
    }

    @Test func aRunThatIsNotOverSaysNothing() {
        let states: [PipelineState] = [
            .scanning, .idle, .queued(position: 1), .running, .unreachable(reason: .timedOut),
            .partial(kind: "transcribe-only", stagesComplete: []),
            .stopped(stagesComplete: [], interrupted: false),
            .stopped(stagesComplete: [], interrupted: true),
        ]
        for state in states {
            #expect(RunBanner.plan(for: state, terminus: nil, stopRequested: false) == nil, "\(state)")
        }
    }

    @Test func anOverflowRowCountsAsAFailureBecauseTheWireTruncatedTheList() {
        // More failures than the wire carries: the visible ones may all be
        // deferred, but the hidden ones are failures.
        let overflow = SessionFailure(
            sessionId: nil, sourceFile: nil, cause: Cause(category: .network, message: "... and 3 more"))
        let s = summary(quoteFailures: [cause(.deferred, session: "s1"), overflow])
        #expect(RunBanner.hasSessionFailure(s))
    }

    /// `dominantCategory()` returns the wire's `CauseCategory`; the banner reads
    /// it as the row's `PipelineFailureCategory` by raw value. Two enums nothing
    /// else keeps in step: this pins which wire categories have no row category
    /// (and so name no reason).
    @Test func theWireCategoriesWithNoRowCategoryAreExactlyTheKnownTwo() {
        let unmapped = CauseCategory.allCases
            .filter { PipelineFailureCategory(rawValue: $0.rawValue) == nil }
        #expect(Set(unmapped) == [.cloudFetch, .deferred])
    }

    // Duration.

    @Test func theDurationIsOmittedWhenAnEndTimeIsMissing() throws {
        #expect(RunBanner.durationSeconds(of: try terminus(ended: nil)) == nil)
        #expect(RunBanner.durationSeconds(of: nil) == nil)
    }

    @Test func pythonMicrosecondsParse() {
        #expect(RunBanner.parseTimestamp("2026-11-06T09:00:00.123456Z") != nil)
        #expect(RunBanner.parseTimestamp("2026-11-06T09:00:00Z") != nil)
        #expect(RunBanner.parseTimestamp("nonsense") == nil)
    }
}

// MARK: - The words

@MainActor
struct RunBannerTextTests {

    private func english() throws -> I18n {
        let root = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("bristlenose/locales")
        let i18n = I18n()
        i18n.configure(localesDirectory: root)
        i18n.setLocale("en")
        return i18n
    }

    @Test func aFinishedBodyLeadsWithTheOutcomeAndPutsTheDurationLast() throws {
        let plan = RunBannerPlan(kind: .finished, sessionCount: 8, durationSeconds: 38 * 60)
        let text = plan.text(projectName: "Checkout study", i18n: try english())
        #expect(text.title == "Checkout study")
        #expect(text.body == "Analysis finished \u{00B7} 8 sessions \u{00B7} 38m")
    }

    @Test func aFailureNamesItsReasonThenHowFarItGotAndNeverTheDuration() throws {
        let plan = RunBannerPlan(
            kind: .didntFinish, analysed: SessionsAnalysed(done: 5, total: 8),
            reason: .outOfCredit, durationSeconds: 600)
        let text = plan.text(projectName: "Checkout study", i18n: try english())
        #expect(text.body == "The analysis didn\u{2019}t finish \u{00B7} Out of credit \u{00B7} 5 of 8 sessions analysed")
        #expect(text.category == .didntFinish)
    }

    @Test func aFailureWithNoReasonAddsNothingToSayItIsUnknown() throws {
        let plan = RunBannerPlan(kind: .didntFinish)
        let text = plan.text(projectName: "P", i18n: try english())
        #expect(text.body == "The analysis didn\u{2019}t finish")
        #expect(!text.body.lowercased().contains("unknown"))
    }

    @Test func theBodyNeverCarriesAFileNameOrACauseMessage() throws {
        // A plan has no field a file name or a cause message could ride in.
        let mirror = Mirror(reflecting: RunBannerPlan(kind: .didntFinish))
        let names = Set(mirror.children.compactMap(\.label))
        #expect(names == ["kind", "sessionCount", "analysed", "reason", "durationSeconds"])
    }

    /// The locale gate (`scripts/check-locales.py --strict`) is the pin for key
    /// coverage; this reads each key through the runtime in every locale, so a
    /// key the runtime cannot resolve (a raw key on screen) fails here too.
    @Test func everyLocaleResolvesEveryKeyTheBannerReads() throws {
        let i18n = try english()
        for locale in I18n.supportedLocales {
            i18n.setLocale(locale)
            for key in ["desktop.runBanner.finished", "desktop.runBanner.finishedWithFailures",
                        "desktop.runBanner.prealert.title", "desktop.runBanner.prealert.body",
                        "desktop.runBanner.prealert.continue", "desktop.chrome.failedTitle",
                        "settings.general.notifyLabel", "settings.general.notifyOffInSystem",
                        "settings.general.notifyOpenSystemSettings",
                        "settings.heading", "desktop.settingsTabs.general"] {
                #expect(i18n.t(key) != key, "\(key) does not resolve in \(locale)")
            }
            for count in [1, 2, 5] {
                let word = i18n.plural("desktop.runBanner.sessions", count: count)
                #expect(!word.hasPrefix("desktop."), "sessions plural for \(count) does not resolve in \(locale)")
            }
            #expect(i18n.t("desktop.runBanner.prealert.body").contains("{{path}}"), "\(locale) lost the {{path}} placeholder")
            for category in PipelineFailureCategory.allMentionableForBanner {
                #expect(i18n.t(category.labelKey) != category.labelKey, "\(category) label missing in \(locale)")
            }
        }
    }
}

private extension PipelineFailureCategory {
    /// Every category the banner may name, as `RunBanner.mentionable` decides.
    static var allMentionableForBanner: [PipelineFailureCategory] {
        [.auth, .outOfCredit, .network, .quota, .disk, .whisper, .apiRequest, .modelUnavailable,
         .apiServer, .missingDep, .missingInput, .missingBinary, .outputTruncated, .unusableInput]
            .compactMap { RunBanner.mentionable($0) }
    }
}

@Suite struct RunBannerClickTests {
    @Test func aWellFormedClickNamesItsProject() {
        let id = UUID()
        #expect(RunBannerClick.projectID(from: ["projectID": id.uuidString]) == id)
    }

    @Test func anythingElseNamesNothing() {
        #expect(RunBannerClick.projectID(from: nil) == nil)
        #expect(RunBannerClick.projectID(from: [:]) == nil)
        #expect(RunBannerClick.projectID(from: ["projectID": "not a uuid"]) == nil)
        #expect(RunBannerClick.projectID(from: ["projectID": 7]) == nil)
    }

    @Test func onlyTheFrontWindowActsAndOnlyOnAStudyStillInTheSidebar() {
        let id = UUID()
        #expect(RunBannerClick.shouldSelect(id, known: [id], windowIsFront: true))
        #expect(!RunBannerClick.shouldSelect(id, known: [id], windowIsFront: false), "a back window must not change study")
        #expect(!RunBannerClick.shouldSelect(id, known: [UUID()], windowIsFront: true), "a removed study is a quiet no-op")
    }
}

// MARK: - The gate

@Suite struct ResearcherAttentionTests {

    private let looking = ResearcherAttention(
        appIsActive: true, windowIsVisible: true, displayIsAwake: true,
        screenIsUnlocked: true, sessionIsActive: true)

    @Test func theResearcherIsLookingOnlyWhenEveryConditionHolds() {
        #expect(looking.isLooking)
    }

    @Test func anyOneConditionFailingMeansTheyAreAway() {
        var a = looking; a.appIsActive = false; #expect(!a.isLooking, "another app is in front")
        var b = looking; b.windowIsVisible = false; #expect(!b.isLooking, "every window is minimised or closed")
        var c = looking; c.displayIsAwake = false; #expect(!c.isLooking, "the display is asleep")
        var d = looking; d.screenIsUnlocked = false; #expect(!d.isLooking, "the screen is locked")
        var e = looking; e.sessionIsActive = false; #expect(!e.isLooking, "another user's session is in front")
    }
}

// MARK: - The preference

struct RunBannerPreferenceTests {

    private func defaults() -> (UserDefaults, String) {
        let name = "runbanner-\(UUID().uuidString)"
        return (UserDefaults(suiteName: name)!, name)
    }

    @Test func itIsOnWhenNeverSetThroughTheOneAccessor() {
        let (d, name) = defaults(); defer { d.removePersistentDomain(forName: name) }
        #expect(RunBannerPreference.isOn(d))
    }

    @Test func itIsOnAfterRegisteringDefaultsAndOffWhenTheSwitchIsOff() {
        let (d, name) = defaults(); defer { d.removePersistentDomain(forName: name) }
        RunBannerPreference.registerDefaults(d)
        #expect(d.bool(forKey: RunBannerPreference.key), "a plain read of the key must agree with the accessor")
        d.set(false, forKey: RunBannerPreference.key)
        #expect(!RunBannerPreference.isOn(d))
    }
}

// MARK: - The coordinator

@MainActor
final class FakeBannerSystem: RunBannerSystem {
    var status: RunBannerAuthorization = .allowed
    var grants = true
    var requests = 0
    var posts: [(identifier: String, thread: String, text: RunBannerText)] = []
    var categoryRegistrations = 0
    func authorization() async -> RunBannerAuthorization { status }
    func requestAuthorization() async -> Bool { requests += 1; status = grants ? .allowed : .denied; return grants }
    func registerCategories(placeholders: [RunBannerCategory: String]) { categoryRegistrations += 1 }
    func post(identifier: String, threadID: String, projectID: UUID, text: RunBannerText) async {
        posts.append((identifier, threadID, text))
    }
}

@MainActor
final class FakePreAlert: RunBannerPreAlerting {
    var shown = 0
    func present(i18n: I18n) async { shown += 1 }
}

@MainActor
struct RunBannerCoordinatorTests {

    private let away = ResearcherAttention(
        appIsActive: false, windowIsVisible: true, displayIsAwake: true,
        screenIsUnlocked: true, sessionIsActive: true)
    private let looking = ResearcherAttention(
        appIsActive: true, windowIsVisible: true, displayIsAwake: true,
        screenIsUnlocked: true, sessionIsActive: true)

    private func rig(
        attention: ResearcherAttention, on: Bool = true, status: RunBannerAuthorization = .allowed
    ) -> (RunBannerCoordinator, FakeBannerSystem, FakePreAlert) {
        let system = FakeBannerSystem(); system.status = status
        let pre = FakePreAlert()
        let c = RunBannerCoordinator(
            system: system, preAlert: pre, i18n: I18n(), attention: { attention }, isOn: { on })
        return (c, system, pre)
    }

    /// Wait as long for "nothing" as for "something": the coordinator hops a
    /// main-actor task before it posts.
    private func settle() async { try? await Task.sleep(for: .milliseconds(200)) }

    private func end(_ c: RunBannerCoordinator, key: String = "run-1", stop: Bool = false,
                     state: PipelineState = .ready(Date())) {
        c.runDidEnd(projectID: UUID(), projectName: "Checkout study", state: state,
                    terminus: nil, stopRequested: stop, runKey: key)
    }

    @Test func itPostsOnceWhenTheResearcherIsAway() async {
        let (c, system, _) = rig(attention: away)
        end(c)
        await settle()
        #expect(system.posts.count == 1)
        #expect(system.posts.first?.text.title == "Checkout study")
    }

    @Test func itPostsNothingWhileTheResearcherIsLooking() async {
        let (c, system, _) = rig(attention: looking)
        end(c)
        await settle()
        #expect(system.posts.isEmpty)
    }

    @Test func aRunEndedTwiceIsPostedOnce() async {
        let (c, system, _) = rig(attention: away)
        end(c); end(c)
        await settle()
        #expect(system.posts.count == 1, "the same run must not post twice")
    }

    @Test func twoRunsEndingTogetherEachSayTheirOwnThing() async {
        let (c, system, _) = rig(attention: away)
        end(c, key: "run-1"); end(c, key: "run-2")
        await settle()
        #expect(system.posts.count == 2)
        #expect(Set(system.posts.map(\.identifier)) == ["run-1", "run-2"])
    }

    @Test func itPostsNothingWhenTheSwitchIsOff() async {
        let (c, system, _) = rig(attention: away, on: false)
        end(c)
        await settle()
        #expect(system.posts.isEmpty)
    }

    @Test func itPostsNothingWhenNotificationsAreNotAllowed() async {
        for status in [RunBannerAuthorization.denied, .notDetermined] {
            let (c, system, _) = rig(attention: away, status: status)
            end(c)
            await settle()
            #expect(system.posts.isEmpty, "\(status)")
        }
    }

    @Test func aRunTheResearcherStoppedPostsNothing() async {
        let (c, system, _) = rig(attention: away)
        end(c, stop: true)
        await settle()
        #expect(system.posts.isEmpty)
    }

    @Test func aRunThatIsNotOverPostsNothing() async {
        let (c, system, _) = rig(attention: away)
        end(c, state: .running)
        await settle()
        #expect(system.posts.isEmpty)
    }

    // The permission flow.

    @Test func theResearcherStartingARunIsAskedOnceWhileNothingHasBeenAsked() async {
        let (c, system, pre) = rig(attention: away, status: .notDetermined)
        c.researcherStartedRun(); c.researcherStartedRun()
        await settle()
        #expect(pre.shown == 1, "the one-button screen, once")
        #expect(system.requests == 1, "the system's own request, once")
    }

    @Test func nobodyIsAskedAgainOnceAnswered() async {
        for status in [RunBannerAuthorization.allowed, .denied] {
            let (c, system, pre) = rig(attention: away, status: status)
            c.researcherStartedRun()
            await settle()
            #expect(pre.shown == 0 && system.requests == 0, "\(status): the system will not prompt twice, and neither do we")
        }
    }

    @Test func nobodyIsAskedWhenTheSwitchIsOff() async {
        let (c, system, pre) = rig(attention: away, on: false, status: .notDetermined)
        c.researcherStartedRun()
        await settle()
        #expect(pre.shown == 0 && system.requests == 0)
    }
}

// MARK: - The runner's hooks

@MainActor
final class BannerSink: RunBannerNoting {
    var ends: [(projectName: String, state: PipelineState, runKey: String, stop: Bool)] = []
    var starts = 0
    func runDidEnd(projectID: UUID, projectName: String, state: PipelineState,
                   terminus: EventLogReader.Event?, stopRequested: Bool, runKey: String) {
        ends.append((projectName, state, runKey, stopRequested))
    }
    func researcherStartedRun() { starts += 1 }
}

@MainActor
struct RunBannerRunnerTests {

    private func settle() async { try? await Task.sleep(for: .milliseconds(300)) }

    @Test func aRunThatFinishesTellsTheBannerOnceWithItsProject() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("Checkout study")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 10)
        rig.launches[0].exit()
        await PipelineRunnerQueueTests.until { !sink.ends.isEmpty }
        await settle()

        #expect(sink.ends.count == 1)
        #expect(sink.ends.first?.projectName == "Checkout study")
        if case .ready = sink.ends.first?.state { } else { Issue.record("not .ready: \(String(describing: sink.ends.first?.state))") }
    }

    @Test func aRunThatFailsTellsTheBanner() async throws {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("A")
        rig.runner.start(project: a)
        let dir = URL(fileURLWithPath: a.path).appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let now = ISO8601DateFormatter().string(from: Date())
        let lines = [
            #"{"schema_version":5,"ts":"\#(now)","event":"run_started","run_id":"rf","kind":"run","started_at":"\#(now)"}"#,
            #"{"schema_version":5,"ts":"\#(now)","event":"run_failed","run_id":"rf","kind":"run","started_at":"\#(now)","ended_at":"\#(now)","outcome":"failed","cause":{"category":"out_of_credit","message":"x"}}"#,
        ]
        try Data((lines.joined(separator: "\n") + "\n").utf8)
            .write(to: dir.appendingPathComponent(EventLogReader.filename))
        rig.launches[0].exit(.exited(code: 1))
        await PipelineRunnerQueueTests.until { !sink.ends.isEmpty }
        await settle()

        #expect(sink.ends.count == 1)
        if case .failed = sink.ends.first?.state { } else { Issue.record("not .failed") }
    }

    @Test func theResearchersOwnStopTellsTheBannerNothing() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        rig.onSignal = { launch, sig in if sig == SIGINT { launch.exit(.exited(code: 130)) } }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.runner.cancel(project: a)
        await PipelineRunnerQueueTests.until { rig.runner.state[a.id] != .running }
        await settle()

        #expect(sink.ends.isEmpty, "Stop is the researcher's own act")
    }

    @Test func aLaunchScanOfAPastRunTellsTheBannerNothing() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("Last week")
        rig.writeFinishedRun(in: a, tokens: nil)
        rig.runner.scan(project: a)
        await PipelineRunnerQueueTests.until {
            if case .ready = rig.runner.state[a.id] { return true }; return false
        }
        await settle()

        #expect(sink.ends.isEmpty, "a scan reads a past run; it must not announce it")
    }

    /// The end read timed out on a slow disk and settled later, as R29 reads it.
    private func slowEndRig() -> PipelineRunnerQueueTests.Rig {
        PipelineRunnerQueueTests.Rig(
            manifestRead: { _ in
                try? await Task.sleep(for: .milliseconds(120))
                return .ready(Date())
            },
            endStateTimeout: .milliseconds(40))
    }

    @Test func aFinishedRunWhoseEndReadTimedOutIsAnnouncedWhenItIsReadAgain() async {
        let rig = slowEndRig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 10)
        rig.launches[0].exit()
        await PipelineRunnerQueueTests.until { !sink.ends.isEmpty }
        await settle()

        #expect(sink.ends.count == 1, "a late end is still a witnessed end, once")
        #expect(sink.ends.first?.stop == false)
    }

    @Test func aStopWhoseEndReadTimedOutDoesNotAnnounceFinishedWhenItIsReadAgain() async {
        let rig = slowEndRig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        rig.onSignal = { launch, sig in if sig == SIGINT { launch.exit(.exited(code: 1)) } }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 10)
        rig.runner.cancel(project: a)
        await PipelineRunnerQueueTests.until {
            if case .ready = rig.runner.state[a.id] { return true }; return false
        }
        await settle()

        #expect(sink.ends.allSatisfy { $0.stop }, "the researcher's Stop must reach the banner as a stop, even when the end is read late")
    }

    @Test func aTerminusFromBeforeThisRunIsNotThisRunsAndGetsAStableKey() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("A")
        // A finished run is already on disk when this one starts, and this one
        // writes no terminus of its own: the one on disk is the previous run's.
        rig.writeFinishedRun(in: a, runId: "previous", tokens: nil)
        rig.runner.start(project: a)
        rig.launches[0].exit()
        await PipelineRunnerQueueTests.until { !sink.ends.isEmpty }
        await settle()

        #expect(sink.ends.count == 1)
        #expect(sink.ends.first?.runKey == "no-terminus-\(a.id.uuidString)",
                "a previous run's id must not key this run, and the fallback is stable")
    }

    @Test func onlyAStartTheResearcherChoseIsAskedAbout() async {
        let rig = PipelineRunnerQueueTests.Rig(); defer { rig.cleanUp() }
        let sink = BannerSink(); rig.runner.runBanner = sink
        let a = rig.project("A"), b = rig.project("B")
        rig.runner.start(project: a, origin: .automatic)
        #expect(sink.starts == 0, "a queue restore or an automatic re-run must not ask")
        rig.runner.start(project: b)
        #expect(sink.starts == 1)
    }
}
