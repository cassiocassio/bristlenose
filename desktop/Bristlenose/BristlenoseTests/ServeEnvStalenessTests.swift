import Foundation
import Testing
@testable import Bristlenose

/// The prefs/consent fan-out — the fork Stage 3b actually turns on.
@Suite("ServeEnvStaleness")
struct ServeEnvStalenessTests {

    private static let onScreen = UUID()
    private static let exposed = UUID()
    private static let background = UUID()

    @Test func aStoppedInstanceNeedsNothing() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: false, isFronted: false,
            exposedProject: nil) == .nothing)
    }

    @Test func theInstanceOnScreenRestartsNow() {
        #expect(ServeEnvStaleness.action(
            project: Self.onScreen, isRunning: true, isFronted: true,
            exposedProject: nil) == .restartNow)
    }

    /// The exception that makes lazy safe. A background sidecar is harmless
    /// while nobody can read it — and exactly one project is readable by an
    /// external agent at a time. Turn anonymise on, and that one must not keep
    /// serving real names because nobody happens to be looking at its window.
    @Test func theExposedInstanceRestartsNowEvenWithNoOneLookingAtIt() {
        #expect(ServeEnvStaleness.action(
            project: Self.exposed, isRunning: true, isFronted: false,
            exposedProject: Self.exposed) == .restartNow)
    }

    /// The reason lazy was chosen over restart-all: no gratuitous cold SPA
    /// remounts in windows the researcher is not looking at.
    @Test func anUnexposedBackgroundInstanceWaitsUntilSomeoneLooksAtIt() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: true, isFronted: false,
            exposedProject: Self.exposed) == .restartOnNextFront)
    }

    /// The arm that was rejected: fronted-only would have left this one stale
    /// and silent. It must not be `.nothing`.
    @Test func aBackgroundInstanceIsNeverLeftAlone() {
        let action = ServeEnvStaleness.action(
            project: Self.background, isRunning: true, isFronted: false,
            exposedProject: nil)
        #expect(action != .nothing)
        #expect(action == .restartOnNextFront)
    }

    @Test func frontedAndExposedIsStillJustOneRestart() {
        #expect(ServeEnvStaleness.action(
            project: Self.exposed, isRunning: true, isFronted: true,
            exposedProject: Self.exposed) == .restartNow)
    }
}
