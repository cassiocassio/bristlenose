import Foundation

/// Commits a settled value only when it differs from the last one committed.
///
/// Settings that become sidecar env vars restart the serve when they change
/// (`.bristlenosePrefsChanged`), and a restart reloads the report. So such a
/// setting commits at the end of a gesture — a slider's release, Return, focus
/// loss, leaving the pane, closing the window — never per step, and a commit
/// with nothing changed does nothing (R34: a slider drag restarted the serve
/// once per step, and tabbing through the Azure fields ran a billed validation
/// per field). The same commit can therefore be wired to every exit, in any
/// order.
struct CommitGate<Value: Equatable> {
    private(set) var committed: Value?

    /// Record the value already in effect, without committing it — the first
    /// time only, so a view that appears again cannot overwrite a change that
    /// no exit has committed yet.
    mutating func settle(_ value: Value) {
        if committed == nil { committed = value }
    }

    /// `true` when `value` differs from the last value settled or committed,
    /// and records it. With nothing settled yet, any value is a change.
    mutating func commit(_ value: Value) -> Bool {
        guard committed != value else { return false }
        committed = value
        return true
    }
}
