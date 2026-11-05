import Foundation
import os
import AppKit

private let log = Logger(subsystem: "app.bristlenose", category: "standby")

// A sidecar started before a study is chosen (docs/design-standby-sidecar.md).
//
// Opening a study pays for the sidecar's interpreter and imports, which do not depend on the
// study. A standby pays for them at launch, while the researcher is still choosing. It waits on
// stdin for one claim naming the study, then carries on exactly as a cold `serve <path>` would,
// so everything after the claim (the Report: line, the token, the watchdog, the handshake) is
// `ServeManager`'s, unchanged.
//
// One standby at most. A study that cannot use it cold-spawns as before: the standby is an
// optimisation and never a requirement, and every refusal below falls back to the old path.

/// What may be started and claimed. Decisions only, so they test without a process.
enum StandbyPolicy {
    /// The fleet starts the first standby this long after launch, so it does not compete with the
    /// app's own launch.
    static let launchDelay: Duration = .milliseconds(1500)
    /// After a claim, the replacement starts this long after it.
    static let replaceDelay: Duration = .seconds(3)
    /// After a standby dies unclaimed, no new one for this long.
    static let respawnAfterDeath: Duration = .seconds(30)
    /// This many unclaimed deaths in a row and the pool stops trying until the app restarts or a
    /// claim succeeds. A sidecar that cannot boot a standby (an old bundle without the flag) must
    /// not spin.
    static let maxConsecutiveDeaths = 3
    /// A standby that has not said it is ready by now is stopped.
    static let readyCeiling: Duration = .seconds(90)

    static let defaultsKey = "BristlenoseStandbySidecar"

    /// On unless `defaults write app.bristlenose BristlenoseStandbySidecar -bool NO`, or
    /// `BRISTLENOSE_STANDBY=0` in the environment.
    static func isEnabled(defaults: UserDefaults = .standard,
                          environment: [String: String] = ProcessInfo.processInfo.environment) -> Bool {
        if environment["BRISTLENOSE_STANDBY"] == "0" { return false }
        return defaults.object(forKey: defaultsKey) as? Bool ?? true
    }

    struct SpawnInputs {
        var enabled: Bool
        var isBundled: Bool
        var hasLeasedStudy: Bool
        var hasStandby: Bool
        var consecutiveDeaths: Int
        var sinceLastDeath: Duration?
    }

    static func shouldSpawn(_ i: SpawnInputs) -> Bool {
        guard i.enabled, i.isBundled, i.hasLeasedStudy, !i.hasStandby else { return false }
        guard i.consecutiveDeaths < maxConsecutiveDeaths else { return false }
        if let since = i.sinceLastDeath, since < respawnAfterDeath { return false }
        return true
    }

    struct ClaimInputs {
        var phase: StandbySidecar.Phase
        var isAlive: Bool
        var fingerprintMatches: Bool
        var stampMatches: Bool
        /// The study's security-scoped lease existed when the standby was spawned. A child
        /// inherits the sandbox extensions held at spawn, so a study added, located or relocated
        /// afterwards is not readable by a standby that is already running.
        var studyLeasedAtSpawn: Bool
    }

    static func canClaim(_ i: ClaimInputs) -> Bool {
        i.phase == .ready && i.isAlive && i.fingerprintMatches && i.stampMatches && i.studyLeasedAtSpawn
    }

    /// A standby the environment or the binary has moved past: it can never be claimed again.
    static func isStale(_ i: ClaimInputs) -> Bool {
        !i.fingerprintMatches || !i.stampMatches
    }
}

/// One standby process: boots, says it is ready, waits for a claim.
@MainActor
final class StandbySidecar {
    enum Phase: Equatable { case booting, ready, claimed, dead }

    static let readyMarker = "standby-ready"
    private static let heldLineCap = 50

    private(set) var phase: Phase = .booting
    let process: Process
    let spawnedEnvFingerprint: String
    let spawnedSidecarStamp: SidecarBinaryStamp?
    /// The studies whose lease was open when this was spawned, standardised.
    let leasedPaths: [String]
    /// The one reader of the merged stdout+stderr pipe. A claim hands its lines to the manager;
    /// two readers on one handle would split the bytes.
    private(set) var readTask: Task<Void, Never>?

    private let stdinPipe = Pipe()
    private var held: [String] = []
    private var sink: (@MainActor (String) -> Void)?
    private var onTerminated: (@MainActor (Int32) -> Void)?
    /// The pool's hook: ready, and died before a claim.
    var onChange: (@MainActor (StandbySidecar) -> Void)?

    init(executableURL: URL, arguments: [String], environment: [String: String],
         fingerprint: String, stamp: SidecarBinaryStamp?, leasedPaths: [String]) {
        process = Process()
        process.executableURL = executableURL
        process.arguments = arguments
        process.environment = environment
        spawnedEnvFingerprint = fingerprint
        spawnedSidecarStamp = stamp
        self.leasedPaths = leasedPaths.map { URL(fileURLWithPath: $0).standardizedFileURL.path }
    }

    func isLeased(_ path: String) -> Bool {
        leasedPaths.contains(URL(fileURLWithPath: path).standardizedFileURL.path)
    }

    var isAlive: Bool { process.isRunning }

    func start() throws {
        let out = Pipe()
        process.standardOutput = out
        process.standardError = out
        process.standardInput = stdinPipe
        let handle = out.fileHandleForReading
        readTask = Task.detached { [weak self] in
            var framer = ProcessOutputLines()
            while true {
                let data = handle.availableData
                if data.isEmpty {
                    if let last = framer.finish() { await self?.receive(last) }
                    break
                }
                for line in framer.append(data) { await self?.receive(line) }
            }
        }
        process.terminationHandler = { [weak self] p in
            // Off-main: carry only the status across, never the Process.
            let status = p.terminationStatus
            Task { @MainActor in self?.terminated(status) }
        }
        try process.run()
    }

    private func receive(_ line: String) {
        if let sink {
            sink(line)
            return
        }
        if phase == .booting, line.contains(Self.readyMarker) {
            phase = .ready
            onChange?(self)
            return
        }
        if held.count < Self.heldLineCap { held.append(line) }
    }

    private func terminated(_ status: Int32) {
        if let onTerminated {
            onTerminated(status)
            return
        }
        guard phase != .dead else { return }
        phase = .dead
        onChange?(self)
    }

    /// Hand this process to a study. Synchronous on the main actor: the checks that decided to
    /// claim it and the adoption are one step, so a recycle cannot land between them.
    ///
    /// The manager's routes are installed before the liveness re-check, so a standby that dies
    /// in the handover reaches the manager's termination handling, not a handler nobody reads.
    /// Returns false (and leaves the process unclaimed and stopped) if the claim could not be
    /// delivered; the caller then cold-spawns.
    func claim(projectPath: String, mcpToken: String,
               sink: @escaping @MainActor (String) -> Void,
               onTerminated: @escaping @MainActor (Int32) -> Void) -> Bool {
        guard phase == .ready, process.isRunning else { return false }
        self.sink = sink
        self.onTerminated = onTerminated
        phase = .claimed
        guard process.isRunning else {
            self.sink = nil
            self.onTerminated = nil
            phase = .dead
            return false
        }
        let claim: [String: Any] = ["v": 1, "project": projectPath, "mcp_token": mcpToken]
        guard let json = try? JSONSerialization.data(withJSONObject: claim) else {
            abandonClaim()
            return false
        }
        do {
            try stdinPipe.fileHandleForWriting.write(contentsOf: json + Data([10]))
            try? stdinPipe.fileHandleForWriting.close()
        } catch {
            log.warning("standby claim not delivered: \(error.localizedDescription, privacy: .public)")
            abandonClaim()
            return false
        }
        return true
    }

    /// Lines the standby printed before it was claimed (its stderr noise, mostly). The manager
    /// replays them once it has adopted the process: `handleLine` routes by process identity, so
    /// replaying inside `claim` would have them dropped as a stranger's.
    func replayHeld() {
        let early = held
        held = []
        guard let sink else { return }
        for line in early { sink(line) }
    }

    private func abandonClaim() {
        sink = nil
        onTerminated = nil
        phase = .dead
        halt()
    }

    /// Stop an unclaimed standby: SIGINT, the house convention, then SIGTERM if it lingers.
    /// A claimed process belongs to its manager and is never stopped from here.
    func stop() {
        guard phase != .claimed else { return }
        phase = .dead
        try? stdinPipe.fileHandleForWriting.close()
        halt()
    }

    private func halt() {
        readTask?.cancel()
        guard process.isRunning else { return }
        process.interrupt()
        let p = process
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            if p.isRunning { p.terminate() }
        }
    }
}

/// The app's one standby, and when to have it.
@MainActor
final class StandbyPool {
    private(set) var current: StandbySidecar?
    private(set) var consecutiveDeaths = 0
    private var lastDeathAt: ContinuousClock.Instant?
    private var pendingStart: Task<Void, Never>?
    private var readyWatchdog: Task<Void, Never>?
    private var quitObserver: NSObjectProtocol?

    private var mode: () -> SidecarMode? = { nil }
    private var leasedPaths: () -> [String] = { [] }
    private var environmentFor: (SidecarMode) -> [String: String] = { BristlenoseShared.childEnvironment(for: $0) }
    private var stampReader: (URL) -> SidecarBinaryStamp? = { SidecarBinaryStamp.read(at: $0) }
    private var isEnabled: () -> Bool = { StandbyPolicy.isEnabled() }
    private var standbyArguments = ["--no-open", "--port", "0", "--standby"]

    init() {}

    /// Wired by the app once the sidebar model exists. Tests pass their own.
    func configure(mode: @escaping () -> SidecarMode?,
                   leasedPaths: @escaping () -> [String],
                   environmentFor: ((SidecarMode) -> [String: String])? = nil,
                   stampReader: ((URL) -> SidecarBinaryStamp?)? = nil,
                   isEnabled: (() -> Bool)? = nil,
                   arguments: [String]? = nil) {
        self.mode = mode
        self.leasedPaths = leasedPaths
        if let environmentFor { self.environmentFor = environmentFor }
        if let stampReader { self.stampReader = stampReader }
        if let isEnabled { self.isEnabled = isEnabled }
        if let arguments { standbyArguments = arguments }
        if quitObserver == nil {
            quitObserver = NotificationCenter.default.addObserver(
                forName: NSApplication.willTerminateNotification, object: nil, queue: .main
            ) { [weak self] _ in
                MainActor.assumeIsolated { self?.shutdown() }
            }
        }
    }

    /// Start one after `delay`, if the policy still wants one then.
    func scheduleStart(after delay: Duration) {
        pendingStart?.cancel()
        pendingStart = Task { [weak self] in
            try? await Task.sleep(for: delay)
            guard !Task.isCancelled else { return }
            self?.startIfWanted()
        }
    }

    func startIfWanted() {
        let activeMode = mode()
        var isBundled = false
        if case .some(.bundled) = activeMode { isBundled = true }
        let sinceDeath = lastDeathAt.map { ContinuousClock.now - $0 }
        let inputs = StandbyPolicy.SpawnInputs(
            enabled: isEnabled(), isBundled: isBundled,
            hasLeasedStudy: !leasedPaths().isEmpty,
            hasStandby: current != nil,
            consecutiveDeaths: consecutiveDeaths, sinceLastDeath: sinceDeath)
        guard StandbyPolicy.shouldSpawn(inputs), let activeMode,
              let executable = activeMode.executableURL else { return }
        let env = environmentFor(activeMode)
        let sidecar = StandbySidecar(
            executableURL: executable,
            arguments: standbyArguments,
            environment: env,
            fingerprint: ServeEnvStaleness.fingerprint(env),
            stamp: stampReader(executable),
            leasedPaths: leasedPaths())
        sidecar.onChange = { [weak self] changed in self?.changed(changed) }
        do {
            try sidecar.start()
        } catch {
            log.warning("standby did not start: \(error.localizedDescription, privacy: .public)")
            recordDeath()
            return
        }
        current = sidecar
        PerfSignpost.step("standby-spawned")
        readyWatchdog?.cancel()
        readyWatchdog = Task { [weak self, weak sidecar] in
            try? await Task.sleep(for: StandbyPolicy.readyCeiling)
            guard !Task.isCancelled, let self, let sidecar,
                  sidecar.phase == .booting, self.current === sidecar else { return }
            log.warning("standby never said ready — stopping it")
            sidecar.stop()
            self.changed(sidecar)
        }
    }

    private func changed(_ sidecar: StandbySidecar) {
        guard sidecar === current else { return }
        switch sidecar.phase {
        case .ready:
            readyWatchdog?.cancel()
            PerfSignpost.step("standby-ready")
        case .dead:
            readyWatchdog?.cancel()
            current = nil
            recordDeath()
        case .booting, .claimed:
            break
        }
    }

    private func recordDeath() {
        consecutiveDeaths += 1
        lastDeathAt = .now
        if consecutiveDeaths < StandbyPolicy.maxConsecutiveDeaths {
            scheduleStart(after: StandbyPolicy.respawnAfterDeath)
        } else {
            log.warning("standby died \(self.consecutiveDeaths, privacy: .public) times in a row — giving up until a claim succeeds")
        }
    }

    /// The standby a study may take now, or nil. Stale ones are stopped and replaced here.
    func claimable(projectPath: String, fingerprint: String, stamp: SidecarBinaryStamp?) -> StandbySidecar? {
        guard let sidecar = current else { return nil }
        let inputs = StandbyPolicy.ClaimInputs(
            phase: sidecar.phase, isAlive: sidecar.isAlive,
            fingerprintMatches: sidecar.spawnedEnvFingerprint == fingerprint,
            stampMatches: sidecar.spawnedSidecarStamp == stamp,
            studyLeasedAtSpawn: sidecar.isLeased(projectPath))
        if StandbyPolicy.isStale(inputs) { recycle() ; return nil }
        return StandbyPolicy.canClaim(inputs) ? sidecar : nil
    }

    /// Call after a successful `claim`: the standby is now its manager's.
    func didClaim(_ sidecar: StandbySidecar) {
        guard sidecar === current else { return }
        current = nil
        readyWatchdog?.cancel()
        consecutiveDeaths = 0
        lastDeathAt = nil
        scheduleStart(after: StandbyPolicy.replaceDelay)
    }

    /// Call after a `claim` that returned false.
    func claimFailed(_ sidecar: StandbySidecar) {
        guard sidecar === current else { return }
        current = nil
        readyWatchdog?.cancel()
        recordDeath()
    }

    /// The environment may have moved under the waiting standby (a provider, key, language or
    /// Screens change): if it has, replace it.
    func environmentChanged() {
        guard let sidecar = current, let activeMode = mode() else { return }
        let now = ServeEnvStaleness.fingerprint(environmentFor(activeMode))
        if sidecar.spawnedEnvFingerprint != now { recycle() }
    }

    func recycle() {
        current?.stop()
        current = nil
        readyWatchdog?.cancel()
        scheduleStart(after: .seconds(1))
    }

    func shutdown() {
        pendingStart?.cancel()
        readyWatchdog?.cancel()
        current?.stop()
        current = nil
    }
}
