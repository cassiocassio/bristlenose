import SwiftUI

/// Per-project activity indicator for the sidebar row's subtitle-right slot.
///
/// **Pure view.** It takes a precomputed `Kind` from `ProjectRow` (which
/// already observes `PipelineRunner` / `PipelineLiveData` / the copy state), so
/// the indicator adds no observation of its own. Keying is by `project.id`
/// upstream, so this composes unchanged when concurrent runs and multi-window
/// land post-TF: N rows render N indicators from the same dictionary.
///
/// **Vocabulary** (see `docs/design-sidebar-activity-indicators.md`): motion =
/// healthy / ambient; static colour = attention. This slot carries the *motion*
/// signal for an in-flight run *or copy*. Failure / partial-completion stay in
/// the subtitle text + their `MessageKind` glyph — not here. Availability (the
/// cloud glyph) is a separate concern owned by `ProjectRow.subtitleRightSlot`.
///
/// **Determinacy.** A run shows the determinate, Welford-ETA-weighted ring
/// (`.running(fraction:)`, nil → indeterminate spinner before calibration); a
/// drag-import copy shows the determinate byte-ratio ring (`.copying(fraction:)`).
/// Both render identically and share the hover-cancel — they differ only in the
/// `onStop` closure the call site supplies (cancel the run vs cancel the copy).
struct ProjectRowActivityIndicator: View {

    /// What the trailing slot should show for *activity* — distinct from
    /// availability (cloud glyph) and from failure/partial (subtitle text).
    enum Kind: Equatable {
        /// A run is in flight. `fraction` is the determinate ring fill
        /// (monotonic + asymptote-clamped); nil → indeterminate spinner
        /// (uncalibrated first run before any measured signal arrives).
        case running(fraction: Double?)
        /// A drag-import copy is in flight into this project. `fraction` is the
        /// 0…1 byte ratio (always determinate — `CopyMachinery` measures bytes).
        case copying(fraction: Double)
        /// Nothing to show; the row falls back to the cloud glyph / empty.
        case none

        /// Pure derivation from the project's pipeline state. Exhaustive with
        /// no `default:` so a new `PipelineState` case forces an explicit
        /// decision here at compile time rather than silently mapping to
        /// `.none`. `progress` carries the determinate ring fill when in flight.
        /// (Copy isn't a `PipelineState`; `ProjectRow` builds `.copying` directly.)
        static func from(
            pipelineState: PipelineState?, progress: PipelineProgress? = nil
        ) -> Kind {
            switch pipelineState {
            case .running:
                return .running(fraction: progress?.ringFraction)
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

    /// When non-nil (and `kind` is `.running`/`.copying`), hovering swaps the
    /// ring for a cancel × in the *same* fixed frame; clicking it calls this.
    /// Mouse-only fast path (App Store download-ring lineage) — Stop / Cancel
    /// are also reachable via the Project menu (⌘.) and the row context menu,
    /// which is where keyboard and VoiceOver users (who can't hover) reach them.
    var onStop: (() -> Void)? = nil

    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        switch kind {
        case .running(let fraction):
            ring(fraction: fraction)
        case .copying(let fraction):
            ring(fraction: fraction)
        case .none:
            EmptyView()
        }
    }

    /// The determinate ring (or indeterminate spinner when `fraction` is nil),
    /// with a hover-swapped cancel ×. Shared by `.running` and `.copying`.
    @ViewBuilder
    private func ring(fraction: Double?) -> some View {
        ZStack {
            if hovering, onStop != nil {
                // Hover state: a neutral grey cancel × (Finder/App Store idiom —
                // grey, not red; red would read as "error"). A Button, not a tap
                // gesture, so List selection isn't broken on macOS 26 (same
                // reason the `+N` delta is a Button).
                Button(action: { onStop?() }) {
                    Image(systemName: "xmark.circle.fill")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            } else if let fraction {
                // Determinate ring. Stock circular ProgressView (on the system
                // grid). For a run the fill is monotonic + asymptote-capped
                // (RunProgressMath); for a copy it's the raw byte ratio.
                // QA: confirm macOS 26 renders value-circular as a determinate
                // ring, not a spinner ignoring `value` — fall back to
                // `Circle().trim(...)` if the stock style doesn't fill.
                ProgressView(value: fraction)
                    .progressViewStyle(.circular)
                    .controlSize(.small)
            } else {
                ProgressView()
                    .controlSize(.small)
            }
        }
        // Fixed frame: ring and × share one 16pt box, so the hover swap never
        // changes the row's layout — nothing jumps or reflows.
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
        // Decorative + mouse-only: VoiceOver/keyboard reach Stop/Cancel via the
        // menu, and the row's accessibilityLabel carries "Analysing…"/"Copying…".
        .accessibilityHidden(true)
    }
}
