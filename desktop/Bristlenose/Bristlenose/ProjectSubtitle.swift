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
    /// Pipeline reported the project unreachable mid-scan.
    ///
    /// `reason` was a **`String`** until 26 Aug 2026, and the doc-comment here
    /// described it as "a Python-supplied string … rendered verbatim". Both
    /// halves were wrong: all five strings were written in Swift, in
    /// `PipelineRunner`, and rendering them verbatim is what put an
    /// unlocalised, glyph-less, un-clickable sentence on the row — the one case
    /// in this enum breaking the "raw data, never a baked string" rule stated at
    /// the top of the file. It is now `UnreachableReason`, which carries a
    /// `MessageKind` and a locale key, so the view localises it like everything
    /// else and the glyph follows from the kind.
    case unreachable(reason: UnreachableReason)
    /// A drop / Add-Files gesture is landing N interviews in THIS project — the
    /// pre-copy "Adding N interviews…" acknowledgement, held for a ~2 s floor so
    /// it can't flash-and-vanish on a near-instant clonefile copy, then it yields
    /// to the copy/scan states and finally the stage ladder. Phase 2.
    case addingInterviews(count: Int)
    /// A drag-import copy is landing files in THIS project. Carries the 0…1
    /// byte fraction; the view renders "Copying · N%" + a determinate ring
    /// (with hover-cancel) in the trailing slot — the row's *only* copy surface
    /// (the toolbar copy pill was removed: copy is a per-project op, so it lives
    /// on the row; the title-bar pill is reserved for app-global ops — §4
    /// placement axis). Mac direct manipulation: feedback appears on the row you
    /// dropped onto.
    case copying(fraction: Double)
    /// A cloud-import batch is landing recordings in THIS project. Renders
    /// **"3 of 4" and nothing else** — the download phase needs no verb at all
    /// (`docs/mockups/cloud-import-sidebar-progress.html` §3). A count, because
    /// a count is the question a closed window leaves: not how fast, not which
    /// file, but how many are still to wait for.
    ///
    /// `done` counts rows that have *settled*, whatever the outcome. A ring
    /// stalled at 3 because the fourth failed is a ring saying nothing.
    case importingBatch(done: Int, total: Int)
    /// A copy into THIS project is being cancelled (rollback in flight). Renders
    /// "Cancelling…" + an indeterminate spinner — the immediate ack for the
    /// row's hover-cancel, mirroring what the removed toolbar pill showed.
    case copyCancelling
    /// The bare last-run date with an optional delta segment — **Schema A, not
    /// emitted since 29 Jul 2026.** `resolveIdle` now returns `.deltaOnly` or
    /// `.placeholder` instead (Schema E: a clean row shows no status line).
    ///
    /// Retained deliberately, not dead by accident: it is the exact output shape
    /// the deferred Appearance preference would restore, so the pref becomes a
    /// choice between two already-modelled variants rather than new render code.
    /// The view still handles it. Don't delete without reading
    /// `docs/design-desktop-project-status.md` §"Schema E".
    case ready(date: Date, delta: SubtitleDelta?)
    /// A delta with no date anchor (CLI-analysed / imported / pre-this-build
    /// project that never recorded `lastPipelineRunAt`). The delta is the whole
    /// subtitle.
    case deltaOnly(SubtitleDelta)
    /// Nothing to say — the view renders a hidden placeholder to reserve height.
    case placeholder
}

/// What the subtitle's leading glyph does when the user clicks it.
///
/// A glyph is a signifier, and a signifier that names an action must perform
/// one — the popover doc's own anti-pattern list puts it plainly: *"the
/// affordance promises something it doesn't deliver"*. So this and
/// `SubtitleVariant.glyph` are decided together: a state either has a glyph
/// AND a door behind it, or neither.
enum SubtitleGlyphAction: Equatable {
    /// Opens `ProjectDiagnosticPopover`, anchored to the glyph.
    case diagnostics
    /// Opens the files sheet — the folder and the analysis disagree, and the
    /// sheet is where the disagreement is enumerated.
    case files
    /// Runs the Locate flow — the folder isn't where the project expects it.
    case locate
    /// No glyph, or nothing behind it.
    case none
}

extension SubtitleVariant {
    /// The glyph's destination. **Exhaustive, no `default`** so a new variant
    /// forces an explicit decision here rather than silently rendering an inert
    /// glyph (same convention as `ProjectRowActivityIndicator.Kind.from` and
    /// `pipelineIsFree`). Table-tested in `ProjectSubtitleTests`.
    ///
    /// The verb-led progress states (`running`, `copying`, `queued`, …) are
    /// `.none` on purpose and are NOT a gap: they are `MessageKind.info` —
    /// *"it's just happening"* — and the 18 Jun rulings give info no glyph. Their
    /// affordance is the trailing ring's hover-cancel, which is the act a
    /// researcher actually wants mid-run.
    var glyphAction: SubtitleGlyphAction {
        switch self {
        case .failed, .failedDiagnostic, .completedPartial, .unreachable:
            return .diagnostics
        case .cantFind:
            // The glyph called itself "a Locate affordance" in this file's
            // comments while rendering as a static `NSImageView` — Locate lived
            // only in the context menu. Now it is the door it always claimed to
            // be. (26 Aug 2026.)
            return .locate
        case .deltaOnly:
            // Both deltas lead to the same sheet, because they are two readings
            // of one condition: `UnanalysedState` describes a single
            // folder-vs-analysis disagreement, and `NewFilesSheet` already
            // renders both its `newFiles` and its `missingFiles`.
            //
            // `.unanalysed` WAS clickable on the SwiftUI row and lost the click
            // in the AppKit cutover — `SidebarSubtitleText` composes the delta
            // into flat subtitle text, so there was no target left. This is that
            // click restored, and `.missing` joining it.
            return .files
        case .ready(_, let delta):
            // Not emitted under Schema E, but kept honest: a `.ready` carrying a
            // delta is the same disagreement with a date in front of it.
            return delta == nil ? .none : .files
        case .stopping, .running, .queued, .stopped, .partial,
             .addingInterviews, .copying, .importingBatch,
             .copyCancelling, .placeholder:
            return .none
        }
    }

    /// Whether the project can't be reached right now, so the row dims. The
    /// availability twin of `.cantFind`, which dims via `availability.isReady`.
    var isUnreachable: Bool {
        if case .unreachable = self { return true }
        return false
    }

    /// Whether the glyph opens the diagnostic popover. Derived from
    /// `glyphAction` so the two can't disagree.
    var isDiagnostic: Bool { glyphAction == .diagnostics }
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
    /// (idle: copying › missing › unanalysed › silence)`.
    ///
    /// The idle tier's terminus is **silence, not a date** — Schema E, 29 Jul
    /// 2026. See `resolveIdle`.
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
        addingCount: Int?,
        copy: CopyDisplay?,
        importBatch: (done: Int, total: Int)?,
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
                addingCount: addingCount,
                copy: copy,
                importBatch: importBatch,
                lastRunAt: lastRunAt,
                missingCount: missingCount,
                unanalysedCount: unanalysedCount
            )
        }
    }

    /// The idle / ready tier: an active copy, then a data-drift delta, then
    /// **nothing at all**.
    ///
    /// `lastRunAt` is accepted but **not read** (Schema E — the bare date it
    /// used to produce is retired). It stays in the signature because the
    /// deferred Appearance pref would restore the `.ready(date:delta:)` branch
    /// verbatim, and because callers already thread it. The *baseline* job that
    /// `lastPipelineRunAt` still does happens upstream, in
    /// `ProjectIndex.handleWatcherUpdate` — it gates whether `unanalysedCount`
    /// is non-zero at all.
    private static func resolveIdle(
        addingCount: Int?,
        copy: CopyDisplay?,
        importBatch: (done: Int, total: Int)?,
        lastRunAt: Date?,
        missingCount: Int,
        unanalysedCount: Int
    ) -> SubtitleVariant {
        // The pre-copy "Adding N interviews…" gesture ack outranks the copy and
        // the resting date/delta (the ~2 s floor keeps it up briefly). It yields
        // to `.running` automatically — that's returned by the main switch before
        // we ever reach the idle tier.
        if let addingCount { return .addingInterviews(count: addingCount) }
        // A cloud batch outranks a local copy, and both outrank the resting
        // date/delta. The order matters in exactly one situation and it is a
        // real one: a researcher can drop files on a project while a cloud
        // batch is landing in it. The batch is the longer-running and less
        // visible of the two — a local clonefile is near-instant and the
        // researcher just watched themselves start it — so the batch keeps the
        // line. Nothing is lost: the copy's own ~2s "Adding N interviews…" ack
        // has already been shown above.
        if let importBatch {
            return .importingBatch(done: importBatch.done, total: importBatch.total)
        }
        // An active local copy (or its cancellation) outranks the resting date/delta.
        if let copy {
            switch copy {
            case .copying(let fraction): return .copying(fraction: fraction)
            case .cancelling: return .copyCancelling
            }
        }
        let delta = pickDelta(missingCount: missingCount, unanalysedCount: unanalysedCount)
        // **Schema E (settled 29 Jul 2026) — a clean row is silent.** A delta is
        // an exception and earns a line; a project that is simply analysed and
        // fine says nothing, and `ProjectCellSpec` collapses `.placeholder` to a
        // single-line row. The bare last-run date that used to render here is
        // retired: a timestamp earns chrome when it records *someone else's*
        // action (why Mail has dates), and on one researcher's own machine they
        // already know what they did. Full rationale + the supersession note
        // (this overrides the June "defer until async" decision on its merits;
        // that trigger has NOT fired) in
        // `docs/design-desktop-project-status.md` §"Schema E".
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
