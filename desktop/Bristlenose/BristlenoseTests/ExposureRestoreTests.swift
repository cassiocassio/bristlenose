import Foundation
import Testing
@testable import Bristlenose

/// Exposure must survive a quit, because the permission it accompanies always
/// did — and the UI (the "Turn Off Agent Access" verb, the sidebar antenna)
/// promised that it does.
///
/// The bug these pin, found by using the app on 20 Aug 2026: after any restart
/// `agentAccess` was still true and `exposedProject` was nil, so no handshake
/// was written and every agent got "Bristlenose isn't open" — from a project
/// that was open, selected, serving, and showing an antenna. The only repair
/// was toggling the switch off and on.
struct ExposureRestoreTests {
    private let id = UUID()

    @Test func aStillPermittedProjectIsReExposed() {
        #expect(ExposureRestore.decide(stored: id.uuidString) { $0 == self.id } == .adopt(id))
    }

    /// Revoked while the app was closed — or the project removed outright.
    /// Cleared, not merely skipped: a stored id that survives a failed
    /// validation would re-expose the project the moment access came back for
    /// some *other* reason, which is a permission the researcher never regranted.
    @Test func aRevokedProjectIsClearedNotIgnored() {
        #expect(ExposureRestore.decide(stored: id.uuidString) { _ in false } == .clear)
    }

    @Test func nothingStoredChangesNothing() {
        #expect(ExposureRestore.decide(stored: nil) { _ in true } == .none)
    }

    /// A corrupt default must not be read as "revoked" — that would clear a
    /// key we failed to parse rather than one we proved stale. `.none` leaves
    /// the value alone for a future version to make sense of.
    @Test func anUnparseableValueIsLeftAlone() {
        #expect(ExposureRestore.decide(stored: "not-a-uuid") { _ in true } == .none)
    }

    /// The validator is never consulted when there is nothing to validate —
    /// it reaches into the project index, and a launch with no stored exposure
    /// should not touch it at all.
    @Test func theValidatorIsNotCalledWithoutAStoredID() {
        var asked = false
        _ = ExposureRestore.decide(stored: nil) { _ in asked = true; return true }
        #expect(asked == false)
    }
}
