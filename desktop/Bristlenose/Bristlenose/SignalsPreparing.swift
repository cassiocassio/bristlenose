import Foundation

/// The sidebar's "Picking up Signals…" line: when it shows, as a pure
/// decision (`docs/design-signals-lens-readiness.md` §3.3).
///
/// **The fact is the window's own bridge state, not a new message.** While the
/// first Signals report is being built the serve withholds the Signals lens and
/// nothing else, and the SPA posts that over `lens-availability`. A progressive
/// run withholds Signals too, but always with Project and Codebooks beside it
/// (`server/lens_readiness.py`), and a run in flight outranks this line in
/// `ProjectSubtitle` besides, so "Signals and nothing else" is the one shape
/// that means a build, not a run. `LensReadiness.isPreparingSignals`.
///
/// **The hand-over from a run is a native prior**, the shape `ArtifactPrior`
/// and the 2 second floor on "Adding N interviews…" already use. A run's
/// subtitle ends when its process exits; the withheld fact arrives from the
/// serve's poll of a document that is itself reloading, seconds later, so
/// without a prior the row would collapse to one line and grow again. So when
/// a first analysis ends in this window the window predicts "preparing" and
/// holds it until the bridge speaks, or `priorLimit` runs out.
///
/// **A minimum display** applies to every showing, prior or bridge, so a small
/// study that builds in under a second does not flash the line.
struct SignalsPreparing: Equatable {

    /// How long a showing lasts at least.
    static let minimumDisplay: TimeInterval = 2
    /// How long the prior waits for the bridge before it gives up. A quiet
    /// bridge means no report to build (no cloud model) or a window that never
    /// reloaded, so the prior must not hold the line for ever.
    static let priorLimit: TimeInterval = 10

    /// A first analysis ended at `at`, when the bridge had posted `posts`
    /// `lens-availability` messages in all.
    struct Armed: Equatable {
        var at: Date
        var posts: Int
    }

    var armed: Armed?
    var shownSince: Date?

    struct Verdict: Equatable {
        var show: Bool
        /// When to ask again with nothing else having changed: the prior's end,
        /// or the end of the minimum display. Nil when only a change in the
        /// bridge can change the answer.
        var recheckAfter: TimeInterval?
    }

    /// Whether a run's end should arm the prior: this window ran the study's
    /// first analysis to a report. A re-analysis or an added interview leaves
    /// the old report to be read, and the serve never withholds the lens over
    /// one (`signals_preparing`, "a rebuild never takes away what is readable"),
    /// so predicting a build there would be the prior being wrong. A transcribe-
    /// only or stopped or failed run builds nothing.
    static func shouldArm(old: PipelineState?, new: PipelineState?, analysedBefore: Bool) -> Bool {
        guard !analysedBefore, case .running = old else { return false }
        switch new {
        case .ready, .completedPartial:
            return true
        case .failed, .failedWithDiagnostic, .stopped, .partial, .unreachable,
             .running, .queued, .scanning, .idle, nil:
            return false
        }
    }

    mutating func arm(now: Date, posts: Int) {
        armed = Armed(at: now, posts: posts)
    }

    /// Back to nothing: a selection change, where the document goes with it.
    mutating func clear() {
        armed = nil
        shownSince = nil
    }

    /// The answer now. `readiness` is what the bridge last said; `posts` how
    /// many messages it has posted in all.
    ///
    /// The bridge **confirms** the prior only with a post made since the run
    /// ended AND one that describes a finished run: nothing withheld, or
    /// Signals alone. A stale post that still shows the run's own shape (Project
    /// and Codebooks withheld) lands in that gap now and then, and it is not the
    /// bridge speaking about the report.
    mutating func evaluate(readiness: LensReadiness, posts: Int, now: Date) -> Verdict {
        if let armed {
            let spoken = posts > armed.posts && (readiness == .all || readiness.isPreparingSignals)
            if spoken || now.timeIntervalSince(armed.at) >= Self.priorLimit {
                self.armed = nil
            }
        }
        let priorWait = armed.map { Self.priorLimit - now.timeIntervalSince($0.at) }
        let bridgeSays = readiness.isPreparingSignals
        if bridgeSays || priorWait != nil {
            if shownSince == nil { shownSince = now }
            return Verdict(show: true, recheckAfter: bridgeSays ? nil : priorWait)
        }
        if let shownSince {
            let elapsed = now.timeIntervalSince(shownSince)
            if elapsed < Self.minimumDisplay {
                return Verdict(show: true, recheckAfter: Self.minimumDisplay - elapsed)
            }
            self.shownSince = nil
        }
        return Verdict(show: false, recheckAfter: nil)
    }
}

extension LensReadiness {
    /// Signals is the only lens withheld: the first report is being built after
    /// a run, which the server withholds on its own. During a progressive run
    /// Project and Codebooks are withheld beside it, and an overlay that ended
    /// without a report keeps them withheld, so this shape cannot be a run's.
    var isPreparingSignals: Bool { unavailable == [.signals] }
}
