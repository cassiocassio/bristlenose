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

    /// Block until the wall-clock second changes (at most ~1 s).
    private static func waitForTheNextSecond() {
        let start = Int(Date().timeIntervalSince1970)
        while Int(Date().timeIntervalSince1970) == start { usleep(10_000) }
    }

    @Test func write_landsAtMode0600_withTheExpectedContent() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        #expect(MCPHandshake.write(entries: [Self.entry("i", port: 1234)], directory: dir))
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

        #expect(MCPHandshake.write(entries: [Self.entry("i", port: 9)], directory: dir))

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

        #expect(MCPHandshake.write(entries: [Self.entry()], directory: dir))
        #expect(MCPHandshake.write(entries: [Self.entry("two", port: 2)], directory: dir))
        let url = dir.appendingPathComponent(MCPHandshake.filename)
        let object = try JSONSerialization.jsonObject(
            with: Data(contentsOf: url)
        ) as? [String: Any]
        #expect(object?["port"] as? Int == 2)
        #expect(object?["instance_id"] as? String == "two")
    }

    /// One realistic entry, so the write tests exercise the shape production
    /// actually writes rather than a fabricated `key: ""`.
    private static func entry(_ name: String = "one", port: Int = 1) -> HandshakeExposure.Entry {
        HandshakeExposure.Entry(key: "k-\(name)", name: name, path: "/p/\(name)",
                                port: port, token: "a", instanceID: name)
    }

    @Test func remove_deletesTheFile_andIsSilentWhenAbsent() {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        MCPHandshake.write(entries: [Self.entry()], directory: dir)
        MCPHandshake.remove(directory: dir)
        let url = dir.appendingPathComponent(MCPHandshake.filename)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        MCPHandshake.remove(directory: dir)  // absent — must not trap or log-spam
    }

    @Test func write_leavesNoTempFilesBehind() throws {
        let dir = Self.makeTempDir()
        defer { Self.cleanup(dir) }

        #expect(MCPHandshake.write(entries: [Self.entry()], directory: dir))
        let leftovers = try FileManager.default.contentsOfDirectory(atPath: dir.path)
            .filter { $0.contains(".tmp-") }
        #expect(leftovers.isEmpty, "temp files must be renamed or unlinked: \(leftovers)")
    }
    /// The F9 pin, moved onto the writer production actually uses. It sat on
    /// `payload(port:token:instanceID:)` until 20 Aug 2026 — an overload with
    /// no production caller — so it was green while guarding nothing.
    @Test func schemaTwoCarriesNoPath() throws {
        let entry = HandshakeExposure.Entry(
            key: "a3f9c210", name: "Acme Q3", path: "/Users/r/clients/Acme Q3",
            port: 8150, token: "tok", instanceID: "inst")
        let object = try #require(
            try JSONSerialization.jsonObject(with: MCPHandshake.payload(entries: [entry]))
                as? [String: Any])
        #expect(object["schema"] as? Int == 2)
        #expect(object["path"] == nil)
        #expect(object["project"] == nil)
        let projects = try #require(object["projects"] as? [[String: Any]])
        #expect(projects.count == 1)
        #expect(projects[0]["path"] == nil)
        #expect(projects[0]["key"] as? String == "a3f9c210")
        // Schema-1 keys still ride along for a .mcpb installed weeks ago.
        #expect(object["port"] as? Int == 8150)
    }

    /// An empty set writes no schema-1 keys, which an old proxy reads as
    /// "not open" — the correct answer, not a dangling port.
    @Test func anEmptySetAdvertisesNothing() throws {
        let object = try #require(
            try JSONSerialization.jsonObject(with: MCPHandshake.payload(entries: []))
                as? [String: Any])
        #expect(object["port"] == nil)
        #expect(object["token"] == nil)
        #expect((object["projects"] as? [[String: Any]])?.isEmpty == true)
    }


    // MARK: - Team group selection (design-mcp-native-proxy §6.4)

    @Test func teamGroup_picksTheTeamPrefixedEntry_notTheBackgroundAssetsGroup() {
        #expect(MCPHandshake.teamGroup(from: ["group.app.bristlenose", "Z56GZVA2QB.app.bristlenose"])
                == "Z56GZVA2QB.app.bristlenose")
    }

    @Test func teamGroup_isNilWhenOnlyTheGroupDotGroupIsPresent() {
        #expect(MCPHandshake.teamGroup(from: ["group.app.bristlenose"]) == nil)
        #expect(MCPHandshake.teamGroup(from: []) == nil)
    }

    @Test func teamGroup_ignoresAnotherAppsTeamGroup() {
        #expect(MCPHandshake.teamGroup(from: ["Z56GZVA2QB.app.other"]) == nil)
    }

    // MARK: - Both copies (D4: fail closed on the group copy)

    @Test func writeBoth_writesIdenticalCopies_andReadsBack() throws {
        let data = Self.makeTempDir(), group = Self.makeTempDir()
        defer { Self.cleanup(data); Self.cleanup(group) }
        // `updated_at` has one-second resolution, so wait for the clock to
        // tick between the two writes. That is the case that flaked when each
        // copy built its own payload (4 Oct 2026); forcing it every run makes
        // the test deterministic rather than lucky.
        let ok = MCPHandshake.writeBoth(entries: [Self.entry("a"), Self.entry("b", port: 2)],
                                        data: data, group: group) { bytes, dir in
            let written = MCPHandshake.writeBytes(bytes, directory: dir)
            if dir == group { Self.waitForTheNextSecond() }
            return written
        }
        #expect(ok)
        let one = try Data(contentsOf: data.appendingPathComponent(MCPHandshake.filename))
        let two = try Data(contentsOf: group.appendingPathComponent(MCPHandshake.filename))
        #expect(one == two)
        let names = (try JSONSerialization.jsonObject(with: two) as? [String: Any])?["projects"]
            as? [[String: Any]]
        #expect(names?.compactMap { $0["name"] as? String } == ["a", "b"])
    }

    @Test func writeBoth_removesTheGroupCopy_whenItCannotBeRewritten() throws {
        let data = Self.makeTempDir(), group = Self.makeTempDir()
        defer { Self.cleanup(data); Self.cleanup(group) }
        // A previous set naming a project that has since been unshared.
        #expect(MCPHandshake.writeOne(entries: [Self.entry("unshared")], directory: group))
        let stale = group.appendingPathComponent(MCPHandshake.filename)
        #expect(FileManager.default.fileExists(atPath: stale.path))

        let ok = MCPHandshake.writeBoth(entries: [], data: data, group: group) { bytes, dir in
            dir == group ? false : MCPHandshake.writeBytes(bytes, directory: dir)
        }
        #expect(ok)
        #expect(!FileManager.default.fileExists(atPath: stale.path))
        #expect(FileManager.default.fileExists(atPath: data.appendingPathComponent(MCPHandshake.filename).path))
    }
}
