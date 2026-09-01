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
    /// File-subset project with no viewable analysis — the CLI can't analyse
    /// this shape yet, so the pane shows the files instead. A subset project
    /// that somehow HAS analysis data (analysed while folder-shaped, files
    /// added later) falls through to `.report`: the run state must not block
    /// viewing what's already there.
    case unsupportedSubset
    /// The serve-backed surface — boot view, then the report WKWebView.
    case report

    /// Mirror of the `detail` cascade, in its original order: unreachable
    /// beats everything; the shoal owns the pane during analysis; an empty
    /// folder prompts for interviews; an unanalysed file-subset explains
    /// itself; a never-run folder prompts again (`.idle` only — `.scanning`
    /// falls through to the serve so an already-analysed project boots rather
    /// than flashing an empty pane before the manifest read resolves; failed /
    /// cancelled / partial states keep the serve surface, which carries the
    /// cause and log tail).
    static func resolve(
        hasProject: Bool,
        isAvailable: Bool,
        showShoal: Bool,
        pathIsEmpty: Bool,
        isFileSubset: Bool,
        pipelineState: PipelineState?
    ) -> DetailPaneKind {
        guard hasProject else { return .noProject }
        if !isAvailable { return .unavailable }
        if showShoal { return .shoal }
        if pathIsEmpty { return .dragInterviews }
        if isFileSubset && !hasViewableData(pipelineState) { return .unsupportedSubset }
        if case .idle = pipelineState ?? .scanning { return .dragInterviews }
        return .report
    }

    /// Whether a pipeline state means the project has analysis data the user
    /// should be able to view. `.ready` and `.partial` both qualify;
    /// `.completedPartial` ran to terminus and wrote a (degraded) report.
    /// `.failedWithDiagnostic` deliberately stays false — the abandon path
    /// leaves no report on disk. (Moved from `ContentView`, where it gated the
    /// file-subset pane and, wrongly, nothing else.)
    static func hasViewableData(_ state: PipelineState?) -> Bool {
        switch state {
        case .ready, .partial, .completedPartial:
            return true
        default:
            return false
        }
    }
}
