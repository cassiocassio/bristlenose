import Foundation
import Testing
@testable import Bristlenose

/// A restored Re-analyse resumes as a plain Analyse once its fresh run holds a session
/// (owner, 12 Nov 2026). The probe re-implements Python's `holds_an_analysed_session`
/// and the set-aside folder's name, so it is held to
/// `tests/fixtures/fresh-run-probe-contract.json`, which
/// `tests/test_fresh_run_probe_contract.py` holds Python to.
@MainActor
struct FreshRunProbeTests {

    private struct Case {
        let name: String
        let manifest: Any?
        let quotes: Any?
        let holds: Bool
    }

    private static func contract() throws -> (setAside: String, output: String, cases: [Case]) {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("tests/fixtures/fresh-run-probe-contract.json")
        let root = try #require(
            try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let cases = try #require(root["cases"] as? [[String: Any]]).map { c in
            Case(name: c["name"] as? String ?? "",
                 manifest: c["manifest"] is NSNull ? nil : c["manifest"],
                 quotes: c["quotes"] is NSNull ? nil : c["quotes"],
                 holds: c["holds"] as? Bool ?? false)
        }
        return (try #require(root["setAsideDirName"] as? String),
                try #require(root["outputDirName"] as? String), cases)
    }

    /// A study folder with the output a case describes.
    private static func build(_ c: Case, output: String) throws -> URL {
        let study = FileManager.default.temporaryDirectory
            .appendingPathComponent("FreshRunProbeTests-\(UUID().uuidString)")
        let dot = study.appendingPathComponent(output).appendingPathComponent(".bristlenose")
        try FileManager.default.createDirectory(
            at: dot.appendingPathComponent("intermediate"), withIntermediateDirectories: true)
        if let manifest = c.manifest {
            try JSONSerialization.data(withJSONObject: manifest)
                .write(to: dot.appendingPathComponent("pipeline-manifest.json"))
        }
        if let quotes = c.quotes {
            try JSONSerialization.data(withJSONObject: quotes)
                .write(to: dot.appendingPathComponent("intermediate/extracted_quotes.json"))
        }
        return study
    }

    @Test func theOutputRuleMatchesPythonOnEveryContractCase() throws {
        let (_, output, cases) = try Self.contract()
        #expect(cases.count >= 6)
        for c in cases {
            let study = try Self.build(c, output: output)
            defer { try? FileManager.default.removeItem(at: study) }
            #expect(FreshRunProbe.holdsAnalysedSession(output: study.appendingPathComponent(output))
                    == c.holds, "\(c.name)")
        }
    }

    @Test func aFreshRunHoldsASessionOnlyWhenTheOldReportIsSetAsideToo() throws {
        let (setAside, output, cases) = try Self.contract()
        let holding = try #require(cases.first { $0.holds })
        let study = try Self.build(holding, output: output)
        defer { try? FileManager.default.removeItem(at: study) }

        // Before the old report is set aside (the first seconds of a Re-analyse) the
        // output folder IS the old report, and it holds a session too.
        #expect(!FreshRunProbe.freshRunHoldsSession(studyFolder: study))

        try FileManager.default.createDirectory(
            at: study.appendingPathComponent(setAside), withIntermediateDirectories: true)
        #expect(FreshRunProbe.freshRunHoldsSession(studyFolder: study))
    }

    @Test func theSetAsideNameIsPythons() throws {
        let (setAside, _, _) = try Self.contract()
        let study = URL(fileURLWithPath: "/tmp/x")
        #expect(FreshRunProbe.setAsideURL(studyFolder: study).lastPathComponent == setAside)
    }
}
