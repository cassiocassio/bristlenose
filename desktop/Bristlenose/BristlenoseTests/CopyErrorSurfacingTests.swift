import Foundation
import Testing

@testable import Bristlenose

/// Probes for how `CopyMachinery.CopyError` reaches a researcher — written to
/// MEASURE the two catch sites in `ContentView`, not to assert a design.
///
/// The two sites diverge (`git blame`: site 1 was written whole in `0ac2136d`
/// without the `.underlying` arm site 2 has):
///
///   site 1 (loose files → new project)   `catch { toast.show(error.localizedDescription) }`
///   site 2 (drop onto existing project)  `catch .underlying(let msg) { toast.show(msg) }`
///
/// So the SAME error renders two different strings depending on which gesture
/// the researcher used. These tests pin what each site shows today. The
/// defect is recorded with `withKnownIssue`: when it is fixed, Swift Testing
/// reports "known issue did not occur" and this file must be updated — which
/// is the intended signal, not a nuisance. Diagnosis and the proposed fix:
/// `docs/design-copy-error-surfacing.md`.
@MainActor
struct CopyErrorSurfacingTests {

    private func makeTempDir() -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-error-probe-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// Write a measured string somewhere a sandboxed test host can actually
    /// write (NOT /tmp — see the App-Sandbox gotcha in root CLAUDE.md).
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

    // MARK: - Site 1: the bare enum's localizedDescription

    @Test("site 1 exposure: .underlying's REASON is discarded by error.localizedDescription")
    func site1DiscardsTheReason() {
        let reason = "You don’t have permission to save the file “P07.mp4” in the folder “Interviews”."
        let err = CopyMachinery.CopyError.underlying(reason)
        let shown = err.localizedDescription
        record("site1.underlying", shown)

        // Sanity: it is a string, and it is not empty.
        #expect(!shown.isEmpty)

        // THE DEFECT. Site 1 has no `.underlying` arm, so this is what the
        // toast shows. It should carry the reason. It does not.
        withKnownIssue("site 1 renders Foundation's enum-index string, not the wrapped reason") {
            #expect(shown.contains(reason))
        }
    }

    @Test("site 1 exposure: the 'already in flight' literal is also lost at site 1")
    func site1LosesTheInFlightLiteral() {
        // `copy()` throws this as `.underlying("Another copy is already in flight.")`
        // — an unlocalised Swift literal (no locale key exists; grep confirms).
        let err = CopyMachinery.CopyError.underlying("Another copy is already in flight.")
        let shown = err.localizedDescription
        record("site1.inFlight", shown)
        withKnownIssue("even the hardcoded English is discarded at site 1") {
            #expect(shown.contains("in flight"))
        }
    }

    // MARK: - Site 2: what the wrapped Foundation message actually says

    @Test("site 2 exposure: a real permission failure's wrapped message")
    func site2WrappedMessageForPermissionFailure() async throws {
        let root = makeTempDir()
        defer {
            // restore so cleanup can delete it
            try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: root.path)
            try? FileManager.default.removeItem(at: root)
        }
        let srcDir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: srcDir) }
        let src = srcDir.appendingPathComponent("P07.mp4")
        try Data("not really video".utf8).write(to: src)

        // Make the destination unwritable. Running as a normal user this
        // forces copyItem/createDirectory to fail with a permission error.
        try FileManager.default.setAttributes([.posixPermissions: 0o500], ofItemAtPath: root.path)

        let machinery = CopyMachinery()
        var caught: String? = nil
        do {
            _ = try await machinery.copy(
                urls: [src], into: root,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"]
            )
        } catch CopyMachinery.CopyError.underlying(let msg) {
            caught = msg
        } catch {
            caught = "UNEXPECTED \(type(of: error)): \(error.localizedDescription)"
        }

        let shown = try #require(caught)
        record("site2.underlying", shown)

        // Site 2 shows `msg` verbatim. Pin that it is Foundation's sentence,
        // NOT the enum-index string site 1 produces.
        #expect(!shown.contains("CopyError error"),
                "site 2 must show the wrapped reason, got: \(shown)")
        #expect(!shown.isEmpty)
        // And that inFlight cleared — the defer in copy() must run on failure.
        #expect(machinery.inFlight == nil)
    }
}
