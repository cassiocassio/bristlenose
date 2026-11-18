import Foundation
import os

// How the Whisper model reaches this Mac: one seam, one picker, one owner of the download
// (the Background Assets plan, design section).
//
// `WhisperDownloadModel` keeps the phases, the pill and the launch rules. What it no longer
// knows is *how* the bytes arrive: that is an acquirer. Today there is one, the sidecar's own
// `doctor --fetch` (Hugging Face), which is what every channel and OS ships. A second, Apple
// Background Assets for the store build on macOS 26+, plugs into the same seam and is picked by
// `WhisperAcquirerPicker`, a pure function with a table test.
//
// Rules every acquirer follows (owner, 16 Nov 2026):
// - After a failed attempt the app tries again on the next opportunity (a run starting, a
//   launch, Download Now). No acquirer depends on how the system behaves after a failure.
// - Nothing an acquirer reports promises or denies resume. The pill says what is true now.

// MARK: - Which acquirer (pure)

enum WhisperAcquirerKind: Equatable {
    /// `doctor --fetch` in the sidecar: Hugging Face. macOS 15, the Developer-ID `.dmg`, the
    /// fallback when Background Assets is off, unavailable or has failed.
    case sidecarFetch
    /// Apple Background Assets (`AssetPackManager`), Apple-hosted. macOS 26+, App Store or
    /// TestFlight builds only.
    case backgroundAssets
}

enum WhisperAcquirerPicker {
    /// Background Assets only where all four hold: the OS has it (26.0), this is a store build
    /// (a `.dmg` has no extension and Apple hosts packs only for the store), the kill switch is
    /// on, and the pack manager is usable (no recent failure that sent us to the fallback).
    /// Everything else, including an unknown OS, is the sidecar fetch that has always worked.
    static func pick(
        osMajor: Int, channel: DistributionChannel, killSwitchOn: Bool, backgroundAssetsUsable: Bool
    ) -> WhisperAcquirerKind {
        guard osMajor >= 26, channel == .appStoreOrTestFlight,
              killSwitchOn, backgroundAssetsUsable else { return .sidecarFetch }
        return .backgroundAssets
    }
}

// MARK: - The seam

/// What an acquisition ended in. A failure carries the cause a researcher can act on, when the
/// acquirer can tell (the sidecar's stderr tail says disk, network or certificate).
enum WhisperAcquisitionOutcome: Equatable {
    case succeeded
    /// Ended because `stop()` asked it to.
    case stopped
    case failed(cause: WhisperFailureCause?)
}

/// What an acquirer tells the model while it works. The model is the only conformer.
@MainActor
protocol WhisperAcquisitionEvents: AnyObject {
    /// `from` is the sender, so the model ignores an event from an acquirer that is no longer
    /// the current one (a stale end after a fallback must not clear the new attempt).
    func acquisitionTotal(_ bytes: Int64, from: WhisperModelAcquirer)
    func acquisitionProgress(done: Int64, total: Int64, from: WhisperModelAcquirer)
    func acquisitionEnded(_ outcome: WhisperAcquisitionOutcome, from: WhisperModelAcquirer)
}

@MainActor
protocol WhisperModelAcquirer: AnyObject {
    var kind: WhisperAcquirerKind { get }
    /// Whether this acquirer can run at all here (the sidecar to run, the pack manager to ask).
    /// False before anything is reset: the model says "didn't finish" and leaves its numbers.
    var isAvailable: Bool { get }
    /// An attempt is in flight (its process is alive: a Stop after it exited is a no-op).
    var isRunning: Bool { get }
    /// Environment for a pipeline run started now, so Python waits on this acquirer or leaves
    /// the download to it instead of fetching a second copy.
    var runEnvironment: [String: String] { get }
    /// Begin. False when it could not start (the model then shows the failure). Progress and
    /// the end arrive on `events`; the end arrives exactly once per successful start.
    func start(events: WhisperAcquisitionEvents) -> Bool
    /// Ask the attempt to stop; its end then arrives as `.stopped`.
    func stop()
    /// The app is quitting: let go of anything that outlives it.
    func appWillTerminate()
}

// MARK: - Today's download, unchanged

/// `doctor --fetch --progress-lines` in the sidecar, reading its `@download` lines. This is the
/// code that lived in `WhisperDownloadModel`, moved whole.
@MainActor
final class SidecarFetchAcquirer: WhisperModelAcquirer {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "whisper-download")

    let kind: WhisperAcquirerKind = .sidecarFetch
    private var process: Process?
    private var stopRequested = false
    private var stderrTail: [String] = []
    private weak var events: WhisperAcquisitionEvents?

    var isAvailable: Bool { WhisperDownloadModel.sidecar() != nil }
    var isRunning: Bool { process?.isRunning ?? false }

    var runEnvironment: [String: String] {
        guard let p = process, p.isRunning else { return [:] }
        return WhisperDownloadModel.whisperFetchEnvironment(pid: p.processIdentifier)
    }

    func start(events: WhisperAcquisitionEvents) -> Bool {
        guard process == nil, let (binary, mode) = WhisperDownloadModel.sidecar() else { return false }
        self.events = events
        stopRequested = false
        stderrTail = []

        let proc = Process()
        proc.executableURL = binary
        proc.arguments = ["doctor", "--fetch", "--progress-lines"]
        proc.environment = BristlenoseShared.childEnvironment(for: mode)
        proc.standardInput = FileHandle.nullDevice
        let out = Pipe()
        let err = Pipe()
        proc.standardOutput = out
        proc.standardError = err
        WhisperDownloadModel.readLines(out.fileHandleForReading) { [weak self] line in
            Task { @MainActor in self?.consume(line) }
        }
        WhisperDownloadModel.readLines(err.fileHandleForReading) { [weak self] line in
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
            return true
        } catch {
            Self.logger.error("whisper download failed to start: \(error.localizedDescription, privacy: .public)")
            process = nil
            return false
        }
    }

    /// SIGINT first (`ensure_hf_model` aborts hf_xet within about 2 s), then SIGKILL at 5 s.
    func stop() {
        guard let proc = process, proc.isRunning else { return }
        stopRequested = true
        proc.interrupt()
        let pid = proc.processIdentifier
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard let self, let p = self.process, p.processIdentifier == pid, p.isRunning else { return }
            kill(pid, SIGKILL)
        }
    }

    func appWillTerminate() { process?.interrupt() }

    private func consume(_ line: String) {
        guard let parsed = WhisperDownloadLine.parse(line) else { return }
        switch parsed {
        case .start(_, let total):
            events?.acquisitionTotal(total, from: self)
        case .progress(let done, let total):
            events?.acquisitionProgress(done: done, total: total, from: self)
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
            events?.acquisitionEnded(.succeeded, from: self)
        } else if stopRequested {
            Self.logger.info("whisper download stopped by the researcher")
            events?.acquisitionEnded(.stopped, from: self)
        } else {
            Self.logger.error(
                "whisper download exited \(status, privacy: .public): \(self.stderrTail.joined(separator: " | "), privacy: .public)")
            events?.acquisitionEnded(.failed(cause: WhisperFailureCause.classify(stderrTail)), from: self)
        }
    }
}
