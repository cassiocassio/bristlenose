import Foundation

/// State holder for the sessions popover. Thin by design: `SessionsAPI.load`
/// owns the identity discipline (read-at-request-time, post-await port
/// re-check), so all this adds is *what to do with nil* — a superseded fetch
/// keeps the previous state rather than publishing anything.
///
/// `refresh` is called on every popover open (the decided refresh trigger: it
/// closes both the stale-after-a-run case and most of the sidecar-boot window
/// with one mechanism) and takes the identity provider rather than a
/// `ServeManager`, so tests need no serve machinery.
@MainActor
final class SessionsPopoverModel: ObservableObject {

    @Published private(set) var state: SessionsLoadState = .loading

    func refresh(identity provider: @MainActor @Sendable @escaping () -> (port: Int, token: String)?) async {
        // Show the spinner only when there is nothing better on screen — a
        // re-open over an already-loaded list must not flash back to loading
        // for a sub-second localhost round trip.
        if case .loaded = state {} else { state = .loading }

        if let result = await SessionsAPI.load(identity: provider) {
            state = result
        }
        // nil = overtaken by a project switch: keep whatever was showing; the
        // switch itself triggers the next refresh with the new identity.
    }
}
