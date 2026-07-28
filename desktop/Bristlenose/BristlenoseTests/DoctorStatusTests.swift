import Foundation
import Testing

@testable import Bristlenose

/// Pins the doctor wire-status → `MessageKind` mapping (`DoctorStatus`) that the
/// native Health window renders from. The wire values come from
/// `bristlenose/doctor.py`'s `CheckStatus` enum: OK="ok", WARN="warn",
/// FAIL="fail", SKIP="--". If either side's vocabulary drifts, this is the
/// tripwire.
@Suite struct DoctorStatusTests {

    @Test func okMapsToSuccess() {
        #expect(DoctorStatus.messageKind(for: "ok") == .success)
    }

    @Test func warnMapsToWarning() {
        #expect(DoctorStatus.messageKind(for: "warn") == .warning)
    }

    @Test func failMapsToError() {
        #expect(DoctorStatus.messageKind(for: "fail") == .error)
    }

    @Test func skipSentinelMapsToSkipped() {
        // SKIP serialises as the literal "--" (CheckStatus.SKIP = "--").
        #expect(DoctorStatus.messageKind(for: "--") == .skipped)
    }

    @Test func unknownFallsBackToInfo() {
        // Never crash on an unexpected wire value — the spare kind absorbs it.
        #expect(DoctorStatus.messageKind(for: "banana") == .info)
        #expect(DoctorStatus.messageKind(for: "") == .info)
    }

    // MARK: - Decoding

    @Test func decodesWirePayload() throws {
        let json = """
        {"checks": [
            {"status": "ok", "label": "FFmpeg", "detail": "6.1.1", "fix_key": "", "fix": ""},
            {"status": "fail", "label": "Serve mode", "detail": "missing: fastapi",
             "fix_key": "serve_deps_missing", "fix": "pip install 'bristlenose[serve]'"}
        ]}
        """.data(using: .utf8)!
        let report = try JSONDecoder().decode(DoctorReport.self, from: json)
        #expect(report.checks.count == 2)
        #expect(report.checks[0].label == "FFmpeg")
        #expect(report.checks[0].fix.isEmpty)
        #expect(report.checks[1].fix == "pip install 'bristlenose[serve]'")
        #expect(DoctorStatus.messageKind(for: report.checks[1].status) == .error)
    }

    @Test func toleratesMissingOptionalFields() throws {
        // A future/partial payload without detail/fix must still decode.
        let json = """
        {"checks": [{"status": "warn", "label": "Disk space"}]}
        """.data(using: .utf8)!
        let report = try JSONDecoder().decode(DoctorReport.self, from: json)
        #expect(report.checks[0].detail.isEmpty)
        #expect(report.checks[0].fix.isEmpty)
    }

    // MARK: - Plaintext copy

    @Test func plaintextUsesCLIGlyphColumn() {
        let checks = [
            DoctorCheck(status: "ok", label: "FFmpeg", detail: "6.1.1"),
            DoctorCheck(status: "fail", label: "Serve mode", detail: "missing: fastapi",
                        fix: "pip install 'bristlenose[serve]'"),
        ]
        let text = DoctorReportView.formatPlaintext(
            checks: checks, appVersion: "0.22.0", build: "2100", os: "macOS 15.4.0"
        )
        #expect(text.contains("Bristlenose 0.22.0 (2100) on macOS 15.4.0"))
        // CLI glyphs, matching a terminal doctor run.
        #expect(text.contains("\(MessageKind.success.glyph) FFmpeg  6.1.1"))
        #expect(text.contains("\(MessageKind.error.glyph) Serve mode  missing: fastapi"))
        // Fix text hangs indented under its check.
        #expect(text.contains("    pip install 'bristlenose[serve]'"))
    }
}
