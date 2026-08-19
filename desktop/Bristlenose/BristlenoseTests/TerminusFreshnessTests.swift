import Testing
import Foundation
@testable import Bristlenose

/// Pins which run a diagnostic headline is allowed to describe.
///
/// `pipeline-events.jsonl` is append-only and is never truncated between runs,
/// so its tail can hold a `run_failed` from hours ago. An attempt refused
/// *before* the lifecycle opens — `outputExists` is the everyday one — writes no
/// terminus of its own, so a naive tail read returns the stale one and it
/// outranks the live stdout carrying the real blocker.
///
/// Observed 19 Aug 2026: the popover headlined "EOF when reading a line" from an
/// eleven-hour-old run while "Output directory already exists" sat below it
/// under *Last output*. The researcher was told about a failure that was not the
/// one standing in their way.
@Suite struct TerminusFreshnessTests {

    private let spawn = Date(timeIntervalSince1970: 1_755_600_000)  // fixed, no clock reads

    private func stamp(_ offset: TimeInterval, fractional: Bool = false) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = fractional
            ? [.withInternetDateTime, .withFractionalSeconds]
            : [.withInternetDateTime]
        return f.string(from: spawn.addingTimeInterval(offset))
    }

    // MARK: - The bug

    @Test func elevenHourOldTerminusIsNotThisAttempt() {
        #expect(!PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(-11 * 3600), spawnedAt: spawn, attachedFromOrphan: false))
    }

    @Test func aTerminusFromThisAttemptIsUsed() {
        // Python writes `started_at` just after we spawn, so it lands slightly
        // in the future relative to our own Date().
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(+0.4), spawnedAt: spawn, attachedFromOrphan: false))
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(+90), spawnedAt: spawn, attachedFromOrphan: false))
    }

    @Test func theGraceWindowAbsorbsOrderingButNotAPreviousRun() {
        // Sub-second slack between our Date() and Python's first write is fine;
        // a minute is not — by then it is a different run.
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(-1), spawnedAt: spawn, attachedFromOrphan: false))
        #expect(!PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(-60), spawnedAt: spawn, attachedFromOrphan: false))
    }

    // MARK: - Permissive on every unknown

    @Test func anAdoptedOrphanKeepsItsOwnTerminus() {
        // Its run legitimately began before we attached — the whole point of the
        // orphan path. Gating it on our attach time would suppress exactly the
        // cause we reconnected to read.
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(-11 * 3600), spawnedAt: spawn, attachedFromOrphan: true))
    }

    @Test func noSpawnTimeMeansDoNotSuppress() {
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: stamp(-11 * 3600), spawnedAt: nil, attachedFromOrphan: false))
    }

    @Test func anUnreadableStampMeansDoNotSuppress() {
        // Showing a stale cause is bad; swallowing a real one is worse.
        for raw in ["", "not-a-date", "2026-13-45T99:99:99Z"] {
            #expect(PipelineRunner.terminusIsCurrentAttempt(
                eventStartedAt: raw, spawnedAt: spawn, attachedFromOrphan: false),
                "\(raw) should be permissive, not suppressive")
        }
        #expect(PipelineRunner.terminusIsCurrentAttempt(
            eventStartedAt: nil, spawnedAt: spawn, attachedFromOrphan: false))
    }

    // MARK: - Both wire spellings

    @Test func bothTimestampSpellingsParse() {
        // Python's `datetime.now(utc).isoformat()` carries microseconds when
        // they are non-zero and omits them when they are not; the committed
        // smoke fixture uses the second spelling.
        #expect(PipelineRunner.parseEventTimestamp("2026-05-01T12:00:30Z") != nil)
        #expect(PipelineRunner.parseEventTimestamp("2026-05-01T12:00:30.123456Z") != nil)
        #expect(PipelineRunner.parseEventTimestamp(stamp(0, fractional: true)) != nil)
        #expect(PipelineRunner.parseEventTimestamp("2026-05-01 12:00:30") == nil)
    }
}
