import Foundation

/// What a settled batch hands over: where it was aimed, and what reached it.
///
/// `landed` rather than a count, because the names are needed — seeding the
/// folder watcher with them is what stops the project row showing a
/// surprise-files pill for files the researcher deliberately imported.
struct CloudImportBatchResult: Equatable {
    let projectID: UUID
    let landed: [URL]
}

/// What happens to a project once a cloud batch has finished landing files in
/// it.
///
/// **Why this exists at all.** Until now the batch ended at the bytes: the
/// files arrived in the destination folder and nothing started. That is one
/// step short of the feature's own sentence — *"tick the obvious research
/// calls, and click get-them-all — download **and ingest**"* — and it is the
/// half a researcher notices, because a folder of MP4s is the drudgery they
/// were trying to delegate.
///
/// **Why it is a separate, pure type.** The decision has four inputs and no
/// side effects, and every one of its branches is otherwise unreachable
/// without a paid tenant, a live download and a subprocess: "a batch landed
/// into a project whose last run failed" is not a state you can get to by
/// hand. Held here it is an ordinary table test. Held inside the coordinator
/// it would be a comment.
///
/// The guards mirror `ContentView.handleDropOnProject` deliberately — the two
/// paths differ in where the bytes came from and in nothing else, and a
/// researcher who drags four files and one who imports four recordings should
/// not get two different answers about whether their study re-runs.
enum CloudImportHandoff {

    /// How the destination project is shaped, which decides whether a run can
    /// see the new files at all.
    enum Shape: Equatable {
        /// `inputFiles == nil` — the CLI rescans the folder at run time, so
        /// whatever the import wrote folds in by itself. The common case, and
        /// the shape `NewProjectDestination` always creates.
        case folder
        /// `inputFiles != nil` — the project names its inputs, so new paths
        /// must be registered or a run will not see them. The CLI has no
        /// `--files` yet, so it cannot scope a run to just the additions.
        case fileSubset
    }

    enum Action: Equatable {
        /// Seed the folder watcher with the landed names, then start a run.
        /// Incremental if the project has already been analysed, fresh if not
        /// — that difference is the pipeline's, not ours.
        case analyse
        /// Register the paths so a later full run includes them, but start
        /// nothing.
        case registerOnly
        case nothing(Decline)
    }

    /// Why no run started. Each of these is a state where starting one would
    /// be wrong rather than merely unnecessary.
    enum Decline: Equatable {
        /// The batch landed no files — every row failed, or the researcher
        /// stopped it before anything settled. "Never hand a certainly-failing
        /// situation forward."
        case nothingLanded
        /// A run is already going for this project. Its inputs were fixed when
        /// it started, so the new files belong to the next one.
        case runInProgress
        /// The last run failed. Re-running unbidden would burn LLM spend
        /// repeating the same failure; the researcher retries from the pill,
        /// which is a decision rather than an accident.
        case previousRunFailed
        /// The volume is unmounted or the folder has gone.
        case projectUnreachable
    }

    /// - Parameter landed: how many files this batch actually wrote. Not how
    ///   many were requested — a partial batch is ordinary and gets processed
    ///   (incremental analysis is what makes that ordinary), but a batch that
    ///   landed nothing has nothing to analyse.
    static func decide(landed: Int, shape: Shape, state: PipelineState?) -> Action {
        guard landed > 0 else { return .nothing(.nothingLanded) }

        switch state {
        case .running, .queued:
            return .nothing(.runInProgress)
        // Both failure shapes, not just the older one. `.failedWithDiagnostic`
        // is what a modern abandoned run resolves to, so matching only
        // `.failed` would auto-re-run exactly the projects whose failure we
        // know most about.
        case .failed, .failedWithDiagnostic:
            return .nothing(.previousRunFailed)
        case .unreachable:
            return .nothing(.projectUnreachable)
        default:
            break
        }

        switch shape {
        case .folder:     return .analyse
        case .fileSubset: return .registerOnly
        }
    }

    /// Whether the landed names should be handed to the folder watcher as
    /// "known".
    ///
    /// **Only when a run is starting**, and the asymmetry is the point. Seeding
    /// suppresses the row's new-files count pill, which is right when the run
    /// itself is the acknowledgement and wrong in every other case: a batch
    /// that landed into a busy, failed or file-subset project has put real
    /// files in a real folder that nothing is going to read, and the count pill
    /// is the affordance that already says so — from the sidebar, with the
    /// import window long closed.
    ///
    /// So the declines deliberately stay *un*seeded. That is not an oversight
    /// to tidy up later; it is what stops this path needing a toast, a sheet or
    /// a verb it would have had to invent.
    static func seedsWatcher(_ action: Action) -> Bool {
        action == .analyse
    }
}
