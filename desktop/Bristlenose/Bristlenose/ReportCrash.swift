import Foundation

/// The whole report failed to render in this window — the `/report` error
/// boundary's `report-error` bridge message (decision #2, 21 Oct 2026; spec
/// `docs/mockups/report-crash-fallback.html`). The payload of
/// `SubtitleVariant.reportError` and of the popover's crash body.
///
/// Raw data, never a sentence: the row and the popover headline come from a
/// locale key, and this carries only what Copy details needs — where it
/// happened, what the engine said, and the first stack frames. The SPA bounds
/// these before posting (`postReportError`); the parser bounds them again,
/// because a bridge message is input and a limit enforced on one side only is
/// a limit the other side can forget.
///
/// Kept by `BridgeHandler`, so it belongs to the window and never outlives it:
/// the next successful render (a `route-change`, which the fresh layout posts
/// on mount after Retry's reload), a status page, or a project switch in this
/// window (`reset`) clears it. `ready` does not — see `BridgeHandler.reportCrash`.
struct ReportCrash: Equatable, Sendable {
    /// The router path that was showing, e.g. `/report/quotes`.
    let route: String
    /// `TypeError: Cannot read properties of undefined (reading 'quotes')` —
    /// the error's name and message, as the SPA formats them.
    let message: String
    /// The first stack frames, each a line, oldest call first.
    let frames: [String]

    /// The same three numbers as `REPORT_ERROR_*` in `frontend/src/shims/bridge.ts`.
    static let messageLimit = 500
    static let frameLimit = 8
    static let frameLength = 300

    /// The bridge payload as a crash, or nil when it names no route or no
    /// message — a message with neither is not a crash report, and lighting a
    /// row for it would promise a popover with nothing to say. Oversized
    /// fields are cut, never refused: a long message is still a message.
    static func fromBridge(_ body: [String: Any]) -> ReportCrash? {
        guard let route = body["route"] as? String, !route.isEmpty,
              let message = body["message"] as? String, !message.isEmpty
        else { return nil }
        // Frame by frame, so one odd element costs that element, not the stack.
        let frames = (body["frames"] as? [Any] ?? [])
            .compactMap { $0 as? String }
            .prefix(frameLimit)
            .map { String($0.prefix(frameLength)) }
        return ReportCrash(
            route: String(route.prefix(messageLimit)),
            message: String(message.prefix(messageLimit)),
            frames: frames
        )
    }

    /// The state the diagnostic popover is built with when the row's glyph
    /// opens for this crash: the pipeline's, when it has one, else `.idle`.
    /// `.idle` is a stand-in for a non-optional `state`, not a fact about the
    /// project (it may never have been run) — so **no header button may key
    /// on `.idle`**; the crash outranks it, and the headline, body and copy
    /// are the crash's. Nil only when there is neither: nothing to open.
    static func popoverState(pipelineState: PipelineState?, crash: ReportCrash?) -> PipelineState? {
        if let pipelineState { return pipelineState }
        return crash == nil ? nil : .idle
    }

    /// Whether the row's pipeline state leaves the line to a crash. The
    /// verb-led and cause-shaped tier keeps it: a run in flight will reload
    /// the document when it ends; a failed run, a partial completion and an
    /// unreachable folder are plausible causes of which the crash is the
    /// consequence, and their popover (the bucket breakdown, the folder path)
    /// must stay reachable. A queued run yields — it may not start for hours,
    /// and the stack has no other door meanwhile — and so does everything at
    /// rest. Within the idle tier the crash then sits below the activities and
    /// the error-kind delta: see `ProjectSubtitle.resolveIdle`.
    ///
    /// **Exhaustive, no `default`** — the `ProjectSubtitle.resolve` convention:
    /// a new `PipelineState` must say where it stands against a crash.
    static func outranks(_ state: PipelineState?) -> Bool {
        switch state {
        case .failed, .failedWithDiagnostic, .running, .unreachable, .completedPartial:
            return false
        case .queued, .stopped, .partial, .ready, .scanning, .idle, .none:
            return true
        }
    }
}
