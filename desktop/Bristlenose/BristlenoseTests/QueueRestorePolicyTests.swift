import Foundation
import Testing
@testable import Bristlenose

/// Whether a study the run queue held at Quit runs again on the next launch
/// (R19 follow-up, 20 Oct 2026): fresh for 92 hours, Friday 4 pm to Tuesday
/// noon, and only while the study is still there.
@MainActor
struct QueueRestorePolicyTests {

    static let hour: TimeInterval = 60 * 60
    static let now = Date(timeIntervalSince1970: 1_792_490_400)

    static func entry(age: TimeInterval, studyID: String? = nil) -> PersistedQueueEntry {
        PersistedQueueEntry(
            projectID: UUID(), clean: false, enqueuedAt: now.addingTimeInterval(-age),
            studyID: studyID, inFlight: false
        )
    }

    static let project = Project(id: UUID(), name: "Study", path: "/tmp/study")

    static func decide(
        age: TimeInterval, studyID: String? = nil, project: Project? = project,
        availability: ProjectAvailability = .ready,
        evidence: QueueRestorePolicy.DiskEvidence? = .init(studyIDOnDisk: nil, inputs: .present)
    ) -> QueueRestorePolicy.Decision {
        QueueRestorePolicy.decide(
            entry(age: age, studyID: studyID), now: now, project: project,
            availability: availability, evidence: evidence
        )
    }

    // MARK: - The window

    @Test func theWindowIsFridayFourPmToTuesdayNoon() {
        let friday = DateComponents(calendar: .init(identifier: .gregorian), timeZone: .init(identifier: "Europe/London"),
                                    year: 2026, month: 10, day: 16, hour: 16).date!
        let tuesday = DateComponents(calendar: .init(identifier: .gregorian), timeZone: .init(identifier: "Europe/London"),
                                     year: 2026, month: 10, day: 20, hour: 12).date!
        #expect(QueueRestorePolicy.window == tuesday.timeIntervalSince(friday))
    }

    @Test func aQueueLeftOnFridayEveningIsRestoredOnMondayMorning() {
        // Friday 5 pm to Monday 9 am.
        #expect(Self.decide(age: 64 * Self.hour) == .restore)
    }

    @Test func oneSecondInsideTheWindowIsRestored() {
        #expect(Self.decide(age: QueueRestorePolicy.window - 1) == .restore)
    }

    @Test func theWindowItselfHasLapsed() {
        #expect(Self.decide(age: QueueRestorePolicy.window) == .drop(.expired))
    }

    @Test func oneSecondPastTheWindowHasLapsed() {
        #expect(Self.decide(age: QueueRestorePolicy.window + 1) == .drop(.expired))
    }

    @Test func aQueueTwoWeeksOldHasLapsed() {
        #expect(Self.decide(age: 14 * 24 * Self.hour) == .drop(.expired))
    }

    @Test func aQueueOfAMomentAgoIsRestored() {
        #expect(Self.decide(age: 0) == .restore)
    }

    @Test func aStampALittleInTheFutureIsBelieved() {
        #expect(Self.decide(age: -(QueueRestorePolicy.clockSkewTolerance - 1)) == .restore)
    }

    @Test func aStampFarInTheFutureHasNoAgeAndIsNotHonoured() {
        #expect(Self.decide(age: -(QueueRestorePolicy.clockSkewTolerance + 1)) == .drop(.stampedInFuture))
    }

    @Test func aLapsedEntryIsDroppedBeforeAnythingElseIsAsked() {
        #expect(Self.decide(age: QueueRestorePolicy.window, project: nil) == .drop(.expired))
    }

    // MARK: - The study is still there

    @Test func aStudyRemovedFromTheSidebarIsDropped() {
        #expect(Self.decide(age: Self.hour, project: nil) == .drop(.notInSidebar))
    }

    @Test func aFolderThatCannotBeFoundIsDropped() {
        for reason: CantFindReason in [.moved, .missingBookmark, .unmountedVolume(name: "T7"),
                                       .networkUnreachable(host: "nas")] {
            #expect(Self.decide(age: Self.hour, availability: .cantFind(reason: reason)) == .drop(.folderNotFound))
        }
    }

    @Test func aFolderNowCarryingAnotherStudyIsDropped() {
        let decision = Self.decide(
            age: Self.hour, studyID: "aaaaaaaa-0000-0000-0000-000000000001",
            evidence: .init(studyIDOnDisk: "aaaaaaaa-0000-0000-0000-000000000002", inputs: .present)
        )
        #expect(decision == .drop(.differentStudy))
    }

    @Test func theSameStudyInEitherCaseIsRestored() {
        let decision = Self.decide(
            age: Self.hour, studyID: "AAAAAAAA-0000-0000-0000-000000000001",
            evidence: .init(studyIDOnDisk: "aaaaaaaa-0000-0000-0000-000000000001", inputs: .present)
        )
        #expect(decision == .restore)
    }

    @Test func aStudyWithNoMarkerEitherSideIsRestored() {
        // Never analysed when asked for, or its output folder deleted since:
        // nothing says it is another study.
        #expect(Self.decide(age: Self.hour, studyID: nil,
                            evidence: .init(studyIDOnDisk: "x", inputs: .present)) == .restore)
        #expect(Self.decide(age: Self.hour, studyID: "x",
                            evidence: .init(studyIDOnDisk: nil, inputs: .present)) == .restore)
    }

    @Test func aStudyWithNothingLeftToAnalyseIsDropped() {
        #expect(Self.decide(age: Self.hour, evidence: .init(studyIDOnDisk: nil, inputs: .gone))
                == .drop(.nothingToAnalyse))
    }

    @Test func aFolderThatCouldNotBeReadIsNotCountedAsEmpty() {
        #expect(Self.decide(age: Self.hour, evidence: .init(studyIDOnDisk: nil, inputs: .unknown)) == .restore)
    }

    // MARK: - What the folder holds

    final class Folder {
        let root: URL
        init() {
            root = URL(fileURLWithPath: NSTemporaryDirectory())
                .appendingPathComponent("queue-inputs-\(UUID().uuidString)")
            try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        }
        func file(_ relative: String) {
            let url = root.appendingPathComponent(relative)
            try? FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true
            )
            FileManager.default.createFile(atPath: url.path, contents: Data("x".utf8))
        }
        deinit { try? FileManager.default.removeItem(at: root) }
    }

    @Test func anEmptyFolderHasNothingToAnalyse() {
        let f = Folder()
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .gone)
    }

    @Test func aRecordingAtTheTopIsFound() {
        let f = Folder(); f.file("interview.MP4")
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .present)
    }

    @Test func notesAloneAreNothingToAnalyse() {
        let f = Folder(); f.file("notes.txt"); f.file("brief.pdf")
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .gone)
    }

    @Test func aRecordingThreeLevelsDownIsFoundAsPythonFindsIt() {
        let f = Folder(); f.file("week1/zoom1/video.mp4")
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .present)
    }

    @Test func aRecordingFourLevelsDownIsBeyondWhatPythonReads() {
        let f = Folder(); f.file("a/b/c/video.mp4")
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .gone)
    }

    @Test func ourOwnOutputAndHiddenFilesAreNotInputs() {
        let f = Folder()
        f.file("bristlenose-output/clips/s1.mp4")
        f.file(".hidden/clip.mp4")
        f.file("._interview.mp4")
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .gone)
    }

    @Test func aFolderThatIsNotThereCannotBeRead() {
        let missing = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("queue-inputs-missing-\(UUID().uuidString)")
        #expect(QueueRestorePolicy.ingestableFile(under: missing) == .unknown)
    }

    @Test func aLinkNotFollowedLeavesItUnknownRatherThanEmpty() throws {
        let f = Folder(); let target = Folder(); target.file("video.mp4")
        try FileManager.default.createSymbolicLink(
            at: f.root.appendingPathComponent("recordings"), withDestinationURL: target.root
        )
        #expect(QueueRestorePolicy.ingestableFile(under: f.root) == .unknown)
    }
}
