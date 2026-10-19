import AppKit
import Foundation
import os

// The one Whisper download, app-wide (docs/design-apple-first-transcription.md §3 D).
//
// While Apple's speech model transcribes a first run, the 1.6 GB Whisper model
// downloads behind it, once, for every window. The app owns that download: the
// Python run never fetches on the Apple path, because two fetchers of one repo
// each write their own partial under hf_xet. The job runs the sidecar's own
// `doctor --fetch --progress-lines` and reads its `@download` lines; whether
// Whisper is on disk is always Python's answer (`doctor --whisper-status`),
// never a cache path computed here.
//
// Parked behind `BristlenoseFlags.appleSpeechAvailable` with everything else on this path.

// MARK: - Lines from the sidecar (pure)

/// Whisper on disk, as the preflight's own probe reports it.
enum WhisperDiskState: String, Equatable {
    case cached, partial, missing
}

/// One line the sidecar prints for the download job. The grammar is Python's
/// (`bristlenose/preflight/whisper.py`); never localised.
enum WhisperDownloadLine: Equatable {
    case start(repo: String, totalBytes: Int64)
    case progress(doneBytes: Int64, totalBytes: Int64)
    case done
    case status(WhisperDiskState, repo: String, bytesOnDisk: Int64)

    static func parse(_ raw: String) -> WhisperDownloadLine? {
        let parts = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            .split(separator: " ", omittingEmptySubsequences: true).map(String.init)
        guard let head = parts.first else { return nil }
        switch head {
        case "@download-start" where parts.count == 3:
            guard let total = Int64(parts[2]) else { return nil }
            return .start(repo: parts[1], totalBytes: total)
        case "@download" where parts.count == 3:
            guard let done = Int64(parts[1]), let total = Int64(parts[2]) else { return nil }
            return .progress(doneBytes: done, totalBytes: total)
        case "@download-done":
            return .done
        case "@whisper-status" where parts.count >= 3:
            guard let state = WhisperDiskState(rawValue: parts[1]) else { return nil }
            let bytes = parts.count >= 4 ? Int64(parts[3]) ?? 0 : 0
            return .status(state, repo: parts[2], bytesOnDisk: bytes)
        default:
            return nil
        }
    }
}

// MARK: - Rate and time left (pure)

/// Throughput over a sliding window, and minutes left that don't jitter.
///
/// The rate is reported only once the window has filled (plan §3 H): a rate
/// read off the first second of a download is a guess, and Foundation then
/// shows the bytes alone, which is honest. Minutes left are rounded **up** to
/// whole minutes and change with hysteresis — they may fall freely, but rise
/// only by two or more, so "About 3 minutes" never flickers with "About 4".
struct DownloadRate: Equatable {
    static let window: TimeInterval = 8

    private(set) var samples: [Sample] = []
    private(set) var shownMinutes: Int?

    struct Sample: Equatable {
        let time: TimeInterval
        let bytes: Int64
    }

    mutating func add(time: TimeInterval, bytes: Int64) {
        samples.append(Sample(time: time, bytes: bytes))
        // Keep one sample older than the window, so the span can reach it.
        while samples.count > 2, let second = samples.dropFirst().first,
              time - second.time >= Self.window {
            samples.removeFirst()
        }
    }

    /// Bytes a second over the window, or nil until it has filled.
    var bytesPerSecond: Double? {
        guard let first = samples.first, let last = samples.last else { return nil }
        let span = last.time - first.time
        guard span >= Self.window, last.bytes >= first.bytes else { return nil }
        return Double(last.bytes - first.bytes) / span
    }

    /// Whole minutes left (at least 1), or nil without a rate.
    mutating func minutesLeft(done: Int64, total: Int64) -> Int? {
        guard total > 0, let rate = bytesPerSecond, rate > 0 else {
            return shownMinutes
        }
        let seconds = Double(max(0, total - done)) / rate
        let fresh = max(1, Int((seconds / 60).rounded(.up)))
        if let shown = shownMinutes, fresh > shown, fresh < shown + 2 {
            return shown
        }
        shownMinutes = fresh
        return fresh
    }

    mutating func reset() {
        samples = []
        shownMinutes = nil
    }
}

// MARK: - The job

@MainActor
final class WhisperDownloadModel: ObservableObject {
    /// App-wide by nature: one download, one model on disk, every window. A
    /// singleton rather than an environment object so the Settings window,
    /// which AppKit builds lazily, reads the same instance with no injection to
    /// forget (an un-injected `@EnvironmentObject` is a launch crash).
    static let shared = WhisperDownloadModel()

    enum Phase: Equatable {
        /// Not asked yet, or being asked.
        case unknown
        case missing
        /// A download was interrupted; it starts again from the beginning.
        case partial
        case downloading
        case onDisk
        /// The download, or the question "is it on disk", failed. The pill
        /// says so with Retry, and Settings offers Retry too.
        case failed
    }

    @Published private(set) var phase: Phase = .unknown
    @Published private(set) var doneBytes: Int64 = 0
    @Published private(set) var totalBytes: Int64 = 0
    @Published private(set) var bytesOnDisk: Int64 = 0
    @Published private(set) var bytesPerSecond: Double?
    @Published private(set) var minutesLeft: Int?

    /// Shown while bytes move, and after a failure (with Retry), so a row
    /// "Waiting for Whisper" is never left with nothing anywhere saying why
    /// nothing is coming. Gone when Whisper is on disk, or after a deliberate
    /// Stop: the researcher chose that, and Settings still offers Download Now.
    var isPillVisible: Bool { phase == .downloading || phase == .failed }

    private static let logger = Logger(subsystem: "app.bristlenose", category: "whisper-download")
    /// A deliberate Stop Download, remembered across launches: the app does
    /// not start the 1.6 GB again on its own until Download Now (the researcher
    /// may have stopped it on a metered connection).
    private static let stoppedKey = "whisperDownloadStoppedByUser"
    private var process: Process?
    private var rate = DownloadRate()
    private var stopRequested = false
    private var stderrTail: [String] = []
    /// `appLaunched()` runs once per process, though every window's
    /// `onAppear` calls it.
    private var launched = false

    private var stoppedByUser: Bool {
        get { UserDefaults.standard.bool(forKey: Self.stoppedKey) }
        set { UserDefaults.standard.set(newValue, forKey: Self.stoppedKey) }
    }

    private init() {
        NotificationCenter.default.addObserver(
            forName: .bristlenoseAppleSpeechRunStarted, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.startIfNeeded() }
        }
        // A download the app quits on stops with it; the sidecar's own
        // parent-death watcher is the backstop for a crash.
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.process?.interrupt() }
        }
    }

    // MARK: Foundation's progress line

    /// "600.0 MB of 1.61 GB (10.0 MB/s) — About 2 minutes remaining", in the
    /// app's language (§3 H; measured 18 Oct 2026). Bytes alone until the rate
    /// window fills: no invented time.
    var progressLine: String {
        Self.progressLine(done: doneBytes, total: totalBytes,
                          bytesPerSecond: bytesPerSecond, minutesLeft: minutesLeft)
    }

    nonisolated static func progressLine(done: Int64, total: Int64,
                                         bytesPerSecond: Double?, minutesLeft: Int?) -> String {
        // No total from the server: Foundation describes an indeterminate
        // Progress as nothing at all (measured 18 Oct 2026), so say the bytes
        // we have in its own byte format.
        guard total > 0 else {
            return ByteCountFormatter.string(fromByteCount: max(done, 0), countStyle: .file)
        }
        let p = Progress(totalUnitCount: total)
        p.kind = .file
        p.fileOperationKind = .downloading
        p.completedUnitCount = min(done, total)
        if let bytesPerSecond {
            p.throughput = Int(bytesPerSecond)
            if let minutesLeft { p.estimatedTimeRemaining = TimeInterval(minutesLeft * 60) }
        }
        return p.localizedAdditionalDescription ?? ""
    }

    var fractionDone: Double? {
        totalBytes > 0 ? min(1, Double(doneBytes) / Double(totalBytes)) : nil
    }

    // MARK: Lifecycle

    /// At launch: ask Python whether Whisper is on disk, and start again a
    /// download a previous launch left partial — unless the researcher stopped
    /// it (the appliance copes; it does not overrule).
    func appLaunched() {
        guard BristlenoseFlags.appleSpeechAvailable, !launched else { return }
        launched = true
        Task { @MainActor in
            await refresh()
            if phase == .partial, !stoppedByUser { start() }
        }
    }

    /// A run went to Apple's model (the sidecar printed `@transcription-engine
    /// apple`): fetch Whisper behind it, unless it is here, coming, or stopped.
    func startIfNeeded() {
        guard BristlenoseFlags.appleSpeechAvailable, !stoppedByUser else { return }
        switch phase {
        case .downloading, .onDisk: return
        case .unknown:
            Task { @MainActor in
                await refresh()
                if phase != .onDisk && phase != .downloading { start() }
            }
        case .missing, .partial, .failed:
            start()
        }
    }

    /// Download Now / Retry: the researcher asked, so a remembered Stop is
    /// forgotten. Single-flight.
    func downloadNow() {
        stoppedByUser = false
        start()
    }

    private func start() {
        guard process == nil else { return }
        guard let (binary, mode) = Self.sidecar() else {
            Self.logger.error("whisper download: no sidecar to run (bundle or dev path missing)")
            phase = .failed
            return
        }
        stopRequested = false
        stderrTail = []
        rate.reset()
        doneBytes = 0
        totalBytes = 0
        bytesPerSecond = nil
        minutesLeft = nil
        phase = .downloading

        let proc = Process()
        proc.executableURL = binary
        proc.arguments = ["doctor", "--fetch", "--progress-lines"]
        proc.environment = BristlenoseShared.childEnvironment(for: mode)
        proc.standardInput = FileHandle.nullDevice
        let out = Pipe()
        let err = Pipe()
        proc.standardOutput = out
        proc.standardError = err
        Self.readLines(out.fileHandleForReading) { [weak self] line in
            Task { @MainActor in self?.consume(line) }
        }
        Self.readLines(err.fileHandleForReading) { [weak self] line in
            Task { @MainActor in self?.keepTail(line) }
        }
        proc.terminationHandler = { [weak self] p in
            let status = p.terminationStatus
            Task { @MainActor in self?.finished(status: status) }
        }
        do {
            try proc.run()
            process = proc
            Self.logger.info("whisper download started pid=\(proc.processIdentifier, privacy: .public)")
        } catch {
            Self.logger.error("whisper download failed to start: \(error.localizedDescription, privacy: .public)")
            process = nil
            phase = .failed
        }
    }

    /// Stop Download. There is no resume (hf_xet starts again), which is why
    /// the button says so beside it. SIGINT first — `ensure_hf_model` aborts
    /// hf_xet within about 2 s — then SIGKILL if it hasn't gone.
    func stop() {
        guard let proc = process, proc.isRunning else { return }
        stopRequested = true
        stoppedByUser = true
        proc.interrupt()
        let pid = proc.processIdentifier
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard let self, let p = self.process, p.processIdentifier == pid, p.isRunning else { return }
            kill(pid, SIGKILL)
        }
    }

    /// Ask Python whether Whisper is on disk. Never computes the cache path
    /// here. A probe that cannot answer is said (`.failed`, logged with the
    /// sidecar's own words), never left as a blank. Moving to `.onDisk` from
    /// anything else announces Whisper ready, which re-runs waiting projects —
    /// at launch as much as after a download.
    @discardableResult
    func refresh() async -> Bool {
        guard process == nil else { return phase == .onDisk }
        guard let (binary, mode) = Self.sidecar() else {
            Self.logger.error("whisper status: no sidecar to ask")
            phase = .failed
            return false
        }
        let answer = await Self.askStatus(binary: binary, mode: mode)
        guard process == nil else { return false }  // a download started meanwhile
        guard let line = answer.line,
              case .status(let state, _, let bytes)? = WhisperDownloadLine.parse(line) else {
            Self.logger.error(
                "whisper status: no answer (exit \(answer.status, privacy: .public)): \(answer.stderr, privacy: .public)")
            phase = .failed
            return false
        }
        let before = phase
        bytesOnDisk = bytes
        switch state {
        case .cached: phase = .onDisk
        case .partial: phase = .partial
        case .missing: phase = .missing
        }
        if phase == .onDisk, before != .onDisk {
            NotificationCenter.default.post(name: .bristlenoseWhisperReady, object: nil)
        }
        return true
    }

    // MARK: Internals

    private struct StatusAnswer: Sendable {
        let line: String?
        let status: Int32
        let stderr: String
    }

    /// `doctor --whisper-status`, off the main thread, bounded to 60 s.
    private nonisolated static func askStatus(binary: URL, mode: SidecarMode) async -> StatusAnswer {
        let env = await MainActor.run { BristlenoseShared.childEnvironment(for: mode) }
        return await withCheckedContinuation { cont in
            DispatchQueue.global(qos: .utility).async {
                let proc = Process()
                proc.executableURL = binary
                proc.arguments = ["doctor", "--whisper-status"]
                proc.environment = env
                proc.standardInput = FileHandle.nullDevice
                let out = Pipe(), err = Pipe()
                proc.standardOutput = out
                proc.standardError = err
                do { try proc.run() } catch {
                    cont.resume(returning: StatusAnswer(line: nil, status: -1,
                                                        stderr: error.localizedDescription))
                    return
                }
                let deadline = DispatchWorkItem { if proc.isRunning { proc.terminate() } }
                DispatchQueue.global().asyncAfter(deadline: .now() + 60, execute: deadline)
                let data = out.fileHandleForReading.readDataToEndOfFile()
                let errData = err.fileHandleForReading.readDataToEndOfFile()
                proc.waitUntilExit()
                deadline.cancel()
                let text = String(decoding: data, as: UTF8.self)
                let errTail = String(decoding: errData, as: UTF8.self)
                    .split(separator: "\n").suffix(3).joined(separator: " | ")
                cont.resume(returning: StatusAnswer(
                    line: text.split(separator: "\n").map(String.init)
                        .first { $0.hasPrefix("@whisper-status") },
                    status: proc.terminationStatus,
                    stderr: BristlenoseShared.redactKeys(in: errTail)))
            }
        }
    }

    /// Line-split a pipe on newline **bytes** before decoding, so a multi-byte
    /// character that straddles two reads is never dropped with its chunk.
    private nonisolated static func readLines(_ handle: FileHandle,
                                              _ each: @escaping @Sendable (String) -> Void) {
        DispatchQueue.global(qos: .utility).async {
            var buffer = Data()
            while true {
                let data = handle.availableData
                if data.isEmpty { break }
                buffer.append(data)
                while let nl = buffer.firstIndex(of: 0x0A) {
                    let line = buffer[buffer.startIndex..<nl]
                    buffer.removeSubrange(buffer.startIndex...nl)
                    each(String(decoding: line, as: UTF8.self))
                }
            }
            if !buffer.isEmpty { each(String(decoding: buffer, as: UTF8.self)) }
        }
    }

    private func consume(_ line: String) {
        guard let parsed = WhisperDownloadLine.parse(line) else { return }
        switch parsed {
        case .start(_, let total):
            totalBytes = total
        case .progress(let done, let total):
            doneBytes = done
            if total > 0 { totalBytes = total }
            rate.add(time: ProcessInfo.processInfo.systemUptime, bytes: done)
            bytesPerSecond = rate.bytesPerSecond
            minutesLeft = rate.minutesLeft(done: done, total: totalBytes)
        case .done, .status:
            break
        }
    }

    private func keepTail(_ line: String) {
        let clean = line.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return }
        stderrTail.append(BristlenoseShared.redactKeys(in: clean))
        if stderrTail.count > 5 { stderrTail.removeFirst() }
    }

    private func finished(status: Int32) {
        process = nil
        if status == 0 {
            Self.logger.info("whisper download finished")
            // Off `.downloading` before asking, so a probe that fails leaves
            // `.failed`, never a pill frozen on its last bytes.
            phase = .unknown
            Task { @MainActor in await refresh() }
        } else if stopRequested {
            Self.logger.info("whisper download stopped by the researcher")
            phase = .unknown
            Task { @MainActor in await refresh() }
        } else {
            Self.logger.error(
                "whisper download exited \(status, privacy: .public): \(self.stderrTail.joined(separator: " | "), privacy: .public)")
            phase = .failed
        }
    }

    /// The sidecar binary and mode, resolved exactly as a run resolves them.
    private static func sidecar() -> (URL, SidecarMode)? {
        #if DEBUG
        let externalPortRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_EXTERNAL_PORT"]
        let sidecarPathRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_SIDECAR_PATH"]
        #else
        let externalPortRaw: String? = nil
        let sidecarPathRaw: String? = nil
        #endif
        guard case .success(let mode) = SidecarMode.resolve(
            externalPortRaw: externalPortRaw, sidecarPathRaw: sidecarPathRaw,
            bundleResourceURL: Bundle.main.resourceURL
        ) else { return nil }
        switch mode {
        case .bundled(let path), .devSidecar(let path): return (path, mode)
        case .external: return nil
        }
    }

    #if DEBUG
    /// Diagnostics harness: draw the pill and the Settings row in a state
    /// without a real download.
    func debugApply(_ phase: Phase, done: Int64 = 600_000_000, total: Int64 = 1_614_000_000) {
        self.phase = phase
        doneBytes = done
        totalBytes = total
        bytesPerSecond = phase == .downloading ? 10_000_000 : nil
        minutesLeft = phase == .downloading ? 2 : nil
        bytesOnDisk = phase == .onDisk ? total : 0
    }
    #endif
}

extension Notification.Name {
    /// A run went to Apple's speech model (`@transcription-engine apple`).
    static let bristlenoseAppleSpeechRunStarted = Notification.Name("bristlenoseAppleSpeechRunStarted")
    /// Whisper is on disk: announced on every move to `.onDisk`, after a
    /// download or at launch, so a project waiting for it runs again.
    static let bristlenoseWhisperReady = Notification.Name("bristlenoseWhisperReady")
}
