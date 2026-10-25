import Foundation
import Testing
@testable import Bristlenose

/// N191 (sweep 2, MCP-2): a study that sat in a background window with Agent
/// Access off was only marked "restart when fronted" when Anonymise went on.
/// Turning its access on afterwards (from another window's sidebar, or by
/// re-ticking it in Settings, where no content window is fronted) made it
/// readable by agents, with real names, until its own window was clicked.
///
/// The rule under test: a study that becomes readable by agents while marked
/// stale is restarted first, and neither the handshake nor the gate names it
/// until the restarted serve is up.
@MainActor
@Suite("ServeFleet exposes a stale study only after restarting it")
struct ServeFleetStaleExposureTests {

    private static let a = UUID()
    private static let b = UUID()
    private static let restartPort = 9_998

    /// What the gate was told, in order.
    private final class ScopeLog {
        var calls: [(project: UUID, readable: Bool)] = []
        func opened(_ id: UUID) -> Bool { calls.contains { $0.project == id && $0.readable } }
    }

    private final class Access {
        var on: Set<UUID> = []
    }

    private struct Rig {
        let fleet: ServeFleet
        let scope: ScopeLog
        let access: Access
        let dir: URL
        var handshakeFile: URL { dir.appendingPathComponent(MCPHandshake.filename) }
    }

    /// `a` fronted and `b` in a background window, both running, neither
    /// shared; Anonymise has just gone on, so `b` is marked stale.
    private static func rig() throws -> Rig {
        let fleet = ServeFleet(screenReading: ScreenReadingStore(), makeManager: {
            ServeManager(resolvedMode: .success(.external(port: restartPort)))
        })
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let scope = ScopeLog()
        let access = Access()
        fleet.handshakeDirectory = dir
        fleet.agentAccessByID = { [access] id in access.on.contains(id) }
        fleet.applyAgentScope = { [weak fleet] manager, readable in
            guard let id = fleet?.managers.first(where: { $0.value === manager })?.key else { return }
            scope.calls.append((id, readable))
        }
        for (id, port) in [(a, 5000), (b, 5001)] {
            let m = fleet.manager(for: id)
            m.instance.state = .running(port: port)
            m.instance.currentProjectPath = "/p/\(id)"
            m.instance.mcpInstanceID = "inst-\(id)"
            m.instance.mcpToken = "tok-\(id)"
            m.setProjectKeyForTest("key-\(id)")
        }
        fleet.frontedProject = a

        let suite = "ServeFleetStaleExposureTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        fleet.applyEnvChange(defaults: defaults)
        #expect(fleet.staleProjects.contains(b), "precondition: b is marked stale")
        #expect(fleet.staleProjects.contains(a) == false, "precondition: a is fronted, so restarted")
        return Rig(fleet: fleet, scope: scope, access: access, dir: dir)
    }

    private func settle(_ m: ServeManager, to state: ServeState) async {
        for _ in 0..<100 where m.state != state {
            try? await Task.sleep(for: .milliseconds(20))
        }
    }

    /// Whether the handshake file offers the study to a proxy. The file carries
    /// each study's key (`key-<id>` in this rig), not its path.
    private func handshakeNames(_ rig: Rig, _ id: UUID) -> Bool {
        guard let text = try? String(contentsOf: rig.handshakeFile, encoding: .utf8) else { return false }
        return text.contains("key-\(id)")
    }

    @Test func aStaleStudyGivenAccessIsRestartedBeforeAnyAgentCanReadIt() async throws {
        let rig = try Self.rig()
        defer { try? FileManager.default.removeItem(at: rig.dir) }
        let b = rig.fleet.manager(for: Self.b)

        rig.access.on.insert(Self.b)
        rig.fleet.syncHandshake(shown: [Self.a, Self.b])

        // Before the restart lands: the old serve, still on the old environment,
        // is neither named in the handshake nor opened.
        #expect(rig.scope.opened(Self.b) == false,
                "the gate opened on a serve still holding the old Anonymise setting")
        #expect(handshakeNames(rig, Self.b) == false,
                "the handshake named a serve still holding the old Anonymise setting")
        #expect(rig.fleet.staleProjects.contains(Self.b) == false, "the stale mark was left in place")

        await settle(b, to: .running(port: Self.restartPort))
        #expect(b.state == .running(port: Self.restartPort),
                "a stale study that became readable was never restarted")
    }

    /// And once the restarted serve is up, it is exposed like any other.
    @Test func theRestartedStudyIsExposedOnTheNextSync() async throws {
        let rig = try Self.rig()
        defer { try? FileManager.default.removeItem(at: rig.dir) }
        let b = rig.fleet.manager(for: Self.b)
        rig.access.on.insert(Self.b)
        rig.fleet.syncHandshake(shown: [Self.a, Self.b])
        await settle(b, to: .running(port: Self.restartPort))

        // What the health read does once the new serve is up.
        b.instance.mcpInstanceID = "inst-restarted"
        b.instance.mcpToken = "tok-restarted"
        b.setProjectKeyForTest("key-\(Self.b)")
        rig.fleet.syncHandshake(shown: [Self.a, Self.b])

        #expect(rig.scope.calls.last(where: { $0.project == Self.b })?.readable == true)
        #expect(handshakeNames(rig, Self.b))
        #expect(rig.fleet.staleProjects.contains(Self.b) == false)
    }

    /// Lazy stays lazy: a stale study nobody can reach is not restarted.
    @Test func aStaleStudyStaysLazyWhileItsAccessIsOff() async throws {
        let rig = try Self.rig()
        defer { try? FileManager.default.removeItem(at: rig.dir) }
        let b = rig.fleet.manager(for: Self.b)

        rig.fleet.syncHandshake(shown: [Self.a, Self.b])
        await settle(b, to: .running(port: Self.restartPort))

        #expect(rig.fleet.staleProjects.contains(Self.b))
        #expect(b.state == .running(port: 5001), "a private study was restarted for nothing")
    }

    /// …and neither is one whose access is on but whose window is closed:
    /// outside the roster it is out of scope, so nobody can read it.
    @Test func aStaleStudyWithNoWindowIsNotRestarted() async throws {
        let rig = try Self.rig()
        defer { try? FileManager.default.removeItem(at: rig.dir) }
        let b = rig.fleet.manager(for: Self.b)
        rig.access.on.insert(Self.b)

        rig.fleet.syncHandshake(shown: [Self.a])
        await settle(b, to: .running(port: Self.restartPort))

        #expect(rig.fleet.staleProjects.contains(Self.b))
        #expect(b.state == .running(port: 5001))
    }

    /// The control: a study that is not stale is exposed at once, with no
    /// restart, exactly as before.
    @Test func aCurrentStudyGivenAccessIsOpenedAtOnceWithoutARestart() async throws {
        let rig = try Self.rig()
        defer { try? FileManager.default.removeItem(at: rig.dir) }
        // A third study that arrived after Anonymise went on, so it was
        // spawned on the current environment and was never marked.
        let c = UUID()
        let manager = rig.fleet.manager(for: c)
        manager.instance.state = .running(port: 5002)
        manager.instance.currentProjectPath = "/p/\(c)"
        manager.instance.mcpInstanceID = "inst-c"
        manager.instance.mcpToken = "tok-c"
        manager.setProjectKeyForTest("key-\(c)")
        #expect(rig.fleet.staleProjects.contains(c) == false)
        rig.access.on.insert(c)

        rig.fleet.syncHandshake(shown: [Self.a, Self.b, c])
        // Read before suspending: `a`'s own restart is still in flight and its
        // state changes re-sync the handshake from the (empty) real roster.
        #expect(rig.scope.opened(c))
        #expect(handshakeNames(rig, c))
        await settle(manager, to: .running(port: Self.restartPort))

        #expect(manager.state == .running(port: 5002), "a current study was restarted for nothing")
    }
}
