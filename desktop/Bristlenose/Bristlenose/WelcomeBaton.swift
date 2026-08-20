import SwiftUI

// MARK: - Welcome animation baton
//
// Only ONE welcome cell animates at a time, so the "focus of interest" travels
// the golden spiral instead of every cell competing (design-welcome-studytools-
// illustrations.md). A cell that holds the baton animates; everyone else rests on
// their reduce-motion still. When a turn ends the baton passes to the next cell in
// spiral order that has something to animate. Strict one-at-a-time, all cells.

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
    private var reduceMotion = false
    private var driver: Task<Void, Never>?

    init(restBeat: Double = 0.6) { self.restBeat = restBeat }

    func isActive(_ slot: WelcomeSlot) -> Bool { holder == slot }

    /// A cell reports whether it currently has something to animate and how long one
    /// turn should run before the baton passes on. Cheap to call on every appear /
    /// slot change — the running driver reads it live.
    func report(_ slot: WelcomeSlot, wants w: Bool, turn t: Double) {
        wants[slot] = w
        turn[slot] = t
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
                guard let next = Self.nextHolder(after: self.holder, wants: self.wants) else {
                    self.holder = nil                              // nobody wants it — idle poll
                    try? await Task.sleep(for: .seconds(0.3))
                    continue
                }
                self.holder = next
                try? await Task.sleep(for: .seconds(self.turn[next] ?? 9))
                if Task.isCancelled { break }
                self.holder = nil                                  // a beat of stillness between turns
                try? await Task.sleep(for: .seconds(self.restBeat))
            }
        }
    }

    func stop() {
        driver?.cancel(); driver = nil; holder = nil
    }

    /// Pure: the next slot after `current` (spiral order, wrapping) that wants the
    /// baton; nil if nobody does. Unit-tested in `WelcomeBatonTests`.
    static func nextHolder(after current: WelcomeSlot?, wants: [WelcomeSlot: Bool]) -> WelcomeSlot? {
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
/// the ×1.3 they were hand-tuned to before the group knob existed. Every play
/// additionally rests on its opening frame for `leadInSeconds` and on its
/// finished frame for `holdEndSeconds` before looping or handing the baton on
/// (holds are absolute — they don't scale). `welcomeTurn` derives from the
/// same numbers, so turn lengths track any tweak here.
enum WelcomeTempo {
    static let speed: Double = 0.6
    static var stretch: Double { 1.0 / speed }
    static let leadInSeconds: Double = 3.0
    static let holdEndSeconds: Double = 3.0

    /// Local multiplier on top of the group tempo (individual tweak point).
    static func pace(_ kind: WelcomeIllustration) -> Double {
        switch kind {
        case .autocode, .manualTags, .tag, .starHide, .agentChat: return 1.3
        default: return 1.0
        }
    }

    /// Effective duration multiplier for one illustration.
    static func stretch(for kind: WelcomeIllustration) -> Double { stretch * pace(kind) }

    /// Interpolation helpers for the webview illustrations' scripts.
    static func jsStretch(for kind: WelcomeIllustration) -> String {
        String(format: "%.3f", stretch(for: kind))
    }
    static var jsLeadMs: Int { Int(leadInSeconds * 1000) }
}

// MARK: - Per-illustration turn length

extension WelcomeIllustration {
    /// How long one turn of this illustration runs before the baton passes on.
    /// The switch carries the AUTHORED play length (original speed, holds
    /// excluded); the shipped turn stretches with `WelcomeTempo` and adds the
    /// lead-in + end holds, so tempo tweaks never orphan the turn lengths.
    /// Continuous loops (shoal/signal/fan/books/quote) are "showcase" lengths —
    /// a cut mid-loop just freezes to the still.
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
        return base * WelcomeTempo.stretch(for: self)
            + WelcomeTempo.leadInSeconds + WelcomeTempo.holdEndSeconds
    }
}

// MARK: - Environment flag each illustration reads

private struct WelcomeAnimationActiveKey: EnvironmentKey { static let defaultValue = true }

extension EnvironmentValues {
    /// True when the enclosing cell holds the baton. Illustrations animate only when
    /// this is true (and reduce-motion is off); otherwise they show their still.
    var welcomeAnimationActive: Bool {
        get { self[WelcomeAnimationActiveKey.self] }
        set { self[WelcomeAnimationActiveKey.self] = newValue }
    }
}
