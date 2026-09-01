import Foundation

/// Whether the lens affordances can act right now — one derivation for every
/// surface that renders or gates them: the sidebar lens rows (paint AND click
/// gate), the flag-off `LensRail`, the View menu's ⌘1–⌘5, and the report-only
/// toolbar items. Before this existed each surface hand-rolled its own
/// formula (`selectedProjectShowsReport`, `windowProject != nil && isReady`,
/// or nothing at all), and the formulas disagreed — the mirror-drift class
/// `Tab.hasLeftPanel` already documents.
///
/// The rule (design review 1 Sep 2026, D1-C "predict, then confirm"):
/// definitive document identity wins; while the document is still `.loading`,
/// the native side's *prior* answers. The prior is chosen to err dim, because
/// the two mistakes are not symmetric — a dim→lit transition is a promise
/// kept late, a lit→dim transition is a lie walked back.
enum LensAvailability: Equatable {
    case available
    case unavailable(Reason)

    enum Reason: Equatable {
        /// No sole project selected (Welcome, multi-select). The rows stay
        /// visible but dim — they teach the layout before any study exists.
        case noProject
        /// Project folder unreachable (volume ejected, folder moved).
        case projectUnreachable
        /// The pane never mounts a document — drag-interviews, unsupported
        /// subset, or the shoal owning the pane during analysis.
        case noDocument
        /// The sidecar failed to start; the pane shows the retry card.
        case serveFailed
        /// The document identified itself as the status page — no SPA, no
        /// shims, nothing for an activation to reach.
        case statusPage
        /// Document still loading and the prior predicts no report behind it.
        case awaitingDocument
    }

    var isAvailable: Bool { self == .available }

    static func derive(
        pane: DetailPaneKind,
        serveState: ServeState,
        documentState: DocumentState,
        priorPredictsViewableDocument: Bool
    ) -> LensAvailability {
        switch pane {
        case .noProject:
            return .unavailable(.noProject)
        case .unavailable:
            return .unavailable(.projectUnreachable)
        case .shoal, .dragInterviews, .unsupportedSubset:
            return .unavailable(.noDocument)
        case .report:
            break
        }
        // The pane is the serve surface. A failed sidecar shows the retry
        // card — no document is coming until Retry succeeds.
        if case .failed = serveState { return .unavailable(.serveFailed) }
        switch documentState {
        case .spa:
            return .available
        case .statusPage:
            return .unavailable(.statusPage)
        case .loading:
            return priorPredictsViewableDocument
                ? .available
                : .unavailable(.awaitingDocument)
        }
    }
}

/// The native side's best prediction of what the serve will render for a
/// project — consulted *only* while the document hasn't identified itself
/// (`DocumentState.loading`), then overruled by the document's own message.
///
/// Mirrors the deployed serve rule: the SPA renders iff the last terminus
/// completed (`status_page.detect_status`). Drift here is cheap by design —
/// the posterior corrects it within the document load — so this stays an
/// approximation rather than chasing exact parity. When the serve rule
/// changes (plan P5: serve the last good report after a failed re-run), flip
/// the failed-family rows in the same commit.
enum ArtifactPrior {
    static func predictsViewableDocument(
        pipelineState: PipelineState?,
        sessionCount: Int?
    ) -> Bool {
        switch pipelineState {
        case .ready, .partial, .completedPartial:
            // Last terminus completed → the serve renders the SPA.
            return true
        case .failed, .failedWithDiagnostic, .stopped, .unreachable, .idle:
            // Non-completed last terminus (or nothing to serve) → the serve
            // intercepts with the status page. Pre-P5 this holds even when an
            // older good report exists — mirror the serve, not the wish.
            return false
        case .running, .queued, .scanning, nil:
            // The run state doesn't tell us the *last terminus* — fall back
            // to artifact evidence: a populated analysis DB means a completed
            // import happened, and that DB is what the serve renders from.
            return (sessionCount ?? 0) > 0
        }
    }
}
