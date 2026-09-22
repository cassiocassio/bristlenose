import SwiftUI

// MARK: - Welcome animation baton
//
// Only ONE welcome cell animates at a time, so the "focus of interest" travels
// the golden spiral instead of every cell competing (design-welcome-studytools-
// illustrations.md). A cell that holds the baton animates; everyone else rests on
// their reduce-motion still. When a turn ends the baton passes to the next cell in
// spiral order that has something to animate. Strict one-at-a-time, all cells.
//
// **v2, 22 Sep 2026 — the illustration owns the clock.** v1 declared a turn
// LENGTH and slept for it, which meant two clocks that had to agree and nothing
// that made them: the declared turn and the illustration's own beat list. They
// never agreed. Measured across the six looping illustrations, every turn ran
// between 1.26 and 1.83 passes — so every turn ended mid-play, and a truncated
// pass was the last thing on screen before the cell went still. (`quote` was the
// other way: 0.97, so its sequence never once completed.)
//
// Now each illustration plays ONE pass, holds its finished frame, fades down to
// rest and calls `finish`. The baton passes then. `welcomeTurn` survives as a
// WATCHDOG CEILING — what to do when `finish` never arrives — not as a schedule,
// so the hand-written estimates it is built from stop being load-bearing.

/// Welcome cells, in golden-spiral order (the path the baton travels).
enum WelcomeSlot: Int, CaseIterable {
    case studyTools = 0, science, tip, ai, delight
}

@MainActor
final class WelcomeBaton: ObservableObject {
    /// The slot allowed to animate right now (nil = a rest beat, or nobody wants it).
    @Published private(set) var holder: WelcomeSlot?

    private var wants: [WelcomeSlot: Bool] = [:]
    private var turn:  [WelcomeSlot: Double] = [:]
    private let restBeat: Double
    private let tickSeconds: Double
    private var reduceMotion = false
    private var driver: Task<Void, Never>?

    /// Set by `finish` when the holding illustration says it has played out.
    private var finished = false
    /// Set by `claim` when the researcher moves a carousel — the playhead follows them.
    private var claimed: WelcomeSlot?

    init(restBeat: Double = 0.6, tickSeconds: Double = 0.1) {
        self.restBeat = restBeat
        self.tickSeconds = tickSeconds
    }

    func isActive(_ slot: WelcomeSlot) -> Bool { holder == slot }

    /// A cell reports whether it currently has something to animate and the watchdog
    /// ceiling for one turn. Cheap to call on every appear / slot change — the running
    /// driver reads it live.
    func report(_ slot: WelcomeSlot, wants w: Bool, turn t: Double) {
        wants[slot] = w
        turn[slot] = t
    }

    /// The holding illustration has played its one pass and held its finished frame.
    ///
    /// Guarded on `holder == slot`, so a straggling message from an illustration the
    /// baton has already moved past cannot cut the next cell short. That guard is the
    /// whole safety story: a webview is torn down when its cell loses the baton, so a
    /// message cannot outlive a full trip round the spiral and arrive during that same
    /// cell's *next* turn.
    func finish(_ slot: WelcomeSlot) {
        guard holder == slot else { return }
        finished = true
    }

    /// The researcher moved a carousel to a new slide: take the baton there and start
    /// that illustration from the top, interrupting whatever was playing.
    ///
    /// Navigating IS the statement "show me this one" — without it a new slide sits on
    /// its still frame until the spiral comes round, which can be most of a minute, and
    /// reads as a broken illustration. A cell with nothing to animate is ignored, so
    /// paging the Tip cell never takes the baton off a cell that is mid-play.
    func claim(_ slot: WelcomeSlot) {
        guard !reduceMotion, wants[slot] == true else { return }
        claimed = slot
    }

    /// Reduce-motion turns the whole choreography off — every cell shows its still.
    func setReduceMotion(_ on: Bool) {
        reduceMotion = on
        on ? stop() : start()
    }

    func start() {
        guard driver == nil, !reduceMotion else { return }
        driver = Task { @MainActor [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                guard let next = Self.nextHolder(claimed: self.claimed,
                                                 after: self.holder,
                                                 wants: self.wants) else {
                    self.holder = nil                              // nobody wants it — idle poll
                    try? await Task.sleep(for: .seconds(0.3))
                    continue
                }
                self.claimed = nil
                self.finished = false
                self.holder = next
                await self.waitOutTurn(next)
                if Task.isCancelled { break }
                // A claim mid-turn is the researcher asking for the next cell NOW;
                // don't make them sit through the rest beat first.
                if self.claimed != nil { continue }
                self.holder = nil                                  // a beat of stillness between turns
                try? await Task.sleep(for: .seconds(self.restBeat))
            }
        }
    }

    func stop() {
        driver?.cancel(); driver = nil; holder = nil
        finished = false; claimed = nil
    }

    /// Hold the turn open until the illustration says it has played out — or until its
    /// watchdog ceiling, or until a carousel claims the baton.
    ///
    /// A poll rather than a continuation, deliberately: three things can end a turn and
    /// two of them arrive from outside, so racing a continuation against a sleep buys a
    /// lifecycle hazard for granularity nobody can see. 100ms is a tenth of the shortest
    /// fade.
    private func waitOutTurn(_ slot: WelcomeSlot) async {
        let ceiling = turn[slot] ?? WelcomeTempo.fallbackCeiling
        var waited = 0.0
        while !Task.isCancelled, !finished, claimed == nil, waited < ceiling {
            try? await Task.sleep(for: .seconds(tickSeconds))
            waited += tickSeconds
        }
    }

    /// Pure: which slot takes the baton next. A carousel `claimed` wins outright (it is
    /// the researcher pointing at something); otherwise the next slot after `current` in
    /// spiral order, wrapping, that wants it; nil if nobody does. A claim for a slot with
    /// nothing to animate is ignored rather than honoured with an empty turn.
    /// Unit-tested in `WelcomeBatonTests`.
    static func nextHolder(claimed: WelcomeSlot? = nil,
                           after current: WelcomeSlot?,
                           wants: [WelcomeSlot: Bool]) -> WelcomeSlot? {
        if let claimed, wants[claimed] == true { return claimed }
        let order = WelcomeSlot.allCases
        guard order.contains(where: { wants[$0] == true }) else { return nil }
        let startPos = current.flatMap { order.firstIndex(of: $0) } ?? -1
        for step in 1...order.count {
            let slot = order[(startPos + step) % order.count]
            if wants[slot] == true { return slot }
        }
        return nil
    }
}

// MARK: - One tempo for every welcome illustration

/// Group + per-illustration animation tempo (14 Aug 2026 — the set played too
/// "look at me"). `speed` is the fraction of the originally-authored speed the
/// whole group runs at: 0.6 = 60%. `stretch` (1/speed) is the multiplier every
/// authored duration passes through — Swift natives via `stretch(for:)`, the
/// webviews via the interpolated `PACE` their `sleep()` scales by. Each
/// illustration can ALSO carry a local `pace` multiplier (>1 = slower still),
/// so one can be tuned without moving the group — the five tool webviews keep
/// the ×1.3 they were hand-tuned to before the group knob existed.
///
/// **The curtain (22 Sep 2026).** Every play is now punctuated, so a viewer can
/// see where a sequence begins and ends instead of joining one already running:
///
///     fade up → establish → play once → hold the finished frame → fade down to rest
///
/// The fade is the cue. The opening frame used to sit inert for a flat three
/// seconds before anything moved, which meant the eye — which only motion
/// summons — arrived *after* the beginning by design. Holds are absolute: they
/// don't scale with the group tempo, because reading speed doesn't.
enum WelcomeTempo {
    static let speed: Double = 0.6
    static var stretch: Double { 1.0 / speed }

    /// Curtain up and curtain down — the sequence's own punctuation.
    static let fadeSeconds: Double = 0.45
    /// Beat on the composed opening frame once the curtain is up, before anything moves.
    static let establishSeconds: Double = 1.0
    /// …for an opener that is a scene to read rather than an empty stage.
    static let establishReadSeconds: Double = 2.4
    /// Beat on the finished frame. Longer than the establish ON PURPOSE, and not an
    /// oversight to tidy: the opening frame is a stage nobody has earned yet, the
    /// closing one is the result — the payload, and the thing worth dwelling on.
    static let holdEndSeconds: Double = 3.0
    /// A cell that is not holding the baton rests here rather than at full strength.
    ///
    /// The curtain needs somewhere to fall TO. Falling to zero would empty the cell and
    /// leave a hole in the grid, and falling to zero and straight back — which is what
    /// happens when the resting frame and the finished frame are the same picture, as
    /// they are here — reads as a blink, not as an ending. So the rest is a recession,
    /// not a blackout, and it earns its keep twice: it also makes "which cell is
    /// playing" visible, which nothing said before.
    ///
    /// Judgement call, and a one-line one: 1.0 disables the recession and keeps only
    /// the opening dip as punctuation; lower dims the four resting cells harder.
    static let restOpacity: Double = 0.7
    /// Watchdog for an illustration that never reports its turn length.
    static let fallbackCeiling: Double = 20

    /// Local multiplier on top of the group tempo (individual tweak point).
    static func pace(_ kind: WelcomeIllustration) -> Double {
        switch kind {
        case .autocode, .manualTags, .tag, .starHide, .agentChat: return 1.3
        default: return 1.0
        }
    }

    /// Effective duration multiplier for one illustration.
    static func stretch(for kind: WelcomeIllustration) -> Double { stretch * pace(kind) }

    /// How long to rest on the opening frame before the sequence moves.
    ///
    /// The long form goes to the two whose opening frame is a composed scene with prose
    /// in it — Tag and Star&hide both open on a real quote card that is then acted on,
    /// and a beat too short to read the quote is not an establishing beat. (Both used to
    /// build that card *inside* the play function, so the three-second "rest on the
    /// opening frame" was three seconds of an empty box, then a snap. The card is built
    /// up front now.) Everything else opens on an empty stage: nothing to establish.
    static func establish(for kind: WelcomeIllustration) -> Double {
        switch kind {
        case .tag, .starHide: return establishReadSeconds
        default: return establishSeconds
        }
    }

    /// Interpolation helpers for the webview illustrations' scripts.
    static func jsStretch(for kind: WelcomeIllustration) -> String {
        String(format: "%.3f", stretch(for: kind))
    }
    static func jsEstablishMs(for kind: WelcomeIllustration) -> Int {
        Int(establish(for: kind) * 1000)
    }
    static var jsFadeMs: Int { Int(fadeSeconds * 1000) }
    static var jsHoldEndMs: Int { Int(holdEndSeconds * 1000) }
    static var jsRestOpacity: String { String(format: "%.2f", restOpacity) }
}

// MARK: - The curtain, for native illustrations

/// Swift half of the grammar the webviews get from `WelcomeIllustrationHTML.curtain`.
/// One place, so a change to the rhythm cannot land on one side only.
@MainActor
enum WelcomeCurtain {

    /// Run one curtained pass, then return. The caller reports `done` afterwards.
    ///
    ///     dip → open (the opening frame) → fade up → establish → play once
    ///         → hold the finished frame → fade down to rest
    ///
    /// The opening dip is what makes this legible rather than a blink: a resting cell
    /// shows the FINISHED frame of its last pass (that is the still), so getting back to
    /// an opening frame means crossing between two different pictures, and doing it
    /// behind the curtain is the difference between a scene change and a jump cut.
    ///
    /// Every step re-checks cancellation: losing the baton mid-pass has to stop here,
    /// not one hold later.
    static func pass(_ kind: WelcomeIllustration,
                     fade: @escaping (Double, Double) -> Void,
                     open: @escaping () -> Void,
                     play: () async -> Void) async {
        let f = WelcomeTempo.fadeSeconds
        fade(0, f)
        try? await Task.sleep(for: .seconds(f))
        guard !Task.isCancelled else { return }

        open()
        fade(1, f)
        try? await Task.sleep(for: .seconds(f + WelcomeTempo.establish(for: kind)))
        guard !Task.isCancelled else { return }

        await play()
        guard !Task.isCancelled else { return }

        try? await Task.sleep(for: .seconds(WelcomeTempo.holdEndSeconds))
        guard !Task.isCancelled else { return }

        fade(WelcomeTempo.restOpacity, f)
        try? await Task.sleep(for: .seconds(f))
    }
}

// MARK: - Per-illustration watchdog ceiling

extension WelcomeIllustration {
    /// How long a turn may run before the baton gives up waiting for `finish` — a
    /// WATCHDOG, not a schedule. The schedule is the illustration's own beat list,
    /// which now reports when it has played out.
    ///
    /// The switch still carries the AUTHORED play length (original speed, curtain
    /// excluded) because it is the best estimate available, but nothing depends on it
    /// being right any more: it only decides how long a cell sits on its finished frame
    /// in the case where the illustration's own script has failed to speak. That is why
    /// the margin is generous rather than tight — a ceiling that trips during normal
    /// play is the two-clock bug all over again.
    var welcomeTurn: Double {
        let base: Double
        switch self {
        case .none:           return 0
        case .sentimentFan:   base = 11
        case .books:          base = 9
        case .emergentThemes: base = 9
        case .quote:          base = 10
        case .signal:         base = 11
        case .autocode:       base = 12
        case .manualTags:     base = 13
        case .tag:            base = 12   // one play (arc → click → t → type) then hold
        case .starHide:       base = 14   // two beats (star A, hide B) then hold
        case .agentChat:      base = 13   // one play (type → tool call → streamed answer) then hold
        case .ingest:         base = 12   // five rows blink + type, then hold
        case .clips:          base = 14   // menu click → three clips land unit by unit, then hold
        case .miro:           base = 9    // three stickies pop in order, then hold
        }
        let estimate = base * WelcomeTempo.stretch(for: self)
            + WelcomeTempo.establish(for: self)
            + 2 * WelcomeTempo.fadeSeconds
            + WelcomeTempo.holdEndSeconds
        return estimate * 1.4 + 3
    }
}

// MARK: - What each illustration reads from its cell

private struct WelcomeAnimationActiveKey: EnvironmentKey { static let defaultValue = true }

/// How an illustration tells its cell it has played out. A struct wrapping the closure,
/// the way `OpenURLAction` does, so the environment carries a value rather than a
/// naked function type.
struct WelcomeTurnDone {
    private let action: () -> Void
    init(_ action: @escaping () -> Void = {}) { self.action = action }
    func callAsFunction() { action() }
}

private struct WelcomeTurnDoneKey: EnvironmentKey {
    static let defaultValue = WelcomeTurnDone()
}

extension EnvironmentValues {
    /// True when the enclosing cell holds the baton. Illustrations animate only when
    /// this is true (and reduce-motion is off); otherwise they rest on their still.
    var welcomeAnimationActive: Bool {
        get { self[WelcomeAnimationActiveKey.self] }
        set { self[WelcomeAnimationActiveKey.self] = newValue }
    }

    /// Call when the sequence has played its one pass, held its finished frame and
    /// dropped its curtain. The default is a no-op, so an illustration rendered outside
    /// a welcome cell (previews, the degradation lab) needs no special case.
    var welcomeTurnDone: WelcomeTurnDone {
        get { self[WelcomeTurnDoneKey.self] }
        set { self[WelcomeTurnDoneKey.self] = newValue }
    }
}
