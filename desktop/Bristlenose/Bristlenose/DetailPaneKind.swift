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
    enum RunCover: Equatable {
        case queued(position: Int)
        case analysing
    }

    static func runCover(pipelineState: PipelineState?, documentState: DocumentState) -> RunCover? {
        guard case .statusPage = documentState else { return nil }
        switch pipelineState {
        case .queued(let position): return .queued(position: position)
        case .running: return .analysing
        default: return nil
        }
    }
}
