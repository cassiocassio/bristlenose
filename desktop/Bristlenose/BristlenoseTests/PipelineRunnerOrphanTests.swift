import Foundation
import Testing
@testable import Bristlenose

/// Orphan attach on relaunch: the PID file the app wrote for a run must survive
/// a check that could not complete, and a live run of ours must be found.
///
/// `aliveOwnedRunPID` verified ownership by exec'ing `/bin/ps`, which App
/// Sandbox refuses (`ENABLE_APP_SANDBOX = YES` on both configurations, and the
/// exec measured `Operation not permitted` from the sandboxed test host on
/// 12 Oct 2026). The failed exec read as "not ours" and **deleted the PID
/// file**, so a relaunch mid-run could never attach: the row showed Analysing
/// with an inert Stop, and Analyse could spawn a second run against the same
/// folder. Ownership is now libproc (`proc_pidinfo`), and the file is written
/// with the process start-time token so a reused pid cannot match.
struct PipelineRunnerOrphanTests {

    private func project() -> Project {
        Project(id: UUID(), name: "Orphan", path: "/p/orphan")
    }

    private func writePIDFile(_ contents: String, for p: Project) throws -> URL {
        let url = PipelineRunner.pidFileURL(for: p)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(contents.utf8).write(to: url, options: .atomic)
        return url
    }

    // MARK: - The file-level check, against this process

    /// Our own process: alive, our uid, and recorded by the same libproc query
    /// the production check reads with. It must be recognised, and the file
    /// must still be there afterwards. Its parent is reported as launchd, as an
    /// orphan's is once its app has gone.
    @Test func aLiveOwnedRunIsRecognisedAndItsFileKept() throws {
        let p = project()
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        let url = try writePIDFile("\(getpid())\n\(start)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }

        let found = PipelineRunner.aliveOwnedRunPID(for: p, parentPID: { _ in 1 })

        #expect(found == getpid(), "a live run of ours was not recognised")
        #expect(FileManager.default.fileExists(atPath: url.path), "the PID file was deleted on a check that should have passed")
    }

    /// Decision #12: a second copy of the app (a Debug build beside the
    /// installed one shares the container) found the first copy's live run and
    /// attached it, so its Stop and its ⌘Q signalled a run it did not start. A
    /// run whose parent is alive is another copy's: not attached, file kept.
    /// This process stands in for that run; its parent is reported as another
    /// process (a dead parent would read 1: the kernel reparents at once).
    @Test func aLiveRunOfAnotherCopyIsNotAttachedAndItsFileKept() throws {
        let p = project()
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        let url = try writePIDFile("\(getpid())\n\(start)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }

        #expect(PipelineRunner.aliveOwnedRunPID(for: p, parentPID: { _ in 4242 }) == nil, "attached another copy's live run")
        #expect(FileManager.default.fileExists(atPath: url.path), "deleted the PID file of another copy's live run")
    }

    /// The probe reads the kernel's parent, as `getppid` does.
    @Test func theParentProbeReadsTheRealParent() {
        #expect(EventLogReader.procParentPID(pid: getpid()) == getppid())
    }

    /// The same, through the scan: it reads the study off disk instead of
    /// attaching, and leaves the other copy's file in place.
    @Test func aScanOfAnotherCopysRunReadsDiskAndKeepsTheFile() async throws {
        let p = project()
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        let url = try writePIDFile("\(getpid())\n\(start)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        let manifest = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-orphan-scan-\(UUID().uuidString)/pipeline-manifest.json")

        let outcome = await PipelineRunner.performScan(
            project: p, manifestURL: manifest, parentPID: { _ in 4242 })

        if case .orphan = outcome { Issue.record("attached another copy's live run") }
        #expect(FileManager.default.fileExists(atPath: url.path))
    }

    /// A file from a build before the start token existed: pid alone. Stale,
    /// not ours: without the token a reused pid would match on uid alone and
    /// Stop would SIGKILL whatever holds it now (review finding 9).
    @Test func aLegacyPidOnlyFileIsStaleAndRemoved() throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        #expect(PipelineRunner.aliveOwnedRunPID(for: p) == nil)
        #expect(!FileManager.default.fileExists(atPath: url.path))
    }

    /// The caller's half of the keep-file rule. `performScan` used to sweep the
    /// PID file on any nil, which deleted a file the callee had just decided
    /// to keep (review finding 1). Indeterminate here means the file survives
    /// the whole scan, not just the verdict.
    @Test func aScanWithAnIndeterminateCheckKeepsTheFile() async throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\n\(PipelineRunner.noStartToken)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        let manifest = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-orphan-scan-\(UUID().uuidString)/pipeline-manifest.json")

        let outcome = await PipelineRunner.performScan(
            project: p, manifestURL: manifest, startTime: { _ in nil })

        if case .orphan = outcome { Issue.record("an indeterminate check attached as an orphan") }
        #expect(FileManager.default.fileExists(atPath: url.path), "performScan deleted a PID file the verdict said to keep")
    }

    /// A spawn whose libproc query failed writes the sentinel, never an empty
    /// line — an empty line is the legacy shape, which is stale.
    @Test func theNoTokenSentinelIsIndeterminateNotStale() throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\n\(PipelineRunner.noStartToken)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        #expect(PipelineRunner.aliveOwnedRunPID(for: p) == nil)
        #expect(FileManager.default.fileExists(atPath: url.path))
    }

    /// A check that cannot finish is not a verdict. The file stays.
    @Test func anIndeterminateCheckKeepsTheFile() throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\nsome-start-token\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }

        let found = PipelineRunner.aliveOwnedRunPID(for: p, startTime: { _ in nil })

        #expect(found == nil)
        #expect(FileManager.default.fileExists(atPath: url.path), "an indeterminate check deleted the PID file")
    }

    /// A pid the kernel has reused for another of our processes: alive, our
    /// uid, different incarnation. Stale, and the file goes.
    @Test func aReusedPidIsStaleAndItsFileRemoved() throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\nnot-this-incarnation\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }

        #expect(PipelineRunner.aliveOwnedRunPID(for: p) == nil)
        #expect(!FileManager.default.fileExists(atPath: url.path))
    }

    @Test func aDeadPidIsStaleAndItsFileRemoved() throws {
        let p = project()
        let url = try writePIDFile("999999\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        #expect(PipelineRunner.aliveOwnedRunPID(for: p) == nil)
        #expect(!FileManager.default.fileExists(atPath: url.path))
    }

    // MARK: - The verdict table, with every probe injected

    private func verdict(_ contents: String,
                         alive: Bool = true,
                         uid: uid_t? = 501,
                         start: String? = "100.200",
                         parent: pid_t? = 1) -> PipelineRunner.OwnedRunVerdict {
        PipelineRunner.ownedRunVerdict(
            pidFileContents: contents,
            isAlive: { _ in alive },
            processUID: { _ in uid },
            startTime: { _ in start },
            parentPID: { _ in parent },
            currentUID: 501,
            currentPID: 777)
    }

    @Test func verdictTable() {
        #expect(verdict("42\n100.200") == .alive(42))
        #expect(verdict("42\n100.200\n") == .alive(42))
        #expect(verdict("42") == .stale, "legacy pid-only file: no token, no attach")
        #expect(verdict("42\n") == .stale, "empty token line is the legacy shape")
        #expect(verdict("42\n\(PipelineRunner.noStartToken)") == .indeterminate, "sentinel: could not verify")
        #expect(verdict("42\n100.201") == .stale, "start token differs — reused pid")
        #expect(verdict("42\n100.200", alive: false) == .stale)
        #expect(verdict("42\n100.200", uid: 502) == .stale, "another user's process")
        #expect(verdict("42\n100.200", uid: nil) == .indeterminate, "uid query failed")
        #expect(verdict("42\n100.200", start: nil) == .indeterminate, "start query failed")
        #expect(verdict("42\n100.200", parent: 4242) == .ownedByAnotherCopy, "its app is still running")
        #expect(verdict("42\n100.200", parent: nil) == .indeterminate, "parent query failed")
        #expect(verdict("42\n100.200", parent: 777) == .alive(42), "this process's own spawn is ours, not another copy's")
        #expect(verdict("42\n100.201", parent: 4242) == .stale, "a reused pid is stale whoever its parent")
        #expect(verdict("garbage") == .stale)
        #expect(verdict("") == .stale)
        #expect(verdict("-3\n1.2") == .stale)
    }
}
