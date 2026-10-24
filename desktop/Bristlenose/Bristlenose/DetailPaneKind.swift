import Foundation

/// Which pane the detail column shows for the window's project — the decision
/// that lived inline in `ContentView.detail`'s if/else cascade, lifted into
/// data so the other surfaces that need the same answer (lens availability,
/// the report-only toolbar items) read *this* instead of re-deriving
/// approximations that drift (the `selectedProjectShowsReport` lesson).
///
/// `resolve` is a pure function per the house convention: if a SwiftUI view is
/// making a decision, the decision belongs in a testable helper. The view
/// switches on the result; `DetailPaneKindTests` pins the cascade order.
enum DetailPaneKind: Equatable {
    /// No sole project selected — the Welcome home or the multi-select pane.
    case noProject
    /// Project directory not accessible — volume ejected or folder moved.
    case unavailable
    /// Analysing with the decorative shoal taking the pane (preference +
    /// Reduce Motion permitting). No document mounts behind it.
    case shoal
    /// Nothing to analyse yet, or a folder project that has never produced a
    /// report — the "Drag interviews here" pane.
    case dragInterviews
    /// A never-run study whose folder `run` refuses by name — the home folder
    /// or a system root (`ScanSelection.refusal`, `_refuse_reason` in
    /// Python). "Drag Interviews Here" would send the researcher to add files
    /// to a folder that can never be analysed, so the pane says why instead,
    /// in the sentence the serve's status page uses (decision #110, 22 Oct 2026).
    case unsuitableFolder
    /// The serve-backed surface — boot view, then the report WKWebView.
    case report

    /// Mirror of the `detail` cascade, in its original order: unreachable
    /// beats everything; the shoal owns the pane during analysis; an empty
    /// folder prompts for interviews; a never-run folder prompts again, unless
    /// `run` refuses the folder itself (`folderRefused`) (`.idle` only — `.scanning` falls through to the serve so an
    /// already-analysed project boots rather
    /// than flashing an empty pane before the manifest read resolves; failed /
    /// cancelled / partial states keep the serve surface, which carries the
    /// cause and log tail).
    static func resolve(
        hasProject: Bool,
        isAvailable: Bool,
        showShoal: Bool,
        pathIsEmpty: Bool,
        pipelineState: PipelineState?,
        folderRefused: Bool = false
    ) -> DetailPaneKind {
        guard hasProject else { return .noProject }
        if !isAvailable { return .unavailable }
        if showShoal { return .shoal }
        if pathIsEmpty { return .dragInterviews }
        if case .idle = pipelineState ?? .scanning {
            return folderRefused ? .unsuitableFolder : .dragInterviews
        }
        return .report
    }

    /// Whether the decorative shoal takes the pane: while analysing, with the
    /// animation preference on and Reduce Motion off — and only until the
    /// first session is readable. From then the report is the surface: the
    /// Sessions lens can be read while the rest is processed
    /// (docs/design-progressive-lenses.md, Phase 1 step 18).
    static func shoalTakesPane(
        animationOn: Bool, reduceMotion: Bool, analysing: Bool, sessionsReadable: Int?
    ) -> Bool {
        animationOn && !reduceMotion && analysing && (sessionsReadable ?? 0) == 0
    }

    /// Whether the report reloads when a run settles. Not when a progressive
    /// first analysis succeeded under the report the researcher was reading
    /// during it: the SPA refetches when `/last-run` moves, and a reload would
    /// throw away their place in the transcript. A re-analyse still reloads
    /// (it can renumber sessions under the same route), and so does a failure
    /// — the page that describes it is the serve's.
    static func reloadsOnCompletion(
        documentState: DocumentState, settled: PipelineState?, progressive: Bool
    ) -> Bool {
        guard progressive, case .spa = documentState else { return true }
        switch settled {
        case .ready, .completedPartial: return false
        default: return true
        }
    }

    /// What should cover a status page the serve is showing for a project that
    /// has a new run queued or under way — or nil to leave the page showing.
    ///
    /// The serve's status page describes the *last terminus* and knows nothing
    /// of the Mac's run queue, so re-analysing a project whose last run failed
    /// put "Last run failed." under a sidebar row saying "Queued · position 1"
    /// (28 Sep 2026: a 31 Aug out-of-credit failure, resurfaced while the
    /// project waited behind another study's run). A real report (`.spa`) is
    /// left alone — reading the previous analysis while the new one waits is
    /// legitimate. `.running` needs this too: with the shoal off (preference or
    /// Reduce Motion) it reaches the same stale page.
    ///
    /// A run that ended without finishing, or could not start, is covered too:
    /// the Mac draws the failed, stopped, stranded and refused panes natively,
    /// because it knows more than the page — why a run was refused, which
    /// sentence the row's popover gives (owner, 24 Oct 2026,
    /// `docs/mockups/detail-pane-states.html` Q1). A stop over an earlier
    /// report reaches none of this: the serve shows that report (Q4).
    enum RunCover: Equatable {
        case queued(position: Int)
        /// Its line is the row's own (`RunProgressSubtitle.compose`), under the
        /// row's ring.
        case analysing
        /// The app's leaving cut the run short (Quit, a crash, a power cut), or
        /// it lost its process.
        case interrupted
        /// The researcher pressed Stop.
        case stopped
        /// The run was refused for want of an AI provider.
        case needsProvider
        /// The run failed. `sentence` is the category's own localised sentence
        /// (`FailureMessage.failure(for:)`), never the provider's raw words,
        /// which `rawCause` keeps for Show details; `summary` is the breakdown
        /// a run that failed part-way carries.
        case failed(sentence: FailureMessage, rawCause: String?,
                    category: PipelineFailureCategory, summary: PipelineSummary?)
    }

    static func runCover(pipelineState: PipelineState?, documentState: DocumentState) -> RunCover? {
        guard case .statusPage = documentState else { return nil }
        switch pipelineState {
        case .queued(let position): return .queued(position: position)
        case .running: return .analysing
        case .stopped(_, let interrupted): return interrupted ? .interrupted : .stopped
        case let state? where state.isStranded: return .interrupted
        case let state? where state.needsProvider: return .needsProvider
        // A stop the classifier filed as a failure is still the researcher's.
        case .failed(_, .userSignal): return .stopped
        case .failed(let message, let category):
            // A keyed message is already ours (the classifier names the
            // provider it saw); a passthrough is the record's English, so the
            // pane says the category's sentence and keeps the words for details.
            let sentence = message.key == nil ? FailureMessage.failure(for: category) : message
            return .failed(sentence: sentence, rawCause: message.english,
                           category: category, summary: nil)
        case .failedWithDiagnostic(let summary):
            let category = PipelineFailureCategory(
                rawValue: summary.dominantCategory().rawValue) ?? .unknown
            return .failed(sentence: FailureMessage.failure(for: category), rawCause: nil,
                           category: category, summary: summary)
        default: return nil
        }
    }

    /// What a failed run's pane offers, by remedy
    /// (`docs/mockups/error-patterns-and-chrome-crash.html`): the button that
    /// goes to the fix where one exists, Retry where trying again is the act,
    /// and nothing otherwise — a default must never invent a chore.
    enum FailureRemedy: Equatable {
        case setUpProvider
        case retry
        case none

        static func of(_ category: PipelineFailureCategory) -> FailureRemedy {
            switch category {
            // Yours to fix, and the fix is in Settings ▸ LLM Provider.
            case .auth, .modelUnavailable, .providerNotSetUp: return .setUpProvider
            // Nothing wrong at your end (quota, api_server), or ours (unknown,
            // api_request): trying again is the act.
            case .quota, .apiServer, .unknown, .apiRequest: return .retry
            // Yours to fix with no door here, a limit rather than a fault, or
            // the researcher's own stop.
            case .outOfCredit, .network, .disk, .whisper, .missingDep, .missingInput,
                 .missingBinary, .outputExists, .outputTruncated, .unusableInput,
                 .userSignal:
                return .none
            }
        }
    }
}
