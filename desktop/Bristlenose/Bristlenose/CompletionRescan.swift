import Foundation

/// Pure helper deciding which projects just *left* the analysing state — i.e. a
/// run (or passive scan) ended, so the analysis DB may have changed and the
/// sidebar's session count / file deltas need a fresh read. Kept out of the view
/// body so the transition logic is unit-testable (same "decisions live in a
/// testable helper, not the view body" convention as `RunProgressSubtitle` /
/// `RunProgressMath`).
///
/// **Why this exists separately from the report-reload's gate.** The folder
/// watcher only re-reads the analysis DB on its initial scan and on source-file
/// events; the DB lives under `bristlenose-output/`, outside that scope, so a
/// finished run never refreshes the count on its own (see
/// `ProjectFolderWatcher` + `SourceFilesReader`). `scheduleReportReloadOnCompletion`
/// fixes the *report WebView* but fires only on `analysing → report-ready` for
/// the *selected* project. The session count instead needs refreshing for *any*
/// project whose run ended in *any* terminal state — `ready`, `completedPartial`,
/// transcribe-only `partial`, `stopped`, or `failed` — since each can have
/// mutated the `sessions` table. Hence the broad "stopped being analysed"
/// predicate, run over every project in the state map rather than the selection.
enum CompletionRescan {

    /// True while a run/scan is in flight. Mirrors `ContentView.isAnalysing`
    /// (`.scanning` = passive manifest read, `.running` = active pipeline;
    /// neither carries a payload). Keep the two in sync.
    static func isAnalysing(_ state: PipelineState?) -> Bool {
        switch state {
        case .scanning, .running: return true
        default: return false
        }
    }

    /// IDs that transitioned out of the analysing state between `old` and `new`.
    /// Iterates `new.keys`, so a project removed mid-run (gone from `new`, no
    /// watcher to refresh) is skipped, and a freshly-added project (absent from
    /// `old`, so not "leaving" anything) is excluded.
    static func projectsLeavingAnalysis(
        old: [UUID: PipelineState], new: [UUID: PipelineState]
    ) -> [UUID] {
        new.keys.filter { isAnalysing(old[$0]) && !isAnalysing(new[$0]) }
    }

    /// IDs whose **run** just finished — narrower than `projectsLeavingAnalysis`,
    /// which also fires when a passive `.scanning` manifest read ends.
    ///
    /// Used to stamp `Project.lastPipelineRunAt`, which is the analysis
    /// *baseline* marker: `ProjectIndex.handleWatcherUpdate` suppresses the
    /// `+N unanalysed` drift until it's non-nil (the F14 policy — before a run,
    /// every file is "to be analysed" and flagging it would be surprising). A
    /// `.scanning` transition must not open that gate, because no analysis has
    /// happened.
    ///
    /// Deliberately counts **any** run outcome, not just success: the gate asks
    /// "has this project been analysed at all?", not "did it go well". A failed
    /// or cancelled run still leaves ingested sessions behind, and its own
    /// distress state outranks the drift in the precedence chain anyway.
    static func projectsFinishingRun(
        old: [UUID: PipelineState], new: [UUID: PipelineState]
    ) -> [UUID] {
        new.keys.filter { id in
            if case .running = old[id] { return !isAnalysing(new[id]) }
            return false
        }
    }
}
