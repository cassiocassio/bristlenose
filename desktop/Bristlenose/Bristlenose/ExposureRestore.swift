import Foundation

/// Should a stored exposure be re-adopted at launch?
///
/// Exposure has to survive a quit, because the permission it accompanies always
/// did. `Project.agentAccess` lives in the project index, so after a restart the
/// context menu still read "Turn Off Agent Access" and the sidebar still drew an
/// antenna — while `ServeFleet.exposedProject` had silently reset to nil. No
/// manager was `handshakeOwner`, no handshake file existed, and every agent got
/// "Bristlenose isn't open, so there is no study data available." The only
/// repair was toggling Agent Access off and on again.
///
/// One concept must not have two lifetimes. The UI promised persistence; this
/// makes the promise true.
///
/// A pure decision function, like `AgentAccessPolicy` and `HandshakeExposure`:
/// one home for the rule, testable without touching `UserDefaults`.
enum ExposureRestore {

    enum Decision: Equatable {
        /// Re-expose this project — it is still permitted.
        case adopt(UUID)
        /// Forget the stored id: the project no longer holds Agent Access, or
        /// no longer exists. Cleared rather than merely ignored, so a revoked
        /// project cannot be resurrected by a later launch.
        case clear
        /// Nothing stored, or nothing parseable. Leave everything alone.
        case none
    }

    /// - Parameter stillPermitted: does this project currently have Agent
    ///   Access on? A closure rather than a `ProjectIndex`, so the fleet keeps
    ///   knowing nothing about the sidebar model — the same separation
    ///   `agentAccessResolver` maintains.
    ///
    /// Note this is NOT the incidental re-pointing `ServeFleet.setExposed`
    /// warns against. There is nothing to re-point *from* at launch, and
    /// fronting a window still never changes the slot.
    static func decide(stored: String?, stillPermitted: (UUID) -> Bool) -> Decision {
        guard let stored, let id = UUID(uuidString: stored) else { return .none }
        return stillPermitted(id) ? .adopt(id) : .clear
    }
}
