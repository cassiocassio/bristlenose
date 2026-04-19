import Foundation
import Testing

@testable import Bristlenose

@Suite("SidecarMode.resolve")
struct SidecarModeTests {

    // MARK: - External

    @Test("external: valid port parses")
    func externalValidPort() {
        let result = SidecarMode.resolve(
            externalPortRaw: "8150",
            sidecarPathRaw: nil,
            bundleResourceURL: nil
        )
        #expect(result == .success(.external(port: 8150)))
    }

    @Test(
        "external: invalid port raws fail",
        arguments: ["abc", "70000", "0", "-1", ""]
    )
    func externalInvalidPort(raw: String) {
        let result = SidecarMode.resolve(
            externalPortRaw: raw,
            sidecarPathRaw: nil,
            bundleResourceURL: nil
        )
        #expect(result == .failure(.invalidExternalPort(raw)))
    }

    // MARK: - Both set

    @Test("both env vars set: startup error")
    func bothEnvVarsSet() {
        let result = SidecarMode.resolve(
            externalPortRaw: "8150",
            sidecarPathRaw: "/usr/bin/true",
            bundleResourceURL: nil
        )
        #expect(result == .failure(.bothDevEnvVarsSet))
    }

    // MARK: - Dev sidecar

    @Test("dev sidecar: valid executable path resolves")
    func devSidecarValidPath() throws {
        let tempExec = try makeTempExecutable()
        defer { try? FileManager.default.removeItem(at: tempExec) }

        let result = SidecarMode.resolve(
            externalPortRaw: nil,
            sidecarPathRaw: tempExec.path,
            bundleResourceURL: nil
        )
        #expect(result == .success(.devSidecar(path: tempExec)))
    }

    @Test("dev sidecar: tilde expands against HOME")
    func devSidecarTildeExpansion() throws {
        // Create an executable inside a UUID-named subdirectory under $HOME
        // so test cleanup is crash-safe (directory removal unlinks the exec).
        let dir = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent(".sidecar-test-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let execName = "sidecar"
        let absExec = dir.appendingPathComponent(execName)
        FileManager.default.createFile(atPath: absExec.path, contents: Data())
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: Int16(0o755))],
            ofItemAtPath: absExec.path
        )

        let tildePath = "~/\(dir.lastPathComponent)/\(execName)"
        let result = SidecarMode.resolve(
            externalPortRaw: nil,
            sidecarPathRaw: tildePath,
            bundleResourceURL: nil
        )
        #expect(result == .success(.devSidecar(path: absExec)))
    }

    @Test(
        "dev sidecar: invalid raws fail",
        arguments: [
            "",                       // empty
            "   ",                    // whitespace
            "bin/bristlenose",        // relative
        ]
    )
    func devSidecarInvalidSyntax(raw: String) {
        expectInvalidSidecarPath(
            SidecarMode.resolve(
                externalPortRaw: nil,
                sidecarPathRaw: raw,
                bundleResourceURL: nil
            )
        )
    }

    @Test("dev sidecar: non-existent path fails")
    func devSidecarMissing() {
        expectInvalidSidecarPath(
            SidecarMode.resolve(
                externalPortRaw: nil,
                sidecarPathRaw: "/no/such/file-\(UUID().uuidString)",
                bundleResourceURL: nil
            )
        )
    }

    @Test("dev sidecar: directory path fails")
    func devSidecarDirectory() {
        expectInvalidSidecarPath(
            SidecarMode.resolve(
                externalPortRaw: nil,
                sidecarPathRaw: NSTemporaryDirectory(),
                bundleResourceURL: nil
            )
        )
    }

    @Test("dev sidecar: non-executable file fails")
    func devSidecarNonExecutable() throws {
        let tempURL = URL(
            fileURLWithPath: NSTemporaryDirectory()
        ).appendingPathComponent("not-executable-\(UUID().uuidString)")
        FileManager.default.createFile(atPath: tempURL.path, contents: Data())
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: Int16(0o644))],
            ofItemAtPath: tempURL.path
        )
        defer { try? FileManager.default.removeItem(at: tempURL) }

        expectInvalidSidecarPath(
            SidecarMode.resolve(
                externalPortRaw: nil,
                sidecarPathRaw: tempURL.path,
                bundleResourceURL: nil
            )
        )
    }

    // MARK: - Bundled

    @Test("bundled: no env + no bundle → error")
    func bundledMissingBundle() {
        let result = SidecarMode.resolve(
            externalPortRaw: nil,
            sidecarPathRaw: nil,
            bundleResourceURL: nil
        )
        if case .failure(.bundledSidecarMissing) = result {
            // ok
        } else {
            Issue.record("expected .bundledSidecarMissing, got \(result)")
        }
    }

    @Test("bundled: bundle present but sidecar absent → error")
    func bundledBundleWithoutSidecar() throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bundle-test-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let result = SidecarMode.resolve(
            externalPortRaw: nil,
            sidecarPathRaw: nil,
            bundleResourceURL: tempDir
        )
        if case .failure(.bundledSidecarMissing) = result {
            // ok
        } else {
            Issue.record("expected .bundledSidecarMissing, got \(result)")
        }
    }

    @Test("bundled: executable present → .bundled")
    func bundledSidecarPresent() throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bundle-test-\(UUID().uuidString)")
        let sidecarDir = tempDir.appendingPathComponent("bristlenose-sidecar")
        try FileManager.default.createDirectory(at: sidecarDir, withIntermediateDirectories: true)
        let sidecarPath = sidecarDir.appendingPathComponent("bristlenose-sidecar")
        FileManager.default.createFile(atPath: sidecarPath.path, contents: Data())
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: Int16(0o755))],
            ofItemAtPath: sidecarPath.path
        )
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let result = SidecarMode.resolve(
            externalPortRaw: nil,
            sidecarPathRaw: nil,
            bundleResourceURL: tempDir
        )
        #expect(result == .success(.bundled(path: sidecarPath)))
    }

    // MARK: - LocalizedError

    @Test("SidecarResolveError: localizedDescription reads from description")
    func errorLocalizedDescription() {
        let err: SidecarResolveError = .invalidExternalPort("abc")
        #expect((err as Error).localizedDescription == err.description)
    }

    // MARK: - Helpers

    private func expectInvalidSidecarPath(
        _ result: Result<SidecarMode, SidecarResolveError>,
        sourceLocation: SourceLocation = #_sourceLocation
    ) {
        if case .failure(.invalidSidecarPath) = result {
            // ok
        } else {
            Issue.record(
                "expected .invalidSidecarPath, got \(result)",
                sourceLocation: sourceLocation
            )
        }
    }

    private func makeTempExecutable() throws -> URL {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("sidecar-test-\(UUID().uuidString)")
        FileManager.default.createFile(atPath: url.path, contents: Data())
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: Int16(0o755))],
            ofItemAtPath: url.path
        )
        return url
    }
}
