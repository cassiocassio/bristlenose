import SwiftUI

/// Per-project activity indicator for the sidebar row's subtitle-right slot.
///
/// **Pure view.** It takes a precomputed `Kind` from `ProjectRow` (which
/// already observes `PipelineRunner` / `PipelineLiveData`), so the indicator
/// adds no observation of its own. Keying is by `project.id` upstream, so this
/// composes unchanged when concurrent runs and multi-window land post-TF:
/// N rows render N indicators from the same dictionary, no view rework.
///
/// **Vocabulary** (see `docs/design-sidebar-activity-indicators.md`): motion =
/// healthy / ambient; static colour = attention. This slot carries the *motion*
/// signal for an in-flight run. Failure / partial-completion stay in the
/// subtitle text + their `MessageKind` glyph — not here. Availability (the
/// cloud glyph) is a separate concern owned by `ProjectRow.subtitleRightSlot`.
///
/// **Determinacy.** Today a run shows an indeterminate spinner — the same
/// control the toolbar pill uses (`PipelineActivityItem`). The determinate,
/// Welford-ETA-weighted ring (time, not stage-count) lands once the events
/// channel carries the estimate (Phase 0b); copy-in-flight's determinate ring
/// (byte ratio) is a sibling increment. Both add a `Kind` case without touching
/// the call site.
struct ProjectRowActivityIndicator: View {

    /// What the trailing slot should show for *activity* — distinct from
    /// availability (cloud glyph) and from failure/partial (subtitle text).
    enum Kind: Equatable {
        /// A run is in flight — indeterminate spinner (Welford-ETA ring in 0b).
        case running
        /// Nothing to show; the row falls back to the cloud glyph / empty.
        case none

        /// Pure derivation from the project's pipeline state. Exhaustive with
        /// no `default:` so a new `PipelineState` case forces an explicit
        /// decision here at compile time rather than silently mapping to
        /// `.none`.
        static func from(pipelineState: PipelineState?) -> Kind {
            switch pipelineState {
            case .running:
                return .running
            case .scanning, .idle, .queued, .ready, .failed, .unreachable,
                 .partial, .stopped, .completedPartial, .failedWithDiagnostic,
                 .none:
                // .scanning keeps its existing title-right spinner (a transient
                // pre-run state). Queued / stopped / partial / failed /
                // completedPartial are carried by the subtitle text + glyph.
                return .none
            }
        }
    }

    let kind: Kind

    var body: some View {
        switch kind {
        case .running:
            // Same control as the toolbar pill — a system spinner that respects
            // Reduce Motion natively. Hidden from VoiceOver: the row's
            // accessibilityLabel carries the state in words.
            ProgressView()
                .controlSize(.small)
                .accessibilityHidden(true)
        case .none:
            EmptyView()
        }
    }
}
