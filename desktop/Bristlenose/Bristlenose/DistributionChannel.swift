import Foundation

/// How this build reached the user's Mac — used to gate debug affordances
/// (the SQLAdmin `/admin` panel, via the Debug menu) to the direct-notarised
/// **Developer ID** `.dmg` beta channel ONLY.
///
/// **Why not a receipt check.** TestFlight and App Review both run under the
/// StoreKit *sandbox*, so both present a `sandboxReceipt` — a receipt check
/// cannot expose to a TestFlight tester without also exposing to the App Store
/// *reviewer*, who would then see a menu titled "Debug" opening a raw
/// transcript/PII browser (a likely Guideline 2.1 rejection). The only channel
/// we can identify *positively and safely* is our own Developer ID `.dmg`
/// build, via a build-time compilation flag we control end-to-end.
///
/// **Fail-closed by construction.** The App Store / TestFlight path is the
/// `#else` default, so the absence of a positive `DEVELOPER_ID_BETA` marker
/// hides the tools. A misconfigured or unflagged Release build never exposes
/// `/admin` — there is no runtime state (missing receipt, sandbox quirk) that
/// can flip it open.
///
/// **Wiring the beta channel:** set
/// `SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEVELOPER_ID_BETA` in the
/// Developer-ID `.dmg` build configuration ONLY — never in the App Store /
/// TestFlight archive config. Until that config exists the feature is simply
/// dormant everywhere except local `#if DEBUG` builds, which is the safe state.
///
/// See `docs/design-desktop-debug-admin-panel.md`.
enum DistributionChannel {
    case debug                 // local Xcode build (#if DEBUG)
    case developerID           // direct notarised .dmg beta (DEVELOPER_ID_BETA flag)
    case appStoreOrTestFlight  // Release without the beta flag — App Store OR TestFlight

    static let current: DistributionChannel = {
        #if DEBUG
        return .debug
        #elseif DEVELOPER_ID_BETA
        return .developerID
        #else
        return .appStoreOrTestFlight
        #endif
    }()

    /// Debug tools show ONLY in local dev and the Developer-ID beta. Never in an
    /// App Store or TestFlight build (both fall in `.appStoreOrTestFlight`).
    var exposesDebugTools: Bool {
        switch self {
        case .debug, .developerID:
            return true
        case .appStoreOrTestFlight:
            return false
        }
    }
}
