import Darwin
import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "pipeline")

/// Where the run queue is kept between launches.
protocol RunQueueStoring: AnyObject {
    func load() -> PersistedRunQueue?
    func save(_ queue: PersistedRunQueue)
}

/// The app's store: one JSON value in the app's defaults, beside the other
/// app-level state (the selected project, the active provider). Not
/// `projects.json`: the queue is the runner's, not a fact about a project.
///
/// Holds the queue lock for the life of the process. Only one running copy of
/// the app may read or write the queue (decisions-pending #12): a second
/// instance has its own runner, and its view of the queue is not the one to
/// restore.
final class DefaultsRunQueueStore: RunQueueStoring {
    static let key = "runQueue.v1"

    private let defaults: UserDefaults
    private let lock: RunQueueLock?

    init(defaults: UserDefaults, lock: RunQueueLock?) {
        self.defaults = defaults
        self.lock = lock
    }

    func load() -> PersistedRunQueue? {
        guard let data = defaults.data(forKey: Self.key) else { return nil }
        guard let queue = try? JSONDecoder().decode(PersistedRunQueue.self, from: data),
              queue.schema == PersistedRunQueue.currentSchema else {
            log.error("run queue: the saved queue could not be read — not restored")
            return nil
        }
        return queue
    }

    func save(_ queue: PersistedRunQueue) {
        do {
            defaults.set(try JSONEncoder().encode(queue), forKey: Self.key)
        } catch {
            log.error("run queue: could not save the queue: \(error.localizedDescription, privacy: .public)")
        }
    }

    /// The store for this process, or nil when this process must not touch the
    /// queue: under a test host (the host is the real app, and a test must
    /// neither restore a developer's queue nor write one), or when another
    /// copy of the app holds the lock. Made once: a second `flock` from this
    /// process would be refused by its own first.
    @MainActor static let live: DefaultsRunQueueStore? = {
        guard !KeychainHelper.isUnderTestHost else { return nil }
        let support = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first!.appendingPathComponent("Bristlenose")
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        guard let lock = RunQueueLock(url: support.appendingPathComponent("run-queue.lock")) else {
            log.notice("run queue: no queue lock (another copy of the app holds it, or see the error above) — this copy neither restores nor keeps the queue")
            return nil
        }
        return DefaultsRunQueueStore(defaults: .standard, lock: lock)
    }()
}

/// An exclusive `flock` on a file, held until this object goes. The kernel
/// drops it when the process exits or crashes, so a stale lock cannot outlive
/// its holder.
final class RunQueueLock {
    private let fd: Int32

    /// Nil when another holder has it, or the file can't be opened.
    init?(url: URL) {
        let fd = open(url.path, O_RDWR | O_CREAT | O_CLOEXEC, 0o600)
        guard fd >= 0 else {
            log.error("run queue: could not open the lock file errno=\(errno, privacy: .public)")
            return nil
        }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else {
            let err = errno
            if err != EWOULDBLOCK {
                log.error("run queue: could not lock the lock file errno=\(err, privacy: .public)")
            }
            close(fd)
            return nil
        }
        self.fd = fd
    }

    deinit {
        flock(fd, LOCK_UN)
        close(fd)
    }
}

/// A store that keeps the queue in memory. For tests.
final class InMemoryRunQueueStore: RunQueueStoring {
    var saved: PersistedRunQueue?
    private(set) var saves = 0

    init(_ saved: PersistedRunQueue? = nil) { self.saved = saved }

    func load() -> PersistedRunQueue? { saved }

    func save(_ queue: PersistedRunQueue) {
        saved = queue
        saves += 1
    }
}

/// The runner's record of when each waiting study was asked for, and the
/// queue as last written. Written on every change to the queue or the run in
/// flight, so a crash leaves the last one on disk; frozen at Quit, so nothing a
/// quitting app does afterwards (the stopped run's exit) reads as the
/// researcher taking a study out.
@MainActor
final class RunQueueJournal {
    struct Stamp: Equatable, Sendable {
        let at: Date
        let studyID: String?
    }

    private(set) var stamps: [UUID: Stamp] = [:]
    private(set) var store: (any RunQueueStoring)?
    private(set) var frozen = false
    private(set) var restoreStarted = false
    private var lastWritten: PersistedRunQueue?
    var now: () -> Date = { Date() }

    /// Record when `id` was asked for. `fresh` false keeps an earlier stamp:
    /// a second Analyse on a study already waiting is the same request.
    func stamp(_ id: UUID, studyID: String?, fresh: Bool, as given: Stamp? = nil) {
        if let given {
            stamps[id] = given
        } else if fresh || stamps[id] == nil {
            stamps[id] = Stamp(at: now(), studyID: studyID)
        }
    }

    /// Attach the store the queue is restored from and kept in, once per
    /// process; false when one is already attached.
    func attach(_ store: any RunQueueStoring) -> Bool {
        guard !restoreStarted else { return false }
        restoreStarted = true
        self.store = store
        lastWritten = store.load()
        return true
    }

    func freeze() { frozen = true }

    /// Write the queue as it stands: `inFlight` is the run whose process is
    /// live and was not stopped. Stamps are never pruned here: a study popped
    /// from the queue is in neither list until its run is spawned, and pruning
    /// it then lost its request time (review, 20 Oct 2026). `start` decides
    /// fresh or kept, so an old stamp is never reused for a new request.
    func write(inFlight: (id: UUID, clean: Bool)?, queued: [RunQueue.Entry]) {
        guard !frozen, let store else { return }
        var entries: [PersistedQueueEntry] = []
        if let inFlight {
            entries.append(entry(inFlight.id, clean: inFlight.clean, inFlight: true))
        }
        for waiting in queued {
            entries.append(entry(waiting.id, clean: waiting.clean, inFlight: false))
        }
        let snapshot = PersistedRunQueue(entries: entries)
        guard snapshot != lastWritten else { return }
        store.save(snapshot)
        lastWritten = snapshot
    }

    private func entry(_ id: UUID, clean: Bool, inFlight: Bool) -> PersistedQueueEntry {
        if stamps[id] == nil {
            // Every way into the queue stamps first; a gap is a defect, and
            // the request is kept from now rather than lost.
            log.fault("run queue: no request time for project=\(id.uuidString, privacy: .public) — stamped now")
            stamps[id] = Stamp(at: now(), studyID: nil)
        }
        let stamp = stamps[id]!
        return PersistedQueueEntry(
            projectID: id, clean: clean, enqueuedAt: stamp.at,
            studyID: stamp.studyID, inFlight: inFlight
        )
    }
}
