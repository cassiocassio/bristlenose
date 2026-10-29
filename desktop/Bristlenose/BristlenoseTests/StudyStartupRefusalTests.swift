import Combine
import Foundation
import Testing
@testable import Bristlenose

@MainActor
@Suite("Study startup refusal facts")
struct StudyStartupRefusalTests {
    @Test("Missing or malformed structured output cannot supply display facts")
    func malformedOutput() {
        #expect(StudyStartupRefusal.fromLine("ordinary engine output") == nil)
        #expect(StudyStartupRefusal.fromLine(StudyStartupRefusal.prefix + "{") == nil)
        #expect(StudyStartupRefusal.fromLine(StudyStartupRefusal.prefix + #"{"reason":"unknown-new-reason"}"#) == nil)
        #expect(StudyStartupRefusal.unverified.reason == .unverified)
    }

    @Test("A valid refusal carries optional friendly name and source time")
    func metadata() throws {
        let line = StudyStartupRefusal.prefix
            + #"{"reason":"foreign_unfinished","machine_name":"Cassio’s Mac Studio","started_at":"2026-10-28T10:20:00Z"}"#
        let value = try #require(StudyStartupRefusal.fromLine(line))
        #expect(value.machineName == "Cassio’s Mac Studio")
        #expect(value.startedAt == "2026-10-28T10:20:00Z")
        #expect(value.failureMessage.startupRefusal == value)
        #expect(value.headline(using: I18n()) == "Started on another Mac")
        #expect(value.consequence(using: I18n()) == "This study cannot be viewed or edited here.")
    }

    @Test("Computer names are literal text with one emphasis range, not markdown")
    func literalName() {
        let value = StudyStartupRefusal(reason: .foreign, machineName: "Studio **Name**", startedAt: nil)
        let body = value.detail(using: I18n())
        #expect(String(body.characters) == "Analysis started on Studio **Name**.")
        #expect(body.runs.contains { $0.inlinePresentationIntent == .stronglyEmphasized })
    }

    @Test("Missing facts use honest fallback copy")
    func omittedFacts() {
        let value = StudyStartupRefusal(reason: .foreign, machineName: nil, startedAt: "invalid-time")
        #expect(String(value.detail(using: I18n()).characters) == "Analysis started on another Mac.")
        #expect(String(StudyStartupRefusal.unverified.detail(using: I18n()).characters)
            == "An unfinished analysis was found, but the Mac that started it could not be verified.")
    }
}

@MainActor
@Suite("Study startup refusal termination")
struct StudyStartupRefusalTerminationTests {
    @Test("Switching studies keeps the original row's confirmed refusal until a new result")
    func refusalSurvivesSwitch() {
        let fleet = ServeFleet(makeManager: { ServeManager(resolvedMode: .success(.external(port: 9998))) })
        let first = UUID(), second = UUID()
        let manager = fleet.manager(for: first)
        let facts = StudyStartupRefusal(reason: .foreign, machineName: "Home Mac", startedAt: nil)
        manager.state = .failed(error: facts.failureMessage)
        manager.stop() // ContentView's outgoing-project cleanup.
        fleet.front(second)
        #expect(manager.state == .idle)
        #expect(fleet.startupRefusals[first] == facts)
        manager.state = .starting
        #expect(fleet.startupRefusals[first] == facts)
        manager.state = .running(port: 9998)
        #expect(fleet.startupRefusals[first] == nil)
    }

    @Test("A new ordinary failure replaces a retained refusal")
    func newFailureReplacesRefusal() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 9998)))
        manager.state = .failed(error: StudyStartupRefusal.unverified.failureMessage)
        manager.stop()
        manager.state = .failed(error: FailureMessage(english: "New startup failure"))
        #expect(manager.startupRefusal == nil)
    }

    @Test("Retry admission callback runs once, only after the server is ready")
    func retryAdmission() {
        // External mode isolates callback wiring; Python admission itself is
        // covered by the real CLI/factory tests, not this no-subprocess seam.
        let manager = ServeManager(resolvedMode: .success(.external(port: 9998)))
        manager.state = .failed(error: StudyStartupRefusal.unverified.failureMessage)
        var admissions = 0
        manager.recheckStudyStartup(projectPath: "/tmp/bn-startup-retry", onAdmitted: { admissions += 1 })
        #expect(admissions == 1)
        manager.state = .running(port: 9998)
        #expect(admissions == 1)
    }

    @Test("A pending startup cannot be retried or treated as admitted")
    func pendingRetry() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 9998)))
        manager.state = .starting
        var admissions = 0
        manager.recheckStudyStartup(projectPath: "/tmp/bn-startup-retry", onAdmitted: { admissions += 1 })
        #expect(manager.state == .starting)
        manager.state = .running(port: 9998)
        #expect(admissions == 0)
    }

    @Test("Refusal exit without a drained pipe still produces the unverified cause")
    func missingOutput() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 9998)))
        let process = Process()
        manager.instance.process = process
        manager.instance.state = .starting
        manager.handleTermination(processID: ObjectIdentifier(process), status: StudyStartupRefusal.exitCode)
        #expect(manager.startupRefusal == .unverified)
    }

    @Test("Received facts enrich the refusal; a stale process cannot replace it")
    func factsAndIdentity() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 9998)))
        let process = Process()
        let stale = Process()
        let facts = StudyStartupRefusal(reason: .foreign, machineName: "Studio", startedAt: nil)
        manager.instance.process = process
        manager.instance.state = .starting
        manager.instance.pendingStartupRefusal = facts
        manager.handleTermination(processID: ObjectIdentifier(stale), status: StudyStartupRefusal.exitCode)
        #expect(manager.state == .starting)
        manager.handleTermination(processID: ObjectIdentifier(process), status: StudyStartupRefusal.exitCode)
        #expect(manager.startupRefusal == facts)
    }

    @Test("Pipeline refusal covers an already-drawn document with its actual cause")
    func refusalCover() {
        let message = StudyStartupRefusal.unverified.failureMessage
        let cover = DetailPaneKind.runCover(pipelineState: .failed(message, category: .unknown), documentState: .spa)
        guard case .failed(let sentence, _, _, _) = cover else {
            Issue.record("Startup refusal was not shown over the old document")
            return
        }
        #expect(sentence.startupRefusal == .unverified)
    }
}

@Suite("Startup refusal process output framing")
struct StartupRefusalOutputTests {
    @Test("Every byte split preserves a Unicode computer name and complete record")
    func everySplit() throws {
        let line = StudyStartupRefusal.prefix
            + #"{"reason":"foreign_unfinished","machine_name":"Cassio’s Mac 工作室","started_at":null}"#
        let bytes = Data((line + "\n").utf8)
        for split in 0...bytes.count {
            var framer = ProcessOutputLines()
            let first = framer.append(Data(bytes.prefix(split)))
            let second = framer.append(Data(bytes.dropFirst(split)))
            #expect(first + second == [line])
            let value = try #require(StudyStartupRefusal.fromLine((first + second)[0]))
            #expect(value.machineName == "Cassio’s Mac 工作室")
            #expect(framer.finish() == nil)
        }
    }

    @Test("EOF flushes only the current process's remaining line")
    func endOfFile() {
        var first = ProcessOutputLines()
        var second = ProcessOutputLines()
        #expect(first.append(Data("one\ntw".utf8)) == ["one"])
        #expect(second.append(Data("other\n".utf8)) == ["other"])
        #expect(first.append(Data("o".utf8)).isEmpty)
        #expect(first.finish() == "two")
        #expect(first.finish() == nil)
        #expect(second.finish() == nil)
    }
}

@MainActor
@Suite("Non-writing startup Retry probe", .serialized)
struct StudyStartupProbeTests {
    @Test("Shared-server Retry never publishes a boot state or replaces the live process",
          arguments: [false, true])
    func preservesSharedServer(superseded: Bool) async throws {
        let executable = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try "#!/bin/sh\nexit 0\n".write(to: executable, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
        defer { try? FileManager.default.removeItem(at: executable) }
        let manager = ServeManager(resolvedMode: .success(.devSidecar(path: executable)))
        let liveProcess = Process()
        manager.instance.process = liveProcess
        manager.instance.currentProjectPath = "/tmp/bn-shared-startup"
        manager.instance.state = .running(port: 9998)
        let generation = manager.instance.generation
        var transitions = 0
        let observation = manager.instance.$state.dropFirst().sink { _ in transitions += 1 }
        defer { observation.cancel() }
        var admitted = false
        manager.recheckStudyStartup(projectPath: "/tmp/bn-shared-startup") { admitted = true }
        if superseded { manager.instance.generation += 1 }
        let deadline = Date().addingTimeInterval(3)
        while Date() < deadline && !admitted { try? await Task.sleep(for: .milliseconds(10)) }
        #expect(admitted == !superseded)
        #expect(transitions == 0) // Both windows retain the same .running branch/WebViews.
        #expect(manager.instance.process === liveProcess)
        #expect(manager.instance.generation == generation + (superseded ? 1 : 0))
    }

    @Test("Probe admission, refusal and unsupported modes do not touch a live server",
          arguments: [0, 75, 2])
    func probeExit(code: Int) async {
        let probe = StudyStartupProbe()
        let result = await withCheckedContinuation { continuation in
            probe.start(executable: URL(fileURLWithPath: "/bin/sh"),
                        arguments: ["-c", "exit \(code)"], environment: [:]) {
                continuation.resume(returning: $0)
            }
        }
        switch code {
        case 0: #expect(result == .admitted)
        case 75: #expect(result == .refused(.unverified))
        default: #expect(result == .unavailable)
        }
    }

    @Test("A stuck probe is killed and never treated as admission")
    func timeout() async {
        let probe = StudyStartupProbe()
        let result = await withCheckedContinuation { continuation in
            probe.start(executable: URL(fileURLWithPath: "/bin/sh"),
                        arguments: ["-c", "trap '' TERM; while :; do :; done"], environment: [:],
                        timeout: .milliseconds(50)) { continuation.resume(returning: $0) }
        }
        #expect(result == .unavailable)
    }
}

@MainActor
@Suite("Refused analysis preserves the study", .serialized)
struct StudyStartupRefusalPipelineTests {
    @Test("Refusal outranks old report and Stop; no study failure log is written",
          arguments: [false, true])
    func refusedAttempt(stopFirst: Bool) async throws {
        let rig = PipelineRunnerQueueTests.Rig()
        defer { rig.cleanUp() }
        let project = rig.project("Protected")
        rig.writeFinishedRun(in: project, tokens: nil)
        let before = try files(at: project.path)
        rig.runner.start(project: project)
        let launch = try #require(rig.launches.last)
        launch.lines.yield(StudyStartupRefusal.prefix
            + #"{"reason":"foreign_unfinished","machine_name":"Studio","started_at":null}"#)
        if stopFirst { rig.runner.cancel(project: project) }
        launch.exit(.exited(code: StudyStartupRefusal.exitCode))
        let deadline = Date().addingTimeInterval(PipelineRunnerQueueTests.patience)
        while Date() < deadline {
            if case .failed(let message, _) = rig.runner.state[project.id], message.startupRefusal != nil { break }
            try? await Task.sleep(for: .milliseconds(10))
        }
        guard case .failed(let message, _) = rig.runner.state[project.id] else {
            Issue.record("Refusal was replaced by old ready/stopped state")
            return
        }
        #expect(message.startupRefusal?.machineName == "Studio")
        #expect(try files(at: project.path) == before)
    }

    private func files(at path: String) throws -> [String: Data] {
        let root = URL(fileURLWithPath: path)
        guard let entries = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey])
        else { return [:] }
        var result: [String: Data] = [:]
        for case let file as URL in entries {
            if try file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
                result[String(file.path.dropFirst(root.path.count))] = try Data(contentsOf: file)
            }
        }
        return result
    }
}
