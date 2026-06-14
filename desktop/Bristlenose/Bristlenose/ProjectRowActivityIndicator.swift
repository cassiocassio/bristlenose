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

    /// When non-nil and `kind == .running`, hovering swaps the spinner for a
    /// cancel × in the *same* fixed frame; clicking it calls this. Mouse-only
    /// fast path (App Store download-ring lineage) — Stop is also reachable via
    /// the Project menu (⌘.) and the row context menu, which is where keyboard
    /// and VoiceOver users (who can't hover) reach it.
    var onStop: (() -> Void)? = nil

    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        switch kind {
        case .running:
            ZStack {
                if hovering, onStop != nil {
                    // Hover state: a neutral grey cancel × (Finder/App Store
                    // idiom — grey, not red; red would read as "error"). A
                    // Button, not a tap gesture, so List selection isn't broken
                    // on macOS 26 (same reason the `+N` delta is a Button).
                    Button(action: { onStop?() }) {
                        Image(systemName: "xmark.circle.fill")
                            .imageScale(.small)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                } else {
                    ProgressView()
                        .controlSize(.small)
                }
            }
            // Fixed frame: spinner and × share one 16pt box, so the hover swap
            // never changes the row's layout — nothing jumps or reflows.
            .frame(width: 16, height: 16)
            .contentShape(Rectangle())
            .onHover { inside in
                if reduceMotion {
                    hovering = inside
                } else {
                    withAnimation(.easeInOut(duration: 0.12)) { hovering = inside }
                }
                // Pointing-hand only while the × is live (native inline-click
                // affordance; no underline). Balanced push/pop.
                if onStop != nil {
                    if inside { NSCursor.pointingHand.push() } else { NSCursor.pop() }
                }
            }
            // Decorative + mouse-only: VoiceOver/keyboard reach Stop via the
            // menu, and the row's accessibilityLabel carries "Analysing…".
            .accessibilityHidden(true)
        case .none:
            EmptyView()
        }
    }
}
