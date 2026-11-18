import AppKit
import Foundation
import os

// The one Whisper download, app-wide (docs/design-apple-first-transcription.md §3 D).
//
// The 1.6 GB Whisper model downloads in the background, once, for every window:
// from launch once the AI disclosure is acknowledged (owner, 18 and 22 Oct
// 2026), and behind Apple's speech model when that transcribes a first run. The
// app owns that download: a run started meanwhile waits on it rather than
// fetching (two fetchers of one repo each write their own partial under
// hf_xet). The job runs the sidecar's own `doctor --fetch --progress-lines` and
// reads its `@download` lines; whether Whisper is on disk is always Python's
// answer (`doctor --whisper-status`), never a cache path computed here.
//
// The Apple-speech half (`startIfNeeded`) runs when `BristlenoseFlags.appleSpeechAvailable`
// (on by default since 22 Oct 2026; the defaults key is a kill switch).

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

// MARK: - Why a download failed (pure)

/// The three failures a researcher can do something about, read off the last lines the download
/// job wrote to stderr. Anything else stays "The download didn't finish." with nothing added: an
/// unrecognised reason is not guessed at, and a raw Python sentence is not shown to a researcher.
///
/// The patterns are lowercase regexes over the joined tail. Python's own wording is the source
/// (`bristlenose/preflight/whisper.py`: `ensure_disk_room`'s "Disk full: …", and the exceptions
/// `huggingface_hub` and hf_xet raise), and `tests/test_whisper_failure_cause.py` pins that every
/// network marker the Python retry loop waits on is recognised here too. Checked in this order:
/// a certificate failure arrives wrapped in "ConnectError", a network word.
enum WhisperFailureCause: Equatable {
    case disk, network, certificate

    static let diskPattern = #"no space left|enospc|disk full|\[errno 28\]"#
    static let certificatePattern = #"certificate|invalid peer"#
    static let networkPattern =
        #"nodename nor servname|name or service not known|temporary failure in name resolution|network is unreachable|network is down|no route to host|host is down|connection reset|connection aborted|connection closed before|connecttimeout|readtimeout|readerror|remoteprotocolerror|incompleteread|timed out|broken pipe|cached snapshot|unexpected_eof|eof occurred in violation|error decoding response body|error sending request|dns error|failed to lookup address|operation timed out|too many requests|service unavailable|bad gateway|gateway timeout|internal server error|\[errno (8|50|51|54|57|60|65)\]|\(os error (50|51|54|57|60|65)\)"#

    static func classify(_ lines: [String]) -> WhisperFailureCause? {
        let text = lines.joined(separator: " ").lowercased()
        func has(_ pattern: String) -> Bool { text.range(of: pattern, options: .regularExpression) != nil }
        if has(diskPattern) { return .disk }
        if has(certificatePattern) { return .certificate }
        if has(networkPattern) { return .network }
        return nil
    }

    /// Whole keys, not built from parts, so a grep for the key finds this and the locale files.
    var key: String {
        switch self {
        case .disk: return "desktop.modelDownload.causeDisk"
        case .network: return "desktop.modelDownload.causeNetwork"
        case .certificate: return "desktop.modelDownload.causeCertificate"
        }
    }

    /// The popover's title: the cause, in two words, when it has one; else the plain statement.
    /// A full disk is the low-disk popover's own title (one popover for both routes to it).
    static func titleKey(for cause: WhisperFailureCause?) -> String {
        switch cause {
        case .disk?: return "desktop.modelDownload.lowDiskTitle"
        case .network?: return "desktop.modelDownload.causeNetworkTitle"
        case .certificate?: return "desktop.modelDownload.causeCertificateTitle"
        case nil: return "desktop.modelDownload.failedTitle"
        }
    }

    /// Whether Retry can work. It cannot for a full disk: the researcher has to look at
    /// Transcription Settings (other models, Download Now once there is room), not retry.
    var retryCanWork: Bool { self != .disk }

    /// The line a failed download shows: its cause when it has one, else the plain statement.
    static func lineKey(for cause: WhisperFailureCause?) -> String {
        cause?.key ?? "desktop.transcriptionSettings.whisperFailed"
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
        // Bytes going BACK is a restart: the job waited out a dropped network and began the
        // fetch again from zero (hf_xet does not resume). The dead attempt's samples and its
        // minutes-left would otherwise survive into the new one: "About 1 minute" for a fresh
        // 1.6 GB, held there by the hysteresis below.
        if let last = samples.last, bytes < last.bytes { reset() }
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
final class WhisperDownloadModel: ObservableObject, WhisperAcquisitionEvents {
    /// App-wide by nature: one download, one model on disk, every window. A
    /// singleton rather than an environment object so the Settings window,
    /// which AppKit builds lazily, reads the same instance with no injection to
    /// forget (an un-injected `@EnvironmentObject` is a launch crash).
    static let shared = WhisperDownloadModel()

    enum Phase: Equatable {
        /// Not asked yet, or being asked.
        case unknown
        case missing
        /// The Hugging Face cache holds part of it (an interrupted fetch).
        case partial
        case downloading
        case onDisk
        /// The download, or the question "is it on disk", failed. The pill
        /// says so with Retry, and Settings offers Retry too.
        case failed
    }

    @Published private(set) var phase: Phase = .unknown { didSet { updateLowDisk() } }
    @Published private(set) var doneBytes: Int64 = 0
    @Published private(set) var totalBytes: Int64 = 0
    @Published private(set) var bytesOnDisk: Int64 = 0
    @Published private(set) var bytesPerSecond: Double?
    @Published private(set) var minutesLeft: Int?
    /// Why the last download failed, when it is one of the three a researcher can act on.
    @Published private(set) var failureCause: WhisperFailureCause?

    /// Shown while bytes move, and after a failure (with Retry), so a row
    /// "Waiting for Whisper" is never left with nothing anywhere saying why
    /// nothing is coming. Gone when Whisper is on disk, or after a deliberate
    /// Stop: the researcher chose that, and Settings still offers Download Now.
    ///
    /// Also shown, as a warning, when the model is missing and the app would have fetched it
    /// but for the free-space floor (`lowDisk`): a Mac with no room is told why nothing starts.
    var isPillVisible: Bool { phase == .downloading || phase == .failed || lowDisk }

    /// The model is missing, the researcher has not declined it, and the only thing stopping the
    /// app from asking or fetching is less than `autoStartFloorBytes` free. Drives the warning pill
    /// and holds a run's Whisper sessions (`runMustDefer`) rather than fetching into a full disk.
    @Published private(set) var lowDisk = false
    /// Free bytes on the volume that holds the model; injectable so tests need no full disk.
    var freeDiskBytes: () -> Int64? = { OllamaCatalog.freeDiskBytes() }
    /// Whether the AI disclosure is acknowledged. Injectable for the same reason.
    var hasAIConsent: () -> Bool = { PipelineRunner.hasAIConsent }

    private static let logger = Logger(subsystem: "app.bristlenose", category: "whisper-download")
    /// A deliberate Stop, remembered across launches: the app does
    /// not start the 1.6 GB again on its own until Download Now (the researcher
    /// may have stopped it on a metered connection).
    private static let stoppedKey = "whisperDownloadStoppedByUser"
    /// The researcher answered the size question (Download or Not Now), so it
    /// is never asked again on this install (App Review 4.2.3: the size is
    /// shown, and the researcher agrees, before a large download starts).
    private static let askedKey = "whisperDownloadAsked"
    /// The attempt in flight, if any (`WhisperModelAcquirer`).
    private var acquirer: WhisperModelAcquirer?
    /// Bumped by every download start, so a status probe that began before one
    /// cannot overwrite what the download then did (a stale `.missing` over a
    /// `.failed`, say).
    private var downloadEpoch = 0
    /// The probe in flight, if any, and whether someone asked again while it ran.
    private var probeTask: Task<Bool, Never>?
    private var probeAskedAgain = false
    private var rate = DownloadRate()
    /// `checkAtLaunch()` runs once per process, though every window's
    /// `onAppear` calls it.
    private var launched = false

    private var stoppedByUser: Bool {
        get { defaults.bool(forKey: Self.stoppedKey) }
        set { defaults.set(newValue, forKey: Self.stoppedKey) }
    }

    private var hasAnswered: Bool {
        get { defaults.bool(forKey: Self.askedKey) }
        set { defaults.set(newValue, forKey: Self.askedKey) }
    }

    /// Whether this build ships Whisper at all. The one place a build with
    /// Apple's model only (a store-build option, decided near 24 Nov 2026)
    /// turns the size question, and the download behind it, off.
    nonisolated static let whisperInBuild = true

    /// The size question, while it is on screen. A second ask is not stacked.
    private var isAsking = false
    /// Puts the size question to the researcher and answers true for Download.
    /// Set by the app, which holds the strings (`BristlenoseApp`). Unset, the
    /// app never asks and so never downloads on its own.
    var askToDownload: (@MainActor () async -> Bool)?

    private let defaults: UserDefaults
    /// Builds the acquirer for an attempt. `backgroundAssetsUsable` is false once Background
    /// Assets has failed in this process, so the same launch falls to the sidecar fetch.
    private let makeAcquirer: @MainActor (_ backgroundAssetsUsable: Bool) -> WhisperModelAcquirer
    /// Reset by every launch, and by Download Now: a failure sends THIS launch to the fallback,
    /// and the next opportunity asks Background Assets again.
    private var backgroundAssetsUsable = true
    /// Whether the current Stop came from `stop()` (the researcher) or from the system.
    private var stopAsked = false

    /// `shared` is the app's one. Tests build their own with a fake acquirer and a scratch
    /// defaults suite, so nothing they do reaches the real "stopped by user" memory.
    init(defaults: UserDefaults = .standard,
         makeAcquirer: @escaping @MainActor (_ backgroundAssetsUsable: Bool) -> WhisperModelAcquirer =
             WhisperDownloadModel.defaultAcquirer) {
        self.defaults = defaults
        self.makeAcquirer = makeAcquirer
        NotificationCenter.default.addObserver(
            forName: .bristlenoseAppleSpeechRunStarted, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.startIfNeeded() }
        }
        NotificationCenter.default.addObserver(
            forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.updateLowDisk() }
        }
        // A download the app quits on stops with it; the sidecar's own
        // parent-death watcher is the backstop for a crash.
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.acquirer?.appWillTerminate() }
        }
    }

    // MARK: Foundation's progress line

    /// "600.0 MB of 1.61 GB (10.0 MB/s)" then, on its own line, "About 2 minutes remaining", in
    /// the app's language (§3 H; measured 18 Oct 2026). Bytes alone until the rate window fills:
    /// no invented time.
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
            // Nothing reported yet (no byte, no total): say nothing rather than "Zero KB" beside
            // a bar that is already moving (build 6532). No invented figure.
            if done <= 0 { return "" }
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
        return Self.timeLeftOnItsOwnLine(p.localizedAdditionalDescription ?? "")
    }

    /// Foundation joins the byte/rate part and the time left with a spaced dash
    /// ("… (10.0 MB/s) — About 1 minute, 23 seconds remaining"). The popover wraps that badly and
    /// the dash is not ours to ship, so the time left goes on its own line. Only a spaced em or
    /// en dash is split; a language whose line has another separator is left as Foundation wrote it.
    nonisolated static func timeLeftOnItsOwnLine(_ line: String) -> String {
        for dash in [" \u{2014} ", " \u{2013} "] where line.contains(dash) {
            return line.replacingOccurrences(of: dash, with: "\n")
        }
        return line
    }

    var fractionDone: Double? {
        totalBytes > 0 ? min(1, Double(doneBytes) / Double(totalBytes)) : nil
    }

    // MARK: Lifecycle

    /// Free space below which the app does not start the 1.6 GB on its own
    /// (owner, 18 Oct 2026: "rude"). Download Now in Settings is not held by it.
    /// 20 GB until 30 Oct 2026, when it became 10: the download peaks at its final size,
    /// 1,539 MB with no scratch space on top (measured), so 10 GB leaves about 8 for
    /// projects and 20 was asking for a Mac the researcher was not using the room on.
    nonisolated static let autoStartFloorBytes: Int64 = 10_000_000_000

    enum AutoStart: Equatable {
        case nothing
        /// Show the size and ask first (once per install).
        case ask
        case start
    }

    /// What the app does by itself: only after the AI disclosure is
    /// acknowledged (owner, 22 Oct 2026), never over a Stop the researcher
    /// chose (Not Now is one), never while an analysis runs (it may be fetching
    /// the model itself, and two fetchers each write their own partial), only
    /// for a model missing or left partial, and only with room to spare.
    /// Unknown free space counts as room: no crying wolf. When all that holds,
    /// it asks first, unless the researcher already said Download.
    nonisolated static func autoStart(
        phase: Phase, freeBytes: Int64?, stoppedByUser: Bool, hasConsent: Bool, runIsLive: Bool,
        hasAnswered: Bool, whisperInBuild: Bool
    ) -> AutoStart {
        guard whisperInBuild, hasConsent, !stoppedByUser, !runIsLive else { return .nothing }
        guard phase == .missing || phase == .partial else { return .nothing }
        if let freeBytes, freeBytes < autoStartFloorBytes { return .nothing }
        return hasAnswered ? .start : .ask
    }

    /// Exactly the case `autoStart` gives up on for room alone: every other condition would have
    /// let it ask or fetch. Unknown free space counts as room, as there. A researcher's Not Now
    /// or Stop is theirs, so it is not a warning.
    nonisolated static func lowDiskBlocked(
        phase: Phase, freeBytes: Int64?, stoppedByUser: Bool, hasConsent: Bool, whisperInBuild: Bool,
        packModelChosen: Bool = true
    ) -> Bool {
        guard whisperInBuild, hasConsent, !stoppedByUser, packModelChosen else { return false }
        guard phase == .missing || phase == .partial else { return false }
        return belowFloor(freeBytes)
    }

    /// Unknown free space counts as room, as everywhere here.
    nonisolated static func belowFloor(_ freeBytes: Int64?) -> Bool {
        guard let freeBytes else { return false }
        return freeBytes < autoStartFloorBytes
    }

    /// Whether a RUN must not fetch the model for want of room. Wider than the warning: whatever
    /// the phase says (the launch probe may be out, a failure may be left over), only a model
    /// that is here or on its way is safe to leave alone. A cached model is still used under the
    /// marker, so this holds only the sessions that would have fetched.
    nonisolated static func noRoomToFetch(
        phase: Phase, freeBytes: Int64?, hasConsent: Bool, whisperInBuild: Bool
    ) -> Bool {
        guard whisperInBuild, hasConsent, phase != .onDisk, phase != .downloading else { return false }
        return belowFloor(freeBytes)
    }

    private func currentLowDiskBlocked() -> Bool {
        Self.lowDiskBlocked(phase: phase, freeBytes: freeDiskBytes(), stoppedByUser: stoppedByUser,
                            hasConsent: hasAIConsent(), whisperInBuild: Self.whisperInBuild,
                            packModelChosen: Self.chosenModelIsPackModel(defaults))
    }

    private func currentNoRoomToFetch() -> Bool {
        Self.noRoomToFetch(phase: phase, freeBytes: freeDiskBytes(), hasConsent: hasAIConsent(),
                           whisperInBuild: Self.whisperInBuild)
    }

    /// Re-reads free space. Called whenever the phase or a remembered answer changes, and when the
    /// app comes to the front (a researcher who has just cleared room sees the warning go).
    func updateLowDisk() {
        let now = currentLowDiskBlocked()
        guard now != lowDisk else { return }
        let wasBlocked = lowDisk
        lowDisk = now
        // Room appeared: do what the launch check would have done had there been room, so the
        // researcher who frees space is asked, or the download they already agreed to begins,
        // without a relaunch. Only once the launch check has run (consent, sidecar).
        if wasBlocked, launched { Task { @MainActor in await applyAutoStart() } }
    }

    /// At launch, and again when the AI disclosure is acknowledged: ask Python
    /// whether Whisper is on disk and, if not, start fetching it in the
    /// background, so the first analysis doesn't wait 1.6 GB after the key.
    /// Once per process; never under a test host, which is the real app.
    func checkAtLaunch() {
        // A build without Whisper asks nothing: no status probe, so no pill.
        guard Self.whisperInBuild, !launched, !KeychainHelper.isUnderTestHost,
              PipelineRunner.hasAIConsent else { return }
        launched = true
        // No sidecar to ask (the External Server dev scheme): nothing to fetch
        // with, and a failure pill every launch would say nothing true.
        guard Self.sidecar() != nil else { return }
        Task { @MainActor in
            await refresh()
            await applyAutoStart()
        }
    }

    /// What the app does by itself, given the model's phase and the remembered answers.
    func applyAutoStart() async {
        switch Self.autoStart(
            phase: phase, freeBytes: freeDiskBytes(),
            stoppedByUser: stoppedByUser, hasConsent: hasAIConsent(), runIsLive: runIsLive(),
            hasAnswered: hasAnswered, whisperInBuild: Self.whisperInBuild
        ) {
        case .nothing: break
        case .start: start()
        case .ask: await ask()
        }
    }

    /// The size question. Download starts it; Not Now is a remembered Stop, so
    /// the app leaves it alone until Download Now in Settings. Asked once: an
    /// answer either way is kept. A run that began while the question was up
    /// deferred its sessions that need Whisper (`runMustDefer`), so it is not
    /// fetching, and Download starts the download even with that run live.
    /// The size question as a standard alert, a sheet on the front window
    /// (Download is the default; Not Now is Cancel, so Escape answers it).
    static func alertAsk(i18n: I18n) -> @MainActor () async -> Bool {
        { @MainActor in
            let alert = NSAlert()
            alert.messageText = i18n.t("desktop.modelDownload.askTitle")
            alert.informativeText = i18n.t("desktop.modelDownload.askBody",
                                           ["size": i18n.t("desktop.modelDownload.askSize")])
            alert.addButton(withTitle: i18n.t("desktop.modelDownload.askDownload"))
            alert.addButton(withTitle: i18n.t("desktop.modelDownload.askNotNow"))
            let answer: NSApplication.ModalResponse
            if let window = PanelHost.window {
                answer = await alert.beginSheetModal(for: window)
            } else {
                answer = alert.runModal()
            }
            return answer == .alertFirstButtonReturn
        }
    }

    func ask() async {
        guard !isAsking, let askToDownload else { return }
        isAsking = true
        let download = await askToDownload()
        isAsking = false
        hasAnswered = true
        guard download else {
            stoppedByUser = true
            updateLowDisk()
            return
        }
        start()
    }

    /// Whether an analysis is running, set by the app (`PipelineRunner`). The
    /// launch check reads it after its own probe, so a run that started in
    /// that gap, and so fetched the model itself, is not joined by a second.
    var runIsLive: @MainActor () -> Bool = { false }

    /// The environment a pipeline run is given about the model: the sidecar fetch's pid to wait
    /// on while it runs; the host-owns marker when the app, not Python, delivers the model.
    var runEnvironment: [String: String] {
        var env = (acquirer ?? idleAcquirer).runEnvironment
        // Nothing is downloading and no verified pack is here, but the app would not start the
        // download itself (the researcher said Not Now, or has not been asked the size question):
        // the run must not fetch the model behind that. The marker makes Python defer each session
        // that needs Whisper ("Waiting for Whisper"); a model already in the cache is still used.
        if env.isEmpty, Self.runMustDefer(
            whisperInBuild: Self.whisperInBuild, packModelChosen: Self.chosenModelIsPackModel(defaults),
            stoppedByUser: stoppedByUser, hasAnswered: hasAnswered, questionReachable: questionReachable,
            noRoomToFetch: currentNoRoomToFetch()
        ) {
            env = Self.hostOwnsEnvironment
        }
        return env
    }

    /// Whether the size question is one the app can actually put: something to ask with, a
    /// sidecar to download with, the AI disclosure acknowledged, and room for the model.
    private var questionReachable: Bool {
        Self.questionReachable(
            askIsWired: askToDownload != nil, sidecarPresent: Self.sidecar() != nil,
            hasConsent: hasAIConsent(), freeBytes: freeDiskBytes())
    }

    nonisolated static func questionReachable(
        askIsWired: Bool, sidecarPresent: Bool, hasConsent: Bool, freeBytes: Int64?
    ) -> Bool {
        guard askIsWired, sidecarPresent, hasConsent else { return false }
        if let freeBytes, freeBytes < autoStartFloorBytes { return false }
        return true
    }

    /// A run that finds no Whisper model defers instead of fetching when the researcher has
    /// declined the download (Not Now or Stop), when the size question is still to be put and
    /// can be (`questionReachable`), or when there is too little room to fetch (`noRoomToFetch`:
    /// the warning pill is showing, and Download Now in Settings is the way out, so the wait has an
    /// exit). When the question can never be put for another reason (no sidecar) the run goes as
    /// it did before, so nothing waits for ever. Only the app's own model is held:
    /// another model is Python's to fetch. Download Now, or Download in the alert, lifts it.
    nonisolated static func runMustDefer(
        whisperInBuild: Bool, packModelChosen: Bool, stoppedByUser: Bool, hasAnswered: Bool,
        questionReachable: Bool, noRoomToFetch: Bool = false
    ) -> Bool {
        guard whisperInBuild, packModelChosen else { return false }
        return stoppedByUser || noRoomToFetch || (!hasAnswered && questionReachable)
    }

    /// What answers for the environment when nothing is downloading: the acquirer the picker
    /// would choose now, kept so a delivered pack is found without a download in flight.
    private var idleAcquirer: WhisperModelAcquirer {
        if let kept = idleCache, kept.kind == pickedKind { return kept }
        let made = makeAcquirer(backgroundAssetsUsable)
        idleCache = made
        return made
    }
    private var idleCache: WhisperModelAcquirer?
    private var pickedKind: WhisperAcquirerKind { Self.pickedKind(backgroundAssetsUsable: backgroundAssetsUsable) }

    /// Every input injectable, so the whole decision (including the chosen model and whether
    /// this build has Background Assets at all) is tested without a store build.
    nonisolated static func pickedKind(
        backgroundAssetsUsable: Bool,
        compiledIn: Bool = WhisperDownloadModel.backgroundAssetsCompiledIn,
        osMajor: Int = ProcessInfo.processInfo.operatingSystemVersion.majorVersion,
        channel: DistributionChannel = .current,
        killSwitchOn: Bool = BristlenoseFlags.backgroundAssets,
        defaults: UserDefaults = .standard
    ) -> WhisperAcquirerKind {
        WhisperAcquirerPicker.pick(
            osMajor: osMajor, channel: channel, killSwitchOn: killSwitchOn,
            backgroundAssetsUsable: backgroundAssetsUsable && compiledIn
                && chosenModelIsPackModel(defaults))
    }

    /// The app's one pack is `large-v3-turbo`. Another model chosen in Settings, or a
    /// repo id, is not the app's to deliver (Python fetches it as it always has), so Background
    /// Assets is neither used nor claimed for it. An unset preference is the default, turbo.
    nonisolated static func chosenModelIsPackModel(_ defaults: UserDefaults = .standard) -> Bool {
        let model = defaults.string(forKey: "whisperModel") ?? "large-v3-turbo"
        return model == "large-v3-turbo" || model == "turbo"
    }

    /// Background Assets is built only into the store build with the flag on
    /// (`BA_WHISPER`, never in the Developer-ID `.dmg`). Without it nothing here differs from
    /// the sidecar fetch.
    nonisolated static var backgroundAssetsCompiledIn: Bool {
        #if BA_WHISPER && !DEVELOPER_ID_BETA
        return true
        #else
        return false
        #endif
    }

    /// The picker's choice, built. Background Assets where the picker says so and this build has
    /// it; the sidecar fetch everywhere else.
    @MainActor
    static func defaultAcquirer(backgroundAssetsUsable: Bool) -> WhisperModelAcquirer {
        if pickedKind(backgroundAssetsUsable: backgroundAssetsUsable) == .backgroundAssets,
           let acquirer = makeBackgroundAssetsAcquirer() { return acquirer }
        return SidecarFetchAcquirer()
    }

    @MainActor
    private static func makeBackgroundAssetsAcquirer() -> WhisperModelAcquirer? {
        #if BA_WHISPER && !DEVELOPER_ID_BETA
        if #available(macOS 26, *) {
            return BackgroundAssetsAcquirer(adapter: AssetPackManagerAdapter(manifest: .largeV3Turbo))
        }
        #endif
        return nil
    }

    /// The marker that tells Python the app owns the model: it never fetches, it uses the
    /// directory the app sets or refuses (`bristlenose/preflight/whisper.py`).
    nonisolated static let hostOwnsEnvironment = ["_BRISTLENOSE_WHISPER_HOST_OWNS": "1"]

    /// What a run needs to wait on the app's download rather than fetch its own.
    nonisolated static func whisperFetchEnvironment(pid: pid_t?) -> [String: String] {
        guard let pid else { return [:] }
        return ["_BRISTLENOSE_WHISPER_FETCH_PID": String(pid)]
    }

    /// A run went to Apple's model (the sidecar printed `@transcription-engine
    /// apple`): fetch Whisper behind it, unless it is here, coming, or stopped.
    ///
    /// Only once the researcher has said Download: this fires during a run,
    /// when the size question is not put (it waits for the next launch).
    func startIfNeeded() {
        guard Self.whisperInBuild, BristlenoseFlags.appleSpeechAvailable,
              !stoppedByUser, hasAnswered else { return }
        switch phase {
        case .downloading, .onDisk: return
        case .unknown:
            Task { @MainActor in
                await refresh()
                if phase != .onDisk && phase != .downloading && !currentNoRoomToFetch() { start() }
            }
        case .missing, .partial, .failed:
            // The floor holds here as it does at launch: a run is not a reason to start 1.6 GB
            // into a nearly full disk. The warning pill says so; Download Now is the way past it.
            guard !currentNoRoomToFetch() else { return }
            start()
        }
    }

    /// Download Now / Retry: the researcher asked, so a remembered Stop is
    /// forgotten. Single-flight.
    func downloadNow() {
        stoppedByUser = false
        hasAnswered = true
        updateLowDisk()
        if acquirer == nil { backgroundAssetsUsable = true }  // a fallback fetch in flight stays
        start()
    }

    private func start() {
        // A build without Whisper has no acquirer at all, whatever the picker would say.
        guard Self.whisperInBuild, acquirer == nil else { return }
        downloadEpoch += 1
        probeAskedAgain = false  // a re-ask that predates this download is moot: its outcome stands
        let next = makeAcquirer(backgroundAssetsUsable)
        guard next.isAvailable else {
            Self.logger.error("whisper download: no sidecar to run (bundle or dev path missing)")
            phase = .failed
            return
        }
        failureCause = nil
        stopAsked = false
        rate.reset()
        doneBytes = 0
        totalBytes = 0
        bytesPerSecond = nil
        minutesLeft = nil
        phase = .downloading
        acquirer = next
        if !next.start(events: self) {
            acquirer = nil
            phase = .failed
        }
    }

    /// Stop. The Hugging Face fetch has no resume (hf_xet starts again); the system's own
    /// delivery says nothing either way, and the popover carries no note about it. SIGINT
    /// first — `ensure_hf_model` aborts hf_xet within about 2 s — then SIGKILL if it hasn't gone.
    func stop() {
        guard let acquirer, acquirer.isRunning else { return }
        stoppedByUser = true
        stopAsked = true
        updateLowDisk()
        acquirer.stop()
    }

    /// Ask Python whether Whisper is on disk. Never computes the cache path
    /// here. A probe that cannot answer is said (`.failed`, logged with the
    /// sidecar's own words), never left as a blank. Moving to `.onDisk` from
    /// anything else announces Whisper ready, which re-runs waiting projects —
    /// at launch as much as after a download.
    ///
    /// One probe at a time. A call that arrives while one is running does not
    /// start a second, unordered one (the one that finished last used to win,
    /// so a stale "on disk" could hide the row after the Model changed). It
    /// marks the running probe stale; that probe asks again, with the
    /// preferences as they are by then, and every waiting caller gets the last
    /// answer. The launch check reads `phase` straight after this, so a caller
    /// that is overtaken must wait for the newest answer, not return early.
    @discardableResult
    func refresh() async -> Bool {
        if let running = probeTask {
            probeAskedAgain = true
            return await running.value
        }
        let task = Task { @MainActor in
            var answered = false
            repeat {
                probeAskedAgain = false
                answered = await probeOnce()
            } while probeAskedAgain
            probeTask = nil
            return answered
        }
        probeTask = task
        return await task.value
    }

    private func probeOnce() async -> Bool {
        guard acquirer == nil else { return phase == .onDisk }
        guard let (binary, mode) = Self.sidecar() else {
            Self.logger.error("whisper status: no sidecar to ask")
            phase = .failed
            return false
        }
        failureCause = nil  // a failed probe is not the last download's failure
        let epoch = downloadEpoch
        let answer = await Self.askStatus(binary: binary, mode: mode, extra: runEnvironment)
        // A download started meanwhile, and may even have ended: its outcome
        // stands.
        guard acquirer == nil, epoch == downloadEpoch else { return false }
        // Someone asked again while this ran, so this answer is already stale:
        // do not apply it, or announce Whisper ready for a model that is no
        // longer the one chosen. The loop in `refresh()` probes again.
        guard !probeAskedAgain else { return false }
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
    private nonisolated static func askStatus(
        binary: URL, mode: SidecarMode, extra: [String: String]
    ) async -> StatusAnswer {
        let env = await MainActor.run {
            BristlenoseShared.childEnvironment(for: mode).merging(extra) { _, new in new }
        }
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
                // SIGTERM at 60 s, then SIGKILL at +5 s as `stop()` does: a probe
                // that never returned would now hold every later `refresh()`.
                let deadline = DispatchWorkItem {
                    guard proc.isRunning else { return }
                    proc.terminate()
                    let pid = proc.processIdentifier
                    DispatchQueue.global().asyncAfter(deadline: .now() + 5) {
                        if proc.isRunning { kill(pid, SIGKILL) }
                    }
                }
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
    nonisolated static func readLines(_ handle: FileHandle,
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

    /// The researcher's Stop ended a Background Assets attempt that also reported a failure.
    private func acquisitionEndedAfterStop() {
        phase = .unknown
        Task { @MainActor in await refresh() }
    }

    // MARK: Events from the acquirer

    func acquisitionTotal(_ bytes: Int64, from sender: WhisperModelAcquirer) {
        guard sender === acquirer else { return }
        totalBytes = bytes
    }

    func acquisitionProgress(done: Int64, total: Int64, from sender: WhisperModelAcquirer) {
        guard sender === acquirer else { return }
        doneBytes = done
        if total > 0 { totalBytes = total }
        rate.add(time: ProcessInfo.processInfo.systemUptime, bytes: done)
        bytesPerSecond = rate.bytesPerSecond
        minutesLeft = rate.minutesLeft(done: done, total: totalBytes)
    }

    func acquisitionEnded(_ outcome: WhisperAcquisitionOutcome, from sender: WhisperModelAcquirer) {
        guard let ended = acquirer, sender === ended else { return }
        acquirer = nil
        // Background Assets failed: this launch goes to the sidecar fetch, now, so the researcher
        // is not left with nothing. The next opportunity (a launch, Download Now) asks again.
        if case .failed = outcome, ended.kind == .backgroundAssets, stopAsked {
            // Stop landed together with a failure: the researcher's Stop wins, nothing starts.
            acquisitionEndedAfterStop()
            return
        }
        if case .failed = outcome, ended.kind == .backgroundAssets {
            Self.logger.error("background assets failed; falling back to the sidecar fetch for this launch")
            backgroundAssetsUsable = false
            start()
            return
        }
        // A stop nobody here asked for (the system cancelled it) is not the researcher's Stop:
        // it is not remembered, so the next opportunity (launch, run, Download Now) tries again.
        // `stop()` already remembered the researcher's own.
        switch outcome {
        case .succeeded, .stopped:
            // Off `.downloading` before asking, so a probe that fails leaves
            // `.failed`, never a pill frozen on its last bytes.
            phase = .unknown
            Task { @MainActor in await refresh() }
        case .failed(let cause):
            failureCause = cause
            phase = .failed
        }
    }

    /// The sidecar binary and mode, resolved exactly as a run resolves them.
    static func sidecar() -> (URL, SidecarMode)? {
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
