import Foundation
import Testing
@testable import Bristlenose

// The standby sidecar (docs/design-standby-sidecar.md): the decisions as a pure policy, the
// process protocol against /bin/sh stand-ins (no Python), the pool, and the manager taking one.

private let sh = URL(fileURLWithPath: "/bin/sh")

/// Poll `condition` on the main actor until it holds or `seconds` pass.
@MainActor
private func waitUntil(_ seconds: Double = 8, _ condition: () -> Bool) async -> Bool {
    let deadline = ContinuousClock.now + .seconds(seconds)
    while ContinuousClock.now < deadline {
        if condition() { return true }
        try? await Task.sleep(for: .milliseconds(25))
    }
    return condition()
}

private func scratchFile() -> String {
    NSTemporaryDirectory() + "standby-\(UUID().uuidString).txt"
}

/// Prints the ready line, reads one claim line into `out`, prints a Report line, then lingers.
private func cooperative(writingClaimTo out: String, extraBeforeReady: String = "") -> [String] {
    ["-c", "\(extraBeforeReady) echo '[bristlenose] standby-ready'; read line; echo \"$line\" > '\(out)'; echo 'Report: http://127.0.0.1:1/report/'; exec sleep 60"]
}

@MainActor
private func makeSidecar(_ args: [String], leased: [String] = ["/studies/a"],
                         fingerprint: String = "fp", stamp: SidecarBinaryStamp? = nil) -> StandbySidecar {
    StandbySidecar(executableURL: sh, arguments: args, environment: [:],
                   fingerprint: fingerprint, stamp: stamp, leasedPaths: leased)
}

// MARK: - Policy

@Suite struct StandbyPolicyTests {
    private func spawn(enabled: Bool = true, bundled: Bool = true, leased: Bool = true,
                       has: Bool = false, deaths: Int = 0, since: Duration? = nil) -> Bool {
        StandbyPolicy.shouldSpawn(.init(enabled: enabled, isBundled: bundled, hasLeasedStudy: leased,
                                        hasStandby: has, consecutiveDeaths: deaths, sinceLastDeath: since))
    }

    @Test func startsWhenEverythingIsInPlace() { #expect(spawn()) }
    @Test func neverWhenSwitchedOff() { #expect(!spawn(enabled: false)) }
    @Test func neverOutsideTheBundledSidecar() { #expect(!spawn(bundled: false)) }
    @Test func neverWithNoStudyToOpen() { #expect(!spawn(leased: false)) }
    @Test func neverASecondOne() { #expect(!spawn(has: true)) }
    @Test func stopsAfterRepeatedDeaths() {
        #expect(spawn(deaths: StandbyPolicy.maxConsecutiveDeaths - 1))
        #expect(!spawn(deaths: StandbyPolicy.maxConsecutiveDeaths))
    }
    @Test func nothingRunsBeforeConsentOrOnAnExpiredAlpha() {
        #expect(StandbyPolicy.isAllowed(consentVersion: 2, requiredVersion: 2, alphaExpired: false))
        #expect(StandbyPolicy.isAllowed(consentVersion: 3, requiredVersion: 2, alphaExpired: false))
        #expect(!StandbyPolicy.isAllowed(consentVersion: 0, requiredVersion: 2, alphaExpired: false))
        #expect(!StandbyPolicy.isAllowed(consentVersion: 1, requiredVersion: 2, alphaExpired: false))   // a bumped disclosure
        #expect(!StandbyPolicy.isAllowed(consentVersion: 2, requiredVersion: 2, alphaExpired: true))
    }
    @Test func theLiveGateReadsTheStoredConsentVersion() {
        let suite = UserDefaults(suiteName: "standby-\(UUID().uuidString)")!
        #expect(!StandbyPolicy.isAllowedNow(defaults: suite))                     // never answered
        suite.set(AIConsentView.currentVersion, forKey: "aiConsentVersion")
        #expect(StandbyPolicy.isAllowedNow(defaults: suite) == !AlphaBuild.isExpired())
        suite.set(AIConsentView.currentVersion - 1, forKey: "aiConsentVersion")
        #expect(!StandbyPolicy.isAllowedNow(defaults: suite))
    }
    @Test func leaseRetriesAreBounded() {
        #expect(StandbyPolicy.maxLeaseRetries * Int(StandbyPolicy.leaseRetryInterval.components.seconds) <= 120)
    }
    @Test func waitsAfterADeath() {
        #expect(!spawn(since: .seconds(1)))
        #expect(spawn(since: StandbyPolicy.respawnAfterDeath))
    }

    private func claim(_ phase: StandbySidecar.Phase = .ready, alive: Bool = true, fp: Bool = true,
                       stamp: Bool = true, leased: Bool = true) -> StandbyPolicy.ClaimInputs {
        .init(phase: phase, isAlive: alive, fingerprintMatches: fp, stampMatches: stamp,
              studyLeasedAtSpawn: leased)
    }

    @Test func aReadyCurrentLeasedStandbyIsClaimable() { #expect(StandbyPolicy.canClaim(claim())) }
    @Test func notWhileBooting() { #expect(!StandbyPolicy.canClaim(claim(.booting))) }
    @Test func notOnceClaimedOrDead() {
        #expect(!StandbyPolicy.canClaim(claim(.claimed)))
        #expect(!StandbyPolicy.canClaim(claim(.dead)))
    }
    @Test func notWhenItsProcessHasGone() { #expect(!StandbyPolicy.canClaim(claim(alive: false))) }
    @Test func notWhenTheEnvironmentMoved() { #expect(!StandbyPolicy.canClaim(claim(fp: false))) }
    @Test func notWhenTheBinaryChanged() { #expect(!StandbyPolicy.canClaim(claim(stamp: false))) }
    @Test func notForAStudyLeasedAfterItSpawned() { #expect(!StandbyPolicy.canClaim(claim(leased: false))) }

    @Test func onlyAMovedEnvironmentOrBinaryMakesItStale() {
        #expect(StandbyPolicy.isStale(claim(fp: false)))
        #expect(StandbyPolicy.isStale(claim(stamp: false)))
        #expect(!StandbyPolicy.isStale(claim(leased: false)))   // wrong study, not a wrong standby
        #expect(!StandbyPolicy.isStale(claim(.booting)))
    }

    @Test func theKillSwitchIsOnByDefaultAndReadsBothSwitches() {
        let suite = UserDefaults(suiteName: "standby-\(UUID().uuidString)")!
        #expect(StandbyPolicy.isEnabled(defaults: suite, environment: [:]))
        suite.set(false, forKey: StandbyPolicy.defaultsKey)
        #expect(!StandbyPolicy.isEnabled(defaults: suite, environment: [:]))
        let fresh = UserDefaults(suiteName: "standby-\(UUID().uuidString)")!
        #expect(!StandbyPolicy.isEnabled(defaults: fresh, environment: ["BRISTLENOSE_STANDBY": "0"]))
    }
}

// MARK: - The process protocol

@MainActor
@Suite(.serialized) struct StandbySidecarTests {
    @Test func bootsThenSaysReady() async throws {
        let s = makeSidecar(cooperative(writingClaimTo: scratchFile()))
        try s.start()
        #expect(s.phase == .booting)
        #expect(await waitUntil { s.phase == .ready })
        s.stop()
    }

    @Test func aClaimReachesTheProcessAndItsLinesReachTheSink() async throws {
        let out = scratchFile()
        let s = makeSidecar(cooperative(writingClaimTo: out))
        try s.start()
        #expect(await waitUntil { s.phase == .ready })
        var lines: [String] = []
        let ok = s.claim(projectPath: "/studies/a", mcpToken: "tok-1",
                         sink: { lines.append($0) }, onTerminated: { _ in })
        #expect(ok)
        #expect(s.phase == .claimed)
        #expect(await waitUntil { lines.contains { $0.hasPrefix("Report:") } })
        let claim = try String(contentsOfFile: out, encoding: .utf8)
        let json = try JSONSerialization.jsonObject(with: Data(claim.utf8)) as? [String: Any]
        #expect(json?["v"] as? Int == 1)
        #expect(json?["project"] as? String == "/studies/a")
        #expect(json?["mcp_token"] as? String == "tok-1")
        s.process.terminate()
    }

    @Test func aClaimedProcessIsNeverStoppedByTheStandby() async throws {
        let s = makeSidecar(cooperative(writingClaimTo: scratchFile()))
        try s.start()
        #expect(await waitUntil { s.phase == .ready })
        _ = s.claim(projectPath: "/studies/a", mcpToken: "", sink: { _ in }, onTerminated: { _ in })
        s.stop()
        try? await Task.sleep(for: .milliseconds(300))
        #expect(s.process.isRunning)
        s.process.terminate()
    }

    @Test func linesBeforeTheClaimAreHeldAndReplayedOnRequest() async throws {
        let s = makeSidecar(cooperative(writingClaimTo: scratchFile(), extraBeforeReady: "echo early-noise;"))
        try s.start()
        #expect(await waitUntil { s.phase == .ready })
        var lines: [String] = []
        #expect(s.claim(projectPath: "/studies/a", mcpToken: "", sink: { lines.append($0) }, onTerminated: { _ in }))
        #expect(!lines.contains("early-noise"))   // not inside claim: the manager has not adopted yet
        s.replayHeld()
        #expect(lines.first == "early-noise")
        s.process.terminate()
    }

    @Test func aStandbyThatDiesBeforeReadyIsDeadAndTellsThePool() async throws {
        let s = makeSidecar(["-c", "exit 3"])
        var told = false
        s.onChange = { _ in told = true }
        try s.start()
        #expect(await waitUntil { s.phase == .dead })
        #expect(told)
    }

    @Test func aDeadStandbyCannotBeClaimed() async throws {
        let s = makeSidecar(["-c", "echo '[bristlenose] standby-ready'; exit 0"])
        try s.start()
        #expect(await waitUntil { s.phase == .dead || s.phase == .ready })
        _ = await waitUntil { s.phase == .dead }
        let ok = s.claim(projectPath: "/studies/a", mcpToken: "", sink: { _ in }, onTerminated: { _ in })
        #expect(!ok)
        #expect(s.phase == .dead)
    }

    @Test func aDeathAfterTheClaimGoesToTheManagersRoute() async throws {
        let s = makeSidecar(["-c", "echo '[bristlenose] standby-ready'; read line; exit 7"])
        try s.start()
        #expect(await waitUntil { s.phase == .ready })
        var status: Int32?
        #expect(s.claim(projectPath: "/studies/a", mcpToken: "", sink: { _ in }, onTerminated: { status = $0 }))
        #expect(await waitUntil { status != nil })
        #expect(status == 7)
    }

    @Test func stopEndsAnUnclaimedStandby() async throws {
        let s = makeSidecar(["-c", "echo '[bristlenose] standby-ready'; exec sleep 60"])
        try s.start()
        #expect(await waitUntil { s.phase == .ready })
        s.stop()
        #expect(await waitUntil(6) { !s.process.isRunning })
        #expect(s.phase == .dead)
    }

    @Test func leasedPathsAreComparedStandardised() {
        let s = makeSidecar(["-c", "exit 0"], leased: ["/studies/a/../a"])
        #expect(s.isLeased("/studies/a"))
        #expect(!s.isLeased("/studies/b"))
    }
}

// MARK: - The pool

@MainActor
@Suite(.serialized) struct StandbyPoolTests {
    private func pool(leased: [String] = ["/studies/a"], bundled: Bool = true,
                      script: [String], enabled: Bool = true,
                      environment: [String: String] = ["K": "1"]) -> StandbyPool {
        let p = StandbyPool()
        p.configure(
            mode: { bundled ? .bundled(path: sh) : .external(port: 1) },
            leasedPaths: { leased },
            environmentFor: { _ in environment },
            stampReader: { _ in nil },
            isEnabled: { enabled },
            arguments: script)
        return p
    }
    private static let ready = ["-c", "echo '[bristlenose] standby-ready'; read line; exec sleep 60"]

    @Test func startsOneAndOnlyOne() async {
        let p = pool(script: Self.ready)
        p.startIfWanted()
        let first = p.current
        p.startIfWanted()
        #expect(first != nil && p.current === first)
        p.shutdown()
    }

    @Test func withoutConsentItStartsNothingAndCountsNoFailure() {
        let p = pool(script: Self.ready, enabled: false)    // the app's gate answers "not yet"
        p.startIfWanted()
        #expect(p.current == nil)
        #expect(p.consecutiveDeaths == 0)
    }

    @Test func startsNothingWithoutAStudyOrOutsideTheBundleOrWhenOff() {
        for p in [pool(leased: [], script: Self.ready),
                  pool(bundled: false, script: Self.ready),
                  pool(script: Self.ready, enabled: false)] {
            p.startIfWanted()
            #expect(p.current == nil)
        }
    }

    @Test func aStudyItCanReadClaimsIt() async {
        let p = pool(script: Self.ready)
        p.startIfWanted()
        guard let s = p.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { s.phase == .ready })
        let fp = ServeEnvStaleness.fingerprint(["K": "1"])
        #expect(p.claimable(projectPath: "/studies/a", fingerprint: fp, stamp: nil) === s)
        #expect(p.claimable(projectPath: "/studies/other", fingerprint: fp, stamp: nil) == nil)
        p.shutdown()
    }

    @Test func aMovedEnvironmentMakesItStaleAndReplacesIt() async {
        let p = pool(script: Self.ready)
        p.startIfWanted()
        guard let s = p.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { s.phase == .ready })
        let other = ServeEnvStaleness.fingerprint(["K": "2"])
        #expect(p.claimable(projectPath: "/studies/a", fingerprint: other, stamp: nil) == nil)
        #expect(p.current == nil)
        p.shutdown()
    }

    @Test func aStudyLeasedAfterTheStandbySpawnedReplacesIt() async {
        var leased = ["/studies/a"]
        let p = StandbyPool()
        p.configure(mode: { .bundled(path: sh) }, leasedPaths: { leased },
                    environmentFor: { _ in ["K": "1"] }, stampReader: { _ in nil }, arguments: Self.ready)
        p.startIfWanted()
        guard let s = p.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { s.phase == .ready })
        leased = ["/studies/a", "/studies/b"]            // b's lease came after the spawn
        let fp = ServeEnvStaleness.fingerprint(["K": "1"])
        #expect(p.claimable(projectPath: "/studies/b", fingerprint: fp, stamp: nil) == nil)
        #expect(p.current == nil)                          // replaced by one that will cover b
        p.shutdown()
    }

    @Test func aChangedEnvironmentRecyclesTheWaitingOne() async {
        var env = ["K": "1"]
        let p = StandbyPool()
        p.configure(mode: { .bundled(path: sh) }, leasedPaths: { ["/studies/a"] },
                    environmentFor: { _ in env }, stampReader: { _ in nil }, arguments: Self.ready)
        p.startIfWanted()
        #expect(p.current != nil)
        env = ["K": "2"]
        p.environmentChanged()
        #expect(p.current == nil)
        p.shutdown()
    }

    @Test func aClaimClearsTheSlotAndTheDeathCount() async {
        let p = pool(script: Self.ready)
        p.startIfWanted()
        guard let s = p.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { s.phase == .ready })
        #expect(s.claim(projectPath: "/studies/a", mcpToken: "", sink: { _ in }, onTerminated: { _ in }))
        p.didClaim(s)
        #expect(p.current == nil)
        #expect(p.consecutiveDeaths == 0)
        s.process.terminate()
        p.shutdown()
    }

    @Test func deathsAreCountedAndNotRetriedAtOnce() async {
        let p = pool(script: ["-c", "exit 2"])
        p.startIfWanted()
        #expect(await waitUntil { p.consecutiveDeaths == 1 })
        p.startIfWanted()                       // inside the wait after a death: refused
        #expect(p.current == nil)
        p.shutdown()
    }
}

// MARK: - The manager takes one

@MainActor
@Suite(.serialized) struct ServeManagerStandbyTests {
    private func readyPool() async -> (StandbyPool, StandbySidecar, String)? {
        let out = scratchFile()
        let p = StandbyPool()
        p.configure(mode: { .bundled(path: sh) }, leasedPaths: { ["/studies/a"] },
                    environmentFor: { _ in ["K": "1"] }, stampReader: { _ in nil },
                    arguments: cooperative(writingClaimTo: out, extraBeforeReady: "echo early-noise;"))
        p.startIfWanted()
        guard let s = p.current else { return nil }
        // A hang bound, not a speed claim: the macos-26 runner took 16 s to get a `/bin/sh`
        // stand-in to its ready line under load (7 Nov 2026), and an 8 s wait read that as "none".
        guard await waitUntil(30, { s.phase == .ready }) else { return nil }
        return (p, s, out)
    }

    @Test func adoptsTheProcessSendsTheTokenAndReplaysEarlyLines() async throws {
        guard let (pool, standby, out) = await readyPool() else { Issue.record("no ready standby"); return }
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        m.standbyPool = pool
        m.instance.spawnedEnvFingerprint = ServeEnvStaleness.fingerprint(["K": "1"])
        let adopted = m.claimStandby(projectPath: "/studies/a", mcpToken: "tok-9")
        #expect(adopted === standby)
        #expect(pool.current == nil)
        // What start() does next, in the same step.
        m.instance.process = adopted?.process
        adopted?.replayHeld()
        #expect(m.outputLines.contains("early-noise"))
        #expect(await waitUntil { (try? String(contentsOfFile: out, encoding: .utf8))?.contains("tok-9") == true })
        adopted?.process.terminate()
        pool.shutdown()
    }

    @Test func aStaleEnvironmentColdSpawnsInstead() async {
        guard let (pool, _, _) = await readyPool() else { Issue.record("no ready standby"); return }
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        m.standbyPool = pool
        m.instance.spawnedEnvFingerprint = ServeEnvStaleness.fingerprint(["K": "changed"])
        #expect(m.claimStandby(projectPath: "/studies/a", mcpToken: "") == nil)
        pool.shutdown()
    }

    @Test func aStudyOutsideTheLeasedSetColdSpawnsInstead() async {
        guard let (pool, standby, _) = await readyPool() else { Issue.record("no ready standby"); return }
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        m.standbyPool = pool
        m.instance.spawnedEnvFingerprint = ServeEnvStaleness.fingerprint(["K": "1"])
        #expect(m.claimStandby(projectPath: "/studies/added-later", mcpToken: "") == nil)
        #expect(pool.current === standby)        // still there for a study it can read
        pool.shutdown()
    }

    @Test func noPoolIsTheOldPath() {
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        #expect(m.claimStandby(projectPath: "/studies/a", mcpToken: "") == nil)
    }
}

// MARK: - start() itself

@MainActor
@Suite(.serialized) struct ServeManagerStartClaimsStandbyTests {
    @Test func startAdoptsAReadyStandbyAndSendsItTheStudy() async throws {
        let out = scratchFile()
        let mode = SidecarMode.bundled(path: sh)
        let pool = StandbyPool()
        pool.configure(mode: { mode }, leasedPaths: { ["/studies/a"] },
                       arguments: cooperative(writingClaimTo: out))
        pool.startIfWanted()
        guard let standby = pool.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { standby.phase == .ready })

        let m = ServeManager(resolvedMode: .success(mode))
        m.standbyPool = pool
        m.mcpTokenResolver = { _, _ in "tok-start" }
        m.start(projectPath: "/studies/a")

        #expect(m.state == .starting)
        #expect(m.instance.process === standby.process)           // adopted, not spawned
        #expect(pool.current == nil)                               // the slot was taken
        #expect(await waitUntil {
            (try? String(contentsOfFile: out, encoding: .utf8))?.contains("tok-start") == true
        })
        m.stop()
        pool.shutdown()
    }

    /// The review's blocker: nothing owned the adopted StandbySidecar, whose reader and exit
    /// handler hold it weakly, so after `start()` returned no line and no exit reached the manager.
    @Test func theAdoptedStandbyStaysAliveAndItsLinesReachTheManager() async throws {
        let mode = SidecarMode.bundled(path: sh)
        let pool = StandbyPool()
        pool.configure(mode: { mode }, leasedPaths: { ["/studies/a"] },
                       arguments: cooperative(writingClaimTo: scratchFile(), extraBeforeReady: ""))
        pool.startIfWanted()
        weak var weakStandby: StandbySidecar?
        do {
            guard let standby = pool.current else { Issue.record("no standby"); return }
            weakStandby = standby
            #expect(await waitUntil { standby.phase == .ready })
        }
        let m = ServeManager(resolvedMode: .success(mode))
        m.standbyPool = pool
        m.mcpTokenResolver = { _, _ in "t" }
        m.start(projectPath: "/studies/a")
        // Every test-local reference is gone; the pool let go at the claim. Only the manager holds it.
        #expect(weakStandby != nil)
        #expect(await waitUntil { m.outputLines.contains { $0.hasPrefix("Report:") } })
        m.stop()
        #expect(await waitUntil { weakStandby == nil })    // and it is released with its process
        pool.shutdown()
    }

    @Test func anAdoptedStandbyThatDiesReachesTheManagersFailure() async throws {
        let mode = SidecarMode.bundled(path: sh)
        let pool = StandbyPool()
        pool.configure(mode: { mode }, leasedPaths: { ["/studies/a"] },
                       arguments: ["-c", "echo '[bristlenose] standby-ready'; read line; exit 7"])
        pool.startIfWanted()
        do {
            guard let standby = pool.current else { Issue.record("no standby"); return }
            #expect(await waitUntil { standby.phase == .ready })
        }
        let m = ServeManager(resolvedMode: .success(mode))
        m.standbyPool = pool
        m.mcpTokenResolver = { _, _ in "t" }
        m.start(projectPath: "/studies/a")
        #expect(await waitUntil(3) { if case .failed = m.state { return true } else { return false } })
        pool.shutdown()
    }

    /// A claim is only possible while `start()`'s environment fingerprints like the pool's. Today
    /// that holds because the one thing `start()` adds is underscore-prefixed (ignored); a future
    /// plain variable added there would silently disable the standby for good.
    @Test func startsEnvironmentFingerprintsLikeThePoolsOwn() async throws {
        let mode = SidecarMode.bundled(path: sh)
        let m = ServeManager(resolvedMode: .success(mode))
        m.mcpTokenResolver = { _, _ in "t" }
        m.start(projectPath: "/studies/a")
        #expect(m.instance.spawnedEnvFingerprint
                == ServeEnvStaleness.fingerprint(BristlenoseShared.childEnvironment(for: mode)))
        m.stop()
    }

    @Test func startWithAStandbyForAnotherEnvironmentSpawnsItsOwn() async throws {
        let mode = SidecarMode.bundled(path: sh)
        let pool = StandbyPool()
        pool.configure(mode: { mode }, leasedPaths: { ["/studies/a"] },
                       environmentFor: { _ in ["STALE": "1"] },
                       arguments: cooperative(writingClaimTo: scratchFile()))
        pool.startIfWanted()
        guard let standby = pool.current else { Issue.record("no standby"); return }
        #expect(await waitUntil { standby.phase == .ready })

        let m = ServeManager(resolvedMode: .success(mode))
        m.standbyPool = pool
        m.mcpTokenResolver = { _, _ in "t" }
        m.start(projectPath: "/studies/a")
        #expect(m.instance.process !== standby.process)
        m.stop()
        pool.shutdown()
    }
}
