import Testing
@testable import Bristlenose

/// Tests for `RepointDecision.evaluate` — the pure warm-sidecar-pool (Phase A2)
/// policy: can a project switch re-point to the parked sidecar, or must it
/// cold-start?
///
/// This is the only headlessly-testable slice of the warm pool. The Process
/// lifecycle integration in `ServeManager` (park, re-point, eviction, the
/// `/api/health` liveness probe, the `generation` bump) has no Process seam and
/// is covered by human QA — see `docs/private/reviews/warm-sidecar-pool.md` and
/// `.claude/plans/warm-sidecar-pool-implementation.md` §Human-QA boundary.
@Suite("RepointDecision")
struct RepointDecisionTests {

    @Test func coldStart_whenNothingParked() {
        #expect(RepointDecision.evaluate(target: "/p/A", parkedPath: nil, parkedAlive: false) == .coldStart)
    }

    @Test func coldStart_whenParkedIsADifferentProject() {
        #expect(RepointDecision.evaluate(target: "/p/A", parkedPath: "/p/B", parkedAlive: true) == .coldStart)
    }

    @Test func coldStart_whenParkedMatchesButIsDead() {
        // isRunning==false (crashed / self-terminated while parked) must not
        // re-point into a dead port — cold-start instead.
        #expect(RepointDecision.evaluate(target: "/p/A", parkedPath: "/p/A", parkedAlive: false) == .coldStart)
    }

    @Test func repoint_whenParkedMatchesAndAlive() {
        #expect(RepointDecision.evaluate(target: "/p/A", parkedPath: "/p/A", parkedAlive: true) == .repoint)
    }

    /// The brief's named repro at the decision layer: rapid A↔B switching keeps
    /// whichever project you just left warm, so the switch-back always re-points.
    @Test func rapidSwitchBack_repointsBothWays() {
        // Start on A, switch to B → A is now parked. Switching back to A:
        #expect(RepointDecision.evaluate(target: "/p/A", parkedPath: "/p/A", parkedAlive: true) == .repoint)
        // Now on A, B is parked. Switching back to B:
        #expect(RepointDecision.evaluate(target: "/p/B", parkedPath: "/p/B", parkedAlive: true) == .repoint)
    }

    /// Introducing a third distinct project is always a cold start — the single
    /// warm slot only ever holds the immediately-previous project (Option B).
    @Test func thirdDistinctProject_coldStarts() {
        #expect(RepointDecision.evaluate(target: "/p/C", parkedPath: "/p/A", parkedAlive: true) == .coldStart)
    }

    /// Path equality is exact (no normalisation) — a trailing slash is a
    /// different key, so it cold-starts rather than re-pointing to the wrong
    /// sidecar. Documents the contract; callers pass `project.path` verbatim.
    @Test func pathMatchIsExact() {
        #expect(RepointDecision.evaluate(target: "/p/A/", parkedPath: "/p/A", parkedAlive: true) == .coldStart)
    }
}
