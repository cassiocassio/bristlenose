import Foundation

/// The one-of subtitle states a sidebar row can be in, *after* the precedence
/// chain has collapsed every concurrent condition into a single winner.
///
/// Cases carry **raw** data (a `Date`, counts, enum reasons) — never a baked,
/// localised, or date-formatted string. Rendering (i18n + `DateFormatter`)
/// happens in the view, so this enum and `ProjectSubtitle.resolve` stay pure
/// and unit-testable — same split as `RunProgressSubtitle` (the leaf that
/// composes the in-flight ladder) vs the view that shows it.
enum SubtitleVariant: Equatable {
    /// `.cantFind` availability — the folder can't be reached. The view derives
    /// the reason-aware glyph + factual subtitle from `project.availability`, so
    /// the `reason` payload here is load-bearing only for test assertions today
    /// (and the future detail pane, design doc §7 — which would render the
    /// reason differently); the row render re-reads `availability` directly.
    case cantFind(reason: CantFindReason)
    /// `run_failed` with a Python-supplied one-line summary (the older
    /// summary-bearing path). The view shows it behind a clickable error glyph.
    case failed(summary: String)
    /// `run_failed` with a structured diagnostic but no inline summary — the
    /// view shows the localised "Run failed" header behind the error glyph; the
    /// detail lives in the popover.
    case failedDiagnostic
    /// `run_completed` at reduced fidelity (≥1 session failed). Localised
    /// "Partial completion" header behind the warning glyph.
    case completedPartial
    /// The user clicked Stop and the kill is still propagating — outranks the
    /// live progress so the click is acknowledged immediately.
    case stopping
    /// A run is in flight. The view composes the verb ladder (stage · N of M ·
    /// ETA) from `liveData` via `RunProgressSubtitle` — this case carries no
    /// payload because the precedence decision doesn't depend on the ladder
    /// contents, only on "a run is running and we're not stopping it".
    case running
    /// Waiting behind another project's run in the single-slot queue.
    case queued(position: Int)
    /// A prior run was cancelled and left resumable stages on disk.
    case stopped
    /// A `transcribe-only` (or otherwise partial) run completed cleanly.
    /// `transcribeOnly` picks "Transcribed" vs "Partial run".
    case partial(transcribeOnly: Bool)
    /// Pipeline reported the project unreachable mid-scan. `reason` is a
    /// Python-supplied string (not a localisation key) — rendered verbatim.
    case unreachable(reason: String)
    /// A drag-import copy is landing files in THIS project. Carries the 0…1
    /// byte fraction; the view renders "Copying · N%" + a determinate ring
    /// (with hover-cancel) in the trailing slot — the row's *only* copy surface
    /// (the toolbar copy pill was removed: copy is a per-project op, so it lives
    /// on the row; the title-bar pill is reserved for app-global ops — §4
    /// placement axis). Mac direct manipulation: feedback appears on the row you
    /// dropped onto.
    case copying(fraction: Double)
    /// A copy into THIS project is being cancelled (rollback in flight). Renders
    /// "Cancelling…" + an indeterminate spinner — the immediate ack for the
    /// row's hover-cancel, mirroring what the removed toolbar pill showed.
    case copyCancelling
    /// `.ready` / `.inCloud` / idle with analysis history — the bare last-run
    /// date, with an optional single delta segment. The cloud arrow (if any)
    /// renders in the right slot independently of this.
    case ready(date: Date, delta: SubtitleDelta?)
    /// A delta with no date anchor (CLI-analysed / imported / pre-this-build
    /// project that never recorded `lastPipelineRunAt`). The delta is the whole
    /// subtitle.
    case deltaOnly(SubtitleDelta)
    /// Nothing to say — the view renders a hidden placeholder to reserve height.
    case placeholder
}

extension SubtitleVariant {
    /// Whether this is a failure/partial "distress" state whose prefix glyph is a
    /// clickable diagnostic glyph (opens `ProjectDiagnosticPopover`) — vs a
    /// cantFind/locate glyph or a non-glyph state. **Exhaustive, no `default`** so a
    /// new variant forces an explicit diagnostic-or-not decision here rather than
    /// silently rendering no glyph (review F35/Bach; same convention as
    /// `ProjectRowActivityIndicator.Kind.from`). Table-tested in `ProjectSubtitleTests`.
    var isDiagnostic: Bool {
        switch self {
        case .failed, .failedDiagnostic, .completedPartial:
            return true
        case .cantFind, .stopping, .running, .queued, .stopped, .partial,
             .unreachable, .copying, .copyCancelling, .ready, .deltaOnly,
             .placeholder:
            return false
        }
    }
}

/// The single data-drift segment a row may surface (it shows at most one;
/// `ProjectSubtitle.pickDelta` arbitrates "missing wins over unanalysed").
enum SubtitleDelta: Equatable {
    case unanalysed(count: Int)
    case missing(count: Int)
}

/// Display state of an in-flight drag-import copy into a project, fed to
/// `resolve`. Decoupled from `CopyMachinery.InFlight` (the actor type) so the
/// resolver stays pure and testable. `.copying` carries the 0…1 byte fraction;
/// `.cancelling` is the rollback window after the user hits cancel.
enum CopyDisplay: Equatable {
    case copying(fraction: Double)
    case cancelling
}

/// Pure resolver for the sidebar row's subtitle — the cross-source precedence
/// chain lifted out of `ProjectRow`'s view body so it's testable in isolation
/// (the house rule: "a decision a view makes belongs in a testable helper, not
/// the view"; `desktop/CLAUDE.md`). It's also the substrate a future detail
/// pane would share — same arbitrated state rendered at two fidelities
/// (`docs/design-desktop-project-status.md` §6/§7).
///
/// No `i18n`, no `DateFormatter`, no SwiftUI — inputs are plain values, the
/// output is a `SubtitleVariant` carrying raw data the view then renders.
enum ProjectSubtitle {

    /// Apply the precedence chain to the concurrent conditions and return the
    /// single winning variant.
    ///
    /// **Order (settled 18 Jun 2026 — `docs/design-desktop-project-status.md`
    /// §Precedence, §5):**
    /// `cantFind (availability) › failed › running › stopped / partial ›
    /// (idle: copying › missing › unanalysed › ready)`.
    ///
    /// `cantFind` outranks *all* activity: you can't open the report if the
    /// folder's gone, and a run against a vanished folder is already doomed, so
    /// "can't reach the folder" is the only honest line. `.inCloud` is *not*
    /// `cantFind` (macOS materialises evicted files on open) — it falls through
    /// to the activity/idle chain and shows the bare date, with the cloud glyph
    /// in the row's right slot. Copying sits *below* the verb-led pipeline
    /// states (you can't run and copy at once in practice) but *above* the
    /// resting date/delta — an active import outranks "last analysed N days ago".
    static func resolve(
        availability: ProjectAvailability,
        pipelineState: PipelineState?,
        isStopping: Bool,
        copy: CopyDisplay?,
        lastRunAt: Date?,
        missingCount: Int,
        unanalysedCount: Int
    ) -> SubtitleVariant {
        // Tier 1 — availability beats everything when the project can't be
        // reached. `.ready` / `.inCloud` fall through.
        if case .cantFind(let reason) = availability {
            return .cantFind(reason: reason)
        }

        // Tier 2–4 — verb-led pipeline activity. Exhaustive with no `default`:
        // an unmapped future `PipelineState` should be a compile error here,
        // not a silent fall-through to "ready".
        switch pipelineState {
        case .failed(let summary, _):
            return .failed(summary: summary)
        case .failedWithDiagnostic:
            return .failedDiagnostic
        case .completedPartial:
            return .completedPartial
        case .running:
            // Stopping outranks progress — acknowledge the Stop click.
            return isStopping ? .stopping : .running
        case .queued(let position):
            return .queued(position: position)
        case .stopped:
            return .stopped
        case .partial(let kind, _):
            return .partial(transcribeOnly: kind == "transcribe-only")
        case .unreachable(let reason):
            return .unreachable(reason: reason)
        case .ready, .none, .scanning, .idle:
            // No verb-led activity — fall to the idle chain. `.scanning`'s
            // spinner lives in the title-line right slot, not the subtitle, so
            // it resolves the same as idle here.
            return resolveIdle(
                copy: copy,
                lastRunAt: lastRunAt,
                missingCount: missingCount,
                unanalysedCount: unanalysedCount
            )
        }
    }

    /// The idle / ready tier: an active copy, then a data-drift delta, then the
    /// bare last-run date. The date is sourced from `lastPipelineRunAt` (the
    /// persisted project model), so a `.ready` PipelineState and the
    /// `.idle`/`.none` fall-through agree on one truth-source.
    private static func resolveIdle(
        copy: CopyDisplay?,
        lastRunAt: Date?,
        missingCount: Int,
        unanalysedCount: Int
    ) -> SubtitleVariant {
        // An active import (or its cancellation) outranks the resting date/delta.
        if let copy {
            switch copy {
            case .copying(let fraction): return .copying(fraction: fraction)
            case .cancelling: return .copyCancelling
            }
        }
        let delta = pickDelta(missingCount: missingCount, unanalysedCount: unanalysedCount)
        if let lastRunAt {
            return .ready(date: lastRunAt, delta: delta)
        }
        // No date anchor (CLI-analysed / imported). Render the delta alone
        // rather than silently dropping data-drift signal for legacy projects.
        if let delta {
            return .deltaOnly(delta)
        }
        return .placeholder
    }

    /// Pick the single delta to surface: missing (data drift) wins over
    /// unanalysed (a feature gap). Returns nil when neither applies.
    static func pickDelta(missingCount: Int, unanalysedCount: Int) -> SubtitleDelta? {
        if missingCount > 0 {
            return .missing(count: missingCount)
        }
        if unanalysedCount > 0 {
            return .unanalysed(count: unanalysedCount)
        }
        return nil
    }
}
