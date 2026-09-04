import Darwin
import Foundation
import Testing

@testable import Bristlenose

/// Measures the ONE fact nobody had: the dataless-file materialisation policy
/// INSIDE the sandboxed app process. The kernel decides whether touching a
/// cloud-evicted file blocks-and-downloads (policy ON, value 2) or fails
/// instantly with EDEADLK/errno 11 (policy OFF, 0 or 1). A process inherits
/// it across spawn — so whatever this reports is also what the sidecar gets.
///
/// Measured 4 Sep 2026: **2 (ON)**, sandboxed. Every conclusion in
/// docs/design-copy-error-surfacing.md §5 and the copyItem gotcha in
/// desktop/CLAUDE.md rests on that value — so this is a CANARY, not a probe:
/// it asserts ON. If Apple ever changes the inherited default, or a launch
/// path stops inheriting it, the suite goes red and the reader is sent to the
/// doc, instead of the app silently switching from "hangs" to "fails with
/// EDEADLK" with nobody noticing.
struct DatalessPolicyProbeTests {

    private func record(_ label: String, _ value: String) {
        let f = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-error-probe.txt")
        let line = "\(label): \(value)\n"
        if let h = try? FileHandle(forWritingTo: f) {
            h.seekToEndOfFile(); h.write(line.data(using: .utf8)!); try? h.close()
        } else {
            try? line.write(to: f, atomically: true, encoding: .utf8)
        }
        print("PROBE \(line)", terminator: "")
    }

    @Test("record the materialisation policy the sandboxed host runs under")
    func recordMaterialisationPolicy() {
        let type = IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES
        let proc = getiopolicy_np(type, IOPOL_SCOPE_PROCESS)
        let thr  = getiopolicy_np(type, IOPOL_SCOPE_THREAD)
        let sandboxed = ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] != nil
        record("dataless.policy.process", "\(proc)  (2=ON block+materialise, 0/1=OFF -> EDEADLK 11)")
        record("dataless.policy.thread",  "\(thr)")
        record("dataless.policy.sandboxed", "\(sandboxed)  container=\(ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] ?? "-")")
        record("dataless.policy.errno.EDEADLK", "\(EDEADLK)")
        record("dataless.policy.errno.EAGAIN", "\(EAGAIN)")
        #expect(
            proc == IOPOL_MATERIALIZE_DATALESS_FILES_ON,
            "dataless materialisation policy changed from ON (2) to \(proc) — re-read docs/design-copy-error-surfacing.md §5 before touching anything"
        )
    }
}
