import Foundation
import Testing
@testable import Bristlenose

/// Pins the reveal ladder now that two surfaces share it (the export popover row
/// and Project ▸ Show Transcripts in Finder).
///
/// The invariant worth guarding is the **preference order** — `transcripts-cooked/`
/// must win over `transcripts-raw/` when both exist, because cooked is the
/// PII-redacted form and revealing raw when a redacted copy exists hands the
/// researcher the more sensitive folder. That's a privacy-shaped ordering, not a
/// cosmetic one, so it earns a test rather than trusting array order to survive
/// a future edit.
@Suite struct TranscriptsRevealTargetTests {

    /// FileManager stub — `fileExists` answers from a fixed set, so no tree needed.
    private final class StubFM: FileManager {
        let present: Set<String>
        init(present: Set<String>) { self.present = present; super.init() }
        override func fileExists(atPath path: String) -> Bool { present.contains(path) }
    }

    private let project = "/tmp/proj"
    private var output: String { "/tmp/proj/bristlenose-output" }
    private var cooked: String { "/tmp/proj/bristlenose-output/transcripts-cooked" }
    private var raw: String { "/tmp/proj/bristlenose-output/transcripts-raw" }

    @Test func emptyPathResolvesToNil() {
        #expect(TranscriptsRevealTarget.resolve(projectPath: "") == nil)
    }

    /// The privacy-shaped assertion: redacted beats raw when both are present.
    @Test func cookedWinsOverRaw() {
        let fm = StubFM(present: [cooked, raw, output, project])
        #expect(TranscriptsRevealTarget.resolve(projectPath: project, fileManager: fm) == cooked)
    }

    @Test func rawUsedWhenNoCooked() {
        let fm = StubFM(present: [raw, output, project])
        #expect(TranscriptsRevealTarget.resolve(projectPath: project, fileManager: fm) == raw)
    }

    @Test func fallsBackToOutputThenProject() {
        let onlyOutput = StubFM(present: [output, project])
        #expect(TranscriptsRevealTarget.resolve(projectPath: project, fileManager: onlyOutput) == output)

        let onlyProject = StubFM(present: [project])
        #expect(TranscriptsRevealTarget.resolve(projectPath: project, fileManager: onlyProject) == project)
    }

    /// Never nil for a non-empty path: an un-analysed project still reveals its
    /// own folder rather than the command silently doing nothing.
    @Test func neverNilForNonEmptyPath() {
        let nothing = StubFM(present: [])
        #expect(TranscriptsRevealTarget.resolve(projectPath: project, fileManager: nothing) == project)
    }
}
