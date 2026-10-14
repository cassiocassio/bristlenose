import Foundation
import Testing
@testable import Bristlenose

/// The wiring, not the decisions.
///
/// `ServeReaping` and `ServeEnvStaleness` had tests from the day they were
/// written and were called from nowhere — a green suite asserting functions
/// nobody ran. These pin that the fleet actually acts on them, which is the
/// difference between a decision and a behaviour.
@Suite("ServeFleet lifecycle wiring")
@MainActor
struct ServeFleetLifecycleTests {

    private static let a = UUID()
    private static let b = UUID()

    @Test func aStudyWithNoWindowIsNotReapedImmediately() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)

        fleet.sweep(shownProjects: [])

        // Grace, not instant teardown: closing the last window and reopening it
        // must not cost a multi-second cold boot.
        #expect(fleet.managers[Self.a] != nil)
        #expect(fleet.isRunning(Self.a))
    }

    @Test func memoryPressureReapsWithoutWaiting() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)

        fleet.sweep(shownProjects: [], memoryPressure: true)

        #expect(fleet.managers[Self.a] == nil)
    }

    @Test func aSweepNeverTouchesAStudyThatStillHasAWindow() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)
        fleet.manager(for: Self.b).instance.state = .running(port: 5001)

        fleet.sweep(shownProjects: [Self.a, Self.b], memoryPressure: true)

        #expect(fleet.runningProjects == [Self.a, Self.b])
    }

    /// The sweep is a function of the roster, so calling it repeatedly with the
    /// same input must not accumulate anything. This is what makes a missed
    /// `.onDisappear` survivable rather than fatal.
    @Test func repeatedSweepsAreIdempotent() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)
        for _ in 0..<5 { fleet.sweep(shownProjects: [Self.a]) }
        #expect(fleet.runningProjects == [Self.a])
    }

    /// Discard must STOP, not merely forget. Forgetting a running manager
    /// strands ~140 MB and a live port serving a study that was just deleted.
    @Test func discardingAProjectStopsItsSidecar() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)

        fleet.discard(Self.a)

        #expect(fleet.managers[Self.a] == nil)
        #expect(manager.runningPort == nil, "discard left the sidecar running")
    }

    /// The prefs/consent fan-out. Asserts the ROUTING, not the restart: the
    /// restart itself is async (`shutdown` then `start`), so an immediate state
    /// read would be testing the clock. What is new here is which instance is
    /// told to go now and which is told to wait.
    @Test func anEnvChangeDefersABackgroundInstanceButNotTheExposedOne() {
        let fleet = ServeFleet()
        for (id, port) in [(Self.a, 5000), (Self.b, 5001)] {
            let m = fleet.manager(for: id)
            m.instance.state = .running(port: port)
            m.instance.currentProjectPath = "/p/\(id)"
        }
        fleet.setHandshakeProjectPathsForTest(["/p/\(Self.a)"])
        fleet.frontedProject = nil

        fleet.applyEnvChange()

        // `a` is reachable by an agent with nobody watching, so it goes now —
        // the exception that makes lazy safe. Turn Anonymise on and it must not
        // keep serving real names out of a window no one is looking at.
        #expect(fleet.staleProjects.contains(Self.a) == false)
        // `b` is only reachable by looking at it, so it waits rather than
        // costing a cold report remount nobody asked for.
        #expect(fleet.staleProjects.contains(Self.b))
    }

    /// Turning Diagnostics OFF must reach every serve still reading shared
    /// screens, not only the fronted one. Before this, `b` — a background serve
    /// spawned with `BRISTLENOSE_SCREEN_TEXT=1` — was merely marked stale and
    /// went on reading participants' screens until someone fronted its window.
    /// The restart is asserted by its effect, not by the absence of a stale
    /// mark: each manager is resolved to an external server on `restartPort`,
    /// so a real restart (shutdown, then start) lands on that port without
    /// spawning anything, and a serve left alone keeps its fake one.
    private static let restartPort = 9_999

    private static func externalFleet(_ store: ScreenReadingStore? = nil) -> ServeFleet {
        ServeFleet(screenReading: store ?? ScreenReadingStore(), makeManager: {
            ServeManager(resolvedMode: .success(.external(port: restartPort)))
        })
    }

    /// Wait (by suspending, so the restart's Task can run) for a state.
    private func settle(_ m: ServeManager, to state: ServeState) async {
        for _ in 0..<100 where m.state != state {
            try? await Task.sleep(for: .milliseconds(20))
        }
    }

    @Test func diagnosticsOffRestartsEveryServeStillReadingScreens() async throws {
        let suite = "ServeFleetLifecycleTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(false, forKey: DiagnosticsPreference.key)

        let fleet = Self.externalFleet()
        for (id, port, reads) in [(Self.a, 5000, false), (Self.b, 5001, true)] {
            let m = fleet.manager(for: id)
            m.instance.state = .running(port: port)
            m.instance.currentProjectPath = "/p/\(id)"
            m.instance.spawnedReadsScreens = reads
        }
        fleet.frontedProject = nil

        fleet.applyEnvChange(defaults: defaults)
        let b = fleet.manager(for: Self.b)
        await settle(b, to: .running(port: Self.restartPort))

        #expect(b.state == .running(port: Self.restartPort),
                "a background serve kept reading screens after Diagnostics went off")
        #expect(fleet.staleProjects.contains(Self.b) == false)
        #expect(b.spawnedReadsScreens == false, "the restarted serve still claims to read screens")
        // Narrow: a serve that never read screens keeps the lazy restart.
        #expect(fleet.manager(for: Self.a).state == .running(port: 5000))
        #expect(fleet.staleProjects.contains(Self.a))
    }

    /// The boot gap: `spawnedReadsScreens` is set at spawn, seconds before
    /// `.running`. A serve still starting when Diagnostics goes off was spawned
    /// with screen text and must be restarted too, not left to boot and read.
    @Test func diagnosticsOffRestartsAServeStillStarting() async throws {
        let suite = "ServeFleetLifecycleTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(false, forKey: DiagnosticsPreference.key)

        let fleet = Self.externalFleet()
        let b = fleet.manager(for: Self.b)
        b.instance.state = .starting
        b.instance.currentProjectPath = "/p/b"
        b.instance.spawnedReadsScreens = true
        fleet.frontedProject = nil

        fleet.applyEnvChange(defaults: defaults)
        await settle(b, to: .running(port: Self.restartPort))

        #expect(b.state == .running(port: Self.restartPort),
                "a serve booting with screen text was left to finish booting and read")
        // The restart's own start records what it spawned: nothing reads now.
        #expect(b.spawnedReadsScreens == false)
    }

    /// …and a starting serve that never read screens is left alone, as it
    /// always was for every other preference.
    @Test func aStartingServeThatReadsNothingIsLeftAlone() throws {
        let suite = "ServeFleetLifecycleTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(false, forKey: DiagnosticsPreference.key)

        let fleet = Self.externalFleet()
        let a = fleet.manager(for: Self.a)
        a.instance.state = .starting
        a.instance.currentProjectPath = "/p/a"
        fleet.frontedProject = nil

        fleet.applyEnvChange(defaults: defaults)

        #expect(a.state == .starting)
        #expect(fleet.staleProjects.contains(Self.a) == false)
    }

    /// The wiring from a manager's poll to the sidebar's store: a manager's
    /// progress lands under ITS project and nobody else's.
    @Test func aManagersScreenProgressLandsUnderItsOwnProject() {
        let store = ScreenReadingStore()
        let fleet = Self.externalFleet(store)
        let p = ScreenReadingProgress(done: 1, total: 3, secondsDone: 0,
                                      secondsTotal: 30, rate: nil)
        _ = fleet.manager(for: Self.b)
        fleet.manager(for: Self.a).onScreensProgress?(p)
        #expect(store.progress[Self.a] == p)
        #expect(store.progress[Self.b] == nil)

        fleet.discard(Self.a)
        #expect(store.progress[Self.a] == nil, "a discarded project kept its row")
    }

    /// Turning Diagnostics ON withdraws nothing, so it stays lazy everywhere —
    /// the restart-all harm `ServeEnvStaleness` declines.
    @Test func diagnosticsOnStaysLazyForBackgroundServes() throws {
        let suite = "ServeFleetLifecycleTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(true, forKey: DiagnosticsPreference.key)

        let fleet = ServeFleet()
        let m = fleet.manager(for: Self.b)
        m.instance.state = .running(port: 5001)
        m.instance.currentProjectPath = "/p/b"
        m.instance.spawnedReadsScreens = true
        fleet.frontedProject = nil

        fleet.applyEnvChange(defaults: defaults)

        #expect(fleet.staleProjects.contains(Self.b))
    }

    /// The other half: a deferred instance must actually be restarted when
    /// someone looks at it, or "lazy" is just "never".
    @Test func frontingAStaleStudyClearsItsStaleness() {
        let fleet = ServeFleet()
        let m = fleet.manager(for: Self.b)
        m.instance.state = .running(port: 5001)
        m.instance.currentProjectPath = "/p/b"
        fleet.applyEnvChange()
        #expect(fleet.staleProjects.contains(Self.b))

        fleet.front(Self.b)

        #expect(fleet.staleProjects.contains(Self.b) == false)
        #expect(fleet.frontedProject == Self.b)
    }

    /// There is no owner to designate any more. One file, one writer (the
    /// fleet), and membership derived from the window roster — which is what
    /// makes the old flapping impossible rather than merely unlikely: a
    /// designated slot could point at a project whose sidecar had been reaped,
    /// and did, five times across five consecutive tool calls on 20 Aug.
    @Test func everyManagerReportsHandshakeChangesToTheFleet() {
        let fleet = ServeFleet()
        // Not just "the closure was assigned" — firing it must actually
        // re-derive. The deleted test it replaced pinned an observable effect;
        // asserting a non-nil closure would pin an implementation detail one
        // step upstream of the thing that matters.
        let manager = fleet.manager(for: Self.a)
        #expect(manager.onHandshakeDirty != nil)
        manager.onHandshakeDirty?()
        #expect(fleet.handshakeProjectPaths.isEmpty)   // no window, no scope
    }
}

/// The guard that came off `switchProject` when Stage 3b deleted it.
///
/// Two windows on one study both call `start()` on the same manager. Without a
/// same-path guard the second call tears down a sidecar that is still booting,
/// and the first window reports the corpse: "Server exited before becoming
/// ready (code 2)". Observed on screen before this existed.
@Suite("ServeManager same-path start guard")
@MainActor
struct ServeManagerStartGuardTests {

    @Test func startingTheProjectItIsAlreadyRunningIsANoOp() {
        let m = ServeManager()
        m.instance.currentProjectPath = "/p/A"
        m.instance.state = .running(port: 5000)

        m.start(projectPath: "/p/A")

        #expect(m.state == .running(port: 5000), "a second start tore down a healthy sidecar")
    }

    @Test func startingWhileTheSameProjectIsStillBootingIsANoOp() {
        let m = ServeManager()
        m.instance.currentProjectPath = "/p/A"
        m.instance.state = .starting

        m.start(projectPath: "/p/A")

        #expect(m.state == .starting, "a second start interrupted a boot in progress")
    }

    /// Path respelling must not defeat it — bookmark healing rewrites
    /// `Project.path` while the manager holds the spawn-time spelling.
    @Test func theGuardStandardisesPaths() {
        let m = ServeManager()
        m.instance.currentProjectPath = "/p/./A"
        m.instance.state = .running(port: 5000)

        m.start(projectPath: "/p/A")

        #expect(m.state == .running(port: 5000))
    }

    /// Retry after a failure must actually retry.
    ///
    /// External mode, not the default init: with the mode resolved from the
    /// bundle this test spawned a real sidecar on `/p/A` wherever the build had
    /// embedded one, and failed wherever it had not — `start()` returns at its
    /// `mode` guard before touching state, so the failure read as the guard
    /// swallowing the retry. A fresh checkout has no built sidecar to embed.
    @Test func aFailedServeCanBeRestartedOnTheSameProject() {
        let m = ServeManager(resolvedMode: .success(.external(port: 5001)))
        m.instance.currentProjectPath = "/p/A"
        m.instance.state = .failed(error: .passthrough("boom"))

        m.start(projectPath: "/p/A")

        #expect(m.state == .running(port: 5001), "Retry was swallowed by the guard")
    }
}

/// The scene value, and the dedup behaviour it exists to control.
///
/// SwiftUI keys window identity on the whole value. Three failures were observed
/// on screen before this type existed: New Window passing a project re-activated
/// the window that had it; passing `nil` capped the app at two windows, because
/// nil is itself a unique value; and which two you got depended on the order you
/// opened them in.
@Suite("WindowSeed")
struct WindowSeedTests {

    private static let a = UUID()
    private static let b = UUID()

    /// New Window must ALWAYS open. Two fresh seeds for the same study must not
    /// be equal, or dedup swallows the command and the window ordinals with it.
    @Test func twoFreshSeedsForOneStudyAreDistinct() {
        let first = WindowSeed.fresh(project: Self.a)
        let second = WindowSeed.fresh(project: Self.a)
        #expect(first != second)
        #expect(first.project == second.project)
    }

    /// …including with no study at all, which is the case that capped the app
    /// at two windows.
    @Test func twoSeedsWithNoStudyAreStillDistinct() {
        #expect(WindowSeed.fresh() != WindowSeed.fresh())
    }

    /// Open in New Window must reveal rather than duplicate, so its value has to
    /// be STABLE for a study — that is what makes dedup work FOR it.
    @Test func revealingTheSameStudyTwiceProducesTheSameValue() {
        #expect(WindowSeed.revealing(project: Self.a) == WindowSeed.revealing(project: Self.a))
        #expect(WindowSeed.revealing(project: Self.a) != WindowSeed.revealing(project: Self.b))
    }

    /// The two shapes must never collide: a reveal must not be satisfied by a
    /// window some New Window happened to open, and vice versa.
    @Test func freshAndRevealingNeverCollide() {
        #expect(WindowSeed.fresh(project: Self.a) != WindowSeed.revealing(project: Self.a))
    }

    /// The lens rides along — this is what makes the lens row's Open in New
    /// Window one gesture rather than open-then-navigate.
    @Test func aSeedCarriesItsLens() {
        let seed = WindowSeed.fresh(project: Self.a, lens: "codebook")
        #expect(seed.lens == "codebook")
        #expect(seed.project == Self.a)
    }

    /// It is a scene value, so it must survive restoration.
    @Test func itRoundTripsThroughCoding() throws {
        let seed = WindowSeed.fresh(project: Self.a, lens: "quotes")
        let data = try JSONEncoder().encode(seed)
        #expect(try JSONDecoder().decode(WindowSeed.self, from: data) == seed)
    }
}

/// Restoration decoding. A scene value that throws does not fail loudly — it
/// silently loses the researcher's windows, which come back on Welcome.
@Suite("WindowSeed decoding")
struct WindowSeedDecodingTests {

    @Test func aBareUUIDFromTheOlderBuildStillDecodes() throws {
        let legacy = UUID()
        let data = try JSONEncoder().encode(legacy)
        let seed = try JSONDecoder().decode(WindowSeed.self, from: data)
        #expect(seed.project == legacy, "an upgraded window lost its study")
        #expect(seed.token == legacy)
    }

    @Test func aPayloadMissingTheTokenStillDecodes() throws {
        let id = UUID()
        let json = #"{"project":"\#(id.uuidString)"}"#.data(using: .utf8)!
        let seed = try JSONDecoder().decode(WindowSeed.self, from: json)
        #expect(seed.project == id)
    }

    @Test func aCurrentPayloadRoundTripsUnchanged() throws {
        let seed = WindowSeed.fresh(project: UUID(), lens: "quotes")
        let data = try JSONEncoder().encode(seed)
        #expect(try JSONDecoder().decode(WindowSeed.self, from: data) == seed)
    }

    @Test func aSeedWithNoStudySurvivesTheRoundTrip() throws {
        let seed = WindowSeed.fresh()
        let data = try JSONEncoder().encode(seed)
        #expect(try JSONDecoder().decode(WindowSeed.self, from: data) == seed)
    }
}

/// A serve must not outlive the binary it was spawned from.
///
/// Measured 12 Oct 2026: a serve spawned at 23:25 on sidecar 0.36.0 outlived
/// the 00:10 rebuild to 0.37.0 and served all morning. Runs re-resolve the
/// binary per spawn, so the old serve imported the new runs' output. The
/// manager resolved its binary once at `init` and the same-path `start()`
/// returned early while `.running`, so nothing ever compared disk with memory.
@Suite("ServeManager sidecar freshness")
@MainActor
struct ServeManagerFreshnessTests {

    private static let spawned = SidecarBinaryStamp(size: 1, modified: Date(timeIntervalSince1970: 1))
    private static let rebuilt = SidecarBinaryStamp(size: 2, modified: Date(timeIntervalSince1970: 2))

    /// A manager that believes it is serving `/p/A` from a binary stamped
    /// `spawned`, with a reader that reports `onDisk` for the file now. The
    /// mode names a path that is not an executable, so a respawn fails fast
    /// into `.failed` rather than launching anything — the assertion is only
    /// that the guard did not keep the stale serve.
    private func running(onDisk: SidecarBinaryStamp) -> ServeManager {
        let binary = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-fake-sidecar-\(UUID().uuidString)")
        let m = ServeManager(resolvedMode: .success(.bundled(path: binary)))
        m.instance.currentProjectPath = "/p/A"
        m.instance.state = .running(port: 5000)
        m.instance.spawnedSidecarStamp = Self.spawned
        m.sidecarStampReader = { _ in onDisk }
        return m
    }

    @Test func aSamePathStartKeepsAServeWhoseBinaryIsUnchanged() {
        let m = running(onDisk: Self.spawned)
        m.start(projectPath: "/p/A")
        #expect(m.state == .running(port: 5000))
        #expect(m.sidecarBinaryChangedOnDisk == false)
    }

    @Test func aSamePathStartRestartsAServeWhoseBinaryChangedOnDisk() {
        let m = running(onDisk: Self.rebuilt)
        #expect(m.sidecarBinaryChangedOnDisk)
        m.start(projectPath: "/p/A")
        #expect(m.state != .running(port: 5000), "a serve on a rebuilt sidecar was left running")
    }

    /// Fronting a project is the moment a window looks at it again, so it is
    /// where a background serve catches up with a rebuild.
    @Test func frontingAStudyRestartsItWhenItsBinaryChangedOnDisk() {
        let fleet = ServeFleet()
        let id = UUID()
        let m = fleet.manager(for: id)
        m.instance.currentProjectPath = "/p/A"
        m.instance.state = .running(port: 5000)
        m.instance.spawnedSidecarStamp = Self.spawned
        m.sidecarStampReader = { _ in Self.rebuilt }
        // `manager(for:)` resolves the mode from the bundle, which this test
        // host may or may not carry; `sidecarBinaryChangedOnDisk` is false
        // without a mode, so only assert the restart when there is one.
        guard m.mode?.executableURL != nil else { return }

        fleet.front(id)

        #expect(m.state != .running(port: 5000), "fronting left a serve on a rebuilt sidecar running")
    }

    /// An unreadable binary (deleted, or `.external` with none) is not a newer
    /// one — never restart on a nil read.
    @Test func anUnreadableBinaryIsNotAChange() {
        let m = running(onDisk: Self.spawned)
        m.sidecarStampReader = { _ in nil }
        #expect(m.sidecarBinaryChangedOnDisk == false)
    }

    @Test func externalModeNeverReadsAsChanged() {
        let m = ServeManager(resolvedMode: .success(.external(port: 5001)))
        m.instance.spawnedSidecarStamp = Self.spawned
        m.sidecarStampReader = { _ in Self.rebuilt }
        #expect(m.sidecarBinaryChangedOnDisk == false)
    }
}
