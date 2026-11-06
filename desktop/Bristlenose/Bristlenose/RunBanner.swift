import Foundation

// The run-finished banner: the decisions, with nothing that touches the system.
//
// Design: docs/design-run-banner.md. The purpose, from the owner: "do I need to
// look at this?" A researcher who has gone away is told, once, that a run ended
// and how it ended. Everything here is a pure function of values so it can be
// table-tested; `RunBannerCoordinator` is what talks to macOS.

// MARK: - What ended, and how

enum RunBannerKind: Equatable {
    /// Nothing needs the researcher: the report is complete.
    case finished
    /// The report exists, and some sessions in it did not finish.
    case finishedWithFailures
    /// The run did not produce a report; something needs looking at.
    case didntFinish
}

/// The facts a banner may state. Only what the app already knows at the end of a
/// run; never a raw cause message (it can hold file names) and never a
/// session's file name (participant-bearing).
struct RunBannerPlan: Equatable {
    var kind: RunBannerKind
    /// Sessions in the report. Known for a finished run with a summary.
    var sessionCount: Int?
    /// "N of M sessions analysed", from `PipelineSummary.sessionsAnalysed`, so the
    /// banner, the sidebar row and the CLI say the same numbers. Absent when the
    /// run died before quotes, and for a `.failed` state, which has no summary.
    var analysed: SessionsAnalysed?
    /// Why the run did not finish, when it is a reason a researcher can use.
    var reason: PipelineFailureCategory?
    /// How long this analysis took, not the study: a resumed or cached run
    /// reports its own, shorter time. Absent when either end time is missing.
    var durationSeconds: Double?
}

enum RunBanner {

    /// The banner a run's end calls for, or nil when it calls for none.
    ///
    /// - Parameter state: the state the run ended in, after the end read.
    /// - Parameter terminus: the run's own terminal event, for its end times.
    /// - Parameter stopRequested: the researcher pressed Stop for this run. A
    ///   late Stop that still exits 0 reads as `.ready`, and "finished" would be
    ///   a banner for something they just did.
    static func plan(
        for state: PipelineState,
        terminus: EventLogReader.Event?,
        stopRequested: Bool
    ) -> RunBannerPlan? {
        if stopRequested { return nil }
        let duration = durationSeconds(of: terminus)

        switch state {
        case .ready:
            return RunBannerPlan(
                kind: .finished,
                sessionCount: terminus?.summary?.sessionsAnalysed?.total,
                durationSeconds: duration)

        case .completedPartial(let summary):
            // `.completedPartial` is reached by more than failures: quotes left
            // out, sessions waiting for Whisper (which the app finishes by
            // itself), and files refused at ingest. None of those is a session
            // that did not finish, so none makes "with failures" true.
            guard hasSessionFailure(summary) else {
                return RunBannerPlan(
                    kind: .finished, sessionCount: summary.sessionsAnalysed?.total,
                    durationSeconds: duration)
            }
            return RunBannerPlan(
                kind: .finishedWithFailures, analysed: summary.sessionsAnalysed,
                durationSeconds: duration)

        case .failedWithDiagnostic(let summary):
            return RunBannerPlan(
                kind: .didntFinish,
                analysed: summary.sessionsAnalysed,
                reason: mentionable(PipelineFailureCategory(rawValue: summary.dominantCategory().rawValue)),
                durationSeconds: duration)

        case .failed(_, let category):
            // No summary on this state, so no counts, and often no structured
            // cause either: say only what is known.
            return RunBannerPlan(kind: .didntFinish, reason: mentionable(category))

        case .scanning, .idle, .queued, .running, .unreachable, .partial, .stopped:
            return nil
        }
    }

    /// A session (not a file refused at ingest) that failed in a stage, and not
    /// one the app is about to finish on its own.
    static func hasSessionFailure(_ summary: PipelineSummary) -> Bool {
        summary.allBuckets
            .filter { $0.name != .ingest }
            .flatMap { $0.outcome.failed }
            .contains { failure in
                // An overflow row means more failures than the wire carries, so
                // there are failures even if the visible ones are all deferred.
                failure.isOverflowPlaceholder
                    || (failure.sessionId != nil && failure.cause.category != .deferred)
            }
    }

    /// Only categories with a reason a researcher can use. "Failed", "Stopped",
    /// a provider that was never set up and "already analysed" say nothing.
    static func mentionable(_ category: PipelineFailureCategory?) -> PipelineFailureCategory? {
        guard let category else { return nil }
        switch category {
        case .unknown, .userSignal, .providerNotSetUp, .outputExists:
            return nil
        default:
            return category
        }
    }

    // MARK: Duration

    static func durationSeconds(of terminus: EventLogReader.Event?) -> Double? {
        guard let terminus,
              let start = parseTimestamp(terminus.startedAt),
              let end = parseTimestamp(terminus.endedAt) else { return nil }
        let seconds = end.timeIntervalSince(start)
        return seconds > 0 ? seconds : nil
    }

    /// Python writes microseconds; `ISO8601DateFormatter` takes milliseconds.
    static func parseTimestamp(_ raw: String?) -> Date? {
        guard var text = raw else { return nil }
        if let dot = text.firstIndex(of: ".") {
            let afterDot = text.index(after: dot)
            let digitsEnd = text[afterDot...].firstIndex { !$0.isNumber } ?? text.endIndex
            let digits = text[afterDot..<digitsEnd]
            let ms = String(digits.prefix(3)).padding(toLength: 3, withPad: "0", startingAt: 0)
            text = String(text[..<afterDot]) + ms + String(text[digitsEnd...])
        }
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = withFraction.date(from: text) { return date }
        return ISO8601DateFormatter().date(from: text)
    }
}

// MARK: - The words

/// What the banner says. The title is the project's own name (the system shows
/// the app's icon and a relative time, and no app name). The body leads with the
/// outcome, then the facts that say how bad it is, then the duration last, so
/// the system's truncation drops the least useful fact first.
struct RunBannerText: Equatable {
    var title: String
    var body: String
    /// Which hidden-previews placeholder applies.
    var category: RunBannerCategory
}

/// Two categories, each with a generic placeholder the system shows when the
/// researcher has hidden previews (no project name in it).
enum RunBannerCategory: String, CaseIterable {
    case finished = "app.bristlenose.runBanner.finished"
    case didntFinish = "app.bristlenose.runBanner.didntFinish"
}

extension RunBannerPlan {
    var category: RunBannerCategory { kind == .didntFinish ? .didntFinish : .finished }

    /// Joined with " · " as the sidebar's status line is (`RunProgressSubtitle`).
    @MainActor
    func text(projectName: String, i18n: I18n) -> RunBannerText {
        var parts: [String] = []
        switch kind {
        case .finished:
            parts.append(i18n.t("desktop.runBanner.finished"))
            if let count = sessionCount {
                parts.append(i18n.plural("desktop.runBanner.sessions", count: count))
            }
        case .finishedWithFailures:
            parts.append(i18n.t("desktop.runBanner.finishedWithFailures"))
            if let analysed {
                parts.append(SidebarSubtitleText.completedPartialText(analysed, i18n: i18n))
            }
        case .didntFinish:
            parts.append(i18n.t("desktop.chrome.failedTitle"))
            if let reason { parts.append(i18n.t(reason.labelKey)) }
            if let analysed {
                parts.append(SidebarSubtitleText.completedPartialText(analysed, i18n: i18n))
            }
        }
        if let seconds = durationSeconds, kind != .didntFinish {
            parts.append(DurationFormat.human(seconds: seconds))
        }
        return RunBannerText(
            title: projectName, body: parts.joined(separator: " \u{00B7} "), category: category)
    }
}

// MARK: - The preference

/// Settings ▸ General. On by default. One accessor, and the default registered at
/// launch: `@AppStorage`'s own default is not a registered default, so code that
/// reads the key elsewhere (this) would otherwise see "never set" as false.
enum RunBannerPreference {
    static let key = "notifyOnRunEnd"

    static func registerDefaults(_ defaults: UserDefaults = .standard) {
        defaults.register(defaults: [key: true])
    }

    static func isOn(_ defaults: UserDefaults = .standard) -> Bool {
        defaults.object(forKey: key) as? Bool ?? true
    }
}

// MARK: - Is the researcher looking?

/// The researcher is looking at Bristlenose only when all of these hold. One
/// sentence, used everywhere (the ruling, the mockup, this test).
struct ResearcherAttention: Equatable {
    var appIsActive: Bool
    var windowIsVisible: Bool
    var displayIsAwake: Bool
    var screenIsUnlocked: Bool
    var sessionIsActive: Bool

    var isLooking: Bool {
        appIsActive && windowIsVisible && displayIsAwake && screenIsUnlocked && sessionIsActive
    }
}

// MARK: - What the runner tells the banner

/// What `PipelineRunner` calls. A protocol so tests can record, as the runner's
/// other side effects are (`noteRunSucceeded`, `recordRefusal`).
@MainActor
protocol RunBannerNoting: AnyObject {
    /// A run this app started has ended. `runKey` is stable for the run.
    func runDidEnd(
        projectID: UUID, projectName: String, state: PipelineState,
        terminus: EventLogReader.Event?, stopRequested: Bool, runKey: String)

    /// The researcher started an analysis themselves (not a queue restore at
    /// launch, not the automatic re-run when Whisper arrives).
    func researcherStartedRun()
}

enum RunStartOrigin: Equatable {
    case researcher
    case automatic
}
