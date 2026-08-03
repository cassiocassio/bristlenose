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

// MARK: - Per-illustration turn length

extension WelcomeIllustration {
    /// How long one turn of this illustration runs before the baton passes on.
    /// Continuous loops (shoal/signal/fan/books/quote) are "showcase" lengths — a cut
    /// mid-loop just freezes to the still. AutoCode is a discrete play, so its turn
    /// covers one full run.
    var welcomeTurn: Double {
        switch self {
        case .none:           return 0
        case .sentimentFan:   return 11   // half-speed deal → a full cycle needs a longer turn
        case .books:          return 9
        case .emergentThemes: return 9
        case .quote:          return 10
        case .signal:         return 11
        case .autocode:       return 12
        case .manualTags:     return 13
        case .tag:            return 12   // one play (arc → click → t → type) then hold
        case .starHide:       return 14   // two beats (star A, hide B) then hold
        case .agentChat:      return 13   // one play (type → tool call → streamed answer) then hold
        }
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
