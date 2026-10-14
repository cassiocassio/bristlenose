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
            isExposed: false) == .nothing)
    }

    @Test func theInstanceOnScreenRestartsNow() {
        #expect(ServeEnvStaleness.action(
            project: Self.onScreen, isRunning: true, isFronted: true,
            isExposed: false) == .restartNow)
    }

    /// The exception that makes lazy safe. A background sidecar is harmless
    /// while nobody can read it. Since 20 Aug 2026 scope is PLURAL, so this
    /// is asked per project rather than against one designated winner — and
    /// every exposed project earns the eager restart, because any of them can
    /// go on serving real names after anonymise is turned on, unattended,
    /// until someone fronts its window.
    @Test func theExposedInstanceRestartsNowEvenWithNoOneLookingAtIt() {
        #expect(ServeEnvStaleness.action(
            project: Self.exposed, isRunning: true, isFronted: false,
            isExposed: true) == .restartNow)
    }

    /// The reason lazy was chosen over restart-all: no gratuitous cold SPA
    /// remounts in windows the researcher is not looking at.
    @Test func anUnexposedBackgroundInstanceWaitsUntilSomeoneLooksAtIt() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: true, isFronted: false,
            isExposed: false) == .restartOnNextFront)
    }

    /// The arm that was rejected: fronted-only would have left this one stale
    /// and silent. It must not be `.nothing`.
    @Test func aBackgroundInstanceIsNeverLeftAlone() {
        let action = ServeEnvStaleness.action(
            project: Self.background, isRunning: true, isFronted: false,
            isExposed: false)
        #expect(action != .nothing)
        #expect(action == .restartOnNextFront)
    }

    /// Diagnostics off withdraws screen reading. A background serve still
    /// reading shared screens restarts now: the harm (a job OCR'ing
    /// participants' screens) runs whether or not anyone is looking, which is
    /// the same reason the exposed instance goes now under Anonymise.
    @Test func aBackgroundInstanceReadingWithdrawnScreensRestartsNow() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: true, isFronted: false,
            isExposed: false, readsWithdrawnScreens: true) == .restartNow)
    }

    /// …and only that. Not running is still nothing to do.
    @Test func aStoppedInstanceThatReadScreensNeedsNothing() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: false, isFronted: false,
            isExposed: false, readsWithdrawnScreens: true) == .nothing)
    }

    /// A booting serve was spawned seconds ago with the old env. Spawned
    /// reading screens, it restarts now rather than boot and read; otherwise a
    /// booting serve keeps the old answer for every other preference.
    @Test func aStartingInstanceReadingWithdrawnScreensRestartsNow() {
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: false, isFronted: false,
            isExposed: false, readsWithdrawnScreens: true, isStarting: true) == .restartNow)
        #expect(ServeEnvStaleness.action(
            project: Self.background, isRunning: false, isFronted: true,
            isExposed: true, readsWithdrawnScreens: false, isStarting: true) == .nothing)
    }

    @Test func frontedAndExposedIsStillJustOneRestart() {
        #expect(ServeEnvStaleness.action(
            project: Self.exposed, isRunning: true, isFronted: true,
            isExposed: true) == .restartNow)
    }
}
