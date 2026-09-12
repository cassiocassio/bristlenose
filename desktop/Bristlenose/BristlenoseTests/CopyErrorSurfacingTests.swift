import Foundation
import Testing

@testable import Bristlenose

/// `CopyMachinery.CopyError` conforms to `LocalizedError`, so the two catch
/// sites in `ContentView` — the loose-files site, which reads
/// `error.localizedDescription`, and the drop-onto-project site, which
/// destructures `.underlying` — render the same sentence for the same failure.
/// These tests pin that by construction: every case's `errorDescription` is a
/// sentence and never Foundation's enum-index fallback, and `.underlying`
/// carries the wrapped error's own words.
///
/// History: until this landed the two sites diverged — `.underlying` carried a
/// `String`, the enum was not `LocalizedError`, and site 1 rendered
/// "The operation couldn’t be completed. (Bristlenose.CopyMachinery.CopyError
/// error 1.)" for a permission failure the other gesture rendered in full.
/// Measured and diagnosed in `docs/design-copy-error-surfacing.md`; the
/// `withKnownIssue` probes that pinned the defect became these assertions.
@MainActor
struct CopyErrorSurfacingTests {

    /// Foundation's fallback for an error type with no localized text.
    private static let enumIndexFallback = "CopyError error"

    private func makeTempDir() -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("copy-error-probe-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func permissionError(_ text: String) -> NSError {
        NSError(domain: NSCocoaErrorDomain, code: NSFileWriteNoPermissionError,
                userInfo: [NSLocalizedDescriptionKey: text])
    }

    @Test("every case renders a sentence, never the enum-index fallback")
    func everyCaseRendersASentence() {
        let cases: [CopyMachinery.CopyError] = [
            .insufficientDiskSpace(needed: 5_000_000_000, available: 1_000_000_000),
            .noItemsAfterFiltering,
            .alreadyInFlight,
            .underlying(permissionError("You don’t have permission to save the file “P07.mp4”.")),
        ]
        for err in cases {
            let shown = err.localizedDescription
            #expect(!shown.isEmpty, "\(err) rendered nothing")
            #expect(!shown.contains(Self.enumIndexFallback), "\(err) rendered the fallback: \(shown)")
            // `localizedDescription` must resolve through the conformance, not around it.
            #expect(err.errorDescription == shown)
        }
    }

    @Test(".underlying carries the wrapped error’s own sentence, verbatim")
    func underlyingCarriesTheReason() {
        let reason = "You don’t have permission to save the file “P07.mp4” in the folder “Interviews”."
        let err = CopyMachinery.CopyError.underlying(permissionError(reason))
        #expect(err.localizedDescription == reason)
    }

    @Test("the in-flight guard is its own case with its own sentence")
    func alreadyInFlightHasASentence() {
        let shown = CopyMachinery.CopyError.alreadyInFlight.localizedDescription
        #expect(shown.contains("in flight"))
        #expect(!shown.contains(Self.enumIndexFallback))
    }

    @Test("a real permission failure reads the same at both sites")
    func permissionFailureReadsTheSameAtBothSites() async throws {
        let root = makeTempDir()
        defer {
            try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: root.path)
            try? FileManager.default.removeItem(at: root)
        }
        let srcDir = makeTempDir()
        defer { try? FileManager.default.removeItem(at: srcDir) }
        let src = srcDir.appendingPathComponent("P07.mp4")
        try Data("not really video".utf8).write(to: src)

        // An unwritable destination forces copyItem/createDirectory to fail
        // with a permission error when running as a normal user.
        try FileManager.default.setAttributes([.posixPermissions: 0o500], ofItemAtPath: root.path)

        let machinery = CopyMachinery()
        var caught: CopyMachinery.CopyError? = nil
        do {
            _ = try await machinery.copy(
                urls: [src], into: root,
                projectID: UUID(), projectName: "Probe",
                acceptedExtensions: ["mp4"]
            )
        } catch let err as CopyMachinery.CopyError {
            caught = err
        }

        let err = try #require(caught)
        guard case .underlying(let inner) = err else {
            Issue.record("expected .underlying, got \(err)")
            return
        }
        let site1 = err.localizedDescription      // the loose-files site reads this
        let site2 = inner.localizedDescription    // the drop-onto-project site destructures this
        #expect(site1 == site2)
        #expect(!site1.isEmpty)
        #expect(!site1.contains(Self.enumIndexFallback))
        // inFlight cleared — the defer in copy() must run on failure.
        #expect(machinery.inFlight == nil)
    }
}
