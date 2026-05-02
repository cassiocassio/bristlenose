import Foundation
import Testing
@testable import Bristlenose

/// Tests for BristlenoseShared.sslEnvironment(for:) — bundled-sidecar TLS
/// fix. See `docs/private/sandbox-violations-A1c.md` row 4 for context:
/// PyInstaller's bundled Python OpenSSL has compile-time defaults pointing
/// at Homebrew paths blocked by App Sandbox; this helper redirects to
/// certifi's bundled CA file.
@Suite("BristlenoseShared.sslEnvironment")
struct SslEnvironmentTests {

    @Test func bundled_mode_emits_four_ssl_vars() {
        let binary = URL(fileURLWithPath: "/tmp/Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar")
        let env = BristlenoseShared.sslEnvironment(for: .bundled(path: binary))

        let expectedCert = "/tmp/Bristlenose.app/Contents/Resources/bristlenose-sidecar/_internal/certifi/cacert.pem"
        let expectedDir = "/tmp/Bristlenose.app/Contents/Resources/bristlenose-sidecar/_internal/certifi"

        #expect(env["SSL_CERT_FILE"] == expectedCert)
        #expect(env["SSL_CERT_DIR"] == expectedDir)
        #expect(env["REQUESTS_CA_BUNDLE"] == expectedCert)
        #expect(env["OPENSSL_CONF"] == "/dev/null")
        #expect(env.count == 4)
    }

    @Test func dev_sidecar_mode_emits_nothing() {
        // Dev sidecar runs against the developer's venv Python — its OpenSSL
        // is whatever Homebrew/system paths point at, which work fine outside
        // App Sandbox. Don't override.
        let binary = URL(fileURLWithPath: "/Users/dev/.venv/bin/bristlenose")
        let env = BristlenoseShared.sslEnvironment(for: .devSidecar(path: binary))

        #expect(env.isEmpty)
    }

    @Test func external_mode_emits_nothing() {
        // External mode never spawns a subprocess — the host process talks
        // to an already-running serve. No env to set.
        let env = BristlenoseShared.sslEnvironment(for: .external(port: 9131))

        #expect(env.isEmpty)
    }
}
