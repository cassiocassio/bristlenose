import Foundation
import Testing
@testable import Bristlenose

/// The handshake file is a credential-class write (design-mcp-extension §3.1):
/// 0600, atomic, symlink-refusing, no project path in the payload. These
/// tests pin the write path against a temp directory — never the real
/// Application Support.
@Suite("MCPHandshake write path")
struct MCPHandshakeTests {

    private static func makeTempDir() -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("MCPHandshakeTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private static func cleanup(_ dir: URL) {
        try? FileManager.default.removeItem(at: dir)
    }

    @Test func payload_carriesSchemaPortTokenInstanceAndTimestamp_andNoProject() throws {
        let data = MCPHandshake.payload(
            port: 58735, token: "tok", instanceID: "abc123",
            now: Date(timeIntervalSince1970: 1_790_000_000)
        )
        let object = try #require(
            try JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        #expect(object["schema"] as? Int == 1)
        #expect(object["port"] as? Int == 58735)
        #expect(object["token"] as? String == "tok")
        #expect(object["instance_id"] as? String == "abc123")
        #expect(object["updated_at"] as? String != nil)
        // No project field, EVER — MCPTokenStore.accountKey hashes the path
        // precisely so folder names never become readable metadata.
        #expect(object["project"] == nil)
        #expect(object["path"] == nil)
        #expect(object.count == 5)
    }

    @Test func write_landsAtMode0600_withTheExpectedContent() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        #expect(MCPHandshake.write(port: 1234, token: "t", instanceID: "i", directory: dir))
        let url = dir.appendingPathComponent(MCPHandshake.filename)
        let attrs = try FileManager.default.attributesOfItem(atPath: url.path)
        let mode = (attrs[.posixPermissions] as? NSNumber)?.uint16Value ?? 0
        #expect(mode == 0o600, "handshake must land at 0600, got \(String(mode, radix: 8))")

        let object = try #require(
            try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        )
        #expect(object["port"] as? Int == 1234)
        #expect(object["instance_id"] as? String == "i")
    }

    @Test func write_replacesAPlantedSymlink_withoutWritingThroughIt() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        // Attack from the spike (design §5c): pre-plant
        // mcp-handshake.json → somewhere-that-syncs-off-machine. The write
        // must never follow it — the rename replaces the symlink itself and
        // the target stays untouched.
        let target = dir.appendingPathComponent("dropbox-target.json")
        FileManager.default.createFile(atPath: target.path, contents: Data())
        let final = dir.appendingPathComponent(MCPHandshake.filename)
        try FileManager.default.createSymbolicLink(at: final, withDestinationURL: target)

        #expect(MCPHandshake.write(port: 9, token: "t", instanceID: "i", directory: dir))

        let targetData = try Data(contentsOf: target)
        #expect(targetData.isEmpty, "the symlink target must never receive the bearer")
        let resourceValues = try final.resourceValues(forKeys: [.isSymbolicLinkKey])
        #expect(resourceValues.isSymbolicLink != true, "the planted symlink must be replaced")
        let object = try JSONSerialization.jsonObject(
            with: Data(contentsOf: final)
        ) as? [String: Any]
        #expect(object?["port"] as? Int == 9)
    }

    @Test func write_overwritesAPreviousHandshake() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        #expect(MCPHandshake.write(port: 1, token: "a", instanceID: "one", directory: dir))
        #expect(MCPHandshake.write(port: 2, token: "b", instanceID: "two", directory: dir))
        let url = dir.appendingPathComponent(MCPHandshake.filename)
        let object = try JSONSerialization.jsonObject(
            with: Data(contentsOf: url)
        ) as? [String: Any]
        #expect(object?["port"] as? Int == 2)
        #expect(object?["instance_id"] as? String == "two")
    }

    @Test func remove_deletesTheFile_andIsSilentWhenAbsent() {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        MCPHandshake.write(port: 1, token: "a", instanceID: "one", directory: dir)
        MCPHandshake.remove(directory: dir)
        let url = dir.appendingPathComponent(MCPHandshake.filename)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        MCPHandshake.remove(directory: dir)  // absent — must not trap or log-spam
    }

    @Test func write_leavesNoTempFilesBehind() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        #expect(MCPHandshake.write(port: 1, token: "a", instanceID: "one", directory: dir))
        let leftovers = try FileManager.default.contentsOfDirectory(atPath: dir.path)
            .filter { $0.contains(".tmp-") }
        #expect(leftovers.isEmpty, "temp files must be renamed or unlinked: \(leftovers)")
    }
}
