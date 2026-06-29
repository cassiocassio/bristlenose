import Foundation

/// Assigns a new project a distinctive identity icon at creation, drawn from the
/// same curated SF Symbol set the manual picker offers (`IconPickerPopover.palette`).
///
/// Two intentionally-conflicting goals, reconciled by a seeded-then-probed draw:
/// - **Seeded** off the project name, so the same name lands the same icon across
///   machines and re-imports (cross-device recognition) in the common case.
/// - **Collision-avoided** against icons already in the sidebar, so no two
///   projects share an icon until the 99-icon set is exhausted.
///
/// `circle` (the un-iconed default ring) is reserved and never drawn — a
/// randomised project must be visually distinct from an opted-out one.
///
/// The pure entry points (`assign`, `seededOrder`) take all inputs explicitly and
/// use no `Date`/`UUID`/global RNG, so they're deterministic and unit-testable.
enum RandomProjectIcon {

    /// UserDefaults / `@AppStorage` key for the Appearance toggle. Default = on.
    static let defaultsKey = "randomProjectIcons"

    /// Whether new projects get an auto-assigned icon. Off → they keep the
    /// default ring and the user assigns icons by hand via the picker.
    static var isEnabled: Bool {
        UserDefaults.standard.object(forKey: defaultsKey) as? Bool ?? true
    }

    /// The drawable pool — every palette symbol except the reserved default ring.
    /// 99 symbols, so the first forced repeat is the 100th project.
    static let pool: [String] = IconPickerPopover.palette
        .map(\.name)
        .filter { $0 != IconPickerPopover.defaultIcon }

    /// Icon for a new project, or `nil` when the feature is off (→ default ring).
    /// `existing` is the set of icons already assigned to other projects.
    static func iconForNewProject(name: String, existing: Set<String>) -> String? {
        guard isEnabled else { return nil }
        return assign(forName: name, existing: existing)
    }

    /// Pure assignment — deterministic for a given `(name, existing)`. Walks the
    /// name-seeded permutation and returns the first icon not already in use;
    /// once the pool is exhausted (≥99 projects) it allows a repeat, returning
    /// the seed's first choice. Exposed for tests.
    static func assign(forName name: String, existing: Set<String>) -> String {
        let order = seededOrder(forName: name)
        if let free = order.first(where: { !existing.contains($0) }) {
            return free
        }
        return order.first ?? IconPickerPopover.defaultIcon
    }

    /// A deterministic permutation of `pool` seeded by the project name. Same
    /// name → same order on every machine (stable hash + stable Fisher–Yates).
    static func seededOrder(forName name: String) -> [String] {
        let key = name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        var rng = SplitMix64(seed: fnv1a(key))
        var items = pool
        var i = items.count - 1
        while i > 0 {
            let j = Int(rng.next() % UInt64(i + 1))
            items.swapAt(i, j)
            i -= 1
        }
        return items
    }

    /// 64-bit FNV-1a over the UTF-8 bytes. Stable across processes and launches —
    /// unlike Swift's `Hashable`, which is seeded with a per-process random value
    /// and would silently break cross-machine determinism.
    static func fnv1a(_ s: String) -> UInt64 {
        var hash: UInt64 = 0xcbf2_9ce4_8422_2325
        for byte in s.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 0x0000_0100_0000_01b3
        }
        return hash
    }
}

/// Tiny deterministic PRNG (SplitMix64) — seeded, pure, no global state. Used to
/// shuffle the icon pool reproducibly from a name hash.
private struct SplitMix64 {
    private var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state = state &+ 0x9e37_79b9_7f4a_7c15
        var z = state
        z = (z ^ (z >> 30)) &* 0xbf58_476d_1ce4_e5b9
        z = (z ^ (z >> 27)) &* 0x94d0_49bb_1331_11eb
        return z ^ (z >> 31)
    }
}
