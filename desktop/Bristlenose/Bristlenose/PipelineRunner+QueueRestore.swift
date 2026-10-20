import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "pipeline")

extension PipelineRunner {
    /// Bring back the queue the app kept at its last Quit or crash, and keep
    /// the queue in `store` from here on (R19 follow-up, 20 Oct 2026).
    ///
    /// Each kept study is judged by `QueueRestorePolicy`; the ones it honours
    /// are started again in their old order, the run that was in flight first,
    /// each with its old request time and `--clean`. The rest are dropped with
    /// a log line and nothing on screen. Once per process: a second window's
    /// call does nothing.
    ///
    /// - Parameters:
    ///   - evidence: what a study's folder says now. Read off-main from the
    ///     folder by default; a test passes its own.
    ///   - outsideRunPatience: how long to wait for the run Quit stopped to
    ///     finish stopping. SIGINT can wait on a long transcription call, and a
    ///     relaunch inside that time finds it still live: `start` would turn the
    ///     study away and the queue would lose it, as if Quit were a Stop.
    func restoreQueue(
        from store: any RunQueueStoring, index: ProjectIndex,
        evidence: ((Project) async -> QueueRestorePolicy.DiskEvidence)? = nil,
        outsideRunPatience: Duration = .seconds(120)
    ) async {
        let saved = store.load()
        guard queueJournal.attach(store) else { return }
        guard let saved, !saved.entries.isEmpty else { return }
        let now = queueJournal.now()
        var kept: [PersistedQueueEntry] = []
        for entry in saved.entries {
            var project = index.projects.first { $0.id == entry.projectID }
            var decision = QueueRestorePolicy.decide(
                entry, now: now, project: project, availability: project?.availability, evidence: nil
            )
            if decision == .restore, let found = project {
                let read = await (evidence ?? { await self.diskEvidence(for: $0, index: index) })(found)
                // The read can take seconds: ask the sidebar again.
                project = index.projects.first { $0.id == entry.projectID }
                decision = QueueRestorePolicy.decide(
                    entry, now: now, project: project, availability: project?.availability, evidence: read
                )
            }
            switch decision {
            case .restore:
                kept.append(entry)
            case .drop(let reason):
                log.notice(
                    "run queue: not restored project=\(entry.projectID.uuidString, privacy: .public) reason=\(reason.rawValue, privacy: .public)"
                )
            }
        }
        // A relaunch that needs the AI disclosure acknowledged again (a new
        // consent version) shows it as at any launch; the queue waits for it
        // rather than being turned away by `start` and lost. The sheet cannot
        // be dismissed any other way, so this wait has no limit.
        if !kept.isEmpty, !hasAIConsentNow {
            log.notice("run queue: \(kept.count, privacy: .public) queued run(s) waiting for the AI disclosure")
            while !hasAIConsentNow {
                try? await Task.sleep(for: .milliseconds(250))
            }
        }
        // Let the launch scan of these studies finish first: it reads, and may
        // sweep, the PID file the stopped run left, and a run started under it
        // writes a new one there.
        let settled = ContinuousClock.now + Self.scanTimeout + .seconds(1)
        while kept.contains(where: { state[$0.projectID] == .scanning }), ContinuousClock.now < settled {
            try? await Task.sleep(for: .milliseconds(50))
        }
        // …and the run Quit stopped to finish stopping. In order: nothing
        // behind it starts first.
        let stopped = ContinuousClock.now + outsideRunPatience
        while kept.contains(where: { hasOutsideRun($0.projectID) }), ContinuousClock.now < stopped {
            try? await Task.sleep(for: .milliseconds(100))
        }
        for entry in kept {
            guard let project = index.projects.first(where: { $0.id == entry.projectID }) else {
                log.notice("run queue: not restored project=\(entry.projectID.uuidString, privacy: .public) reason=notInSidebar")
                continue
            }
            if hasOutsideRun(project.id) {
                log.notice("run queue: not restored project=\(project.id.uuidString, privacy: .public) reason=earlierRunStillLive")
                continue
            }
            start(
                project: project, clean: entry.clean,
                requested: .init(at: entry.enqueuedAt, studyID: entry.studyID ?? project.studyID)
            )
        }
        // What actually started: `start` can still turn a study away (no AI
        // consent, no API key, folder gone), each with its own log line.
        let started = kept.filter { entry in
            switch state[entry.projectID] {
            case .running, .queued: return true
            default: return false
            }
        }.count
        log.info("run queue: restored \(started, privacy: .public) of \(saved.entries.count, privacy: .public)")
        // With nothing restored no start writes, and the lapsed queue would be
        // read, and dropped, at every launch.
        journalQueue()
    }

    /// What `project`'s folder says now: its study id and whether it has
    /// anything to analyse. Unknown when the read outlasts `scanTimeout` (a
    /// sleeping network share), which the policy does not count as gone.
    private func diskEvidence(
        for project: Project, index: ProjectIndex
    ) async -> QueueRestorePolicy.DiskEvidence {
        let folder = index.leaseURL(projectID: project.id) ?? URL(fileURLWithPath: project.path)
        let reading = Task.detached { () -> QueueRestorePolicy.DiskEvidence in
            QueueRestorePolicy.DiskEvidence(
                studyIDOnDisk: StudyMarker.read(folder: folder),
                inputs: QueueRestorePolicy.ingestableFile(under: folder)
            )
        }
        guard let read = await Self.value(of: reading, within: Self.scanTimeout) else {
            log.notice("run queue: a queued study's folder was slow to read project=\(project.id.uuidString, privacy: .public)")
            return .init(studyIDOnDisk: nil, inputs: .unknown)
        }
        return read
    }
}
