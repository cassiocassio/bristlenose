import Foundation
import Testing
@testable import Bristlenose

/// N195 and N194 (owner calls, 7 Nov 2026), both about what the handshake says.
///
/// N195: two shared studies in folders with the same name (two clients' `interviews`) were offered
/// to an agent under the same name, with only opaque keys to tell them apart, while the sidebar
/// already tells them apart. The handshake now carries the sidebar's own label.
///
/// N194: when the handshake cannot be written the proxies read "closed" (it fails closed), but the
/// antenna still showed the study as shared. It now follows what a proxy can read.
@MainActor
@Suite("The handshake names studies as the sidebar does and the antenna follows the file")
struct ServeFleetHandshakeLabelTests {
    private static let a = UUID()
    private static let b = UUID()

    private final class Access { var on: Set<UUID> = [] }

    private static func rig(directory: URL) -> (fleet: ServeFleet, access: Access) {
        let fleet = ServeFleet(screenReading: ScreenReadingStore(), makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 9_998)))
        })
        let access = Access()
        fleet.handshakeDirectory = directory
        fleet.agentAccessByID = { [access] id in access.on.contains(id) }
        fleet.applyAgentScope = { _, _ in }
        // Both studies live in a folder called `interviews`, as two clients' do.
        for (id, port, parent) in [(a, 5000, "acme"), (b, 5001, "zeta")] {
            let m = fleet.manager(for: id)
            m.instance.state = .running(port: port)
            m.instance.currentProjectPath = "/clients/\(parent)/interviews"
            m.instance.mcpInstanceID = "inst-\(id)"
            m.instance.mcpToken = "tok-\(id)"
            m.setProjectKeyForTest("key-\(id)")
        }
        fleet.frontedProject = a
        access.on = [a, b]
        return (fleet, access)
    }

    private static func tempDir() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private static func names(in dir: URL) throws -> [String] {
        let data = try Data(contentsOf: dir.appendingPathComponent(MCPHandshake.filename))
        let object = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        let projects = try #require(object["projects"] as? [[String: Any]])
        return projects.compactMap { $0["name"] as? String }.sorted()
    }

    @Test func twoStudiosInSameNamedFoldersAreOfferedUnderTheirSidebarNames() throws {
        let dir = try Self.tempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let (fleet, _) = Self.rig(directory: dir)
        fleet.nameByID = { [a = Self.a] id in id == a ? "interviews" : "interviews 2" }

        fleet.syncHandshake(shown: [Self.a, Self.b])

        #expect(try Self.names(in: dir) == ["interviews", "interviews 2"])
    }

    @Test func withoutASidebarNameTheFolderNameIsStillUsed() throws {
        let dir = try Self.tempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let (fleet, _) = Self.rig(directory: dir)
        fleet.nameByID = nil

        fleet.syncHandshake(shown: [Self.a, Self.b])

        #expect(try Self.names(in: dir) == ["interviews", "interviews"])
    }

    @Test func aWrittenHandshakeShowsTheStudyAsShared() throws {
        let dir = try Self.tempDir()
        defer { try? FileManager.default.removeItem(at: dir) }
        let (fleet, _) = Self.rig(directory: dir)

        fleet.syncHandshake(shown: [Self.a, Self.b])

        #expect(fleet.isExposed(Self.a), "control: a written file shows it as shared")
        #expect(fleet.isExposed(Self.b))
    }

    @Test func aHandshakeThatCannotBeWrittenDoesNotShowTheStudyAsShared() throws {
        // A directory that cannot be created: its parent is a regular file.
        let parent = try Self.tempDir()
        defer { try? FileManager.default.removeItem(at: parent) }
        let file = parent.appendingPathComponent("not-a-directory")
        try Data("x".utf8).write(to: file)
        let (fleet, _) = Self.rig(directory: file.appendingPathComponent("inside"))

        fleet.syncHandshake(shown: [Self.a, Self.b])

        #expect(!fleet.isExposed(Self.a), "no file was written, so a proxy reads closed")
        #expect(fleet.handshakeProjectPaths.isEmpty)
    }
}
