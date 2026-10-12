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
    /// must still be there afterwards.
    @Test func aLiveOwnedRunIsRecognisedAndItsFileKept() throws {
        let p = project()
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        let url = try writePIDFile("\(getpid())\n\(start)\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }

        let found = PipelineRunner.aliveOwnedRunPID(for: p)

        #expect(found == getpid(), "a live run of ours was not recognised")
        #expect(FileManager.default.fileExists(atPath: url.path), "the PID file was deleted on a check that should have passed")
    }

    /// A file from a build before the start token existed: pid alone. Accepted
    /// on uid, so an upgrade mid-run still attaches.
    @Test func aLegacyPidOnlyFileIsStillRecognised() throws {
        let p = project()
        let url = try writePIDFile("\(getpid())\n", for: p)
        defer { try? FileManager.default.removeItem(at: url) }
        #expect(PipelineRunner.aliveOwnedRunPID(for: p) == getpid())
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
                         start: String? = "100.200") -> PipelineRunner.OwnedRunVerdict {
        PipelineRunner.ownedRunVerdict(
            pidFileContents: contents,
            isAlive: { _ in alive },
            processUID: { _ in uid },
            startTime: { _ in start },
            currentUID: 501)
    }

    @Test func verdictTable() {
        #expect(verdict("42\n100.200") == .alive(42))
        #expect(verdict("42\n100.200\n") == .alive(42))
        #expect(verdict("42") == .alive(42), "legacy pid-only file")
        #expect(verdict("42\n100.201") == .stale, "start token differs — reused pid")
        #expect(verdict("42\n100.200", alive: false) == .stale)
        #expect(verdict("42\n100.200", uid: 502) == .stale, "another user's process")
        #expect(verdict("42\n100.200", uid: nil) == .indeterminate, "uid query failed")
        #expect(verdict("42\n100.200", start: nil) == .indeterminate, "start query failed")
        #expect(verdict("garbage") == .stale)
        #expect(verdict("") == .stale)
        #expect(verdict("-3\n1.2") == .stale)
    }
}
